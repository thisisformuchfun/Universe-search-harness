"""Real-data Propose/Probe/Compose for review ranking, with a sealed science policy.

The utility is an explicit engineering heuristic, not a detection metric. Proposals
see training aggregates only. Validation selects a bounded configuration. Held-out
metrics are unavailable here and require an explicit frozen-run evaluation.
"""

import hashlib
import math
from concurrent.futures import ThreadPoolExecutor
from harness2.core.components import HarnessBundle
from harness2.core.guards import verify_guard


def partition(source_id):
    p = int.from_bytes(hashlib.sha256(source_id.encode("ascii")).digest()[:8], "big") % 10
    return "train" if p < 6 else "validation" if p < 8 else "test"


def features(r):
    return (
        math.log1p(min(r["f_phot_solar"], 1e6)),
        -math.log1p(100 * (r["parallax_relative_error"] + r["period_relative_error"])),
        r["efficiency"] or 0.0,
    )


def rank(rows, config):
    def score(r):
        return sum(a * b for a, b in zip(features(r), config.to_dict().values()))

    return sorted(rows, key=lambda r: (-score(r), r["record_id"]))


def utility(rows, config, budget=20):
    """Frozen quality-weighted triage utility; no completeness/FAP/detection claim."""
    top = rank(rows, config)[:budget]
    if not top:
        return {"utility": None, "evaluated": 0}
    values = []
    for r in top:
        # Precision/efficiency and standard-solution preference are ranking utility only.
        precision = 1 / (1 + 10 * (r["parallax_relative_error"] + r["period_relative_error"]))
        quality = 0.5 * precision + 0.5 * (r["efficiency"] or 0.0)
        if "Alternative" in r["nss_solution_type"] or "Targeted" in r["nss_solution_type"]:
            quality *= 0.25
        values.append(quality)
    return {"utility": sum(values) / len(values), "evaluated": len(top)}


class Harness2Engine:
    def __init__(self, router, library):
        self.router = router
        self.library = library

    def run_task(self, records, k=2, mode="parallel", budget=20):
        if not 1 <= budget <= 1000:
            raise ValueError("review budget outside 1..1000")
        if mode not in ("parallel", "sequential") or not 1 <= k <= 32:
            raise ValueError("Invalid mode/budget")
        guard = verify_guard()
        base = self.library.load(guard)
        # Known objects never participate in novel-review ranking or adaptation.
        eligible = [r for r in records if r["status"] == "HOLD_QUALITY_AND_NOVELTY"]
        train = [r for r in eligible if partition(r["source_id"]) == "train"]
        val = [r for r in eligible if partition(r["source_id"]) == "validation"]
        train_summary = {
            "count": len(train),
            "mean_f_phot": sum(r["f_phot_solar"] for r in train) / len(train) if train else None,
            "mean_relative_error": (
                sum(r["parallax_relative_error"] + r["period_relative_error"] for r in train) / len(train)
                if train
                else None
            ),
        }
        best = base
        current = utility(val, best, budget)
        traces = []
        for step in range(k):
            parent = base if mode == "parallel" else best
            proposed = self.router.propose(parent, train_summary, step)
            # A deterministic domain proposal emphasizes measurement precision, not target yield.
            domain = HarnessBundle.from_dict(
                {**parent.to_dict(), "precision_weight": min(4.0, parent.precision_weight + 0.5)}
            )
            composed = HarnessBundle.from_dict(
                {key: (proposed.to_dict()[key] + domain.to_dict()[key]) / 2 for key in proposed.to_dict()}
            )
            configs = [proposed, domain, composed]
            if mode == "parallel":
                with ThreadPoolExecutor(max_workers=3) as ex:
                    probes = list(ex.map(lambda c: utility(val, c, budget), configs))
            else:
                probes = [utility(val, c, budget) for c in configs]
            winner = best
            metric = current
            # Strict improvement only, so scant/empty validation never creates a false lesson.
            for c, p in zip(configs, probes):
                if (
                    p["utility"] is not None
                    and metric["utility"] is not None
                    and p["utility"] > metric["utility"] + 1e-12
                ):
                    winner, metric = c, p
            traces.append(
                {
                    "step": step,
                    "mode": mode,
                    "parent": parent.to_dict(),
                    "proposed": proposed.to_dict(),
                    "domain": domain.to_dict(),
                    "composed": composed.to_dict(),
                    "validation_probes": probes,
                    "adopted": winner.to_dict(),
                }
            )
            best, current = winner, metric
            if verify_guard() != guard:
                raise RuntimeError("Guard modified while probing")
        result = {
            "review_budget": budget,
            "mode": mode,
            "k": k,
            "guard_hash": guard,
            "train_rows": len(train),
            "validation_rows": len(val),
            "base_configuration": base.to_dict(),
            "adopted_configuration": best.to_dict(),
            "validation_metric": current,
            "traces": traces,
            "model_calls": self.router.call_count,
            "provider": self.router.config.provider,
            "model": self.router.config.model if self.router.config.provider == "local" else None,
            "metric_meaning": "Quality-weighted triage utility only. Not precision/recall, SNR, FAP, discovery yield or model training.",
        }
        if len(train) >= 5 and len(val) >= 3 and current["utility"] is not None:
            self.library.save(
                best,
                guard,
                {"training_rows": len(train), "validation_rows": len(val), "validation_metric": current},
            )
            result["memory_saved"] = True
        else:
            result["memory_saved"] = False
        return result, rank(eligible, best)
