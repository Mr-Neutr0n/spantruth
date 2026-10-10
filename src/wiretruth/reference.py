"""A small, deliberately plain instrumentation of the OpenAI and Anthropic SDKs.

It exists to test the suite, not to be used. `control-honest` runs it as written and has to
pass every check. `control-faulty` runs it with known faults switched on and has to fail
exactly the checks those faults target. If either control moves, the suite is broken.

Faults:
    anthropic-raw-input   report Anthropic's wire `input_tokens`, without cache tokens
    close-leaks-span      `stream.close()` does not end the span
    errors-as-success     exceptions are not recorded on the span
    estimate-tokens       a stream without usage gets an estimate from the text length
"""

from __future__ import annotations

import functools
from typing import Any

from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer


class _Call:
    """The span of one call and the facts gathered for it."""

    def __init__(self, tracer: Tracer, provider: str, model: str, faults: set[str]) -> None:
        self.span = tracer.start_span(
            f"chat {model}",
            kind=SpanKind.CLIENT,
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": provider,
                "gen_ai.request.model": model,
            },
        )
        self.provider, self.faults = provider, faults
        self.finish: list[str] = []
        self.text = ""
        self.usage_seen = False
        self.ended = False

    def set(self, key: str, value: Any) -> None:
        if value is not None:
            self.span.set_attribute(key, value)

    def usage(
        self, inp: int, out: int | None, read: int = 0, write: int = 0, reasoning: int = 0
    ) -> None:
        self.usage_seen = True
        if self.provider == "anthropic" and "anthropic-raw-input" not in self.faults:
            inp += read + write
        self.set("gen_ai.usage.input_tokens", inp)
        self.set("gen_ai.usage.output_tokens", out)
        self.set("gen_ai.usage.cache_read.input_tokens", read or None)
        self.set("gen_ai.usage.cache_write.input_tokens", write or None)
        self.set("gen_ai.usage.reasoning.output_tokens", reasoning or None)

    def fail(self, exc: BaseException) -> None:
        if "errors-as-success" not in self.faults:
            self.span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
            self.set("error.type", type(exc).__name__)
        self.end()

    def end(self) -> None:
        if self.ended:
            return
        self.ended = True
        if self.finish:
            self.set("gen_ai.response.finish_reasons", self.finish)
        if not self.usage_seen and self.text and "estimate-tokens" in self.faults:
            self.set("gen_ai.usage.output_tokens", max(1, len(self.text) // 4))
        self.span.end()


def _openai_response(call: _Call, r: Any) -> None:
    call.set("gen_ai.response.model", r.model)
    call.set("gen_ai.response.id", r.id)
    call.finish = [c.finish_reason for c in r.choices]
    _openai_usage(call, r.usage)


def _openai_usage(call: _Call, u: Any) -> None:
    cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0
    reasoning = getattr(u.completion_tokens_details, "reasoning_tokens", 0) or 0
    call.usage(u.prompt_tokens, u.completion_tokens, read=cached, reasoning=reasoning)


def _openai_chunk(call: _Call, c: Any) -> None:
    call.set("gen_ai.response.model", c.model)
    call.set("gen_ai.response.id", c.id)
    for choice in c.choices:
        if choice.delta.content:
            call.text += choice.delta.content
        if choice.finish_reason:
            call.finish.append(choice.finish_reason)
    if c.usage:
        _openai_usage(call, c.usage)


def _anthropic_response(call: _Call, r: Any) -> None:
    call.set("gen_ai.response.model", r.model)
    call.set("gen_ai.response.id", r.id)
    call.finish = [r.stop_reason]
    u = r.usage
    call.usage(
        u.input_tokens,
        u.output_tokens,
        u.cache_read_input_tokens or 0,
        u.cache_creation_input_tokens or 0,
    )


def _anthropic_event(call: _Call, e: Any) -> None:
    if e.type == "message_start":
        m = e.message
        call.set("gen_ai.response.model", m.model)
        call.set("gen_ai.response.id", m.id)
        u = m.usage
        call.usage(
            u.input_tokens, None, u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
        )
    elif e.type == "message_delta":
        # Output is cumulative here. Input and cache counts, when repeated, are not added again.
        call.set("gen_ai.usage.output_tokens", e.usage.output_tokens)
        if e.delta.stop_reason:
            call.finish = [e.delta.stop_reason]
    elif e.type == "content_block_delta" and e.delta.type == "text_delta":
        call.text += e.delta.text


class _Stream:
    def __init__(self, inner: Any, call: _Call, on_event) -> None:
        self._inner, self._call, self._on_event = inner, call, on_event

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __iter__(self):
        try:
            for event in self._inner:
                self._on_event(self._call, event)
                yield event
        except Exception as exc:
            self._call.fail(exc)
            raise
        self._call.end()

    def __aiter__(self):
        return self._agen()

    async def _agen(self):
        try:
            async for event in self._inner:
                self._on_event(self._call, event)
                yield event
        except Exception as exc:
            self._call.fail(exc)
            raise
        self._call.end()

    def _closed(self) -> None:
        if "close-leaks-span" not in self._call.faults:
            self._call.end()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._inner.__exit__(*exc)
        self._closed()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._inner.__aexit__(*exc)
        self._closed()

    def close(self):
        result = self._inner.close()
        if hasattr(result, "__await__"):
            return self._aclose(result)
        self._closed()
        return result

    async def _aclose(self, pending):
        await pending
        self._closed()


def _wrap(tracer: Tracer, provider: str, faults: set[str], on_result, on_event, create, is_async):
    def begin(kwargs: dict) -> _Call:
        return _Call(tracer, provider, kwargs.get("model", ""), faults)

    # Decided by class, not by inspection: the SDKs wrap async methods in sync decorators.
    if is_async:

        @functools.wraps(create)
        async def acall(self, *args, **kwargs):
            call = begin(kwargs)
            try:
                result = await create(self, *args, **kwargs)
            except Exception as exc:
                call.fail(exc)
                raise
            return _finish(call, result, kwargs, on_result, on_event)

        return acall

    @functools.wraps(create)
    def scall(self, *args, **kwargs):
        call = begin(kwargs)
        try:
            result = create(self, *args, **kwargs)
        except Exception as exc:
            call.fail(exc)
            raise
        return _finish(call, result, kwargs, on_result, on_event)

    return scall


def _finish(call: _Call, result: Any, kwargs: dict, on_result, on_event) -> Any:
    if kwargs.get("stream"):
        return _Stream(result, call, on_event)
    on_result(call, result)
    call.end()
    return result


def instrument(tracer_provider, faults: set[str] = frozenset()) -> None:
    tracer = tracer_provider.get_tracer("wiretruth.reference")
    import anthropic.resources.messages as am
    import openai.resources.chat.completions as oc

    for cls, is_async in ((oc.Completions, False), (oc.AsyncCompletions, True)):
        cls.create = _wrap(
            tracer, "openai", set(faults), _openai_response, _openai_chunk, cls.create, is_async
        )
    for cls, is_async in ((am.Messages, False), (am.AsyncMessages, True)):
        cls.create = _wrap(
            tracer,
            "anthropic",
            set(faults),
            _anthropic_response,
            _anthropic_event,
            cls.create,
            is_async,
        )
