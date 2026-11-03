"""Evidence verifier: the reward signal for the agent loop.

A verdict only counts if every claim cites (call_id, field, value) triples that
match data the tools actually returned in this investigation. Verdict-specific
rules then check that the right kind of evidence exists. This is what makes the
loop safe to optimize: a model cannot score by inventing citations.
"""

from __future__ import annotations

from harness2.agent.schema import CONFIDENCE, LITERATURE_TOOLS, VERDICTS, finite_number

MATCH_TOOLS = frozenset({"known_catalogs", "vizier_crossmatch", "simbad_lookup", "ads_search"})
QUALITY_TOOLS = frozenset({"gaia_quality", "nss_orbit"})


def find_values(data, field):
    """All values stored under key `field` anywhere in a nested structure."""
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == field:
                out.append(v)
                if isinstance(v, list):
                    out.extend(v)
            out.extend(find_values(v, field))
    elif isinstance(data, list):
        for item in data:
            out.extend(find_values(item, field))
    return out


def values_match(claimed, actual) -> bool:
    if isinstance(claimed, bool) or isinstance(actual, bool):
        return claimed is actual
    if finite_number(claimed) and finite_number(actual):
        return abs(claimed - actual) <= max(1e-9, 1e-3 * abs(actual))
    if isinstance(claimed, str) and isinstance(actual, str):
        return claimed.strip().casefold() == actual.strip().casefold()
    if claimed is None and actual is None:
        return True
    return False


def _shape_errors(v):
    if not isinstance(v, dict):
        return ["verdict is not an object"]
    errs = []
    if v.get("verdict") not in VERDICTS:
        errs.append(f"unknown verdict {v.get('verdict')!r}")
    if v.get("confidence") not in CONFIDENCE:
        errs.append("confidence must be low, medium or high")
    for key, limit in (("summary", 600), ("next_test", 300)):
        if not isinstance(v.get(key), str) or len(v[key]) > limit:
            errs.append(f"{key} must be a string up to {limit} chars")
    claims = v.get("claims")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
        errs.append("claims must be a list of 1..8 items")
    return errs


def verify(verdict, log, source_id) -> dict:
    errors = _shape_errors(verdict)
    by_id = {e["call_id"]: e for e in log}
    checked = failed = 0
    cited_tools = []  # (tool, field, value) for verified evidence only
    if not errors:
        for i, claim in enumerate(verdict["claims"]):
            ev_list = claim.get("evidence") if isinstance(claim, dict) else None
            if not isinstance(claim, dict) or not isinstance(claim.get("statement"), str) or not ev_list:
                errors.append(f"claim {i}: needs a statement and at least one evidence item")
                continue
            for ev in ev_list:
                checked += 1
                problem = _check_evidence(ev, by_id, source_id)
                if problem:
                    failed += 1
                    errors.append(f"claim {i}: {problem}")
                else:
                    cited_tools.append((by_id[ev["call_id"]]["tool"], ev["field"], ev["value"]))
        errors.extend(_verdict_rules(verdict["verdict"], cited_tools, log))
    return {"valid": not errors, "errors": errors, "evidence_checked": checked, "evidence_failed": failed}


def _check_evidence(ev, by_id, source_id):
    if not isinstance(ev, dict) or not {"call_id", "field", "value"} <= set(ev):
        return "evidence must have call_id, field and value"
    entry = by_id.get(ev["call_id"])
    if entry is None:
        return f"{ev['call_id']} was never called"
    if entry["args"].get("source_id") != source_id:
        return f"{ev['call_id']} concerns another source"
    if not entry["ok"]:
        # The only true statement about a failed call is that it failed.
        if ev["field"] == "ok" and ev["value"] is False:
            return None
        return f"{ev['call_id']} failed and has no data"
    actual = find_values(entry["data"], ev["field"])
    if not actual:
        return f"{ev['call_id']} returned no field {ev['field']!r}"
    if not any(values_match(ev["value"], a) for a in actual):
        return f"{ev['call_id']}.{ev['field']} is not {ev['value']!r}"
    return None


def _verdict_rules(kind, cited, log):
    tools_ok = {e["tool"] for e in log if e["ok"]}
    if kind == "PUBLISHED_PRIOR":
        if not any(t in MATCH_TOOLS and f == "matched" and v is True for t, f, v in cited):
            return ["PUBLISHED_PRIOR must cite matched=true from a catalog, SIMBAD or ADS call"]
    elif kind in ("LIKELY_BLEND_OR_LUMINOUS", "LIKELY_SPURIOUS_ORBIT"):
        if not any(t in QUALITY_TOOLS for t, _, _ in cited):
            return [f"{kind} must cite gaia_quality or nss_orbit data"]
    elif kind == "NEEDS_FOLLOWUP":
        missing = []
        if "gaia_quality" not in tools_ok:
            missing.append("gaia_quality")
        if not tools_ok & LITERATURE_TOOLS:
            missing.append("a literature tool")
        if missing:
            return ["NEEDS_FOLLOWUP requires successful " + " and ".join(missing)]
        if any(e["ok"] and e["data"].get("matched") is True for e in log if e["tool"] in MATCH_TOOLS):
            return ["NEEDS_FOLLOWUP contradicts a matched=true literature result in this investigation"]
    elif kind == "INSUFFICIENT_DATA":
        if not any(not e["ok"] for e in log):
            return ["INSUFFICIENT_DATA requires at least one failed tool call"]
    return []
