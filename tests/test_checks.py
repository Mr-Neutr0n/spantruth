"""Every verdict the checks can return, on hand-built records. No subprocess, no network."""

from wiretruth import scenarios
from wiretruth.checks import cell_verdict, grade
from wiretruth.receiver import SpanRecord

TRACE, PARENT = "a" * 32, "b" * 16
BASE = {"exception": None, "seen": {"text": "x", "events": 0, "response_id": "r", "usage": None}}


def span(attrs, name="chat", trace=TRACE, status="UNSET", span_id="c" * 16):
    return SpanRecord(trace, span_id, PARENT, name, 3, 1, 2, status, "", attrs, {}, "lib", ())


def obs(probe=None, **seen):
    return {
        "exception": seen.pop("exception", None),
        "seen": BASE["seen"] | seen,
        "parent": {"trace_id": TRACE, "span_id": PARENT},
        "probe": probe or {},
    }


def by_id(checks):
    return {c.id: c for c in checks}


def honest(sid):
    t = scenarios.truth(scenarios.get(sid))
    attrs = {"gen_ai.operation.name": "chat", "gen_ai.request.model": t.request_model}
    for fact, name in [
        ("response_model", "gen_ai.response.model"),
        ("response_id", "gen_ai.response.id"),
        ("input_tokens", "gen_ai.usage.input_tokens"),
        ("output_tokens", "gen_ai.usage.output_tokens"),
        ("cache_read_tokens", "gen_ai.usage.cache_read.input_tokens"),
        ("cache_write_tokens", "gen_ai.usage.cache_creation.input_tokens"),
    ]:
        if getattr(t, fact) is not None:
            attrs[name] = getattr(t, fact)
    if t.finish_reasons:
        attrs["gen_ai.response.finish_reasons"] = list(t.finish_reasons)
    return t, attrs


def test_correct_span_passes():
    sc = scenarios.get("anthropic/cache-hit")
    t, attrs = honest(sc.id)
    checks = grade(sc, t, BASE, obs(), [span(attrs)])
    assert cell_verdict(checks) == "pass", [c for c in checks if c.verdict != "pass"]


def test_anthropic_input_without_cache_is_wrong_and_the_formula_is_named():
    sc = scenarios.get("anthropic/cache-hit")
    t, attrs = honest(sc.id)
    attrs["gen_ai.usage.input_tokens"] = 1187
    c = by_id(grade(sc, t, BASE, obs(), [span(attrs)]))["input_tokens"]
    assert (c.verdict, c.expected, c.got) == ("wrong", 5802, 1187)
    assert c.detail == "cache reads and writes left out"


def test_cache_reads_counted_twice_is_named():
    sc = scenarios.get("anthropic/cache-hit")
    t, attrs = honest(sc.id)
    attrs["gen_ai.usage.input_tokens"] = 5802 + 4096 + 519
    assert by_id(grade(sc, t, BASE, obs(), [span(attrs)]))["input_tokens"].detail == (
        "cache tokens counted twice"
    )


def test_absent_value_is_missing_not_wrong():
    sc = scenarios.get("openai/basic")
    t, attrs = honest(sc.id)
    del attrs["gen_ai.response.id"]
    assert by_id(grade(sc, t, BASE, obs(), [span(attrs)]))["response_id"].verdict == "missing"


def test_openinference_names_are_read_and_reported():
    sc = scenarios.get("openai/basic")
    t = scenarios.truth(sc)
    attrs = {
        "llm.token_count.prompt": 1187,
        "llm.token_count.completion": 263,
        "llm.model_name": t.response_model,
    }
    c = by_id(grade(sc, t, BASE, obs(), [span(attrs)]))
    assert (
        c["input_tokens"].verdict == "pass" and c["input_tokens"].where == "llm.token_count.prompt"
    )


def test_span_that_never_ended_is_lost():
    sc = scenarios.get("openai/stream-early-exit")
    t = scenarios.truth(sc)
    probe = {"d" * 16: {"name": "chat gpt-5-mini", "start_ns": 1, "end_ns": None}}
    checks = grade(sc, t, BASE, obs(probe), [])
    assert cell_verdict(checks) == "lost"


def test_no_span_at_all_is_missing():
    sc = scenarios.get("openai/basic")
    checks = grade(sc, scenarios.truth(sc), BASE, obs(), [])
    assert by_id(checks)["span.recorded"].verdict == "missing"


def test_changed_exception_is_broken():
    sc = scenarios.get("openai/stream-dropped")
    base = BASE | {"exception": "httpx.RemoteProtocolError"}
    checks = grade(sc, scenarios.truth(sc), base, obs(), [])
    assert by_id(checks)["app.unchanged"].verdict == "broken"


def test_hang_is_broken():
    sc = scenarios.get("openai/basic")
    assert cell_verdict(grade(sc, scenarios.truth(sc), BASE, {"hang": True}, [])) == "broken"


def test_error_recorded_as_success_is_wrong():
    sc = scenarios.get("openai/rate-limited")
    attrs = {"gen_ai.request.model": "gpt-5-mini"}
    c = by_id(grade(sc, scenarios.truth(sc), BASE, obs(), [span(attrs, status="UNSET")]))
    assert c["error.status"].verdict == "wrong" and c["error.type"].verdict == "missing"


def test_any_error_type_passes():
    sc = scenarios.get("anthropic/rate-limited")
    attrs = {"gen_ai.request.model": "m", "error.type": "RateLimitError"}
    c = by_id(grade(sc, scenarios.truth(sc), BASE, obs(), [span(attrs, status="ERROR")]))
    assert c["error.status"].verdict == "pass" and c["error.type"].verdict == "pass"


def test_span_in_another_trace_is_wrong():
    sc = scenarios.get("openai/basic")
    t, attrs = honest(sc.id)
    c = by_id(grade(sc, t, BASE, obs(), [span(attrs, trace="f" * 32)]))
    assert c["span.parented"].verdict == "wrong"


def test_usage_on_two_spans_is_a_double_count():
    sc = scenarios.get("openai/stream")
    t, attrs = honest(sc.id)
    two = [span(attrs), span(attrs, name="streaming response", span_id="e" * 16)]
    assert by_id(grade(sc, t, BASE, obs(), two))["tokens.single-report"].verdict == "wrong"


def test_count_from_the_unread_stream_is_wrong():
    sc = scenarios.get("openai/stream-early-exit")
    t = scenarios.truth(sc)
    attrs = {"gen_ai.request.model": "gpt-5-mini", "gen_ai.usage.output_tokens": 347}
    c = by_id(grade(sc, t, BASE, obs(), [span(attrs)]))["output_tokens"]
    assert c.verdict == "wrong" and "unread" in c.detail


def test_estimated_tokens_on_a_stream_without_usage_are_wrong():
    sc = scenarios.get("openai/stream-no-usage")
    attrs = {"gen_ai.request.model": "gpt-5-mini", "gen_ai.usage.output_tokens": 15}
    c = by_id(grade(sc, scenarios.truth(sc), BASE, obs(), [span(attrs)]))["output_tokens"]
    assert c.verdict == "wrong" and "estimated" in c.detail


def test_zero_for_an_absent_count_is_fine():
    sc = scenarios.get("openai/stream-no-usage")
    attrs = {"gen_ai.request.model": "gpt-5-mini", "gen_ai.usage.output_tokens": 0}
    c = by_id(grade(sc, scenarios.truth(sc), BASE, obs(), [span(attrs)]))["output_tokens"]
    assert c.verdict == "n/a"


def test_normalized_finish_reason_is_accepted():
    sc = scenarios.get("anthropic/basic")
    t, attrs = honest(sc.id)
    attrs["gen_ai.response.finish_reasons"] = ["stop"]
    assert by_id(grade(sc, t, BASE, obs(), [span(attrs)]))["finish_reasons"].verdict == "pass"


def test_instrument_failure_is_inconclusive_not_a_verdict_on_the_library():
    sc = scenarios.get("openai/basic")
    checks = grade(sc, scenarios.truth(sc), BASE, {"instrument_error": "ImportError"}, [])
    assert cell_verdict(checks) == "inconclusive"


def test_fact_outside_openinference_conventions_is_not_graded():
    sc = scenarios.get("openai/basic")
    t = scenarios.truth(sc)
    attrs = {"llm.token_count.prompt": 1187, "llm.model_name": t.response_model}
    c = by_id(grade(sc, t, BASE, obs(), [span(attrs)]))
    assert c["response_id"].verdict == "n/a"
    assert c["finish_reasons"].verdict == "missing"


def test_with_block_variant_exists():
    sc = scenarios.get("anthropic/stream-early-exit-with")
    assert sc.with_block and sc.read_events == 2


def test_error_type_is_not_graded_on_openinference_spans():
    sc = scenarios.get("openai/rate-limited")
    attrs = {"llm.system": "openai", "llm.invocation_parameters": "{}"}
    c = by_id(grade(sc, scenarios.truth(sc), BASE, obs(), [span(attrs, status="ERROR")]))
    assert c["error.status"].verdict == "pass" and c["error.type"].verdict == "n/a"
