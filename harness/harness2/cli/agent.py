"""harness2-agent: tool-using follow-up agent, control evaluation and playbook optimization.

Examples (run from harness/ after `harness2-universe run --output runs/base ...`):
  harness2-agent investigate --run runs/base --held --provider heuristic --tools replay --fixtures fixtures/live
  harness2-agent eval --run runs/base --split tune --provider openai --model qwen3 --tools record --fixtures fixtures/live
  harness2-agent optimize --run runs/base --rounds 4 --provider openrouter --model YOUR_OPENROUTER_MODEL_ID \\
      --allow-remote-model --proposer llm --tools replay --fixtures fixtures/live
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness2.agent import evaluate as ev
from harness2.agent.models import ModelError, build_model
from harness2.agent.schema import Budget, Playbook
from harness2.agent.tools import (
    LiveBackend,
    RecordingBackend,
    ReplayBackend,
    ToolBox,
    default_ads_token,
    load_policy,
)
from harness2.core.guards import ROOT, verify_guard
from harness2.core.library import atomic_json
from harness2.universe.novelty import CATALOGS, bundled_catalogs


def _catalog_members(policy):
    by_table = {spec["table"]: key for key, spec in policy["vizier_catalogs"].items()}
    members = {}
    for filename, column, _count, table in CATALOGS:
        lines = [
            x
            for x in (ROOT / "data/pilot" / filename).read_text().splitlines()
            if x.strip() and not x.startswith("#")
        ]
        idx = lines[0].split("\t").index(column)
        members[by_table.get(table, table)] = {ln.split("\t")[idx].strip() for ln in lines[3:]}
    return members


def _toolbox(args):
    policy = load_policy()
    known, _ = bundled_catalogs()
    token = default_ads_token() if args.ads else None
    if args.tools == "replay":
        backend = ReplayBackend(args.fixtures)
    else:
        from harness2.universe.connectors.public_archives import PublicSkyConnector

        live = LiveBackend(
            PublicSkyConnector(args.cache, timeout=args.timeout, retries=1), policy, ads_token=token
        )
        backend = RecordingBackend(live, args.fixtures) if args.tools == "record" else live
    ads = bool(token) or (args.tools == "replay" and args.ads)
    return ToolBox.from_run(args.run, backend, policy=policy, known=known, ads_available=ads)


def _model(args, prefix=""):
    g = lambda k: getattr(args, prefix + k)  # noqa: E731
    return build_model(
        g("provider"),
        g("model") or "",
        g("base_url"),
        args.allow_remote_model,
        g("api_key_env"),
        args.max_output_tokens,
    )


def _budget(args):
    return Budget(args.max_steps, args.max_tool_calls, args.max_tokens)


def _playbook(args):
    if args.playbook:
        return Playbook.from_dict(json.loads(Path(args.playbook).read_text()).get("playbook", {}))
    return Playbook()


def _progress(i, n, res):
    print(
        f"[{i}/{n}] {res['source_id']} -> {res['accepted_verdict']} "
        f"({len(res['tool_calls'])} calls, {res['usage']['input_tokens'] + res['usage']['output_tokens']} tok)",
        file=sys.stderr,
    )


def cmd_build_controls(args):
    records = json.loads((Path(args.run) / "records.json").read_text())
    known, _ = bundled_catalogs()
    data = ev.build_controls(records, known, _catalog_members(load_policy()))
    atomic_json(args.output, data)
    n = len(data["controls"])
    tune = sum(c["split"] == "tune" for c in data["controls"])
    return {"controls": n, "tune": tune, "test": n - tune, "path": str(args.output)}


def cmd_investigate(args):
    box = _toolbox(args)
    records = json.loads((Path(args.run) / "records.json").read_text())
    ids = list(args.ids or [])
    if args.held:
        ids += [r["source_id"] for r in records if r["status"] == "HOLD_QUALITY_AND_NOVELTY"]
    if not ids:
        raise ValueError("give --ids or --held")
    items = [{"source_id": s} for s in dict.fromkeys(ids)]
    out = Path(args.out)
    res = ev.run_batch(
        items, _model(args), box, _playbook(args), _budget(args), out_dir=out, blind=False, progress=_progress
    )
    summary = ev.score(res)
    atomic_json(out / "summary.json", {"score": summary, "tool_stats": box.stats, "guard": verify_guard()})
    return summary


def cmd_eval(args):
    box = _toolbox(args)
    controls, chash = ev.load_controls(args.controls)
    pb = _playbook(args)
    if args.split == "test":
        if not args.final:
            raise ValueError("the test split is a one-shot holdout; pass --final to spend it")
        return ev.final_test(_model(args), box, controls, chash, pb, _budget(args), args.ledger, out_dir=args.out)
    items = [c for c in controls["controls"] if c["split"] == "tune"][: args.limit or None]
    res = ev.run_batch(
        items, _model(args), box, pb, _budget(args), out_dir=args.out, blind=not args.not_blind, progress=_progress
    )
    s = ev.score(res)
    s["failures"] = ev.failures(res)
    s["tool_stats"] = box.stats
    if args.out:
        atomic_json(Path(args.out) / "summary.json", s)
    return s


def cmd_optimize(args):
    box = _toolbox(args)
    controls, chash = ev.load_controls(args.controls)
    agent = _model(args)
    if args.proposer == "rule":
        proposer = ev.RuleProposer()
    else:
        proposer = ev.LLMProposer(_model(args, "proposer_") if args.proposer_provider else agent)
    pb, s, history = ev.optimize(
        agent,
        proposer,
        box,
        controls,
        chash,
        args.rounds,
        _budget(args),
        args.memory,
        out_dir=args.out,
        limit=args.limit,
        progress=_progress,
    )
    return {"playbook": pb.to_dict(), "tune_score": s, "rounds": len(history) - 1, "memory": args.memory}


def parser():
    p = argparse.ArgumentParser(
        prog="harness2-agent", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp, needs_run=True):
        if needs_run:
            sp.add_argument("--run", required=True, help="run directory from harness2-universe run")
        sp.add_argument(
            "--provider", default="heuristic", choices=["heuristic", "openai", "openrouter", "anthropic"]
        )
        sp.add_argument("--model", default="")
        sp.add_argument("--base-url", default=None)
        sp.add_argument("--api-key-env", default=None)
        sp.add_argument(
            "--allow-remote-model",
            action="store_true",
            help="permit a non-loopback model endpoint (public archive data and prompts are sent)",
        )
        sp.add_argument("--max-output-tokens", type=int, default=1500)
        sp.add_argument("--tools", default="replay", choices=["replay", "live", "record"])
        sp.add_argument("--fixtures", default="fixtures/live")
        sp.add_argument("--cache", default="data/cache")
        sp.add_argument("--timeout", type=int, default=30)
        sp.add_argument("--ads", action="store_true", help="enable ads_search (live needs ADS_API_TOKEN)")
        sp.add_argument("--max-steps", type=int, default=12)
        sp.add_argument("--max-tool-calls", type=int, default=10)
        sp.add_argument("--max-tokens", type=int, default=40000)
        sp.add_argument("--playbook", default=None, help="playbook memory JSON to use")
        sp.add_argument("--controls", default=str(ev.CONTROLS_PATH))

    b = sub.add_parser("build-controls", help="derive labeled controls from a snapshot run")
    b.add_argument("--run", required=True)
    b.add_argument("--output", default=str(ev.CONTROLS_PATH))

    i = sub.add_parser("investigate", help="run the agent on chosen sources")
    common(i)
    i.add_argument("--ids", nargs="*")
    i.add_argument("--held", action="store_true", help="all HOLD_QUALITY_AND_NOVELTY sources in the run")
    i.add_argument("--out", required=True)

    e = sub.add_parser("eval", help="score the agent on blind positive controls")
    common(e)
    e.add_argument("--split", choices=["tune", "test"], default="tune")
    e.add_argument("--final", action="store_true")
    e.add_argument("--ledger", default="runs/agent-test-ledger.json")
    e.add_argument("--limit", type=int, default=None)
    e.add_argument("--not-blind", action="store_true")
    e.add_argument("--out", default=None)

    o = sub.add_parser("optimize", help="Propose/Probe/Compose over the playbook on the tune split")
    common(o)
    o.add_argument("--rounds", type=int, default=3)
    o.add_argument("--proposer", choices=["rule", "llm"], default="rule")
    o.add_argument("--proposer-provider", default=None, choices=["openai", "openrouter", "anthropic"])
    o.add_argument("--proposer-model", default="")
    o.add_argument("--proposer-base-url", default=None)
    o.add_argument("--proposer-api-key-env", default=None)
    o.add_argument("--memory", default="runs/playbook-memory.json")
    o.add_argument("--limit", type=int, default=None)
    o.add_argument("--out", default=None)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    handlers = {
        "build-controls": cmd_build_controls,
        "investigate": cmd_investigate,
        "eval": cmd_eval,
        "optimize": cmd_optimize,
    }
    try:
        result = handlers[args.command](args)
    except (ValueError, RuntimeError, ModelError, OSError, KeyError) as exc:
        print("FAILED CLOSED: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
