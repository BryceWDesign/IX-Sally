"""Receipt-backed bounded orchestration loops for IX-Sally."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.forge_results import ForgeResultRecord
from ix_sally.foundation import FoundationError, require_text
from ix_sally.orchestration import StageAdvanceKind, StageAdvanceResult, StageOrchestrator
from ix_sally.orchestration_receipts import StageAdvanceTrace
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


class StageLoopStopReason(StrEnum):
    """Reason a bounded orchestration loop stopped."""

    EXTERNAL_INPUT_REQUIRED = "external_input_required"
    CHAMBER_CLOSE_ATTEMPTED = "chamber_close_attempted"
    STEP_LIMIT_REACHED = "step_limit_reached"


@dataclass(frozen=True, slots=True)
class StageLoopResult:
    """Receipt-grade result for a bounded IX-Sally orchestration loop."""

    state: NinefoldRunState
    trace: StageAdvanceTrace
    stop_reason: StageLoopStopReason
    final_snapshot: RunStageSnapshot
    max_steps: int
    forge_results_consumed: int

    def executed_steps(self) -> int:
        """Return how many orchestration steps were executed."""
        return len(self.trace.ledger.receipts)

    def stopped_for_external_input(self) -> bool:
        """Return whether the loop stopped because outside input is required."""
        return self.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED

    def stopped_for_step_limit(self) -> bool:
        """Return whether the loop stopped because the step budget was exhausted."""
        return self.stop_reason is StageLoopStopReason.STEP_LIMIT_REACHED

    def attempted_chamber_close(self) -> bool:
        """Return whether the loop stopped after a chamber close attempt."""
        return self.stop_reason is StageLoopStopReason.CHAMBER_CLOSE_ATTEMPTED

    def latest_kind(self) -> StageAdvanceKind | None:
        """Return the latest recorded advance kind, if any."""
        latest = self.trace.latest()
        if latest is None:
            return None
        return latest.kind

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible loop result."""
        latest = self.trace.latest()
        return {
            "state_digest": self.state.digest().value,
            "trace_digest": self.trace.digest().value,
            "stop_reason": self.stop_reason.value,
            "final_snapshot_digest": self.final_snapshot.digest().value,
            "final_stage": self.final_snapshot.stage.value,
            "max_steps": self.max_steps,
            "executed_steps": self.executed_steps(),
            "forge_results_consumed": self.forge_results_consumed,
            "latest_receipt_digest": latest.digest().value if latest is not None else None,
            "latest_kind": self.latest_kind().value if self.latest_kind() is not None else None,
            "stopped_for_external_input": self.stopped_for_external_input(),
            "stopped_for_step_limit": self.stopped_for_step_limit(),
            "attempted_chamber_close": self.attempted_chamber_close(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this loop result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StageLoopRunner:
    """Runs legal IX-Sally stages until a deterministic stop condition is reached."""

    orchestrator: StageOrchestrator

    @classmethod
    def create(cls) -> StageLoopRunner:
        """Create a loop runner with the standard stage orchestrator."""
        return cls(orchestrator=StageOrchestrator.create())

    def run_until_stop(
        self,
        *,
        state: NinefoldRunState,
        max_steps: int,
        forge_results: Iterable[ForgeResultRecord] = (),
        chamber_close_summary: str = (
            "IX-Sally chamber closed after staged work completed."
        ),
    ) -> StageLoopResult:
        """Advance legal stages until input, close-attempt, or step limit stops the loop."""
        if max_steps <= 0:
            raise FoundationError("stage loop max_steps must be positive")

        summary = require_text(
            chamber_close_summary,
            field_name="chamber_close_summary",
        )
        current = state
        trace = StageAdvanceTrace.create()
        supplied_forge_results = tuple(forge_results)
        consumed_forge_results = 0

        for _step in range(max_steps):
            snapshot = RunStageSnapshot.from_state(current)
            staged_results = self._forge_results_for_stage(
                snapshot=snapshot,
                forge_results=supplied_forge_results,
                consumed_count=consumed_forge_results,
            )
            consumed_forge_results += len(staged_results)

            result = self.orchestrator.advance_once(
                state=current,
                forge_results=staged_results,
                chamber_close_summary=summary,
            )
            current = result.state
            trace = trace.record_result(result)

            stop_reason = self._stop_reason_for_result(result)
            if stop_reason is not None:
                return StageLoopResult(
                    state=current,
                    trace=trace,
                    stop_reason=stop_reason,
                    final_snapshot=RunStageSnapshot.from_state(current),
                    max_steps=max_steps,
                    forge_results_consumed=consumed_forge_results,
                )

        return StageLoopResult(
            state=current,
            trace=trace,
            stop_reason=StageLoopStopReason.STEP_LIMIT_REACHED,
            final_snapshot=RunStageSnapshot.from_state(current),
            max_steps=max_steps,
            forge_results_consumed=consumed_forge_results,
        )

    def _forge_results_for_stage(
        self,
        *,
        snapshot: RunStageSnapshot,
        forge_results: tuple[ForgeResultRecord, ...],
        consumed_count: int,
    ) -> tuple[ForgeResultRecord, ...]:
        """Return Forge results only when the current stage can legally consume them."""
        if snapshot.stage is not RunStage.FORGE_RESULT_PROCESSING:
            return ()

        return forge_results[consumed_count:]

    def _stop_reason_for_result(
        self,
        result: StageAdvanceResult,
    ) -> StageLoopStopReason | None:
        """Return the loop stop reason implied by one advance result."""
        if result.kind in {
            StageAdvanceKind.WAITING_FOR_PROPOSAL,
            StageAdvanceKind.WAITING_FOR_FORGE_RESULTS,
            StageAdvanceKind.HUMAN_REVIEW_REQUIRED,
        }:
            return StageLoopStopReason.EXTERNAL_INPUT_REQUIRED

        if result.kind is StageAdvanceKind.CHAMBER_CLOSE_ATTEMPTED:
            return StageLoopStopReason.CHAMBER_CLOSE_ATTEMPTED

        return None
