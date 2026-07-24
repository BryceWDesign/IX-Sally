"""Tests for the installed-wheel package smoke gate."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import package_smoke


def test_isolated_environment_removes_python_path_overrides(
    monkeypatch: object,
) -> None:
    """Installed-package checks must not inherit source-tree import overrides."""
    monkeypatch.setenv("PYTHONPATH", "source-tree")
    monkeypatch.setenv("PYTHONHOME", "custom-home")

    environment = package_smoke._isolated_environment()

    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment


def test_virtual_environment_paths_match_platform() -> None:
    """Smoke commands must use the platform's virtual-environment layout."""
    environment_root = Path("environment")

    if os.name == "nt":
        assert package_smoke._venv_python(environment_root) == (
            environment_root / "Scripts" / "python.exe"
        )
        assert package_smoke._venv_console_script(environment_root) == (
            environment_root / "Scripts" / "ix-sally.exe"
        )
    else:
        assert package_smoke._venv_python(environment_root) == (
            environment_root / "bin" / "python"
        )
        assert package_smoke._venv_console_script(environment_root) == (
            environment_root / "bin" / "ix-sally"
        )


def test_build_wheel_requires_exactly_one_artifact(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """The package gate must reject missing or ambiguous wheel output."""

    def fake_run(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(package_smoke, "_run", fake_run)

    with pytest.raises(
        RuntimeError,
        match="expected exactly one IX-Sally wheel",
    ):
        package_smoke._build_wheel(
            repository_root=tmp_path,
            wheel_directory=tmp_path,
        )
