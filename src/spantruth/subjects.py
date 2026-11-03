"""Subjects: one directory per library under `subjects/`, each with its own environment."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

SUBJECTS = paths.data("subjects")
# Part of the environment cache key. Raise it when the content of an environment changes, so no
# environment built the old way is reused. 2: the driver comes from PYTHONPATH, not an install.
LAYOUT = 2


@dataclass(frozen=True)
class Subject:
    name: str
    title: str
    homepage: str
    providers: tuple[str, ...]
    packages: tuple[str, ...]
    track: tuple[str, ...] = ()
    kind: str = "library"
    env: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    @property
    def directory(self) -> Path:
        return SUBJECTS / self.name


def base() -> dict:
    return tomllib.loads((SUBJECTS / "_base.toml").read_text())


def load(name: str) -> Subject:
    data = tomllib.loads((SUBJECTS / name / "subject.toml").read_text())
    return Subject(
        name=name,
        title=data["title"],
        homepage=data["homepage"],
        providers=tuple(data["providers"]),
        packages=tuple(data.get("packages", ())),
        track=tuple(data.get("track", ())),
        kind=data.get("kind", "library"),
        env=dict(data.get("env", {})),
        notes=data.get("notes", ""),
    )


def all_names() -> list[str]:
    return sorted(p.parent.name for p in SUBJECTS.glob("*/subject.toml"))


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
