"""Forge result processing flow for IX-Sally action completion."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.actions import BoundedActionRecord
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.forge_results import ForgeResultRecord
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class ForgeResultProcessingResult:
    """Result of recording a Forge result and updating the bounded action ledger."""

    state: NinefoldRunState
    original_action: BoundedActionRecord
    forge_result: ForgeResultRecord
    updated_action: BoundedActionRecord

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result processing result."""
        return {
            "state_digest": self.state.digest().value,
            "original_action_digest": self.original_action.digest().value,
            "forge_result_digest": self.forge_result.digest().value,
            "updated_action_digest": self.updated_action.digest().value,
            "updated_action_status": self.updated_action.status.value,
            "forge_result_status": self.forge_result.status.value,
            "requires_human_review": self.forge_result.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result processing result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeResultBatchProcessingResult:
    """Result of processing all supplied Forge results in order."""

    state: NinefoldRunState
    processed: tuple[ForgeResultProcessingResult, ...]

    def processed_count(self) -> int:
        """Return how many Forge results were processed."""
        return len(self.processed)

    def passed_count(self) -> int:
        """Return how many processed Forge results passed."""
        return sum(1 for result in self.processed if result.forge_result.succeeded())

    def human_review_count(self) -> int:
        """Return how many processed Forge results require human review."""
        return sum(1 for result in self.processed if result.forge_result.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible Forge result batch result."""
        processed_payload: JsonArray = []
        for result in self.processed:
            processed_payload.append(result.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "processed_count": self.processed_count(),
            "passed_count": self.passed_count(),
            "human_review_count": self.human_review_count(),
            "processed": processed_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this Forge result batch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ForgeResultProcessor:
    """Processes Forge execution results into run state and action completion records."""

    recorder: StateRecorder

    def process_result(
        self,
        *,
        state: NinefoldRunState,
        result: ForgeResultRecord,
    ) -> ForgeResultProcessingResult:
        """Record one Forge result and update the matching bounded action."""
        action = state.actions.require_action(result.action_id.value)
        self._require_result_matches_action(action=action, result=result)

        if result.succeeded():
            updated_action = action.with_execution_digest(result.digest())
        else:
            updated_action = action.with_blocking_result(
                execution_digest=result.digest(),
                boundary_note=self._blocking_note(result),
            )

        updated_state = self.recorder.record_forge_result(state, result)
        updated_state = updated_state.replace_action(updated_action)
        updated_state = self.recorder.record_action(updated_state, updated_action)

        return ForgeResultProcessingResult(
            state=updated_state,
            original_action=action,
            forge_result=result,
            updated_action=updated_action,
        )

    def process_results(
        self,
        *,
        state: NinefoldRunState,
        results: tuple[ForgeResultRecord, ...],
    ) -> ForgeResultBatchProcessingResult:
        """Process Forge results in the supplied order."""
        current = state
        processed: list[ForgeResultProcessingResult] = []

        for result in results:
            processed_result = self.process_result(state=current, result=result)
            current = processed_result.state
            processed.append(processed_result)

        return ForgeResultBatchProcessingResult(
            state=current,
            processed=tuple(processed),
        )

    def _require_result_matches_action(
        self,
        *,
        action: BoundedActionRecord,
        result: ForgeResultRecord,
    ) -> None:
        """Reject Forge results that do not match the current action digest."""
        if result.cycle != action.cycle:
            raise FoundationError("Forge result cycle must match bounded action cycle")

        if result.action_digest != action.digest():
            raise FoundationError("Forge result action digest must match current bounded action")

    def _blocking_note(self, result: ForgeResultRecord) -> str:
        """Return the best available blocking note for failed or blocked Forge results."""
        if result.boundary_note is not None:
            return result.boundary_note

        if result.failure_reason is not None:
            return result.failure_reason

        return result.summary
