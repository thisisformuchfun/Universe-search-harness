"""Data shapes shared by the agent loop: verdicts, playbooks and budgets.

A verdict is the only thing an agent can produce. There is deliberately no
verdict that means "new black hole": the agent triages, humans decide.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field

VERDICTS = {
    "PUBLISHED_PRIOR": "Source already appears in a compact-companion catalog or paper.",
    "LIKELY_SPURIOUS_ORBIT": "Orbit solution itself looks unreliable (low significance, poor fit, alternative solution).",
    "LIKELY_BLEND_OR_LUMINOUS": "Quality flags point to blended light, a luminous companion or a multiple system.",
    "NEEDS_FOLLOWUP": "No disqualifier found in the checks performed; worth radial-velocity or literature follow-up.",
    "INSUFFICIENT_DATA": "Required tools failed or returned nothing usable.",
}
CONFIDENCE = ("low", "medium", "high")
TOOL_NAMES = (
    "nss_orbit",
    "gaia_quality",
    "simbad_lookup",
    "vizier_crossmatch",
    "known_catalogs",
    "ads_search",
)
LITERATURE_TOOLS = frozenset({"simbad_lookup", "vizier_crossmatch", "known_catalogs", "ads_search"})


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Budget:
    """Hard per-candidate limits. Exceeding any of them ends the investigation."""

    max_steps: int = 12
    max_tool_calls: int = 10
    max_tokens: int = 40_000

    def __post_init__(self):
        if not 1 <= self.max_steps <= 64 or not 1 <= self.max_tool_calls <= 64:
            raise ValueError("budget steps/tool calls must be 1..64")
        if not 1_000 <= self.max_tokens <= 2_000_000:
            raise ValueError("budget tokens must be 1k..2M")


@dataclass(frozen=True)
class Playbook:
    """The editable part of the agent. This is what the outer loop optimizes.

    Everything that defines correctness (tools, verifier, verdict rules,
    controls) lives outside the playbook and cannot be changed by a proposal.
    """

    notes: str = (
        "Check prior literature first: simbad_lookup, then vizier_crossmatch on each catalog, "
        "then ads_search if available. If a compact-companion match exists, submit PUBLISHED_PRIOR "
        "immediately. Otherwise call gaia_quality and nss_orbit. RUWE well above 1.4 with high "
        "ipd_frac_multi_peak or ipd_gof_harmonic_amplitude suggests a blend. Alternative or "
        "low-significance solutions suggest a spurious orbit."
    )
    tool_priority: tuple = ("simbad_lookup", "vizier_crossmatch", "ads_search", "gaia_quality", "nss_orbit")
    max_tool_calls: int = 8
    stop_when_published: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "Playbook":
        allowed = set(cls.__dataclass_fields__)
        if not isinstance(data, dict) or not set(data) <= allowed:
            raise ValueError(f"playbook keys must be a subset of {sorted(allowed)}")
        merged = {**asdict(cls()), **data}
        notes = merged["notes"]
        if not isinstance(notes, str) or not 1 <= len(notes) <= 2000:
            raise ValueError("playbook notes must be 1..2000 characters")
        priority = tuple(merged["tool_priority"])
        if not priority or any(t not in TOOL_NAMES for t in priority) or len(set(priority)) != len(priority):
            raise ValueError("tool_priority must be distinct known tool names")
        calls = merged["max_tool_calls"]
        if isinstance(calls, bool) or not isinstance(calls, int) or not 2 <= calls <= 20:
            raise ValueError("max_tool_calls must be an integer 2..20")
        if not isinstance(merged["stop_when_published"], bool):
            raise ValueError("stop_when_published must be boolean")
        return cls(
            notes=notes,
            tool_priority=priority,
            max_tool_calls=calls,
            stop_when_published=merged["stop_when_published"],
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tool_priority"] = list(self.tool_priority)
        return d

    def digest(self) -> str:
        return canonical_hash(self.to_dict())[:16]


VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
        "summary": {"type": "string", "maxLength": 600},
        "claims": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string", "maxLength": 300},
                    "evidence": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "call_id": {"type": "string"},
                                "field": {"type": "string"},
                                "value": {},
                            },
                            "required": ["call_id", "field", "value"],
                        },
                    },
                },
                "required": ["statement", "evidence"],
            },
        },
        "next_test": {"type": "string", "maxLength": 300},
    },
    "required": ["verdict", "confidence", "summary", "claims", "next_test"],
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: "Usage"):
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.model_calls += other.model_calls


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class AssistantTurn:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


def finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
