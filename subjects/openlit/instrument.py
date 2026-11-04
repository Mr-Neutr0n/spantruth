"""The documented setup: openlit.init() with an existing global tracer provider."""

from pathlib import Path

PRICING = Path(__file__).resolve().parent / "pricing.json"


def instrument(tracer_provider, otlp_endpoint):
    import openlit
    from opentelemetry import trace

    # OpenLIT reuses a global SDK tracer provider if one is set, so register it first.
    trace.set_tracer_provider(tracer_provider)
    # Pass a local pricing file so openlit does not attempt an outbound request to GitHub.
    openlit.init(pricing_json=str(PRICING))
