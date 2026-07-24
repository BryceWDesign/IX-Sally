from __future__ import annotations

import subprocess
import sys

import ix_sally
from tests.subprocess_support import repository_subprocess_environment


def test_package_exports_version() -> None:
    assert ix_sally.__version__ == "0.1.0"


def test_cli_module_reports_package_identity() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "ix_sally"],
        check=True,
        capture_output=True,
        text=True,
        env=repository_subprocess_environment(),
    )

    assert completed.stdout == "IX-Sally 0.1.0\n"
    assert completed.stderr == ""
