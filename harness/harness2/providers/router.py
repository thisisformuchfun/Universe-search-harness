"""Optional local LLM proposals. No silent fallback; no model-generated execution."""

from dataclasses import dataclass
import json
import os
import urllib.request
import urllib.parse
from harness2.core.components import HarnessBundle


@dataclass
class LLMConfig:
    provider: str = "deterministic"
    model: str = ""
    base_url: str = "http://127.0.0.1:8080/v1"

    @classmethod
    def from_env(cls, provider_override=None, model_override=None):
        return cls(
            provider_override or "deterministic",
            model_override or os.getenv("LOCAL_AI_MODEL", ""),
            os.getenv("LOCAL_AI_BASE_URL", "http://127.0.0.1:8080/v1"),
        )


class UniversalModelRouter:
    def __init__(self, config=None):
        self.config = config or LLMConfig()
        self.call_count = 0
        if self.config.provider not in ("deterministic", "local"):
            raise ValueError("Only deterministic or explicit localhost model supported")
        u = urllib.parse.urlparse(self.config.base_url)
        if self.config.provider == "local" and (
            u.hostname not in ("localhost", "127.0.0.1", "::1")
            or u.scheme not in ("http", "https")
            or u.username
            or u.password
            or u.query
            or u.fragment
        ):
            raise ValueError("Local proposer URL must be loopback; remote transmission disabled")

    def propose(self, base, training_summary, step):
        self.call_count += 1
        if self.config.provider == "deterministic":
            variants = [(0.8, 2.0, 1.5), (1.0, 3.0, 2.0), (0.5, 4.0, 2.5), (1.5, 2.0, 3.0)]
            w = variants[step % len(variants)]
            # Sequential engine passes its adopted parent; parallel always passes initial parent.
            return HarnessBundle.from_dict({k: (v + w[i]) / 2 for i, (k, v) in enumerate(base.to_dict().items())})
        if not self.config.model:
            raise ValueError("Set LOCAL_AI_MODEL to an actually served model identifier")
        body = {
            "model": self.config.model,
            "temperature": 0,
            "max_tokens": 256,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON with mass_function_weight, precision_weight, efficiency_weight, each finite 0..4. Optimize review-priority stability, not discoveries. You may not change science gates, source data, policy, or execute code.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"current": base.to_dict(), "training_summary": training_summary, "step": step}
                    ),
                },
            ],
        }
        req = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # Do not follow a localhost server redirect to a remote host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **kw):
                raise RuntimeError("Model endpoint redirect forbidden")

        # A loopback URL must not inherit an environment proxy that forwards
        # local training aggregates to an external service.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        with opener.open(req, timeout=60) as resp:
            raw = resp.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Model response too large")
        text = json.loads(raw)["choices"][0]["message"]["content"]
        return HarnessBundle.from_dict(json.loads(text))
