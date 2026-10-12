"""A recorded body replays as recorded: kartsan03/wiretruth's fixture format, vendored verbatim."""

import json

import openai.types.responses
import pydantic
import pytest

from spantruth import recorded, scenarios
from spantruth.model import Event

RESPONSES_EVENT = pydantic.TypeAdapter(openai.types.responses.ResponseStreamEvent)
ABORT = recorded.FIXTURES / "openai-responses" / "stream.missing-finish-abort.json"


def test_an_aborted_stream_drops_after_its_last_recorded_event():
    r = recorded.load(ABORT)
    assert len(r.events) == 8 and r.drop_after == 8 and r.status == 200
    assert r.events[0].event == "response.created"
    assert [e.event for e in r.events].count("response.output_text.delta") == 4


def test_every_recorded_event_parses_with_the_sdk_type():
    for e in recorded.load(ABORT).events:
        assert RESPONSES_EVENT.validate_python(json.loads(e.data)).type == e.event


def test_the_vendored_fixture_keeps_its_provenance_and_licence():
    doc = json.loads(ABORT.read_text())
    assert doc["derived_from"]["fixture"] == "openai-responses/truncation.text-stream"
    assert "MIT License" in (ABORT.parent / "NOTICE.md").read_text()


def test_a_clean_end_is_not_a_drop(tmp_path):
    doc = json.loads(ABORT.read_text())
    doc["exchanges"][0]["response"]["end"] = "complete"
    path = tmp_path / "f.json"
    path.write_text(json.dumps(doc))
    assert recorded.load(path).drop_after is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(format="wiretruth.fixture/v2"), "format"),
        (lambda d: d["exchanges"].append(d["exchanges"][0]), "one exchange"),
        (lambda d: d["exchanges"][0]["response"].update(end="half"), "end"),
    ],
)
def test_an_unknown_fixture_is_refused(tmp_path, mutate, message):
    doc = json.loads(ABORT.read_text())
    mutate(doc)
    path = tmp_path / "f.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match=message):
        recorded.load(path)


def test_an_sse_frame_splits_into_event_and_data():
    assert recorded.frame('event: x.y\ndata: {"a":1}') == Event(data='{"a":1}', event="x.y")


def test_the_responses_scenario_is_a_dropped_connection():
    sc = scenarios.get("openai/responses-stream-missing-finish-abort")
    assert sc.api == "responses" and sc.stream
    t = scenarios.truth(sc)
    assert t.error == "connection dropped" and t.output_tokens is None
