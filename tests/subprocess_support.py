"""Repository-local environment helpers for subprocess-based tests."""

from __future__ import annotations

import os
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _REPOSITORY_ROOT / "src"


def repository_subprocess_environment() -> dict[str, str]:
    """Return an environment that imports IX-Sally from this source tree first."""
    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    search_paths = [str(_SOURCE_ROOT)]
    if existing_pythonpath:
        search_paths.append(existing_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(search_paths)
    return environment
