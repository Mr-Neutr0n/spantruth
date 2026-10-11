"""Requirement resolution, including `--with` overrides, without building an environment."""

from wiretruth import cli, subjects

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


def test_an_override_for_a_package_nobody_installs_is_refused(capsys):
    code = cli.main(["run", "--subject", "control-honest", "--with", PR_HEAD, "--out", "/dev/null"])
    assert code == 2
    assert "no selected subject installs" in capsys.readouterr().err
