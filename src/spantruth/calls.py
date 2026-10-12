"""The app side of each scenario: how a normal application calls the provider SDK.

Runs inside a subject's virtual environment. Every function returns what the app saw, so the
runner can compare an instrumented run with an uninstrumented one.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .model import Scenario

PROMPT = [{"role": "user", "content": "What is the capital of France?"}]
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {"type": "object", "properties": {key: {"type": "string"}}},
        },
    }
    for name, key in (("get_weather", "city"), ("get_time", "zone"))
]
ANTHROPIC_TOOLS = [
    {"name": name, "input_schema": {"type": "object", "properties": {key: {"type": "string"}}}}
    for name, key in (("get_weather", "city"), ("get_time", "zone"))
]


class Seen:
    """What the application observed. Compared between the baseline and instrumented runs."""

    def __init__(self) -> None:
        self.text = ""
        self.events = 0
        self.response_id: str | None = None
        self.usage: dict | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "events": self.events,
            "response_id": self.response_id,
            "usage": self.usage,
        }


def _openai_kwargs(sc: Scenario) -> dict:
    kw: dict = {"model": sc.request_model, "messages": PROMPT}
    if sc.tools:
        kw["tools"] = OPENAI_TOOLS
    if sc.stream:
        kw["stream"] = True
    if sc.stream and sc.stream_usage:
        kw["stream_options"] = {"include_usage": True}
    return kw


def _anthropic_kwargs(sc: Scenario) -> dict:
    kw: dict = {"model": sc.request_model, "max_tokens": 1024, "messages": PROMPT}
    if sc.tools:
        kw["tools"] = ANTHROPIC_TOOLS
    if sc.stream:
        kw["stream"] = True
    return kw


def _openai_result(r: Any, seen: Seen) -> None:
    msg = r.choices[0].message
    seen.text = (msg.content or "") + "".join(t.function.name for t in msg.tool_calls or ())
    seen.response_id, seen.usage = r.id, r.usage.model_dump()


def _openai_chunk(c: Any, seen: Seen) -> None:
    seen.events += 1
    seen.response_id = c.id
    if c.choices and c.choices[0].delta.content:
        seen.text += c.choices[0].delta.content
    if c.usage:
        seen.usage = c.usage.model_dump()


def _anthropic_result(r: Any, seen: Seen) -> None:
    seen.text = "".join(b.text if b.type == "text" else b.name for b in r.content)
    seen.response_id, seen.usage = r.id, r.usage.model_dump()


def _anthropic_event(e: Any, seen: Seen) -> None:
    seen.events += 1
    if e.type == "message_start":
        seen.response_id = e.message.id
    elif e.type == "content_block_delta" and e.delta.type == "text_delta":
        seen.text += e.delta.text


def run(sc: Scenario, base_url: str, seen: Seen) -> None:
    """Run one scenario the way an application would. Exceptions propagate to the caller."""
    if sc.asynchronous:
        asyncio.run(_run_async(sc, base_url, seen))
        return
    if sc.provider == "openai":
        import openai

        client = openai.OpenAI(base_url=base_url, api_key="wt-test", max_retries=0, timeout=10)
        result = client.chat.completions.create(**_openai_kwargs(sc))
        on_result, on_event = _openai_result, _openai_chunk
    else:
        import anthropic

        client = anthropic.Anthropic(
            base_url=base_url, api_key="wt-test", max_retries=0, timeout=10
        )
        result = client.messages.create(**_anthropic_kwargs(sc))
        on_result, on_event = _anthropic_result, _anthropic_event
    if not sc.stream:
        on_result(result, seen)
        return
    if sc.with_block:
        with result as stream:
            _read(stream, sc, seen, on_event)
        return
    _read(result, sc, seen, on_event)
    result.close()


def _read(stream: Any, sc: Scenario, seen: Seen, on_event) -> None:
    for event in stream:
        on_event(event, seen)
        if sc.read_events is not None and seen.events >= sc.read_events:
            break


async def _run_async(sc: Scenario, base_url: str, seen: Seen) -> None:
    if sc.provider == "openai":
        import openai

        client = openai.AsyncOpenAI(base_url=base_url, api_key="wt-test", max_retries=0, timeout=10)
        result = await client.chat.completions.create(**_openai_kwargs(sc))
        on_result, on_event = _openai_result, _openai_chunk
    else:
        import anthropic

        client = anthropic.AsyncAnthropic(
            base_url=base_url, api_key="wt-test", max_retries=0, timeout=10
        )
        result = await client.messages.create(**_anthropic_kwargs(sc))
        on_result, on_event = _anthropic_result, _anthropic_event
    if not sc.stream:
        on_result(result, seen)
        return
    if sc.with_block:
        async with result as stream:
            await _aread(stream, sc, seen, on_event)
        return
    await _aread(result, sc, seen, on_event)
    await result.close()


async def _aread(stream: Any, sc: Scenario, seen: Seen, on_event) -> None:
    async for event in stream:
        on_event(event, seen)
        if sc.read_events is not None and seen.events >= sc.read_events:
            break
