"""The GitHub Action, run outside GitHub with the variables a runner sets."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((REPO / "action.yml").read_text())


def step(step_id: str) -> dict:
    (found,) = [s for s in ACTION["runs"]["steps"] if s.get("id") == step_id]
    return found


def test_inputs_reach_the_script_only_through_the_environment():
    script = step("run")["run"]
    assert "${{" not in script
    assert set(step("run")["env"]) >= {"SUBJECT", "WITH", "SCENARIO", "EXPECT", "LATEST"}


def test_every_action_the_action_uses_is_pinned_to_a_commit():
    for s in ACTION["runs"]["steps"]:
        if "uses" in s:
            ref = s["uses"].split("@", 1)[1]
            assert len(ref) == 40 and int(ref, 16) >= 0, s["uses"]


def run_action(tmp_path: Path, runner_temp: Path, **inputs: str) -> tuple[int, dict[str, str], str]:
    """Run the action's script as a runner would. Return its status, outputs and step summary.

    Every step of a job shares one RUNNER_TEMP, so two runs in one job must not collide there.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    runner_temp.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "run.sh"
    script.write_text(step("run")["run"])
    output, summary = tmp_path / "output", tmp_path / "summary.md"
    output.touch()
    summary.touch()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_ACTION_PATH": str(REPO),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
        **{k.upper(): v for k, v in inputs.items()},
    }
    for name in ("SUBJECT", "WITH", "SCENARIO", "EXPECT", "LATEST", "ARTIFACT_NAME"):
        env.setdefault(name, "")
    proc = subprocess.run(["bash", str(script)], env=env, cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    return int(outputs["exit-code"]), outputs, summary.read_text()


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(600)
def test_the_action_compares_with_an_expectation_file(tmp_path):
    empty = tmp_path / "empty.toml"
    empty.write_text("")
    common = {
        "subject": "control-faulty",
        "scenario": "openai/stream-no-usage\n\nanthropic/basic\n",
    }
    runner_temp = tmp_path / "runner"
    code, outputs, summary = run_action(
        tmp_path / "a", runner_temp, expect="subjects/control-faulty/expected.toml", **common
    )
    assert code == 0, summary
    assert outputs["artifact-name"] == "spantruth-control-faulty"
    assert Path(outputs["results"]).is_file()
    assert (Path(outputs["results"]).parent / "report.html").is_file()
    code, _, summary = run_action(
        tmp_path / "b", runner_temp, expect=str(empty), artifact_name="x", **common
    )
    assert code == 1
    assert "new failure" in summary and "openai/stream-no-usage" in summary


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_a_failed_install_still_reports_exit_code_3(tmp_path):
    script = tmp_path / "run.sh"
    script.write_text(step("run")["run"])
    output = tmp_path / "output"
    output.touch()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_ACTION_PATH": str(tmp_path / "no-such-checkout"),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "SUBJECT": "control-honest",
        "WITH": "",
        "SCENARIO": "",
        "EXPECT": "",
        "LATEST": "",
        "ARTIFACT_NAME": "",
    }
    proc = subprocess.run(["bash", str(script)], env=env, cwd=REPO, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "exit-code=3" in output.read_text()
