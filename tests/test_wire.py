"""Fixtures are valid wire data, and the truth derived from them is what the spec says."""

import json

import anthropic.types
import openai.types.chat
import openai.types.responses
import pydantic
import pytest

from spantruth import scenarios
from spantruth.model import Response

ALL = list(scenarios.SCENARIOS.values())
ANTHROPIC_EVENT = pydantic.TypeAdapter(anthropic.types.RawMessageStreamEvent)
RESPONSES_EVENT = pydantic.TypeAdapter(openai.types.responses.ResponseStreamEvent)


@pytest.mark.parametrize("sc", ALL, ids=lambda s: s.id)
def test_fixtures_parse_with_sdk_types(sc):
    r = sc.response
    if r.status >= 400:
        assert r.body is not None and "error" in r.body
        return
    if sc.api == "responses":
        for e in r.events or ():
            assert RESPONSES_EVENT.validate_python(json.loads(e.data)).type == e.event
    elif sc.provider == "openai":
        if r.body is not None:
            openai.types.chat.ChatCompletion.model_validate(r.body, strict=False)
        for e in r.events or ():
            if isinstance(e.data, dict):
                openai.types.chat.ChatCompletionChunk.model_validate(e.data)
            else:
                assert e.data == "[DONE]"
    else:
        if r.body is not None:
            anthropic.types.Message.model_validate(r.body)
        for e in r.events or ():
            if e.event == "error":
                # Not a RawMessageStreamEvent: the SDK raises on it before parsing.
                assert e.data["error"]["type"] in {"overloaded_error", "api_error"}
                continue
            parsed = ANTHROPIC_EVENT.validate_python(e.data)
            assert parsed.type == e.event


@pytest.mark.parametrize("sc", ALL, ids=lambda s: s.id)
def test_fixture_truth_values_are_distinct(sc):
    t = scenarios.truth(sc)
    values = [
        v
        for v in (
            t.input_tokens,
            t.output_tokens,
            t.cache_read_tokens,
            t.cache_write_tokens,
            t.reasoning_tokens,
        )
        if v is not None
    ]
    assert len(values) == len(set(values)), f"{sc.id} repeats a token value: {values}"
    if t.response_model is not None:
        assert t.response_model != t.request_model


def test_anthropic_input_tokens_include_cache_read_and_write():
    t = scenarios.truth(scenarios.get("anthropic/cache-hit"))
    assert (t.input_tokens, t.cache_read_tokens, t.cache_write_tokens) == (5802, 4096, 519)


def test_cumulative_delta_counts_cache_once():
    t = scenarios.truth(scenarios.get("anthropic/stream-cache-cumulative"))
    assert (t.input_tokens, t.output_tokens) == (5673, 467)


def test_error_event_and_missing_usage():
    assert scenarios.truth(scenarios.get("anthropic/stream-error-event")).error == (
        "error event: overloaded_error"
    )
    t = scenarios.truth(scenarios.get("openai/stream-no-usage"))
    assert t.input_tokens is None and t.finish_reasons == ("stop",)


def test_anthropic_stream_takes_cache_from_message_start_and_output_from_delta():
    t = scenarios.truth(scenarios.get("anthropic/stream-cache-hit"))
    assert (t.input_tokens, t.output_tokens) == (8424, 511)
    assert (t.cache_read_tokens, t.cache_write_tokens) == (6144, 737)
    assert t.finish_reasons == ("end_turn",)


def test_openai_prompt_tokens_already_include_cached_tokens():
    t = scenarios.truth(scenarios.get("openai/stream-cache-hit"))
    assert (t.input_tokens, t.cache_read_tokens, t.output_tokens) == (7213, 6144, 511)


def test_openai_reasoning_stays_inside_output_tokens():
    t = scenarios.truth(scenarios.get("openai/reasoning"))
    assert (t.output_tokens, t.reasoning_tokens) == (2219, 1792)


def test_openai_early_exit_holds_no_usage_and_marks_the_unread_counts():
    t = scenarios.truth(scenarios.get("openai/stream-early-exit"))
    assert t.response_model is not None and t.response_id is not None
    assert t.input_tokens is None and t.output_tokens is None and t.finish_reasons is None
    assert set(t.unread_counts) == {1913, 347}


def test_anthropic_early_exit_knows_input_from_message_start_only():
    t = scenarios.truth(scenarios.get("anthropic/stream-early-exit"))
    assert (t.input_tokens, t.output_tokens, t.finish_reasons) == (1913, None, None)
    assert t.unread_counts == (347,)


def test_openai_stream_without_usage_is_flagged():
    assert scenarios.truth(scenarios.get("openai/stream-no-usage")).no_usage


@pytest.mark.parametrize("sid", ["openai/stream-dropped", "anthropic/stream-dropped"])
def test_dropped_stream_is_an_error_with_no_values(sid):
    t = scenarios.truth(scenarios.get(sid))
    assert t.error == "connection dropped"
    assert t.output_tokens is None and t.finish_reasons is None


def test_error_truth_is_the_status():
    t = scenarios.truth(scenarios.get("openai/rate-limited"))
    assert t.error == "HTTP 429" and t.input_tokens is None


def test_zero_cache_counts_are_not_graded():
    t = scenarios.truth(scenarios.get("openai/basic"))
    assert t.cache_read_tokens is None and t.reasoning_tokens is None


def test_response_rejects_body_and_events_together():
    with pytest.raises(ValueError):
        Response(body={}, events=())


def test_async_variants_exist_for_stream_patterns():
    assert scenarios.get("openai/async-stream-early-exit").asynchronous
    assert scenarios.get("anthropic/async-stream").asynchronous
