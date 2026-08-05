"""Immutable ledger for complete human-review reentry closeout reports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_complete_reentry_report import (
        CompleteHumanReviewReentryCloseoutReport,
    )
    from ix_sally.human_review_control_plane_report import (
        HumanReviewControlPlaneReportStatus,
    )
    from ix_sally.human_review_reentry import HumanReviewReentryStatus
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutLedgerEntry:
    """One immutable ledger entry for a complete reentry closeout report."""

    entry_id: CanonicalKey
    sequence: int
    closeout_report_digest: DigestRecord
    complete_reentry_result_digest: DigestRecord
    complete_reentry_receipt_digest: DigestRecord
    final_workflow_operation_digest: DigestRecord
    state_digest: DigestRecord
    control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    audit_status: HumanReviewReentryAuditStatus
    report_status: HumanReviewControlPlaneReportStatus
    closeout_status: CompleteHumanReviewReentryCloseoutStatus
    max_steps: int
    executed_steps: int
    reentry_count: int
    reentry_audit_count: int
    audited_reentry_count: int
    complete_reentry_count: int
    finding_count: int
    blocking_finding_count: int

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        closeout_report_digest: DigestRecord,
        complete_reentry_result_digest: DigestRecord,
        complete_reentry_receipt_digest: DigestRecord,
        final_workflow_operation_digest: DigestRecord,
        state_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        audit_status: HumanReviewReentryAuditStatus,
        report_status: HumanReviewControlPlaneReportStatus,
        closeout_status: CompleteHumanReviewReentryCloseoutStatus,
        max_steps: int,
        executed_steps: int,
        reentry_count: int,
        reentry_audit_count: int,
        audited_reentry_count: int,
        complete_reentry_count: int,
        finding_count: int,
        blocking_finding_count: int,
        entry_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutLedgerEntry:
        """Create a normalized complete reentry closeout ledger entry."""
        if sequence <= 0:
            raise FoundationError(
                "complete human-review reentry closeout ledger sequence "
                "must be positive"
            )
        if max_steps <= 0:
            raise FoundationError(
                "complete human-review reentry closeout ledger max_steps "
                "must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete human-review reentry closeout ledger executed_steps "
                "must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete human-review reentry closeout ledger executed_steps "
                "exceeds max_steps"
            )

        for field_name, value in {
            "reentry_count": reentry_count,
            "reentry_audit_count": reentry_audit_count,
            "audited_reentry_count": audited_reentry_count,
            "complete_reentry_count": complete_reentry_count,
            "finding_count": finding_count,
            "blocking_finding_count": blocking_finding_count,
        }.items():
            if value < 0:
                raise FoundationError(
                    f"complete human-review reentry closeout ledger {field_name} "
                    "must not be negative"
                )

        if blocking_finding_count > finding_count:
            raise FoundationError(
                "complete human-review reentry closeout ledger "
                "blocking_finding_count exceeds finding_count"
            )
        if (
            blocking_finding_count > 0
            and closeout_status is not CompleteHumanReviewReentryCloseoutStatus.BLOCKED
        ):
            raise FoundationError(
                "complete human-review reentry closeout ledger blocking findings "
                "must have blocked status"
            )

        closeout_report_digest.require_algorithm("sha256")
        complete_reentry_result_digest.require_algorithm("sha256")
        complete_reentry_receipt_digest.require_algorithm("sha256")
        final_workflow_operation_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-ledger-{sequence}-"
                f"{closeout_report_digest.value[:16]}-{closeout_status.value}",
                field_name="entry_id",
            ),
            sequence=sequence,
            closeout_report_digest=closeout_report_digest,
            complete_reentry_result_digest=complete_reentry_result_digest,
            complete_reentry_receipt_digest=complete_reentry_receipt_digest,
            final_workflow_operation_digest=final_workflow_operation_digest,
            state_digest=state_digest,
            control_plane_digest=control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            audit_status=audit_status,
            report_status=report_status,
            closeout_status=closeout_status,
            max_steps=max_steps,
            executed_steps=executed_steps,
            reentry_count=reentry_count,
            reentry_audit_count=reentry_audit_count,
            audited_reentry_count=audited_reentry_count,
            complete_reentry_count=complete_reentry_count,
            finding_count=finding_count,
            blocking_finding_count=blocking_finding_count,
        )

    @classmethod
    def from_report(
        cls,
        *,
        sequence: int,
        report: CompleteHumanReviewReentryCloseoutReport,
    ) -> CompleteHumanReviewReentryCloseoutLedgerEntry:
        """Create a closeout ledger entry from a closeout report."""
        return cls.create(
            sequence=sequence,
            closeout_report_digest=report.digest(),
            complete_reentry_result_digest=report.complete_reentry_result_digest,
            complete_reentry_receipt_digest=report.complete_reentry_receipt_digest,
            final_workflow_operation_digest=report.final_workflow_operation_digest,
            state_digest=report.state_digest,
            control_plane_digest=report.control_plane_digest,
            final_stage=report.final_stage,
            reentry_status=report.reentry_status,
            audit_status=report.audit_status,
            report_status=report.report_status,
            closeout_status=report.closeout_status,
            max_steps=report.max_steps,
            executed_steps=report.executed_steps,
            reentry_count=report.reentry_count,
            reentry_audit_count=report.reentry_audit_count,
            audited_reentry_count=report.audited_reentry_count,
            complete_reentry_count=report.complete_reentry_count,
            finding_count=len(report.findings),
            blocking_finding_count=len(report.blocking_findings()),
        )

    def accepted(self) -> bool:
        """Return whether this closeout entry was accepted."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED

    def waiting_for_external_input(self) -> bool:
        """Return whether this closeout entry is valid but waiting externally."""
        return (
            self.closeout_status
            is CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def blocked(self) -> bool:
        """Return whether this closeout entry is blocked."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.BLOCKED

    def has_blocking_findings(self) -> bool:
        """Return whether the closeout entry has blocking findings."""
        return self.blocking_finding_count > 0

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether this closeout entry reached the requested final stage."""
        return self.final_stage is stage

    def matches_closeout_status(
        self,
        status: CompleteHumanReviewReentryCloseoutStatus,
    ) -> bool:
        """Return whether this entry has the requested closeout status."""
        return self.closeout_status is status

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible closeout ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "closeout_report_digest": {
                "algorithm": self.closeout_report_digest.algorithm,
                "value": self.closeout_report_digest.value,
            },
            "complete_reentry_result_digest": {
                "algorithm": self.complete_reentry_result_digest.algorithm,
                "value": self.complete_reentry_result_digest.value,
            },
            "complete_reentry_receipt_digest": {
                "algorithm": self.complete_reentry_receipt_digest.algorithm,
                "value": self.complete_reentry_receipt_digest.value,
            },
            "final_workflow_operation_digest": {
                "algorithm": self.final_workflow_operation_digest.algorithm,
                "value": self.final_workflow_operation_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "control_plane_digest": {
                "algorithm": self.control_plane_digest.algorithm,
                "value": self.control_plane_digest.value,
            },
            "final_stage": self.final_stage.value,
            "reentry_status": self.reentry_status.value,
            "audit_status": self.audit_status.value,
            "report_status": self.report_status.value,
            "closeout_status": self.closeout_status.value,
            "max_steps": self.max_steps,
            "executed_steps": self.executed_steps,
            "reentry_count": self.reentry_count,
            "reentry_audit_count": self.reentry_audit_count,
            "audited_reentry_count": self.audited_reentry_count,
            "complete_reentry_count": self.complete_reentry_count,
            "finding_count": self.finding_count,
            "blocking_finding_count": self.blocking_finding_count,
            "accepted": self.accepted(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "blocked": self.blocked(),
            "has_blocking_findings": self.has_blocking_findings(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this closeout ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutLedger:
    """Immutable ledger of complete human-review reentry closeout reports."""

    entries: tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[CompleteHumanReviewReentryCloseoutLedgerEntry],
    ) -> CompleteHumanReviewReentryCloseoutLedger:
        """Create a closeout ledger and reject duplicate or unordered entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_report_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate complete reentry closeout ledger sequence: "
                    f"{entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate complete reentry closeout ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.closeout_report_digest.value in seen_report_digests:
                raise FoundationError(
                    f"duplicate complete reentry closeout report digest: "
                    f"{entry.closeout_report_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "complete reentry closeout ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_report_digests.add(entry.closeout_report_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next closeout ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: CompleteHumanReviewReentryCloseoutLedgerEntry,
    ) -> CompleteHumanReviewReentryCloseoutLedger:
        """Return a new closeout ledger with an appended entry."""
        return CompleteHumanReviewReentryCloseoutLedger.create((*self.entries, entry))

    def append_report(
        self,
        report: CompleteHumanReviewReentryCloseoutReport,
    ) -> CompleteHumanReviewReentryCloseoutLedger:
        """Return a new closeout ledger with a report recorded."""
        return self.append(
            CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
                sequence=self.next_sequence(),
                report=report,
            )
        )

    def latest(self) -> CompleteHumanReviewReentryCloseoutLedgerEntry | None:
        """Return the latest closeout ledger entry, if present."""
        if not self.entries:
            return None
        return self.entries[-1]

    def accepted_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return accepted closeout entries."""
        return tuple(entry for entry in self.entries if entry.accepted())

    def waiting_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return closeout entries waiting for external input."""
        return tuple(entry for entry in self.entries if entry.waiting_for_external_input())

    def blocked_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return blocked closeout entries."""
        return tuple(entry for entry in self.entries if entry.blocked())

    def blocking_finding_entries(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return closeout entries with blocking findings."""
        return tuple(entry for entry in self.entries if entry.has_blocking_findings())

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return closeout entries that reached the requested stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def entries_for_closeout_status(
        self,
        status: CompleteHumanReviewReentryCloseoutStatus,
    ) -> tuple[CompleteHumanReviewReentryCloseoutLedgerEntry, ...]:
        """Return closeout entries matching the requested status."""
        return tuple(
            entry for entry in self.entries if entry.matches_closeout_status(status)
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible closeout ledger."""
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
            "blocking_finding_entry_count": len(self.blocking_finding_entries()),
            "forge_dispatch_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_DISPATCH)
            ),
            "forge_result_processing_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING)
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry closeout ledger."""
        return DigestRecord.from_payload(self.to_payload())
