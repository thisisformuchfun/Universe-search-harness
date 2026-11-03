"""Conservative prior-literature exclusion. Absence from these catalogs is not novelty."""

import json
import hashlib
from harness2.core.guards import ROOT

CATALOGS = (
    ("shahaf177.tsv", "GaiaDR3", 177, "J/MNRAS/518/2991/table2"),
    ("jayasinghe234.tsv", "Source", 234, "J/MNRAS/521/5927/table"),
)


def bundled_catalogs():
    known = json.loads((ROOT / "policy/known_objects.json").read_text())
    coverage = []
    manifest = json.loads((ROOT / "data/pilot/SNAPSHOT_MANIFEST.json").read_text())
    for filename, column, count, table in CATALOGS:
        p = ROOT / "data/pilot" / filename
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["files"][filename]:
            raise ValueError("Known-catalog snapshot hash mismatch")
        lines = [line for line in raw.decode().splitlines() if line.strip() and not line.startswith("#")]
        header = lines[0].split("\t")
        idx = header.index(column)
        found = []
        for line in lines[3:]:
            cells = line.split("\t")
            if len(cells) != len(header):
                raise ValueError("Malformed catalog TSV")
            sid = cells[idx].strip()
            if not sid.isdecimal():
                raise ValueError("Malformed catalog Gaia ID")
            found.append(sid)
            if sid not in known:
                known[sid] = {
                    "status": "EXCLUDE_PREVIOUSLY_STUDIED",
                    "reason": "Already in a compact-companion study (conservative over-exclusion; not all are black holes)",
                    "evidence": ["https://cdsarc.cds.unistra.fr/viz-bin/cat/" + table.rsplit("/", 1)[0]],
                }
        if len(found) != count:
            raise ValueError("Catalog snapshot count mismatch")
        coverage.append(
            {
                "catalog": table,
                "rows": len(found),
                "source": "bundled real 2026-10-19 snapshot",
                "sha256": manifest["files"][filename],
            }
        )
    return known, coverage


def augment_live(known, results):
    coverage = []
    for table, result in results.items():
        for row in result.rows:
            sid = row.get("source_id") or row.get("GaiaDR3") or row.get("Source")
            if not isinstance(sid, str) or not sid.isdecimal():
                raise ValueError("Lossless catalog ID required")
            if sid not in known:
                known[sid] = {
                    "status": "EXCLUDE_PREVIOUSLY_STUDIED",
                    "reason": "Present in published compact-companion sample; conservative exclusion, not BH confirmation",
                    "evidence": ["https://cdsarc.cds.unistra.fr/viz-bin/cat/" + table.rsplit("/", 1)[0]],
                }
        coverage.append({"catalog": table, "rows": len(result.rows), "provenance": result.provenance})
    return coverage
