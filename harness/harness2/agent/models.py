"""Model adapters with one interface: complete(messages, tools) -> AssistantTurn.

  openai     - any OpenAI-compatible /chat/completions server with tool calling:
               OpenRouter, OpenAI, vLLM, llama.cpp server, Ollama, LM Studio
  anthropic  - Anthropic Messages API (native tool use)
  heuristic  - deterministic rule-based baseline; no model, no tokens
  scripted   - fixed turns, for tests and replay

Remote endpoints are refused unless allow_remote=True. What a remote model sees
is public archive data plus the prompt; no local files are sent. Model output
is parsed as data only. Tool calls go through the validating ToolBox; nothing
the model writes is executed.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

from harness2.agent.schema import AssistantTurn, ToolCall, Usage

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
MAX_RESPONSE = 4 * 1024 * 1024


class ModelError(RuntimeError):
    pass


def check_endpoint(url: str, allow_remote: bool) -> bool:
    """Return True if loopback. Raise if the URL is not acceptable."""
    u = urllib.parse.urlparse(url)
    if u.username or u.password or u.query or u.fragment:
        raise ModelError("model URL must not carry credentials, query or fragment")
    if u.hostname in LOOPBACK and u.scheme in ("http", "https"):
        return True
    if not allow_remote:
        raise ModelError("remote model endpoint refused; pass --allow-remote-model to opt in")
    if u.scheme != "https":
        raise ModelError("remote model endpoints must use https")
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        raise ModelError("model endpoint redirect refused")


def _post_json(url, body, headers, loopback, timeout=180):
    handlers = [_NoRedirect]
    if loopback:
        handlers.append(urllib.request.ProxyHandler({}))  # never route loopback via a proxy
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", "replace")
        raise ModelError(f"HTTP {exc.code} from model endpoint: {detail}") from None
    except OSError as exc:
        raise ModelError(f"model endpoint unreachable: {type(exc).__name__}: {exc}") from None
    if len(raw) > MAX_RESPONSE:
        raise ModelError("model response too large")
    return json.loads(raw)


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        obj = json.loads(raw or "{}")
        return obj if isinstance(obj, dict) else {"__invalid__": str(raw)[:200]}
    except json.JSONDecodeError:
        return {"__invalid__": str(raw)[:200]}


class OpenAICompatible:
    name = "openai"

    def __init__(
        self,
        model,
        base_url="http://127.0.0.1:8080/v1",
        api_key_env="OPENAI_API_KEY",
        allow_remote=False,
        max_output_tokens=1500,
        temperature=0.0,
    ):
        if not model:
            raise ModelError("model name required")
        self.model, self.base_url = model, base_url.rstrip("/")
        self.loopback = check_endpoint(self.base_url, allow_remote)
        self.api_key = os.getenv(api_key_env) if api_key_env else None
        self.max_output_tokens, self.temperature = max_output_tokens, temperature

    def complete(self, messages, tools):
        body = {
            "model": self.model,
            "messages": [self._msg(m) for m in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = _post_json(self.base_url + "/chat/completions", body, headers, self.loopback)
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise ModelError(f"unexpected response shape: {str(resp)[:300]}") from None
        calls = [
            ToolCall(c.get("id") or f"t{i}", c["function"]["name"], _parse_args(c["function"].get("arguments")))
            for i, c in enumerate(msg.get("tool_calls") or [])
        ]
        u = resp.get("usage") or {}
        usage = Usage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0), 1)
        return AssistantTurn(msg.get("content") or "", calls, usage)

    @staticmethod
    def _msg(m):
        if m["role"] == "assistant":
            out = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                out["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m["tool_calls"]
                ]
            return out
        if m["role"] == "tool":
            return {"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]}
        return {"role": m["role"], "content": m["content"]}


class AnthropicMessages:
    name = "anthropic"

    def __init__(
        self,
        model,
        base_url="https://api.anthropic.com",
        api_key_env="ANTHROPIC_API_KEY",
        allow_remote=False,
        max_output_tokens=1500,
        temperature=0.0,
    ):
        if not model:
            raise ModelError("model name required")
        self.model, self.base_url = model, base_url.rstrip("/")
        self.loopback = check_endpoint(self.base_url, allow_remote)
        self.api_key = os.getenv(api_key_env)
        if not self.api_key and not self.loopback:
            raise ModelError(f"set {api_key_env}")
        self.max_output_tokens, self.temperature = max_output_tokens, temperature

    def complete(self, messages, tools):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        converted = []
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                    converted[-1]["content"].append(block)
                else:
                    converted.append({"role": "user", "content": [block]})
            elif m["role"] == "assistant":
                blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
                blocks += [
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in m.get("tool_calls") or []
                ]
                converted.append({"role": "assistant", "content": blocks or [{"type": "text", "text": "."}]})
            else:
                converted.append({"role": "user", "content": m["content"]})
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": converted,
        }
        if tools:
            body["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                for t in tools
            ]
        headers = {"x-api-key": self.api_key or "", "anthropic-version": "2023-06-01"}
        resp = _post_json(self.base_url + "/v1/messages", body, headers, self.loopback)
        text, calls = [], []
        for block in resp.get("content", []):
            if block.get("type") == "text":
                text.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(block["id"], block["name"], _parse_args(block.get("input"))))
        u = resp.get("usage") or {}
        usage = Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0), 1)
        return AssistantTurn("".join(text), calls, usage)


class ScriptedModel:
    """Returns pre-written turns. Each item is an AssistantTurn or f(messages, tools) -> AssistantTurn."""

    name = "scripted"

    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, messages, tools):
        if not self.turns:
            return AssistantTurn("script exhausted")
        t = self.turns.pop(0)
        return t(messages, tools) if callable(t) else t


# ------------------------------------------------------------ heuristic


BLEND_LIMITS = {"ipd_frac_multi_peak": 2, "ipd_gof_harmonic_amplitude": 0.1}
SPURIOUS_LIMITS = {"significance_min": 20.0, "goodness_of_fit_max": 5.0}


class HeuristicAgent:
    """Deterministic baseline that uses the same tools and verifier as an LLM.

    Any model worth its tokens should beat this on the control set. Thresholds
    are triage heuristics, not validated physical cuts.
    """

    name = "heuristic"

    def complete(self, messages, tools):
        sid = re.search(r"source_id (\d+)", messages[1]["content"]).group(1)
        names = [t["name"] for t in tools]
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        catalogs = []
        for t in tools:
            if t["name"] == "vizier_crossmatch":
                catalogs = t["parameters"]["properties"]["catalog"]["enum"]
        plan = []
        for name in ("known_catalogs", "simbad_lookup"):
            if name in names:
                plan.append((name, {"source_id": sid}))
        plan += [("vizier_crossmatch", {"source_id": sid, "catalog": c}) for c in catalogs]
        for name in ("ads_search", "gaia_quality", "nss_orbit"):
            if name in names:
                plan.append((name, {"source_id": sid}))

        for r in results:
            if r["ok"] and isinstance(r.get("data"), dict) and r["data"].get("matched") is True:
                return self._submit(
                    "PUBLISHED_PRIOR",
                    "high",
                    "Found in a published compact-companion source.",
                    [("Literature match", r["call_id"], "matched", True)],
                )
        step = len(results)
        if step < len(plan) and step < 12:
            name, args = plan[step]
            return AssistantTurn("", [ToolCall(f"h{step}", name, args)])
        return self._decide(results)

    def _decide(self, results):
        by_tool = {r["tool"]: r for r in results}
        q, o = by_tool.get("gaia_quality"), by_tool.get("nss_orbit")
        lit = [
            r
            for r in results
            if r["tool"] in ("simbad_lookup", "vizier_crossmatch", "ads_search", "known_catalogs") and r["ok"]
        ]
        if not (q and q["ok"]) or not lit:
            failed = [r for r in results if not r["ok"]]
            if failed:
                return self._submit(
                    "INSUFFICIENT_DATA",
                    "low",
                    "Required tools failed.",
                    [("A required call failed", failed[0]["call_id"], "ok", False)],
                    allow_fail=True,
                )
        if q and q["ok"]:
            d = q["data"]
            for key, limit in BLEND_LIMITS.items():
                if isinstance(d.get(key), (int, float)) and d[key] > limit:
                    return self._submit(
                        "LIKELY_BLEND_OR_LUMINOUS",
                        "medium",
                        f"{key} exceeds {limit}.",
                        [(f"{key} is high", q["call_id"], key, d[key])],
                    )
            if d.get("duplicated_source") is True:
                return self._submit(
                    "LIKELY_BLEND_OR_LUMINOUS",
                    "medium",
                    "Duplicated source flag set.",
                    [("duplicated_source", q["call_id"], "duplicated_source", True)],
                )
        if o and o["ok"] and o["data"].get("found"):
            s = o["data"]["solutions"][0]
            if "Alternative" in s.get("nss_solution_type", ""):
                return self._submit(
                    "LIKELY_SPURIOUS_ORBIT",
                    "low",
                    "Alternative orbital solution.",
                    [("Alternative solution", o["call_id"], "nss_solution_type", s["nss_solution_type"])],
                )
            sig, gof = s.get("significance"), s.get("goodness_of_fit")
            if isinstance(sig, float) and sig < SPURIOUS_LIMITS["significance_min"]:
                return self._submit(
                    "LIKELY_SPURIOUS_ORBIT",
                    "low",
                    "Low orbit significance.",
                    [("Low significance", o["call_id"], "significance", sig)],
                )
            if isinstance(gof, float) and gof > SPURIOUS_LIMITS["goodness_of_fit_max"]:
                return self._submit(
                    "LIKELY_SPURIOUS_ORBIT",
                    "low",
                    "Poor goodness of fit.",
                    [("Poor fit", o["call_id"], "goodness_of_fit", gof)],
                )
        claims = []
        if q and q["ok"] and "ruwe" in q["data"]:
            claims.append(("RUWE checked", q["call_id"], "ruwe", q["data"]["ruwe"]))
        if lit:
            claims.append(("No literature match", lit[0]["call_id"], "matched", False))
        return self._submit("NEEDS_FOLLOWUP", "low", "No disqualifier found in the checks run.", claims or [])

    @staticmethod
    def _submit(verdict, confidence, summary, claims, allow_fail=False):
        args = {
            "verdict": verdict,
            "confidence": confidence,
            "summary": summary,
            "claims": [
                {"statement": s, "evidence": [{"call_id": c, "field": f, "value": v}]} for s, c, f, v in claims
            ],
            "next_test": "Independent multi-epoch radial velocities." if verdict == "NEEDS_FOLLOWUP" else "None.",
        }
        return AssistantTurn("", [ToolCall("submit", "submit_verdict", args)])


def build_model(provider, model="", base_url=None, allow_remote=False, api_key_env=None, max_output_tokens=1500):
    if provider == "heuristic":
        return HeuristicAgent()
    if provider == "openai":
        return OpenAICompatible(
            model,
            base_url or os.getenv("LOCAL_AI_BASE_URL", "http://127.0.0.1:8080/v1"),
            api_key_env or "OPENAI_API_KEY",
            allow_remote,
            max_output_tokens,
        )
    if provider == "openrouter":
        return OpenAICompatible(
            model,
            base_url or "https://openrouter.ai/api/v1",
            api_key_env or "OPENROUTER_API_KEY",
            allow_remote,
            max_output_tokens,
        )
    if provider == "anthropic":
        return AnthropicMessages(
            model,
            base_url or "https://api.anthropic.com",
            api_key_env or "ANTHROPIC_API_KEY",
            allow_remote,
            max_output_tokens,
        )
    raise ModelError(f"unknown provider {provider!r}")
