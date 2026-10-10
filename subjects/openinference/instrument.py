"""The documented setup: each instrumentor with a caller-supplied tracer provider."""


def instrument(tracer_provider, otlp_endpoint):
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
