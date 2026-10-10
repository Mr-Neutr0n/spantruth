"""Render a results document as Markdown or as one static HTML page."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

KNOWN = Path(__file__).resolve().parents[2] / "known_issues.toml"

MARK = {
    "pass": "✅ pass",
    "missing": "🟡 missing",
    "wrong": "❌ wrong",
    "lost": "🕳️ lost",
    "broken": "💥 broken",
    "inconclusive": "❔ inconclusive",
    "n/a": "·",
}
LEGEND = {
    "pass": "every graded value matches the wire",
    "missing": "the span ended without a value the wire carried",
    "wrong": "a reported value does not match the wire",
    "lost": "the span never ended, so no backend ever receives it",
    "broken": "the application saw something different from an uninstrumented run",
    "inconclusive": "the harness could not run the cell; no verdict on the library",
}


def _subjects(doc: dict) -> list[str]:
    # Libraries first, controls last, each group in name order. No ranking.
    return sorted(doc["subjects"], key=lambda n: (doc["subjects"][n]["kind"] == "control", n))


def known_issues(path: Path = KNOWN) -> list[dict[str, Any]]:
    return tomllib.loads(path.read_text()).get("issue", []) if path.exists() else []


def findings(doc: dict, known: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every check that did not pass, with the upstream issue that tracks it, if any."""
    known = known_issues() if known is None else known
    out = []
    for name in _subjects(doc):
        for sid, cell in doc["subjects"][name]["cells"].items():
            for c in cell["checks"]:
                if c["verdict"] in ("pass", "n/a"):
                    continue
                issue = next(
                    (
                        k
                        for k in known
                        if k["subject"] == name and sid in k["scenarios"] and k["check"] == c["id"]
                    ),
                    None,
                )
                out.append({"subject": name, "scenario": sid, **c, "issue": issue})
    return out


def _link(issue: dict | None) -> str:
    return f"[{issue['status']}]({issue['url']})" if issue else "—"


def _fmt(value: Any) -> str:
    return "—" if value is None else f"`{value}`"


def markdown(doc: dict) -> str:
    names = _subjects(doc)
    lines = [
        f"wiretruth {doc['wiretruth']}, {doc['mode']} versions, {doc['created']}",
        "",
        "| Scenario | " + " | ".join(names) + " |",
        "| --- | " + " | ".join("---" for _ in names) + " |",
    ]
    for sid in doc["scenarios"]:
        row = [
            MARK.get(doc["subjects"][n]["cells"].get(sid, {}).get("verdict", "n/a"), "?")
            for n in names
        ]
        lines.append(f"| `{sid}` | " + " | ".join(row) + " |")
    lines += ["", *(f"- {MARK[k]}: {v}" for k, v in LEGEND.items())]
    found = findings(doc)
    if found:
        lines += [
            "",
            "| Subject | Scenario | Check | Verdict | Expected | Reported | Read from | Note "
            "| Upstream |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for f in found:
            lines.append(
                f"| {f['subject']} | `{f['scenario']}` | {f['id']} | {f['verdict']} | "
                f"{_fmt(f['expected'])} | {_fmt(f['got'])} | {_fmt(f['where'])} | "
                f"{f['detail'].replace('|', '/')[:160]} | "
                f"{_link(f['issue'])} |"
            )
    errors = {n: s["error"] for n, s in doc["subjects"].items() if s.get("error")}
    lines += [f"\n{n}: {e}" for n, e in errors.items()]
    return "\n".join(lines)


def html(doc: dict) -> str:
    from .site import render

    return render(doc)
