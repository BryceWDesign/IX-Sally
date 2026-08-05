"""Tests for the installed-wheel package smoke gate."""

from __future__ import annotations

import os
from pathlib import Path

import package_smoke
import pytest


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


def test_source_copy_excludes_generated_artifacts(tmp_path: Path) -> None:
    """Disposable builds must not copy generated or repository-local artifacts."""
    repository_root = tmp_path / "repository"
    source_root = tmp_path / "source"
    (repository_root / "src" / "ix_sally").mkdir(parents=True)
    (repository_root / "src" / "ix_sally" / "__init__.py").write_text(
        "__version__ = '0.1.0'\n",
        encoding="utf-8",
    )
    (repository_root / "pyproject.toml").write_text(
        "[build-system]\n",
        encoding="utf-8",
    )
    generated_entries = (
        repository_root / "build",
        repository_root / "dist",
        repository_root / ".pytest_cache",
        repository_root / "src" / "ix_sally.egg-info",
        repository_root / "src" / "ix_sally" / "__pycache__",
    )
    for entry in generated_entries:
        entry.mkdir(parents=True)
        (entry / "generated.txt").write_text("generated\n", encoding="utf-8")

    package_smoke._copy_source_tree(
        repository_root=repository_root,
        source_root=source_root,
    )

    assert (source_root / "pyproject.toml").is_file()
    assert (source_root / "src" / "ix_sally" / "__init__.py").is_file()
    assert not (source_root / "build").exists()
    assert not (source_root / "dist").exists()
    assert not (source_root / ".pytest_cache").exists()
    assert not (source_root / "src" / "ix_sally.egg-info").exists()
    assert not (source_root / "src" / "ix_sally" / "__pycache__").exists()


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
            source_root=tmp_path,
            wheel_directory=tmp_path / "dist",
        )
