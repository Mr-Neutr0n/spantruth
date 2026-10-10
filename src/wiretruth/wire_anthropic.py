"""Anthropic Messages wire format: response builders and the truth they imply.

Shapes follow the published API reference. tests/test_wire.py parses every body and every
event with the `anthropic` SDK's own types, so a fixture the SDK would reject fails the suite.
"""

from __future__ import annotations

from .model import Event, Response, Truth


def _usage(input_tokens: int, output_tokens: int, cache_read: int, cache_write: int) -> dict:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
    }


def message(
    *,
    id: str,
    model: str,
    text: str | None,
    stop: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_write: int = 0,
    tool_uses: tuple[tuple[str, str, dict], ...] = (),
) -> Response:
    content: list[dict] = [{"type": "text", "text": text}] if text else []
    content += [{"type": "tool_use", "id": i, "name": n, "input": a} for i, n, a in tool_uses]
    return Response(
        body={
            "id": id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": _usage(input_tokens, output_tokens, cache_read, cache_write),
        }
    )


def events(
    *,
    id: str,
    model: str,
    parts: tuple[str, ...],
    stop: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_write: int = 0,
    drop_after: int | None = None,
    cumulative_delta: bool = False,
    error_after: int | None = None,
) -> Response:
    """A stream as the API sends it.

    `message_delta` carries only the final output count, unless `cumulative_delta` is set: the
    API may also repeat the cumulative input and cache counts there, and a library that adds
    them to `message_start` counts them twice. `error_after` replaces the rest of the stream with
    an `error` event after that many events, as the API does when it is overloaded mid-stream.
    """

    def ev(kind: str, **data: object) -> Event:
        return Event({"type": kind, **data}, event=kind)

    start = {
        "id": id,
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": _usage(input_tokens, 1, cache_read, cache_write),
    }
    stream = [
        ev("message_start", message=start),
        ev("content_block_start", index=0, content_block={"type": "text", "text": ""}),
    ]
    stream += [
        ev("content_block_delta", index=0, delta={"type": "text_delta", "text": p}) for p in parts
    ]
    stream += [
        ev("content_block_stop", index=0),
        ev(
            "message_delta",
            delta={"stop_reason": stop, "stop_sequence": None},
            usage=(
                _usage(input_tokens, output_tokens, cache_read, cache_write)
                if cumulative_delta
                else {"output_tokens": output_tokens}
            ),
        ),
        ev("message_stop"),
    ]
    if error_after is not None:
        overloaded = {"type": "overloaded_error", "message": "Overloaded"}
        stream = [*stream[:error_after], ev("error", error=overloaded)]
    return Response(events=tuple(stream), drop_after=drop_after)


def error(status: int, kind: str, message: str) -> Response:
    return Response(
        status=status, body={"type": "error", "error": {"type": kind, "message": message}}
    )


def truth(request_model: str, response: Response, read_events: int | None = None) -> Truth:
    """Derive the truth from what the app received.

    Anthropic's `input_tokens` excludes cached tokens. The GenAI conventions require the
    instrumentation to add cache reads and cache writes, so the truth carries the sum.
    `message_start` carries the input counts, so they are known as soon as the app has it.
    """
    if response.status >= 400:
        return Truth(request_model=request_model, error=f"HTTP {response.status}")
    if response.body is not None:
        body = response.body
        return Truth(
            request_model=request_model,
            response_model=body["model"],
            response_id=body["id"],
            finish_reasons=(body["stop_reason"],),
            **_tokens(body["usage"], body["usage"]["output_tokens"]),
        )
    if response.reaches_drop(read_events):
        return Truth(request_model=request_model, error="connection dropped")
    seen = [e.data for e in response.consumed(read_events) if isinstance(e.data, dict)]
    failure = next((d["error"]["type"] for d in seen if d["type"] == "error"), None)
    if failure:
        return Truth(request_model=request_model, error=f"error event: {failure}")
    every = [e.data for e in response.events or () if isinstance(e.data, dict)]
    start = next((d["message"] for d in seen if d["type"] == "message_start"), None)
    delta = next((d for d in reversed(seen) if d["type"] == "message_delta"), None)
    final = next((d for d in reversed(every) if d["type"] == "message_delta"), None)
    output = delta["usage"]["output_tokens"] if delta else None
    return Truth(
        request_model=request_model,
        response_model=start["model"] if start else None,
        response_id=start["id"] if start else None,
        finish_reasons=(delta["delta"]["stop_reason"],) if delta else None,
        unread_counts=(final["usage"]["output_tokens"],) if final and not delta else (),
        **(_tokens(start["usage"], output) if start else {}),
    )


def _tokens(usage: dict, output_tokens: int | None) -> dict:
    read = usage.get("cache_read_input_tokens") or 0
    write = usage.get("cache_creation_input_tokens") or 0
    return {
        "input_tokens": usage["input_tokens"] + read + write,
        "output_tokens": output_tokens,
        "cache_read_tokens": read or None,
        "cache_write_tokens": write or None,
    }
