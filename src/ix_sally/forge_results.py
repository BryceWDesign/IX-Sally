"""Forge result records for dispatched IX-Sally execution outcomes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.execution_queue import ExecutionQueueItem, ExecutionQueueStatus
from ix_sally.foundation import CanonicalKey, FoundationError, require_optional_text, require_text


class ForgeResultStatus(StrEnum):
    """Status assigned to a dispatched Forge execution result."""

    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ForgeResultRecord:
    """A receipt-grade result for a dispatched IX-Forge queue item."""

    result_id: CanonicalKey
    cycle: int
    queue_item_digest: DigestRecord
    action_id: CanonicalKey
    action_digest: DigestRecord
    executed_by: AgentRole
    status: ForgeResultStatus
    summary: str
    observed_output: str | None = None
    failure_reason: str | None = None
    boundary_note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        queue_item_digest: DigestRecord,
        action_id: CanonicalKey,
        action_digest: DigestRecord,
        status: ForgeResultStatus,
        summary: str,
        executed_by: AgentRole = AgentRole.FORGE,
        observed_output: str | None = None,
        failure_reason: str | None = None,
        boundary_note: str | None = None,
        result_id: CanonicalKey | None = None,
    ) -> ForgeResultRecord:
        """Create a normalized Forge result record."""
        if cycle < 0:
            raise FoundationError("Forge result cycle must not be negative")

        queue_item_digest.require_algorithm("sha256")
        action_digest.require_algorithm("sha256")
        normalized_summary = require_text(summary, field_name="summary")
        normalized_output = require_optional_text(
            observed_output,
            field_name="observed_output",
        )
        normalized_failure = require_optional_text(
            failure_reason,
            field_name="failure_reason",
        )
        normalized_boundary = require_optional_text(
            boundary_note,
            field_name="boundary_note",
        )

        if status is ForgeResultStatus.FAILED and normalized_failure is None:
            raise FoundationError("failed Forge results require a failure reason")

        if status is ForgeResultStatus.BLOCKED and normalized_boundary is None:
            raise FoundationError("blocked Forge results require a boundary note")

        if status is ForgeResultStatus.PASSED and normalized_failure is not None:
            raise FoundationError("passed Forge results must not carry a failure reason")

        return cls(
            result_id=result_id
            or CanonicalKey.from_text(
                f"{cycle}-{executed_by.value}-{action_id.value}-{status.value}",
                field_name="result_id",
            ),
            cycle=cycle,
            queue_item_digest=queue_item_digest,
            action_id=action_id,
            action_digest=action_digest,
            executed_by=executed_by,
            status=status,
            summary=normalized_summary,
            observed_output=normalized_output,
            failure_reason=normalized_failure,
            boundary_note=normalized_boundary,
        )

    @classmethod
    def from_dispatched_item(
        cls,
        *,
        item: ExecutionQueueItem,
        action: BoundedActionRecord,
        status: ForgeResultStatus,
        summary: str,
        observed_output: str | None = None,
        failure_reason: str | None = None,
        boundary_note: str | None = None,
    ) -> ForgeResultRecord:
        """Create a Forge result from a dispatched queue item and matching action."""
        if item.status is not ExecutionQueueStatus.DISPATCHED:
            raise FoundationError("Forge results require a dispatched execution queue item")

        if item.action_id != action.action_id:
            raise FoundationError("Forge result queue item must match bounded action id")

        return cls.create(
            cycle=item.cycle,
            queue_item_digest=item.digest(),
            action_id=item.action_id,
            action_digest=action.digest(),
            executed_by=item.dispatch_role,
            status=status,
            summary=summary,
            observed_output=observed_output,
            failure_reason=failure_reason,
            boundary_note=boundary_note,
        )

    def succeeded(self) -> bool:
        """Return whether Forge execution passed."""
        return self.status is ForgeResultStatus.PASSED

    def failed(self) -> bool:
        """Return whether Forge execution failed."""
        return self.status is ForgeResultStatus.FAILED

    def blocked(self) -> bool:
        """Return whether Forge execution was blocked by a boundary."""
        return self.status is ForgeResultStatus.BLOCKED

    def requires_human_review(self) -> bool:
        """Return whether this result requires human review."""
        return self.status in {ForgeResultStatus.FAILED, ForgeResultStatus.BLOCKED}

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result representation."""
        return {
            "result_id": self.result_id.value,
            "cycle": self.cycle,
            "queue_item_digest": {
                "algorithm": self.queue_item_digest.algorithm,
                "value": self.queue_item_digest.value,
            },
            "action_id": self.action_id.value,
            "action_digest": {
                "algorithm": self.action_digest.algorithm,
                "value": self.action_digest.value,
            },
            "executed_by": self.executed_by.value,
            "status": self.status.value,
            "summary": self.summary,
            "observed_output": self.observed_output,
            "failure_reason": self.failure_reason,
            "boundary_note": self.boundary_note,
            "succeeded": self.succeeded(),
            "failed": self.failed(),
            "blocked": self.blocked(),
            "requires_human_review": self.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeResultLedger:
    """Immutable ledger of Forge execution results."""

    results: tuple[ForgeResultRecord, ...]

    @classmethod
    def create(cls, results: Iterable[ForgeResultRecord]) -> ForgeResultLedger:
        """Create a Forge result ledger and reject duplicate result identifiers."""
        normalized = tuple(results)
        seen: set[str] = set()

        for result in normalized:
            if result.result_id.value in seen:
                raise FoundationError(f"duplicate Forge result id: {result.result_id.value}")
            seen.add(result.result_id.value)

        return cls(results=normalized)

    def append(self, result: ForgeResultRecord) -> ForgeResultLedger:
        """Return a new ledger with an appended Forge result."""
        return ForgeResultLedger.create((*self.results, result))

    def passed_results(self) -> tuple[ForgeResultRecord, ...]:
        """Return passed Forge results."""
        return tuple(result for result in self.results if result.succeeded())

    def failed_results(self) -> tuple[ForgeResultRecord, ...]:
        """Return failed Forge results."""
        return tuple(result for result in self.results if result.failed())

    def blocked_results(self) -> tuple[ForgeResultRecord, ...]:
        """Return boundary-blocked Forge results."""
        return tuple(result for result in self.results if result.blocked())

    def human_review_results(self) -> tuple[ForgeResultRecord, ...]:
        """Return Forge results requiring human review."""
        return tuple(result for result in self.results if result.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result ledger representation."""
        result_payload: JsonArray = []
        for result in self.results:
            result_payload.append(result.to_payload())

        return {
            "results": result_payload,
            "passed_count": len(self.passed_results()),
            "failed_count": len(self.failed_results()),
            "blocked_count": len(self.blocked_results()),
            "human_review_count": len(self.human_review_results()),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result ledger."""
        return DigestRecord.from_payload(self.to_payload())
