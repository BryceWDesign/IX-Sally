"""Run the IX-Sally repository quality gates from one stable entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True, slots=True)
class QualityGate:
    """One repository quality gate and its Python module command."""

    name: str
    label: str
    module: str
    arguments: tuple[str, ...]

    def command(self) -> tuple[str, ...]:
        """Return the interpreter-bound command for this quality gate."""
        return (sys.executable, "-m", self.module, *self.arguments)


QUALITY_GATES: Final[tuple[QualityGate, ...]] = (
    QualityGate(
        name="format",
        label="Ruff format check",
        module="ruff",
        arguments=("format", "--check", "."),
    ),
    QualityGate(
        name="lint",
        label="Ruff lint check",
        module="ruff",
        arguments=("check", "."),
    ),
    QualityGate(
        name="type-check",
        label="Mypy strict type check",
        module="mypy",
        arguments=("src", "tests"),
    ),
    QualityGate(
        name="repository",
        label="Cross-platform repository integrity",
        module="repository_check",
        arguments=(),
    ),
    QualityGate(
        name="dependencies",
        label="Runtime dependency graph",
        module="dependency_check",
        arguments=(),
    ),
    QualityGate(
        name="architecture",
        label="Runtime architecture boundaries",
        module="architecture_check",
        arguments=(),
    ),
    QualityGate(
        name="test",
        label="Pytest suite",
        module="pytest",
        arguments=(),
    ),
    QualityGate(
        name="package",
        label="Installed wheel smoke test",
        module="package_smoke",
        arguments=(),
    ),
)

_GATE_BY_NAME: Final[dict[str, QualityGate]] = {gate.name: gate for gate in QUALITY_GATES}


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for repository quality checks."""
    parser = argparse.ArgumentParser(
        description=(
            "Run IX-Sally formatting, lint, typing, repository, dependency, "
            "architecture, test, and package gates."
        ),
    )
    parser.add_argument(
        "--gate",
        action="append",
        choices=tuple(_GATE_BY_NAME),
        dest="gate_names",
        help="Run only the named gate. Repeat to select multiple gates.",
    )
    return parser


def _selected_gates(
    gate_names: Sequence[str] | None,
) -> tuple[QualityGate, ...]:
    """Return all gates or the requested gates in command-line order."""
    if gate_names is None:
        return QUALITY_GATES
    return tuple(_GATE_BY_NAME[name] for name in gate_names)


def _run_gate(gate: QualityGate, *, repository_root: Path) -> int:
    """Run one quality gate and return its process exit code."""
    sys.stdout.write(f"==> {gate.label}\n")
    sys.stdout.flush()
    completed = subprocess.run(
        gate.command(),
        cwd=repository_root,
        check=False,
    )
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected quality gates and return a combined process status."""
    arguments = _parser().parse_args(argv)
    repository_root = Path(__file__).resolve().parent
    failures: list[str] = []

    for gate in _selected_gates(arguments.gate_names):
        return_code = _run_gate(
            gate,
            repository_root=repository_root,
        )
        if return_code != 0:
            failures.append(gate.name)

    if failures:
        sys.stderr.write(f"Failed quality gates: {', '.join(failures)}\n")
        return 1

    sys.stdout.write("All selected quality gates passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
