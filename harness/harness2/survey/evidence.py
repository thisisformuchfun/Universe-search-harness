"""Batched evidence gathering for shortlisted candidates.

One query serves hundreds of candidates, where the agent tools issue one query
per candidate. Queries are fixed templates filled with validated integer IDs.
Text that comes back from an archive (titles, object types) is only ever
compared against fixed patterns; it is never executed or followed.
"""

from __future__ import annotations

import math
import re

from harness2.survey.net import GAIA_TAP, SIMBAD_TAP_MIRRORS, VIZIER_ASU_MIRRORS, Fetcher, NetError, safe_ids, tsv_table

BATCH = 150
MEMBERSHIP_TABLES = {
    "vari_eclipsing_binary": "Gaia DR3 photometric eclipsing-binary candidate",
    "vari_compact_companion": "Gaia DR3 ellipsoidal variable with possible compact companion (Gomel et al. 2023)",
    "nss_acceleration_astro": "Gaia DR3 astrometric acceleration solution for the same source",
    "nss_non_linear_spectro": "Gaia DR3 spectroscopic trend solution for the same source",
}
FLAME_COLUMNS = ("mass_flame", "radius_flame", "lum_flame", "evolstage_flame", "age_flame")
# Fixed patterns only. A hit means "someone has discussed this object in this context".
COMPACT_TITLE = re.compile(
    r"black[\s-]?hole|neutron[\s-]?star|compact (object|companion|binar)|dark companion|dormant|"
    r"unseen companion|non-?interacting|white[\s-]?dwarf|massive companion",
    re.IGNORECASE,
)
COMPACT_OTYPES = frozenset({"BH", "BH?", "N*", "N*?", "XB*", "HXB", "LXB", "XB?", "HX?", "LX?", "Psr", "WD*", "WD?", "CV*", "CV?"})


def _batches(ids, size=BATCH):
    ids = safe_ids(ids)
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _num(text):
    try:
        return float(text) if text not in ("", "null") else None
    except ValueError:
        return None


def check_schema(fetcher: Fetcher, release="gaiadr3"):
    """Confirm every table this module queries exists in the release. Fails closed."""
    wanted = [f"{release}.{t}" for t in (*MEMBERSHIP_TABLES, "gaia_source", "astrophysical_parameters")]
    _, rows, prov = fetcher.tap_csv(
        GAIA_TAP, f"SELECT table_name FROM tap_schema.tables WHERE schema_name = '{release}'", "schema check"
    )
    have = {r[0] for r in rows}
    missing = sorted(set(wanted) - have)
    if missing:
        raise NetError(f"archive lacks tables the vetting stage needs: {missing}")
    return prov


def gaia_positions(fetcher: Fetcher, ids, release="gaiadr3"):
    out, prov = {}, []
    for batch in _batches(ids, 400):
        _, rows, p = fetcher.tap_csv(
            GAIA_TAP, f"SELECT source_id, ra, dec FROM {release}.gaia_source WHERE source_id IN ({','.join(batch)})", "positions", expect_rows=len(batch)
        )
        prov.append(p)
        out.update({r[0]: (float(r[1]), float(r[2])) for r in rows})
    return out, prov


def gaia_neighbours(fetcher: Fetcher, positions, radius_arcsec, release="gaiadr3"):
    """Other Gaia sources within the radius of each candidate. {source_id: [..]}

    positions: {source_id: (ra_deg, dec_deg)} from gaia_positions. One query covers
    a batch of small cones; separations are then computed locally.
    """
    targets = [(safe_ids([sid])[0], float(ra), float(dec)) for sid, (ra, dec) in positions.items()]
    if any(not (0 <= ra < 360 and -90 <= dec <= 90) for _, ra, dec in targets):
        raise NetError("target coordinates out of range")
    out, prov = {sid: [] for sid, _, _ in targets}, []
    rad = float(radius_arcsec) / 3600.0
    for i in range(0, len(targets), 40):
        batch = targets[i : i + 40]
        cones = " OR ".join(
            f"1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra:.8f},{dec:.8f},{rad:.8f}))" for _, ra, dec in batch
        )
        q = f"SELECT source_id, ra, dec, phot_g_mean_mag FROM {release}.gaia_source WHERE {cones}"
        _, rows, p = fetcher.tap_csv(GAIA_TAP, q, "neighbours")
        prov.append(p)
        found = {r[0]: (float(r[1]), float(r[2]), _num(r[3])) for r in rows}
        for sid, ra, dec in batch:
            if sid not in found:
                raise NetError(f"cone search did not return the target {sid} itself")
            tg = found[sid][2]
            for other, (ora, odec, og) in found.items():
                if other == sid:
                    continue
                sep = 3600.0 * math.hypot((ora - ra) * math.cos(math.radians(dec)), odec - dec)
                if sep <= radius_arcsec:
                    delta = og - tg if og is not None and tg is not None else None
                    out[sid].append({"neighbour_id": other, "sep_arcsec": round(sep, 3), "delta_g": delta})
    return out, prov


def gaia_membership(fetcher: Fetcher, ids, release="gaiadr3"):
    """Which candidates appear in each auxiliary Gaia table. {table: set(ids)}"""
    out, prov = {t: set() for t in MEMBERSHIP_TABLES}, []
    for table in MEMBERSHIP_TABLES:
        for batch in _batches(ids, 400):
            _, rows, p = fetcher.tap_csv(
                GAIA_TAP, f"SELECT DISTINCT source_id FROM {release}.{table} WHERE source_id IN ({','.join(batch)})", table
            )
            prov.append(p)
            out[table].update(r[0] for r in rows)
    return out, prov


def gaia_flame(fetcher: Fetcher, ids, release="gaiadr3"):
    out, prov = {}, []
    for batch in _batches(ids, 400):
        _, rows, p = fetcher.tap_csv(
            GAIA_TAP,
            f"SELECT source_id,{','.join(FLAME_COLUMNS)} FROM {release}.astrophysical_parameters WHERE source_id IN ({','.join(batch)})",
            "flame",
        )
        prov.append(p)
        for r in rows:
            out[r[0]] = {name: _num(v) for name, v in zip(FLAME_COLUMNS, r[1:])}
    return out, prov


def simbad(fetcher: Fetcher, ids):
    """SIMBAD identification and bibliography for each candidate, via the first mirror that answers."""
    out = {s: {"found": False, "bibcodes": [], "compact_context_refs": []} for s in safe_ids(ids)}
    prov = []
    for batch in _batches(ids, 100):
        names = ",".join(f"'Gaia DR3 {s}'" for s in batch)
        q1 = f"SELECT i.id, b.main_id, b.otype, b.nbref FROM ident AS i JOIN basic AS b ON i.oidref = b.oid WHERE i.id IN ({names})"
        q2 = (
            "SELECT i.id, r.bibcode, r.title FROM ident AS i JOIN has_ref AS h ON h.oidref = i.oidref "
            f"JOIN ref AS r ON h.oidbibref = r.oidbib WHERE i.id IN ({names})"
        )
        _, rows, p = fetcher.first_working(SIMBAD_TAP_MIRRORS, lambda ep: fetcher.tap_csv(ep, q1, "simbad basic"))
        prov.append(p)
        for ident, main_id, otype, nbref in rows:
            sid = ident.replace("Gaia DR3", "").strip()
            if sid in out:
                out[sid].update(found=True, main_id=main_id.strip(), otype=otype.strip(), nbref=int(nbref or 0), compact_otype=otype.strip() in COMPACT_OTYPES)
        _, rows, p = fetcher.first_working(SIMBAD_TAP_MIRRORS, lambda ep: fetcher.tap_csv(ep, q2, "simbad refs"))
        prov.append(p)
        for ident, bibcode, title in rows:
            sid = ident.replace("Gaia DR3", "").strip()
            if sid not in out:
                continue
            out[sid]["bibcodes"].append(bibcode)
            if COMPACT_TITLE.search(title or ""):
                out[sid]["compact_context_refs"].append({"bibcode": bibcode, "title": (title or "")[:160]})
    for entry in out.values():
        entry["bibcodes"] = sorted(set(entry["bibcodes"]), reverse=True)
    return out, prov


def vizier_catalog_ids(fetcher: Fetcher, spec: dict):
    """All Gaia source IDs listed in one published catalogue (ID column only)."""
    table, column = spec["table"], spec["id_column"]
    if not re.fullmatch(r"[A-Za-z0-9+/._-]{3,80}", table) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", column):
        raise NetError("catalogue specification fails validation")
    query = f"?-source={table}&-out={column}&-out.max=unlimited"

    def attempt(base):
        raw, p = fetcher.fetch(base + query, label=f"vizier {table}")
        header, rows = tsv_table(raw)
        if column not in header:
            raise NetError(f"VizieR table {table} has no column {column}")
        i = header.index(column)
        ids = {r[i].strip() for r in rows if re.fullmatch(r"[0-9]{6,19}", r[i].strip())}
        if not ids:
            raise NetError(f"VizieR table {table} returned no Gaia IDs")
        if spec.get("rows") and len(rows) != spec["rows"]:
            raise NetError(f"VizieR table {table}: {len(rows)} rows, expected {spec['rows']}")
        return ids, dict(p, rows=len(rows))

    return fetcher.first_working(VIZIER_ASU_MIRRORS, attempt)


SHAHAF_TABLE = {"table": "J/MNRAS/518/2991/table1", "rows": 101380, "bibcode": "2023MNRAS.518.2991S"}


def shahaf_classification(fetcher: Fetcher):
    """Published AMRF class probabilities (Shahaf et al. 2023, table 1) for the clean
    astrometric sample: {source_id: {"p_class2": .., "p_class3": ..}}. Class III means
    neither one main-sequence star nor a close main-sequence pair explains the orbit."""
    query = f"?-source={SHAHAF_TABLE['table']}&-out=GaiaDR3&-out=PII&-out=PIII&-out.max=unlimited"

    def attempt(base):
        raw, p = fetcher.fetch(base + query, label="vizier shahaf2023 classes")
        header, rows = tsv_table(raw)
        if not {"GaiaDR3", "PII", "PIII"} <= set(header):
            raise NetError("Shahaf table 1 lacks the expected columns")
        if len(rows) != SHAHAF_TABLE["rows"]:
            raise NetError(f"Shahaf table 1: {len(rows)} rows, expected {SHAHAF_TABLE['rows']}")
        i, j, k = (header.index(c) for c in ("GaiaDR3", "PII", "PIII"))
        out = {}
        for r in rows:
            sid = r[i].strip()
            if re.fullmatch(r"[0-9]{6,19}", sid):
                out[sid] = {"p_class2": _num(r[j].strip()), "p_class3": _num(r[k].strip())}
        return out, dict(p, rows=len(rows))

    return fetcher.first_working(VIZIER_ASU_MIRRORS, attempt)
