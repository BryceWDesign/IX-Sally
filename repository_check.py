"""Validate cross-platform integrity of the IX-Sally repository tree."""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_WINDOWS_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
)
_PYTHON_MODULE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*\.py$")
_SPECIAL_PYTHON_FILES: Final[frozenset[str]] = frozenset({"__init__.py", "__main__.py"})
_REQUIRED_PATHS: Final[tuple[str, ...]] = (
    "LICENSE",
    "pyproject.toml",
    "src/ix_sally/__init__.py",
    "src/ix_sally/py.typed",
    "tests/__init__.py",
)
_SCAN_ROOTS: Final[tuple[str, ...]] = ("src", "tests")


@dataclass(frozen=True, slots=True)
class RepositoryViolation:
    """One deterministic repository-integrity violation."""

    rule: str
    path: str
    detail: str

    def render(self) -> str:
        """Return a stable human-readable violation message."""
        return f"{self.rule}: {self.path}: {self.detail}"


def _relative_path(*, repository_root: Path, path: Path) -> str:
    """Return one normalized repository-relative path."""
    return path.relative_to(repository_root).as_posix()


def _scanned_paths(*, repository_root: Path) -> tuple[Path, ...]:
    """Return all source and test paths in deterministic order."""
    paths: list[Path] = []
    for root_name in _SCAN_ROOTS:
        root = repository_root / root_name
        if root.exists():
            paths.extend(root.rglob("*"))
    return tuple(sorted(paths, key=lambda path: path.as_posix().casefold()))


def _required_path_violations(
    *,
    repository_root: Path,
) -> tuple[RepositoryViolation, ...]:
    """Return violations for required repository files that are absent."""
    return tuple(
        RepositoryViolation(
            rule="required-path",
            path=relative,
            detail="required repository path is missing",
        )
        for relative in _REQUIRED_PATHS
        if not (repository_root / relative).is_file()
    )


def _case_collision_violations(
    *,
    repository_root: Path,
    paths: tuple[Path, ...],
) -> tuple[RepositoryViolation, ...]:
    """Return path collisions that fail on case-insensitive filesystems."""
    by_casefolded_path: dict[str, list[str]] = {}
    for path in paths:
        relative = _relative_path(
            repository_root=repository_root,
            path=path,
        )
        by_casefolded_path.setdefault(relative.casefold(), []).append(relative)

    violations: list[RepositoryViolation] = []
    for variants in by_casefolded_path.values():
        unique_variants = tuple(sorted(set(variants)))
        if len(unique_variants) > 1:
            rendered = ", ".join(unique_variants)
            violations.append(
                RepositoryViolation(
                    rule="case-collision",
                    path=unique_variants[0],
                    detail=f"case-insensitive collision with: {rendered}",
                )
            )
    return tuple(violations)


def _path_component_violations(
    *,
    repository_root: Path,
    paths: tuple[Path, ...],
) -> tuple[RepositoryViolation, ...]:
    """Return Windows-incompatible or ambiguous path-component violations."""
    violations: list[RepositoryViolation] = []
    for path in paths:
        relative = _relative_path(
            repository_root=repository_root,
            path=path,
        )
        for component in Path(relative).parts:
            if component != component.rstrip(" ."):
                violations.append(
                    RepositoryViolation(
                        rule="path-component",
                        path=relative,
                        detail=(f"component {component!r} ends with a space or period"),
                    )
                )

            stem = component.split(".", maxsplit=1)[0].casefold()
            if stem in _WINDOWS_RESERVED_NAMES:
                violations.append(
                    RepositoryViolation(
                        rule="windows-reserved-name",
                        path=relative,
                        detail=f"component {component!r} is reserved on Windows",
                    )
                )
    return tuple(violations)


def _python_filename_violations(
    *,
    repository_root: Path,
    paths: tuple[Path, ...],
) -> tuple[RepositoryViolation, ...]:
    """Return invalid Python module filename violations."""
    violations: list[RepositoryViolation] = []
    for path in paths:
        if not path.is_file() or path.suffix != ".py":
            continue
        if path.name in _SPECIAL_PYTHON_FILES:
            continue
        if not _PYTHON_MODULE_PATTERN.fullmatch(path.name):
            violations.append(
                RepositoryViolation(
                    rule="python-module-name",
                    path=_relative_path(
                        repository_root=repository_root,
                        path=path,
                    ),
                    detail=("Python modules must use lowercase snake_case filenames"),
                )
            )
    return tuple(violations)


def _package_marker_violations(
    *,
    repository_root: Path,
) -> tuple[RepositoryViolation, ...]:
    """Return source package directories missing ``__init__.py`` markers."""
    package_root = repository_root / "src" / "ix_sally"
    if not package_root.is_dir():
        return ()

    violations: list[RepositoryViolation] = []
    directories = {package_root}
    directories.update(path.parent for path in package_root.rglob("*.py") if path.is_file())

    for directory in sorted(directories):
        marker = directory / "__init__.py"
        if not marker.is_file():
            violations.append(
                RepositoryViolation(
                    rule="package-marker",
                    path=_relative_path(
                        repository_root=repository_root,
                        path=directory,
                    ),
                    detail="Python package directory is missing __init__.py",
                )
            )
    return tuple(violations)


def _python_source_violations(
    *,
    repository_root: Path,
    paths: tuple[Path, ...],
) -> tuple[RepositoryViolation, ...]:
    """Return UTF-8 decoding and Python parsing violations."""
    violations: list[RepositoryViolation] = []
    for path in paths:
        if not path.is_file() or path.suffix != ".py":
            continue

        relative = _relative_path(
            repository_root=repository_root,
            path=path,
        )
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            violations.append(
                RepositoryViolation(
                    rule="utf8-source",
                    path=relative,
                    detail=f"source is not valid UTF-8: {error}",
                )
            )
            continue

        try:
            ast.parse(source, filename=str(path))
        except SyntaxError as error:
            location = f"line {error.lineno}" if error.lineno is not None else "unknown line"
            violations.append(
                RepositoryViolation(
                    rule="python-syntax",
                    path=relative,
                    detail=(f"source does not parse at {location}: {error.msg}"),
                )
            )
    return tuple(violations)


def repository_violations(
    *,
    repository_root: Path,
) -> tuple[RepositoryViolation, ...]:
    """Return all deterministic cross-platform repository violations."""
    paths = _scanned_paths(repository_root=repository_root)
    violations = (
        *_required_path_violations(repository_root=repository_root),
        *_case_collision_violations(
            repository_root=repository_root,
            paths=paths,
        ),
        *_path_component_violations(
            repository_root=repository_root,
            paths=paths,
        ),
        *_python_filename_violations(
            repository_root=repository_root,
            paths=paths,
        ),
        *_package_marker_violations(repository_root=repository_root),
        *_python_source_violations(
            repository_root=repository_root,
            paths=paths,
        ),
    )
    return tuple(
        sorted(
            set(violations),
            key=lambda violation: (
                violation.rule,
                violation.path.casefold(),
                violation.detail,
            ),
        )
    )


def _failure_message(
    violations: tuple[RepositoryViolation, ...],
) -> str:
    """Return a readable failure message for repository violations."""
    lines = ["IX-Sally repository integrity violations detected:"]
    lines.extend(f"- {violation.render()}" for violation in violations)
    return "\n".join(lines)


def main() -> int:
    """Validate the current IX-Sally repository tree."""
    repository_root = Path(__file__).resolve().parent
    violations = repository_violations(repository_root=repository_root)
    if violations:
        sys.stderr.write(f"{_failure_message(violations)}\n")
        return 1

    scanned_files = sum(
        1 for path in _scanned_paths(repository_root=repository_root) if path.is_file()
    )
    sys.stdout.write(
        f"IX-Sally repository integrity passed: {scanned_files} source/test files, 0 violations.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
