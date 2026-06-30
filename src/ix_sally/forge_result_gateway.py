"""Stage-gated Forge result submission for IX-Sally orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.forge_result_processing import (
    ForgeResultBatchProcessingResult,
    ForgeResultProcessor,
)
from ix_sally.forge_results import ForgeResultRecord
from ix_sally.foundation import FoundationError, require_text
from ix_sally.recording import StateRecorder
from ix_sally.stage_gate import RunStageGate, StageGateDecision
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class ForgeResultSubmissionReceipt:
    """Compact receipt for a stage-gated Forge result submission."""

    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    gate_decision_digest: DigestRecord
    processing_digest: DigestRecord
    result_count: int
    passed_count: int
    human_review_count: int
    detail: str

    @classmethod
    def create(
        cls,
        *,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        processing_digest: DigestRecord,
        result_count: int,
        passed_count: int,
        human_review_count: int,
        detail: str,
    ) -> ForgeResultSubmissionReceipt:
        """Create a normalized Forge result submission receipt."""
        if result_count <= 0:
            raise FoundationError("Forge result submission result_count must be positive")
        if passed_count < 0:
            raise FoundationError("Forge result submission passed_count must not be negative")
        if human_review_count < 0:
            raise FoundationError(
                "Forge result submission human_review_count must not be negative"
            )
        if passed_count > result_count:
            raise FoundationError("Forge result submission passed_count exceeds result_count")
        if human_review_count > result_count:
            raise FoundationError(
                "Forge result submission human_review_count exceeds result_count"
            )

        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")
        processing_digest.require_algorithm("sha256")

        return cls(
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            gate_decision_digest=gate_decision_digest,
            processing_digest=processing_digest,
            result_count=result_count,
            passed_count=passed_count,
            human_review_count=human_review_count,
            detail=require_text(detail, field_name="detail"),
        )

    @classmethod
    def from_processing(
        cls,
        *,
        before_state_digest: DigestRecord,
        gate_decision: StageGateDecision,
        processing_result: ForgeResultBatchProcessingResult,
    ) -> ForgeResultSubmissionReceipt:
        """Create a submission receipt from a Forge result processing batch."""
        return cls.create(
            before_state_digest=before_state_digest,
            after_state_digest=processing_result.state.digest(),
            gate_decision_digest=gate_decision.digest(),
            processing_digest=processing_result.digest(),
            result_count=processing_result.processed_count(),
            passed_count=processing_result.passed_count(),
            human_review_count=processing_result.human_review_count(),
            detail="Accepted Forge results into run state after Forge-result stage gate.",
        )

    def changed_state(self) -> bool:
        """Return whether this submission changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def requires_human_review(self) -> bool:
        """Return whether submitted Forge results require human review."""
        return self.human_review_count > 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result submission receipt."""
        return {
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "processing_digest": {
                "algorithm": self.processing_digest.algorithm,
                "value": self.processing_digest.value,
            },
            "result_count": self.result_count,
            "passed_count": self.passed_count,
            "human_review_count": self.human_review_count,
            "changed_state": self.changed_state(),
            "requires_human_review": self.requires_human_review(),
            "detail": self.detail,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result submission receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeResultSubmissionResult:
    """Result of submitting Forge results through the stage gate."""

    state: NinefoldRunState
    before_snapshot: RunStageSnapshot
    gate_decision: StageGateDecision
    processing_result: ForgeResultBatchProcessingResult
    receipt: ForgeResultSubmissionReceipt

    def next_snapshot(self) -> RunStageSnapshot:
        """Return the next stage snapshot after Forge result submission."""
        return RunStageSnapshot.from_state(self.state)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result submission result."""
        result_payload: JsonArray = []
        for processed in self.processing_result.processed:
            result_payload.append(processed.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "before_snapshot_digest": self.before_snapshot.digest().value,
            "before_stage": self.before_snapshot.stage.value,
            "next_snapshot_digest": self.next_snapshot().digest().value,
            "next_stage": self.next_snapshot().stage.value,
            "gate_decision_digest": self.gate_decision.digest().value,
            "processing_digest": self.processing_result.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "result_count": self.processing_result.processed_count(),
            "passed_count": self.processing_result.passed_count(),
            "human_review_count": self.processing_result.human_review_count(),
            "processed": result_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result submission result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeResultGateway:
    """Accepts Forge results only when the run state is waiting for Forge results."""

    gate: RunStageGate
    processor: ForgeResultProcessor

    @classmethod
    def create(cls) -> ForgeResultGateway:
        """Create a Forge result gateway with the standard IX-Sally recorder."""
        recorder = StateRecorder()
        return cls(
            gate=RunStageGate(),
            processor=ForgeResultProcessor(recorder),
        )

    def submit(
        self,
        *,
        state: NinefoldRunState,
        results: Iterable[ForgeResultRecord],
    ) -> ForgeResultSubmissionResult:
        """Submit Forge results if and only if Forge result processing is active."""
        normalized_results = tuple(results)
        if not normalized_results:
            raise FoundationError("Forge result submission requires at least one result")

        before_snapshot = RunStageSnapshot.from_state(state)
        decision = self.gate.require(
            state=state,
            expected_stage=RunStage.FORGE_RESULT_PROCESSING,
        )

        self._require_results_match_pending_dispatches(
            state=state,
            results=normalized_results,
        )
        processing_result = self.processor.process_results(
            state=state,
            results=normalized_results,
        )
        receipt = ForgeResultSubmissionReceipt.from_processing(
            before_state_digest=before_snapshot.state_digest,
            gate_decision=decision,
            processing_result=processing_result,
        )

        return ForgeResultSubmissionResult(
            state=processing_result.state,
            before_snapshot=before_snapshot,
            gate_decision=decision,
            processing_result=processing_result,
            receipt=receipt,
        )

    def _require_results_match_pending_dispatches(
        self,
        *,
        state: NinefoldRunState,
        results: tuple[ForgeResultRecord, ...],
    ) -> None:
        """Reject Forge results that do not match pending dispatched queue items."""
        pending_queue_digests = {
            item.digest().value for item in state.execution_queue.dispatched_items()
        }
        recorded_queue_digests = {
            result.queue_item_digest.value for result in state.forge_results.results
        }
        supplied_queue_digests: set[str] = set()

        for result in results:
            result.queue_item_digest.require_algorithm("sha256")
            result.action_digest.require_algorithm("sha256")

            queue_digest = result.queue_item_digest.value
            if queue_digest in supplied_queue_digests:
                raise FoundationError("duplicate Forge result for dispatched queue item")
            if queue_digest in recorded_queue_digests:
                raise FoundationError("Forge result already recorded for dispatched queue item")
            if queue_digest not in pending_queue_digests:
                raise FoundationError(
                    "Forge result does not match a pending dispatched queue item"
                )

            action = state.actions.require_action(result.action_id.value)
            if result.action_digest != action.digest():
                raise FoundationError("Forge result action digest must match current action")

            supplied_queue_digests.add(queue_digest)
