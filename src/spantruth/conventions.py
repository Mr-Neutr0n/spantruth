"""Where each fact lives, under every naming convention the suite knows.

A check reads a fact under any of these names, in this order, so a library is never marked
wrong for its choice of names. The first name of each fact is the current OpenTelemetry GenAI
name at the pinned semantic-conventions-genai commit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# open-telemetry/semantic-conventions-genai main, 2026-10-09. The repo has no releases yet.
SEMCONV_GENAI_COMMIT = "6fd0d763"


@dataclass(frozen=True)
class Fact:
    current: str
    others: tuple[str, ...] = ()
    # (attribute, key) pairs for conventions that store the fact inside a JSON string.
    json: tuple[tuple[str, str], ...] = ()
    # False when the OpenInference conventions define no attribute for this fact.
    in_openinference: bool = True

    @property
    def names(self) -> tuple[str, ...]:
        return (self.current, *self.others)


FACTS: dict[str, Fact] = {
    "provider": Fact("gen_ai.provider.name", ("gen_ai.system", "llm.provider", "llm.system")),
    "request_model": Fact(
        "gen_ai.request.model",
        ("llm.request.model_name",),
        json=(("llm.invocation_parameters", "model"),),
    ),
    "response_model": Fact("gen_ai.response.model", ("llm.response.model_name", "llm.model_name")),
    "response_id": Fact("gen_ai.response.id", in_openinference=False),
    "finish_reasons": Fact("gen_ai.response.finish_reasons", ("llm.finish_reason",)),
    "input_tokens": Fact(
        "gen_ai.usage.input_tokens",
        ("gen_ai.usage.prompt_tokens", "llm.usage.prompt_tokens", "llm.token_count.prompt"),
    ),
    "output_tokens": Fact(
        "gen_ai.usage.output_tokens",
        (
            "gen_ai.usage.completion_tokens",
            "llm.usage.completion_tokens",
            "llm.token_count.completion",
        ),
    ),
    "cache_read_tokens": Fact(
        "gen_ai.usage.cache_read.input_tokens",
        ("gen_ai.usage.cache_read_input_tokens", "llm.token_count.prompt_details.cache_read"),
    ),
    "cache_write_tokens": Fact(
        "gen_ai.usage.cache_write.input_tokens",
        (
            "gen_ai.usage.cache_creation.input_tokens",
            "gen_ai.usage.cache_creation_input_tokens",
            "llm.token_count.prompt_details.cache_write",
        ),
    ),
    "reasoning_tokens": Fact(
        "gen_ai.usage.reasoning.output_tokens",
        ("gen_ai.usage.reasoning_tokens", "llm.token_count.completion_details.reasoning"),
    ),
}

# Facts that identify a span as an LLM call. The driver's own span carries none of them.
LLM_MARKERS = (
    frozenset(name for fact in FACTS.values() for name in fact.names)
    | {"gen_ai.operation.name"}
    | {a for fact in FACTS.values() for a, _ in fact.json}
)

# Provider finish reasons and the normalized values some libraries record instead.
FINISH_ALIASES = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "tool_use": "tool_call",
    "tool_calls": "tool_call",
    "max_tokens": "length",
}


def openinference_only(attributes: dict[str, Any]) -> bool:
    keys = attributes.keys()
    return any(k.startswith("llm.") for k in keys) and not any(
        k.startswith("gen_ai.") for k in keys
    )


def defined_for(attributes: dict[str, Any], fact: str) -> bool:
    """False when the span follows only OpenInference names and they have no name for `fact`."""
    return FACTS[fact].in_openinference or not openinference_only(attributes)


def lookup(attributes: dict[str, Any], fact: str) -> tuple[str, Any] | None:
    """Return (attribute name, value) for the first name of `fact` present, or None."""
    spec = FACTS[fact]
    for name in spec.names:
        if name in attributes and attributes[name] not in (None, ""):
            return name, attributes[name]
    for name, key in spec.json:
        raw = attributes.get(name)
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except ValueError:
                continue
            if isinstance(parsed, dict) and parsed.get(key) is not None:
                return f"{name}[{key}]", parsed[key]
    return None


def same_finish(expected: tuple[str, ...], got: Any) -> bool:
    if isinstance(got, str):
        got = [got]
    if not isinstance(got, (list, tuple)):
        return False

    def norm(values) -> list[str]:
        return sorted(FINISH_ALIASES.get(v, v) for v in values)

    return norm(expected) == norm(got)
