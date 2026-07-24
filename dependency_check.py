"""Validate the IX-Sally internal runtime dependency graph."""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_PACKAGE_NAME: Final = "ix_sally"


@dataclass(frozen=True, slots=True)
class ModuleDependency:
    """One internal runtime dependency discovered from Python source."""

    source: str
    target: str
    line: int


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    """A directed graph of IX-Sally runtime module dependencies."""

    modules: tuple[str, ...]
    dependencies: tuple[ModuleDependency, ...]

    def adjacency(self) -> dict[str, tuple[str, ...]]:
        """Return deterministic adjacency entries for every known module."""
        targets: dict[str, set[str]] = {module: set() for module in self.modules}
        for dependency in self.dependencies:
            targets[dependency.source].add(dependency.target)
        return {
            module: tuple(sorted(module_targets))
            for module, module_targets in targets.items()
        }

    def cycles(self) -> tuple[tuple[str, ...], ...]:
        """Return deterministic strongly connected runtime dependency cycles."""
        adjacency = self.adjacency()
        index = 0
        indices: dict[str, int] = {}
        low_links: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        components: list[tuple[str, ...]] = []

        def visit(module: str) -> None:
            nonlocal index
            indices[module] = index
            low_links[module] = index
            index += 1
            stack.append(module)
            on_stack.add(module)

            for target in adjacency[module]:
                if target not in indices:
                    visit(target)
                    low_links[module] = min(low_links[module], low_links[target])
                elif target in on_stack:
                    low_links[module] = min(low_links[module], indices[target])

            if low_links[module] != indices[module]:
                return

            component: list[str] = []
            while stack:
                target = stack.pop()
                on_stack.remove(target)
                component.append(target)
                if target == module:
                    break
            components.append(tuple(sorted(component)))

        for module in self.modules:
            if module not in indices:
                visit(module)

        cyclic_components = [
            component
            for component in components
            if len(component) > 1
            or (
                len(component) == 1
                and component[0] in adjacency[component[0]]
            )
        ]
        return tuple(sorted(cyclic_components))


def _module_name(*, source_root: Path, path: Path) -> str:
    """Return the dotted module name for one Python source path."""
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_paths(*, source_root: Path) -> dict[str, Path]:
    """Return every Python module below the configured source root."""
    package_root = source_root / _PACKAGE_NAME
    return {
        _module_name(source_root=source_root, path=path): path
        for path in sorted(package_root.rglob("*.py"))
    }


def _is_type_checking_guard(node: ast.expr) -> bool:
    """Return whether an expression is the conventional TYPE_CHECKING guard."""
    return isinstance(node, ast.Name) and node.id == "TYPE_CHECKING"


def _internal_import_targets(
    *,
    tree: ast.Module,
    known_modules: set[str],
) -> tuple[tuple[str, int], ...]:
    """Return internal imports that execute outside TYPE_CHECKING guards."""
    imports: list[tuple[str, int]] = []

    def visit_statements(
        statements: Iterable[ast.stmt],
        *,
        type_checking_only: bool,
    ) -> None:
        for statement in statements:
            if isinstance(statement, ast.If):
                guarded = type_checking_only or _is_type_checking_guard(statement.test)
                visit_statements(statement.body, type_checking_only=guarded)
                visit_statements(
                    statement.orelse,
                    type_checking_only=type_checking_only,
                )
                continue

            if isinstance(statement, ast.ImportFrom) and not type_checking_only:
                module = statement.module
                if module is not None and module in known_modules:
                    imports.append((module, statement.lineno))
                continue

            if isinstance(statement, ast.Import) and not type_checking_only:
                for alias in statement.names:
                    if alias.name in known_modules:
                        imports.append((alias.name, statement.lineno))
                continue

            nested_statements: list[ast.stmt] = []
            if isinstance(
                statement,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                nested_statements.extend(statement.body)
            elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                nested_statements.extend(statement.body)
                nested_statements.extend(statement.orelse)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                nested_statements.extend(statement.body)
            elif isinstance(statement, ast.Try):
                nested_statements.extend(statement.body)
                nested_statements.extend(statement.orelse)
                nested_statements.extend(statement.finalbody)
                for handler in statement.handlers:
                    nested_statements.extend(handler.body)
            elif isinstance(statement, ast.Match):
                for case in statement.cases:
                    nested_statements.extend(case.body)

            if nested_statements:
                visit_statements(
                    nested_statements,
                    type_checking_only=type_checking_only,
                )

    visit_statements(tree.body, type_checking_only=False)
    return tuple(imports)


def build_dependency_graph(*, source_root: Path) -> DependencyGraph:
    """Build the internal runtime dependency graph from Python source."""
    module_paths = _module_paths(source_root=source_root)
    known_modules = set(module_paths)
    dependencies: list[ModuleDependency] = []

    for module, path in module_paths.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for target, line in _internal_import_targets(
            tree=tree,
            known_modules=known_modules,
        ):
            dependencies.append(
                ModuleDependency(
                    source=module,
                    target=target,
                    line=line,
                )
            )

    return DependencyGraph(
        modules=tuple(sorted(module_paths)),
        dependencies=tuple(
            sorted(
                dependencies,
                key=lambda dependency: (
                    dependency.source,
                    dependency.target,
                    dependency.line,
                ),
            )
        ),
    )


def _cycle_message(
    cycles: tuple[tuple[str, ...], ...],
    dependencies: tuple[ModuleDependency, ...],
) -> str:
    """Return a readable failure message for dependency cycles."""
    dependency_lines: dict[tuple[str, str], list[int]] = {}
    cycle_modules = {module for cycle in cycles for module in cycle}
    for dependency in dependencies:
        if (
            dependency.source in cycle_modules
            and dependency.target in cycle_modules
        ):
            pair = (dependency.source, dependency.target)
            dependency_lines.setdefault(pair, []).append(dependency.line)

    lines = ["IX-Sally runtime dependency cycles detected:"]
    for cycle in cycles:
        lines.append(f"- {' -> '.join(cycle)}")
        for source in cycle:
            for target in cycle:
                locations = dependency_lines.get((source, target))
                if locations:
                    rendered = ", ".join(str(line) for line in sorted(locations))
                    lines.append(
                        f"  {source} imports {target} at line(s) {rendered}"
                    )
    return "\n".join(lines)


def main() -> int:
    """Validate the current repository's internal runtime dependencies."""
    repository_root = Path(__file__).resolve().parent
    graph = build_dependency_graph(source_root=repository_root / "src")
    cycles = graph.cycles()
    if cycles:
        sys.stderr.write(f"{_cycle_message(cycles, graph.dependencies)}\n")
        return 1

    sys.stdout.write(
        "IX-Sally runtime dependency graph passed: "
        f"{len(graph.modules)} modules, {len(graph.dependencies)} imports, 0 cycles.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
