"""A fake provider endpoint that serves scenario fixtures.

The scenario is chosen by a path prefix, `/s/<scenario key>/...`, so no SDK header
pass-through is needed. Streams use HTTP/1.1 chunked encoding, so a dropped connection is a
truncated body to the client, exactly as on the real network, and not a clean end of stream.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import scenarios
from .model import Event, Scenario


def _sse(event: Event) -> bytes:
    data = event.data if isinstance(event.data, str) else json.dumps(event.data)
    head = f"event: {event.event}\n" if event.event else ""
    return f"{head}data: {data}\n\n".encode()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: MockServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        request = self.rfile.read(length)
        parts = self.path.split("/")
        if len(parts) < 3 or parts[1] != "s":
            self._json(404, {"error": {"message": f"no scenario in path {self.path}"}})
            return
        try:
            sc = scenarios.by_key(parts[2])
        except KeyError as exc:
            self._json(404, {"error": {"message": str(exc)}})
            return
        self.server.record(sc.id, self.path, request)
        if sc.response.body is not None:
            self._json(sc.response.status, sc.response.body)
        else:
            self._stream(sc)

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.send_header("x-request-id", "req_wiretruth")
        self.end_headers()
        self.wfile.write(payload)

    def _stream(self, sc: Scenario) -> None:
        self.send_response(sc.response.status)
        self.send_header("content-type", "text/event-stream")
        self.send_header("transfer-encoding", "chunked")
        self.send_header("x-request-id", "req_wiretruth")
        self.end_headers()
        events = sc.response.events or ()
        drop = sc.response.drop_after
        for index, event in enumerate(events):
            if drop is not None and index == drop:
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            chunk = _sse(event)
            self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


class MockServer(ThreadingHTTPServer):
    """Serve fixtures on 127.0.0.1. Use as a context manager."""

    daemon_threads = True

    def __init__(self, port: int = 0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.requests: list[tuple[str, str, bytes]] = []
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

    def base_url(self, sc: Scenario) -> str:
        return base_url(self.url, sc)

    def record(self, scenario_id: str, path: str, body: bytes) -> None:
        with self._lock:
            self.requests.append((scenario_id, path, body))

    def __enter__(self) -> MockServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
        self.server_close()


def base_url(server_url: str, sc: Scenario) -> str:
    """The `base_url` an SDK client needs for this scenario."""
    prefix = f"{server_url}/s/{sc.key}"
    return f"{prefix}/v1" if sc.provider == "openai" else prefix
