"""A minimal OTLP/HTTP receiver that keeps what it receives as plain records.

Only the exact paths `/v1/traces`, `/v1/logs` and `/v1/metrics` are kept. Any other POST is
answered 200 and dropped, so a library that also exports to its own backend path cannot deliver a
span twice.
"""

from __future__ import annotations

import gzip
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.common.v1.common_pb2 import AnyValue

STATUS = {0: "UNSET", 1: "OK", 2: "ERROR"}


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str
    name: str
    kind: int
    start_ns: int
    end_ns: int
    status: str
    status_message: str
    attributes: dict[str, Any]
    resource: dict[str, Any]
    scope: str
    events: tuple[str, ...]


def value(v: AnyValue) -> Any:
    kind = v.WhichOneof("value")
    if kind is None:
        return None
    if kind == "array_value":
        return [value(x) for x in v.array_value.values]
    if kind == "kvlist_value":
        return {kv.key: value(kv.value) for kv in v.kvlist_value.values}
    return getattr(v, kind)


def _attrs(kvs) -> dict[str, Any]:
    return {kv.key: value(kv.value) for kv in kvs}


def decode_traces(payload: bytes) -> list[SpanRecord]:
    req = trace_service_pb2.ExportTraceServiceRequest.FromString(payload)
    out = []
    for rs in req.resource_spans:
        resource = _attrs(rs.resource.attributes)
        for ss in rs.scope_spans:
            for s in ss.spans:
                out.append(
                    SpanRecord(
                        trace_id=s.trace_id.hex(),
                        span_id=s.span_id.hex(),
                        parent_span_id=s.parent_span_id.hex(),
                        name=s.name,
                        kind=s.kind,
                        start_ns=s.start_time_unix_nano,
                        end_ns=s.end_time_unix_nano,
                        status=STATUS.get(s.status.code, str(s.status.code)),
                        status_message=s.status.message,
                        attributes=_attrs(s.attributes),
                        resource=resource,
                        scope=ss.scope.name,
                        events=tuple(e.name for e in s.events),
                    )
                )
    return out


def _decode_count(kind: str, payload: bytes) -> int:
    """Logs and metrics are counted in v0.1, not graded."""
    if kind == "logs":
        req = logs_service_pb2.ExportLogsServiceRequest.FromString(payload)
        return sum(len(s.log_records) for r in req.resource_logs for s in r.scope_logs)
    req = metrics_service_pb2.ExportMetricsServiceRequest.FromString(payload)
    return sum(len(s.metrics) for r in req.resource_metrics for s in r.scope_metrics)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: Receiver

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        payload = self.rfile.read(int(self.headers.get("content-length") or 0))
        if self.headers.get("content-encoding") == "gzip":
            payload = gzip.decompress(payload)
        kind = {"/v1/traces": "traces", "/v1/logs": "logs", "/v1/metrics": "metrics"}.get(self.path)
        try:
            if kind == "traces":
                self.server.add_spans(decode_traces(payload))
            elif kind is not None:
                self.server.add_count(kind, _decode_count(kind, payload))
        except DecodeError as exc:
            self.server.add_error(f"{self.path}: {exc}")
            self.send_response(400)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("content-type", "application/x-protobuf")
        self.send_header("content-length", "0")
        self.end_headers()


class Receiver(ThreadingHTTPServer):
    """Collect OTLP on 127.0.0.1. Use as a context manager."""

    daemon_threads = True

    def __init__(self, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.spans: list[SpanRecord] = []
        self.counts = {"logs": 0, "metrics": 0}
        self.errors: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    def handle_error(self, request, client_address) -> None:
        # A client that closes its connection early is a scenario, not a server fault.
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def add_spans(self, spans: list[SpanRecord]) -> None:
        with self._lock:
            self.spans.extend(spans)

    def add_count(self, kind: str, n: int) -> None:
        with self._lock:
            self.counts[kind] += n

    def add_error(self, message: str) -> None:
        with self._lock:
            self.errors.append(message)

    def __enter__(self) -> Receiver:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
        self.server_close()
