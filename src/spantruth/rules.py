"""The rule each check applies, with a permalink to the sentence that states it."""

from __future__ import annotations

GENAI = (
    "https://github.com/open-telemetry/semantic-conventions-genai/blob/"
    "6fd0d763a092db245a54104fc1124031eb3c51d2"
)
RECORDING_ERRORS = (
    "https://github.com/open-telemetry/semantic-conventions/blob/v1.44.0/"
    "docs/general/recording-errors.md"
)

RULES: dict[str, tuple[str, str]] = {
    "app.unchanged": (
        "spantruth rule: instrumentation does not change what the application receives: the same "
        "return values, the same chunks, the same exceptions, and no hang.",
        "",
    ),
    "span.ended": (
        "GenAI spans SHOULD end when the response is fully received or the operation is "
        "terminated due to an error or cancellation.",
        f"{GENAI}/docs/gen-ai/gen-ai-spans.md#L29-L31",
    ),
    "span.recorded": (
        "spantruth rule: a call the application made produces at least one span.",
        "",
    ),
    "span.parented": (
        "The span belongs to the trace that was active when the application made the call.",
        "https://opentelemetry.io/docs/specs/otel/trace/api/#context-interaction",
    ),
    "error.status": (
        "Span status SHOULD follow Recording Errors: an operation that ended in an error "
        "sets the status to Error.",
        RECORDING_ERRORS,
    ),
    "error.type": (
        "`error.type` is conditionally required if the operation ended in an error. Any "
        "low-cardinality identifier is allowed, so only its presence is graded.",
        f"{GENAI}/model/gen-ai/spans.yaml#L3-L12",
    ),
    "request_model": (
        "The model name the request asked for.",
        f"{GENAI}/model/gen-ai/registry.yaml#L98",
    ),
    "response_model": (
        "The name of the model that generated the response.",
        f"{GENAI}/model/gen-ai/registry.yaml#L205",
    ),
    "response_id": (
        "The unique identifier of the completion.",
        f"{GENAI}/model/gen-ai/registry.yaml#L200",
    ),
    "finish_reasons": (
        "One finish reason per choice, as received. A normalized value is accepted too.",
        f"{GENAI}/model/gen-ai/registry.yaml#L210-L221",
    ),
    "input_tokens": (
        "Input tokens SHOULD include all types of input tokens, including cached tokens. For "
        "Anthropic, whose `input_tokens` excludes them, cache reads and cache writes MUST be "
        "added. OpenInference states the same rule for `llm.token_count.prompt`.",
        f"{GENAI}/model/gen-ai/spans.yaml#L842-L866",
    ),
    "output_tokens": (
        "Output tokens, with reasoning tokens included.",
        f"{GENAI}/model/gen-ai/registry.yaml#L336",
    ),
    "cache_read_tokens": (
        "Input tokens read from the provider cache.",
        f"{GENAI}/model/gen-ai/registry.yaml#L301",
    ),
    "cache_write_tokens": (
        "Input tokens written to the provider cache.",
        f"{GENAI}/model/gen-ai/registry.yaml#L308",
    ),
    "reasoning_tokens": (
        "Output tokens used for reasoning.",
        f"{GENAI}/model/gen-ai/registry.yaml#L346",
    ),
    "tokens.single-report": (
        "spantruth rule: one call reports its token usage on one span. Usage on two spans of one "
        "call is counted twice by any backend that sums token attributes across spans.",
        "",
    ),
}
