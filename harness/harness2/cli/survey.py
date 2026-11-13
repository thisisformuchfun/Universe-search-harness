"""harness2-survey: whole-catalogue search with a built-in vetting stage.

  harness2-survey acquire --store data/cache/bulk
  harness2-survey run     --store data/cache/bulk --out runs/survey-YYYYMMDD
  harness2-survey bench   --store data/cache/bulk

`run` works through the catalogue in shards. Shortlisted anomalies accumulate in
a ledger; whenever enough unvetted ones have piled up (and always at the end)
the vetting battery runs on them. No output of this tool is a discovery claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

from harness2.core.guards import ROOT, disposition, sha, verify_guard
from harness2.core.library import atomic_json
from harness2.survey import SURVEY_VERSION, context, find, store, vet
from harness2.survey import physics as ph
from harness2.survey.criteria import CRITERIA, criteria_hash
from harness2.survey.net import Fetcher, NetError, utc_now
from harness2.universe.detectors.signal_pipeline import measure
from harness2.universe.novelty import CATALOGS, bundled_catalogs

CATALOGUE_FILE = ROOT / "data/survey/prior_catalogues.json"
SUPPLEMENT_FILE = ROOT / "data/survey/literature_supplement.json"
SEALED_KEYS = {"shahaf177.tsv": "shahaf2023_class3_bundled", "jayasinghe234.tsv": "jayasinghe2023_sb1_bundled"}


def seal_state():
    """Which survey modules the guard manifest covers. Unsealed code is reported, never hidden."""
    manifest = json.loads((ROOT / "policy/guard_manifest.json").read_text())["files"]
    files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "harness2/survey").glob("*.py"))
    files.append("harness2/cli/survey.py")
    unsealed = [f for f in files if manifest.get(f) != sha(ROOT / f)]
    return {
        "survey_code_sealed": not unsealed,
        "unsealed_files": unsealed,
        "note": "Unsealed survey code has not been through human review and seal_release.py." if unsealed else "",
    }


def bundled_members():
    out = {}
    for filename, column, _count, _table in CATALOGS:
        lines = [x for x in (ROOT / "data/pilot" / filename).read_text().splitlines() if x.strip() and not x.startswith("#")]
        idx = lines[0].split("\t").index(column)
        out[SEALED_KEYS[filename]] = {ln.split("\t")[idx].strip() for ln in lines[3:]}
    # Papers with no VizieR table: source IDs printed in the paper, bundled as data.
    for paper in json.loads(SUPPLEMENT_FILE.read_text())["papers"]:
        out[paper["key"]] = set(paper["ids"])
    return out


def load_ledger(path: Path):
    if path.exists():
        return json.loads(path.read_text())
    return {"version": 1, "candidates": {}, "vetting": {}, "shards_done": [], "events": [], "find_stats": {}}


def control_check(ledger):
    """How published positives fare. Tune-split controls and policy black holes only;
    the test split is never read here, so it stays unspent."""
    controls = json.loads((ROOT / "data/controls/controls_v1.json").read_text())["controls"]
    known = json.loads((ROOT / "policy/known_objects.json").read_text())
    ids = {c["source_id"]: "control_tune:" + ",".join(c["label_sources"]) for c in controls if c["split"] == "tune"}
    spent_only_once = {c["source_id"] for c in controls if c["split"] == "test"}
    ids.update({sid: e["status"] for sid, e in known.items() if sid not in spent_only_once})
    by_source = {}
    for cid, c in ledger["candidates"].items():
        by_source.setdefault(c["source_id"], []).append(cid)
    rows = []
    for sid, label in sorted(ids.items(), key=lambda kv: int(kv[0])):
        cids = by_source.get(sid, [])
        rows.append(
            {
                "source_id": sid,
                "label": label,
                "shortlisted": bool(cids),
                "tiers": [ledger["vetting"][c]["tier"] for c in cids if c in ledger["vetting"]],
                "physics_tiers": [ledger["vetting"][c]["physics_tier_ignoring_literature"] for c in cids if c in ledger["vetting"]],
            }
        )
    short = [r for r in rows if r["shortlisted"]]
    return {
        "meaning": "Published positives used as a sanity check of the search and vetting, not as a tuning target. "
        "Most controls have f_phot well below this survey's mass cut and are not expected to be shortlisted.",
        "n": len(rows),
        "shortlisted": len(short),
        "excluded_as_published": sum("EXCLUDED_PUBLISHED_PRIOR" in r["tiers"] for r in short),
        "shortlisted_but_not_excluded": [r["source_id"] for r in short if "EXCLUDED_PUBLISHED_PRIOR" not in r["tiers"]],
        "physics_tier_counts": dict(Counter(t for r in short for t in r["physics_tiers"])),
        "rows": rows,
    }


def raw_row(table, i):
    """One bulk-table row in the string form the sealed per-row pipeline reads."""
    row = {"source_id": str(int(table["source_id"][i])), "nss_solution_type": str(table["nss_solution_type"][i])}
    for name, col in table.items():
        if name in row or name in ("corr_vec", "corr_len", "solution_id"):
            continue
        v = float(col[i])
        row[name] = repr(v) if np.isfinite(v) else ""
    n = int(table["corr_len"][i])
    # Missing correlations stay missing (None): the sealed code then reports covariance as unavailable.
    row["corr_vec"] = [float(x) if np.isfinite(x) else None for x in table["corr_vec"][i, :n]] if n else ""
    return row


def export_agent_run(out: Path, table, ledger):
    """Write the survivors in the format `harness2-agent investigate --run` reads,
    measured and dispositioned by the sealed per-row code."""
    known, _ = bundled_catalogs()
    keep = {
        c["candidate_id"]
        for c in ledger["candidates"].values()
        if c["channel"] == "astrometric"
        and ledger["vetting"].get(c["candidate_id"], {}).get("tier") in ("HELD_SURVIVED_AUTOMATED_VETTING", "HELD_WITH_CAVEATS")
    }
    key = np.char.add(table["source_id"].astype(str), np.char.add(":", table["nss_solution_type"]))
    rows, records = [], []
    for i in np.flatnonzero(np.isin(key, sorted(keep))):
        row = raw_row(table, i)
        rec = measure(row, 4096, "numpy")
        rec.update(disposition(rec, known))
        rows.append(row)
        records.append(rec)
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out / "records.json", records)
    atomic_json(out / "raw_rows.json", rows)
    return len(records)


def write_outputs(out: Path, ledger, table_prov, ctx, started, backend_label, args_seen, evidence_log=()):
    cands = sorted(ledger["candidates"].values(), key=lambda c: -(c["m2_dark"]["q05"] or 0))
    vetting = ledger["vetting"]
    tiers = Counter(vetting[c["candidate_id"]]["tier"] for c in cands if c["candidate_id"] in vetting)
    by_channel = Counter((c["channel"], vetting[c["candidate_id"]]["tier"]) for c in cands if c["candidate_id"] in vetting)
    fails = Counter(
        t["test"] for c in cands if c["candidate_id"] in vetting for t in vetting[c["candidate_id"]]["tests"] if t["result"] == "FAIL"
    )
    order = {t: i for i, t in enumerate(reversed(vet.TIERS))}
    queue = sorted(
        (c for c in cands if c["candidate_id"] in vetting),
        key=lambda c: (order[vetting[c["candidate_id"]]["tier"]], -(c["m2_dark"]["q05"] or 0)),
    )
    stats = {}
    for shard_stats in ledger["find_stats"].values():
        for ch, s in shard_stats.items():
            agg = stats.setdefault(ch, Counter())
            for k in ("rows_scanned", "rows_monte_carlo", "point_m2_above_cut", "shortlisted", "seconds"):
                agg[k] += s[k]
    summary = {
        "label": "Whole-catalogue anomaly survey with automated vetting. Not companion masses, not black-hole detections.",
        "release": store.RELEASE,
        "rows_in_table": table_prov["rows"],
        "find": {ch: dict(v) for ch, v in stats.items()},
        "shortlisted": len(cands),
        "vetted": len(vetting),
        "tier_counts": dict(tiers),
        "tier_counts_by_channel": {f"{a}:{b}": n for (a, b), n in sorted(by_channel.items())},
        "fail_reasons": dict(fails.most_common()),
        "tier_meaning": vet.TIER_MEANING,
        "vetting_rounds": [e for e in ledger["events"] if e["event"] == "vet"],
        "evidence_errors": sorted({k for e in ledger["events"] if e["event"] == "vet" for k in e["evidence_errors"]}),
        "controls": {k: v for k, v in control_check(ledger).items() if k != "rows"},
        "agent_run_records": ledger.get("agent_run_records"),
        "new_candidates": [],
        "releasable_novel_candidates": 0,
        "discovery_claims": 0,
        "data_mode": table_prov["mode"],
        "vetting_evidence_mode": "REPLAYED_RECORDED_RESPONSES" if any(e.get("cache_reused") for e in evidence_log) else "LIVE_ARCHIVE_QUERIES",
        "seconds_total": round(time.time() - started, 1),
        "backend": backend_label,
    }
    # The two large files are written compactly; everything else stays indented for reading.
    for name, payload in (("candidates.json", cands), ("vetting.json", [vetting[c["candidate_id"]] for c in queue])):
        (out / name).write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf8")
    atomic_json(out / "controls_check.json", control_check(ledger))
    atomic_json(
        out / "evidence_index.json",
        {"meaning": "Every archive response used by vetting: request label, SHA-256, size, time, and whether it was replayed.",
         "any_replayed": any(e.get("cache_reused") for e in evidence_log), "responses": list(evidence_log)},
    )
    atomic_json(out / "summary.json", summary)
    atomic_json(
        out / "provenance.json",
        {"nss_bulk": table_prov, "gaia_source_context": ctx["source_meta"], "binary_masses": ctx["masses_meta"],
         "prior_catalogues": json.loads(CATALOGUE_FILE.read_text()),
         "literature_supplement": [{k: p[k] for k in ("key", "url", "title", "html_sha256")} | {"ids": len(p["ids"])}
                                   for p in json.loads(SUPPLEMENT_FILE.read_text())["papers"]]},
    )
    fields = ["tier", "physics_tier", "source_id", "nss_solution_type", "channel", "mass_range_label", "m2_dark_q05", "m2_dark_q50",
              "m2_dark_q95", "m1", "m1_source", "period", "eccentricity", "significance", "phot_g_mean_mag", "ra", "dec", "warn", "fail", "na", "failed_or_warned_tests"]
    with (out / "review_queue.csv").open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for c in queue:
            v = vetting[c["candidate_id"]]
            w.writerow(
                {
                    "tier": v["tier"], "physics_tier": v["physics_tier_ignoring_literature"], "source_id": c["source_id"],
                    "nss_solution_type": c["nss_solution_type"], "channel": c["channel"], "mass_range_label": c["mass_range_label"],
                    "m2_dark_q05": round(c["m2_dark"]["q05"], 3), "m2_dark_q50": round(c["m2_dark"]["q50"], 3),
                    "m2_dark_q95": round(c["m2_dark"]["q95"], 3), "m1": round(c["primary"]["m1"], 3), "m1_source": c["primary"]["m1_source"],
                    "period": c["orbit"]["period"], "eccentricity": c["orbit"]["eccentricity"], "significance": c["orbit"]["significance"],
                    "phot_g_mean_mag": c["context"]["phot_g_mean_mag"], "ra": (v.get("position_deg") or [None, None])[0], "dec": (v.get("position_deg") or [None, None])[1],
                    "warn": v["counts"]["WARN"], "fail": v["counts"]["FAIL"], "na": v["counts"]["NA"],
                    "failed_or_warned_tests": ";".join(f"{t['test']}={t['result']}" for t in v["tests"] if t["result"] in ("FAIL", "WARN", "PRIOR")),
                }
            )
    hashes = {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "run_manifest.json"}
    atomic_json(
        out / "run_manifest.json",
        {
            "created_at_utc": utc_now(),
            "survey_version": SURVEY_VERSION,
            "criteria": CRITERIA,
            "criteria_sha256": criteria_hash(),
            "guard_hash": verify_guard(),
            "seal_state": seal_state(),
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "backend": backend_label,
            "arguments": args_seen,
            "output_hashes": hashes,
            "release_enabled": False,
            "gpu_benchmark_claim": False,
        },
    )
    return summary


def cmd_acquire(args):
    fetcher = Fetcher(Path(args.store) / "evidence", timeout=args.timeout)
    prov = store.acquire_bulk(args.store, fetcher)
    table, prov = store.load_table(args.store)
    _, m_meta = context.acquire_binary_masses(args.store, fetcher)
    _, s_meta = context.acquire_source_context(args.store, table["source_id"], fetcher, workers=args.workers)
    return {"nss_rows": prov["rows"], "binary_masses_rows": m_meta["rows"], "gaia_source_rows": s_meta["rows"], "bulk_sha256": prov["sha256"]}


def cmd_run(args):
    started = time.time()
    guard = verify_guard()
    out = Path(args.out)
    if (out / "run_manifest.json").exists():
        raise ValueError("completed output exists; choose a new run directory")
    out.mkdir(parents=True, exist_ok=True)
    table, table_prov = store.load_table(args.store)
    ctx = context.load_context(args.store)
    backend = ph.Backend(args.backend)
    fetcher = Fetcher(args.evidence_dir or out / "evidence", mode=args.evidence, timeout=args.timeout)
    specs = json.loads(CATALOGUE_FILE.read_text())["catalogues"]
    known = json.loads((ROOT / "policy/known_objects.json").read_text())
    policy_bibcodes = set(json.loads((ROOT / "policy/agent_tools.json").read_text())["compact_companion_bibcodes"])
    members = bundled_members()
    ledger_path = out / "ledger.json"
    ledger = load_ledger(ledger_path)
    cache = {}

    def vet_pending(reason):
        pending = [c for cid, c in ledger["candidates"].items() if cid not in ledger["vetting"]]
        if not pending:
            return
        t0 = time.time()
        reports, info = vet.vet_batch(pending, table, fetcher, specs, known, members, policy_bibcodes, catalogue_cache=cache)
        for r in reports:
            ledger["vetting"][r["candidate_id"]] = r
        ledger["evidence_log"] = ledger.get("evidence_log", []) + fetcher.log
        fetcher.log.clear()
        ledger["events"].append(
            {"event": "vet", "reason": reason, "candidates": len(reports), "tiers": dict(Counter(r["tier"] for r in reports)),
             "evidence_errors": info["evidence_errors"], "seconds": round(time.time() - t0, 1), "at_utc": utc_now()}
        )
        atomic_json(ledger_path, ledger)
        print(f"  vet[{reason}]: {len(reports)} candidates in {time.time() - t0:.0f}s -> {dict(Counter(r['tier'] for r in reports))}", file=sys.stderr)

    for shard in range(args.shards):
        if shard in ledger["shards_done"]:
            continue
        found, stats = find.run_find(table, ctx, backend, shard, args.shards)
        new = [c for c in found if c["candidate_id"] not in ledger["candidates"]]
        for c in new:
            ledger["candidates"][c["candidate_id"]] = c
        ledger["find_stats"][str(shard)] = stats
        ledger["shards_done"].append(shard)
        ledger["events"].append({"event": "find", "shard": shard, "new": len(new), "at_utc": utc_now()})
        atomic_json(ledger_path, ledger)
        print(f"find shard {shard + 1}/{args.shards}: {len(new)} shortlisted", file=sys.stderr)
        if sum(cid not in ledger["vetting"] for cid in ledger["candidates"]) >= args.vet_after:
            vet_pending(f"{args.vet_after}+ unvetted after shard {shard}")
    vet_pending("end of run")
    # Evidence that was unreachable earlier may be reachable now: retry those candidates once.
    stale = [cid for cid, v in ledger["vetting"].items() if v.get("evidence_incomplete")]
    if stale:
        for cid in stale:
            del ledger["vetting"][cid]
        vet_pending(f"retry of {len(stale)} candidates vetted with incomplete evidence")
    if verify_guard() != guard:
        raise RuntimeError("guard changed during execution")
    exported = export_agent_run(out / "agent_run", table, ledger)
    ledger["agent_run_records"] = exported
    summary = write_outputs(out, ledger, table_prov, ctx, started, backend.label, {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "func"}, ledger.get("evidence_log", []))
    return summary


def cmd_bench(args):
    """Time the sealed per-row path against the vectorized path on the same real rows."""
    table, _ = store.load_table(args.store)
    ctx = context.load_context(args.store)
    types = table["nss_solution_type"]
    rows = np.flatnonzero((types == "Orbital") & (table["bit_index"] == 8191))[: args.rows]
    sub = {k: v[rows] for k, v in table.items()}
    t0 = time.time()
    sealed = [measure(raw_row(table, i), args.draws, "numpy") for i in rows]
    t_sealed = time.time() - t0
    cols = find.attach_context(sub, ctx)
    out = {"rows": len(rows), "draws": args.draws, "sealed_per_row_seconds": round(t_sealed, 3)}
    for name in args.backends:
        backend = ph.Backend(name)
        t0 = time.time()
        res = find.scan_astrometric(sub, cols, backend, draws=args.draws, m2_cut=0.0)
        dt = time.time() - t0
        f_sealed = np.array([r["f_phot_solar"] for r in sealed])
        q_sealed = np.array([r["uncertainty"].get("f_phot_q50", np.nan) for r in sealed])
        out[backend.label] = {
            "seconds": round(dt, 3),
            "speedup_vs_sealed": round(t_sealed / dt, 1),
            "max_rel_diff_f_phot": float(np.nanmax(np.abs(res["f_phot"] - f_sealed) / f_sealed)),
            "median_rel_diff_f_phot_q50": float(np.nanmedian(np.abs(res["f_phot_q"][:, 1] - q_sealed) / q_sealed)),
            "note": "The vectorized path also computes m2_dark, AMRF and predicted RV amplitude per draw; the sealed path computes f_phot only.",
        }
    return out


def parser():
    p = argparse.ArgumentParser(prog="harness2-survey", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("acquire", help="download and verify the bulk NSS table and catalogue-wide context")
    a.add_argument("--store", default="data/cache/bulk")
    a.add_argument("--timeout", type=int, default=600)
    a.add_argument("--workers", type=int, default=4)
    a.set_defaults(func=cmd_acquire)
    r = sub.add_parser("run", help="find, then vet whenever enough candidates accumulate")
    r.add_argument("--store", default="data/cache/bulk")
    r.add_argument("--out", required=True)
    r.add_argument("--shards", type=int, default=8)
    r.add_argument("--vet-after", type=int, default=CRITERIA["vet_after_new_candidates"])
    r.add_argument("--backend", default="numpy", help="numpy, torch, torch:cpu, torch:cuda or torch:mps")
    r.add_argument("--evidence", choices=["live", "replay"], default="live")
    r.add_argument("--evidence-dir", default=None, help="where archive responses are stored or replayed from (default: <out>/evidence)")
    r.add_argument("--timeout", type=int, default=300)
    r.set_defaults(func=cmd_run)
    b = sub.add_parser("bench", help="time sealed per-row code against the vectorized kernels on real rows")
    b.add_argument("--store", default="data/cache/bulk")
    b.add_argument("--rows", type=int, default=2000)
    b.add_argument("--draws", type=int, default=4096)
    b.add_argument("--backends", nargs="+", default=["numpy"])
    b.set_defaults(func=cmd_bench)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = args.func(args)
    except (ValueError, RuntimeError, OSError, KeyError, NetError) as exc:
        print("FAILED CLOSED: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
