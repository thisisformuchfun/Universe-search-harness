"""Labeled controls, scoring, and the harness2 Propose/Probe/Compose outer loop.

Controls are snapshot sources already known to be published (Gaia BH1/BH2,
refuted candidates, Shahaf 2023 and Jayasinghe 2023 members, Li 2026
candidates). In blind mode the catalog that produced a control's label is
withheld, so the agent has to rediscover it through other routes (SIMBAD
bibliography, the other catalog, ADS). Because every PUBLISHED_PRIOR verdict
must cite a real matched=true tool result, "always say published" scores zero.

What gets optimized is only the Playbook. Tools, verifier, controls and
scoring are guarded and cannot be changed by a proposal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from harness2.agent.loop import investigate
from harness2.agent.models import ModelError
from harness2.agent.schema import Budget, Playbook, canonical_hash
from harness2.core.guards import ROOT, verify_guard
from harness2.core.library import atomic_json

CONTROLS_PATH = ROOT / "data/controls/controls_v1.json"
LI2026_CONTROLS = ("4491401821468887552", "824344003814438528")


def split_of(source_id: str) -> str:
    h = int.from_bytes(hashlib.sha256(("controls-v1:" + source_id).encode()).digest()[:8], "big") % 10
    return "tune" if h < 6 else "test"


def build_controls(records, known, catalog_members):
    """catalog_members: {catalog_key: set(source_ids)} from the bundled TSV snapshots."""
    in_run = {r["source_id"] for r in records}
    controls = []
    for sid in sorted(in_run, key=int):
        sources = [k for k, ids in sorted(catalog_members.items()) if sid in ids]
        if sid in known and known[sid]["status"] in ("EXCLUDE_KNOWN_BH", "EXCLUDE_PRIOR_REFUTED_CANDIDATE"):
            sources.append("known_objects")
        if sid in LI2026_CONTROLS:
            sources.append("li2026")
        if sources:
            controls.append(
                {"source_id": sid, "label": "PUBLISHED_PRIOR", "label_sources": sources, "split": split_of(sid)}
            )
    return {
        "version": "controls-v1",
        "meaning": "Sources in the bundled 500-row snapshot already published as compact-companion candidates, "
        "known black holes or refuted candidates. Positives only: absence of a label is not novelty.",
        "blind_rule": "Hide known_catalogs and withhold each control's labeling VizieR catalog.",
        "controls": controls,
    }


def load_controls(path=CONTROLS_PATH):
    data = json.loads(Path(path).read_text())
    return data, hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_batch(items, model, box, playbook, budget, out_dir=None, blind=True, progress=None):
    """items: list of {"source_id", optional "label_sources"}."""
    results = []
    for i, item in enumerate(items):
        hidden = ("known_catalogs",) if blind else ()
        blocked = (
            tuple(s for s in item.get("label_sources", ()) if s in box.policy["vizier_catalogs"]) if blind else ()
        )
        session = box.session(item["source_id"], hidden=hidden, blocked_catalogs=blocked)
        res = investigate(item["source_id"], model, session, playbook, budget)
        if "label" in item:
            res["label"] = item["label"]
        results.append(res)
        if out_dir:
            atomic_json(Path(out_dir) / "investigations" / f"{item['source_id']}.json", res)
        if progress:
            progress(i + 1, len(items), res)
    if out_dir:
        with open(Path(out_dir) / "verdicts.jsonl", "w", encoding="utf-8") as fh:
            for r in results:
                fh.write(
                    json.dumps(
                        {
                            k: r.get(k)
                            for k in ("source_id", "label", "accepted_verdict", "stop_reason", "usage", "playbook")
                        }
                    )
                    + "\n"
                )
    return results


def score(results, cost_weight_calls=0.02, cost_weight_ktokens=0.002):
    n = len(results)
    if not n:
        return {"n": 0, "objective": None}
    labeled = [r for r in results if "label" in r]
    correct = sum(r["accepted_verdict"] == r["label"] for r in labeled)
    valid = sum(r["verification"]["valid"] for r in results)
    checked = sum(r["verification"]["evidence_checked"] for r in results)
    failed = sum(r["verification"]["evidence_failed"] for r in results)
    calls = sum(len(r["tool_calls"]) for r in results) / n
    tokens = sum(r["usage"]["input_tokens"] + r["usage"]["output_tokens"] for r in results) / n
    recall = correct / len(labeled) if labeled else None
    verified = valid / n
    s = {
        "n": n,
        "recall": recall,
        "verified_rate": verified,
        "citation_failure_rate": failed / checked if checked else 0.0,
        "mean_tool_calls": calls,
        "mean_tokens": tokens,
        "verdict_counts": _counts(r["accepted_verdict"] for r in results),
        "meaning": "recall = verified PUBLISHED_PRIOR on blind positive controls. Not a discovery metric.",
    }
    s["objective"] = (
        (recall or 0.0) + 0.25 * verified - cost_weight_calls * calls - cost_weight_ktokens * tokens / 1000
    )
    return s


def _counts(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def failures(results, limit=6):
    out = []
    for r in results:
        if r.get("label") and r["accepted_verdict"] != r["label"]:
            out.append(
                {
                    "source_id": r["source_id"],
                    "expected": r["label"],
                    "got": r["accepted_verdict"],
                    "submitted": (r["verdict"] or {}).get("verdict"),
                    "verifier_errors": r["verification"]["errors"][:3],
                    "tools_called": [(c["tool"], c["args"].get("catalog"), c["ok"]) for c in r["tool_calls"]],
                    "stop_reason": r["stop_reason"],
                }
            )
    return out[:limit]


# ------------------------------------------------------------ proposers


class RuleProposer:
    """Deterministic proposer; the no-LLM baseline for the outer loop."""

    name = "rule"

    def propose(self, current: Playbook, summary, fails, step):
        d = current.to_dict()
        if any(f["stop_reason"] != "submitted" or any("limit" in e for e in f["verifier_errors"]) for f in fails):
            d["max_tool_calls"] = min(20, d["max_tool_calls"] + 2)
        tools_seen = {t for f in fails for t, _, _ in f["tools_called"]}
        order = list(d["tool_priority"])
        for t in ("simbad_lookup", "ads_search", "vizier_crossmatch"):
            if t not in tools_seen and t in order:
                order.remove(t)
                order.insert(0, t)
                break
        else:
            order = order[1:] + order[:1] if step % 2 else order
        d["tool_priority"] = order
        d["notes"] = current.notes
        return Playbook.from_dict(d)


class LLMProposer:
    name = "llm"
    TOOL = {
        "name": "submit_playbook",
        "description": "Return an improved playbook.",
        "parameters": {
            "type": "object",
            "properties": {
                "notes": {"type": "string", "maxLength": 2000},
                "tool_priority": {"type": "array", "items": {"type": "string"}},
                "max_tool_calls": {"type": "integer", "minimum": 2, "maximum": 20},
                "stop_when_published": {"type": "boolean"},
            },
            "required": ["notes", "tool_priority", "max_tool_calls", "stop_when_published"],
        },
    }

    def __init__(self, model):
        self.model = model

    def propose(self, current: Playbook, summary, fails, step):
        messages = [
            {
                "role": "system",
                "content": (
                    "You improve a playbook for an astronomy triage agent. The agent must find published prior work "
                    "on Gaia binaries using only its tools, and cite tool output exactly. You see its score on "
                    "labeled controls and failure traces. Change strategy, not facts. You cannot change tools, "
                    "the verifier, or the controls. Keep notes short; every token is paid on every candidate."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"current_playbook": current.to_dict(), "score": summary, "failures": fails, "round": step}
                ),
            },
        ]
        turn = self.model.complete(messages, [self.TOOL])
        for call in turn.tool_calls:
            if call.name == "submit_playbook":
                return Playbook.from_dict(call.arguments)
        raise ModelError("proposer did not call submit_playbook")


def compose(current: Playbook, proposed: Playbook) -> Playbook:
    """Crossover: proposed strategy text with the current tool order and the larger call budget."""
    return Playbook.from_dict(
        {
            **proposed.to_dict(),
            "tool_priority": list(current.tool_priority),
            "max_tool_calls": max(current.max_tool_calls, proposed.max_tool_calls),
        }
    )


class PlaybookLibrary:
    def __init__(self, path):
        self.path = Path(path)

    def load(self, guard, controls_hash):
        if not self.path.exists():
            return Playbook(), None
        obj = json.loads(self.path.read_text())
        if obj.get("guard_hash") != guard or obj.get("controls_sha256") != controls_hash:
            raise ValueError("playbook memory was tuned under different code or controls; start a new memory file")
        return Playbook.from_dict(obj["playbook"]), obj.get("tune_score")

    def save(self, playbook, guard, controls_hash, tune_score, history):
        atomic_json(
            self.path,
            {
                "guard_hash": guard,
                "controls_sha256": controls_hash,
                "playbook": playbook.to_dict(),
                "playbook_digest": playbook.digest(),
                "tune_score": tune_score,
                "history": history,
                "meaning": "Strategy tuned on the tune split of positive controls only.",
            },
        )


def optimize(
    agent_model,
    proposer,
    box,
    controls,
    controls_hash,
    rounds,
    budget: Budget,
    library_path,
    out_dir=None,
    limit=None,
    progress=None,
):
    guard = verify_guard()
    tune = [c for c in controls["controls"] if c["split"] == "tune"][: limit or None]
    lib = PlaybookLibrary(library_path)
    current, _ = lib.load(guard, controls_hash)
    cur_res = run_batch(tune, agent_model, box, current, budget, progress=progress)
    cur_score = score(cur_res)
    history = [{"round": 0, "playbook": current.digest(), "score": cur_score, "adopted": True}]
    seen = {current.digest()}
    for step in range(1, rounds + 1):
        try:
            proposed = proposer.propose(current, cur_score, failures(cur_res), step)
        except (ModelError, ValueError) as exc:
            history.append({"round": step, "error": str(exc)})
            continue
        best = None
        for cand in (proposed, compose(current, proposed)):
            if cand.digest() in seen:
                continue
            seen.add(cand.digest())
            res = run_batch(tune, agent_model, box, cand, budget, progress=progress)
            s = score(res)
            history.append(
                {
                    "round": step,
                    "playbook": cand.digest(),
                    "candidate": cand.to_dict(),
                    "score": s,
                    "adopted": False,
                }
            )
            if (
                s["objective"] is not None
                and s["objective"] > cur_score["objective"] + 1e-9
                and (best is None or s["objective"] > best[1]["objective"])
            ):
                best = (cand, s, res, len(history) - 1)
        if best:
            current, cur_score, cur_res = best[0], best[1], best[2]
            history[best[3]]["adopted"] = True
        if verify_guard() != guard:
            raise RuntimeError("guarded code changed during optimization")
    lib.save(current, guard, controls_hash, cur_score, history)
    if out_dir:
        atomic_json(
            Path(out_dir) / "optimize.json",
            {
                "final_playbook": current.to_dict(),
                "tune_score": cur_score,
                "history": history,
                "budget": asdict(budget),
            },
        )
    return current, cur_score, history


def final_test(agent_model, box, controls, controls_hash, playbook, budget, ledger_path, out_dir=None):
    """One frozen evaluation on the test split per control set. Never feed it back into tuning."""
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if controls_hash in ledger:
        raise ValueError(
            "test split already evaluated for this control set; build a new holdout instead of retuning"
        )
    test = [c for c in controls["controls"] if c["split"] == "test"]
    res = run_batch(test, agent_model, box, playbook, budget, out_dir=out_dir)
    s = score(res)
    ledger[controls_hash] = {
        "playbook": playbook.to_dict(),
        "playbook_digest": playbook.digest(),
        "score": s,
        "model": getattr(agent_model, "name", "?"),
        "guard_hash": verify_guard(),
    }
    atomic_json(ledger_path, ledger)
    return s


def config_hash(**kw):
    return canonical_hash(kw)[:12]
