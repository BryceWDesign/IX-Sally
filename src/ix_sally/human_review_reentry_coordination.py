"""One-call coordination for certified IX-Sally human-review reentry."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_reentry import (
    HumanReviewReentryResult,
    HumanReviewReentryRunner,
    HumanReviewReentryStatus,
)
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowOperation,
    HumanReviewWorkflowStage,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewReentryCoordinationReceipt:
    """Receipt proving a certified resume was reentered and ledger-recorded."""

    receipt_id: CanonicalKey
    resume_operation_digest: DigestRecord
    reentry_result_digest: DigestRecord
    workflow_operation_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_control_plane_digest: DigestRecord
    after_control_plane_digest: DigestRecord
    final_stage: RunStage
    reentry_status: HumanReviewReentryStatus
    report_status: HumanReviewControlPlaneReportStatus
    max_steps: int
    executed_steps: int

    @classmethod
    def create(
        cls,
        *,
        resume_operation_digest: DigestRecord,
        reentry_result_digest: DigestRecord,
        workflow_operation_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_control_plane_digest: DigestRecord,
        after_control_plane_digest: DigestRecord,
        final_stage: RunStage,
        reentry_status: HumanReviewReentryStatus,
        report_status: HumanReviewControlPlaneReportStatus,
        max_steps: int,
        executed_steps: int,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryCoordinationReceipt:
        """Create a normalized human-review reentry coordination receipt."""
        if max_steps <= 0:
            raise FoundationError(
                "human-review reentry coordination max_steps must be positive"
            )
        if executed_steps < 0:
            raise FoundationError(
                "human-review reentry coordination executed_steps must not be negative"
            )
        if executed_steps > max_steps:
            raise FoundationError(
                "human-review reentry coordination executed_steps exceeds max_steps"
            )

        resume_operation_digest.require_algorithm("sha256")
        reentry_result_digest.require_algorithm("sha256")
        workflow_operation_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_control_plane_digest.require_algorithm("sha256")
        after_control_plane_digest.require_algorithm("sha256")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-reentry-coordination-"
                f"{resume_operation_digest.value[:16]}-"
                f"{workflow_operation_digest.value[:16]}",
                field_name="receipt_id",
            ),
            resume_operation_digest=resume_operation_digest,
            reentry_result_digest=reentry_result_digest,
            workflow_operation_digest=workflow_operation_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_control_plane_digest=before_control_plane_digest,
            after_control_plane_digest=after_control_plane_digest,
            final_stage=final_stage,
            reentry_status=reentry_status,
            report_status=report_status,
            max_steps=max_steps,
            executed_steps=executed_steps,
        )

    def changed_state(self) -> bool:
        """Return whether reentry changed run state."""
        return self.before_state_digest != self.after_state_digest

    def changed_control_plane(self) -> bool:
        """Return whether reentry recording changed the control plane."""
        return self.before_control_plane_digest != self.after_control_plane_digest

    def recorded_reentry(self) -> bool:
        """Return whether the workflow report shows reentry was recorded."""
        return self.report_status in {
            HumanReviewControlPlaneReportStatus.REENTRY_RECORDED,
            HumanReviewControlPlaneReportStatus.REENTRY_WAITING_FOR_EXTERNAL_INPUT,
        }

    def waiting_for_external_input(self) -> bool:
        """Return whether reentry stopped waiting for outside input."""
        return (
            self.reentry_status
            is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry coordination receipt."""
        return {
            "receipt_id": self.receipt_id.value,
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
            "after_control_plane_digest": {
                "algorithm": self.after_control_plane_digest.algorithm,
                "value": self.after_control_plane_digest.value,
            },
            "final_stage": self.final_stage.value,
            "reentry_status": self.reentry_status.value,
            "report_status": self.report_status.value,
            "max_steps": self.max_steps,
            "executed_steps": self.executed_steps,
            "changed_state": self.changed_state(),
            "changed_control_plane": self.changed_control_plane(),
            "recorded_reentry": self.recorded_reentry(),
            "waiting_for_external_input": self.waiting_for_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryCoordinationResult:
    """Result of running and recording certified human-review reentry."""

    resume_operation: HumanReviewWorkflowOperation
    reentry_result: HumanReviewReentryResult
    workflow_operation: HumanReviewWorkflowOperation
    receipt: HumanReviewReentryCoordinationReceipt

    @classmethod
    def create(
        cls,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        reentry_result: HumanReviewReentryResult,
        workflow_operation: HumanReviewWorkflowOperation,
        receipt: HumanReviewReentryCoordinationReceipt,
    ) -> HumanReviewReentryCoordinationResult:
        """Create a normalized coordination result and validate all links."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "human-review reentry coordination requires resume-recorded operation"
            )
        if reentry_result.resume_operation.digest() != resume_operation.digest():
            raise FoundationError(
                "human-review reentry coordination resume operation mismatch"
            )
        if workflow_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.REENTRY_RECORDED:
            raise FoundationError(
                "human-review reentry coordination requires reentry-recorded workflow"
            )
        if workflow_operation.require_reentry().digest() != reentry_result.digest():
            raise FoundationError(
                "human-review reentry coordination workflow reentry mismatch"
            )
        if workflow_operation.run_state.digest() != reentry_result.state.digest():
            raise FoundationError(
                "human-review reentry coordination workflow state mismatch"
            )
        if receipt.resume_operation_digest != resume_operation.digest():
            raise FoundationError(
                "human-review reentry coordination receipt resume digest mismatch"
            )
        if receipt.reentry_result_digest != reentry_result.digest():
            raise FoundationError(
                "human-review reentry coordination receipt reentry digest mismatch"
            )
        if receipt.workflow_operation_digest != workflow_operation.digest():
            raise FoundationError(
                "human-review reentry coordination receipt workflow digest mismatch"
            )
        if receipt.after_state_digest != workflow_operation.run_state.digest():
            raise FoundationError(
                "human-review reentry coordination receipt state digest mismatch"
            )
        if receipt.after_control_plane_digest != workflow_operation.control_plane.digest():
            raise FoundationError(
                "human-review reentry coordination receipt control-plane digest mismatch"
            )

        return cls(
            resume_operation=resume_operation,
            reentry_result=reentry_result,
            workflow_operation=workflow_operation,
            receipt=receipt,
        )

    @property
    def state(self) -> NinefoldRunState:
        """Return the post-reentry run state."""
        return self.workflow_operation.run_state

    @property
    def control_plane(self) -> HumanReviewControlPlaneState:
        """Return the post-reentry human-review control plane."""
        return self.workflow_operation.control_plane

    def final_stage(self) -> RunStage:
        """Return the final run stage after coordinated reentry."""
        return self.receipt.final_stage

    def status(self) -> HumanReviewReentryStatus:
        """Return the reentry status."""
        return self.receipt.reentry_status

    def changed_state(self) -> bool:
        """Return whether coordinated reentry changed run state."""
        return self.receipt.changed_state()

    def changed_control_plane(self) -> bool:
        """Return whether coordinated reentry changed control-plane state."""
        return self.receipt.changed_control_plane()

    def recorded_reentry(self) -> bool:
        """Return whether the reentry was recorded in workflow state."""
        return self.receipt.recorded_reentry()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination result."""
        return {
            "resume_operation_digest": self.resume_operation.digest().value,
            "reentry_result_digest": self.reentry_result.digest().value,
            "workflow_operation_digest": self.workflow_operation.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "state_digest": self.state.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "final_stage": self.final_stage().value,
            "status": self.status().value,
            "report_status": self.workflow_operation.report.status.value,
            "max_steps": self.receipt.max_steps,
            "executed_steps": self.receipt.executed_steps,
            "changed_state": self.changed_state(),
            "changed_control_plane": self.changed_control_plane(),
            "recorded_reentry": self.recorded_reentry(),
            "reentry_count": self.control_plane.reentry_count(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryCoordinator:
    """Runs certified reentry and records it into the human-review workflow."""

    reentry_runner: HumanReviewReentryRunner
    workflow_kit: HumanReviewWorkflowKit

    @classmethod
    def create(cls) -> HumanReviewReentryCoordinator:
        """Create a standard human-review reentry coordinator."""
        return cls(
            reentry_runner=HumanReviewReentryRunner.create(),
            workflow_kit=HumanReviewWorkflowKit.create(),
        )

    def resume_and_record(
        self,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        max_steps: int,
    ) -> HumanReviewReentryCoordinationResult:
        """Resume staged orchestration and record the reentry in one operation."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError(
                "human-review reentry coordination requires resume-recorded operation"
            )

        reentry_result = self.reentry_runner.resume_until_stop(
            resume_operation=resume_operation,
            max_steps=max_steps,
        )
        workflow_operation = self.workflow_kit.record_reentry(
            reentry_result=reentry_result,
            control_plane=resume_operation.control_plane,
        )
        receipt = HumanReviewReentryCoordinationReceipt.create(
            resume_operation_digest=resume_operation.digest(),
            reentry_result_digest=reentry_result.digest(),
            workflow_operation_digest=workflow_operation.digest(),
            before_state_digest=resume_operation.run_state.digest(),
            after_state_digest=workflow_operation.run_state.digest(),
            before_control_plane_digest=resume_operation.control_plane.digest(),
            after_control_plane_digest=workflow_operation.control_plane.digest(),
            final_stage=reentry_result.final_stage(),
            reentry_status=reentry_result.status(),
            report_status=workflow_operation.report.status,
            max_steps=max_steps,
            executed_steps=reentry_result.loop_result.executed_steps(),
        )

        return HumanReviewReentryCoordinationResult.create(
            resume_operation=resume_operation,
            reentry_result=reentry_result,
            workflow_operation=workflow_operation,
            receipt=receipt,
        )
