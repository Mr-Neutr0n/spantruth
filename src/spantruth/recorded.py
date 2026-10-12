"""Replay a recorded provider response, in kartsan03/wiretruth's fixture format.

The scenarios in `scenarios.py` build their responses in code. A recorded fixture is the other
source: a real provider stream, kept byte for byte, with the provenance of where it came from.
Only what replay needs is read: one exchange, its status, its SSE frames, and how it ended.
Format: https://github.com/kartsan03/wiretruth/blob/main/docs/formats.md
"""

from __future__ import annotations

import json
from pathlib import Path

from .model import Event, Response

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FORMAT = "wiretruth.fixture/v1"


def frame(raw: str) -> Event:
    """One recorded SSE frame, `event: <name>\\ndata: <json>`, as an Event."""
    name, data = None, []
    for line in raw.splitlines():
        if line.startswith("event:"):
            name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:") :].lstrip())
    return Event(data="\n".join(data), event=name)


def load(path: Path) -> Response:
    """The response of a recorded fixture. An `abort` end drops the connection after the end."""
    doc = json.loads(Path(path).read_text())
    if doc.get("format") != FORMAT:
        raise ValueError(f"{path}: format {doc.get('format')!r}, expected {FORMAT!r}")
    if len(doc["exchanges"]) != 1:
        raise ValueError(f"{path}: replay needs exactly one exchange")
    response = doc["exchanges"][0]["response"]
    events = tuple(frame(raw) for raw in response["body"]["sse"])
    end = response.get("end", "complete")
    if end not in ("complete", "abort"):
        raise ValueError(f"{path}: unknown end {end!r}")
    return Response(
        status=response["status"],
        events=events,
        drop_after=len(events) if end == "abort" else None,
    )


def requested_model(path: Path) -> str:
    return json.loads(Path(path).read_text())["provenance"]["requested_model"]
