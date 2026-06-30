"""Complete audited human-review reentry coordination for IX-Sally."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_audited_reentry import (
    AuditedHumanReviewReentryCoordinator,
    AuditedHumanReviewReentryResult,
)
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowOperation,
    HumanReviewWorkflowStage,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryReceipt:
    """Receipt proving reentry was run, audited, and fully ledger-recorded."""

    receipt_id: CanonicalKey
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
        receipt_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryReceipt:
        """Create a normalized complete human-review reentry receipt."""
        if max_steps <= 0:
            raise FoundationError(
                "complete human-review reentry max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete human-review reentry executed_steps must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete human-review reentry executed_steps exceeds max_steps"
            )

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
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"complete-human-review-reentry-"
                f"{resume_operation_digest.value[:16]}-"
                f"{after_control_plane_digest.value[:16]}-{report_status.value}",
                field_name="receipt_id",
            ),
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

    def changed_state(self) -> bool:
        """Return whether the complete reentry changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_reentry_and_audit(self) -> bool:
        """Return whether the audited reentry coordinator changed the control plane."""
        return self.before_control_plane_digest != self.audited_reentry_control_plane_digest

    def recorded_complete_audited_reentry(self) -> bool:
        """Return whether final audited-reentry ledger recording changed the plane."""
        return self.audited_reentry_control_plane_digest != self.after_control_plane_digest

    def accepted(self) -> bool:
        """Return whether the complete reentry ended in an accepted report state."""
        return self.report_status in {
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
        }

    def requires_operator_attention(self) -> bool:
        """Return whether the final report status requires operator attention."""
        return self.report_status in {
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED,
            HumanReviewControlPlaneReportStatus.DEFERRAL_OPEN,
        }

    def waiting_for_external_input(self) -> bool:
        """Return whether the accepted complete reentry is waiting externally."""
        return (
            self.report_status
            is HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible complete reentry receipt."""
        return {
            "receipt_id": self.receipt_id.value,
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
            "requires_operator_attention": self.requires_operator_attention(),
            "waiting_for_external_input": self.waiting_for_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryResult:
    """Result of running a complete audited human-review reentry workflow."""

    resume_operation: HumanReviewWorkflowOperation
    audited_reentry_result: AuditedHumanReviewReentryResult
    final_workflow_operation: HumanReviewWorkflowOperation
    receipt: CompleteHumanReviewReentryReceipt

    @classmethod
    def create(
        cls,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        audited_reentry_result: AuditedHumanReviewReentryResult,
        final_workflow_operation: HumanReviewWorkflowOperation,
        receipt: CompleteHumanReviewReentryReceipt,
    ) -> CompleteHumanReviewReentryResult:
        """Create a normalized complete reentry result and validate all links."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "complete human-review reentry requires resume-recorded operation"
            )
        if audited_reentry_result.resume_operation.digest() != resume_operation.digest():
            raise FoundationError("complete human-review reentry resume mismatch")
        if (
            final_workflow_operation.receipt.workflow_stage
            is not HumanReviewWorkflowStage.AUDITED_REENTRY_RECORDED
        ):
            raise FoundationError(
                "complete human-review reentry requires audited-reentry workflow"
            )
        if (
            final_workflow_operation.require_audited_reentry_result().digest()
            != audited_reentry_result.digest()
        ):
            raise FoundationError(
                "complete human-review reentry final workflow result mismatch"
            )
        if final_workflow_operation.run_state.digest() != audited_reentry_result.state.digest():
            raise FoundationError("complete human-review reentry state mismatch")
        if receipt.resume_operation_digest != resume_operation.digest():
            raise FoundationError("complete human-review reentry receipt resume mismatch")
        if receipt.audited_reentry_result_digest != audited_reentry_result.digest():
            raise FoundationError("complete human-review reentry receipt result mismatch")
        if receipt.audited_reentry_receipt_digest != audited_reentry_result.receipt.digest():
            raise FoundationError(
                "complete human-review reentry receipt audited receipt mismatch"
            )
        if receipt.final_workflow_operation_digest != final_workflow_operation.digest():
            raise FoundationError(
                "complete human-review reentry receipt workflow mismatch"
            )
        if receipt.after_state_digest != final_workflow_operation.run_state.digest():
            raise FoundationError("complete human-review reentry receipt state mismatch")
        if receipt.after_control_plane_digest != final_workflow_operation.control_plane.digest():
            raise FoundationError(
                "complete human-review reentry receipt control-plane mismatch"
            )

        return cls(
            resume_operation=resume_operation,
            audited_reentry_result=audited_reentry_result,
            final_workflow_operation=final_workflow_operation,
            receipt=receipt,
        )

    @property
    def state(self) -> NinefoldRunState:
        """Return the final run state."""
        return self.final_workflow_operation.run_state

    @property
    def control_plane(self) -> HumanReviewControlPlaneState:
        """Return the final control-plane state."""
        return self.final_workflow_operation.control_plane

    def final_stage(self) -> RunStage:
        """Return the final run stage after complete reentry."""
        return self.receipt.final_stage

    def reentry_status(self) -> HumanReviewReentryStatus:
        """Return the reentry status."""
        return self.receipt.reentry_status

    def audit_status(self) -> HumanReviewReentryAuditStatus:
        """Return the reentry audit status."""
        return self.receipt.audit_status

    def report_status(self) -> HumanReviewControlPlaneReportStatus:
        """Return the final control-plane report status."""
        return self.receipt.report_status

    def changed_state(self) -> bool:
        """Return whether complete reentry changed the run state."""
        return self.receipt.changed_state()

    def accepted(self) -> bool:
        """Return whether complete reentry was accepted."""
        return self.receipt.accepted()

    def requires_operator_attention(self) -> bool:
        """Return whether complete reentry requires operator attention."""
        return self.receipt.requires_operator_attention()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible complete reentry result."""
        return {
            "resume_operation_digest": self.resume_operation.digest().value,
            "audited_reentry_result_digest": self.audited_reentry_result.digest().value,
            "final_workflow_operation_digest": (
                self.final_workflow_operation.digest().value
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
            "accepted": self.accepted(),
            "requires_operator_attention": self.requires_operator_attention(),
            "reentry_count": self.control_plane.reentry_count(),
            "reentry_audit_count": self.control_plane.reentry_audit_count(),
            "audited_reentry_count": self.control_plane.audited_reentry_count(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this complete reentry result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCoordinator:
    """Runs, audits, records, and final-ledgers a human-review reentry."""

    audited_reentry_coordinator: AuditedHumanReviewReentryCoordinator
    workflow_kit: HumanReviewWorkflowKit

    @classmethod
    def create(cls) -> CompleteHumanReviewReentryCoordinator:
        """Create a standard complete human-review reentry coordinator."""
        return cls(
            audited_reentry_coordinator=AuditedHumanReviewReentryCoordinator.create(),
            workflow_kit=HumanReviewWorkflowKit.create(),
        )

    def resume_audit_record_and_finalize(
        self,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        max_steps: int,
    ) -> CompleteHumanReviewReentryResult:
        """Run complete audited reentry and record the final audited result."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "complete human-review reentry requires resume-recorded operation"
            )

        audited_reentry = self.audited_reentry_coordinator.resume_audit_and_record(
            resume_operation=resume_operation,
            max_steps=max_steps,
        )
        final_workflow = self.workflow_kit.record_audited_reentry(
            audited_reentry_result=audited_reentry,
            control_plane=audited_reentry.control_plane,
        )
        receipt = CompleteHumanReviewReentryReceipt.create(
            resume_operation_digest=resume_operation.digest(),
            audited_reentry_result_digest=audited_reentry.digest(),
            audited_reentry_receipt_digest=audited_reentry.receipt.digest(),
            final_workflow_operation_digest=final_workflow.digest(),
            before_state_digest=resume_operation.run_state.digest(),
            after_state_digest=final_workflow.run_state.digest(),
            before_control_plane_digest=resume_operation.control_plane.digest(),
            audited_reentry_control_plane_digest=audited_reentry.control_plane.digest(),
            after_control_plane_digest=final_workflow.control_plane.digest(),
            final_stage=audited_reentry.final_stage(),
            reentry_status=audited_reentry.reentry_status(),
            audit_status=audited_reentry.audit_status(),
            report_status=final_workflow.report.status,
            max_steps=max_steps,
            executed_steps=audited_reentry.receipt.executed_steps,
        )

        return CompleteHumanReviewReentryResult.create(
            resume_operation=resume_operation,
            audited_reentry_result=audited_reentry,
            final_workflow_operation=final_workflow,
            receipt=receipt,
        )
