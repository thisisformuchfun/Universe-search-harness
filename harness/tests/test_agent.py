"""Agent loop tests. Offline: archive responses come from a fake backend or
replay fixtures, and model adapters talk to stub HTTP servers on loopback."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from harness2.agent import evaluate as ev
from harness2.agent.loop import investigate
from harness2.agent.models import (
    AnthropicMessages,
    HeuristicAgent,
    ModelError,
    OpenAICompatible,
    ScriptedModel,
    check_endpoint,
)
from harness2.agent.schema import AssistantTurn, Budget, Playbook, ToolCall, Usage
from harness2.agent.tools import RecordingBackend, ReplayBackend, ToolBox, ToolError, load_policy
from harness2.agent.verify import verify

PUB, BLEND, CLEAN, ALT = "1000000000000000001", "1000000000000000002", "1000000000000000003", "1000000000000000004"
TEST_FIXTURE_NOTE = "synthetic test data, not observations"


def _record(sid, kind="Orbital"):
    return {
        "record_id": f"{sid}:{kind}",
        "source_id": sid,
        "nss_solution_type": kind,
        "a0_mas": 1.2,
        "f_phot_solar": 4.0,
        "parallax_relative_error": 0.02,
        "period_relative_error": 0.01,
        "efficiency": 0.4,
        "uncertainty": {"status": "UNAVAILABLE"},
        "status": "HOLD_QUALITY_AND_NOVELTY",
        "novelty_status": "UNKNOWN_NOT_CLEARED",
        "reasons": ["x"],
        "evidence": [],
        "partition": "train",
    }


def _raw(sid, kind="Orbital", sig="45.0", gof="1.1"):
    return {
        "source_id": sid,
        "nss_solution_type": kind,
        "period": "300.0",
        "eccentricity": "0.2",
        "significance": sig,
        "goodness_of_fit": gof,
        "parallax": "2.0",
    }


class FakeBackend:
    def __init__(self):
        self.calls = 0

    def fetch(self, tool, args):
        self.calls += 1
        sid = args["source_id"]
        if tool == "gaia_quality":
            mp = 9 if sid == BLEND else 0
            return {
                "found": True,
                "source_id": sid,
                "ruwe": 3.1,
                "ipd_frac_multi_peak": mp,
                "ipd_gof_harmonic_amplitude": 0.02,
                "duplicated_source": False,
            }, {"note": TEST_FIXTURE_NOTE}
        if tool == "simbad_lookup":
            hit = ["2023MNRAS.518.2991S"] if sid == PUB else []
            return {
                "found": True,
                "main_id": f"Gaia DR3 {sid}",
                "otype": "*",
                "bibcodes": hit + ["2022yCat.1355....0G"],
                "compact_companion_bibcodes": hit,
                "matched": bool(hit),
            }, {"note": TEST_FIXTURE_NOTE}
        if tool == "vizier_crossmatch":
            return {"catalog": args["catalog"], "matched": False, "rows_checked": 100}, {"note": TEST_FIXTURE_NOTE}
        raise ToolError("unavailable")


def make_box(backend=None, known=None):
    records = [_record(PUB), _record(BLEND), _record(CLEAN), _record(ALT, "OrbitalAlternative")]
    raws = [_raw(PUB), _raw(BLEND), _raw(CLEAN), _raw(ALT, "OrbitalAlternative")]
    return ToolBox(records, raws, backend or FakeBackend(), policy=load_policy(), known=known or {})


def submit(verdict, claims, conf="medium"):
    args = {
        "verdict": verdict,
        "confidence": conf,
        "summary": "s",
        "next_test": "t",
        "claims": [
            {"statement": s, "evidence": [{"call_id": c, "field": f, "value": v}]} for s, c, f, v in claims
        ],
    }
    return AssistantTurn("", [ToolCall("v", "submit_verdict", args)], Usage(100, 20, 1))


def call(name, sid, **kw):
    return AssistantTurn("", [ToolCall("x", name, {"source_id": sid, **kw})], Usage(100, 20, 1))


class ToolValidation(unittest.TestCase):
    def setUp(self):
        self.s = make_box().session(CLEAN, hidden=("known_catalogs",), blocked_catalogs=("shahaf2023",))

    def test_rejects_other_source(self):
        self.assertFalse(self.s.call("gaia_quality", {"source_id": PUB})["ok"])

    def test_rejects_unknown_and_hidden_tools(self):
        self.assertFalse(self.s.call("shell", {"source_id": CLEAN})["ok"])
        self.assertFalse(self.s.call("known_catalogs", {"source_id": CLEAN})["ok"])

    def test_catalog_allowlist_and_blinding(self):
        self.assertFalse(self.s.call("vizier_crossmatch", {"source_id": CLEAN, "catalog": "J/evil"})["ok"])
        self.assertFalse(self.s.call("vizier_crossmatch", {"source_id": CLEAN, "catalog": "shahaf2023"})["ok"])
        self.assertTrue(self.s.call("vizier_crossmatch", {"source_id": CLEAN, "catalog": "jayasinghe2023"})["ok"])

    def test_rejects_extra_arguments(self):
        self.assertFalse(self.s.call("gaia_quality", {"source_id": CLEAN, "query": "SELECT 1"})["ok"])

    def test_nss_orbit_hides_pipeline_labels(self):
        entry = self.s.call("nss_orbit", {"source_id": CLEAN})
        sol = entry["data"]["solutions"][0]
        for leaked in ("status", "novelty_status", "reasons", "evidence", "partition"):
            self.assertNotIn(leaked, sol)
        self.assertEqual(sol["significance"], 45.0)

    def test_call_ids_and_cache(self):
        backend = FakeBackend()
        box = make_box(backend)
        a = box.session(CLEAN).call("gaia_quality", {"source_id": CLEAN})
        b = box.session(CLEAN).call("gaia_quality", {"source_id": CLEAN})
        self.assertEqual((a["call_id"], b["call_id"]), ("c1", "c1"))
        self.assertEqual(backend.calls, 1)
        self.assertEqual(box.stats["cache_hits"], 1)


class Verifier(unittest.TestCase):
    def setUp(self):
        self.s = make_box().session(PUB)
        self.s.call("simbad_lookup", {"source_id": PUB})
        self.s.call("gaia_quality", {"source_id": PUB})
        self.s.call("ads_search", {"source_id": PUB})  # unavailable -> failed call

    def v(self, verdict, claims):
        return verify(submit(verdict, claims).tool_calls[0].arguments, self.s.log, PUB)

    def test_valid_published(self):
        r = self.v(
            "PUBLISHED_PRIOR", [("hit", "c1", "matched", True), ("bib", "c1", "bibcodes", "2023MNRAS.518.2991S")]
        )
        self.assertTrue(r["valid"], r["errors"])

    def test_fabricated_value_rejected(self):
        r = self.v("LIKELY_BLEND_OR_LUMINOUS", [("ruwe", "c2", "ruwe", 9.9)])
        self.assertFalse(r["valid"])
        self.assertEqual(r["evidence_failed"], 1)

    def test_uncalled_id_rejected(self):
        self.assertFalse(self.v("LIKELY_BLEND_OR_LUMINOUS", [("x", "c9", "ruwe", 3.1)])["valid"])

    def test_published_needs_match(self):
        self.assertFalse(self.v("PUBLISHED_PRIOR", [("ruwe", "c2", "ruwe", 3.1)])["valid"])

    def test_followup_cannot_ignore_match(self):
        self.assertFalse(self.v("NEEDS_FOLLOWUP", [("ruwe", "c2", "ruwe", 3.1)])["valid"])

    def test_failed_call_only_supports_failure(self):
        self.assertTrue(self.v("INSUFFICIENT_DATA", [("ads failed", "c3", "ok", False)])["valid"])
        self.assertFalse(self.v("INSUFFICIENT_DATA", [("ads", "c3", "matched", True)])["valid"])

    def test_no_discovery_verdict(self):
        self.assertFalse(self.v("NEW_BLACK_HOLE", [("x", "c2", "ruwe", 3.1)])["valid"])


class Loop(unittest.TestCase):
    def test_scripted_valid_and_hallucinated(self):
        box = make_box()
        good = ScriptedModel(
            [
                call("gaia_quality", BLEND),
                submit("LIKELY_BLEND_OR_LUMINOUS", [("mp", "c1", "ipd_frac_multi_peak", 9)]),
            ]
        )
        r = investigate(BLEND, good, box.session(BLEND), Playbook())
        self.assertEqual(r["accepted_verdict"], "LIKELY_BLEND_OR_LUMINOUS")
        self.assertEqual(r["usage"]["model_calls"], 2)
        bad = ScriptedModel([submit("PUBLISHED_PRIOR", [("made up", "c1", "matched", True)])])
        r = investigate(CLEAN, bad, box.session(CLEAN), Playbook())
        self.assertEqual(r["accepted_verdict"], "UNVERIFIED")

    def test_tool_limit_enforced(self):
        box = make_box()
        turns = [call("gaia_quality", CLEAN)] * 5 + [submit("NEEDS_FOLLOWUP", [("r", "c1", "ruwe", 3.1)])]
        r = investigate(CLEAN, ScriptedModel(turns), box.session(CLEAN), Playbook(max_tool_calls=2))
        self.assertEqual(len(r["tool_calls"]), 2)

    def test_token_budget(self):
        heavy = AssistantTurn("", [ToolCall("x", "gaia_quality", {"source_id": CLEAN})], Usage(900, 200, 1))
        r = investigate(
            CLEAN, ScriptedModel([heavy] * 5), make_box().session(CLEAN), Playbook(), Budget(max_tokens=2000)
        )
        self.assertEqual(r["stop_reason"], "token_budget")
        self.assertEqual(r["accepted_verdict"], "UNVERIFIED")

    def test_heuristic_baseline(self):
        box = make_box()
        got = {
            sid: investigate(sid, HeuristicAgent(), box.session(sid, hidden=("known_catalogs",)), Playbook())
            for sid in (PUB, BLEND, CLEAN, ALT)
        }
        self.assertEqual(got[PUB]["accepted_verdict"], "PUBLISHED_PRIOR")
        self.assertEqual(got[BLEND]["accepted_verdict"], "LIKELY_BLEND_OR_LUMINOUS")
        self.assertEqual(got[ALT]["accepted_verdict"], "LIKELY_SPURIOUS_ORBIT")
        self.assertEqual(got[CLEAN]["accepted_verdict"], "NEEDS_FOLLOWUP")
        for r in got.values():
            self.assertTrue(r["verification"]["valid"], r["verification"]["errors"])


class Backends(unittest.TestCase):
    def test_record_then_replay(self):
        with tempfile.TemporaryDirectory() as d:
            rec = RecordingBackend(FakeBackend(), d)
            live = make_box(rec).session(CLEAN).call("gaia_quality", {"source_id": CLEAN})
            replayed = make_box(ReplayBackend(d)).session(CLEAN).call("gaia_quality", {"source_id": CLEAN})
            self.assertEqual(live["data"], replayed["data"])
            missing = make_box(ReplayBackend(d)).session(CLEAN).call("simbad_lookup", {"source_id": CLEAN})
            self.assertFalse(missing["ok"])
            self.assertIn("no recorded fixture", missing["error"])


class Endpoints(unittest.TestCase):
    def test_remote_needs_opt_in_and_https(self):
        self.assertTrue(check_endpoint("http://127.0.0.1:8080/v1", False))
        with self.assertRaises(ModelError):
            check_endpoint("https://openrouter.ai/api/v1", False)
        with self.assertRaises(ModelError):
            check_endpoint("http://example.com/v1", True)
        self.assertFalse(check_endpoint("https://openrouter.ai/api/v1", True))
        with self.assertRaises(ModelError):
            check_endpoint("https://u:p@openrouter.ai/api/v1", True)


class _Stub(BaseHTTPRequestHandler):
    reply = {}
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.seen.append((self.path, body))
        raw = json.dumps(_Stub.reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class Adapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Stub)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Stub.seen.clear()
        self.msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "source_id 1"},
            {"role": "assistant", "content": "", "tool_calls": [ToolCall("a", "nss_orbit", {"source_id": "1"})]},
            {"role": "tool", "tool_call_id": "a", "name": "nss_orbit", "content": "{}"},
        ]
        self.tools = [
            {"name": "nss_orbit", "description": "d", "parameters": {"type": "object", "properties": {}}}
        ]

    def test_openai_compatible(self):
        _Stub.reply = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "t1",
                                "type": "function",
                                "function": {"name": "gaia_quality", "arguments": '{"source_id":"7"}'},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 9},
        }
        turn = OpenAICompatible("m", self.url + "/v1", api_key_env=None).complete(self.msgs, self.tools)
        self.assertEqual(turn.tool_calls[0].arguments, {"source_id": "7"})
        self.assertEqual(turn.usage.total, 59)
        path, body = _Stub.seen[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(body["messages"][2]["tool_calls"][0]["function"]["name"], "nss_orbit")
        self.assertEqual(body["messages"][3]["role"], "tool")

    def test_anthropic_messages(self):
        _Stub.reply = {
            "content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "id": "u1", "name": "simbad_lookup", "input": {"source_id": "7"}},
            ],
            "usage": {"input_tokens": 40, "output_tokens": 5},
        }
        turn = AnthropicMessages("m", self.url, api_key_env="UNSET_TEST_KEY").complete(self.msgs, self.tools)
        self.assertEqual(turn.tool_calls[0].name, "simbad_lookup")
        path, body = _Stub.seen[0]
        self.assertEqual(path, "/v1/messages")
        self.assertEqual(body["system"], "sys")
        self.assertEqual(body["messages"][2]["content"][0]["type"], "tool_result")
        self.assertEqual(body["tools"][0]["input_schema"]["type"], "object")

    def test_bad_arguments_become_rejected_call(self):
        _Stub.reply = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "t", "function": {"name": "gaia_quality", "arguments": "not json"}}]
                    }
                }
            ]
        }
        turn = OpenAICompatible("m", self.url + "/v1", api_key_env=None).complete(self.msgs, self.tools)
        entry = make_box().session(CLEAN).call(turn.tool_calls[0].name, turn.tool_calls[0].arguments)
        self.assertFalse(entry["ok"])


class OuterLoop(unittest.TestCase):
    def controls(self):
        items = [
            {"source_id": s, "label": "PUBLISHED_PRIOR", "label_sources": ["shahaf2023"], "split": "tune"}
            for s in (PUB, CLEAN)
        ]
        items.append({"source_id": PUB, "label": "PUBLISHED_PRIOR", "label_sources": [], "split": "test"})
        return {"controls": items}

    def test_score_and_optimize(self):
        box = make_box()
        with tempfile.TemporaryDirectory() as d:
            mem = Path(d) / "mem.json"
            pb, s, hist = ev.optimize(
                HeuristicAgent(), ev.RuleProposer(), box, self.controls(), "h1", 2, Budget(), mem
            )
            self.assertEqual(s["recall"], 0.5)  # PUB found via SIMBAD bibcode; CLEAN is honestly not found
            self.assertTrue(hist[0]["adopted"])
            for h in hist[1:]:
                if h.get("adopted"):
                    self.assertGreater(h["score"]["objective"], hist[0]["score"]["objective"])
            self.assertTrue(mem.exists())
            with self.assertRaises(ValueError):
                ev.PlaybookLibrary(mem).load(json.loads(mem.read_text())["guard_hash"], "other-controls")

    def test_always_published_scores_zero(self):
        box = make_box()
        liar = lambda m, t: submit("PUBLISHED_PRIOR", [("trust me", "c1", "matched", True)])  # noqa: E731
        res = ev.run_batch(
            [{"source_id": CLEAN, "label": "PUBLISHED_PRIOR"}], ScriptedModel([liar]), box, Playbook(), Budget()
        )
        self.assertEqual(ev.score(res)["recall"], 0.0)

    def test_test_split_is_one_shot(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.json"
            ev.final_test(HeuristicAgent(), make_box(), self.controls(), "h1", Playbook(), Budget(), ledger)
            with self.assertRaises(ValueError):
                ev.final_test(HeuristicAgent(), make_box(), self.controls(), "h1", Playbook(), Budget(), ledger)


class BundledControls(unittest.TestCase):
    def test_controls_match_snapshot(self):
        data, _ = ev.load_controls()
        ids = [c["source_id"] for c in data["controls"]]
        self.assertEqual(len(ids), 42)
        self.assertEqual(len(set(ids)), 42)
        self.assertIn("4373465352415301632", ids)  # Gaia BH1
        self.assertTrue(set(ev.LI2026_CONTROLS) <= set(ids))
        self.assertTrue(all(c["split"] == ev.split_of(c["source_id"]) for c in data["controls"]))


if __name__ == "__main__":
    unittest.main()
