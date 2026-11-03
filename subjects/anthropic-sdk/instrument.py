"""The documented setup: register a tracer provider, and the SDK creates its spans with it.

Nothing to install. The driver registers the caller-supplied provider globally when the subject
does not, and the SDK reads the global provider when a client is created.
"""


def instrument(tracer_provider, otlp_endpoint):
    return None
