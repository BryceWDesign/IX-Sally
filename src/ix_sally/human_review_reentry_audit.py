"""Audit reports for certified IX-Sally human-review reentry coordination."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_reentry_audit_status import HumanReviewReentryAuditStatus
from ix_sally.human_review_reentry_coordination import (
    HumanReviewReentryCoordinationResult,
)
from ix_sally.human_review_reentry_status import HumanReviewReentryStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowStage
from ix_sally.stage_readiness import RunStage


class HumanReviewReentryAuditSeverity(StrEnum):
    """Severity labels for human-review reentry audit findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class HumanReviewReentryAuditFinding:
    """One deterministic audit finding for a human-review reentry coordination."""

    finding_id: CanonicalKey
    severity: HumanReviewReentryAuditSeverity
    code: str
    detail: str

    @classmethod
    def create(
        cls,
        *,
        severity: HumanReviewReentryAuditSeverity,
        code: str,
        detail: str,
        finding_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryAuditFinding:
        """Create a normalized human-review reentry audit finding."""
        normalized_code = require_text(code, field_name="code")
        normalized_detail = require_text(detail, field_name="detail")

        return cls(
            finding_id=finding_id
            or CanonicalKey.from_text(
                f"human-review-reentry-audit-{severity.value}-{normalized_code}",
                field_name="finding_id",
            ),
            severity=severity,
            code=normalized_code,
            detail=normalized_detail,
        )

    def is_blocking(self) -> bool:
        """Return whether this finding blocks reentry acceptance."""
        return self.severity is HumanReviewReentryAuditSeverity.BLOCKING

    def is_warning(self) -> bool:
        """Return whether this finding is a warning."""
        return self.severity is HumanReviewReentryAuditSeverity.WARNING

    def is_info(self) -> bool:
        """Return whether this finding is informational."""
        return self.severity is HumanReviewReentryAuditSeverity.INFO

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audit finding."""
        return {
            "finding_id": self.finding_id.value,
            "severity": self.severity.value,
            "code": self.code,
            "detail": self.detail,
            "is_blocking": self.is_blocking(),
            "is_warning": self.is_warning(),
            "is_info": self.is_info(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audit finding."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryAuditReport:
    """Receipt-grade audit report for a coordinated human-review reentry."""

    report_id: CanonicalKey
    coordination_digest: DigestRecord
    resume_operation_digest: DigestRecord
    reentry_result_digest: DigestRecord
    workflow_operation_digest: DigestRecord
    state_digest: DigestRecord
    control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    status: HumanReviewReentryAuditStatus
    findings: tuple[HumanReviewReentryAuditFinding, ...]

    @classmethod
    def create(
        cls,
        *,
        coordination_digest: DigestRecord,
        resume_operation_digest: DigestRecord,
        reentry_result_digest: DigestRecord,
        workflow_operation_digest: DigestRecord,
        state_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        status: HumanReviewReentryAuditStatus,
        findings: Iterable[HumanReviewReentryAuditFinding],
        report_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryAuditReport:
        """Create a normalized human-review reentry audit report."""
        coordination_digest.require_algorithm("sha256")
        resume_operation_digest.require_algorithm("sha256")
        reentry_result_digest.require_algorithm("sha256")
        workflow_operation_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")

        normalized_findings = tuple(findings)
        expected_status = _status_for_findings(
            findings=normalized_findings,
            reentry_status=reentry_status,
        )
        if status is not expected_status:
            raise FoundationError("human-review reentry audit status does not match findings")

        return cls(
            report_id=report_id
            or CanonicalKey.from_text(
                f"human-review-reentry-audit-{coordination_digest.value[:16]}-{status.value}",
                field_name="report_id",
            ),
            coordination_digest=coordination_digest,
            resume_operation_digest=resume_operation_digest,
            reentry_result_digest=reentry_result_digest,
            workflow_operation_digest=workflow_operation_digest,
            state_digest=state_digest,
            control_plane_digest=control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            status=status,
            findings=normalized_findings,
        )

    @classmethod
    def from_coordination(
        cls,
        coordination: HumanReviewReentryCoordinationResult,
    ) -> HumanReviewReentryAuditReport:
        """Create an audit report from a human-review reentry coordination result."""
        findings = _findings_from_coordination(coordination)
        status = _status_for_findings(
            findings=findings,
            reentry_status=coordination.status(),
        )

        return cls.create(
            coordination_digest=coordination.digest(),
            resume_operation_digest=coordination.resume_operation.digest(),
            reentry_result_digest=coordination.reentry_result.digest(),
            workflow_operation_digest=coordination.workflow_operation.digest(),
            state_digest=coordination.state.digest(),
            control_plane_digest=coordination.control_plane.digest(),
            final_stage=coordination.final_stage(),
            reentry_status=coordination.status(),
            status=status,
            findings=findings,
        )

    def blocking_findings(self) -> tuple[HumanReviewReentryAuditFinding, ...]:
        """Return blocking findings."""
        return tuple(finding for finding in self.findings if finding.is_blocking())

    def warning_findings(self) -> tuple[HumanReviewReentryAuditFinding, ...]:
        """Return warning findings."""
        return tuple(finding for finding in self.findings if finding.is_warning())

    def info_findings(self) -> tuple[HumanReviewReentryAuditFinding, ...]:
        """Return informational findings."""
        return tuple(finding for finding in self.findings if finding.is_info())

    def passed(self) -> bool:
        """Return whether the audit passed without blocking findings."""
        return self.status is HumanReviewReentryAuditStatus.PASSED

    def failed(self) -> bool:
        """Return whether the audit failed with blocking findings."""
        return self.status is HumanReviewReentryAuditStatus.FAILED

    def waiting_for_external_input(self) -> bool:
        """Return whether reentry is valid but waiting for external input."""
        return self.status is HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT

    def has_blocking_findings(self) -> bool:
        """Return whether this audit contains blocking findings."""
        return bool(self.blocking_findings())

    def has_warnings(self) -> bool:
        """Return whether this audit contains warnings."""
        return bool(self.warning_findings())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry audit report."""
        finding_payload: JsonArray = []
        for finding in self.findings:
            finding_payload.append(finding.to_payload())

        return {
            "report_id": self.report_id.value,
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
            "status": self.status.value,
            "findings": finding_payload,
            "finding_count": len(self.findings),
            "blocking_finding_count": len(self.blocking_findings()),
            "warning_finding_count": len(self.warning_findings()),
            "info_finding_count": len(self.info_findings()),
            "passed": self.passed(),
            "failed": self.failed(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "has_blocking_findings": self.has_blocking_findings(),
            "has_warnings": self.has_warnings(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review reentry audit report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryAuditor:
    """Builds audit reports for coordinated human-review reentry results."""

    def audit(
        self,
        coordination: HumanReviewReentryCoordinationResult,
    ) -> HumanReviewReentryAuditReport:
        """Return a deterministic audit report for coordinated reentry."""
        return HumanReviewReentryAuditReport.from_coordination(coordination)


def _findings_from_coordination(
    coordination: HumanReviewReentryCoordinationResult,
) -> tuple[HumanReviewReentryAuditFinding, ...]:
    """Build deterministic findings from a reentry coordination result."""
    findings: list[HumanReviewReentryAuditFinding] = []

    if (
        coordination.resume_operation.receipt.workflow_stage
        is HumanReviewWorkflowStage.RESUME_RECORDED
    ):
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="resume-operation-certified",
                detail="The source workflow operation is a certified resume.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="resume-operation-not-certified",
                detail="The source workflow operation is not a certified resume.",
            )
        )

    if (
        coordination.workflow_operation.receipt.workflow_stage
        is HumanReviewWorkflowStage.REENTRY_RECORDED
    ):
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="workflow-reentry-recorded",
                detail="The workflow operation recorded human-review reentry.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="workflow-reentry-missing",
                detail="The workflow operation did not record human-review reentry.",
            )
        )

    if coordination.changed_state():
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="run-state-advanced",
                detail="Human-review reentry advanced the run state.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.WARNING,
                code="run-state-unchanged",
                detail="Human-review reentry completed without changing run state.",
            )
        )

    if coordination.changed_control_plane():
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="control-plane-recorded",
                detail="Human-review reentry changed the control-plane ledger state.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="control-plane-unchanged",
                detail="Human-review reentry was not recorded in control-plane state.",
            )
        )
    if coordination.recorded_reentry() and coordination.control_plane.reentry_count() > 0:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="reentry-ledger-populated",
                detail="The control-plane reentry ledger contains a recorded entry.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="reentry-ledger-empty",
                detail="The control-plane reentry ledger has no recorded entry.",
            )
        )

    if coordination.control_plane.latest_reentry_digest() is not None:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="latest-reentry-digest-present",
                detail="The control plane exposes the latest reentry ledger digest.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="latest-reentry-digest-missing",
                detail="The control plane does not expose a latest reentry digest.",
            )
        )

    if coordination.final_stage() is RunStage.HUMAN_REVIEW:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.BLOCKING,
                code="reentered-human-review",
                detail="Human-review reentry ended back in human review.",
            )
        )
    else:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="final-stage-not-human-review",
                detail="Human-review reentry ended outside the human-review stage.",
            )
        )

    if coordination.status() is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT:
        findings.append(
            _finding(
                severity=HumanReviewReentryAuditSeverity.INFO,
                code="external-input-required",
                detail="Reentry is valid and now waits for external input.",
            )
        )

    return tuple(findings)


def _status_for_findings(
    *,
    findings: tuple[HumanReviewReentryAuditFinding, ...],
    reentry_status: HumanReviewReentryStatus,
) -> HumanReviewReentryAuditStatus:
    """Select the audit status from findings and reentry status."""
    if any(finding.is_blocking() for finding in findings):
        return HumanReviewReentryAuditStatus.FAILED

    if reentry_status is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT:
        return HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT

    return HumanReviewReentryAuditStatus.PASSED


def _finding(
    *,
    severity: HumanReviewReentryAuditSeverity,
    code: str,
    detail: str,
) -> HumanReviewReentryAuditFinding:
    """Create one normalized audit finding."""
    return HumanReviewReentryAuditFinding.create(
        severity=severity,
        code=code,
        detail=detail,
    )
