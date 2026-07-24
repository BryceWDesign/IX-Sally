"""Tests for the IX-Sally runtime dependency graph gate."""

from __future__ import annotations

from pathlib import Path

import dependency_check


def _create_package(path: Path) -> None:
    """Create one explicit Python package directory."""
    path.mkdir(
        parents=True,
        exist_ok=True,
    )
    (path / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )


def test_repository_runtime_dependency_graph_is_acyclic() -> None:
    """The current IX-Sally runtime graph must remain cycle-free."""
    repository_root = Path(
        dependency_check.__file__
    ).resolve().parent

    graph = dependency_check.build_dependency_graph(
        source_root=repository_root / "src",
    )

    assert graph.modules
    assert graph.dependencies
    assert graph.cycles() == ()


def test_dependency_graph_detects_multi_module_cycle() -> None:
    """Strongly connected internal imports must be reported as one cycle."""
    graph = dependency_check.DependencyGraph(
        modules=(
            "ix_sally.alpha",
            "ix_sally.beta",
            "ix_sally.gamma",
        ),
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
        (
            "ix_sally.alpha",
            "ix_sally.beta",
            "ix_sally.gamma",
        ),
    )


def test_dependency_graph_ignores_type_checking_imports(
    tmp_path: Path,
) -> None:
    """Static-only type imports must not become runtime dependency edges."""
    package_root = tmp_path / "ix_sally"
    package_root.mkdir()
    (package_root / "__init__.py").write_text(
        "",
        encoding="utf-8",
    )
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

    graph = dependency_check.build_dependency_graph(
        source_root=tmp_path,
    )

    assert graph.dependencies == (
        dependency_check.ModuleDependency(
            source="ix_sally.beta",
            target="ix_sally.alpha",
            line=1,
        ),
    )
    assert graph.cycles() == ()


def test_dependency_graph_ignores_qualified_type_checking_imports(
    tmp_path: Path,
) -> None:
    """Qualified ``typing.TYPE_CHECKING`` guards must remain static-only."""
    package_root = tmp_path / "ix_sally"
    _create_package(package_root)
    (package_root / "alpha.py").write_text(
        "import typing\n"
        "if typing.TYPE_CHECKING:\n"
        "    from . import beta\n",
        encoding="utf-8",
    )
    (package_root / "beta.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    graph = dependency_check.build_dependency_graph(
        source_root=tmp_path,
    )

    assert dependency_check.ModuleDependency(
        source="ix_sally.alpha",
        target="ix_sally.beta",
        line=3,
    ) not in graph.dependencies


def test_dependency_graph_resolves_relative_submodule_imports(
    tmp_path: Path,
) -> None:
    """Nested package imports must resolve to their concrete modules."""
    package_root = tmp_path / "ix_sally"
    language_root = package_root / "language"
    _create_package(package_root)
    _create_package(language_root)
    (language_root / "alpha.py").write_text(
        "from . import beta\n",
        encoding="utf-8",
    )
    (language_root / "beta.py").write_text(
        "from .alpha import VALUE\n",
        encoding="utf-8",
    )

    graph = dependency_check.build_dependency_graph(
        source_root=tmp_path,
    )

    assert dependency_check.ModuleDependency(
        source="ix_sally.language.alpha",
        target="ix_sally.language.beta",
        line=1,
    ) in graph.dependencies
    assert dependency_check.ModuleDependency(
        source="ix_sally.language.beta",
        target="ix_sally.language.alpha",
        line=1,
    ) in graph.dependencies
    assert graph.cycles() == (
        (
            "ix_sally.language.alpha",
            "ix_sally.language.beta",
        ),
    )


def test_dependency_graph_resolves_parent_relative_imports(
    tmp_path: Path,
) -> None:
    """Parent-relative imports must resolve across nested package layers."""
    package_root = tmp_path / "ix_sally"
    language_root = package_root / "language"
    _create_package(package_root)
    _create_package(language_root)
    (package_root / "foundation.py").write_text(
        "class FoundationError(Exception):\n"
        "    pass\n",
        encoding="utf-8",
    )
    (language_root / "runtime.py").write_text(
        "from ..foundation import FoundationError\n",
        encoding="utf-8",
    )

    graph = dependency_check.build_dependency_graph(
        source_root=tmp_path,
    )

    assert dependency_check.ModuleDependency(
        source="ix_sally.language.runtime",
        target="ix_sally.foundation",
        line=1,
    ) in graph.dependencies


def test_dependency_graph_resolves_package_member_modules(
    tmp_path: Path,
) -> None:
    """Package-member imports must target child modules when they exist."""
    package_root = tmp_path / "ix_sally"
    _create_package(package_root)
    (package_root / "state.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    (package_root / "bridge.py").write_text(
        "from ix_sally import state\n",
        encoding="utf-8",
    )

    graph = dependency_check.build_dependency_graph(
        source_root=tmp_path,
    )

    assert dependency_check.ModuleDependency(
        source="ix_sally.bridge",
        target="ix_sally.state",
        line=1,
    ) in graph.dependencies


def test_dependency_check_main_reports_repository_summary(
    capsys: object,
) -> None:
    """The command entry point must report a successful graph summary."""
    assert dependency_check.main() == 0

    output = capsys.readouterr().out
    assert "IX-Sally runtime dependency graph passed:" in output
    assert "0 cycles" in output
