"""IX-Forge execution receipts for sandboxed action records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class ExecutionStatus(StrEnum):
    """Status assigned to an IX-Forge execution receipt."""

    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ForgeExecutionReceipt:
    """A deterministic receipt for an action attempted by IX-Forge."""

    receipt_id: CanonicalKey
    cycle: int
    tool_key: CanonicalKey
    command: tuple[str, ...]
    sandboxed: bool
    status: ExecutionStatus
    summary: str
    exit_code: int | None = None
    stdout_digest: DigestRecord | None = None
    stderr_digest: DigestRecord | None = None
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        tool_key: str,
        command: Iterable[str],
        sandboxed: bool,
        status: ExecutionStatus,
        summary: str,
        exit_code: int | None = None,
        stdout_digest: DigestRecord | None = None,
        stderr_digest: DigestRecord | None = None,
        boundary_note: str | None = None,
        receipt_id: CanonicalKey | None = None,
    ) -> ForgeExecutionReceipt:
        """Create a normalized IX-Forge execution receipt."""
        if cycle < 0:
            raise FoundationError("execution cycle must not be negative")

        normalized_tool = CanonicalKey.from_text(tool_key, field_name="tool_key")
        normalized_command = tuple(
            require_text(part, field_name="command_part") for part in command
        )
        if not normalized_command:
            raise FoundationError("execution command requires at least one part")

        normalized_summary = require_text(summary, field_name="summary")
        normalized_boundary_note = require_optional_text(
            boundary_note,
            field_name="boundary_note",
        )

        if stdout_digest is not None:
            stdout_digest.require_algorithm("sha256")
        if stderr_digest is not None:
            stderr_digest.require_algorithm("sha256")

        if not sandboxed and status is not ExecutionStatus.BLOCKED:
            raise FoundationError("non-sandboxed execution must be blocked")

        if status is ExecutionStatus.PASSED and exit_code != 0:
            raise FoundationError("passed execution receipts require exit_code 0")

        if status is ExecutionStatus.FAILED and exit_code in {None, 0}:
            raise FoundationError("failed execution receipts require a non-zero exit_code")

        if status in {ExecutionStatus.BLOCKED, ExecutionStatus.TIMED_OUT}:
            if normalized_boundary_note is None:
                raise FoundationError("blocked or timed-out executions require a boundary note")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"ix-forge-{cycle}-{normalized_tool.value}-{normalized_summary}",
                field_name="receipt_id",
            ),
            cycle=cycle,
            tool_key=normalized_tool,
            command=normalized_command,
            sandboxed=sandboxed,
            status=status,
            summary=normalized_summary,
            exit_code=exit_code,
            stdout_digest=stdout_digest,
            stderr_digest=stderr_digest,
            boundary_note=normalized_boundary_note,
        )

    def succeeded(self) -> bool:
        """Return whether this receipt records a successful execution."""
        return self.status is ExecutionStatus.PASSED

    def blocks_progress(self) -> bool:
        """Return whether this receipt blocks the current runtime path."""
        return self.status in {ExecutionStatus.BLOCKED, ExecutionStatus.TIMED_OUT}

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible execution receipt representation."""
        return {
            "receipt_id": self.receipt_id.value,
            "cycle": self.cycle,
            "tool_key": self.tool_key.value,
            "command": list(self.command),
            "sandboxed": self.sandboxed,
            "status": self.status.value,
            "summary": self.summary,
            "exit_code": self.exit_code,
            "stdout_digest": (
                {
                    "algorithm": self.stdout_digest.algorithm,
                    "value": self.stdout_digest.value,
                }
                if self.stdout_digest is not None
                else None
            ),
            "stderr_digest": (
                {
                    "algorithm": self.stderr_digest.algorithm,
                    "value": self.stderr_digest.value,
                }
                if self.stderr_digest is not None
                else None
            ),
            "boundary_note": self.boundary_note,
            "succeeded": self.succeeded(),
            "blocks_progress": self.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this execution receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeExecutionPacket:
    """Structured IX-Forge packet containing sandbox execution receipts."""

    packet_id: CanonicalKey
    cycle: int
    execution_summary: str
    receipts: tuple[ForgeExecutionReceipt, ...]

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        execution_summary: str,
        receipts: Iterable[ForgeExecutionReceipt],
        packet_id: CanonicalKey | None = None,
    ) -> ForgeExecutionPacket:
        """Create a normalized IX-Forge execution packet."""
        if cycle < 0:
            raise FoundationError("execution packet cycle must not be negative")

        normalized_summary = require_text(execution_summary, field_name="execution_summary")
        normalized_receipts = tuple(receipts)

        if not normalized_receipts:
            raise FoundationError("execution packet requires at least one receipt")

        for receipt in normalized_receipts:
            if receipt.cycle != cycle:
                raise FoundationError("execution receipts must match packet cycle")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"ix-forge-{cycle}-{normalized_summary}",
                field_name="packet_id",
            ),
            cycle=cycle,
            execution_summary=normalized_summary,
            receipts=normalized_receipts,
        )

    def passed_count(self) -> int:
        """Return the number of successful execution receipts."""
        return sum(1 for receipt in self.receipts if receipt.succeeded())

    def blocked_count(self) -> int:
        """Return the number of blocking execution receipts."""
        return sum(1 for receipt in self.receipts if receipt.blocks_progress())

    def failed_count(self) -> int:
        """Return the number of failed execution receipts."""
        return sum(1 for receipt in self.receipts if receipt.status is ExecutionStatus.FAILED)

    def has_blocker(self) -> bool:
        """Return whether this packet contains any blocking execution receipt."""
        return self.blocked_count() > 0

    def to_artifact(self) -> AgentArtifact:
        """Convert this packet into a shared runtime artifact."""
        return AgentArtifact.create(
            cycle=self.cycle,
            role=AgentRole.FORGE,
            kind=AgentArtifactKind.EXECUTION_RECEIPT,
            summary=f"IX-Forge recorded {len(self.receipts)} execution receipt(s).",
            referenced_digests=tuple(receipt.digest() for receipt in self.receipts),
            data=self.to_payload(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible execution packet representation."""
        receipts_payload: JsonArray = []
        for receipt in self.receipts:
            receipts_payload.append(receipt.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "cycle": self.cycle,
            "execution_summary": self.execution_summary,
            "receipts": receipts_payload,
            "passed_count": self.passed_count(),
            "failed_count": self.failed_count(),
            "blocked_count": self.blocked_count(),
            "has_blocker": self.has_blocker(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this execution packet."""
        return DigestRecord.from_payload(self.to_payload())
