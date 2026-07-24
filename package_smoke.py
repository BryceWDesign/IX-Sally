"""Build and verify the IX-Sally wheel in an isolated environment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path
from typing import Final

_PACKAGE_NAME: Final = "ix-sally"
_PACKAGE_VERSION: Final = "0.1.0"
_SHA256_HEX_LENGTH: Final = 64


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one smoke-test command and capture its text output."""
    return subprocess.run(
        tuple(command),
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _isolated_environment() -> dict[str, str]:
    """Return an environment without source-tree Python path overrides."""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    return environment


def _venv_python(environment_root: Path) -> Path:
    """Return the platform-specific Python executable inside a virtual environment."""
    if os.name == "nt":
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _venv_console_script(environment_root: Path) -> Path:
    """Return the platform-specific IX-Sally console-script path."""
    if os.name == "nt":
        return environment_root / "Scripts" / "ix-sally.exe"
    return environment_root / "bin" / "ix-sally"


def _build_wheel(*, repository_root: Path, wheel_directory: Path) -> Path:
    """Build one dependency-free wheel from the current repository."""
    _run(
        (
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_directory),
        ),
        cwd=repository_root,
    )
    wheels = tuple(sorted(wheel_directory.glob("ix_sally-*.whl")))
    if len(wheels) != 1:
        raise RuntimeError(
            f"expected exactly one IX-Sally wheel, found {len(wheels)}"
        )
    return wheels[0]


def _install_wheel(
    *,
    repository_root: Path,
    environment_root: Path,
    wheel_path: Path,
) -> Path:
    """Install the built wheel into a clean virtual environment."""
    venv.EnvBuilder(with_pip=True, clear=True).create(environment_root)
    python_executable = _venv_python(environment_root)
    _run(
        (
            str(python_executable),
            "-m",
            "pip",
            "install",
            "--no-index",
            str(wheel_path),
        ),
        cwd=repository_root,
        environment=_isolated_environment(),
    )
    return python_executable


def _verify_installed_package(
    *,
    repository_root: Path,
    environment_root: Path,
    python_executable: Path,
) -> None:
    """Verify imports, module execution, and the installed console script."""
    environment = _isolated_environment()
    import_statement = (
        "import ix_sally; "
        f"assert ix_sally.__version__ == {_PACKAGE_VERSION!r}; "
        "assert ix_sally.NinefoldRunState.__module__ == 'ix_sally.state'"
    )
    import_check = _run(
        (str(python_executable), "-c", import_statement),
        cwd=repository_root,
        environment=environment,
    )
    if import_check.stderr:
        raise RuntimeError(import_check.stderr)

    module_result = _run(
        (str(python_executable), "-m", "ix_sally", "--runtime-baseline"),
        cwd=repository_root,
        environment=environment,
    )
    payload = json.loads(module_result.stdout)
    if payload.get("package") != _PACKAGE_NAME:
        raise RuntimeError("installed module reported an unexpected package name")
    if payload.get("version") != _PACKAGE_VERSION:
        raise RuntimeError("installed module reported an unexpected package version")

    console_result = _run(
        (str(_venv_console_script(environment_root)), "--baseline-digest"),
        cwd=repository_root,
        environment=environment,
    )
    digest_line = console_result.stdout.strip()
    prefix, separator, digest_value = digest_line.partition(":")
    if prefix != "sha256" or separator != ":" or len(digest_value) != _SHA256_HEX_LENGTH:
        raise RuntimeError("installed console script returned an invalid baseline digest")


def main() -> int:
    """Build, install, and verify the current IX-Sally wheel."""
    repository_root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="ix-sally-package-smoke-") as directory:
        temporary_root = Path(directory)
        wheel_path = _build_wheel(
            repository_root=repository_root,
            wheel_directory=temporary_root / "dist",
        )
        environment_root = temporary_root / "venv"
        python_executable = _install_wheel(
            repository_root=repository_root,
            environment_root=environment_root,
            wheel_path=wheel_path,
        )
        _verify_installed_package(
            repository_root=repository_root,
            environment_root=environment_root,
            python_executable=python_executable,
        )

    sys.stdout.write("Installed IX-Sally wheel smoke test passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
