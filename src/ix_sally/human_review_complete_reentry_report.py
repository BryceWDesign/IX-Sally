"""Closeout reporting for complete IX-Sally human-review reentry results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_control_plane_report_status import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.stage_readiness import RunStage

if TYPE_CHECKING:
    from ix_sally.human_review_complete_reentry import CompleteHumanReviewReentryResult
    from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
    from ix_sally.human_review_reentry import HumanReviewReentryStatus
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus


class CompleteHumanReviewReentryCloseoutStatus(StrEnum):
    """Closeout status for a complete human-review reentry result."""

    ACCEPTED = "accepted"
    WAITING_FOR_EXTERNAL_INPUT = "waiting_for_external_input"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutFinding:
    """One closeout finding for a complete human-review reentry report."""

    finding_id: CanonicalKey
    blocking: bool
    message: str

    @classmethod
    def create(
        cls,
        *,
        message: str,
        blocking: bool = False,
        finding_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutFinding:
        """Create a normalized complete reentry closeout finding."""
        normalized_message = require_text(message, field_name="message")
        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-finding-"
                f"{'blocking' if blocking else 'info'}-{normalized_message[:48]}",
                field_name="finding_id",
            ),
            blocking=blocking,
            message=normalized_message,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible closeout finding."""
        return {
            "finding_id": self.finding_id.value,
            "blocking": self.blocking,
            "message": self.message,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this closeout finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutReport:
    """Receipt-grade closeout report for a complete human-review reentry result."""

    report_id: CanonicalKey
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
    findings: tuple[CompleteHumanReviewReentryCloseoutFinding, ...]

    @classmethod
    def create(
        cls,
        *,
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
        findings: tuple[CompleteHumanReviewReentryCloseoutFinding, ...],
        report_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutReport:
        """Create a normalized complete reentry closeout report."""
        if max_steps <= 0:
            raise FoundationError(
                "complete human-review reentry closeout max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete human-review reentry closeout executed_steps "
                "must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete human-review reentry closeout executed_steps exceeds max_steps"
            )

        for field_name, value in {
            "reentry_count": reentry_count,
            "reentry_audit_count": reentry_audit_count,
            "audited_reentry_count": audited_reentry_count,
            "complete_reentry_count": complete_reentry_count,
        }.items():
            if value < 0:
                raise FoundationError(
                    f"complete human-review reentry closeout {field_name} "
                    "must not be negative"
                )

        complete_reentry_result_digest.require_algorithm("sha256")
        complete_reentry_receipt_digest.require_algorithm("sha256")
        final_workflow_operation_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")

        has_blocking = any(finding.blocking for finding in findings)
        if has_blocking and closeout_status is not CompleteHumanReviewReentryCloseoutStatus.BLOCKED:
            raise FoundationError(
                "complete human-review reentry closeout with blocking findings "
                "must be blocked"
            )
        if (
            not has_blocking
            and closeout_status is CompleteHumanReviewReentryCloseoutStatus.BLOCKED
        ):
            raise FoundationError(
                "complete human-review reentry closeout blocked status requires "
                "blocking findings"
            )

        return cls(
            report_id=report_id
            or CanonicalKey.from_text(
                f"complete-human-review-reentry-closeout-"
                f"{complete_reentry_result_digest.value[:16]}-"
                f"{closeout_status.value}",
                field_name="report_id",
            ),
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
            findings=findings,
        )

    @classmethod
    def from_result(
        cls,
        result: CompleteHumanReviewReentryResult,
    ) -> CompleteHumanReviewReentryCloseoutReport:
        """Create a closeout report from a complete human-review reentry result."""
        recorded_control_plane = _recorded_control_plane_for_result(result)
        findings = _findings_for_result(result, recorded_control_plane)
        closeout_status = _select_closeout_status(result, findings)

        return cls.create(
            complete_reentry_result_digest=result.digest(),
            complete_reentry_receipt_digest=result.receipt.digest(),
            final_workflow_operation_digest=result.final_workflow_operation.digest(),
            state_digest=result.state.digest(),
            control_plane_digest=recorded_control_plane.digest(),
            final_stage=result.final_stage(),
            reentry_status=result.reentry_status(),
            audit_status=result.audit_status(),
            report_status=_complete_reentry_report_status(result),
            closeout_status=closeout_status,
            max_steps=result.receipt.max_steps,
            executed_steps=result.receipt.executed_steps,
            reentry_count=recorded_control_plane.reentry_count(),
            reentry_audit_count=recorded_control_plane.reentry_audit_count(),
            audited_reentry_count=recorded_control_plane.audited_reentry_count(),
            complete_reentry_count=recorded_control_plane.complete_reentry_count(),
            findings=findings,
        )

    def blocking_findings(
        self,
    ) -> tuple[CompleteHumanReviewReentryCloseoutFinding, ...]:
        """Return blocking closeout findings."""
        return tuple(finding for finding in self.findings if finding.blocking)

    def accepted(self) -> bool:
        """Return whether the complete reentry closeout is accepted."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED

    def waiting_for_external_input(self) -> bool:
        """Return whether the complete reentry is valid but waiting externally."""
        return (
            self.closeout_status
            is CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def blocked(self) -> bool:
        """Return whether the complete reentry closeout is blocked."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.BLOCKED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible closeout report."""
        return {
            "report_id": self.report_id.value,
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
            "finding_count": len(self.findings),
            "blocking_finding_count": len(self.blocking_findings()),
            "accepted": self.accepted(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "blocked": self.blocked(),
            "findings": [finding.to_payload() for finding in self.findings],
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry closeout report."""
        return DigestRecord.from_payload(self.to_payload())


def _select_closeout_status(
    result: CompleteHumanReviewReentryResult,
    findings: tuple[CompleteHumanReviewReentryCloseoutFinding, ...],
) -> CompleteHumanReviewReentryCloseoutStatus:
    """Select closeout status from result state and findings."""
    if any(finding.blocking for finding in findings):
        return CompleteHumanReviewReentryCloseoutStatus.BLOCKED

    if result.receipt.waiting_for_external_input():
        return CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT

    return CompleteHumanReviewReentryCloseoutStatus.ACCEPTED


def _recorded_control_plane_for_result(
    result: CompleteHumanReviewReentryResult,
) -> HumanReviewControlPlaneState:
    """Return the control-plane state after recording the complete reentry result."""
    updated_ledger = result.control_plane.complete_reentry_ledger.append_result(result)
    return result.control_plane.with_complete_reentry_ledger(updated_ledger)


def _complete_reentry_report_status(
    result: CompleteHumanReviewReentryResult,
) -> HumanReviewControlPlaneReportStatus:
    """Promote an audited-reentry report status to its complete-reentry status."""
    status = result.report_status()
    if status is HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED:
        return HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED
    if (
        status
        is HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT
    ):
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT
        )
    if status is HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED:
        return HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED
    return status


def _findings_for_result(
    result: CompleteHumanReviewReentryResult,
    recorded_control_plane: HumanReviewControlPlaneState,
) -> tuple[CompleteHumanReviewReentryCloseoutFinding, ...]:
    """Build deterministic findings for complete human-review reentry closeout."""
    findings: list[CompleteHumanReviewReentryCloseoutFinding] = []

    if result.changed_state():
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry changed the run state.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry did not change the run state.",
                blocking=True,
            )
        )

    if recorded_control_plane.reentry_count() > 0:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Reentry result was recorded in the control plane.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Reentry result was not recorded in the control plane.",
                blocking=True,
            )
        )

    if recorded_control_plane.reentry_audit_count() > 0:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Reentry audit was recorded in the control plane.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Reentry audit was not recorded in the control plane.",
                blocking=True,
            )
        )

    if recorded_control_plane.audited_reentry_count() > 0:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Audited reentry result was recorded in the control plane.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Audited reentry result was not recorded in the control plane.",
                blocking=True,
            )
        )

    if recorded_control_plane.complete_reentry_count() > 0:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry result was recorded in the control plane.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry result was not recorded in the control plane.",
                blocking=True,
            )
        )

    if result.accepted():
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry final report accepted the result.",
            )
        )
    else:
        findings.append(
            CompleteHumanReviewReentryCloseoutFinding.create(
                message="Complete reentry final report did not accept the result.",
                blocking=True,
            )
        )

    return tuple(findings)
