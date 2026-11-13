"""Bounded, allowlisted, evidence-recording HTTP for the survey engine.

Every response body is stored content-addressed with its SHA-256 before it is
interpreted. `replay` mode reads only stored bodies and marks them as reused, so
a cached answer can never be reported as a live one. A failed live request is a
failure: there is no fallback to old bytes.

Queries are built by harness code from fixed templates and validated integer
IDs. Nothing here accepts a query, URL or path written by a model.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path

GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap/sync"
GAIA_BULK = "https://cdn.gea.esac.esa.int/Gaia/gdr3/"
SIMBAD_TAP_MIRRORS = (
    "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
    "https://simbad.cfa.harvard.edu/simbad/sim-tap/sync",
)
VIZIER_ASU_MIRRORS = (
    "https://vizier.cds.unistra.fr/viz-bin/asu-tsv",
    "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv",
)
ALLOWED_HOSTS = frozenset(
    {
        "gea.esac.esa.int",
        "cdn.gea.esac.esa.int",
        "simbad.cds.unistra.fr",
        "simbad.cfa.harvard.edu",
        "vizier.cds.unistra.fr",
        "vizier.cfa.harvard.edu",
    }
)
USER_AGENT = "UniverseSurveyHarness/1.0 (read-only scientific audit)"
# Row counts at which public TAP services silently truncate synchronous output.
SUSPECT_ROW_CAPS = frozenset({2000, 50000, 3000000})


class NetError(RuntimeError):
    """A request or integrity failure. Callers must treat coverage as incomplete."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS or u.username or u.password or u.port not in (None, 443):
        raise NetError("URL must be HTTPS on an allowlisted public archive host")
    return url


def safe_ids(values) -> list[str]:
    """Lossless decimal Gaia source IDs, deduplicated and sorted numerically."""
    out = set()
    for v in values:
        if isinstance(v, (bool, float)):
            raise NetError("source IDs must be exact integers or decimal strings")
        s = str(v).strip()
        if not re.fullmatch(r"[0-9]{1,19}", s) or not 0 < int(s) < 2**63:
            raise NetError(f"invalid source ID {s!r}")
        out.add(s)
    return sorted(out, key=int)


class _AllowlistedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    """mode: 'live' fetches and stores; 'replay' serves stored bodies only."""

    def __init__(self, evidence_dir, mode="live", timeout=120, retries=2, max_bytes=512 * 1024 * 1024):
        if mode not in ("live", "replay"):
            raise ValueError("mode must be live or replay")
        if not 1 <= timeout <= 1800 or not 0 <= retries <= 5:
            raise ValueError("invalid request bounds")
        self.dir = Path(evidence_dir)
        self.mode, self.timeout, self.retries, self.max_bytes = mode, timeout, retries, max_bytes
        self.opener = urllib.request.build_opener(_AllowlistedRedirect())
        self.log = []
        self._mirror = {}

    # -- storage -----------------------------------------------------------
    def _key(self, request: dict) -> str:
        return sha256(json.dumps(request, sort_keys=True).encode())

    def _load(self, key):
        meta_path = self.dir / f"{key}.json"
        if not meta_path.exists():
            raise NetError(f"no recorded evidence for request {key[:12]} (replay mode)")
        meta = json.loads(meta_path.read_text())
        raw = (self.dir / meta["body_file"]).read_bytes()
        if sha256(raw) != meta["sha256"]:
            raise NetError("stored evidence does not match its recorded hash")
        return raw, dict(meta, cache_reused=True)

    def _store(self, key, request, raw, extra):
        self.dir.mkdir(parents=True, exist_ok=True)
        digest = sha256(raw)
        body = f"{key[:16]}.{digest[:16]}.body"
        (self.dir / body).write_bytes(raw)
        meta = dict(
            extra,
            request=request,
            sha256=digest,
            bytes=len(raw),
            body_file=body,
            fetched_at_utc=utc_now(),
            cache_reused=False,
        )
        tmp = self.dir / f"{key}.json.tmp"
        tmp.write_text(json.dumps(meta, indent=1))
        tmp.replace(self.dir / f"{key}.json")
        return meta

    # -- transport ---------------------------------------------------------
    def fetch(self, url, form=None, label=""):
        """GET (form=None) or POST form-encoded. Returns (bytes, provenance)."""
        check_url(url)
        request = {"url": url, "form": form}
        key = self._key(request)
        if self.mode == "replay":
            raw, meta = self._load(key)
        else:
            raw, meta = self._live(url, form, key, request)
        prov = {
            k: meta.get(k)
            for k in ("sha256", "bytes", "fetched_at_utc", "cache_reused", "http_status", "host", "seconds")
        }
        prov["evidence"] = key[:16]
        prov["label"] = label
        self.log.append(prov)
        return raw, prov

    def _live(self, url, form, key, request):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        last = None
        for attempt in range(self.retries + 1):
            started = time.time()
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
                with self.opener.open(req, timeout=self.timeout) as resp:
                    check_url(resp.geturl())
                    raw = resp.read(self.max_bytes + 1)
                    if len(raw) > self.max_bytes:
                        raise NetError("response exceeds byte cap")
                    declared = resp.headers.get("Content-Length")
                    if declared and declared.isdigit() and int(declared) != len(raw):
                        raise NetError("incomplete HTTP body")
                    return raw, self._store(
                        key,
                        request,
                        raw,
                        {
                            "http_status": resp.status,
                            "host": urllib.parse.urlsplit(url).hostname,
                            "seconds": round(time.time() - started, 3),
                        },
                    )
            except urllib.error.HTTPError as exc:
                detail = exc.read(2000).decode("utf-8", "replace")
                last = NetError(f"HTTP {exc.code} from {urllib.parse.urlsplit(url).hostname}: {detail[:300]}")
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    raise last from None
            except (TimeoutError, urllib.error.URLError, OSError, HTTPException) as exc:
                last = NetError(f"network failure: {type(exc).__name__}: {exc}")
            if attempt < self.retries:
                time.sleep(min(20, 2 ** (attempt + 1)))
        raise last

    # -- protocol helpers --------------------------------------------------
    def tap_csv(self, endpoint, query, label="", expect_rows=None):
        """Run one harness-built ADQL SELECT and return (header, rows, provenance).

        CSV carries no overflow marker, so a result whose size equals a known
        server cap is refused unless the caller states the exact expected count.
        """
        if not query.lstrip().upper().startswith("SELECT ") or len(query) > 200000:
            raise NetError("only bounded SELECT queries are supported")
        raw, prov = self.fetch(
            endpoint, {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": query}, label
        )
        head = raw[:200].lstrip()
        if head.startswith(b"<"):
            raise NetError("TAP returned a non-CSV body: " + raw[:300].decode("utf-8", "replace"))
        reader = csv.reader(io.StringIO(raw.decode("utf-8")))
        try:
            header = next(reader)
        except StopIteration:
            raise NetError("empty TAP response") from None
        rows = [r for r in reader if r]
        if any(len(r) != len(header) for r in rows):
            raise NetError("ragged CSV rows in TAP response")
        if expect_rows is not None and len(rows) != expect_rows:
            raise NetError(f"TAP returned {len(rows)} rows, expected {expect_rows}")
        if expect_rows is None and len(rows) in SUSPECT_ROW_CAPS:
            raise NetError(f"TAP result has exactly {len(rows)} rows: possible silent truncation")
        prov["rows"] = len(rows)
        return header, rows, prov

    def first_working(self, endpoints, attempt):
        """Try mirrors in order. Returns the first success; raises the last failure."""
        last = None
        preferred = self._mirror.get(tuple(endpoints))
        for ep in ([preferred] if preferred else []) + [e for e in endpoints if e != preferred]:
            try:
                result = attempt(ep)
                self._mirror[tuple(endpoints)] = ep
                return result
            except NetError as exc:
                last = exc
        raise last


def tsv_table(raw: bytes):
    """Parse a VizieR ASU TSV body into (header, rows). Comment and rule lines are dropped."""
    text = raw.decode("utf-8", "replace")
    if "<html" in text[:2000].lower():
        raise NetError("VizieR returned an HTML page instead of a table")
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    # Layout: column names, units (often blank), a rule of dashes, then data.
    rule = next((i for i, ln in enumerate(lines) if ln.strip() and set(ln.replace("\t", "").strip()) == {"-"}), None)
    if rule is None or rule < 2:
        return [], []
    header = lines[rule - 2].split("\t")
    rows = [ln.split("\t") for ln in lines[rule + 1 :] if ln.strip()]
    return header, [r for r in rows if len(r) == len(header)]
