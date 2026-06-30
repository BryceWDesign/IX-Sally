"""Immutable ledger for IX-Sally human-review reentry audit reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_reentry import HumanReviewReentryStatus
    from ix_sally.human_review_reentry_audit import (
        HumanReviewReentryAuditReport,
        HumanReviewReentryAuditStatus,
    )


@dataclass(frozen=True, slots=True)
class HumanReviewReentryAuditLedgerEntry:
    """One immutable ledger entry for a human-review reentry audit report."""

    entry_id: CanonicalKey
    sequence: int
    audit_report_digest: DigestRecord
    coordination_digest: DigestRecord
    resume_operation_digest: DigestRecord
    reentry_result_digest: DigestRecord
    workflow_operation_digest: DigestRecord
    state_digest: DigestRecord
    control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    audit_status: HumanReviewReentryAuditStatus
    finding_count: int
    blocking_finding_count: int
    warning_finding_count: int
    info_finding_count: int

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        audit_report_digest: DigestRecord,
        coordination_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        reentry_result_digest: DigestRecord,
        workflow_operation_digest: DigestRecord,
        state_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        audit_status: HumanReviewReentryAuditStatus,
        finding_count: int,
        blocking_finding_count: int,
        warning_finding_count: int,
        info_finding_count: int,
        entry_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryAuditLedgerEntry:
        """Create a normalized human-review reentry audit ledger entry."""
        if sequence <= 0:
            raise FoundationError(
                "human-review reentry audit ledger sequence must be positive"
            )

        for field_name, value in {
            "finding_count": finding_count,
            "blocking_finding_count": blocking_finding_count,
            "warning_finding_count": warning_finding_count,
            "info_finding_count": info_finding_count,
        }.items():
            if value < 0:
                raise FoundationError(
                    f"human-review reentry audit ledger {field_name} "
                    "must not be negative"
                )

        if (
            blocking_finding_count + warning_finding_count + info_finding_count
            != finding_count
        ):
            raise FoundationError(
                "human-review reentry audit ledger finding subtotals must equal "
                "finding_count"
            )

        audit_report_digest.require_algorithm("sha256")
        coordination_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        reentry_result_digest.require_algorithm("sha256")
        workflow_operation_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"human-review-reentry-audit-ledger-{sequence}-"
                f"{audit_report_digest.value[:16]}-{audit_status.value}",
                field_name="entry_id",
            ),
            sequence=sequence,
            audit_report_digest=audit_report_digest,
            coordination_digest=coordination_digest,
            resume_operation_digest=resume_operation_digest,
            reentry_result_digest=reentry_result_digest,
            workflow_operation_digest=workflow_operation_digest,
            state_digest=state_digest,
            control_plane_digest=control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            audit_status=audit_status,
            finding_count=finding_count,
            blocking_finding_count=blocking_finding_count,
            warning_finding_count=warning_finding_count,
            info_finding_count=info_finding_count,
        )

    @classmethod
    def from_report(
        cls,
        *,
        sequence: int,
        report: HumanReviewReentryAuditReport,
    ) -> HumanReviewReentryAuditLedgerEntry:
        """Create a reentry audit ledger entry from an audit report."""
        return cls.create(
            sequence=sequence,
            audit_report_digest=report.digest(),
            coordination_digest=report.coordination_digest,
            resume_operation_digest=report.resume_operation_digest,
            reentry_result_digest=report.reentry_result_digest,
            workflow_operation_digest=report.workflow_operation_digest,
            state_digest=report.state_digest,
            control_plane_digest=report.control_plane_digest,
            final_stage=report.final_stage,
            reentry_status=report.reentry_status,
            audit_status=report.status,
            finding_count=len(report.findings),
            blocking_finding_count=len(report.blocking_findings()),
            warning_finding_count=len(report.warning_findings()),
            info_finding_count=len(report.info_findings()),
        )

    def passed(self) -> bool:
        """Return whether this ledger entry records a passed audit."""
        return self.audit_status.value == "passed"

    def failed(self) -> bool:
        """Return whether this ledger entry records a failed audit."""
        return self.audit_status.value == "failed"

    def waiting_for_external_input(self) -> bool:
        """Return whether this ledger entry records valid waiting reentry."""
        return self.audit_status.value == "waiting_for_external_input"

    def has_blocking_findings(self) -> bool:
        """Return whether the audit entry contains blocking findings."""
        return self.blocking_finding_count > 0

    def has_warnings(self) -> bool:
        """Return whether the audit entry contains warning findings."""
        return self.warning_finding_count > 0

    def reached_stage(self, stage: RunStage) -> bool:
        """Return whether the audited reentry reached the requested final stage."""
        return self.final_stage is stage

    def matches_reentry_status(self, status: HumanReviewReentryStatus) -> bool:
        """Return whether the audited reentry had the requested reentry status."""
        return self.reentry_status.value == status.value

    def matches_audit_status_value(self, status_value: str) -> bool:
        """Return whether this entry has the requested audit status value."""
        return self.audit_status.value == status_value

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry audit ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "audit_report_digest": {
                "algorithm": self.audit_report_digest.algorithm,
                "value": self.audit_report_digest.value,
            },
            "coordination_digest": {
                "algorithm": self.coordination_digest.algorithm,
                "value": self.coordination_digest.value,
            },
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "reentry_result_digest": {
                "algorithm": self.reentry_result_digest.algorithm,
                "value": self.reentry_result_digest.value,
            },
            "workflow_operation_digest": {
                "algorithm": self.workflow_operation_digest.algorithm,
                "value": self.workflow_operation_digest.value,
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
            "finding_count": self.finding_count,
            "blocking_finding_count": self.blocking_finding_count,
            "warning_finding_count": self.warning_finding_count,
            "info_finding_count": self.info_finding_count,
            "passed": self.passed(),
            "failed": self.failed(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "has_blocking_findings": self.has_blocking_findings(),
            "has_warnings": self.has_warnings(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audit ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryAuditLedger:
    """Immutable ledger of human-review reentry audit reports."""

    entries: tuple[HumanReviewReentryAuditLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[HumanReviewReentryAuditLedgerEntry],
    ) -> HumanReviewReentryAuditLedger:
        """Create a reentry audit ledger and reject duplicates or bad ordering."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_report_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate human-review reentry audit ledger sequence: "
                    f"{entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate human-review reentry audit ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.audit_report_digest.value in seen_report_digests:
                raise FoundationError(
                    f"duplicate human-review reentry audit report digest: "
                    f"{entry.audit_report_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "human-review reentry audit ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_report_digests.add(entry.audit_report_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next audit ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: HumanReviewReentryAuditLedgerEntry,
    ) -> HumanReviewReentryAuditLedger:
        """Return a new audit ledger with an appended entry."""
        return HumanReviewReentryAuditLedger.create((*self.entries, entry))

    def append_report(
        self,
        report: HumanReviewReentryAuditReport,
    ) -> HumanReviewReentryAuditLedger:
        """Return a new audit ledger with an audit report recorded."""
        return self.append(
            HumanReviewReentryAuditLedgerEntry.from_report(
                sequence=self.next_sequence(),
                report=report,
            )
        )

    def latest(self) -> HumanReviewReentryAuditLedgerEntry | None:
        """Return the latest audit ledger entry, if present."""
        if not self.entries:
            return None
        return self.entries[-1]

    def passed_entries(self) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return entries that recorded passed audits."""
        return tuple(entry for entry in self.entries if entry.passed())

    def failed_entries(self) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return entries that recorded failed audits."""
        return tuple(entry for entry in self.entries if entry.failed())

    def waiting_entries(self) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return entries that recorded valid waiting-for-input reentries."""
        return tuple(entry for entry in self.entries if entry.waiting_for_external_input())

    def blocking_entries(self) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return entries with blocking audit findings."""
        return tuple(entry for entry in self.entries if entry.has_blocking_findings())

    def warning_entries(self) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return entries with warning audit findings."""
        return tuple(entry for entry in self.entries if entry.has_warnings())

    def entries_for_stage(
        self,
        stage: RunStage,
    ) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return audit entries whose reentry reached the requested stage."""
        return tuple(entry for entry in self.entries if entry.reached_stage(stage))

    def entries_for_reentry_status(
        self,
        status: HumanReviewReentryStatus,
    ) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return audit entries whose reentry had the requested status."""
        return tuple(entry for entry in self.entries if entry.matches_reentry_status(status))

    def entries_by_audit_status_value(
        self,
        status_value: str,
    ) -> tuple[HumanReviewReentryAuditLedgerEntry, ...]:
        """Return audit entries whose audit status value matches."""
        return tuple(
            entry for entry in self.entries if entry.matches_audit_status_value(status_value)
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review reentry audit ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "passed_entry_count": len(self.passed_entries()),
            "failed_entry_count": len(self.failed_entries()),
            "waiting_entry_count": len(self.waiting_entries()),
            "blocking_entry_count": len(self.blocking_entries()),
            "warning_entry_count": len(self.warning_entries()),
            "forge_dispatch_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_DISPATCH)
            ),
            "forge_result_processing_entry_count": len(
                self.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING)
            ),
            "advanced_reentry_entry_count": len(
                self.entries_by_audit_status_value("passed")
            ),
            "waiting_reentry_entry_count": len(
                self.entries_by_audit_status_value("waiting_for_external_input")
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review reentry audit ledger."""
        return DigestRecord.from_payload(self.to_payload())
