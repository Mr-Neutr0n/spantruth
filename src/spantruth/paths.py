"""Where the data files are: next to the package in a wheel, at the repository root in a clone.

The subjects and `known_issues.toml` live at the repository root, where contributors find them.
The wheel maps both into the package (`force-include` in pyproject.toml), so an installed
spantruth needs no clone.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def data(name: str, package: Path = PACKAGE) -> Path:
    """The path of a shipped data file or directory, in a wheel or in a clone."""
    packaged = package / name
    return packaged if packaged.exists() else package.parents[1] / name


def cache_dir(env: Mapping[str, str] = os.environ) -> Path:
    """Where runs keep environments and results, outside any checkout the caller works in."""
    base = env.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "spantruth"
