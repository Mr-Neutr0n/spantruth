"""The reference instrumentation, as written."""

from wiretruth import reference


def instrument(tracer_provider, otlp_endpoint):
    reference.instrument(tracer_provider)
