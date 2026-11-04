"""Known failures, so that a CI job fails on a change and not on a bug it already knows about.

An expectation file lists the checks that one subject fails, in the format of
`subjects/control-faulty/expected.toml`:

    "anthropic/stream" = { "output_tokens" = "wrong" }

A failing check is any check whose verdict is not `pass` or `n/a`, `inconclusive` included. A run
matches the file when its failing checks equal the file's, for every scenario that ran.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import scenarios
from .checks import FAILING
from .rules import RULES

# Every check ID the grader can emit. `harness` is the one check that is not about the subject.
CHECK_IDS = frozenset(RULES) | {"harness"}

Failing = dict[str, dict[str, str]]


class ExpectationError(ValueError):
    """An expectation file that cannot be read, or that names an unknown scenario or check."""


@dataclass(frozen=True, order=True)
class Difference:
    scenario: str
    check: str
    expected: str | None  # None: the check was expected to pass
    got: str | None  # None: the check passes now


def failing(subject_result: dict[str, Any]) -> Failing:
    """The failing checks of one subject's results, as {scenario: {check: verdict}}."""
    out: Failing = {}
    for sid, cell in subject_result["cells"].items():
        found = {c["id"]: c["verdict"] for c in cell["checks"] if c["verdict"] in FAILING}
        if found:
            out[sid] = found
    return out


def load(path: Path) -> Failing:
    """Read an expectation file. Raise ExpectationError for anything the runner would not emit."""
    try:
        data = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ExpectationError(f"{path}: {exc}") from None
    for sid, found in data.items():
        if sid not in scenarios.SCENARIOS:
            raise ExpectationError(f"{path}: unknown scenario {sid}; run `spantruth list`")
        if not isinstance(found, dict):
            raise ExpectationError(f"{path}: {sid} must map to a table of checks")
        for check, verdict in found.items():
            if check not in CHECK_IDS:
                raise ExpectationError(f"{path}: {sid}: unknown check {check}")
            if verdict not in FAILING:
                raise ExpectationError(
                    f"{path}: {sid}: {check}: verdict {verdict} is not a failing verdict "
                    f"({', '.join(FAILING)})"
                )
    return data


def dumps(known: Failing, header: str) -> str:
    """An expectation file: the header as comments, then one line per scenario, sorted."""
    lines = [f"# {line}" if line else "#" for line in header.splitlines()]
    for sid in sorted(known):
        pairs = ", ".join(
            f"{json.dumps(c)} = {json.dumps(v)}" for c, v in sorted(known[sid].items())
        )
        lines.append(f"{json.dumps(sid)} = {{ {pairs} }}")
    return "\n".join(lines) + "\n"


def compare(expected: Failing, got: Failing, ran: set[str]) -> list[Difference]:
    """Every check whose verdict differs from the file, in the scenarios that ran."""
    out = []
    for sid in sorted(ran):
        want, have = expected.get(sid, {}), got.get(sid, {})
        for check in sorted(set(want) | set(have)):
            if want.get(check) != have.get(check):
                out.append(Difference(sid, check, want.get(check), have.get(check)))
    return out


def describe(differences: list[Difference], skipped: list[str] | tuple[str, ...] = ()) -> str:
    """The differences as a Markdown list, which reads the same in a CI log and a job summary.

    `skipped` are the scenarios the file names that did not run, so they were not compared.
    """
    if not differences:
        lines = ["The failing checks match the expectation file."]
    else:
        lines = [f"{len(differences)} difference(s) from the expectation file:", ""]
        for d in differences:
            cell = f"`{d.scenario}` `{d.check}`"
            if d.expected is None:
                lines.append(f"- new failure: {cell}: {d.got}")
            elif d.got is None:
                lines.append(f"- now passes: {cell}: was {d.expected}")
            else:
                lines.append(f"- changed: {cell}: was {d.expected}, now {d.got}")
        lines += ["", "If the change is intended, record the new state with `--write-expect FILE`."]
    if skipped:
        lines += ["", f"In the file but not run, so not compared: {', '.join(skipped)}."]
    return "\n".join(lines)
