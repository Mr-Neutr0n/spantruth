"""The reference instrumentation with every known fault switched on."""

from spantruth import reference

FAULTS = {"anthropic-raw-input", "close-leaks-span", "errors-as-success", "estimate-tokens"}


def instrument(tracer_provider, otlp_endpoint):
    reference.instrument(tracer_provider, faults=FAULTS)
