"""Build and verify the IX-Sally wheel in an isolated environment."""

from __future__ import annotations

import ast
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from collections.abc import Sequence
from pathlib import Path
from typing import Final

_PACKAGE_NAME: Final = "ix-sally"
_SHA256_HEX_LENGTH: Final = 64
_IGNORED_SOURCE_PATTERNS: Final[tuple[str, ...]] = (
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "*.egg-info",
    "*.pyc",
    "*.pyo",
    "build",
    "dist",
)


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
    environment.pop(
        "PYTHONPATH",
        None,
    )
    environment.pop(
        "PYTHONHOME",
        None,
    )
    return environment


def _venv_python(
    environment_root: Path,
) -> Path:
    """Return the platform-specific Python executable in a virtual environment."""
    if os.name == "nt":
        return environment_root / "Scripts" / "python.exe"

    return environment_root / "bin" / "python"


def _venv_console_script(
    environment_root: Path,
) -> Path:
    """Return the platform-specific IX-Sally console-script path."""
    if os.name == "nt":
        return environment_root / "Scripts" / "ix-sally.exe"

    return environment_root / "bin" / "ix-sally"


def _source_version(
    *,
    repository_root: Path,
) -> str:
    """Return the canonical version declared by the source package."""
    version_path = repository_root / "src" / "ix_sally" / "version.py"
    tree = ast.parse(
        version_path.read_text(encoding="utf-8"),
        filename=str(version_path),
    )

    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            continue

        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value:
            return value.value

    raise RuntimeError("IX-Sally source version is missing or is not a string literal")


def _ignored_source_entries(
    _directory: str,
    names: list[str],
) -> set[str]:
    """Return generated or repository-local entries excluded from smoke builds."""
    return {
        name
        for name in names
        if any(
            fnmatch.fnmatchcase(
                name,
                pattern,
            )
            for pattern in _IGNORED_SOURCE_PATTERNS
        )
    }


def _copy_source_tree(
    *,
    repository_root: Path,
    source_root: Path,
) -> None:
    """Copy build inputs into disposable storage without generated artifacts."""
    shutil.copytree(
        repository_root,
        source_root,
        ignore=_ignored_source_entries,
    )


def _build_wheel(
    *,
    source_root: Path,
    wheel_directory: Path,
) -> Path:
    """Build one dependency-free wheel from a disposable source tree."""
    wheel_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
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
        cwd=source_root,
    )

    wheels = tuple(sorted(wheel_directory.glob("ix_sally-*.whl")))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one IX-Sally wheel, found {len(wheels)}")

    return wheels[0]


def _install_wheel(
    *,
    working_root: Path,
    environment_root: Path,
    wheel_path: Path,
) -> Path:
    """Install the built wheel into a clean virtual environment."""
    venv.EnvBuilder(
        with_pip=True,
        clear=True,
    ).create(environment_root)

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
        cwd=working_root,
        environment=_isolated_environment(),
    )
    return python_executable


def _verify_installed_package(
    *,
    working_root: Path,
    environment_root: Path,
    python_executable: Path,
    expected_version: str,
) -> None:
    """Verify imports, module execution, and the installed console script."""
    environment = _isolated_environment()
    import_statement = (
        "import ix_sally; "
        f"assert ix_sally.__version__ == {expected_version!r}; "
        "assert ix_sally.NinefoldRunState.__module__ == "
        "'ix_sally.state'"
    )
    import_check = _run(
        (
            str(python_executable),
            "-c",
            import_statement,
        ),
        cwd=working_root,
        environment=environment,
    )
    if import_check.stderr:
        raise RuntimeError(import_check.stderr)

    module_result = _run(
        (
            str(python_executable),
            "-m",
            "ix_sally",
            "--runtime-baseline",
        ),
        cwd=working_root,
        environment=environment,
    )
    payload = json.loads(module_result.stdout)
    if payload.get("package") != _PACKAGE_NAME:
        raise RuntimeError("installed module reported an unexpected package name")
    if payload.get("version") != expected_version:
        raise RuntimeError("installed module reported an unexpected package version")

    console_result = _run(
        (
            str(_venv_console_script(environment_root)),
            "--baseline-digest",
        ),
        cwd=working_root,
        environment=environment,
    )
    digest_line = console_result.stdout.strip()
    prefix, separator, digest_value = digest_line.partition(":")

    if prefix != "sha256" or separator != ":" or len(digest_value) != _SHA256_HEX_LENGTH:
        raise RuntimeError("installed console script returned an invalid baseline digest")


def main() -> int:
    """Build, install, and verify the current IX-Sally wheel."""
    repository_root = Path(__file__).resolve().parent
    expected_version = _source_version(repository_root=repository_root)

    with tempfile.TemporaryDirectory(prefix="ix-sally-package-smoke-") as directory:
        temporary_root = Path(directory)
        source_root = temporary_root / "source"

        _copy_source_tree(
            repository_root=repository_root,
            source_root=source_root,
        )
        wheel_path = _build_wheel(
            source_root=source_root,
            wheel_directory=temporary_root / "dist",
        )
        environment_root = temporary_root / "venv"
        python_executable = _install_wheel(
            working_root=temporary_root,
            environment_root=environment_root,
            wheel_path=wheel_path,
        )
        _verify_installed_package(
            working_root=temporary_root,
            environment_root=environment_root,
            python_executable=python_executable,
            expected_version=expected_version,
        )

    sys.stdout.write("Installed IX-Sally wheel smoke test passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
