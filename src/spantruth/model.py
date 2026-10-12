"""The data model: what the fake provider sends, and the truth that implies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    """One server-sent event. `event` is None for providers that send data lines only."""

    data: dict | str
    event: str | None = None


@dataclass(frozen=True)
class Response:
    """What the mock server answers.

    Exactly one of `body` (a JSON document) and `events` (an SSE stream) is set.
    `drop_after` closes the connection after that many events, without ending the stream.
    """

    status: int = 200
    body: dict | None = None
    events: tuple[Event, ...] | None = None
    drop_after: int | None = None

    def __post_init__(self) -> None:
        if (self.body is None) == (self.events is None):
            raise ValueError("a Response needs exactly one of body and events")
        if self.drop_after is not None and self.events is None:
            raise ValueError("drop_after needs an event stream")

    def reaches_drop(self, read_events: int | None) -> bool:
        """True when the app reads up to the point where the connection drops."""
        return self.drop_after is not None and (
            read_events is None or read_events > self.drop_after
        )

    def consumed(self, read_events: int | None) -> tuple[Event, ...]:
        """The events an app receives when it stops reading after `read_events`."""
        stream = self.events or ()
        limits = [n for n in (read_events, self.drop_after) if n is not None]
        return stream[: min(limits)] if limits else stream


@dataclass(frozen=True)
class Truth:
    """What a correct instrumentation reports for one call.

    None means the wire carries no value for that fact, so the fact is not graded.
    Token totals follow the OpenTelemetry GenAI rules: input tokens include cached tokens,
    output tokens include reasoning tokens.
    """

    request_model: str
    response_model: str | None = None
    response_id: str | None = None
    finish_reasons: tuple[str, ...] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None
    # Why the call failed, as the app experienced it: "HTTP 429", "connection dropped", ...
    error: str | None = None
    # Token counts that only the unread part of a stream carries. Reporting one proves the
    # instrumentation read past the point where the app closed the stream.
    unread_counts: tuple[int, ...] = ()
    # The wire carries no usage at all, so any token count is an estimate.
    no_usage: bool = False


@dataclass(frozen=True)
class Scenario:
    """One call pattern against one fixture.

    `read_events` makes the app stop reading after that many stream events and close the stream.
    `with_block` makes the app read the stream inside a `with` block and leave it, instead of
    calling `close()`.
    `stream_usage` False leaves out OpenAI's `include_usage`, so the stream carries no usage.
    """

    id: str
    provider: str
    title: str
    request_model: str
    response: Response
    stream: bool = False
    read_events: int | None = None
    with_block: bool = False
    tools: bool = False
    stream_usage: bool = True
    asynchronous: bool = False
    catches: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        """The path-safe form of the id, used in the mock server URL."""
        return self.id.replace("/", "--")

    @property
    def expects_error(self) -> bool:
        return (
            self.response.status >= 400
            or self.response.drop_after is not None
            or any(
                isinstance(e.data, dict) and e.data.get("type") == "error"
                for e in self.response.events or ()
            )
        )
