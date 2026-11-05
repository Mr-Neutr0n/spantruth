"""Known failures: recorded, compared with a run, and turned into an exit code for CI."""

import pytest

from spantruth import checks, cli, expectations, runner, scenarios
from spantruth.subjects import SUBJECTS

FAULTY = SUBJECTS / "control-faulty" / "expected.toml"


def subject(**cells):
    """A subject's results, with each cell given as {check: verdict}."""
    return {
        "cells": {
            sid.replace("__", "/"): {
                "verdict": "",
                "checks": [{"id": c, "verdict": v} for c, v in found.items()],
            }
            for sid, found in cells.items()
        }
    }


def test_failing_keeps_every_verdict_but_pass_and_na():
    result = subject(
        openai__basic={"input_tokens": "pass", "response_id": "n/a", "output_tokens": "wrong"},
        openai__stream={"subject.instrument": "inconclusive"},
        openai__tool_call={"finish_reasons": "pass"},
    )
    assert expectations.failing(result) == {
        "openai/basic": {"output_tokens": "wrong"},
        "openai/stream": {"subject.instrument": "inconclusive"},
    }


def test_an_expectation_file_round_trips(tmp_path):
    failing = {
        "anthropic/stream": {"output_tokens": "wrong", "span.ended": "lost"},
        "openai/basic": {"input_tokens": "missing"},
    }
    path = tmp_path / "expected.toml"
    path.write_text(expectations.dumps(failing, header="Known failures of my-lib."))
    assert expectations.load(path) == failing
    assert path.read_text().startswith("# Known failures of my-lib.\n")


def test_the_faulty_control_file_is_an_expectation_file():
    assert expectations.load(FAULTY)["openai/stream-no-usage"] == {"output_tokens": "wrong"}


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('"openai/nope" = { "output_tokens" = "wrong" }\n', "unknown scenario openai/nope"),
        ('"openai/basic" = { "output_tokns" = "wrong" }\n', "unknown check output_tokns"),
        ('"openai/basic" = { "output_tokens" = "pass" }\n', "verdict pass is not a failing"),
        ('"openai/basic" = "wrong"\n', "a table of checks"),
        ('"openai/basic" = {\n', "expected.toml"),
    ],
)
def test_a_bad_expectation_file_is_refused(tmp_path, content, message):
    path = tmp_path / "expected.toml"
    path.write_text(content)
    with pytest.raises(expectations.ExpectationError, match=message):
        expectations.load(path)


def test_compare_names_each_new_fixed_and_changed_check():
    expected = {"openai/basic": {"output_tokens": "wrong"}, "openai/stream": {"span.ended": "lost"}}
    got = {
        "openai/basic": {"output_tokens": "missing"},
        "openai/reasoning": {"error.type": "wrong"},
    }
    ran = {"openai/basic", "openai/stream", "openai/reasoning"}
    assert expectations.compare(expected, got, ran) == [
        expectations.Difference("openai/basic", "output_tokens", "wrong", "missing"),
        expectations.Difference("openai/reasoning", "error.type", None, "wrong"),
        expectations.Difference("openai/stream", "span.ended", "lost", None),
    ]


def test_compare_ignores_a_scenario_that_did_not_run():
    expected = {"openai/stream": {"span.ended": "lost"}}
    assert expectations.compare(expected, {}, ran={"openai/basic"}) == []


def test_describe_says_how_to_record_an_intended_change():
    text = expectations.describe(
        [expectations.Difference("openai/basic", "output_tokens", None, "wrong")]
    )
    assert "new failure" in text and "openai/basic" in text and "--write-expect" in text
    assert "match" in expectations.describe([])


def test_every_check_the_grader_can_emit_is_known():
    emitted = {"app.unchanged", "span.ended", "span.recorded", "span.parented", "error.status"}
    emitted |= {
        "error.type",
        "status.unset",
        "tokens.single-report",
        "harness",
        "subject.instrument",
    }
    assert emitted | set(checks.VALUES) <= expectations.CHECK_IDS


def test_an_instrument_error_is_a_failing_check_and_not_a_gap_in_the_run():
    sc = scenarios.get("openai/basic")
    graded = checks.grade(sc, scenarios.truth(sc), {}, {"instrument_error": "ImportError"}, [])
    assert [(c.id, c.verdict) for c in graded] == [("subject.instrument", "inconclusive")]
    doc = {"subjects": {"lib": subject(openai__basic={"subject.instrument": "inconclusive"})}}
    assert runner.incomplete(doc) == []


def test_exit_code_three_wins_over_a_difference():
    gap = {"subjects": {"lib": subject(openai__basic={"harness": "inconclusive"})}}
    broken_env = {"subjects": {"lib": {"error": "environment build failed", "cells": {}}}}
    fine = {"subjects": {"lib": subject(openai__basic={"input_tokens": "pass"})}}
    difference = [expectations.Difference("openai/basic", "input_tokens", None, "wrong")]
    assert cli.exit_code(gap, difference) == 3
    assert cli.exit_code(broken_env, []) == 3
    assert cli.exit_code(fine, difference) == 1
    assert cli.exit_code(fine, []) == 0


def test_an_early_exit_scenario_brings_the_full_stream_it_depends_on():
    assert scenarios.with_dependencies(["openai/stream-early-exit-with"]) == [
        "openai/stream-early-exit-with",
        "openai/stream",
    ]
    assert scenarios.with_dependencies(["anthropic/async-stream-early-exit"]) == [
        "anthropic/async-stream-early-exit",
        "anthropic/async-stream",
    ]
    assert scenarios.with_dependencies(["openai/basic", "openai/basic"]) == ["openai/basic"]


def test_expect_takes_exactly_one_subject(tmp_path, capsys):
    path = tmp_path / "expected.toml"
    path.write_text("")
    args = ["run", "--subject", "control-honest", "--subject", "control-faulty"]
    assert cli.main([*args, "--expect", str(path)]) == 2
    assert "exactly one --subject" in capsys.readouterr().err


def test_a_bad_expectation_file_stops_the_run_before_it_starts(tmp_path, capsys):
    path = tmp_path / "expected.toml"
    path.write_text('"openai/nope" = { "output_tokens" = "wrong" }\n')
    assert cli.main(["run", "--subject", "control-faulty", "--expect", str(path)]) == 2
    assert "unknown scenario openai/nope" in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(600)
def test_the_exit_code_follows_the_expectation_file(tmp_path):
    """The mechanism the controls use is the one a maintainer's CI uses."""
    cache, empty = str(tmp_path / "venvs"), tmp_path / "empty.toml"
    empty.write_text("")
    base = ["run", "--subject", "control-faulty", "--scenario", "openai/stream-no-usage"]
    base += ["--cache", cache, "--out", str(tmp_path / "results.json")]
    written, summary = tmp_path / "written.toml", tmp_path / "summary.md"
    assert cli.main([*base, "--expect", str(FAULTY), "--write-expect", str(written)]) == 0
    assert expectations.load(written) == {"openai/stream-no-usage": {"output_tokens": "wrong"}}
    assert cli.main([*base, "--expect", str(empty), "--summary", str(summary)]) == 1
    assert "new failure" in summary.read_text() and "openai/stream-no-usage" in summary.read_text()


def test_expect_needs_a_scenario_that_applies_to_the_subject(tmp_path, capsys):
    path = tmp_path / "expected.toml"
    path.write_text("")
    args = ["run", "--subject", "anthropic-sdk", "--scenario", "openai/basic"]
    assert cli.main([*args, "--expect", str(path)]) == 2
    assert "no selected scenario applies to anthropic-sdk" in capsys.readouterr().err


def test_describe_is_a_markdown_list_and_names_what_did_not_run():
    text = expectations.describe(
        [expectations.Difference("openai/basic", "output_tokens", None, "wrong")],
        skipped=["anthropic/stream"],
    )
    assert "\n- new failure: `openai/basic` `output_tokens`: wrong" in text
    assert "anthropic/stream" in text and "not compared" in text


def test_an_unexpected_error_is_exit_code_3(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(runner, "run", boom)
    assert cli.main(["run", "--subject", "control-honest", "--scenario", "openai/basic"]) == 3
    assert "FileNotFoundError" in capsys.readouterr().err


def _incomplete_doc(*args, **kwargs):
    return {
        "spantruth": "x",
        "mode": "pinned",
        "created": "now",
        "scenarios": {},
        "subjects": {
            "control-faulty": {
                "title": "t",
                "homepage": "https://example.com",
                "kind": "control",
                "error": "environment build failed",
                "cells": {},
            }
        },
    }


def test_an_incomplete_run_is_not_compared_and_writes_no_expectations(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "run", _incomplete_doc)
    written, summary = tmp_path / "w.toml", tmp_path / "summary.md"
    args = ["run", "--subject", "control-faulty", "--out", str(tmp_path / "r.json")]
    args += ["--expect", str(FAULTY), "--write-expect", str(written), "--summary", str(summary)]
    assert cli.main(args) == 3
    assert not written.exists()
    assert "not compared" in summary.read_text()
