"""Read-only, argument-validated tools for the follow-up agent.

The model never writes ADQL, URLs or file paths. Each tool takes a Gaia source
ID (which must be the candidate under investigation) plus at most one
allowlisted parameter, and returns compact JSON. Every call is logged with an
ID so the verifier can check that a verdict only cites data that was actually
returned.

Backends:
  live    - public archives via PublicSkyConnector (plus ADS if a token is set)
  replay  - recorded fixtures only; no network, deterministic, zero cost
  record  - live, and also writes each response as a replay fixture
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from harness2.agent.schema import TOOL_NAMES, canonical_hash
from harness2.core.guards import ROOT

ADS_ENDPOINT = "https://api.adsabs.harvard.edu/v1/search/query"
SAFE_TERMS = re.compile(r"[A-Za-z0-9 .+\-]{0,80}")
MAX_RESULT_CHARS = 3000
# Fields that would leak the pipeline's own disposition (and so control labels).
LABEL_FIELDS = {"status", "novelty_status", "reasons", "evidence", "review_links", "partition"}


class ToolError(Exception):
    """A call the agent made incorrectly or that the backend could not serve."""


def load_policy() -> dict:
    return json.loads((ROOT / "policy/agent_tools.json").read_text())


def _source_id(value) -> str:
    sid = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,20}", sid) or int(sid) <= 0:
        raise ToolError("source_id must be a decimal Gaia DR3 source ID string")
    return sid


# ---------------------------------------------------------------- backends


class ReplayBackend:
    """Serves recorded responses. A missing fixture is an error, never a guess."""

    def __init__(self, fixture_dir):
        self.dir = Path(fixture_dir)

    def key(self, tool, args):
        return canonical_hash({"tool": tool, "args": args})

    def fetch(self, tool, args):
        path = self.dir / f"{self.key(tool, args)}.json"
        if not path.exists():
            raise ToolError(f"no recorded fixture for {tool} {args}")
        fixture = json.loads(path.read_text())
        if fixture.get("tool") != tool or fixture.get("args") != args:
            raise ToolError("fixture does not match request")
        return fixture["data"], dict(fixture.get("provenance", {}), mode="replay")


class LiveBackend:
    def __init__(self, connector, policy, ads_token=None, timeout=30):
        self.connector = connector
        self.policy = policy
        self.ads_token = ads_token
        self.timeout = timeout
        self._catalog_cache = {}

    def fetch(self, tool, args):
        from harness2.universe.connectors.public_archives import ArchiveError

        try:
            return getattr(self, "_" + tool)(**args)
        except ArchiveError as exc:
            raise ToolError(f"archive error: {exc}") from None

    def _gaia_quality(self, source_id):
        cols = ",".join(self.policy["gaia_quality_columns"])
        release = self.policy["gaia_release"]
        if not re.fullmatch(r"gaiadr[0-9]+", release):
            raise ToolError("invalid gaia_release in policy")
        q = f"SELECT {cols} FROM {release}.gaia_source WHERE source_id = {source_id}"
        result = self.connector.query_gaia_dr3_tap(q, 2, required=("source_id",))
        row = result.rows[0] if result.rows else None
        data = {"found": row is not None, **(row or {})}
        return data, _prov(result.provenance)

    def _simbad_lookup(self, source_id):
        from harness2.universe.connectors.public_archives import SIMBAD_TAP

        q = (
            "SELECT b.oid, b.main_id, b.otype, b.nbref FROM ident AS i JOIN basic AS b "
            f"ON i.oidref = b.oid WHERE i.id = 'Gaia DR3 {source_id}'"
        )
        basic = self.connector.tap(SIMBAD_TAP, q, 5, required=("main_id", "otype"))
        if not basic.rows:
            return {"found": False, "matched": False, "bibcodes": [], "compact_companion_bibcodes": []}, _prov(
                basic.provenance
            )
        row = basic.rows[0]
        oid = int(row["oid"])
        refs = self.connector.tap(
            SIMBAD_TAP,
            "SELECT TOP 200 r.bibcode FROM has_ref AS h JOIN ref AS r ON h.oidbibref = r.oidbib "
            f"WHERE h.oidref = {oid}",
            200,
            required=("bibcode",),
        )
        bibcodes = sorted({r["bibcode"] for r in refs.rows if r.get("bibcode")})
        known = self.policy["compact_companion_bibcodes"]
        hits = [b for b in bibcodes if b in known]
        data = {
            "found": True,
            "main_id": row["main_id"],
            "otype": row["otype"],
            "nbref": row.get("nbref"),
            "bibcodes": bibcodes[:20],
            "compact_companion_bibcodes": hits,
            "matched": bool(hits),
        }
        return data, _prov(refs.provenance)

    def _vizier_crossmatch(self, source_id, catalog):
        from harness2.universe.connectors.public_archives import VIZIER_TAP

        spec = self.policy["vizier_catalogs"][catalog]
        if catalog not in self._catalog_cache:
            # Small curated tables: fetch the ID column once, match locally.
            q = f'SELECT "{spec["id_column"]}" AS source_id FROM "{spec["table"]}"'
            result = self.connector.tap(VIZIER_TAP, q, 10000, required=("source_id",))
            ids = {str(r["source_id"]) for r in result.rows if r.get("source_id")}
            self._catalog_cache[catalog] = (ids, _prov(result.provenance))
        ids, prov = self._catalog_cache[catalog]
        return {
            "catalog": catalog,
            "table": spec["table"],
            "rows_checked": len(ids),
            "matched": source_id in ids,
        }, prov

    def _ads_search(self, source_id, extra_terms=""):
        if not self.ads_token:
            raise ToolError("ads_search unavailable: set ADS_API_TOKEN")
        query = f'full:"{source_id}"' + (f" AND ({extra_terms})" if extra_terms else "")
        url = ADS_ENDPOINT + "?" + urllib.parse.urlencode({"q": query, "fl": "bibcode,title,year", "rows": 10})
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.ads_token}"})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(2 * 1024 * 1024 + 1)
        except OSError as exc:
            raise ToolError(f"ADS request failed: {type(exc).__name__}") from None
        if len(raw) > 2 * 1024 * 1024:
            raise ToolError("ADS response too large")
        body = json.loads(raw)["response"]
        docs = [
            {"bibcode": d.get("bibcode"), "year": d.get("year"), "title": (d.get("title") or [""])[0][:200]}
            for d in body.get("docs", [])
        ]
        data = {"query": query, "num_found": body.get("numFound", 0), "docs": docs, "matched": bool(docs)}
        return data, {"endpoint": ADS_ENDPOINT, "query": query, "mode": "live"}


class RecordingBackend:
    """Live fetch that also writes a replay fixture, so reruns cost nothing."""

    def __init__(self, inner, fixture_dir):
        self.inner = inner
        self.replay = ReplayBackend(fixture_dir)
        self.replay.dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, tool, args):
        data, prov = self.inner.fetch(tool, args)
        path = self.replay.dir / f"{self.replay.key(tool, args)}.json"
        path.write_text(json.dumps({"tool": tool, "args": args, "data": data, "provenance": prov}, indent=1))
        return data, prov


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        raise ToolError("redirect refused")


def _prov(p):
    keep = ("raw_sha256", "retrieval_record", "fetched_at_utc", "effective_url", "cache_reused", "row_count")
    return {k: p.get(k) for k in keep if k in p}


# ---------------------------------------------------------------- toolbox


TOOL_DESCRIPTIONS = {
    "nss_orbit": "Gaia DR3 two-body orbit for the candidate from this run: solution type, period, "
    "eccentricity, significance, goodness_of_fit, efficiency, photocentre a0 (mas), f_phot "
    "(photocentre mass function in solar masses; NOT the companion mass) and relative errors.",
    "gaia_quality": "Gaia DR3 gaia_source quality and blend diagnostics: ruwe, ipd_frac_multi_peak, "
    "ipd_gof_harmonic_amplitude, duplicated_source, bp_rp excess, radial velocity and rv scatter fields.",
    "simbad_lookup": "SIMBAD identification for the Gaia DR3 ID: main_id, otype, reference count, up to 20 "
    "bibcodes, and which bibcodes are known compact-companion papers (matched=true).",
    "vizier_crossmatch": "Check whether the source ID is in one curated published compact-companion catalog.",
    "known_catalogs": "Local list of known black holes, refuted candidates and previously studied sources.",
    "ads_search": "NASA ADS full-text search for the exact Gaia source ID, optionally ANDed with a few "
    "plain words. matched=true if any paper mentions the ID.",
}


class ToolBox:
    """Shared across investigations: holds run records, policy, backend and cache."""

    def __init__(self, records, raw_rows, backend, policy=None, known=None, ads_available=False):
        self.policy = policy or load_policy()
        self.backend = backend
        self.known = known
        self.ads_available = ads_available
        raw_by_key = {(r["source_id"], r["nss_solution_type"]): r for r in raw_rows}
        self.orbits = {}
        for rec in records:
            raw = raw_by_key.get((rec["source_id"], rec["nss_solution_type"]), {})
            self.orbits.setdefault(rec["source_id"], []).append(_orbit_view(rec, raw))
        self.cache = {}
        self.stats = {"backend_calls": 0, "cache_hits": 0}

    @classmethod
    def from_run(cls, run_dir, backend, **kw):
        run_dir = Path(run_dir)
        records = json.loads((run_dir / "records.json").read_text())
        raw_rows = json.loads((run_dir / "raw_rows.json").read_text())
        return cls(records, raw_rows, backend, **kw)

    def available(self, hidden=()):
        names = [n for n in TOOL_NAMES if n not in hidden]
        if not self.ads_available:
            names = [n for n in names if n != "ads_search"]
        if self.known is None:
            names = [n for n in names if n != "known_catalogs"]
        return names

    def specs(self, hidden=()):
        sid = {"source_id": {"type": "string", "description": "Gaia DR3 source_id as a decimal string"}}
        specs = []
        for name in self.available(hidden):
            props, required = dict(sid), ["source_id"]
            if name == "vizier_crossmatch":
                props["catalog"] = {"type": "string", "enum": sorted(self.policy["vizier_catalogs"])}
                required.append("catalog")
            if name == "ads_search":
                props["extra_terms"] = {"type": "string", "description": "Optional plain words, max 80 chars"}
            specs.append(
                {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS[name],
                    "parameters": {"type": "object", "properties": props, "required": required},
                }
            )
        return specs

    def session(self, source_id, hidden=(), blocked_catalogs=()):
        return Session(self, _source_id(source_id), tuple(hidden), tuple(blocked_catalogs))

    def _serve(self, tool, args):
        if tool == "nss_orbit":
            orbits = self.orbits.get(args["source_id"])
            if not orbits:
                return {"found": False, "solutions": []}, {"mode": "local_run_records"}
            return {"found": True, "solutions": orbits}, {"mode": "local_run_records"}
        if tool == "known_catalogs":
            entry = self.known.get(args["source_id"])
            data = {"matched": entry is not None}
            if entry:
                data.update(status=entry["status"], reason=entry["reason"])
            return data, {"mode": "bundled_catalogs"}
        key = canonical_hash({"tool": tool, "args": args})
        if key in self.cache:
            self.stats["cache_hits"] += 1
            return self.cache[key]
        self.stats["backend_calls"] += 1
        result = self.backend.fetch(tool, args)
        self.cache[key] = result
        return result


class Session:
    """One investigation. Owns the call log the verifier checks against."""

    def __init__(self, box, source_id, hidden, blocked):
        self.box, self.source_id, self.hidden, self.blocked = box, source_id, hidden, blocked
        self.log = []

    def specs(self):
        return self.box.specs(self.hidden)

    def call(self, name, args):
        call_id = f"c{len(self.log) + 1}"
        entry = {"call_id": call_id, "tool": name, "args": args, "ok": False}
        try:
            clean = self._validate(name, args)
            entry["args"] = clean
            data, prov = self.box._serve(name, clean)
            entry.update(ok=True, data=data, provenance=prov)
        except ToolError as exc:
            entry["error"] = str(exc)
        self.log.append(entry)
        return entry

    def _validate(self, name, args):
        if name not in self.box.available(self.hidden):
            raise ToolError(f"tool {name!r} is not available")
        if not isinstance(args, dict):
            raise ToolError("arguments must be an object")
        sid = _source_id(args.get("source_id", ""))
        if sid != self.source_id:
            raise ToolError(f"this investigation is limited to source_id {self.source_id}")
        clean = {"source_id": sid}
        extra = set(args) - {"source_id", "catalog", "extra_terms"}
        if extra:
            raise ToolError(f"unknown arguments {sorted(extra)}")
        if name == "vizier_crossmatch":
            cat = args.get("catalog")
            if cat not in self.box.policy["vizier_catalogs"]:
                raise ToolError(f"catalog must be one of {sorted(self.box.policy['vizier_catalogs'])}")
            if cat in self.blocked:
                raise ToolError(f"catalog {cat} is withheld for this evaluation")
            clean["catalog"] = cat
        elif "catalog" in args:
            raise ToolError("catalog only applies to vizier_crossmatch")
        if name == "ads_search":
            terms = str(args.get("extra_terms", "")).strip()
            if not SAFE_TERMS.fullmatch(terms):
                raise ToolError("extra_terms: letters, digits, spaces and . + - only, max 80 chars")
            if terms:
                clean["extra_terms"] = terms
        elif "extra_terms" in args:
            raise ToolError("extra_terms only applies to ads_search")
        return clean

    @staticmethod
    def render(entry) -> str:
        """Compact JSON for the model's context. Truncated to bound tokens."""
        shown = {k: entry[k] for k in ("call_id", "tool", "ok") if k in entry}
        shown["data" if entry["ok"] else "error"] = entry.get("data") if entry["ok"] else entry.get("error")
        text = json.dumps(shown, separators=(",", ":"), default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = text[: MAX_RESULT_CHARS - 20] + '..."TRUNCATED"}'
        return text


def _orbit_view(rec, raw):
    view = {k: v for k, v in rec.items() if k not in LABEL_FIELDS}
    for k in ("period", "eccentricity", "significance", "goodness_of_fit", "parallax", "flags"):
        if k in raw:
            try:
                view[k] = float(raw[k])
            except (TypeError, ValueError):
                view[k] = raw[k]
    return view


def default_ads_token():
    return os.getenv("ADS_API_TOKEN") or None
