"""Tests for the repository-owned IX-Sally quality-gate runner."""

from __future__ import annotations

from pathlib import Path

import check_green


def test_quality_gate_commands_match_ci_tools() -> None:
    """The shared runner must retain every declared repository gate."""
    commands = {
        gate.name: gate.command()[1:] for gate in check_green.QUALITY_GATES
    }

    assert commands == {
        "format": ("-m", "ruff", "format", "--check", "."),
        "lint": ("-m", "ruff", "check", "."),
        "type-check": ("-m", "mypy", "src", "tests"),
        "dependencies": ("-m", "dependency_check"),
        "test": ("-m", "pytest"),
        "package": ("-m", "package_smoke"),
    }


def test_main_runs_all_gates_in_declared_order(monkeypatch: object) -> None:
    """Running without selectors must execute the complete gate sequence."""
    observed: list[str] = []

    def fake_run_gate(
        gate: check_green.QualityGate,
        *,
        repository_root: Path,
    ) -> int:
        assert repository_root == Path(check_green.__file__).resolve().parent
        observed.append(gate.name)
        return 0

    monkeypatch.setattr(check_green, "_run_gate", fake_run_gate)

    assert check_green.main([]) == 0
    assert observed == [
        "format",
        "lint",
        "type-check",
        "dependencies",
        "test",
        "package",
    ]


def test_main_runs_only_requested_gates(monkeypatch: object) -> None:
    """Repeated gate selectors must preserve their requested order."""
    observed: list[str] = []

    def fake_run_gate(
        gate: check_green.QualityGate,
        *,
        repository_root: Path,
    ) -> int:
        del repository_root
        observed.append(gate.name)
        return 0

    monkeypatch.setattr(check_green, "_run_gate", fake_run_gate)

    result = check_green.main(["--gate", "package", "--gate", "format"])

    assert result == 0
    assert observed == ["package", "format"]


def test_main_returns_failure_after_running_selected_gates(
    monkeypatch: object,
    capsys: object,
) -> None:
    """One failing gate must fail the runner without hiding later results."""
    observed: list[str] = []

    def fake_run_gate(
        gate: check_green.QualityGate,
        *,
        repository_root: Path,
    ) -> int:
        del repository_root
        observed.append(gate.name)
        return 1 if gate.name == "lint" else 0

    monkeypatch.setattr(check_green, "_run_gate", fake_run_gate)

    assert check_green.main([]) == 1
    assert observed == [
        "format",
        "lint",
        "type-check",
        "dependencies",
        "test",
        "package",
    ]
    assert "Failed quality gates: lint" in capsys.readouterr().err


def test_ci_workflow_delegates_each_gate_to_shared_runner() -> None:
    """GitHub CI must use the repository-owned gate definitions."""
    repository_root = Path(check_green.__file__).resolve().parent
    workflow = (
        repository_root / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    for gate_name in (
        "format",
        "lint",
        "type-check",
        "dependencies",
        "test",
        "package",
    ):
        assert f"python check_green.py --gate {gate_name}" in workflow
