"""Regression tests for human-review control-plane module boundaries."""

import subprocess
import sys

import pytest
from tests.subprocess_support import repository_subprocess_environment


@pytest.mark.parametrize(
    "modules",
    (
        (
            "ix_sally.human_review_control_plane",
            "ix_sally.human_review_control_plane_report",
        ),
        (
            "ix_sally.human_review_control_plane_report",
            "ix_sally.human_review_control_plane",
        ),
    ),
)
def test_control_plane_modules_import_in_either_order(
    modules: tuple[str, str],
) -> None:
    """Control-plane modules must not depend on a favorable import order."""
    statement = "; ".join(f"import {module}" for module in modules)

    completed = subprocess.run(
        [sys.executable, "-c", statement],
        check=False,
        capture_output=True,
        text=True,
        env=repository_subprocess_environment(),
    )

    assert completed.returncode == 0, completed.stderr
