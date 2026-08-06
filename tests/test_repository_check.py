"""Tests for the IX-Sally cross-platform repository integrity gate."""

from __future__ import annotations

from pathlib import Path

import repository_check


def _minimal_repository(root: Path) -> None:
    """Create the required minimal repository structure for focused tests."""
    (root / "src" / "ix_sally").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "LICENSE").write_text(
        "license\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[build-system]\n",
        encoding="utf-8",
    )
    (root / "src" / "ix_sally" / "__init__.py").write_text(
        '"""Package."""\n',
        encoding="utf-8",
    )
    (root / "src" / "ix_sally" / "py.typed").write_text(
        "",
        encoding="utf-8",
    )
    (root / "tests" / "__init__.py").write_text(
        '"""Tests."""\n',
        encoding="utf-8",
    )


def test_repository_integrity_passes_for_current_checkout() -> None:
    """The current repository must satisfy every cross-platform invariant."""
    repository_root = Path(repository_check.__file__).resolve().parent

    assert (
        repository_check.repository_violations(
            repository_root=repository_root,
        )
        == ()
    )


def test_repository_integrity_detects_case_collision(
    tmp_path: Path,
) -> None:
    """Paths differing only by case must be rejected for Windows safety."""
    _minimal_repository(tmp_path)
    paths = (
        tmp_path / "tests" / "sample.py",
        tmp_path / "tests" / "Sample.py",
    )

    violations = repository_check._case_collision_violations(
        repository_root=tmp_path,
        paths=paths,
    )

    assert any(violation.rule == "case-collision" for violation in violations)


def test_repository_integrity_detects_invalid_module_case(
    tmp_path: Path,
) -> None:
    """Mixed-case Python module names must be rejected cross-platform."""
    _minimal_repository(tmp_path)
    module = tmp_path / "tests" / "Sample.py"
    module.write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    violations = repository_check.repository_violations(
        repository_root=tmp_path,
    )

    assert any(violation.rule == "python-module-name" for violation in violations)


def test_repository_integrity_detects_missing_package_marker(
    tmp_path: Path,
) -> None:
    """Nested source packages must include explicit package markers."""
    _minimal_repository(tmp_path)
    nested = tmp_path / "src" / "ix_sally" / "nested"
    nested.mkdir()
    (nested / "module.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    violations = repository_check.repository_violations(
        repository_root=tmp_path,
    )

    assert (
        repository_check.RepositoryViolation(
            rule="package-marker",
            path="src/ix_sally/nested",
            detail="Python package directory is missing __init__.py",
        )
        in violations
    )


def test_repository_integrity_detects_invalid_python_source(
    tmp_path: Path,
) -> None:
    """Python files that cannot be parsed must fail before runtime tests."""
    _minimal_repository(tmp_path)
    invalid = tmp_path / "src" / "ix_sally" / "invalid.py"
    invalid.write_text(
        "def broken(:\n",
        encoding="utf-8",
    )

    violations = repository_check.repository_violations(
        repository_root=tmp_path,
    )

    assert any(
        violation.rule == "python-syntax" and violation.path == "src/ix_sally/invalid.py"
        for violation in violations
    )


def test_repository_integrity_detects_windows_reserved_name(
    tmp_path: Path,
) -> None:
    """Windows-reserved path components must be rejected explicitly."""
    _minimal_repository(tmp_path)
    reserved = tmp_path / "tests" / "con.py"
    reserved.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    violations = repository_check.repository_violations(
        repository_root=tmp_path,
    )

    assert (
        repository_check.RepositoryViolation(
            rule="windows-reserved-name",
            path="tests/con.py",
            detail="component 'con.py' is reserved on Windows",
        )
        in violations
    )


def test_repository_check_main_reports_summary(
    capsys: object,
) -> None:
    """The command entry point must report a successful integrity summary."""
    assert repository_check.main() == 0

    output = capsys.readouterr().out
    assert "IX-Sally repository integrity passed:" in output
    assert "0 violations" in output
