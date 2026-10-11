"""The Markdown and HTML renderers, on a small hand-built results document."""

from wiretruth import report

HOSTILE = "<script>alert(1)</script>"


def doc():
    check = {
        "id": "output_tokens",
        "verdict": "wrong",
        "expected": 419,
        "got": 420,
        "where": "gen_ai.usage.output_tokens",
        "detail": HOSTILE,
        "rule": "r",
        "rule_url": "https://example.com/rule",
    }
    return {
        "wiretruth": "0.1.0",
        "mode": "pinned",
        "created": "2026-10-10T00:00:00+00:00",
        "python": "3.12",
        "semconv_genai": "6fd0d763",
        "scenarios": {
            "anthropic/stream": {"title": "Stream", "catches": "", "provider": "anthropic"}
        },
        "subjects": {
            "lib": {
                "title": HOSTILE,
                "homepage": "https://example.com",
                "kind": "library",
                "versions": {"lib": "1.0"},
                "cells": {"anthropic/stream": {"verdict": "wrong", "checks": [check]}},
            },
            "control-honest": {
                "title": "c",
                "homepage": "https://example.com",
                "kind": "control",
                "cells": {"anthropic/stream": {"verdict": "pass", "checks": []}},
            },
        },
    }


def test_known_issue_is_linked_from_its_finding():
    known = [
        {
            "subject": "lib",
            "scenarios": ["anthropic/stream"],
            "check": "output_tokens",
            "status": "reported",
            "url": "https://example.com/issues/1",
            "note": "",
        }
    ]
    (f,) = report.findings(doc(), known)
    assert f["issue"]["url"] == "https://example.com/issues/1"
    assert report.findings(doc(), [])[0]["issue"] is None


def test_markdown_lists_libraries_before_controls_and_shows_the_finding():
    md = report.markdown(doc())
    assert "| Scenario | lib | control-honest |" in md
    assert "| lib | `anthropic/stream` | output_tokens | wrong | `419` | `420` |" in md


def test_html_escapes_every_value_from_the_results():
    page = report.html(doc())
    assert HOSTILE not in page
    assert "&lt;script&gt;" in page
    assert 'href="https://example.com/rule"' in page


def test_html_has_no_scripts_and_no_external_assets():
    page = report.html(doc())
    assert "<script" not in page.replace("&lt;script", "")
    assert "src=" not in page


def test_badges_count_graded_cells_and_skip_controls():
    d = doc()
    d["subjects"]["lib"]["cells"]["openai/basic"] = {"verdict": "pass", "checks": []}
    d["subjects"]["lib"]["cells"]["openai/stream"] = {"verdict": "inconclusive", "checks": []}
    badges = report.badges(d)
    assert set(badges) == {"lib"}
    assert badges["lib"] == {
        "schemaVersion": 1,
        "label": "wiretruth",
        "message": "1/2 pass",
        "color": "orange",
    }
    d["subjects"]["lib"]["cells"]["anthropic/stream"]["verdict"] = "pass"
    assert report.badges(d)["lib"]["color"] == "brightgreen"
