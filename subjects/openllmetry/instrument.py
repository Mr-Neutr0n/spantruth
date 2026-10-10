"""The documented setup: each instrumentor with a caller-supplied tracer provider."""


def instrument(tracer_provider, otlp_endpoint):
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
