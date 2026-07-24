"""Import-order regression tests for the complete IX-Sally runtime package."""

from __future__ import annotations

import pkgutil
import subprocess
import sys

import ix_sally


def _runtime_module_names() -> tuple[str, ...]:
    """Return every runtime module except the executable entry point."""
    return tuple(
        sorted(
            module.name
            for module in pkgutil.iter_modules(
                ix_sally.__path__,
                f"{ix_sally.__name__}.",
            )
            if module.name != "ix_sally.__main__"
        )
    )


def _import_orders() -> tuple[tuple[str, ...], ...]:
    """Return deterministic orders that stress package import dependencies."""
    modules = _runtime_module_names()
    midpoint = len(modules) // 2
    return (
        modules,
        tuple(reversed(modules)),
        modules[midpoint:] + modules[:midpoint],
    )


def test_runtime_module_inventory_is_not_empty() -> None:
    """The import gate must discover the installed IX-Sally runtime modules."""
    assert _runtime_module_names()


def test_runtime_modules_import_in_multiple_orders() -> None:
    """All runtime modules must load under multiple deterministic import orders."""
    failures: list[str] = []

    for order_index, module_names in enumerate(_import_orders(), start=1):
        statement = "; ".join(f"import {module_name}" for module_name in module_names)
        completed = subprocess.run(
            [sys.executable, "-c", statement],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            failures.append(
                f"order {order_index}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )

    assert not failures, "\n".join(failures)
