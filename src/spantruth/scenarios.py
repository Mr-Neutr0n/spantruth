"""The scenario registry. Every token count is distinct and non-round on purpose.

A swapped field, a dropped cache count or a wrong sum then shows up as a wrong number,
never as a coincidental pass. Model names are placeholders: no request leaves the machine.
"""

from __future__ import annotations

from dataclasses import replace

from . import recorded
from . import wire_anthropic as an
from . import wire_openai as oa
from .model import Scenario, Truth

OPENAI_MODEL = "gpt-5-mini"
OPENAI_SERVED = "gpt-5-mini-2026-08-07"
ANTHROPIC_MODEL = "claude-sonnet-5-5"
ANTHROPIC_SERVED = "claude-sonnet-5-5-20260915"
PARTS = ("The capital", " of France", " is Paris.")
WEATHER = ("get_weather", {"city": "Paris"})
TIME = ("get_time", {"zone": "Europe/Paris"})

# Async variants run the same fixture through the async client.
ASYNC_PATTERNS = ("basic", "stream", "stream-early-exit", "stream-dropped", "stream-error-event")


def _openai() -> list[Scenario]:
    def sc(name: str, title: str, catches: str, response, **kw) -> Scenario:
        return Scenario(
            id=f"openai/{name}",
            provider="openai",
            title=title,
            catches=catches,
            request_model=OPENAI_MODEL,
            response=response,
            **kw,
        )

    body = dict(model=OPENAI_SERVED, text="The capital of France is Paris.", finish="stop")
    stream = dict(model=OPENAI_SERVED, parts=PARTS, finish="stop")
    return [
        sc(
            "basic",
            "One call",
            "model, id, finish reason and tokens",
            oa.completion(id="chatcmpl-wt-basic", prompt=1187, completion_tokens=263, **body),
        ),
        sc(
            "stream",
            "Stream read to the end",
            "usage read from the final chunk",
            oa.chunks(id="chatcmpl-wt-stream", prompt=2311, completion_tokens=419, **stream),
            stream=True,
        ),
        sc(
            "stream-early-exit",
            "App closes the stream after two chunks",
            "a span that never ends, a drained response",
            oa.chunks(id="chatcmpl-wt-early", prompt=1913, completion_tokens=347, **stream),
            stream=True,
            read_events=2,
        ),
        sc(
            "cache-hit",
            "Prompt cache hit",
            "cached tokens dropped from usage",
            oa.completion(
                id="chatcmpl-wt-cache", prompt=5379, completion_tokens=377, cached=4096, **body
            ),
        ),
        sc(
            "stream-cache-hit",
            "Prompt cache hit, streamed",
            "cached tokens lost in a stream",
            oa.chunks(
                id="chatcmpl-wt-scache", prompt=7213, completion_tokens=511, cached=6144, **stream
            ),
            stream=True,
        ),
        sc(
            "stream-no-usage",
            "Stream without include_usage",
            "token counts invented when the stream carries none",
            oa.chunks(
                id="chatcmpl-wt-nousage",
                prompt=1667,
                completion_tokens=389,
                include_usage=False,
                **stream,
            ),
            stream=True,
            stream_usage=False,
        ),
        sc(
            "tool-call",
            "Two parallel tool calls",
            "the finish reason of a tool-call response",
            oa.completion(
                id="chatcmpl-wt-tools",
                model=OPENAI_SERVED,
                text=None,
                finish="tool_calls",
                prompt=931,
                completion_tokens=88,
                tool_calls=(
                    ("call_wt_1", WEATHER[0], '{"city":"Paris"}'),
                    ("call_wt_2", TIME[0], '{"zone":"Europe/Paris"}'),
                ),
            ),
            tools=True,
        ),
        sc(
            "rate-limited",
            "HTTP 429",
            "a failed call recorded as a success",
            oa.error(429, "rate_limit_exceeded", "Rate limit reached for gpt-5-mini."),
        ),
        sc(
            "stream-dropped",
            "Connection drops mid-stream",
            "an error swallowed into a cut-off answer",
            oa.chunks(
                id="chatcmpl-wt-drop", prompt=1427, completion_tokens=301, drop_after=3, **stream
            ),
            stream=True,
        ),
        sc(
            "reasoning",
            "Reasoning tokens",
            "reasoning tokens lost from output",
            oa.completion(
                id="chatcmpl-wt-reason", prompt=1601, completion_tokens=2219, reasoning=1792, **body
            ),
        ),
    ]


def _recorded() -> list[Scenario]:
    """Scenarios replayed from recorded provider streams, rather than built in code."""
    abort = recorded.FIXTURES / "openai-responses" / "stream.missing-finish-abort.json"
    return [
        Scenario(
            id="openai/responses-stream-missing-finish-abort",
            provider="openai",
            api="responses",
            title="Responses API stream cut after eight recorded events",
            catches="an aborted stream recorded as a success",
            request_model=recorded.requested_model(abort),
            response=recorded.load(abort),
            stream=True,
            tags=("recorded",),
        )
    ]


def _anthropic() -> list[Scenario]:
    def sc(name: str, title: str, catches: str, response, **kw) -> Scenario:
        return Scenario(
            id=f"anthropic/{name}",
            provider="anthropic",
            title=title,
            catches=catches,
            request_model=ANTHROPIC_MODEL,
            response=response,
            **kw,
        )

    body = dict(model=ANTHROPIC_SERVED, text="The capital of France is Paris.", stop="end_turn")
    stream = dict(model=ANTHROPIC_SERVED, parts=PARTS, stop="end_turn")
    return [
        sc(
            "basic",
            "One call",
            "model, id, finish reason and tokens",
            an.message(id="msg_wt_basic", input_tokens=1187, output_tokens=263, **body),
        ),
        sc(
            "stream",
            "Stream read to the end",
            "usage split across message_start and message_delta",
            an.events(id="msg_wt_stream", input_tokens=2311, output_tokens=419, **stream),
            stream=True,
        ),
        sc(
            "stream-early-exit",
            "App closes the stream after two events",
            "a span that never ends, a drained response",
            an.events(id="msg_wt_early", input_tokens=1913, output_tokens=347, **stream),
            stream=True,
            read_events=2,
        ),
        sc(
            "cache-hit",
            "Prompt cache read and write",
            "cache tokens not added to input tokens",
            an.message(
                id="msg_wt_cache",
                input_tokens=1187,
                output_tokens=377,
                cache_read=4096,
                cache_write=519,
                **body,
            ),
        ),
        sc(
            "stream-cache-hit",
            "Prompt cache read and write, streamed",
            "cache counts reset by message_delta",
            an.events(
                id="msg_wt_scache",
                input_tokens=1543,
                output_tokens=511,
                cache_read=6144,
                cache_write=737,
                **stream,
            ),
            stream=True,
        ),
        sc(
            "stream-cache-cumulative",
            "Cache counts repeated in message_delta",
            "cache tokens counted twice",
            an.events(
                id="msg_wt_cumul",
                input_tokens=1279,
                output_tokens=467,
                cache_read=3583,
                cache_write=811,
                cumulative_delta=True,
                **stream,
            ),
            stream=True,
        ),
        sc(
            "stream-error-event",
            "Overloaded error event mid-stream",
            "an error event swallowed into a cut-off answer",
            an.events(
                id="msg_wt_overload",
                input_tokens=1301,
                output_tokens=283,
                error_after=3,
                **stream,
            ),
            stream=True,
        ),
        sc(
            "tool-call",
            "Two parallel tool uses",
            "the finish reason of a tool-call response",
            an.message(
                id="msg_wt_tools",
                model=ANTHROPIC_SERVED,
                text=None,
                stop="tool_use",
                input_tokens=931,
                output_tokens=88,
                tool_uses=(("toolu_wt_1", *WEATHER), ("toolu_wt_2", *TIME)),
            ),
            tools=True,
        ),
        sc(
            "rate-limited",
            "HTTP 429",
            "a failed call recorded as a success",
            an.error(429, "rate_limit_error", "Number of request tokens has exceeded your limit."),
        ),
        sc(
            "stream-dropped",
            "Connection drops mid-stream",
            "an error swallowed into a cut-off answer",
            an.events(
                id="msg_wt_drop", input_tokens=1427, output_tokens=301, drop_after=3, **stream
            ),
            stream=True,
        ),
    ]


def _with_block(scenarios: list[Scenario]) -> list[Scenario]:
    """The early exit again, leaving a `with` block instead of calling `close()`."""
    extra = []
    for s in scenarios:
        provider, name = s.id.split("/", 1)
        if name == "stream-early-exit":
            extra.append(
                replace(
                    s,
                    id=f"{provider}/stream-early-exit-with",
                    with_block=True,
                    title=f"{s.title.replace('closes', 'leaves')} with a with block",
                )
            )
    return scenarios + extra


def _with_async(scenarios: list[Scenario]) -> list[Scenario]:
    extra = []
    for s in scenarios:
        provider, name = s.id.split("/", 1)
        if name in ASYNC_PATTERNS:
            extra.append(
                replace(
                    s, id=f"{provider}/async-{name}", asynchronous=True, title=f"{s.title} (async)"
                )
            )
    return scenarios + extra


SCENARIOS: dict[str, Scenario] = {
    s.id: s for s in _with_async(_with_block(_openai() + _anthropic())) + _recorded()
}


def get(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        raise KeyError(f"unknown scenario {scenario_id!r}; run `spantruth list`") from None


def by_key(key: str) -> Scenario:
    return get(key.replace("--", "/"))


def truth(scenario: Scenario) -> Truth:
    if scenario.api == "responses":
        derive = oa.responses_truth
    else:
        derive = oa.truth if scenario.provider == "openai" else an.truth
    return derive(scenario.request_model, scenario.response, scenario.read_events)
