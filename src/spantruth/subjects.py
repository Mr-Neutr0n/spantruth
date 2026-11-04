"""Subjects: one directory per library, each with its own environment.

The built-in subjects are the directories in `subjects/`. A subject can also live anywhere, for
example in the repository of the library it tests, and be named by its path.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import paths, scenarios

SUBJECTS = paths.data("subjects")
# Part of the environment cache key. Raise it when the content of an environment changes, so no
# environment built the old way is reused. 2: the driver comes from PYTHONPATH, not an install.
LAYOUT = 2


REQUIRED = ("title", "homepage", "providers")


class SubjectError(ValueError):
    """A subject that cannot be loaded, or a `--with` value that cannot be resolved."""


@dataclass(frozen=True)
class Subject:
    name: str
    title: str
    homepage: str
    providers: tuple[str, ...]
    packages: tuple[str, ...]
    directory: Path
    track: tuple[str, ...] = ()
    kind: str = "library"
    env: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    # How the subject was named: a built-in name, or the path that was given.
    ref: str = ""


def base() -> dict:
    return tomllib.loads((SUBJECTS / "_base.toml").read_text())


def is_path(ref: str) -> bool:
    """A reference with a slash, or `.` or `..`, is a directory. Anything else is a name."""
    return "/" in ref or ref in (".", "..")


def load(ref: str) -> Subject:
    """A built-in subject by name, or the subject in a directory, named after the directory."""
    directory = Path(ref).expanduser().resolve() if is_path(ref) else SUBJECTS / ref
    config = directory / "subject.toml"
    if not config.is_file():
        hint = "" if is_path(ref) else "; run `spantruth list` for the built-in subjects"
        raise SubjectError(f"no subject {ref!r}: {config} does not exist{hint}")
    try:
        data = tomllib.loads(config.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise SubjectError(f"{config}: {exc}") from None
    missing = [key for key in REQUIRED if key not in data]
    if missing:
        raise SubjectError(f"{config}: missing {', '.join(missing)}")
    known = {sc.provider for sc in scenarios.SCENARIOS.values()}
    unknown = sorted(set(data["providers"]) - known)
    if unknown:
        raise SubjectError(
            f"{config}: unknown provider {', '.join(unknown)}; known: {', '.join(sorted(known))}"
        )
    if not (directory / "instrument.py").is_file():
        raise SubjectError(f"{directory}: no instrument.py")
    if not str(data["homepage"]).startswith(("https://", "http://")):
        raise SubjectError(f"{config}: homepage must be an http or https address")
    kind = data.get("kind", "library")
    if kind == "control" and directory.parent != SUBJECTS:
        raise SubjectError(f'{config}: kind = "control" is reserved for the built-in controls')
    return Subject(
        name=directory.name,
        directory=directory,
        title=data["title"],
        homepage=data["homepage"],
        providers=tuple(data["providers"]),
        packages=tuple(data.get("packages", ())),
        track=tuple(data.get("track", ())),
        kind=kind,
        env=dict(data.get("env", {})),
        notes=data.get("notes", ""),
        ref=ref if is_path(ref) else directory.name,
    )


def all_names() -> list[str]:
    return sorted(p.parent.name for p in SUBJECTS.glob("*/subject.toml"))


def resolve_override(spec: str) -> str:
    """A `--with` value as a requirement. A local checkout becomes `<name> @ file:///abs/path`.

    A value is a checkout when it is a directory and has a slash or starts with a dot, the rule
    pip uses, so a bare package name never turns into a path by accident.
    """
    path = Path(spec).expanduser()
    if not (("/" in spec or spec.startswith(".")) and path.is_dir()):
        return spec
    pyproject = path / "pyproject.toml"
    try:
        meta = tomllib.loads(pyproject.read_text()) if pyproject.is_file() else {}
    except tomllib.TOMLDecodeError as exc:
        raise SubjectError(f"--with {spec}: {pyproject}: {exc}") from None
    name = meta.get("project", {}).get("name") or meta.get("tool", {}).get("poetry", {}).get("name")
    if not name:
        raise SubjectError(
            f"--with {spec}: {pyproject} names no package ([project].name or [tool.poetry].name)"
        )
    return f"{name} @ {path.resolve().as_uri()}"


def package_name(spec: str) -> str:
    """The normalized distribution name a requirement installs: `Foo_Bar @ git+...` is foo-bar."""
    name = re.split(r"[\s<>=!~@\[;]", spec.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements(subject: Subject, latest: bool, overrides: tuple[str, ...] = ()) -> list[str]:
    """Pinned requirements, or with the tracked packages unpinned for `--latest`.

    A subject package replaces the base package of the same name, for a library that cannot run
    the base SDK versions. `--latest` unpins the subject's `track` list and the base `track` list
    (the SDKs). An override replaces the requirement for the same package, for example with a pull
    request's head: `pkg @ git+https://github.com/org/repo@refs/pull/1/head#subdirectory=pkg`.
    """
    common = base()
    own = {package_name(p) for p in subject.packages}
    reqs = [r for r in common["packages"] if package_name(r) not in own] + list(subject.packages)
    if latest:
        track = {package_name(t) for t in (*common.get("track", ()), *subject.track)}
        reqs = [package_name(r) if package_name(r) in track else r for r in reqs]
    by_name = {package_name(o): o for o in overrides}
    return [by_name.get(package_name(r), r) for r in reqs]


def _uv(args: list[str], cache: Path, **kwargs) -> subprocess.CompletedProcess:
    """Run uv without the caller's configuration files, from a directory inside the cache.

    A maintainer's `uv.toml` or `[tool.uv]` (another index, constraints) must not change what a
    subject environment contains.
    """
    return subprocess.run(["uv", *args, "--no-config"], cwd=cache, check=True, text=True, **kwargs)


def _build(venv: Path, python: str, reqs: list[str], cache: Path) -> None:
    _uv(["venv", "--quiet", "--clear", "--python", python, str(venv)], cache)
    _uv(["pip", "install", "--quiet", "--python", str(venv / "bin" / "python"), *reqs], cache)


def environment(
    subject: Subject, cache: Path, latest: bool = False, overrides: tuple[str, ...] = ()
) -> tuple[Path, dict[str, str]]:
    """Build (or reuse) the subject's virtual environment. Return its python and versions."""
    reqs = requirements(subject, latest, overrides)
    overridden = reqs != requirements(subject, latest)
    python = base()["python"]
    key = hashlib.sha256(json.dumps([LAYOUT, python, reqs, latest]).encode()).hexdigest()[:12]
    cache.mkdir(parents=True, exist_ok=True)
    venv = cache / f"{subject.name}-{key}"
    py = venv / "bin" / "python"
    ready = venv / ".ready"
    # A git ref such as a pull request head moves, so an override is always reinstalled.
    if not ready.exists() or latest or overridden:
        try:
            _build(venv, python, reqs, cache)
        except subprocess.CalledProcessError:
            # Once more: a maintainer's CI must not fail on one PyPI hiccup.
            _build(venv, python, reqs, cache)
        ready.write_text("\n".join(reqs))
    freeze = _uv(["pip", "freeze", "--python", str(py)], cache, capture_output=True).stdout
    versions = {}
    for line in freeze.splitlines():
        # `name==1.2.3`, or `name @ git+https://...@<sha>` for an override from a git ref.
        sep = "==" if "==" in line else " @ " if " @ " in line else None
        if sep:
            name, version = line.split(sep, 1)
            versions[name] = version
    return py, versions
