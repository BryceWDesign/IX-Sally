"""Workflow kit for IX-Sally human-review control-plane operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneCoordinator,
    HumanReviewControlPlaneOperationKind,
    HumanReviewControlPlaneOperationResult,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReport,
    HumanReviewControlPlaneReporter,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_handoff import HumanReviewHandoffResult
from ix_sally.human_review_resume_coordination import HumanReviewResumeCoordinationResult
from ix_sally.state import NinefoldRunState

if TYPE_CHECKING:
    from ix_sally.human_review_reentry import HumanReviewReentryResult
    from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditReport


class HumanReviewWorkflowStage(StrEnum):
    """High-level stage label for human-review workflow kit results."""

    HANDOFF_READY = "handoff_ready"
    DECISION_RECORDED = "decision_recorded"
    CLEARANCE_ASSESSED = "clearance_assessed"
    RESUME_RECORDED = "resume_recorded"
    REENTRY_RECORDED = "reentry_recorded"
    REENTRY_AUDIT_RECORDED = "reentry_audit_recorded"


@dataclass(frozen=True, slots=True)
class HumanReviewWorkflowReceipt:
    """Compact receipt for one human-review workflow kit operation."""

    receipt_id: CanonicalKey
    workflow_stage: HumanReviewWorkflowStage
    run_state_digest: DigestRecord
    control_plane_digest: DigestRecord
    report_digest: DigestRecord
    operation_digest: DigestRecord | None
    clearance_assessment_digest: DigestRecord | None
    detail: str

    @classmethod
    def create(
        cls,
        *,
        workflow_stage: HumanReviewWorkflowStage,
        run_state_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        report_digest: DigestRecord,
        detail: str,
        operation_digest: DigestRecord | None = None,
        clearance_assessment_digest: DigestRecord | None = None,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewWorkflowReceipt:
        """Create a normalized human-review workflow receipt."""
        run_state_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")
        report_digest.require_algorithm("sha256")
        if operation_digest is not None:
            operation_digest.require_algorithm("sha256")
        if clearance_assessment_digest is not None:
            clearance_assessment_digest.require_algorithm("sha256")

        normalized_detail = require_text(detail, field_name="detail")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-workflow-{workflow_stage.value}-"
                f"{run_state_digest.value[:16]}-{control_plane_digest.value[:16]}",
                field_name="receipt_id",
            ),
            workflow_stage=workflow_stage,
            run_state_digest=run_state_digest,
            control_plane_digest=control_plane_digest,
            report_digest=report_digest,
            operation_digest=operation_digest,
            clearance_assessment_digest=clearance_assessment_digest,
            detail=normalized_detail,
        )

    def records_operation(self) -> bool:
        """Return whether this receipt records a control-plane operation."""
        return self.operation_digest is not None

    def records_clearance_assessment(self) -> bool:
        """Return whether this receipt records a clearance assessment."""
        return self.clearance_assessment_digest is not None

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible workflow receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "workflow_stage": self.workflow_stage.value,
            "run_state_digest": {
                "algorithm": self.run_state_digest.algorithm,
                "value": self.run_state_digest.value,
            },
            "control_plane_digest": {
                "algorithm": self.control_plane_digest.algorithm,
                "value": self.control_plane_digest.value,
            },
            "report_digest": {
                "algorithm": self.report_digest.algorithm,
                "value": self.report_digest.value,
            },
            "operation_digest": (
                {
                    "algorithm": self.operation_digest.algorithm,
                    "value": self.operation_digest.value,
                }
                if self.operation_digest is not None
                else None
            ),
            "clearance_assessment_digest": (
                {
                    "algorithm": self.clearance_assessment_digest.algorithm,
                    "value": self.clearance_assessment_digest.value,
                }
                if self.clearance_assessment_digest is not None
                else None
            ),
            "detail": self.detail,
            "records_operation": self.records_operation(),
            "records_clearance_assessment": self.records_clearance_assessment(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this workflow receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewWorkflowOperation:
    """Result of a human-review workflow operation that updates control-plane state."""

    run_state: NinefoldRunState
    control_plane: HumanReviewControlPlaneState
    operation_result: HumanReviewControlPlaneOperationResult
    report: HumanReviewControlPlaneReport
    receipt: HumanReviewWorkflowReceipt

    @classmethod
    def create(
        cls,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        operation_result: HumanReviewControlPlaneOperationResult,
        report: HumanReviewControlPlaneReport,
        workflow_stage: HumanReviewWorkflowStage,
        detail: str,
    ) -> HumanReviewWorkflowOperation:
        """Create a normalized workflow operation result."""
        if control_plane != operation_result.after_control_plane:
            raise FoundationError("workflow control-plane state must match operation result")

        receipt = HumanReviewWorkflowReceipt.create(
            workflow_stage=workflow_stage,
            run_state_digest=run_state.digest(),
            control_plane_digest=control_plane.digest(),
            report_digest=report.digest(),
            operation_digest=operation_result.digest(),
            detail=detail,
        )

        return cls(
            run_state=run_state,
            control_plane=control_plane,
            operation_result=operation_result,
            report=report,
            receipt=receipt,
        )

    def operation_kind(self) -> HumanReviewControlPlaneOperationKind:
        """Return the underlying control-plane operation kind."""
        return self.operation_result.operation_kind()

    def require_handoff(self) -> HumanReviewHandoffResult:
        """Return the handoff result for a handoff workflow operation."""
        return self.operation_result.require_handoff_result()

    def require_resume(self) -> HumanReviewResumeCoordinationResult:
        """Return the resume result for a resume workflow operation."""
        return self.operation_result.require_resume_result()

    def require_reentry(self) -> HumanReviewReentryResult:
        """Return the reentry result for a reentry workflow operation."""
        return self.operation_result.require_reentry_result()

    def require_reentry_audit_report(self) -> HumanReviewReentryAuditReport:
        """Return the reentry audit report for an audit workflow operation."""
        return self.operation_result.require_reentry_audit_report()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible workflow operation result."""
        return {
            "run_state_digest": self.run_state.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "operation_result_digest": self.operation_result.digest().value,
            "report_digest": self.report.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "workflow_stage": self.receipt.workflow_stage.value,
            "operation_kind": self.operation_kind().value,
            "report_status": self.report.status.value,
            "reentry_count": self.control_plane.reentry_count(),
            "reentry_audit_count": self.control_plane.reentry_audit_count(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this workflow operation."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewWorkflowClearance:
    """Result of assessing clearance without mutating control-plane state."""

    run_state: NinefoldRunState
    control_plane: HumanReviewControlPlaneState
    handoff: HumanReviewHandoffResult
    assessment: HumanReviewClearanceAssessment
    report: HumanReviewControlPlaneReport
    receipt: HumanReviewWorkflowReceipt

    @classmethod
    def create(
        cls,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        handoff: HumanReviewHandoffResult,
        assessment: HumanReviewClearanceAssessment,
        report: HumanReviewControlPlaneReport,
    ) -> HumanReviewWorkflowClearance:
        """Create a normalized workflow clearance result."""
        if assessment.bundle.digest() != handoff.bundle.digest():
            raise FoundationError("workflow clearance assessment must match handoff bundle")
        if assessment.decision_ledger.digest() != control_plane.decision_ledger.digest():
            raise FoundationError(
                "workflow clearance assessment must match control-plane decisions"
            )

        receipt = HumanReviewWorkflowReceipt.create(
            workflow_stage=HumanReviewWorkflowStage.CLEARANCE_ASSESSED,
            run_state_digest=run_state.digest(),
            control_plane_digest=control_plane.digest(),
            report_digest=report.digest(),
            clearance_assessment_digest=assessment.digest(),
            detail="Human-review clearance was assessed against recorded decisions.",
        )

        return cls(
            run_state=run_state,
            control_plane=control_plane,
            handoff=handoff,
            assessment=assessment,
            report=report,
            receipt=receipt,
        )

    def cleared_to_resume(self) -> bool:
        """Return whether the clearance assessment allows resume certification."""
        return self.assessment.cleared_to_resume()

    def requires_operator_attention(self) -> bool:
        """Return whether the clearance assessment still requires operator attention."""
        return self.assessment.requires_operator_attention()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible workflow clearance result."""
        return {
            "run_state_digest": self.run_state.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "handoff_digest": self.handoff.digest().value,
            "assessment_digest": self.assessment.digest().value,
            "report_digest": self.report.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "workflow_stage": self.receipt.workflow_stage.value,
            "report_status": self.report.status.value,
            "cleared_to_resume": self.cleared_to_resume(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this workflow clearance result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewWorkflowKit:
    """Facade for the IX-Sally human-review control-plane workflow."""

    coordinator: HumanReviewControlPlaneCoordinator
    reporter: HumanReviewControlPlaneReporter

    @classmethod
    def create(cls) -> HumanReviewWorkflowKit:
        """Create the standard human-review workflow kit."""
        return cls(
            coordinator=HumanReviewControlPlaneCoordinator.create(),
            reporter=HumanReviewControlPlaneReporter(),
        )

    def open_handoff(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState | None = None,
        authority_note: str = (
            "Human authority is required before IX-Sally may treat these "
            "targets as resolved."
        ),
    ) -> HumanReviewWorkflowOperation:
        """Record a human-review handoff and return the updated workflow operation."""
        starting_plane = control_plane or HumanReviewControlPlaneState.create()
        operation = self.coordinator.record_handoff(
            run_state=run_state,
            control_plane=starting_plane,
            authority_note=authority_note,
        )
        report = self.reporter.report(
            run_state=run_state,
            control_plane=operation.after_control_plane,
        )

        return HumanReviewWorkflowOperation.create(
            run_state=run_state,
            control_plane=operation.after_control_plane,
            operation_result=operation,
            report=report,
            workflow_stage=HumanReviewWorkflowStage.HANDOFF_READY,
            detail="Human-review handoff was assembled and recorded.",
        )

    def record_action_decision(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        action_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        rationale: str,
    ) -> HumanReviewWorkflowOperation:
        """Record a human-review action decision and return updated workflow state."""
        operation = self.coordinator.record_action_decision(
            run_state=run_state,
            control_plane=control_plane,
            action_id=action_id,
            reviewer=reviewer,
            status=status,
            rationale=rationale,
        )
        decision_state = operation.require_decision_result().state
        report = self.reporter.report(
            run_state=decision_state,
            control_plane=operation.after_control_plane,
        )

        return HumanReviewWorkflowOperation.create(
            run_state=decision_state,
            control_plane=operation.after_control_plane,
            operation_result=operation,
            report=report,
            workflow_stage=HumanReviewWorkflowStage.DECISION_RECORDED,
            detail="Human-review action decision was applied and recorded.",
        )

    def assess_clearance(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
        handoff: HumanReviewHandoffResult,
    ) -> HumanReviewWorkflowClearance:
        """Assess whether a recorded handoff is cleared by recorded decisions."""
        assessment = HumanReviewClearanceAssessment.from_bundle(
            bundle=handoff.bundle,
            decision_ledger=control_plane.decision_ledger,
        )
        report = self.reporter.report(
            run_state=run_state,
            control_plane=control_plane,
        )

        return HumanReviewWorkflowClearance.create(
            run_state=run_state,
            control_plane=control_plane,
            handoff=handoff,
            assessment=assessment,
            report=report,
        )

    def record_resume(
        self,
        *,
        clearance: HumanReviewWorkflowClearance,
        control_plane: HumanReviewControlPlaneState | None = None,
        rationale: str = (
            "Human-review clearance is complete; IX-Sally may resume staged "
            "orchestration from the resumed state."
        ),
    ) -> HumanReviewWorkflowOperation:
        """Certify and record a cleared human-review resume."""
        starting_plane = control_plane or clearance.control_plane
        operation = self.coordinator.record_resume(
            assessment=clearance.assessment,
            resumed_state=clearance.run_state,
            control_plane=starting_plane,
            rationale=rationale,
        )
        resume_state = operation.require_resume_result().state
        report = self.reporter.report(
            run_state=resume_state,
            control_plane=operation.after_control_plane,
        )

        return HumanReviewWorkflowOperation.create(
            run_state=resume_state,
            control_plane=operation.after_control_plane,
            operation_result=operation,
            report=report,
            workflow_stage=HumanReviewWorkflowStage.RESUME_RECORDED,
            detail="Human-review resume was certified and recorded.",
        )

    def record_reentry(
        self,
        *,
        reentry_result: HumanReviewReentryResult,
        control_plane: HumanReviewControlPlaneState | None = None,
    ) -> HumanReviewWorkflowOperation:
        """Record certified human-review reentry and return updated workflow state."""
        starting_plane = control_plane or reentry_result.control_plane
        operation = self.coordinator.record_reentry(
            reentry_result=reentry_result,
            control_plane=starting_plane,
        )
        report = self.reporter.report(
            run_state=reentry_result.state,
            control_plane=operation.after_control_plane,
        )

        return HumanReviewWorkflowOperation.create(
            run_state=reentry_result.state,
            control_plane=operation.after_control_plane,
            operation_result=operation,
            report=report,
            workflow_stage=HumanReviewWorkflowStage.REENTRY_RECORDED,
            detail="Human-review reentry was advanced and recorded.",
        )

    def record_reentry_audit(
        self,
        *,
        run_state: NinefoldRunState,
        audit_report: HumanReviewReentryAuditReport,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewWorkflowOperation:
        """Record a human-review reentry audit and return updated workflow state."""
        if run_state.digest() != audit_report.state_digest:
            raise FoundationError(
                "workflow reentry audit run state must match audit report"
            )

        operation = self.coordinator.record_reentry_audit(
            audit_report=audit_report,
            control_plane=control_plane,
        )
        report = self.reporter.report(
            run_state=run_state,
            control_plane=operation.after_control_plane,
        )

        return HumanReviewWorkflowOperation.create(
            run_state=run_state,
            control_plane=operation.after_control_plane,
            operation_result=operation,
            report=report,
            workflow_stage=HumanReviewWorkflowStage.REENTRY_AUDIT_RECORDED,
            detail="Human-review reentry audit was recorded.",
        )
