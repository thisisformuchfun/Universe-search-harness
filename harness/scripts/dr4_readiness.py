"""Gaia DR4 readiness: compare a Gaia release's archive schema with what this harness reads.

Maintainer tool. It does not edit guarded code or policy and never switches the
harness to a new release. On DR4 release day it answers four questions:

1. Do the tables and columns the harness queries exist under the new release?
2. Which tables look like epoch astrometry, epoch radial velocities or a
   cross-release (DR3 -> DR4) match? Name matches only; read the data model.
3. Do sampled NSS rows use covariance layouts the current parser accepts?
4. Which sources should be pulled first? (`watchlist`)

    python scripts/dr4_readiness.py requirements
    python scripts/dr4_readiness.py check --release gaiadr3 --sample 0     # positive control
    python scripts/dr4_readiness.py check --release gaiadr4 --out runs/dr4-readiness.json
    python scripts/dr4_readiness.py watchlist --out data/dr4/watchlist.csv

Queries are built only from constants and a release name that must match
`gaiadr<N>`. An archive failure is reported as a failure (exit 2), never as
"not published". See docs/DR4.md for the release-day runbook.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness2.universe.connectors.public_archives import (  # noqa: E402
    GAIA_TAP,
    NSS_COLUMNS,
    NSS_REQUIRED,
    ArchiveError,
    PublicSkyConnector,
)
from harness2.universe.detectors.signal_pipeline import COVARIANCE_ORDERS, EXPECTED_BITS  # noqa: E402

RELEASE_RE = re.compile(r"gaiadr[0-9]{1,2}")
# Gaia DR3 reference epoch (Julian year) of watchlist positions. The bundled snapshot
# has no proper motions, so match DR3 -> DR4 by the official cross-release table, not position.
DR3_REF_EPOCH = 2016.0

# Columns PublicSkyConnector.gaia_context selects from gaia_source. A test checks
# this list against the connector source, so it cannot drift silently.
CONTEXT_COLUMNS = (
    "source_id",
    "ra",
    "dec",
    "parallax",
    "parallax_error",
    "ruwe",
    "phot_g_mean_mag",
    "phot_bp_mean_mag",
    "phot_rp_mean_mag",
    "phot_bp_rp_excess_factor",
    "ipd_frac_multi_peak",
    "duplicated_source",
    "astrometric_excess_noise",
    "visibility_periods_used",
)
# Columns the code cannot do without, even if a query were rewritten.
CORE_COLUMNS = {
    "nss_two_body_orbit": set(NSS_REQUIRED),
    "gaia_source": {"source_id", "ruwe"},
}
# Table-name patterns worth a human look in a new release. Each entry is a list
# of alternatives; every fragment in an alternative must appear in the name.
DISCOVERY_HINTS = {
    "epoch_astrometry": [("epoch", "astrom")],
    "epoch_radial_velocity": [("epoch", "rv"), ("epoch", "radial")],
    "epoch_other": [("epoch",)],
    "cross_release_match": [("neighbourhood",), ("neighborhood",), ("dr3",)],
    "non_single_star": [("nss",)],
}
SAMPLE_COLUMNS = ("nss_solution_type", "bit_index", "corr_vec")
MAX_SAMPLE = 5000


def check_release(release: str) -> str:
    if not isinstance(release, str) or not RELEASE_RE.fullmatch(release):
        raise ValueError("release must look like gaiadr4 (lowercase, gaiadr followed by digits)")
    return release


def _policy() -> dict:
    return json.loads((ROOT / "policy/agent_tools.json").read_text())


def requirements(release: str) -> dict:
    """What this harness reads from a Gaia release, derived from the code and policy."""
    release = check_release(release)
    policy = _policy()
    gaia_source = list(dict.fromkeys([*policy["gaia_quality_columns"], *CONTEXT_COLUMNS]))
    return {
        "release": release,
        "tables": {
            f"{release}.nss_two_body_orbit": {
                "selected_columns": list(NSS_COLUMNS),
                "core_columns": sorted(CORE_COLUMNS["nss_two_body_orbit"]),
                "used_by": "harness2-universe run --live, probe and the covariance parser",
            },
            f"{release}.gaia_source": {
                "selected_columns": gaia_source,
                "core_columns": sorted(CORE_COLUMNS["gaia_source"]),
                "used_by": "agent gaia_quality tool and harness2-universe run --context",
            },
        },
        "covariance_layouts": {
            kind: {"bit_index": EXPECTED_BITS[kind], "corr_vec_length": len(names) * (len(names) - 1) // 2}
            for kind, names in COVARIANCE_ORDERS.items()
        },
        "not_checked_here": [
            "source_id continuity between DR3 and the new release",
            "solution-type semantics, units and reference epoch",
            "SIMBAD and VizieR identifiers for the new release (literature tools still use 'Gaia DR3 <id>')",
        ],
    }


def _qualified(name: str, release: str) -> str:
    name = str(name).strip().lower()
    return name if "." in name else f"{release}.{name}"


def discover(table_names) -> dict:
    found = {key: [] for key in DISCOVERY_HINTS}
    for name in sorted(table_names):
        short = name.split(".", 1)[-1]
        for key, alternatives in DISCOVERY_HINTS.items():
            if any(all(fragment in short for fragment in alt) for alt in alternatives):
                found[key].append(name)
    return found


def _corr_values(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip().strip("[]").replace(",", " ").split()
    values = []
    for v in raw:
        try:
            x = float(v) if v is not None else math.nan
        except (TypeError, ValueError):
            x = math.nan
        values.append(x)
    return values


def summarize_layouts(rows) -> dict:
    """Group sampled NSS rows by (solution type, bit_index, corr_vec length) and flag what the parser accepts."""
    groups = Counter()
    for row in rows:
        kind = str(row.get("nss_solution_type") or "")
        bit = row.get("bit_index")
        try:
            bit = int(bit) if bit is not None else None
        except (TypeError, ValueError):
            bit = None
        values = _corr_values(row.get("corr_vec"))
        length = None if values is None else len(values)
        finite = None if values is None else sum(math.isfinite(v) for v in values)
        groups[(kind, bit, length, finite)] += 1
    layouts = []
    for (kind, bit, length, finite), count in sorted(groups.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        names = COVARIANCE_ORDERS.get(kind)
        expected = None if names is None else len(names) * (len(names) - 1) // 2
        accepted = names is not None and bit == EXPECTED_BITS[kind] and length == expected and finite == expected
        layouts.append(
            {
                "nss_solution_type": kind,
                "bit_index": bit,
                "corr_vec_length": length,
                "corr_vec_finite": finite,
                "rows": count,
                "supported_type": names is not None,
                "accepted_by_current_parser": accepted,
            }
        )
    supported = [g for g in layouts if g["supported_type"]]
    if not rows:
        status = "NO_SUPPORTED_ROWS"
    elif supported and all(g["accepted_by_current_parser"] for g in supported):
        status = "MATCHES"
    elif not supported:
        status = "NO_SUPPORTED_ROWS"
    else:
        status = "MISMATCH"
    return {"status": status, "sampled_rows": len(rows), "layouts": layouts}


def assess(release, table_rows, column_rows, sample_rows=None) -> dict:
    """Pure comparison of archive metadata with requirements(release). No network."""
    req = requirements(release)
    tables = {_qualified(r.get("table_name", ""), release) for r in table_rows}
    tables.discard(f"{release}.")
    columns = {}
    for r in column_rows:
        columns.setdefault(_qualified(r.get("table_name", ""), release), set()).add(
            str(r.get("column_name", "")).strip().lower()
        )
    report = {
        "release": release,
        "tables_in_schema": len(tables),
        "tables": {},
        "candidate_tables": discover(tables),
        "layout": {"status": "NOT_SAMPLED"} if sample_rows is None else summarize_layouts(sample_rows),
        "not_checked_here": req["not_checked_here"],
    }
    if not tables:
        report["status"] = "NOT_PUBLISHED"
        report["meaning"] = f"The archive returned no tables for schema {release}."
        return report
    incompatible = False
    for table, spec in req["tables"].items():
        present = table in tables
        have = columns.get(table, set())
        missing = [c for c in spec["selected_columns"] if c not in have] if present else spec["selected_columns"]
        core_missing = [c for c in spec["core_columns"] if c in missing]
        report["tables"][table] = {
            "present": present,
            "missing_selected_columns": missing,
            "missing_core_columns": core_missing,
            "used_by": spec["used_by"],
        }
        incompatible |= bool(missing)
    if incompatible:
        report["status"] = "INCOMPATIBLE"
        report["meaning"] = "Queries written for DR3 would fail or lose data. A reviewed code change is needed."
    elif report["layout"]["status"] in ("MISMATCH", "NO_SUPPORTED_ROWS"):
        report["status"] = "NEEDS_PARSER_REVIEW"
        report["meaning"] = "Columns exist, but sampled NSS rows do not match the covariance layouts the parser accepts."
    else:
        report["status"] = "SCHEMA_COMPATIBLE"
        report["meaning"] = (
            "Every column the harness selects exists. This is not a science validation; "
            "follow docs/DR4.md before changing gaia_release."
        )
    return report


# ------------------------------------------------------------------ live


def fetch_metadata(connector, release, sample=0):
    """Read TAP_SCHEMA (and optionally a small NSS sample) for one release."""
    release = check_release(release)
    if not 0 <= sample <= MAX_SAMPLE:
        raise ValueError(f"sample must be 0..{MAX_SAMPLE}")
    tables = connector.tap(
        GAIA_TAP,
        f"SELECT table_name FROM TAP_SCHEMA.tables WHERE schema_name = '{release}'",
        2000,
        required=("table_name",),
    )
    names = {_qualified(r["table_name"], release) for r in tables.rows if r.get("table_name")}
    wanted = [t for t in requirements(release)["tables"] if t in names]
    column_rows, column_prov = [], None
    if wanted:
        columns = connector.tap(
            GAIA_TAP,
            "SELECT table_name, column_name FROM TAP_SCHEMA.columns WHERE table_name IN ("
            + ",".join(f"'{t}'" for t in wanted)
            + ")",
            5000,
            required=("table_name", "column_name"),
        )
        column_rows, column_prov = columns.rows, columns.provenance
    sample_rows, sample_prov = None, None
    nss = f"{release}.nss_two_body_orbit"
    nss_columns = {str(r["column_name"]).lower() for r in column_rows if _qualified(r["table_name"], release) == nss}
    if sample and set(SAMPLE_COLUMNS) <= nss_columns:
        kinds = ",".join(f"'{k}'" for k in COVARIANCE_ORDERS if re.fullmatch(r"[A-Za-z0-9]+", k))
        result = connector.tap(
            GAIA_TAP,
            f"SELECT TOP {int(sample)} {','.join(SAMPLE_COLUMNS)} FROM {nss} WHERE nss_solution_type IN ({kinds})",
            int(sample),
            required=("nss_solution_type",),
        )
        sample_rows, sample_prov = result.rows, result.provenance
    provenance = {"tables": tables.provenance, "columns": column_prov, "sample": sample_prov}
    return tables.rows, column_rows, sample_rows, provenance


# ------------------------------------------------------------- watchlist


WATCHLIST_FIELDS = (
    "dr3_source_id",
    "roles",
    "pipeline_status",
    "nss_solution_type",
    "ref_epoch",
    "ra",
    "dec",
    "parallax",
    "period",
    "f_phot_solar",
)


def watchlist(run_dir, controls_path) -> list[dict]:
    """Held anomalies plus labeled controls: the sources to pull from DR4 first."""
    run_dir = Path(run_dir)
    records = json.loads((run_dir / "records.json").read_text())
    raw = {(r["source_id"], r["nss_solution_type"]): r for r in json.loads((run_dir / "raw_rows.json").read_text())}
    controls = {c["source_id"]: c for c in json.loads(Path(controls_path).read_text())["controls"]}
    by_source = {}
    for rec in records:
        by_source.setdefault(rec["source_id"], []).append(rec)
    rows = []
    for sid in sorted(by_source, key=int):
        recs = by_source[sid]
        roles = []
        if any(r["status"] == "HOLD_QUALITY_AND_NOVELTY" for r in recs):
            roles.append("held")
        if sid in controls:
            roles.append("control")
        if not roles:
            continue
        lead = max(recs, key=lambda r: r["f_phot_solar"])
        src = raw.get((sid, lead["nss_solution_type"]), {})
        rows.append(
            {
                "dr3_source_id": sid,
                "roles": ";".join(roles),
                "pipeline_status": ";".join(sorted({r["status"] for r in recs})),
                "nss_solution_type": ";".join(sorted({r["nss_solution_type"] for r in recs})),
                "ref_epoch": DR3_REF_EPOCH,
                **{k: src.get(k, "") for k in ("ra", "dec", "parallax", "period")},
                "f_phot_solar": round(lead["f_phot_solar"], 6),
            }
        )
    missing = set(controls) - {r["dr3_source_id"] for r in rows}
    if missing:
        raise ValueError(f"controls not found in run {run_dir}: {sorted(missing, key=int)[:5]}")
    return rows


def watchlist_csv(rows) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=WATCHLIST_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("requirements", help="print what the harness reads from a release (offline)")
    r.add_argument("--release", default="gaiadr4")
    c = sub.add_parser("check", help="compare a release's live archive schema with the requirements")
    c.add_argument("--release", default="gaiadr4")
    c.add_argument("--sample", type=int, default=2000, help=f"NSS rows to sample for covariance layout (0..{MAX_SAMPLE})")
    c.add_argument("--cache", default="runs/cache/dr4-readiness")
    c.add_argument("--timeout", type=int, default=60)
    c.add_argument("--out", help="write the JSON report here as well as to stdout")
    c.add_argument("--require-published", action="store_true", help="exit 1 if the release is not published yet")
    w = sub.add_parser("watchlist", help="write held sources and controls as a CSV (offline)")
    w.add_argument("--run", default="runs/verified-release")
    w.add_argument("--controls", default="data/controls/controls_v1.json")
    w.add_argument("--out", help="CSV path; stdout if omitted")
    args = p.parse_args(argv)

    if args.cmd == "requirements":
        print(json.dumps(requirements(args.release), indent=2))
        return 0
    if args.cmd == "watchlist":
        text = watchlist_csv(watchlist(args.run, args.controls))
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0

    release = check_release(args.release)
    connector = PublicSkyConnector(args.cache, timeout=args.timeout)
    try:
        tables, columns, sample, provenance = fetch_metadata(connector, release, args.sample)
        report = assess(release, tables, columns, sample)
        report["provenance"] = provenance
    except ArchiveError as exc:
        report = {
            "release": release,
            "status": "ARCHIVE_ERROR",
            "meaning": "The archive request failed. This says nothing about whether the release exists.",
            "error": str(exc),
        }
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if report["status"] == "ARCHIVE_ERROR":
        return 2
    if report["status"] == "NOT_PUBLISHED":
        return 1 if args.require_published else 0
    return 0 if report["status"] == "SCHEMA_COMPATIBLE" else 1


if __name__ == "__main__":
    sys.exit(main())
