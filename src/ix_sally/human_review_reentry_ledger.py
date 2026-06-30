"""Immutable ledger for IX-Sally human-review reentry receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_reentry import HumanReviewReentryResult, HumanReviewReentryStatus
from ix_sally.orchestration_loop import StageLoopStopReason
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class HumanReviewReentryLedgerEntry:
    """One immutable ledger entry for a certified human-review reentry run."""

    entry_id: CanonicalKey
    sequence: int
    reentry_receipt_digest: DigestRecord
    resume_operation_digest: DigestRecord
    resume_certificate_digest: DigestRecord
    control_plane_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    loop_digest: DigestRecord
    final_stage: RunStage
    stop_reason: StageLoopStopReason
    executed_steps: int
    status: HumanReviewReentryStatus

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        reentry_receipt_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        resume_certificate_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        loop_digest: DigestRecord,
        final_stage: RunStage,
        stop_reason: StageLoopStopReason,
        executed_steps: int,
        status: HumanReviewReentryStatus,
        entry_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryLedgerEntry:
        """Create a normalized human-review reentry ledger entry."""
        if sequence <= 0:
            raise FoundationError("human-review reentry ledger sequence must be positive")
        if executed_steps < 0:
            raise FoundationError(
                "human-review reentry ledger executed_steps must not be negative"
            )

        reentry_receipt_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        resume_certificate_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        loop_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"human-review-reentry-ledger-{sequence}-"
                f"{reentry_receipt_digest.value[:16]}-{after_state_digest.value[:16]}",
                field_name="entry_id",
            ),
            sequence=sequence,
            reentry_receipt_digest=reentry_receipt_digest,
            resume_operation_digest=resume_operation_digest,
            resume_certificate_digest=resume_certificate_digest,
            control_plane_digest=control_plane_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            loop_digest=loop_digest,
            final_stage=final_stage,
            stop_reason=stop_reason,
            executed_steps=executed_steps,
            status=status,
        )

    @classmethod
    def from_result(
        cls,
        *,
        sequence: int,
        result: HumanReviewReentryResult,
    ) -> HumanReviewReentryLedgerEntry:
        """Create a reentry ledger entry from a certified reentry result."""
        return cls.create(
            sequence=sequence,
            reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            resume_certificate_digest=result.receipt.resume_certificate_digest,
            control_plane_digest=result.receipt.control_plane_digest,
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            loop_digest=result.receipt.loop_digest,
            final_stage=result.receipt.final_stage,
            stop_reason=result.receipt.stop_reason,
            executed_steps=result.receipt.executed_steps,
            status=result.receipt.status,
        )

    def changed_state(self) -> bool:
        """Return whether the reentry run changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def stopped_for_external_input(self) -> bool:
        """Return whether this entry stopped because outside input is required."""
        return self.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED

    def matches_status(self, status: HumanReviewReentryStatus) -> bool:
        """Return whether this entry has the requested reentry status."""
        return self.status is status

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether this entry reached the requested final stage."""
        return self.final_stage is stage

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "reentry_receipt_digest": {
                "algorithm": self.reentry_receipt_digest.algorithm,
                "value": self.reentry_receipt_digest.value,
            },
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "resume_certificate_digest": {
                "algorithm": self.resume_certificate_digest.algorithm,
                "value": self.resume_certificate_digest.value,
            },
            "control_plane_digest": {
                "algorithm": self.control_plane_digest.algorithm,
                "value": self.control_plane_digest.value,
            },
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "loop_digest": {
                "algorithm": self.loop_digest.algorithm,
                "value": self.loop_digest.value,
            },
            "final_stage": self.final_stage.value,
            "stop_reason": self.stop_reason.value,
            "executed_steps": self.executed_steps,
            "status": self.status.value,
            "changed_state": self.changed_state(),
            "stopped_for_external_input": self.stopped_for_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this reentry ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryLedger:
    """Immutable ledger of certified human-review reentry runs."""

    entries: tuple[HumanReviewReentryLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[HumanReviewReentryLedgerEntry],
    ) -> HumanReviewReentryLedger:
        """Create a reentry ledger and reject duplicate or out-of-order entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_reentry_receipts: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate human-review reentry ledger sequence: {entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate human-review reentry ledger entry id: {entry.entry_id.value}"
                )
            if entry.reentry_receipt_digest.value in seen_reentry_receipts:
                raise FoundationError(
                    f"duplicate human-review reentry receipt digest: "
                    f"{entry.reentry_receipt_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError("human-review reentry ledger sequences must increase")

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_reentry_receipts.add(entry.reentry_receipt_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: HumanReviewReentryLedgerEntry,
    ) -> HumanReviewReentryLedger:
        """Return a new ledger with an appended reentry entry."""
        return HumanReviewReentryLedger.create((*self.entries, entry))

    def append_result(
        self,
        result: HumanReviewReentryResult,
    ) -> HumanReviewReentryLedger:
        """Return a new ledger with a reentry result recorded at the next sequence."""
        return self.append(
            HumanReviewReentryLedgerEntry.from_result(
                sequence=self.next_sequence(),
                result=result,
            )
        )

    def latest(self) -> HumanReviewReentryLedgerEntry | None:
        """Return the latest reentry entry, if any."""
        if not self.entries:
            return None
        return self.entries[-1]

    def changed_entries(self) -> tuple[HumanReviewReentryLedgerEntry, ...]:
        """Return entries whose reentry run changed the run state."""
        return tuple(entry for entry in self.entries if entry.changed_state())

    def external_input_entries(self) -> tuple[HumanReviewReentryLedgerEntry, ...]:
        """Return entries that stopped for external input."""
        return tuple(entry for entry in self.entries if entry.stopped_for_external_input())

    def entries_by_status(
        self,
        status: HumanReviewReentryStatus,
    ) -> tuple[HumanReviewReentryLedgerEntry, ...]:
        """Return reentry entries matching the requested status."""
        return tuple(entry for entry in self.entries if entry.matches_status(status))

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[HumanReviewReentryLedgerEntry, ...]:
        """Return reentry entries that reached the requested final stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review reentry ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "changed_entry_count": len(self.changed_entries()),
            "external_input_entry_count": len(self.external_input_entries()),
            "advanced_entry_count": len(
                self.entries_by_status(HumanReviewReentryStatus.ADVANCED)
            ),
            "waiting_entry_count": len(
                self.entries_by_status(HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT)
            ),
            "forge_result_processing_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING)
            ),
            "chamber_close_entry_count": len(
                self.entries_for_stage(RunStage.CHAMBER_CLOSE_READY)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review reentry ledger."""
        return DigestRecord.from_payload(self.to_payload())
