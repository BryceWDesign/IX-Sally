"""One-call coordination for complete IX-Sally human-review reentry closeout."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_complete_reentry import (
    CompleteHumanReviewReentryCoordinator,
    CompleteHumanReviewReentryResult,
)
from ix_sally.human_review_complete_reentry_closeout_status import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_complete_reentry_report import CompleteHumanReviewReentryCloseoutReport
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneOperationKind,
)
from ix_sally.human_review_control_plane_report_status import HumanReviewControlPlaneReportStatus
from ix_sally.human_review_reentry_audit_status import HumanReviewReentryAuditStatus
from ix_sally.human_review_reentry_status import HumanReviewReentryStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowOperation,
    HumanReviewWorkflowStage,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutCoordinationReceipt:
    """Receipt linking complete reentry execution, closeout, and closeout recording."""

    receipt_id: CanonicalKey
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
        receipt_id: CanonicalKey | None = None,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationReceipt:
        """Create a normalized complete reentry closeout coordination receipt."""
        if max_steps <= 0:
            raise FoundationError(
                "complete human-review reentry closeout coordination max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "complete human-review reentry closeout coordination executed_steps "
                "must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "complete human-review reentry closeout coordination executed_steps "
                "exceeds max_steps"
            )

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
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"complete-reentry-closeout-coordination-"
                f"{complete_reentry_result_digest.value[:16]}-"
                f"{closeout_status.value}",
                field_name="receipt_id",
            ),
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

    def changed_state(self) -> bool:
        """Return whether closeout coordination changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def recorded_complete_reentry(self) -> bool:
        """Return whether complete reentry recording changed the control plane."""
        return self.before_control_plane_digest != self.closeout_control_plane_digest

    def recorded_closeout(self) -> bool:
        """Return whether closeout recording changed the control plane."""
        return self.closeout_control_plane_digest != self.after_control_plane_digest

    def accepted(self) -> bool:
        """Return whether the closeout coordination accepted the reentry."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED

    def waiting_for_external_input(self) -> bool:
        """Return whether closeout coordination is valid but waiting externally."""
        return (
            self.closeout_status
            is CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def blocked(self) -> bool:
        """Return whether closeout coordination is blocked."""
        return self.closeout_status is CompleteHumanReviewReentryCloseoutStatus.BLOCKED

    def requires_operator_attention(self) -> bool:
        """Return whether this coordination requires operator attention."""
        return self.blocked()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination receipt."""
        return {
            "receipt_id": self.receipt_id.value,
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
        """Return a deterministic digest for this coordination receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutCoordinationResult:
    """Result of complete human-review reentry closeout coordination."""

    complete_reentry_result: CompleteHumanReviewReentryResult
    closeout_report: CompleteHumanReviewReentryCloseoutReport
    closeout_workflow_operation: HumanReviewWorkflowOperation
    receipt: CompleteHumanReviewReentryCloseoutCoordinationReceipt

    @classmethod
    def create(
        cls,
        *,
        complete_reentry_result: CompleteHumanReviewReentryResult,
        closeout_report: CompleteHumanReviewReentryCloseoutReport,
        closeout_workflow_operation: HumanReviewWorkflowOperation,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationResult:
        """Create a validated complete reentry closeout coordination result."""
        if closeout_report.complete_reentry_result_digest != (complete_reentry_result.digest()):
            raise FoundationError(
                "complete reentry closeout report must match complete reentry result"
            )
        if closeout_report.control_plane_digest != (
            closeout_workflow_operation.operation_result.before_control_plane.digest()
        ):
            raise FoundationError(
                "complete reentry closeout report must match closeout control plane"
            )
        if closeout_workflow_operation.receipt.workflow_stage is not (
            HumanReviewWorkflowStage.COMPLETE_REENTRY_CLOSEOUT_RECORDED
        ):
            raise FoundationError("complete reentry closeout workflow must record closeout stage")
        if closeout_workflow_operation.operation_kind() is not (
            HumanReviewControlPlaneOperationKind.COMPLETE_REENTRY_CLOSEOUT_RECORDED
        ):
            raise FoundationError(
                "complete reentry closeout workflow must record closeout operation"
            )
        if (
            closeout_workflow_operation.require_complete_reentry_closeout_report()
            != closeout_report
        ):
            raise FoundationError("complete reentry closeout workflow must carry closeout report")
        if closeout_workflow_operation.run_state.digest() != (
            complete_reentry_result.state.digest()
        ):
            raise FoundationError(
                "complete reentry closeout workflow state must match result state"
            )

        receipt = CompleteHumanReviewReentryCloseoutCoordinationReceipt.create(
            resume_operation_digest=(complete_reentry_result.receipt.resume_operation_digest),
            complete_reentry_result_digest=complete_reentry_result.digest(),
            complete_reentry_receipt_digest=complete_reentry_result.receipt.digest(),
            closeout_report_digest=closeout_report.digest(),
            closeout_workflow_operation_digest=closeout_workflow_operation.digest(),
            before_state_digest=complete_reentry_result.receipt.before_state_digest,
            after_state_digest=complete_reentry_result.receipt.after_state_digest,
            before_control_plane_digest=(
                complete_reentry_result.receipt.before_control_plane_digest
            ),
            closeout_control_plane_digest=closeout_report.control_plane_digest,
            after_control_plane_digest=closeout_workflow_operation.control_plane.digest(),
            final_stage=complete_reentry_result.final_stage(),
            reentry_status=complete_reentry_result.reentry_status(),
            audit_status=complete_reentry_result.audit_status(),
            report_status=closeout_report.report_status,
            closeout_status=closeout_report.closeout_status,
            max_steps=complete_reentry_result.receipt.max_steps,
            executed_steps=complete_reentry_result.receipt.executed_steps,
        )

        return cls(
            complete_reentry_result=complete_reentry_result,
            closeout_report=closeout_report,
            closeout_workflow_operation=closeout_workflow_operation,
            receipt=receipt,
        )

    @property
    def state(self) -> NinefoldRunState:
        """Return the final coordinated run state."""
        return self.closeout_workflow_operation.run_state

    @property
    def control_plane(self) -> HumanReviewControlPlaneState:
        """Return the final coordinated control-plane state."""
        return self.closeout_workflow_operation.control_plane

    def accepted(self) -> bool:
        """Return whether closeout coordination accepted the reentry."""
        return self.receipt.accepted()

    def waiting_for_external_input(self) -> bool:
        """Return whether closeout coordination is waiting externally."""
        return self.receipt.waiting_for_external_input()

    def blocked(self) -> bool:
        """Return whether closeout coordination is blocked."""
        return self.receipt.blocked()

    def requires_operator_attention(self) -> bool:
        """Return whether closeout coordination requires operator attention."""
        return self.receipt.requires_operator_attention()

    def final_stage(self) -> RunStage:
        """Return the final run stage after complete reentry closeout."""
        return self.receipt.final_stage

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination result."""
        return {
            "complete_reentry_result_digest": self.complete_reentry_result.digest().value,
            "closeout_report_digest": self.closeout_report.digest().value,
            "closeout_workflow_operation_digest": (self.closeout_workflow_operation.digest().value),
            "receipt_digest": self.receipt.digest().value,
            "state_digest": self.state.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "final_stage": self.final_stage().value,
            "closeout_status": self.closeout_report.closeout_status.value,
            "accepted": self.accepted(),
            "waiting_for_external_input": self.waiting_for_external_input(),
            "blocked": self.blocked(),
            "requires_operator_attention": self.requires_operator_attention(),
            "complete_reentry_count": self.control_plane.complete_reentry_count(),
            "complete_reentry_closeout_count": (
                self.control_plane.complete_reentry_closeout_count()
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CompleteHumanReviewReentryCloseoutCoordinator:
    """Runs complete reentry, closeout report creation, and closeout recording."""

    complete_reentry_coordinator: CompleteHumanReviewReentryCoordinator
    workflow: HumanReviewWorkflowKit

    @classmethod
    def create(cls) -> CompleteHumanReviewReentryCloseoutCoordinator:
        """Create the standard complete reentry closeout coordinator."""
        return cls(
            complete_reentry_coordinator=CompleteHumanReviewReentryCoordinator.create(),
            workflow=HumanReviewWorkflowKit.create(),
        )

    def resume_closeout_and_record(
        self,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        max_steps: int,
    ) -> CompleteHumanReviewReentryCloseoutCoordinationResult:
        """Resume, audit, finalize, close out, and record closeout in one call."""
        complete_reentry = self.complete_reentry_coordinator.resume_audit_record_and_finalize(
            resume_operation=resume_operation,
            max_steps=max_steps,
        )
        closeout_report = CompleteHumanReviewReentryCloseoutReport.from_result(complete_reentry)
        closeout_workflow = self.workflow.record_complete_reentry_closeout(
            run_state=complete_reentry.state,
            closeout_report=closeout_report,
            control_plane=complete_reentry.control_plane,
        )

        return CompleteHumanReviewReentryCloseoutCoordinationResult.create(
            complete_reentry_result=complete_reentry,
            closeout_report=closeout_report,
            closeout_workflow_operation=closeout_workflow,
        )
