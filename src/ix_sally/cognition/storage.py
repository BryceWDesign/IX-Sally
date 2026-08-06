"""Atomic local snapshot storage with backup validation and explicit recovery."""

from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from ix_sally.cognition.persistence import CognitiveSnapshot
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError


class SnapshotSource(StrEnum):
    """Source selected while loading a persisted cognitive snapshot."""

    PRIMARY = "primary"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class SnapshotSaveReceipt:
    """Receipt for one atomic primary-file replacement attempt."""

    path: str
    backup_path: str
    snapshot_digest: DigestRecord
    bytes_written: int
    backup_created: bool

    def to_payload(self) -> JsonObject:
        """Return a canonical save receipt."""
        return {
            "path": self.path,
            "backup_path": self.backup_path,
            "snapshot_digest": {
                "algorithm": self.snapshot_digest.algorithm,
                "value": self.snapshot_digest.value,
            },
            "bytes_written": self.bytes_written,
            "backup_created": self.backup_created,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic receipt identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SnapshotLoadResult:
    """Validated load result that records whether recovery used a backup."""

    snapshot: CognitiveSnapshot
    source: SnapshotSource
    primary_error: str | None = None

    def to_payload(self) -> JsonObject:
        """Return a canonical load/recovery result."""
        return {
            "snapshot": self.snapshot.to_payload(),
            "source": self.source.value,
            "primary_error": self.primary_error,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic load-result identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SnapshotRepository:
    """Persist snapshots with temporary-file replacement and one validated backup."""

    path: Path

    def __post_init__(self) -> None:
        """Require a file path rather than an existing directory."""
        if self.path.exists() and self.path.is_dir():
            raise FoundationError("snapshot path must not be a directory")

    @property
    def backup_path(self) -> Path:
        """Return the deterministic sibling backup path."""
        return self.path.with_name(f"{self.path.name}.bak")

    @property
    def temporary_path(self) -> Path:
        """Return the deterministic sibling temporary path."""
        return self.path.with_name(f"{self.path.name}.tmp")

    def save(self, snapshot: CognitiveSnapshot) -> SnapshotSaveReceipt:
        """Validate, write, flush, and atomically replace the primary snapshot.

        The method uses operating-system replacement semantics. It does not claim
        storage-hardware durability beyond the completed writes and flush requests.
        """
        encoded = snapshot.to_json().encode("utf-8")
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        backup_created = False
        if self.temporary_path.exists():
            self.temporary_path.unlink()
        try:
            with self.temporary_path.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            restored = CognitiveSnapshot.from_json(self.temporary_path.read_text(encoding="utf-8"))
            if restored.state_digest != snapshot.state_digest:
                raise FoundationError("temporary snapshot verification failed")
            if self.path.exists():
                current = CognitiveSnapshot.from_json(self.path.read_text(encoding="utf-8"))
                backup_encoded = current.to_json().encode("utf-8")
                with self.backup_path.open("wb") as handle:
                    handle.write(backup_encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                backup_created = True
            self.temporary_path.replace(self.path)
            self._flush_directory(parent)
        finally:
            if self.temporary_path.exists():
                self.temporary_path.unlink()
        loaded = CognitiveSnapshot.from_json(self.path.read_text(encoding="utf-8"))
        if loaded.state_digest != snapshot.state_digest:
            raise FoundationError("persisted snapshot verification failed")
        return SnapshotSaveReceipt(
            path=self.path.as_posix(),
            backup_path=self.backup_path.as_posix(),
            snapshot_digest=snapshot.state_digest,
            bytes_written=len(encoded),
            backup_created=backup_created,
        )

    def load(self, *, allow_backup: bool = True) -> SnapshotLoadResult:
        """Load the primary snapshot or a separately validated backup."""
        primary_error: str | None = None
        try:
            snapshot = CognitiveSnapshot.from_json(self.path.read_text(encoding="utf-8"))
            return SnapshotLoadResult(snapshot, SnapshotSource.PRIMARY)
        except (OSError, UnicodeError, FoundationError) as exc:
            primary_error = f"{type(exc).__name__}: {exc}"
        if not allow_backup:
            raise FoundationError(f"primary cognitive snapshot failed: {primary_error}")
        try:
            snapshot = CognitiveSnapshot.from_json(self.backup_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, FoundationError) as exc:
            backup_error = f"{type(exc).__name__}: {exc}"
            raise FoundationError(
                "primary and backup cognitive snapshots failed: "
                f"primary={primary_error}; backup={backup_error}"
            ) from exc
        return SnapshotLoadResult(
            snapshot=snapshot,
            source=SnapshotSource.BACKUP,
            primary_error=primary_error,
        )

    @staticmethod
    def _flush_directory(directory: Path) -> None:
        """Best-effort flush of directory metadata on platforms that support it."""
        flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
        try:
            descriptor = os.open(directory, flags)
        except OSError:
            return
        try:
            with suppress(OSError):
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
