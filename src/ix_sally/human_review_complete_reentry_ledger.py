"""Immutable ledger for complete IX-Sally human-review reentry results."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_complete_reentry import CompleteHumanReviewReentryResult
    from ix_sally.human_review_control_plane_report import (
        HumanReviewControlPlaneReportStatus,
    )
    from ix_sally.human_review_reentry import HumanReviewReentryStatus
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryLedgerEntry:
    """One immutable ledger entry for a complete human-review reentry result."""

    entry_id: CanonicalKey
    sequence: int
    complete_reentry_result_digest: DigestRecord
    complete_reentry_receipt_digest: DigestRecord
    resume_operation_digest: DigestRecord
    audited_reentry_result_digest: DigestRecord
    audited_reentry_receipt_digest: DigestRecord
    final_workflow_operation_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_control_plane_digest: DigestRecord
    audited_reentry_control_plane_digest: DigestRecord
    after_control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    audit_status: HumanReviewReentryAuditStatus
    report_status: HumanReviewControlPlaneReportStatus
    max_steps: int
    executed_steps: int

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        complete_reentry_result_digest: DigestRecord,
        complete_reentry_receipt_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        audited_reentry_result_digest: DigestRecord,
        audited_reentry_receipt_digest: DigestRecord,
        final_workflow_operation_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_control_plane_digest: DigestRecord,
        audited_reentry_control_plane_digest: DigestRecord,
        after_control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        audit_status: HumanReviewReentryAuditStatus,
        report_status: HumanReviewControlPlaneReportStatus,
        max_steps: int,
        executed_steps: int,
        entry_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryLedgerEntry:
        """Create a normalized complete human-review reentry ledger entry."""
        if sequence <= 0:
            raise FoundationError(
                "complete human-review reentry ledger sequence must be positive"
            )
        if max_steps <= 0:
            raise FoundationError(
                "complete human-review reentry ledger max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete human-review reentry ledger executed_steps must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete human-review reentry ledger executed_steps exceeds max_steps"
            )

        complete_reentry_result_digest.require_algorithm("sha256")
        complete_reentry_receipt_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        audited_reentry_result_digest.require_algorithm("sha256")
        audited_reentry_receipt_digest.require_algorithm("sha256")
        final_workflow_operation_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_control_plane_digest.require_algorithm("sha256")
        audited_reentry_control_plane_digest.require_algorithm("sha256")
        after_control_plane_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"complete-human-review-reentry-ledger-{sequence}-"
                f"{complete_reentry_result_digest.value[:16]}-{report_status.value}",
                field_name="entry_id",
            ),
            sequence=sequence,
            complete_reentry_result_digest=complete_reentry_result_digest,
            complete_reentry_receipt_digest=complete_reentry_receipt_digest,
            resume_operation_digest=resume_operation_digest,
            audited_reentry_result_digest=audited_reentry_result_digest,
            audited_reentry_receipt_digest=audited_reentry_receipt_digest,
            final_workflow_operation_digest=final_workflow_operation_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_control_plane_digest=before_control_plane_digest,
            audited_reentry_control_plane_digest=audited_reentry_control_plane_digest,
            after_control_plane_digest=after_control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            audit_status=audit_status,
            report_status=report_status,
            max_steps=max_steps,
            executed_steps=executed_steps,
        )

    @classmethod
    def from_result(
        cls,
        *,
        sequence: int,
        result: CompleteHumanReviewReentryResult,
    ) -> CompleteHumanReviewReentryLedgerEntry:
        """Create a complete reentry ledger entry from a complete reentry result."""
        return cls.create(
            sequence=sequence,
            complete_reentry_result_digest=result.digest(),
            complete_reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            audited_reentry_result_digest=result.receipt.audited_reentry_result_digest,
            audited_reentry_receipt_digest=result.receipt.audited_reentry_receipt_digest,
            final_workflow_operation_digest=(
                result.receipt.final_workflow_operation_digest
            ),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            audited_reentry_control_plane_digest=(
                result.receipt.audited_reentry_control_plane_digest
            ),
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            max_steps=result.receipt.max_steps,
            executed_steps=result.receipt.executed_steps,
        )

    def changed_state(self) -> bool:
        """Return whether complete reentry changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_reentry_and_audit(self) -> bool:
        """Return whether run/audit recording changed the control plane."""
        return self.before_control_plane_digest != self.audited_reentry_control_plane_digest

    def recorded_complete_audited_reentry(self) -> bool:
        """Return whether final complete reentry recording changed the control plane."""
        return self.audited_reentry_control_plane_digest != self.after_control_plane_digest

    def accepted(self) -> bool:
        """Return whether this complete reentry was accepted."""
        return self.report_status.value in {
            "audited_reentry_accepted",
            "audited_reentry_waiting_for_external_input",
        }

    def failed(self) -> bool:
        """Return whether this complete reentry failed."""
        return self.report_status.value == "audited_reentry_failed"

    def waiting_for_external_input(self) -> bool:
        """Return whether this complete reentry is valid but waiting externally."""
        return self.report_status.value == "audited_reentry_waiting_for_external_input"

    def requires_operator_attention(self) -> bool:
        """Return whether the final report requires operator attention."""
        return self.report_status.value in {
            "audited_reentry_failed",
            "rejection_blocked",
            "deferral_open",
        }

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether complete reentry reached the requested final stage."""
        return self.final_stage is stage

    def matches_report_status(
        self,
        status: HumanReviewControlPlaneReportStatus,
    ) -> bool:
        """Return whether this entry has the requested final report status."""
        return self.report_status.value == status.value

    def matches_reentry_status(
        self,
        status: HumanReviewReentryStatus,
    ) -> bool:
        """Return whether this entry has the requested reentry status."""
        return self.reentry_status.value == status.value

    def matches_audit_status(
        self,
        status: HumanReviewReentryAuditStatus,
    ) -> bool:
        """Return whether this entry has the requested audit status."""
        return self.audit_status.value == status.value

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible complete reentry ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "complete_reentry_result_digest": {
                "algorithm": self.complete_reentry_result_digest.algorithm,
                "value": self.complete_reentry_result_digest.value,
            },
            "complete_reentry_receipt_digest": {
                "algorithm": self.complete_reentry_receipt_digest.algorithm,
                "value": self.complete_reentry_receipt_digest.value,
            },
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "audited_reentry_result_digest": {
                "algorithm": self.audited_reentry_result_digest.algorithm,
                "value": self.audited_reentry_result_digest.value,
            },
            "audited_reentry_receipt_digest": {
                "algorithm": self.audited_reentry_receipt_digest.algorithm,
                "value": self.audited_reentry_receipt_digest.value,
            },
            "final_workflow_operation_digest": {
                "algorithm": self.final_workflow_operation_digest.algorithm,
                "value": self.final_workflow_operation_digest.value,
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
            "audited_reentry_control_plane_digest": {
                "algorithm": self.audited_reentry_control_plane_digest.algorithm,
                "value": self.audited_reentry_control_plane_digest.value,
            },
            "after_control_plane_digest": {
                "algorithm": self.after_control_plane_digest.algorithm,
                "value": self.after_control_plane_digest.value,
            },
            "final_stage": self.final_stage.value,
            "reentry_status": self.reentry_status.value,
            "audit_status": self.audit_status.value,
            "report_status": self.report_status.value,
            "max_steps": self.max_steps,
            "executed_steps": self.executed_steps,
            "changed_state": self.changed_state(),
            "recorded_reentry_and_audit": self.recorded_reentry_and_audit(),
            "recorded_complete_audited_reentry": (
                self.recorded_complete_audited_reentry()
            ),
            "accepted": self.accepted(),
            "failed": self.failed(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryLedger:
    """Immutable ledger of complete audited human-review reentry results."""

    entries: tuple[CompleteHumanReviewReentryLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[CompleteHumanReviewReentryLedgerEntry],
    ) -> CompleteHumanReviewReentryLedger:
        """Create a complete reentry ledger and reject duplicate or unordered entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_result_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate complete human-review reentry ledger sequence: "
                    f"{entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate complete human-review reentry ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.complete_reentry_result_digest.value in seen_result_digests:
                raise FoundationError(
                    f"duplicate complete human-review reentry result digest: "
                    f"{entry.complete_reentry_result_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "complete human-review reentry ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_result_digests.add(entry.complete_reentry_result_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next complete reentry ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: CompleteHumanReviewReentryLedgerEntry,
    ) -> CompleteHumanReviewReentryLedger:
        """Return a new ledger with an appended complete reentry entry."""
        return CompleteHumanReviewReentryLedger.create((*self.entries, entry))

    def append_result(
        self,
        result: CompleteHumanReviewReentryResult,
    ) -> CompleteHumanReviewReentryLedger:
        """Return a new ledger with a complete reentry result recorded."""
        return self.append(
            CompleteHumanReviewReentryLedgerEntry.from_result(
                sequence=self.next_sequence(),
                result=result,
            )
        )

    def latest(self) -> CompleteHumanReviewReentryLedgerEntry | None:
        """Return the latest complete reentry entry, if present."""
        if not self.entries:
            return None
        return self.entries[-1]

    def accepted_entries(self) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries accepted by the complete reentry workflow."""
        return tuple(entry for entry in self.entries if entry.accepted())

    def failed_entries(self) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries that failed the complete reentry workflow."""
        return tuple(entry for entry in self.entries if entry.failed())

    def waiting_entries(self) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries that are valid but waiting for external input."""
        return tuple(entry for entry in self.entries if entry.waiting_for_external_input())

    def operator_attention_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries whose final report requires operator attention."""
        return tuple(entry for entry in self.entries if entry.requires_operator_attention())

    def changed_state_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries whose complete reentry changed run state."""
        return tuple(entry for entry in self.entries if entry.changed_state())

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[CompleteHumanReviewReentryLedgerEntry, ...]:
        """Return entries that reached the requested final stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible complete reentry ledger."""
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
            "failed_entry_count": len(self.failed_entries()),
            "waiting_entry_count": len(self.waiting_entries()),
            "operator_attention_entry_count": len(self.operator_attention_entries()),
            "changed_state_entry_count": len(self.changed_state_entries()),
            "forge_dispatch_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_DISPATCH)
            ),
            "forge_result_processing_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry ledger."""
        return DigestRecord.from_payload(self.to_payload())
