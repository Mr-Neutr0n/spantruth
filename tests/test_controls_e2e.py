"""The falsification of the whole suite: both controls, end to end, in real subprocesses.

control-honest has to pass every check. control-faulty has to fail exactly the checks in its
expected.toml, compared by the same code that compares a maintainer's expectation file. A harness
change that breaks either is a harness bug, whatever it looks like.
"""

import pytest

from spantruth import expectations, runner, scenarios, subjects
from spantruth.subjects import SUBJECTS

pytestmark = [pytest.mark.slow, pytest.mark.external, pytest.mark.timeout(900)]


@pytest.fixture(scope="module")
def doc(tmp_path_factory):
    cache = tmp_path_factory.mktemp("venvs")
    controls = [subjects.load("control-honest"), subjects.load("control-faulty")]
    return runner.run(controls, list(scenarios.SCENARIOS), cache)


def test_the_run_is_complete(doc):
    assert runner.incomplete(doc) == []
    assert doc["schema"] == 1


def test_honest_control_passes_every_scenario(doc):
    result = doc["subjects"]["control-honest"]
    assert set(result["cells"]) == set(scenarios.SCENARIOS)
    assert expectations.failing(result) == {}


def test_faulty_control_fails_exactly_its_planted_faults(doc):
    result = doc["subjects"]["control-faulty"]
    expected = expectations.load(SUBJECTS / "control-faulty" / "expected.toml")
    got = expectations.failing(result)
    assert expectations.compare(expected, got, ran=set(result["cells"])) == []
    assert got == expected
