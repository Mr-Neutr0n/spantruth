"""spantruth runs from a clone and from an installed wheel, with one source of subjects."""

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import spantruth
from spantruth import cli, paths, runner, subjects
from spantruth.mockserver import MockServer

REPO = Path(__file__).resolve().parents[1]


def test_data_resolves_to_the_repository_in_a_clone():
    assert paths.data("subjects") == REPO / "subjects"
    assert paths.data("known_issues.toml") == REPO / "known_issues.toml"


def test_data_prefers_the_copy_next_to_the_package(tmp_path):
    package = tmp_path / "site-packages" / "spantruth"
    (package / "subjects").mkdir(parents=True)
    assert paths.data("subjects", package=package) == package / "subjects"


def test_cache_is_in_the_user_cache_directory():
    assert paths.cache_dir({"XDG_CACHE_HOME": "/srv/cache"}) == Path("/srv/cache/spantruth")
    assert paths.cache_dir({}) == Path.home() / ".cache" / "spantruth"


def test_run_defaults_write_nothing_into_the_working_directory():
    args = cli.parser().parse_args(["run"])
    assert Path(args.out).is_relative_to(paths.cache_dir())
    assert Path(args.cache).is_relative_to(paths.cache_dir())


def test_list_names_where_the_subjects_come_from(capsys):
    assert cli.main(["list"]) == 0
    assert str(subjects.SUBJECTS) in capsys.readouterr().out


def test_the_version_has_one_source():
    from importlib.metadata import version

    assert version("spantruth") == spantruth.__version__


def test_an_environment_build_is_retried_once(tmp_path, monkeypatch):
    calls = []

    def flaky(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["uv", "venv"]:
            Path(next(a for a in cmd if a.startswith(str(tmp_path)))).mkdir(
                parents=True, exist_ok=True
            )
        if cmd[:3] == ["uv", "pip", "install"] and len(calls) < 3:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subjects.subprocess, "run", flaky)
    subjects.environment(subjects.load("control-honest"), tmp_path)
    installs = [c for c in calls if c[:3] == ["uv", "pip", "install"]]
    assert len(installs) == 2
    assert all("--no-config" in c for c in calls if c[0] == "uv")


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(600)
def test_the_callers_uv_configuration_does_not_reach_a_subject(tmp_path, monkeypatch):
    """A maintainer's uv.toml may point at another index. A subject environment ignores it."""
    caller = tmp_path / "repo"
    caller.mkdir()
    (caller / "uv.toml").write_text('index-url = "http://127.0.0.1:9/simple"\n')
    monkeypatch.chdir(caller)
    py, versions = subjects.environment(subjects.load("control-honest"), tmp_path / "venvs")
    assert py.is_file() and "openai" in versions


def test_driver_path_holds_only_spantruth(tmp_path):
    shim = runner.driver_path(tmp_path)
    assert [p.name for p in shim.iterdir()] == ["spantruth"]
    assert (shim / "spantruth" / "driver.py").is_file()


@pytest.mark.slow
def test_driver_ignores_a_spantruth_in_the_working_directory(tmp_path):
    """A maintainer's repository can hold anything. The driver must not import from it."""
    cwd = tmp_path / "cwd"
    (cwd / "spantruth").mkdir(parents=True)
    (cwd / "spantruth" / "__init__.py").write_text("raise ImportError('imported the cwd')")
    shim = runner.driver_path(tmp_path / "shim")
    out = tmp_path / "baseline.json"
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(shim)}
    with MockServer() as mock:
        proc = runner._driver(
            Path(sys.executable),
            ["baseline", "openai/basic", "--mock", mock.url, "--out", str(out)],
            env,
            cwd=cwd,
        )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["openai/basic"]["exception"] is None


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(600)
def test_wheel_runs_a_control_without_a_clone(tmp_path):
    """Build the sdist and the wheel, install the wheel, and run from an empty directory."""
    dist = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist), str(REPO)], check=True, capture_output=True
    )
    (wheel,) = dist.glob("spantruth-*.whl")
    names = zipfile.ZipFile(wheel).namelist()
    assert "spantruth/subjects/control-honest/subject.toml" in names
    assert "spantruth/known_issues.toml" in names
    assert {n.split("/")[0] for n in names} == {
        "spantruth",
        wheel.name.split("-py3")[0] + ".dist-info",
    }
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", "--quiet", "--python", "3.12", str(venv)], check=True)
    py = str(venv / "bin" / "python")
    subprocess.run(["uv", "pip", "install", "--quiet", "--python", py, str(wheel)], check=True)
    empty = tmp_path / "empty"
    empty.mkdir()
    cli = str(venv / "bin" / "spantruth")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    listed = subprocess.run([cli, "list"], cwd=empty, env=env, capture_output=True, text=True)
    assert listed.returncode == 0, listed.stderr
    assert "control-honest" in listed.stdout and "openai/basic" in listed.stdout

    out = tmp_path / "results.json"
    args = ["run", "--subject", "control-honest", "--scenario", "openai/basic"]
    args += ["--out", str(out), "--cache", str(tmp_path / "venvs")]
    run = subprocess.run([cli, *args], cwd=empty, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    cell = json.loads(out.read_text())["subjects"]["control-honest"]["cells"]["openai/basic"]
    assert cell["verdict"] == "pass", cell
    assert list(empty.iterdir()) == [], "a run writes nothing into the working directory"
