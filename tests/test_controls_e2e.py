"""The falsification of the whole suite: both controls, end to end, in real subprocesses.

control-honest has to pass every check. control-faulty has to fail exactly the checks in its
expected.toml. A harness change that breaks either is a harness bug, whatever it looks like.
"""

import tomllib

import pytest

from wiretruth import runner, scenarios
from wiretruth.subjects import SUBJECTS

pytestmark = [pytest.mark.slow, pytest.mark.external, pytest.mark.timeout(900)]


@pytest.fixture(scope="module")
def doc(tmp_path_factory):
    cache = tmp_path_factory.mktemp("venvs")
    return runner.run(["control-honest", "control-faulty"], list(scenarios.SCENARIOS), cache)


def failing(cell):
    return {c["id"]: c["verdict"] for c in cell["checks"] if c["verdict"] not in ("pass", "n/a")}


def test_honest_control_passes_every_scenario(doc):
    cells = doc["subjects"]["control-honest"]["cells"]
    assert set(cells) == set(scenarios.SCENARIOS)
    bad = {sid: failing(cell) for sid, cell in cells.items() if failing(cell)}
    assert bad == {}


def test_faulty_control_fails_exactly_its_planted_faults(doc):
    expected = tomllib.loads((SUBJECTS / "control-faulty" / "expected.toml").read_text())
    cells = doc["subjects"]["control-faulty"]["cells"]
    got = {sid: failing(cell) for sid, cell in cells.items() if failing(cell)}
    assert got == expected
