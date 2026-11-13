"""Bulk acquisition and columnar storage of the Gaia DR3 non-single-star orbit table.

The sealed pipeline pages the archive 500 rows at a time. Here the whole table
(443,205 solutions) is taken from ESA's own bulk file, checked against ESA's
published MD5, and held as NumPy columns so every later step is vectorized.

Source IDs are int64 (exact for every Gaia ID). Missing values are NaN.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from harness2.survey.net import GAIA_BULK, Fetcher, NetError, utc_now

RELEASE = "gaiadr3"
BULK_DIR = GAIA_BULK + "Non-single_stars/nss_two_body_orbit/"
BULK_FILE = "NssTwoBodyOrbit_1.csv.gz"
EXPECTED_ROWS = 443205  # Gaia DR3 documentation and COUNT(*) on the archive, 2026-11-12
FLOAT_COLUMNS = (
    "ra",
    "dec",
    "parallax",
    "pmra",
    "pmdec",
    "a_thiele_innes",
    "b_thiele_innes",
    "f_thiele_innes",
    "g_thiele_innes",
    "c_thiele_innes",
    "h_thiele_innes",
    "period",
    "t_periastron",
    "eccentricity",
    "center_of_mass_velocity",
    "semi_amplitude_primary",
)
PLAIN_FLOATS = (
    "goodness_of_fit",
    "efficiency",
    "significance",
    "obj_func",
    "conf_spectro_period",
    "astrometric_n_good_obs_al",
    "rv_n_good_obs_primary",
    "bit_index",
    "flags",
)
MAX_CORR = 105  # 15 fitted parameters -> 15*14/2 correlations
ASTROMETRIC_PREFIXES = ("Orbital", "AstroSpectroSB1")


def md5_file(path: Path) -> str:
    h = hashlib.md5()  # noqa: S324 - matches ESA's published checksum, not a security use
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def acquire_bulk(store_dir, fetcher: Fetcher | None = None) -> dict:
    """Download the bulk file once and verify it against ESA's checksum list.

    Returns provenance. An existing file is re-verified, never trusted blindly.
    """
    store = Path(store_dir)
    store.mkdir(parents=True, exist_ok=True)
    path = store / BULK_FILE
    prov_path = store / "bulk_provenance.json"
    fetcher = fetcher or Fetcher(store / "evidence")
    md5_raw, md5_prov = fetcher.fetch(BULK_DIR + "_MD5SUM.txt", label="bulk md5 list")
    published = {}
    for line in md5_raw.decode().splitlines():
        parts = line.split()
        if len(parts) == 2:
            published[parts[1]] = parts[0]
    if BULK_FILE not in published:
        raise NetError("ESA checksum list does not name the bulk file")
    reused = path.exists()
    if not reused:
        fetcher_big = Fetcher(store / "evidence", mode=fetcher.mode, timeout=1800, retries=fetcher.retries)
        raw, _ = fetcher_big.fetch(BULK_DIR + BULK_FILE, label="bulk nss_two_body_orbit")
        tmp = path.with_suffix(".part")
        tmp.write_bytes(raw)
        tmp.replace(path)
    actual = md5_file(path)
    if actual != published[BULK_FILE]:
        raise NetError("bulk file MD5 does not match ESA's published checksum")
    prov = {
        "release": RELEASE,
        "table": "nss_two_body_orbit",
        "url": BULK_DIR + BULK_FILE,
        "md5": actual,
        "md5_published_by_esa": published[BULK_FILE],
        "md5_list_sha256": md5_prov["sha256"],
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "verified_at_utc": utc_now(),
        "local_file_reused": reused,
        "mode": "REAL_ARCHIVE_BULK_FILE",
    }
    prov_path.write_text(json.dumps(prov, indent=1))
    return prov


def _f(text: str) -> float:
    if text == "" or text == "null":
        return np.nan
    return float(text)


def parse_bulk(path) -> dict:
    """Parse the gzip ECSV into columns. Pure Python csv: no pandas dependency."""
    path = Path(path)
    cols: dict[str, list] = {k: [] for k in ("source_id", "nss_solution_type", "solution_id")}
    names = list(FLOAT_COLUMNS) + [c + "_error" for c in FLOAT_COLUMNS] + list(PLAIN_FLOATS)
    for n in names:
        cols[n] = []
    corr_rows, corr_len = [], []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(line for line in handle if not line.startswith("#"))
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        missing = [n for n in ("source_id", "nss_solution_type", "corr_vec", *names) if n not in idx]
        if missing:
            raise NetError(f"bulk file schema lacks columns: {missing}")
        picks = [(n, idx[n]) for n in names]
        i_sid, i_typ, i_sol, i_corr = idx["source_id"], idx["nss_solution_type"], idx["solution_id"], idx["corr_vec"]
        for row in reader:
            if len(row) != len(header):
                raise NetError("ragged row in bulk file")
            typ = row[i_typ]
            cols["source_id"].append(int(row[i_sid]))
            cols["solution_id"].append(int(row[i_sol]))
            cols["nss_solution_type"].append(typ)
            for n, i in picks:
                cols[n].append(_f(row[i]))
            if typ.startswith(ASTROMETRIC_PREFIXES):
                text = row[i_corr].strip("[]").replace("NaN", "nan")
                vec = np.array(text.split(","), dtype=np.float32) if text else np.empty(0, np.float32)
                if len(vec) > MAX_CORR:
                    raise NetError("corr_vec longer than any supported layout")
                corr_rows.append(vec)
                corr_len.append(len(vec))
            else:
                corr_rows.append(None)
                corr_len.append(0)
    n = len(cols["source_id"])
    out = {
        "source_id": np.array(cols["source_id"], dtype=np.int64),
        "solution_id": np.array(cols["solution_id"], dtype=np.int64),
        "nss_solution_type": np.array(cols["nss_solution_type"]),
        "corr_len": np.array(corr_len, dtype=np.int16),
    }
    for name in names:
        out[name] = np.array(cols[name], dtype=np.float64)
    corr = np.full((n, MAX_CORR), np.nan, dtype=np.float32)
    for i, vec in enumerate(corr_rows):
        if vec is not None and len(vec):
            corr[i, : len(vec)] = vec
    out["corr_vec"] = corr
    return out


def load_table(store_dir, expected_rows=EXPECTED_ROWS) -> tuple[dict, dict]:
    """Columns plus provenance. Parsed columns are cached beside the bulk file,
    keyed by its SHA-256, so a changed file is never read through a stale cache."""
    store = Path(store_dir)
    prov = json.loads((store / "bulk_provenance.json").read_text())
    path = store / BULK_FILE
    if sha256_file(path) != prov["sha256"]:
        raise NetError("bulk file changed since it was verified")
    cache = store / f"columns.{prov['sha256'][:16]}.npz"
    if cache.exists():
        with np.load(cache, allow_pickle=False) as z:
            table = {k: z[k] for k in z.files}
    else:
        table = parse_bulk(path)
        np.savez(cache, **table)
    n = len(table["source_id"])
    if expected_rows is not None and n != expected_rows:
        raise NetError(f"bulk table has {n} rows, expected {expected_rows}")
    keys = np.char.add(table["source_id"].astype(str), np.char.add(":", table["nss_solution_type"]))
    if len(np.unique(keys)) != n:
        raise NetError("duplicate source/solution records in bulk table")
    return table, dict(prov, rows=n)


def select(table: dict, mask) -> dict:
    return {k: v[mask] for k, v in table.items()}
