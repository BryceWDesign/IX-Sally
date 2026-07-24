"""Enforce directional boundaries in the IX-Sally runtime architecture."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dependency_check import DependencyGraph, build_dependency_graph

_HUMAN_REVIEW_PREFIX: Final = "ix_sally.human_review"
_FOUNDATION_TARGETS: Final[dict[str, frozenset[str]]] = {
    "ix_sally.foundation": frozenset(),
    "ix_sally.digest": frozenset({"ix_sally.foundation"}),
}


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    """One internal dependency that violates an architectural boundary."""

    rule: str
    source: str
    target: str
    line: int

    def render(self) -> str:
        """Return a stable human-readable violation message."""
        return (
            f"{self.rule}: {self.source} imports {self.target} "
            f"at line {self.line}"
        )


def _is_status_module(module: str) -> bool:
    """Return whether a module is a dependency-neutral status boundary."""
    return module.rsplit(".", maxsplit=1)[-1].endswith("_status")


def architecture_violations(
    graph: DependencyGraph,
) -> tuple[ArchitectureViolation, ...]:
    """Return deterministic directional dependency violations."""
    violations: list[ArchitectureViolation] = []

    for dependency in graph.dependencies:
        allowed_targets = _FOUNDATION_TARGETS.get(dependency.source)
        if allowed_targets is not None and dependency.target not in allowed_targets:
            violations.append(
                ArchitectureViolation(
                    rule="foundation-boundary",
                    source=dependency.source,
                    target=dependency.target,
                    line=dependency.line,
                )
            )

        if _is_status_module(dependency.source):
            violations.append(
                ArchitectureViolation(
                    rule="status-boundary",
                    source=dependency.source,
                    target=dependency.target,
                    line=dependency.line,
                )
            )

        if (
            dependency.target.startswith(_HUMAN_REVIEW_PREFIX)
            and not dependency.source.startswith(_HUMAN_REVIEW_PREFIX)
        ):
            violations.append(
                ArchitectureViolation(
                    rule="human-review-quarantine",
                    source=dependency.source,
                    target=dependency.target,
                    line=dependency.line,
                )
            )

    return tuple(
        sorted(
            set(violations),
            key=lambda violation: (
                violation.rule,
                violation.source,
                violation.target,
                violation.line,
            ),
        )
    )


def _failure_message(
    violations: tuple[ArchitectureViolation, ...],
) -> str:
    """Return a readable failure message for architecture violations."""
    lines = ["IX-Sally runtime architecture violations detected:"]
    lines.extend(f"- {violation.render()}" for violation in violations)
    return "\n".join(lines)


def main() -> int:
    """Validate directional boundaries in the current repository."""
    repository_root = Path(__file__).resolve().parent
    graph = build_dependency_graph(source_root=repository_root / "src")
    violations = architecture_violations(graph)
    if violations:
        sys.stderr.write(f"{_failure_message(violations)}\n")
        return 1

    sys.stdout.write(
        "IX-Sally runtime architecture passed: "
        f"{len(graph.modules)} modules, {len(graph.dependencies)} imports, "
        "0 boundary violations.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
