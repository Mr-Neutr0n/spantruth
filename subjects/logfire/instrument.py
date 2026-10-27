"""The documented no-account setup.

Logfire installs the global tracer provider inside ``configure``. The driver
reads that provider afterwards for the parent span. The provider is returned
so its exporter is flushed.
"""


def instrument(tracer_provider, otlp_endpoint):
    import os

    import logfire
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    # configure() also exports wherever OTEL_EXPORTER_OTLP_ENDPOINT points, and
    # the harness sets that. Skip the automatic exporter so each span is sent once.
    os.environ["OTEL_TRACES_EXPORTER"] = "none"
    logfire.configure(
        send_to_logfire=False,
        additional_span_processors=[
            SimpleSpanProcessor(OTLPSpanExporter(f"{otlp_endpoint}/v1/traces")),
        ],
    )
    logfire.instrument_openai()
    logfire.instrument_anthropic()
    return [trace.get_tracer_provider()]
