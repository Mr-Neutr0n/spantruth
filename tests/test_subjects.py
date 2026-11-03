"""Requirement resolution, including `--with` overrides, without building an environment."""

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
