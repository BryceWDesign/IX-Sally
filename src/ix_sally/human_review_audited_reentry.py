"""One-call audited human-review reentry coordination for IX-Sally."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import (
    HumanReviewReentryAuditReport,
    HumanReviewReentryAuditStatus,
    HumanReviewReentryAuditor,
)
from ix_sally.human_review_reentry_coordination import (
    HumanReviewReentryCoordinationResult,
    HumanReviewReentryCoordinator,
)
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowOperation,
    HumanReviewWorkflowStage,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class AuditedHumanReviewReentryReceipt:
    """Receipt proving reentry ran, was audited, and the audit was recorded."""

    receipt_id: CanonicalKey
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
        receipt_id: CanonicalKey | None = None,
    ) -> AuditedHumanReviewReentryReceipt:
        """Create a normalized audited reentry receipt."""
        if max_steps <= 0:
            raise FoundationError("audited human-review reentry max_steps must be positive")
        if executed_steps < 0:
            raise FoundationError(
                "audited human-review reentry executed_steps must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "audited human-review reentry executed_steps exceeds max_steps"
            )

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
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"audited-human-review-reentry-"
                f"{resume_operation_digest.value[:16]}-"
                f"{after_control_plane_digest.value[:16]}-{audit_status.value}",
                field_name="receipt_id",
            ),
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

    def changed_state(self) -> bool:
        """Return whether audited reentry changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_reentry(self) -> bool:
        """Return whether reentry recording changed the control plane."""
        return self.before_control_plane_digest != self.reentry_control_plane_digest

    def recorded_audit(self) -> bool:
        """Return whether audit recording changed the control plane."""
        return self.reentry_control_plane_digest != self.after_control_plane_digest

    def audit_passed(self) -> bool:
        """Return whether the audit passed."""
        return self.audit_status is HumanReviewReentryAuditStatus.PASSED

    def audit_failed(self) -> bool:
        """Return whether the audit failed."""
        return self.audit_status is HumanReviewReentryAuditStatus.FAILED

    def waiting_for_external_input(self) -> bool:
        """Return whether the audited reentry is valid but waiting externally."""
        return (
            self.audit_status
            is HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audited reentry receipt."""
        return {
            "receipt_id": self.receipt_id.value,
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
            "audit_passed": self.audit_passed(),
            "audit_failed": self.audit_failed(),
            "waiting_for_external_input": self.waiting_for_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audited reentry receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuditedHumanReviewReentryResult:
    """Result of running, recording, auditing, and recording a human-review reentry."""

    resume_operation: HumanReviewWorkflowOperation
    reentry_coordination: HumanReviewReentryCoordinationResult
    audit_report: HumanReviewReentryAuditReport
    audit_workflow_operation: HumanReviewWorkflowOperation
    receipt: AuditedHumanReviewReentryReceipt

    @classmethod
    def create(
        cls,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        reentry_coordination: HumanReviewReentryCoordinationResult,
        audit_report: HumanReviewReentryAuditReport,
        audit_workflow_operation: HumanReviewWorkflowOperation,
        receipt: AuditedHumanReviewReentryReceipt,
    ) -> AuditedHumanReviewReentryResult:
        """Create a normalized audited reentry result and validate all links."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "audited human-review reentry requires resume-recorded operation"
            )
        if reentry_coordination.resume_operation.digest() != resume_operation.digest():
            raise FoundationError("audited human-review reentry resume mismatch")
        if audit_report.coordination_digest != reentry_coordination.digest():
            raise FoundationError("audited human-review reentry audit mismatch")
        if (
            audit_workflow_operation.receipt.workflow_stage
            is not HumanReviewWorkflowStage.REENTRY_AUDIT_RECORDED
        ):
            raise FoundationError(
                "audited human-review reentry requires audit-recorded workflow"
            )
        if (
            audit_workflow_operation.require_reentry_audit_report().digest()
            != audit_report.digest()
        ):
            raise FoundationError(
                "audited human-review reentry workflow audit mismatch"
            )
        if audit_workflow_operation.run_state.digest() != audit_report.state_digest:
            raise FoundationError("audited human-review reentry state mismatch")
        if receipt.resume_operation_digest != resume_operation.digest():
            raise FoundationError("audited human-review reentry receipt resume mismatch")
        if receipt.reentry_coordination_digest != reentry_coordination.digest():
            raise FoundationError(
                "audited human-review reentry receipt coordination mismatch"
            )
        if receipt.audit_report_digest != audit_report.digest():
            raise FoundationError("audited human-review reentry receipt audit mismatch")
        if receipt.audit_workflow_operation_digest != audit_workflow_operation.digest():
            raise FoundationError(
                "audited human-review reentry receipt workflow mismatch"
            )
        if receipt.after_state_digest != audit_workflow_operation.run_state.digest():
            raise FoundationError("audited human-review reentry receipt state mismatch")
        if (
            receipt.after_control_plane_digest
            != audit_workflow_operation.control_plane.digest()
        ):
            raise FoundationError(
                "audited human-review reentry receipt control-plane mismatch"
            )

        return cls(
            resume_operation=resume_operation,
            reentry_coordination=reentry_coordination,
            audit_report=audit_report,
            audit_workflow_operation=audit_workflow_operation,
            receipt=receipt,
        )

    @property
    def state(self) -> NinefoldRunState:
        """Return the post-audit run state."""
        return self.audit_workflow_operation.run_state

    @property
    def control_plane(self) -> HumanReviewControlPlaneState:
        """Return the post-audit human-review control-plane state."""
        return self.audit_workflow_operation.control_plane

    def final_stage(self) -> RunStage:
        """Return the final run stage after audited reentry."""
        return self.receipt.final_stage

    def reentry_status(self) -> HumanReviewReentryStatus:
        """Return the underlying reentry status."""
        return self.receipt.reentry_status

    def audit_status(self) -> HumanReviewReentryAuditStatus:
        """Return the audit status."""
        return self.receipt.audit_status

    def report_status(self) -> HumanReviewControlPlaneReportStatus:
        """Return the workflow control-plane report status."""
        return self.receipt.report_status

    def changed_state(self) -> bool:
        """Return whether audited reentry changed the run state."""
        return self.receipt.changed_state()

    def recorded_reentry(self) -> bool:
        """Return whether reentry was recorded."""
        return self.receipt.recorded_reentry()

    def recorded_audit(self) -> bool:
        """Return whether the reentry audit was recorded."""
        return self.receipt.recorded_audit()

    def accepted(self) -> bool:
        """Return whether audited reentry is accepted without blocking findings."""
        return self.audit_status() in {
            HumanReviewReentryAuditStatus.PASSED,
            HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT,
        }

    def requires_operator_attention(self) -> bool:
        """Return whether the final report requires operator attention."""
        return self.audit_workflow_operation.report.requires_operator_attention()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible audited reentry result."""
        return {
            "resume_operation_digest": self.resume_operation.digest().value,
            "reentry_coordination_digest": self.reentry_coordination.digest().value,
            "audit_report_digest": self.audit_report.digest().value,
            "audit_workflow_operation_digest": (
                self.audit_workflow_operation.digest().value
            ),
            "receipt_digest": self.receipt.digest().value,
            "state_digest": self.state.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "final_stage": self.final_stage().value,
            "reentry_status": self.reentry_status().value,
            "audit_status": self.audit_status().value,
            "report_status": self.report_status().value,
            "max_steps": self.receipt.max_steps,
            "executed_steps": self.receipt.executed_steps,
            "changed_state": self.changed_state(),
            "recorded_reentry": self.recorded_reentry(),
            "recorded_audit": self.recorded_audit(),
            "accepted": self.accepted(),
            "requires_operator_attention": self.requires_operator_attention(),
            "reentry_count": self.control_plane.reentry_count(),
            "reentry_audit_count": self.control_plane.reentry_audit_count(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this audited reentry result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuditedHumanReviewReentryCoordinator:
    """Runs certified reentry, audits it, and records both results."""

    reentry_coordinator: HumanReviewReentryCoordinator
    auditor: HumanReviewReentryAuditor
    workflow_kit: HumanReviewWorkflowKit

    @classmethod
    def create(cls) -> AuditedHumanReviewReentryCoordinator:
        """Create a standard audited human-review reentry coordinator."""
        return cls(
            reentry_coordinator=HumanReviewReentryCoordinator.create(),
            auditor=HumanReviewReentryAuditor(),
            workflow_kit=HumanReviewWorkflowKit.create(),
        )

    def resume_audit_and_record(
        self,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        max_steps: int,
    ) -> AuditedHumanReviewReentryResult:
        """Run reentry, audit it, and record the audit in one operation."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "audited human-review reentry requires resume-recorded operation"
            )

        reentry_coordination = self.reentry_coordinator.resume_and_record(
            resume_operation=resume_operation,
            max_steps=max_steps,
        )
        audit_report = self.auditor.audit(reentry_coordination)
        audit_workflow_operation = self.workflow_kit.record_reentry_audit(
            run_state=reentry_coordination.state,
            audit_report=audit_report,
            control_plane=reentry_coordination.control_plane,
        )
        receipt = AuditedHumanReviewReentryReceipt.create(
            resume_operation_digest=resume_operation.digest(),
            reentry_coordination_digest=reentry_coordination.digest(),
            audit_report_digest=audit_report.digest(),
            audit_workflow_operation_digest=audit_workflow_operation.digest(),
            before_state_digest=resume_operation.run_state.digest(),
            after_state_digest=audit_workflow_operation.run_state.digest(),
            before_control_plane_digest=resume_operation.control_plane.digest(),
            reentry_control_plane_digest=reentry_coordination.control_plane.digest(),
            after_control_plane_digest=audit_workflow_operation.control_plane.digest(),
            final_stage=reentry_coordination.final_stage(),
            reentry_status=reentry_coordination.status(),
            audit_status=audit_report.status,
            report_status=audit_workflow_operation.report.status,
            max_steps=max_steps,
            executed_steps=reentry_coordination.receipt.executed_steps,
        )

        return AuditedHumanReviewReentryResult.create(
            resume_operation=resume_operation,
            reentry_coordination=reentry_coordination,
            audit_report=audit_report,
            audit_workflow_operation=audit_workflow_operation,
            receipt=receipt,
        )
