"""Human-review reentry into IX-Sally staged orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_reentry_status import HumanReviewReentryStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowOperation,
    HumanReviewWorkflowStage,
)
from ix_sally.orchestration_loop import StageLoopResult, StageLoopRunner, StageLoopStopReason
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewReentryReceipt:
    """Receipt proving a cleared human-review resume reentered orchestration."""

    receipt_id: CanonicalKey
    resume_operation_digest: DigestRecord
    resume_certificate_digest: DigestRecord
    control_plane_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    loop_digest: DigestRecord
    final_stage: RunStage
    stop_reason: StageLoopStopReason
    executed_steps: int
    status: HumanReviewReentryStatus

    @classmethod
    def create(
        cls,
        *,
        resume_operation_digest: DigestRecord,
        resume_certificate_digest: DigestRecord,
        control_plane_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        loop_digest: DigestRecord,
        final_stage: RunStage,
        stop_reason: StageLoopStopReason,
        executed_steps: int,
        status: HumanReviewReentryStatus,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewReentryReceipt:
        """Create a normalized human-review reentry receipt."""
        if executed_steps < 0:
            raise FoundationError("human-review reentry executed_steps must not be negative")

        resume_operation_digest.require_algorithm("sha256")
        resume_certificate_digest.require_algorithm("sha256")
        control_plane_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        loop_digest.require_algorithm("sha256")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-reentry-{resume_operation_digest.value[:16]}-"
                f"{after_state_digest.value[:16]}",
                field_name="receipt_id",
            ),
            resume_operation_digest=resume_operation_digest,
            resume_certificate_digest=resume_certificate_digest,
            control_plane_digest=control_plane_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            loop_digest=loop_digest,
            final_stage=final_stage,
            stop_reason=stop_reason,
            executed_steps=executed_steps,
            status=status,
        )

    def changed_state(self) -> bool:
        """Return whether reentry orchestration changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def stopped_for_external_input(self) -> bool:
        """Return whether reentry stopped because outside input is required."""
        return self.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "resume_operation_digest": {
                "algorithm": self.resume_operation_digest.algorithm,
                "value": self.resume_operation_digest.value,
            },
            "resume_certificate_digest": {
                "algorithm": self.resume_certificate_digest.algorithm,
                "value": self.resume_certificate_digest.value,
            },
            "control_plane_digest": {
                "algorithm": self.control_plane_digest.algorithm,
                "value": self.control_plane_digest.value,
            },
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "loop_digest": {
                "algorithm": self.loop_digest.algorithm,
                "value": self.loop_digest.value,
            },
            "final_stage": self.final_stage.value,
            "stop_reason": self.stop_reason.value,
            "executed_steps": self.executed_steps,
            "status": self.status.value,
            "changed_state": self.changed_state(),
            "stopped_for_external_input": self.stopped_for_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this reentry receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryResult:
    """Result of resuming staged orchestration after human-review clearance."""

    resume_operation: HumanReviewWorkflowOperation
    control_plane: HumanReviewControlPlaneState
    loop_result: StageLoopResult
    receipt: HumanReviewReentryReceipt

    @property
    def state(self) -> NinefoldRunState:
        """Return the post-reentry run state."""
        return self.loop_result.state

    def status(self) -> HumanReviewReentryStatus:
        """Return the reentry status from the receipt."""
        return self.receipt.status

    def final_stage(self) -> RunStage:
        """Return the final stage after reentry orchestration."""
        return self.loop_result.final_snapshot.stage

    def changed_state(self) -> bool:
        """Return whether reentry orchestration changed the run state."""
        return self.receipt.changed_state()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible reentry result."""
        return {
            "resume_operation_digest": self.resume_operation.digest().value,
            "control_plane_digest": self.control_plane.digest().value,
            "loop_digest": self.loop_result.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "state_digest": self.state.digest().value,
            "status": self.status().value,
            "final_stage": self.final_stage().value,
            "executed_steps": self.loop_result.executed_steps(),
            "changed_state": self.changed_state(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this reentry result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewReentryRunner:
    """Runs IX-Sally orchestration only from a certified human-review resume."""

    loop_runner: StageLoopRunner

    @classmethod
    def create(cls) -> HumanReviewReentryRunner:
        """Create a standard human-review reentry runner."""
        return cls(loop_runner=StageLoopRunner.create())

    def resume_until_stop(
        self,
        *,
        resume_operation: HumanReviewWorkflowOperation,
        max_steps: int,
    ) -> HumanReviewReentryResult:
        """Resume staged orchestration from a cleared human-review workflow operation."""
        self._require_resume_operation(resume_operation)
        resume_result = resume_operation.require_resume()
        loop_result = self.loop_runner.run_until_stop(
            state=resume_operation.run_state,
            max_steps=max_steps,
        )
        receipt = HumanReviewReentryReceipt.create(
            resume_operation_digest=resume_operation.digest(),
            resume_certificate_digest=resume_result.resume_result.certificate.digest(),
            control_plane_digest=resume_operation.control_plane.digest(),
            before_state_digest=resume_operation.run_state.digest(),
            after_state_digest=loop_result.state.digest(),
            loop_digest=loop_result.digest(),
            final_stage=loop_result.final_snapshot.stage,
            stop_reason=loop_result.stop_reason,
            executed_steps=loop_result.executed_steps(),
            status=self._status_from_loop(loop_result),
        )

        return HumanReviewReentryResult(
            resume_operation=resume_operation,
            control_plane=resume_operation.control_plane,
            loop_result=loop_result,
            receipt=receipt,
        )

    def _require_resume_operation(
        self,
        resume_operation: HumanReviewWorkflowOperation,
    ) -> None:
        """Raise unless the workflow operation is a cleared resume operation."""
        if resume_operation.receipt.workflow_stage is not HumanReviewWorkflowStage.RESUME_RECORDED:
            raise FoundationError("human-review reentry requires a resume-recorded operation")

        resume_result = resume_operation.require_resume()
        if not resume_result.cleared_to_resume():
            raise FoundationError("human-review reentry requires cleared resume authority")
        if resume_result.next_stage() is RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review reentry cannot resume to human_review")
        if resume_result.state.digest() != resume_operation.run_state.digest():
            raise FoundationError("human-review reentry resume state mismatch")

    def _status_from_loop(
        self,
        loop_result: StageLoopResult,
    ) -> HumanReviewReentryStatus:
        """Map a stage-loop stop reason to a reentry status."""
        if loop_result.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED:
            return HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
        if loop_result.stop_reason is StageLoopStopReason.CHAMBER_CLOSE_ATTEMPTED:
            return HumanReviewReentryStatus.CHAMBER_CLOSE_ATTEMPTED
        if loop_result.stop_reason is StageLoopStopReason.STEP_LIMIT_REACHED:
            if loop_result.executed_steps() > 0:
                return HumanReviewReentryStatus.ADVANCED
            return HumanReviewReentryStatus.STEP_LIMIT_REACHED

        raise FoundationError(
            f"unsupported human-review reentry stop reason: {loop_result.stop_reason.value}"
        )
