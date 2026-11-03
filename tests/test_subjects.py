"""Requirement resolution, including `--with` overrides, without building an environment."""

import pytest

from spantruth import cli, subjects

PR_HEAD = (
    "opentelemetry-instrumentation-anthropic @ git+https://github.com/traceloop/openllmetry"
    "@refs/pull/4377/head#subdirectory=packages/opentelemetry-instrumentation-anthropic"
)


def test_package_name_normalizes_every_requirement_form():
    assert subjects.package_name("openai==3.28.0") == "openai"
    assert subjects.package_name("Foo_Bar.baz>=1") == "foo-bar-baz"
    assert subjects.package_name("pkg[extra]==1") == "pkg"
    assert subjects.package_name(PR_HEAD) == "opentelemetry-instrumentation-anthropic"


def test_an_override_replaces_only_the_package_it_names():
    lib = subjects.load("openllmetry")
    pinned = subjects.requirements(lib, latest=False)
    got = subjects.requirements(lib, latest=False, overrides=(PR_HEAD,))
    assert PR_HEAD in got
    assert "opentelemetry-instrumentation-anthropic==0.62.4" not in got
    assert [r for r in got if r != PR_HEAD] == [
        r for r in pinned if not r.startswith("opentelemetry-instrumentation-anthropic")
    ]


def test_a_subject_package_replaces_the_base_package_of_the_same_name():
    lib = subjects.Subject(
        name="old-sdk",
        title="t",
        homepage="h",
        providers=("anthropic",),
        packages=("Anthropic==0.79.0", "lib==1.0"),
        directory=subjects.SUBJECTS / "old-sdk",
    )
    reqs = subjects.requirements(lib, latest=False)
    assert [r for r in reqs if subjects.package_name(r) == "anthropic"] == ["Anthropic==0.79.0"]
    assert "lib==1.0" in reqs


def test_sdk_tracing_is_off_unless_the_subject_grades_it():
    from pathlib import Path

    from spantruth import runner

    def env(name):
        return runner._env(subjects.load(name), "http://127.0.0.1:9", Path("/shim"))

    assert env("openllmetry")["ANTHROPIC_OPEN_TELEMETRY"] == "false"
    assert env("anthropic-sdk")["ANTHROPIC_OPEN_TELEMETRY"] == "true"


def test_latest_also_unpins_the_sdks():
    reqs = subjects.requirements(subjects.load("openllmetry"), latest=True)
    assert {"openai", "anthropic", "opentelemetry-instrumentation-openai"} <= set(reqs)
    assert any(r.startswith("opentelemetry-sdk==") for r in reqs)


def test_an_override_for_a_package_nobody_installs_is_refused(capsys):
    code = cli.main(["run", "--subject", "control-honest", "--with", PR_HEAD, "--out", "/dev/null"])
    assert code == 2
    assert "no selected subject installs" in capsys.readouterr().err


def _copy_subject(tmp_path, name="my-lib", source="control-honest", keep_kind=False):
    """A copy of a built-in subject in another directory, as a maintainer would keep it."""
    import shutil

    target = tmp_path / name
    shutil.copytree(subjects.SUBJECTS / source, target)
    config = target / "subject.toml"
    if not keep_kind:  # outside subjects/, a copy of a control is an ordinary subject
        lines = config.read_text().splitlines()
        config.write_text("\n".join(line for line in lines if not line.startswith("kind")) + "\n")
    return target


def test_a_subject_loads_from_a_directory(tmp_path):
    directory = _copy_subject(tmp_path)
    lib = subjects.load(str(directory))
    assert (lib.name, lib.directory) == ("my-lib", directory.resolve())
    assert subjects.load(f"{directory}/").name == "my-lib"


def test_dot_is_a_directory_not_a_name(tmp_path, monkeypatch):
    monkeypatch.chdir(_copy_subject(tmp_path))
    assert subjects.load(".").name == "my-lib"


def test_a_name_without_a_slash_is_a_built_in_subject():
    lib = subjects.load("openllmetry")
    assert lib.directory == subjects.SUBJECTS / "openllmetry"


def test_a_bad_subject_is_one_clear_error(tmp_path):
    import pytest

    with pytest.raises(subjects.SubjectError, match="does not exist"):
        subjects.load(str(tmp_path / "nope"))
    with pytest.raises(subjects.SubjectError, match="spantruth list"):
        subjects.load("no-such-subject")
    directory = _copy_subject(tmp_path)
    (directory / "subject.toml").write_text('homepage = "h"\nproviders = ["openai"]\n')
    with pytest.raises(subjects.SubjectError, match="missing title"):
        subjects.load(str(directory))
    (directory / "subject.toml").write_text('title = "t"\nhomepage = "h"\nproviders = ["opnai"]\n')
    with pytest.raises(subjects.SubjectError, match="unknown provider opnai"):
        subjects.load(str(directory))
    (directory / "subject.toml").write_text('title = "t"\nhomepage = "h"\nproviders = ["openai"]\n')
    (directory / "instrument.py").unlink()
    with pytest.raises(subjects.SubjectError, match=r"no instrument\.py"):
        subjects.load(str(directory))


def test_two_subjects_with_one_name_are_refused(tmp_path, capsys):
    twin = _copy_subject(tmp_path, name="control-honest")
    code = cli.main(["run", "--subject", "control-honest", "--subject", str(twin)])
    assert code == 2
    assert "two subjects named control-honest" in capsys.readouterr().err


def _checkout(tmp_path, pyproject):
    directory = tmp_path / "checkout"
    directory.mkdir()
    (directory / "pyproject.toml").write_text(pyproject)
    return directory


def test_a_local_checkout_becomes_a_direct_reference(tmp_path):
    directory = _checkout(tmp_path, '[project]\nname = "my-instrumentation"\n')
    spec = subjects.resolve_override(str(directory))
    assert spec == f"my-instrumentation @ {directory.resolve().as_uri()}"
    assert subjects.package_name(spec) == "my-instrumentation"


def test_a_poetry_checkout_is_named_by_its_poetry_table(tmp_path):
    directory = _checkout(
        tmp_path, '[tool.poetry]\nname = "opentelemetry-instrumentation-openai"\n'
    )
    assert subjects.resolve_override(str(directory)).startswith(
        "opentelemetry-instrumentation-openai @ file://"
    )


def test_a_checkout_without_a_name_is_refused(tmp_path):
    import pytest

    directory = _checkout(tmp_path, "[build-system]\n")
    with pytest.raises(subjects.SubjectError, match="names no package"):
        subjects.resolve_override(str(directory))


def test_a_requirement_is_left_as_it_is():
    assert subjects.resolve_override("openai==3.42.1") == "openai==3.42.1"
    assert subjects.resolve_override(PR_HEAD) == PR_HEAD


def test_the_cli_checks_a_local_checkout_by_its_package_name(tmp_path, capsys):
    directory = _checkout(tmp_path, '[project]\nname = "nobody-installs-this"\n')
    code = cli.main(["run", "--subject", "control-honest", "--with", str(directory)])
    assert code == 2
    assert "no selected subject installs nobody-installs-this" in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(300)
def test_a_local_checkout_is_rebuilt_after_an_edit(tmp_path):
    """uv caches the build of a local checkout by its pyproject.toml. An edit must still install."""
    import subprocess

    checkout = tmp_path / "checkout"
    (checkout / "src" / "probe_pkg").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(
        '[project]\nname = "probe-pkg"\nversion = "1.0"\n'
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/probe_pkg"]\n'
    )
    module = checkout / "src" / "probe_pkg" / "__init__.py"
    requirement = subjects.resolve_override(str(checkout))
    venv, cache = tmp_path / "venv", tmp_path / "cache"
    cache.mkdir()
    for value in ("first build", "edited source"):
        module.write_text(f"VALUE = {value!r}\n")
        subjects._build(venv, "3.12", [requirement], cache)
        probe = [str(venv / "bin" / "python"), "-c", "import probe_pkg; print(probe_pkg.VALUE)"]
        assert subprocess.run(probe, capture_output=True, text=True).stdout.strip() == value


@pytest.mark.slow
@pytest.mark.external
@pytest.mark.timeout(600)
def test_a_directory_subject_runs_end_to_end(tmp_path):
    from spantruth import runner

    lib = subjects.load(str(_copy_subject(tmp_path, name="maintainers-own")))
    doc = runner.run([lib], ["openai/basic"], tmp_path / "venvs")
    assert doc["subjects"]["maintainers-own"]["cells"]["openai/basic"]["verdict"] == "pass"


def test_a_homepage_must_be_a_web_address(tmp_path):
    directory = _copy_subject(tmp_path)
    (directory / "subject.toml").write_text(
        'title = "t"\nhomepage = "javascript:alert(1)"\nproviders = ["openai"]\n'
    )
    with pytest.raises(subjects.SubjectError, match="http or https"):
        subjects.load(str(directory))


def test_only_a_built_in_subject_can_be_a_control(tmp_path):
    directory = _copy_subject(tmp_path, keep_kind=True)
    with pytest.raises(subjects.SubjectError, match="reserved for the built-in controls"):
        subjects.load(str(directory))
    assert subjects.load("control-honest").kind == "control"


def test_a_checkout_with_a_broken_pyproject_is_a_usage_error(tmp_path):
    directory = _checkout(tmp_path, "[project\nname = ")
    with pytest.raises(subjects.SubjectError, match=r"pyproject\.toml"):
        subjects.resolve_override(str(directory))


def test_a_directory_subject_remembers_how_it_was_named(tmp_path):
    directory = _copy_subject(tmp_path, source="openllmetry")
    assert subjects.load(str(directory)).ref == str(directory)
    assert subjects.load("openllmetry").ref == "openllmetry"
