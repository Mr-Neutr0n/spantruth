"""OpenAI Chat Completions wire format: response builders and the truth they imply.

Shapes follow the published API reference. tests/test_wire.py parses every body and every
chunk with the `openai` SDK's own types, so a fixture the SDK would reject fails the suite.
"""

from __future__ import annotations

from .model import Event, Response, Truth

CREATED = 1760000000
FINGERPRINT = "fp_wt0001"


def _usage(prompt: int, completion: int, cached: int, reasoning: int) -> dict:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "prompt_tokens_details": {"cached_tokens": cached, "audio_tokens": 0},
        "completion_tokens_details": {
            "reasoning_tokens": reasoning,
            "audio_tokens": 0,
            "accepted_prediction_tokens": 0,
            "rejected_prediction_tokens": 0,
        },
    }


def _tool_call(index: int, call_id: str, name: str, arguments: str) -> dict:
    return {
        "index": index,
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def completion(
    *,
    id: str,
    model: str,
    text: str | None,
    finish: str,
    prompt: int,
    completion_tokens: int,
    cached: int = 0,
    reasoning: int = 0,
    tool_calls: tuple[tuple[str, str, str], ...] = (),
) -> Response:
    message: dict = {"role": "assistant", "content": text, "refusal": None, "annotations": []}
    if tool_calls:
        message["tool_calls"] = [
            {k: v for k, v in _tool_call(i, *call).items() if k != "index"}
            for i, call in enumerate(tool_calls)
        ]
    return Response(
        body={
            "id": id,
            "object": "chat.completion",
            "created": CREATED,
            "model": model,
            "system_fingerprint": FINGERPRINT,
            "service_tier": "default",
            "choices": [
                {"index": 0, "message": message, "finish_reason": finish, "logprobs": None}
            ],
            "usage": _usage(prompt, completion_tokens, cached, reasoning),
        }
    )


def chunks(
    *,
    id: str,
    model: str,
    parts: tuple[str, ...],
    finish: str,
    prompt: int,
    completion_tokens: int,
    cached: int = 0,
    reasoning: int = 0,
    drop_after: int | None = None,
    include_usage: bool = True,
) -> Response:
    """A stream. With `include_usage`, as sent for `stream_options={"include_usage": True}`."""

    def chunk(delta: dict, finish_reason: str | None = None) -> Event:
        return Event(
            {
                "id": id,
                "object": "chat.completion.chunk",
                "created": CREATED,
                "model": model,
                "system_fingerprint": FINGERPRINT,
                "service_tier": "default",
                "choices": [
                    {"index": 0, "delta": delta, "finish_reason": finish_reason, "logprobs": None}
                ],
                "usage": None,
            }
        )

    events = [chunk({"role": "assistant", "content": "", "refusal": None})]
    events += [chunk({"content": part}) for part in parts]
    events.append(chunk({}, finish))
    if include_usage:
        usage = chunk({}).data | {
            "choices": [],
            "usage": _usage(prompt, completion_tokens, cached, reasoning),
        }
        events.append(Event(usage))
    events.append(Event("[DONE]"))
    return Response(events=tuple(events), drop_after=drop_after)


def error(status: int, code: str, message: str) -> Response:
    return Response(
        status=status,
        body={"error": {"message": message, "type": "requests", "param": None, "code": code}},
    )


def truth(request_model: str, response: Response, read_events: int | None = None) -> Truth:
    """Derive the truth from what the app received.

    For a stream, only the events the app consumed count. An instrumentation sees the same
    events, so a value that never reached the app cannot be expected in the telemetry.
    """
    if response.status >= 400:
        return Truth(request_model=request_model, error=f"HTTP {response.status}")
    if response.body is not None:
        body = response.body
        return Truth(
            request_model=request_model,
            response_model=body["model"],
            response_id=body["id"],
            finish_reasons=tuple(c["finish_reason"] for c in body["choices"]),
            **_tokens(body["usage"]),
        )
    if response.reaches_drop(read_events):
        return Truth(request_model=request_model, error="connection dropped")
    seen = [e.data for e in response.consumed(read_events) if isinstance(e.data, dict)]
    every = [e.data for e in response.events or () if isinstance(e.data, dict)]
    usage = next((d["usage"] for d in seen if d.get("usage")), None)
    full = next((d["usage"] for d in every if d.get("usage")), None)
    finishes = tuple(
        c["finish_reason"] for d in seen for c in d["choices"] if c.get("finish_reason")
    )
    return Truth(
        request_model=request_model,
        response_model=seen[0]["model"] if seen else None,
        response_id=seen[0]["id"] if seen else None,
        finish_reasons=finishes or None,
        unread_counts=tuple(v for v in _tokens(full).values() if v) if full and not usage else (),
        no_usage=full is None,
        **(_tokens(usage) if usage else {}),
    )


def responses_truth(
    request_model: str, response: Response, read_events: int | None = None
) -> Truth:
    """The truth of a Responses API stream. Only the failure paths are graded so far."""
    if response.status >= 400:
        return Truth(request_model=request_model, error=f"HTTP {response.status}")
    if response.reaches_drop(read_events):
        return Truth(request_model=request_model, error="connection dropped")
    raise NotImplementedError("a Responses stream that ends is not graded yet")


def _tokens(usage: dict) -> dict:
    return {
        "input_tokens": usage["prompt_tokens"],
        "output_tokens": usage["completion_tokens"],
        "cache_read_tokens": usage["prompt_tokens_details"]["cached_tokens"] or None,
        "reasoning_tokens": usage["completion_tokens_details"]["reasoning_tokens"] or None,
    }
