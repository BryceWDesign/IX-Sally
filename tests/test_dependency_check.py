"""Tests for the IX-Sally runtime dependency graph gate."""

from __future__ import annotations

from pathlib import Path

import dependency_check


def test_repository_runtime_dependency_graph_is_acyclic() -> None:
    """The current IX-Sally runtime graph must remain cycle-free."""
    repository_root = Path(dependency_check.__file__).resolve().parent

    graph = dependency_check.build_dependency_graph(
        source_root=repository_root / "src",
    )

    assert graph.modules
    assert graph.dependencies
    assert graph.cycles() == ()


def test_dependency_graph_detects_multi_module_cycle() -> None:
    """Strongly connected internal imports must be reported as one cycle."""
    graph = dependency_check.DependencyGraph(
        modules=("ix_sally.alpha", "ix_sally.beta", "ix_sally.gamma"),
        dependencies=(
            dependency_check.ModuleDependency(
                source="ix_sally.alpha",
                target="ix_sally.beta",
                line=3,
            ),
            dependency_check.ModuleDependency(
                source="ix_sally.beta",
                target="ix_sally.gamma",
                line=4,
            ),
            dependency_check.ModuleDependency(
                source="ix_sally.gamma",
                target="ix_sally.alpha",
                line=5,
            ),
        ),
    )

    assert graph.cycles() == (
        ("ix_sally.alpha", "ix_sally.beta", "ix_sally.gamma"),
    )


def test_dependency_graph_ignores_type_checking_imports(
    tmp_path: Path,
) -> None:
    """Static-only type imports must not become runtime dependency edges."""
    package_root = tmp_path / "ix_sally"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "alpha.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from ix_sally.beta import Beta\n",
        encoding="utf-8",
    )
    (package_root / "beta.py").write_text(
        "from ix_sally.alpha import Alpha\n",
        encoding="utf-8",
    )

    graph = dependency_check.build_dependency_graph(source_root=tmp_path)

    assert graph.dependencies == (
        dependency_check.ModuleDependency(
            source="ix_sally.beta",
            target="ix_sally.alpha",
            line=1,
        ),
    )
    assert graph.cycles() == ()


def test_dependency_check_main_reports_repository_summary(
    capsys: object,
) -> None:
    """The command entry point must report a successful graph summary."""
    assert dependency_check.main() == 0

    output = capsys.readouterr().out
    assert "IX-Sally runtime dependency graph passed:" in output
    assert "0 cycles" in output
