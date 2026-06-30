"""Immutable ledger for audited IX-Sally human-review reentry results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_audited_reentry import AuditedHumanReviewReentryResult


@dataclass(frozen=True, slots=True)
class AuditedHumanReviewReentryLedgerEntry:
    """One immutable ledger entry for a fully audited human-review reentry."""

    entry_id: CanonicalKey
    sequence: int
    audited_reentry_result_digest: DigestRecord
    audited_reentry_receipt_digest: DigestRecord
    resume_operation_digest: DigestRecord
    reentry_coordination_digest: DigestRecord
    audit_report_digest: DigestRecord
    audit_workflow_operation_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_control_plane_digest: DigestRecord
    reentry_control_plane_digest: DigestRecord
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
        audited_reentry_result_digest: DigestRecord,
        audited_reentry_receipt_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        reentry_coordination_digest: DigestRecord,
        audit_report_digest: DigestRecord,
        audit_workflow_operation_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_control_plane_digest: DigestRecord,
        reentry_control_plane_digest: DigestRecord,
        after_control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        audit_status: HumanReviewReentryAuditStatus,
        report_status: HumanReviewControlPlaneReportStatus,
        max_steps: int,
        executed_steps: int,
        entry_id: CanonicalKey | None = None,
    ) -> AuditedHumanReviewReentryLedgerEntry:
        """Create a normalized audited human-review reentry ledger entry."""
        if sequence <= 0:
            raise FoundationError(
                "audited human-review reentry ledger sequence must be positive"
            )
        if max_steps <= 0:
            raise FoundationError(
                "audited human-review reentry ledger max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "audited human-review reentry ledger executed_steps must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "audited human-review reentry ledger executed_steps exceeds max_steps"
            )

        audited_reentry_result_digest.require_algorithm("sha256")
        audited_reentry_receipt_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        reentry_coordination_digest.require_algorithm("sha256")
        audit_report_digest.require_algorithm("sha256")
        audit_workflow_operation_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_control_plane_digest.require_algorithm("sha256")
        reentry_control_plane_digest.require_algorithm("sha256")
        after_control_plane_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"audited-human-review-reentry-ledger-{sequence}-"
                f"{audited_reentry_result_digest.value[:16]}-{audit_status.value}",
                field_name="entry_id",
            ),
            sequence=sequence,
            audited_reentry_result_digest=audited_reentry_result_digest,
            audited_reentry_receipt_digest=audited_reentry_receipt_digest,
            resume_operation_digest=resume_operation_digest,
            reentry_coordination_digest=reentry_coordination_digest,
            audit_report_digest=audit_report_digest,
            audit_workflow_operation_digest=audit_workflow_operation_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_control_plane_digest=before_control_plane_digest,
            reentry_control_plane_digest=reentry_control_plane_digest,
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
        result: AuditedHumanReviewReentryResult,
    ) -> AuditedHumanReviewReentryLedgerEntry:
        """Create an audited reentry ledger entry from an audited reentry result."""
        return cls.create(
            sequence=sequence,
            audited_reentry_result_digest=result.digest(),
            audited_reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            reentry_coordination_digest=result.receipt.reentry_coordination_digest,
            audit_report_digest=result.receipt.audit_report_digest,
            audit_workflow_operation_digest=(
                result.receipt.audit_workflow_operation_digest
            ),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            reentry_control_plane_digest=result.receipt.reentry_control_plane_digest,
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            max_steps=result.receipt.max_steps,
            executed_steps=result.receipt.executed_steps,
        )

    def changed_state(self) -> bool:
        """Return whether audited reentry changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_reentry(self) -> bool:
        """Return whether reentry recording changed the control plane."""
        return self.before_control_plane_digest != self.reentry_control_plane_digest

    def recorded_audit(self) -> bool:
        """Return whether audit recording changed the control plane."""
        return self.reentry_control_plane_digest != self.after_control_plane_digest

    def accepted(self) -> bool:
        """Return whether the audited reentry was accepted."""
        return self.audit_status in {
            HumanReviewReentryAuditStatus.PASSED,
            HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT,
        }

    def failed(self) -> bool:
        """Return whether the audited reentry failed audit."""
        return self.audit_status is HumanReviewReentryAuditStatus.FAILED

    def waiting_for_external_input(self) -> bool:
        """Return whether audited reentry is valid but waiting externally."""
        return (
            self.audit_status
            is HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def requires_operator_attention(self) -> bool:
        """Return whether the final report status requires operator attention."""
        return self.report_status in {
            HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED,
            HumanReviewControlPlaneReportStatus.DEFERRAL_OPEN,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_FAILED,
        }

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether audited reentry reached the requested final stage."""
        return self.final_stage is stage

    def matches_audit_status(
        self,
        status: HumanReviewReentryAuditStatus,
    ) -> bool:
        """Return whether this entry has the requested audit status."""
        return self.audit_status is status

    def matches_reentry_status(
        self,
        status: HumanReviewReentryStatus,
    ) -> bool:
        """Return whether this entry has the requested reentry status."""
        return self.reentry_status is status

    def matches_report_status(
        self,
        status: HumanReviewControlPlaneReportStatus,
    ) -> bool:
        """Return whether this entry has the requested report status."""
        return self.report_status is status

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audited reentry ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "audited_reentry_result_digest": {
                "algorithm": self.audited_reentry_result_digest.algorithm,
                "value": self.audited_reentry_result_digest.value,
            },
            "audited_reentry_receipt_digest": {
                "algorithm": self.audited_reentry_receipt_digest.algorithm,
                "value": self.audited_reentry_receipt_digest.value,
            },
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "reentry_coordination_digest": {
                "algorithm": self.reentry_coordination_digest.algorithm,
                "value": self.reentry_coordination_digest.value,
            },
            "audit_report_digest": {
                "algorithm": self.audit_report_digest.algorithm,
                "value": self.audit_report_digest.value,
            },
            "audit_workflow_operation_digest": {
                "algorithm": self.audit_workflow_operation_digest.algorithm,
                "value": self.audit_workflow_operation_digest.value,
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
            "reentry_control_plane_digest": {
                "algorithm": self.reentry_control_plane_digest.algorithm,
                "value": self.reentry_control_plane_digest.value,
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
            "recorded_reentry": self.recorded_reentry(),
            "recorded_audit": self.recorded_audit(),
            "accepted": self.accepted(),
            "failed": self.failed(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audited reentry ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuditedHumanReviewReentryLedger:
    """Immutable ledger of fully audited human-review reentry results."""

    entries: tuple[AuditedHumanReviewReentryLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[AuditedHumanReviewReentryLedgerEntry],
    ) -> AuditedHumanReviewReentryLedger:
        """Create an audited reentry ledger and reject duplicate or unordered entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_result_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate audited human-review reentry ledger sequence: "
                    f"{entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate audited human-review reentry ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.audited_reentry_result_digest.value in seen_result_digests:
                raise FoundationError(
                    f"duplicate audited human-review reentry result digest: "
                    f"{entry.audited_reentry_result_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "audited human-review reentry ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_result_digests.add(entry.audited_reentry_result_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next audited reentry ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: AuditedHumanReviewReentryLedgerEntry,
    ) -> AuditedHumanReviewReentryLedger:
        """Return a new ledger with an appended audited reentry entry."""
        return AuditedHumanReviewReentryLedger.create((*self.entries, entry))

    def append_result(
        self,
        result: AuditedHumanReviewReentryResult,
    ) -> AuditedHumanReviewReentryLedger:
        """Return a new ledger with an audited reentry result recorded."""
        return self.append(
            AuditedHumanReviewReentryLedgerEntry.from_result(
                sequence=self.next_sequence(),
                result=result,
            )
        )

    def latest(self) -> AuditedHumanReviewReentryLedgerEntry | None:
        """Return the latest audited reentry entry, if present."""
        if not self.entries:
            return None
        return self.entries[-1]

    def accepted_entries(self) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries accepted by the audit layer."""
        return tuple(entry for entry in self.entries if entry.accepted())

    def failed_entries(self) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries that failed the audit layer."""
        return tuple(entry for entry in self.entries if entry.failed())

    def waiting_entries(self) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries validly waiting for external input."""
        return tuple(entry for entry in self.entries if entry.waiting_for_external_input())

    def operator_attention_entries(
        self,
    ) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries whose final report requires operator attention."""
        return tuple(entry for entry in self.entries if entry.requires_operator_attention())

    def changed_state_entries(self) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries whose audited reentry changed the run state."""
        return tuple(entry for entry in self.entries if entry.changed_state())

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries that reached the requested final stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def entries_for_audit_status(
        self,
        status: HumanReviewReentryAuditStatus,
    ) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries matching an audit status."""
        return tuple(entry for entry in self.entries if entry.matches_audit_status(status))

    def entries_for_reentry_status(
        self,
        status: HumanReviewReentryStatus,
    ) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries matching a reentry status."""
        return tuple(entry for entry in self.entries if entry.matches_reentry_status(status))

    def entries_for_report_status(
        self,
        status: HumanReviewControlPlaneReportStatus,
    ) -> tuple[AuditedHumanReviewReentryLedgerEntry, ...]:
        """Return entries matching a control-plane report status."""
        return tuple(entry for entry in self.entries if entry.matches_report_status(status))

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audited reentry ledger."""
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
            "passed_audit_entry_count": len(
                self.entries_for_audit_status(HumanReviewReentryAuditStatus.PASSED)
            ),
            "waiting_audit_entry_count": len(
                self.entries_for_audit_status(
                    HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
                )
            ),
            "advanced_reentry_entry_count": len(
                self.entries_for_reentry_status(HumanReviewReentryStatus.ADVANCED)
            ),
            "waiting_reentry_entry_count": len(
                self.entries_for_reentry_status(
                    HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
                )
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audited reentry ledger."""
        return DigestRecord.from_payload(self.to_payload())
