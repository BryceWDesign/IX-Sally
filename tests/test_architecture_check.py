"""Tests for the IX-Sally runtime architecture boundary gate."""

from __future__ import annotations

from pathlib import Path

import architecture_check
from dependency_check import DependencyGraph, ModuleDependency


def test_repository_runtime_architecture_respects_boundaries() -> None:
    """The current IX-Sally runtime must satisfy every directional rule."""
    repository_root = Path(architecture_check.__file__).resolve().parent
    graph = architecture_check.build_dependency_graph(
        source_root=repository_root / "src",
    )

    assert architecture_check.architecture_violations(graph) == ()


def test_architecture_rejects_foundation_dependency() -> None:
    """Foundation modules must not depend on higher runtime layers."""
    graph = DependencyGraph(
        modules=("ix_sally.foundation", "ix_sally.state"),
        dependencies=(
            ModuleDependency(
                source="ix_sally.foundation",
                target="ix_sally.state",
                line=7,
            ),
        ),
    )

    assert architecture_check.architecture_violations(graph) == (
        architecture_check.ArchitectureViolation(
            rule="foundation-boundary",
            source="ix_sally.foundation",
            target="ix_sally.state",
            line=7,
        ),
    )


def test_architecture_rejects_status_runtime_dependency() -> None:
    """Status boundary modules must remain dependency-neutral."""
    graph = DependencyGraph(
        modules=(
            "ix_sally.human_review_reentry_status",
            "ix_sally.foundation",
        ),
        dependencies=(
            ModuleDependency(
                source="ix_sally.human_review_reentry_status",
                target="ix_sally.foundation",
                line=4,
            ),
        ),
    )

    assert architecture_check.architecture_violations(graph) == (
        architecture_check.ArchitectureViolation(
            rule="status-boundary",
            source="ix_sally.human_review_reentry_status",
            target="ix_sally.foundation",
            line=4,
        ),
    )


def test_architecture_quarantines_human_review_subsystem() -> None:
    """General runtime modules must not acquire human-review dependencies."""
    graph = DependencyGraph(
        modules=("ix_sally.state", "ix_sally.human_review_workflow"),
        dependencies=(
            ModuleDependency(
                source="ix_sally.state",
                target="ix_sally.human_review_workflow",
                line=11,
            ),
        ),
    )

    assert architecture_check.architecture_violations(graph) == (
        architecture_check.ArchitectureViolation(
            rule="human-review-quarantine",
            source="ix_sally.state",
            target="ix_sally.human_review_workflow",
            line=11,
        ),
    )


def test_architecture_check_main_reports_repository_summary(
    capsys: object,
) -> None:
    """The command entry point must report a successful architecture summary."""
    assert architecture_check.main() == 0

    output = capsys.readouterr().out
    assert "IX-Sally runtime architecture passed:" in output
    assert "0 boundary violations" in output
