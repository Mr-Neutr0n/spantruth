"""Subjects: one directory per library under `subjects/`, each with its own environment."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUBJECTS = REPO / "subjects"


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


def requirements(subject: Subject, latest: bool) -> list[str]:
    """Pinned requirements, or with the subject's own packages unpinned for `--latest`."""
    reqs = list(base()["packages"]) + list(subject.packages)
    if latest:
        reqs = [r.split("==")[0] if r.split("==")[0] in subject.track else r for r in reqs]
    return reqs


def environment(subject: Subject, cache: Path, latest: bool = False) -> tuple[Path, dict[str, str]]:
    """Build (or reuse) the subject's virtual environment. Return its python and versions."""
    reqs = requirements(subject, latest)
    python = base()["python"]
    key = hashlib.sha256(json.dumps([python, reqs, latest]).encode()).hexdigest()[:12]
    venv = cache / f"{subject.name}-{key}"
    py = venv / "bin" / "python"
    ready = venv / ".ready"
    if not ready.exists() or latest:
        subprocess.run(
            ["uv", "venv", "--quiet", "--clear", "--python", python, str(venv)], check=True
        )
        install = ["uv", "pip", "install", "--quiet", "--python", str(py)]
        subprocess.run([*install, *reqs], check=True)
        # Editable, so the driver in every cached environment is always the current source.
        subprocess.run([*install, "--no-deps", "-e", str(REPO)], check=True)
        ready.write_text("\n".join(reqs))
    freeze = subprocess.run(
        ["uv", "pip", "freeze", "--python", str(py)], check=True, capture_output=True, text=True
    ).stdout
    versions = dict(line.split("==", 1) for line in freeze.splitlines() if "==" in line)
    return py, versions
