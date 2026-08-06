"""Tests for IX-Sally package-version identity."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import package_smoke

import ix_sally
from ix_sally.session_baseline import (
    session_one_baseline_payload,
)
from ix_sally.version import __version__
from tests.subprocess_support import (
    repository_subprocess_environment,
)


def test_package_root_exports_canonical_version() -> None:
    """The package root must expose the canonical version object."""
    assert ix_sally.__version__ == __version__


def test_runtime_baseline_uses_canonical_version() -> None:
    """Runtime baseline identity must come from the version module."""
    assert session_one_baseline_payload()["version"] == __version__


def test_project_metadata_uses_dynamic_version_source() -> None:
    """Setuptools must derive wheel metadata from the version module."""
    repository_root = Path(__file__).resolve().parents[1]
    project_data = tomllib.loads((repository_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert project_data["project"]["dynamic"] == ["version"]
    assert project_data["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "ix_sally.version.__version__",
    }


def test_package_smoke_reads_canonical_source_version() -> None:
    """Installed-package verification must use the source version."""
    repository_root = Path(__file__).resolve().parents[1]

    assert package_smoke._source_version(repository_root=repository_root) == __version__


def test_version_module_is_dependency_neutral() -> None:
    """Reading package identity must not initialize cognitive runtime modules."""
    statement = """
import sys
from ix_sally.version import __version__

assert __version__ == '0.1.0'

forbidden = {
    'ix_sally.state',
    'ix_sally.runtime',
    'ix_sally.human_review_workflow',
}
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise SystemExit(f'eagerly loaded modules: {loaded}')
"""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            statement,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=repository_subprocess_environment(),
    )

    assert completed.returncode == 0, completed.stderr
