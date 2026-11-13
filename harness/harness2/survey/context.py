"""Catalogue-wide context: gaia_source quality/photometry and Gaia binary_masses.

Pulled in parallel source-ID ranges derived from the local NSS table, so each
range has a known expected ID set. A range that returns anything else fails the
acquisition; there is no partial success.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from harness2.survey.net import GAIA_TAP, Fetcher, NetError, utc_now

SOURCE_FLOATS = (
    "ra",
    "dec",
    "parallax",
    "parallax_error",
    "phot_g_mean_mag",
    "bp_rp",
    "ruwe",
    "ipd_frac_multi_peak",
    "ipd_gof_harmonic_amplitude",
    "phot_bp_rp_excess_factor",
    "radial_velocity",
    "radial_velocity_error",
    "rv_nb_transits",
    "rv_amplitude_robust",
    "rv_chisq_pvalue",
    "rv_renormalised_gof",
    "ag_gspphot",
    "ebpminrp_gspphot",
    "teff_gspphot",
    "logg_gspphot",
    "mh_gspphot",
    "l",
    "b",
    "grvs_mag",
    "vbroad",
    "astrometric_excess_noise",
    "visibility_periods_used",
    "non_single_star",
)
SOURCE_OTHER = ("duplicated_source", "phot_variable_flag")
MASS_FLOATS = ("m1", "m1_lower", "m1_upper", "m2", "m2_lower", "m2_upper", "fluxratio", "fluxratio_lower", "fluxratio_upper")
MASS_OTHER = ("combination_method", "m1_ref", "flag")


def _num(text):
    return float(text) if text not in ("", "null") else np.nan


def _ranges(ids: np.ndarray, per_chunk: int):
    ids = np.unique(ids)
    for start in range(0, len(ids), per_chunk):
        part = ids[start : start + per_chunk]
        yield int(part[0]), int(part[-1]), part


def _pull_source_chunk(fetcher, release, lo, hi, expected):
    cols = ",".join("g." + c for c in ("source_id", *SOURCE_FLOATS, *SOURCE_OTHER))
    query = (
        f"SELECT {cols} FROM {release}.gaia_source AS g JOIN "
        f"(SELECT DISTINCT source_id FROM {release}.nss_two_body_orbit "
        f"WHERE source_id BETWEEN {lo} AND {hi}) AS n ON g.source_id = n.source_id"
    )
    header, rows, prov = fetcher.tap_csv(GAIA_TAP, query, f"gaia_source {lo}-{hi}", expect_rows=len(expected))
    got = np.sort(np.array([int(r[0]) for r in rows], dtype=np.int64))
    if not np.array_equal(got, expected):
        raise NetError(f"gaia_source range {lo}-{hi} returned a different source set than the NSS table holds")
    return header, rows, prov


def acquire_source_context(store_dir, nss_source_ids, fetcher: Fetcher, release="gaiadr3", per_chunk=20000, workers=4):
    store = Path(store_dir)
    out = store / "gaia_source_context.npz"
    meta_path = store / "gaia_source_context.json"
    ranges = list(_ranges(np.asarray(nss_source_ids, dtype=np.int64), per_chunk))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda r: _pull_source_chunk(fetcher, release, *r), ranges))
    header = results[0][0]
    rows = [row for _, chunk, _ in results for row in chunk]
    idx = {name: i for i, name in enumerate(header)}
    table = {"source_id": np.array([int(r[0]) for r in rows], dtype=np.int64)}
    for name in SOURCE_FLOATS:
        table[name] = np.array([_num(r[idx[name]]) for r in rows])
    table["duplicated_source"] = np.array([r[idx["duplicated_source"]].lower() == "true" for r in rows])
    table["phot_variable_flag"] = np.array([r[idx["phot_variable_flag"]] for r in rows])
    order = np.argsort(table["source_id"])
    table = {k: v[order] for k, v in table.items()}
    np.savez(out, **table)
    meta = {
        "release": release,
        "table": "gaia_source",
        "rows": len(rows),
        "chunks": [p for _, _, p in results],
        "acquired_at_utc": utc_now(),
        "completeness": "every NSS source ID returned exactly once",
    }
    meta_path.write_text(json.dumps(meta, indent=1))
    return table, meta


def acquire_binary_masses(store_dir, fetcher: Fetcher, release="gaiadr3", bins=16):
    store = Path(store_dir)
    _, count_rows, count_prov = fetcher.tap_csv(
        GAIA_TAP, f"SELECT COUNT(*) AS n FROM {release}.binary_masses", "binary_masses count", expect_rows=1
    )
    total = int(count_rows[0][0])
    edges = [int(x) for x in np.linspace(0, 2**63 - 1, bins + 1)]
    cols = ",".join(("source_id", *MASS_FLOATS, *MASS_OTHER))

    def pull(i):
        q = f"SELECT {cols} FROM {release}.binary_masses WHERE source_id >= {edges[i]} AND source_id < {edges[i + 1]}"
        return fetcher.tap_csv(GAIA_TAP, q, f"binary_masses bin {i}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(pull, range(bins)))
    header = results[0][0]
    rows = [row for _, chunk, _ in results for row in chunk]
    if len(rows) != total:
        raise NetError(f"binary_masses: got {len(rows)} rows, archive COUNT(*) says {total}")
    idx = {name: i for i, name in enumerate(header)}
    table = {"source_id": np.array([int(r[0]) for r in rows], dtype=np.int64)}
    for name in MASS_FLOATS:
        table[name] = np.array([_num(r[idx[name]]) for r in rows])
    for name in MASS_OTHER:
        table[name] = np.array([r[idx[name]] for r in rows])
    order = np.argsort(table["source_id"], kind="stable")
    table = {k: v[order] for k, v in table.items()}
    np.savez(store / "binary_masses.npz", **table)
    meta = {
        "release": release,
        "table": "binary_masses",
        "rows": total,
        "count_check": count_prov,
        "chunks": [p for _, _, p in results],
        "acquired_at_utc": utc_now(),
    }
    (store / "binary_masses.json").write_text(json.dumps(meta, indent=1))
    return table, meta


def load_context(store_dir):
    store = Path(store_dir)
    out = {}
    for key, name in (("source", "gaia_source_context"), ("masses", "binary_masses")):
        with np.load(store / f"{name}.npz", allow_pickle=False) as z:
            out[key] = {k: z[k] for k in z.files}
        out[key + "_meta"] = json.loads((store / f"{name}.json").read_text())
    return out


def lookup(sorted_ids: np.ndarray, wanted: np.ndarray):
    """Index of each wanted ID in a sorted unique ID array, and a found mask."""
    pos = np.searchsorted(sorted_ids, wanted)
    pos = np.clip(pos, 0, len(sorted_ids) - 1)
    return pos, sorted_ids[pos] == wanted
