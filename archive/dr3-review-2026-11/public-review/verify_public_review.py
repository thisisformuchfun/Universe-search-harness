"""Offline checks of the dated public literature packet; does not change research state."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
EXPECTED = {
    "li-2026-source.raw": "243e8ec21a7e4d7b4300dedecb16d5616bfd6d4a96774e854fa52cdd23953016",
    "simon-2026-source.raw": "838447d246a87cfa1f56d1bf0b8ee24908a7cbbae3d8903bcf2875877fe8715d",
    "muller-ms.csv": "72e76ab548df79f942bb064360ce1c4eacb607e2d067920818709e263d9cdaa2",
    "muller-rgb.csv": "dbe32424ff4ec5fa773d92ac2892958ae080e777f6a8d2afcaf19617553fcdb5",
    "zhou-table.raw": "94f41f32f8c0d34798fc223d4af10fd19a16fc63bc9e30069a6d2ff4ead90267",
    "xp-evidence.json": "0e1e78812b9308b104a16cd4132871732a902332b16611f8837d54698708b50e",
    "wide-pair-evidence.json": "b52522a68a9b9bf3e08a72eb808432645f1aa4ecbce4e27929cc689a42443278",
    "lamost-identifications.json": "063c1d5a8ce80261d5c332607e6ea75b800d49844144a2104a354041f7bf6d90",
    "gaia-2mass-crossmatch.raw": "2a49eccecc716e4fe4e8a5d3b5dc3189da198fbf8b6b01dcb3a6264ede6d04f9",
    "held-objects.json": "989a7695c1f7110d54e703d2fd55ee4e016511b8adf568ca4ef5c2e370519d09",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def whole_id(text, source_id):
    return bool(re.search(r"(?<![0-9])" + re.escape(source_id) + r"(?![0-9])", text))


def checked_bytes(name):
    data = (EVIDENCE / name).read_bytes()
    require(hashlib.sha256(data).hexdigest() == EXPECTED[name], f"Evidence hash mismatch: {name}")
    return data


def member_text(data, name, expected=None):
    # Do not extract article archives or execute content from them.
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        member = archive.getmember(name)
        require(member.isfile() and member.size <= 2_000_000, "Unsupported archive member")
        raw = archive.extractfile(member).read()
    if expected:
        require(hashlib.sha256(raw).hexdigest() == expected, "Article table hash mismatch")
    return raw.decode("utf-8", "replace")


def source_catalogue(raw, expected_count, expected_md5):
    require(hashlib.md5(raw).hexdigest() == expected_md5, "Author catalogue checksum mismatch")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    ids = [row.get("source_id") for row in rows]
    require(len(ids) == expected_count and len(set(ids)) == expected_count and all(x and x.isdigit() for x in ids), "Catalogue identity mismatch")
    return set(ids)


def main():
    review = json.loads((ROOT / "review.json").read_text(encoding="utf-8-sig"))
    snapshot = json.loads((ROOT.parent / "dashboard" / "src" / "snapshot.json").read_text(encoding="utf-8-sig"))
    rows = snapshot["rows"]
    ids = [row["source_id"] for row in rows]
    require(len(ids) == 14 and len(set(ids)) == 14 and all(isinstance(x, str) and x.isdigit() for x in ids), "Expected fourteen exact string identifiers")
    held = json.loads(checked_bytes("held-objects.json"))
    require({r["source_id"] for r in held["sources"]} == set(ids), "Held-queue identities differ")
    require(set(review["reviews"]) == set(ids), "Review coverage differs")
    require(all(row["public_review"] == review["reviews"][row["source_id"]] for row in rows), "Dashboard review details differ")

    li = member_text(checked_bytes("li-2026-source.raw"), "Compact_binary_Gaia_DR3_RV_arxiv.tex")
    li_ids = {sid for sid in ids if whole_id(li, sid)}
    require(li_ids == {"4491401821468887552", "824344003814438528"}, "Li positive controls failed")
    require(re.search(r"\\author\[\]\{Ye Xu\}[\s\S]{0,1200}\\email\[show\]\{xuye@pmo\.ac\.cn\}", li), "Li corresponding-author control failed")

    simon = member_text(checked_bytes("simon-2026-source.raw"), "sample_table.tex", "57fa33fa38355b7bac59dcf473d8102baf40d7879fcc48bad7ec423ae31ea9b0")
    simon_ids = re.findall(r"(?m)^\s*(\d{16,19})(?=\s*&|\\tablenotemark)", simon)
    require(len(simon_ids) == 34 and len(set(simon_ids)) == 34 and "4373465352415301632" in simon_ids, "Simon sample control failed")
    muller_ids = source_catalogue(checked_bytes("muller-ms.csv"), 19664, "07eb6acff1f98d3a656741f2e61daed3")
    muller_ids |= source_catalogue(checked_bytes("muller-rgb.csv"), 21028, "000dac405ed9e75d28f7c47d206ec345")
    zhou = checked_bytes("zhou-table.raw")
    lines = [line for line in zhou.decode("ascii").splitlines() if len(line) == 197 and line[:19].strip().isdigit() and line[62:65].strip() in ("II", "III")]
    zhou_ids = [line[:19].strip() for line in lines]
    require(len(zhou_ids) == 17 and len(set(zhou_ids)) == 17, "Zhou Table 2 control failed")
    previous = json.loads((EVIDENCE / "zhou-comparison.json").read_text(encoding="utf-8-sig"))
    require(previous.get("table_body_sha256") == hashlib.sha256(zhou).hexdigest() and previous.get("target_count") == 14 and previous.get("table1_type_i_count") == 2 and previous.get("table1_type_i_matches") == [], "Saved Zhou Type I comparison unavailable")
    require(not (set(ids) & (set(simon_ids) | muller_ids | set(zhou_ids))), "Unexpected finite-sample match")

    xp = json.loads(checked_bytes("xp-evidence.json"))
    xp_rows = {r["source_id"]: r for r in xp["rows"]}
    require(set(xp_rows) == set(ids) and xp.get("matched_source_count") == 8 and xp.get("full_hdf5_file_checksum_verified") is False, "XP scope or membership differs")
    pair = json.loads(checked_bytes("wide-pair-evidence.json"))["exact_selected_fields"]
    require(pair["Source1"]["exact_text"] == "2852726284550996352" and pair["Source2"]["exact_text"] == "2852726284550996224", "Wide-pair identity differs")
    ident = json.loads(checked_bytes("lamost-identifications.json"))
    ident_rows = {r["source_id"]: r for r in ident["sources"]}
    require(set(ident_rows) == set(ids), "LAMOST identity coverage differs")
    obs = [(sid, item["obsid"]) for sid in ids for item in ident_rows[sid]["lamost_distinct_observations"]]
    require(set(obs) == {("1533365584518328576", "294101037"), ("4491401821468887552", "664307135")}, "LAMOST observation identities differ")

    cross = ET.fromstring(checked_bytes("gaia-2mass-crossmatch.raw"))
    fields = [f.attrib.get("name") for f in cross.findall(".//{*}FIELD")]
    require({"source_id", "original_ext_source_id", "angular_distance", "number_of_mates"} <= set(fields), "Crossmatch schema differs")
    cross_rows = {}
    for tr in cross.findall(".//{*}TR"):
        cells = [(td.text or "").strip() for td in tr.findall("{*}TD")]
        require(len(cells) == len(fields), "Crossmatch row width differs")
        row = dict(zip(fields, cells)); sid = row["source_id"]
        require(sid in ids and sid not in cross_rows and re.fullmatch(r"\d{8}[+-]\d{7}", row["original_ext_source_id"]), "Crossmatch identity differs")
        separation = float(row["angular_distance"]); mates = int(row["number_of_mates"])
        require(math.isfinite(separation) and separation >= 0 and mates >= 0, "Crossmatch values invalid")
        cross_rows[sid] = ("2MASS J" + row["original_ext_source_id"], separation, mates)
    require(set(cross_rows) == set(ids), "Crossmatch coverage differs")

    for sid in ids:
        result = review["reviews"][sid]
        matches = result["matches"]
        kinds = [m["kind"] for m in matches]
        require(("Published compact-candidate study" in kinds) == (sid in li_ids), f"Li review mismatch: {sid}")
        require(("Published spectral-model catalogue row" in kinds) == (xp_rows[sid].get("published_model_fields") is not None), f"XP review mismatch: {sid}")
        require(("Published wide-pair catalogue entry" in kinds) == (sid == "2852726284550996352"), f"Wide-pair review mismatch: {sid}")
        require(kinds.count("Public spectrum") == len(ident_rows[sid]["lamost_distinct_observations"]), f"Spectrum review mismatch: {sid}")
        cross_id = result["cross_id"]; designation, separation, mates = cross_rows[sid]
        require(cross_id["designation"] == designation and cross_id["separation_arcsec"] == separation and cross_id["number_of_mates"] == mates, f"Crossmatch review mismatch: {sid}")
        checks = result["checks"]
        require(len(checks) == 4 and (checks[0]["result"] == "Exact ID appears in the printed tables.") == (sid in li_ids), f"Li table review mismatch: {sid}")
        require("No exact ID match" in checks[1]["result"] and "No exact ID match" in checks[2]["result"] and "No exact ID match" in checks[3]["result"], f"Finite-sample review mismatch: {sid}")
    require(review["counts"] == {"sources": 14, "compact_candidate_paper_matches": 2, "xp_parent_dataset_matches": 8, "published_wide_pair_matches": 1, "public_lamost_spectra": 2}, "Review count mismatch")
    print("Verified: 14 exact IDs, 2 published candidate controls, 8 XP rows, 1 wide pair, 2 spectra, 14 Gaia/2MASS matches.")
    print("Finite samples only; no novelty clearance or new black-hole confirmation.")


if __name__ == "__main__":
    main()
