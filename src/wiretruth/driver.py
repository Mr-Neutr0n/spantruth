"""The process that runs inside a subject's virtual environment.

    python -m wiretruth.driver baseline --mock URL --out FILE SCENARIO...
    python -m wiretruth.driver instrumented --mock URL --otlp URL --subject DIR --out FILE SCENARIO

`baseline` runs scenarios with no instrumentation and records what the app saw.
`instrumented` runs one scenario, in a fresh process, with the subject attached, inside a parent
span, and records the same observations plus the parent span's ids and timing.
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from . import calls, scenarios
from .mockserver import base_url

HANG_SECONDS = 20


def _exception_name(exc: BaseException) -> str:
    return f"{type(exc).__module__.split('.')[0]}.{type(exc).__name__}"


def observe(scenario_id: str, mock: str) -> dict[str, Any]:
    sc = scenarios.get(scenario_id)
    seen = calls.Seen()
    start = time.time_ns()
    exception = None
    try:
        calls.run(sc, base_url(mock, sc), seen)
    except Exception as exc:  # the observation IS which exception the app received
        exception = _exception_name(exc)
    return {
        "scenario": scenario_id,
        "exception": exception,
        "seen": seen.as_dict(),
        "start_ns": start,
        "end_ns": time.time_ns(),
    }


def _write(path: str, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))


def _watchdog(out: str, scenario_id: str) -> threading.Timer:
    def fire() -> None:
        _write(out, {"scenario": scenario_id, "hang": True})
        sys.stdout.flush()
        os._exit(3)

    timer = threading.Timer(HANG_SECONDS, fire)
    timer.daemon = True
    timer.start()
    return timer


def _load_subject(directory: str):
    path = Path(directory) / "instrument.py"
    spec = importlib.util.spec_from_file_location("wiretruth_subject", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_probe() -> dict[str, dict[str, Any]]:
    """Record every SDK span's start and end in this process, whichever provider made it.

    A span that never ends is never exported, so the receiver alone cannot tell a span that
    never ended from one that was never started. The probe can.
    """
    from opentelemetry.sdk import trace as sdk_trace

    spans: dict[str, dict[str, Any]] = {}
    start, end = sdk_trace.Span.start, sdk_trace.Span.end

    def probed_start(self, *args, **kwargs):
        start(self, *args, **kwargs)
        sid = format(self.get_span_context().span_id, "016x")
        spans[sid] = {"name": self.name, "start_ns": time.time_ns(), "end_ns": None}

    def probed_end(self, *args, **kwargs):
        sid = format(self.get_span_context().span_id, "016x")
        if sid in spans and spans[sid]["end_ns"] is None:
            spans[sid]["end_ns"] = time.time_ns()
        end(self, *args, **kwargs)

    sdk_trace.Span.start, sdk_trace.Span.end = probed_start, probed_end
    return spans


def _flush_all(providers: list[Any]) -> None:
    seen: set[int] = set()
    for p in providers:
        if p is not None and id(p) not in seen and hasattr(p, "force_flush"):
            seen.add(id(p))
            p.force_flush()


def instrumented(scenario_id: str, mock: str, otlp: str, subject: str, out: str) -> int:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    probe = _install_probe()
    provider = TracerProvider(resource=Resource.create({"service.name": "wiretruth"}))
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(f"{otlp}/v1/traces")))
    result: dict[str, Any] = {"scenario": scenario_id, "hang": False}
    try:
        # The subject owns the global provider: some libraries set it themselves, and the
        # OpenTelemetry API refuses a second set without an error.
        extra = _load_subject(subject).instrument(tracer_provider=provider, otlp_endpoint=otlp)
    except Exception:
        result["instrument_error"] = traceback.format_exc(limit=5)
        _write(out, result)
        return 2
    current = trace.get_tracer_provider()
    if not isinstance(current, TracerProvider):
        trace.set_tracer_provider(provider)
        current = provider
    timer = _watchdog(out, scenario_id)
    with current.get_tracer("wiretruth.driver").start_as_current_span("wiretruth.scenario") as p:
        ctx = p.get_span_context()
        result |= observe(scenario_id, mock)
        result["parent"] = {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    timer.cancel()
    gc.collect()
    result["probe"] = {sid: dict(rec) for sid, rec in probe.items()}
    _flush_all([provider, current, *(extra or [])])
    _write(out, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiretruth.driver")
    parser.add_argument("mode", choices=["baseline", "instrumented"])
    parser.add_argument("scenarios", nargs="+")
    parser.add_argument("--mock", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--otlp")
    parser.add_argument("--subject")
    args = parser.parse_args(argv)
    if args.mode == "baseline":
        _write(args.out, {sid: observe(sid, args.mock) for sid in args.scenarios})
        return 0
    if len(args.scenarios) != 1 or not (args.otlp and args.subject):
        parser.error("instrumented mode takes one scenario, --otlp and --subject")
    return instrumented(args.scenarios[0], args.mock, args.otlp, args.subject, args.out)


if __name__ == "__main__":
    sys.exit(main())
