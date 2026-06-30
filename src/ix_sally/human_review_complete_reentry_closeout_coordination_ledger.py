"""Ledger for complete IX-Sally human-review reentry closeout coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_complete_reentry_closeout_coordination import (
        CompleteHumanReviewReentryCloseoutCoordinationResult,
    )
    from ix_sally.human_review_control_plane_report import (
        HumanReviewControlPlaneReportStatus,
    )
    from ix_sally.human_review_reentry import HumanReviewReentryStatus
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry:
    """One immutable ledger entry for a complete closeout coordination result."""

    entry_id: CanonicalKey
    sequence: int
    coordination_result_digest: DigestRecord
    coordination_receipt_digest: DigestRecord
    resume_operation_digest: DigestRecord
    complete_reentry_result_digest: DigestRecord
    complete_reentry_receipt_digest: DigestRecord
    closeout_report_digest: DigestRecord
    closeout_workflow_operation_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_control_plane_digest: DigestRecord
    closeout_control_plane_digest: DigestRecord
    after_control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    audit_status: HumanReviewReentryAuditStatus
    report_status: HumanReviewControlPlaneReportStatus
    closeout_status: CompleteHumanReviewReentryCloseoutStatus
    max_steps: int
    executed_steps: int

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        coordination_result_digest: DigestRecord,
        coordination_receipt_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        complete_reentry_result_digest: DigestRecord,
        complete_reentry_receipt_digest: DigestRecord,
        closeout_report_digest: DigestRecord,
        closeout_workflow_operation_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_control_plane_digest: DigestRecord,
        closeout_control_plane_digest: DigestRecord,
        after_control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        audit_status: HumanReviewReentryAuditStatus,
        report_status: HumanReviewControlPlaneReportStatus,
        closeout_status: CompleteHumanReviewReentryCloseoutStatus,
        max_steps: int,
        executed_steps: int,
        entry_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry:
        """Create a normalized closeout coordination ledger entry."""
        if sequence <= 0:
            raise FoundationError(
                "complete reentry closeout coordination ledger sequence "
                "must be positive"
            )
        if max_steps <= 0:
            raise FoundationError(
                "complete reentry closeout coordination ledger max_steps "
                "must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete reentry closeout coordination ledger executed_steps "
                "must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete reentry closeout coordination ledger executed_steps "
                "exceeds max_steps"
            )

        coordination_result_digest.require_algorithm("sha256")
        coordination_receipt_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        complete_reentry_result_digest.require_algorithm("sha256")
        complete_reentry_receipt_digest.require_algorithm("sha256")
        closeout_report_digest.require_algorithm("sha256")
        closeout_workflow_operation_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_control_plane_digest.require_algorithm("sha256")
        closeout_control_plane_digest.require_algorithm("sha256")
        after_control_plane_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-coordination-ledger-{sequence}-"
                f"{coordination_result_digest.value[:16]}-"
                f"{closeout_status.value}",
                field_name="entry_id",
            ),
            sequence=sequence,
            coordination_result_digest=coordination_result_digest,
            coordination_receipt_digest=coordination_receipt_digest,
            resume_operation_digest=resume_operation_digest,
            complete_reentry_result_digest=complete_reentry_result_digest,
            complete_reentry_receipt_digest=complete_reentry_receipt_digest,
            closeout_report_digest=closeout_report_digest,
            closeout_workflow_operation_digest=closeout_workflow_operation_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_control_plane_digest=before_control_plane_digest,
            closeout_control_plane_digest=closeout_control_plane_digest,
            after_control_plane_digest=after_control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            audit_status=audit_status,
            report_status=report_status,
            closeout_status=closeout_status,
            max_steps=max_steps,
            executed_steps=executed_steps,
        )

    @classmethod
    def from_result(
        cls,
        *,
        sequence: int,
        result: CompleteHumanReviewReentryCloseoutCoordinationResult,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry:
        """Create a closeout coordination ledger entry from a result."""
        return cls.create(
            sequence=sequence,
            coordination_result_digest=result.digest(),
            coordination_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            complete_reentry_result_digest=(
                result.receipt.complete_reentry_result_digest
            ),
            complete_reentry_receipt_digest=(
                result.receipt.complete_reentry_receipt_digest
            ),
            closeout_report_digest=result.receipt.closeout_report_digest,
            closeout_workflow_operation_digest=(
                result.receipt.closeout_workflow_operation_digest
            ),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            closeout_control_plane_digest=result.receipt.closeout_control_plane_digest,
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            closeout_status=result.receipt.closeout_status,
            max_steps=result.receipt.max_steps,
            executed_steps=result.receipt.executed_steps,
        )

    def changed_state(self) -> bool:
        """Return whether coordination changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_complete_reentry(self) -> bool:
        """Return whether complete reentry recording changed the control plane."""
        return self.before_control_plane_digest != self.closeout_control_plane_digest

    def recorded_closeout(self) -> bool:
        """Return whether closeout recording changed the control plane."""
        return self.closeout_control_plane_digest != self.after_control_plane_digest

    def accepted(self) -> bool:
        """Return whether closeout coordination accepted the reentry."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED

    def waiting_for_external_input(self) -> bool:
        """Return whether coordination is valid but waiting externally."""
        return (
            self.closeout_status
            is CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def blocked(self) -> bool:
        """Return whether coordination is blocked."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.BLOCKED

    def requires_operator_attention(self) -> bool:
        """Return whether this coordination entry requires operator attention."""
        return self.blocked()

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether this coordination entry reached the requested stage."""
        return self.final_stage is stage

    def matches_closeout_status(
        self,
        status: CompleteHumanReviewReentryCloseoutStatus,
    ) -> bool:
        """Return whether this entry has the requested closeout status."""
        return self.closeout_status is status

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "coordination_result_digest": {
                "algorithm": self.coordination_result_digest.algorithm,
                "value": self.coordination_result_digest.value,
            },
            "coordination_receipt_digest": {
                "algorithm": self.coordination_receipt_digest.algorithm,
                "value": self.coordination_receipt_digest.value,
            },
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "complete_reentry_result_digest": {
                "algorithm": self.complete_reentry_result_digest.algorithm,
                "value": self.complete_reentry_result_digest.value,
            },
            "complete_reentry_receipt_digest": {
                "algorithm": self.complete_reentry_receipt_digest.algorithm,
                "value": self.complete_reentry_receipt_digest.value,
            },
            "closeout_report_digest": {
                "algorithm": self.closeout_report_digest.algorithm,
                "value": self.closeout_report_digest.value,
            },
            "closeout_workflow_operation_digest": {
                "algorithm": self.closeout_workflow_operation_digest.algorithm,
                "value": self.closeout_workflow_operation_digest.value,
            },
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "before_control_plane_digest": {
                "algorithm": self.before_control_plane_digest.algorithm,
                "value": self.before_control_plane_digest.value,
            },
            "closeout_control_plane_digest": {
                "algorithm": self.closeout_control_plane_digest.algorithm,
                "value": self.closeout_control_plane_digest.value,
            },
            "after_control_plane_digest": {
                "algorithm": self.after_control_plane_digest.algorithm,
                "value": self.after_control_plane_digest.value,
            },
            "final_stage": self.final_stage.value,
            "reentry_status": self.reentry_status.value,
            "audit_status": self.audit_status.value,
            "report_status": self.report_status.value,
            "closeout_status": self.closeout_status.value,
            "max_steps": self.max_steps,
            "executed_steps": self.executed_steps,
            "changed_state": self.changed_state(),
            "recorded_complete_reentry": self.recorded_complete_reentry(),
            "recorded_closeout": self.recorded_closeout(),
            "accepted": self.accepted(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "blocked": self.blocked(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutCoordinationLedger:
    """Immutable ledger of complete reentry closeout coordination results."""

    entries: tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry],
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedger:
        """Create a ledger and reject duplicate or unordered coordination entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_result_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate complete reentry closeout coordination ledger "
                    f"sequence: {entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate complete reentry closeout coordination ledger "
                    f"entry id: {entry.entry_id.value}"
                )
            if entry.coordination_result_digest.value in seen_result_digests:
                raise FoundationError(
                    f"duplicate complete reentry closeout coordination result "
                    f"digest: {entry.coordination_result_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "complete reentry closeout coordination ledger sequences "
                    "must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_result_digests.add(entry.coordination_result_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next coordination ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedger:
        """Return a new ledger with an appended coordination entry."""
        return CompleteHumanReviewReentryCloseoutCoordinationLedger.create(
            (*self.entries, entry)
        )

    def append_result(
        self,
        result: CompleteHumanReviewReentryCloseoutCoordinationResult,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedger:
        """Return a new ledger with a coordination result recorded."""
        return self.append(
            CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
                sequence=self.next_sequence(),
                result=result,
            )
        )

    def latest(
        self,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry | None:
        """Return the latest coordination entry, if present."""
        if not self.entries:
            return None
        return self.entries[-1]

    def accepted_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return accepted closeout coordination entries."""
        return tuple(entry for entry in self.entries if entry.accepted())

    def waiting_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return closeout coordination entries waiting for external input."""
        return tuple(entry for entry in self.entries if entry.waiting_for_external_input())

    def blocked_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return blocked closeout coordination entries."""
        return tuple(entry for entry in self.entries if entry.blocked())

    def operator_attention_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return coordination entries requiring operator attention."""
        return tuple(entry for entry in self.entries if entry.requires_operator_attention())

    def changed_state_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return coordination entries that changed run state."""
        return tuple(entry for entry in self.entries if entry.changed_state())

    def recorded_closeout_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return coordination entries whose closeout was recorded."""
        return tuple(entry for entry in self.entries if entry.recorded_closeout())

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return coordination entries that reached the requested stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def entries_for_closeout_status(
        self,
        status: CompleteHumanReviewReentryCloseoutStatus,
    ) -> tuple[CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry, ...]:
        """Return coordination entries matching the requested closeout status."""
        return tuple(
            entry for entry in self.entries if entry.matches_closeout_status(status)
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible closeout coordination ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "accepted_entry_count": len(self.accepted_entries()),
            "waiting_entry_count": len(self.waiting_entries()),
            "blocked_entry_count": len(self.blocked_entries()),
            "operator_attention_entry_count": len(self.operator_attention_entries()),
            "changed_state_entry_count": len(self.changed_state_entries()),
            "recorded_closeout_entry_count": len(self.recorded_closeout_entries()),
            "forge_dispatch_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_DISPATCH)
            ),
            "forge_result_processing_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this closeout coordination ledger."""
        return DigestRecord.from_payload(self.to_payload())
