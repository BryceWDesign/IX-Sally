"""Tests for repository-local subprocess isolation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.subprocess_support import repository_subprocess_environment


def test_subprocess_imports_ix_sally_from_repository_source() -> None:
    """Fresh Python processes must resolve IX-Sally from this checkout first."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ix_sally; print(ix_sally.__file__)",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=repository_subprocess_environment(),
    )

    repository_root = Path(__file__).resolve().parents[1]
    expected_package_root = repository_root / "src" / "ix_sally"
    imported_path = Path(completed.stdout.strip()).resolve()

    assert imported_path.is_relative_to(expected_package_root)
    assert completed.stderr == ""
