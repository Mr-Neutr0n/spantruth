"""Grade one cell: what the app saw, and what the telemetry says, against the wire truth.

Pure functions over plain records, so every verdict is testable without a subprocess.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .conventions import LLM_MARKERS, defined_for, lookup, openinference_only, same_finish
from .model import Scenario, Truth
from .receiver import SpanRecord
from .rules import RULES

# Ordered by severity. The cell takes the most severe verdict of its checks.
SEVERITY = ("n/a", "pass", "missing", "wrong", "lost", "broken", "inconclusive")
TOKENS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)
VALUES = ("request_model", "response_model", "response_id", "finish_reasons", *TOKENS)


@dataclass(frozen=True)
class Check:
    id: str
    verdict: str
    expected: Any = None
    got: Any = None
    where: str | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        rule, url = RULES.get(self.id, ("", ""))
        return asdict(self) | {"rule": rule, "rule_url": url}


def cell_verdict(checks: list[Check]) -> str:
    return max((c.verdict for c in checks), key=SEVERITY.index, default="n/a")


def _app(base: dict, obs: dict) -> Check:
    if obs.get("hang"):
        return Check("app.unchanged", "broken", detail="the app hung until the watchdog fired")
    diffs = []
    if obs.get("exception") != base.get("exception"):
        diffs.append(f"exception {base.get('exception')} became {obs.get('exception')}")
    for key in ("text", "events", "response_id", "usage"):
        if obs["seen"].get(key) != base["seen"].get(key):
            diffs.append(f"{key} {base['seen'].get(key)!r} became {obs['seen'].get(key)!r}")
    return Check("app.unchanged", "broken" if diffs else "pass", detail="; ".join(diffs))


def _formula(fact: str, got: int, t: Truth) -> str:
    """Name the arithmetic a wrong token count most likely came from."""
    read, write = t.cache_read_tokens or 0, t.cache_write_tokens or 0
    if fact == "input_tokens" and t.input_tokens is not None:
        total = t.input_tokens
        guesses = {
            total - read - write: "cache reads and writes left out",
            total - write: "cache writes left out",
            total - read: "cache reads left out",
            total + read + write: "cache tokens counted twice",
            2 * total: "counted twice",
        }
        if got in guesses and read + write:
            return guesses[got]
    for other in TOKENS:
        if other != fact and getattr(t, other) == got:
            return f"equals {other.replace('_', ' ')}"
    return ""


def _value(fact: str, expected: Any, found: list[tuple[SpanRecord, str, Any]], t: Truth) -> Check:
    if expected is None:
        for _span, name, v in found:
            if fact not in TOKENS or not v:
                continue
            if t.no_usage:
                return Check(fact, "wrong", None, v, name, "estimated: the stream carried no usage")
            if v in t.unread_counts:
                return Check(
                    fact,
                    "wrong",
                    None,
                    v,
                    name,
                    "only the unread part of the stream carries this count",
                )
        return Check(fact, "n/a")
    if not found:
        return Check(fact, "missing", expected)
    for _span, name, v in found:
        ok = (
            same_finish(expected, v)
            if fact == "finish_reasons"
            else (isinstance(v, (int, float)) and v == expected)
            if fact in TOKENS
            else v == expected
        )
        if not ok and fact == "response_model" and name == "llm.model_name":
            ok = v == t.request_model  # this name does not separate request and response model
        if not ok:
            detail = _formula(fact, v, t) if fact in TOKENS and isinstance(v, int) else ""
            return Check(fact, "wrong", expected, v, name, detail)
    return Check(fact, "pass", expected, found[0][2], found[0][1])


def grade(
    sc: Scenario, t: Truth, base: dict | None, obs: dict | None, spans: list[SpanRecord]
) -> list[Check]:
    if obs is None or base is None:
        return [Check("harness", "inconclusive", detail="no observation was written")]
    if "instrument_error" in obs:
        return [Check("harness", "inconclusive", detail=obs["instrument_error"])]
    checks = [_app(base, obs)]
    if obs.get("hang"):
        return checks
    parent = obs["parent"]
    llm = [s for s in spans if s.span_id != parent["span_id"] and LLM_MARKERS & s.attributes.keys()]
    open_spans = [
        r["name"]
        for sid, r in obs.get("probe", {}).items()
        if r["end_ns"] is None and sid != parent["span_id"]
    ]
    if open_spans:
        checks.append(Check("span.ended", "lost", detail=f"never ended: {', '.join(open_spans)}"))
    if not llm:
        if not open_spans:
            checks.append(Check("span.recorded", "missing", detail="no LLM span arrived"))
        return checks
    orphans = [s.name for s in llm if s.trace_id != parent["trace_id"]]
    checks.append(
        Check(
            "span.parented",
            "wrong" if orphans else "pass",
            detail=f"outside the app's trace: {', '.join(orphans)}" if orphans else "",
        )
    )
    if t.error is not None:
        errored = [s for s in llm if s.status == "ERROR"]
        checks.append(
            Check(
                "error.status",
                "pass" if errored else "wrong",
                "ERROR",
                sorted({s.status for s in llm}),
            )
        )
        typed = [s.attributes["error.type"] for s in llm if s.attributes.get("error.type")]
        if typed:
            checks.append(Check("error.type", "pass", got=typed[0]))
        elif all(openinference_only(s.attributes) for s in llm):
            checks.append(
                Check(
                    "error.type",
                    "n/a",
                    detail="OpenInference records errors as span status and events",
                )
            )
        else:
            checks.append(Check("error.type", "missing"))
        return checks
    for fact in VALUES:
        if not any(defined_for(s.attributes, fact) for s in llm):
            checks.append(
                Check(fact, "n/a", detail="not defined by the conventions this library follows")
            )
            continue
        found = [(s, *hit) for s in llm if (hit := lookup(s.attributes, fact))]
        checks.append(_value(fact, getattr(t, fact), found, t))
    reporting = [
        s.name
        for s in llm
        if lookup(s.attributes, "input_tokens") or lookup(s.attributes, "output_tokens")
    ]
    if len(reporting) > 1:
        checks.append(
            Check(
                "tokens.single-report",
                "wrong",
                1,
                len(reporting),
                detail=f"usage on {len(reporting)} spans: {', '.join(reporting)}",
            )
        )
    return checks
