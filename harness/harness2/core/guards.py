"""Immutable-in-the-proposal-loop scientific guard boundary, not an OS sandbox."""

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_guard():
    expected = json.loads((ROOT / "policy/guard_manifest.json").read_text())
    for name, digest in expected["files"].items():
        p = ROOT / name
        if Path(name).is_absolute() or ".." in Path(name).parts or not p.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("Invalid guard manifest path")
        if p.is_symlink() or sha(p) != digest:
            raise RuntimeError("Protected scientific code changed: " + name)
    return sha(ROOT / "policy/guard_manifest.json")


def load_policy():
    return json.loads((ROOT / "policy/scientific_policy.json").read_text())


def disposition(measured, known):
    sid = measured["source_id"]
    typ = measured["nss_solution_type"]
    if sid in known:
        entry = known[sid]
        return {
            "status": entry["status"],
            "novelty_status": "PREVIOUSLY_PUBLISHED",
            "reasons": [entry["reason"]],
            "evidence": entry["evidence"],
        }
    if measured["f_phot_solar"] <= load_policy()["review_anomaly_threshold_f_phot"]:
        return {
            "status": "NOT_SHORTLISTED",
            "novelty_status": "NOT_ASSESSED",
            "reasons": ["Below exploratory photocentre observable threshold"],
            "evidence": [],
        }
    reasons = [
        "No exhaustive literature/novelty clearance",
        "No independent orbit and luminous/blend/triple-alternative validation",
    ]
    if "Alternative" in typ or "Targeted" in typ:
        reasons.append("Alternative/targeted solution needs independent review")
    unc = measured["uncertainty"]
    if unc.get("status") == "UNAVAILABLE":
        reasons.append("Full supported covariance unavailable or invalid")
    else:
        reasons.append("Catalog covariance propagation does not establish orbital validity")
        threshold = load_policy()["review_anomaly_threshold_f_phot"]
        # Informational only: the hold stands either way.
        if unc.get("f_phot_q05", 0) > threshold:
            reasons.append("Propagated f_phot 5th percentile also exceeds threshold")
        else:
            reasons.append("Propagated f_phot 5th percentile falls below threshold; anomaly may be noise")
    return {
        "status": "HOLD_QUALITY_AND_NOVELTY",
        "novelty_status": "UNKNOWN_NOT_CLEARED",
        "reasons": reasons,
        "evidence": [],
    }
