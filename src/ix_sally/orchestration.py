"""Stage-gated one-step orchestration for IX-Sally run states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from ix_sally.authority_processing import AuthorityProcessor
from ix_sally.chamber_closing import ChamberCloseResult, ChamberCloser
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.evidence_support_processing import EvidenceSupportProcessor
from ix_sally.execution_dispatch import ExecutionDispatcher
from ix_sally.execution_planning import ExecutionPlanner
from ix_sally.forge_result_processing import ForgeResultProcessor
from ix_sally.forge_results import ForgeResultRecord
from ix_sally.foundation import FoundationError, require_text
from ix_sally.recording import StateRecorder
from ix_sally.stage_gate import RunStageGate, StageGateDecision
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState
from ix_sally.state_audit import StateAuditor


class StageAdvanceKind(StrEnum):
    """Outcome kind for one stage-gated orchestration step."""

    WAITING_FOR_PROPOSAL = "waiting_for_proposal"
    AUTHORITY_PROCESSED = "authority_processed"
    EXECUTION_PLANNED = "execution_planned"
    EXECUTION_DISPATCHED = "execution_dispatched"
    WAITING_FOR_FORGE_RESULTS = "waiting_for_forge_results"
    FORGE_RESULTS_PROCESSED = "forge_results_processed"
    EVIDENCE_SUPPORT_REVIEWED = "evidence_support_reviewed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    CHAMBER_CLOSE_ATTEMPTED = "chamber_close_attempted"


@dataclass(frozen=True, slots=True)
class StageAdvanceResult:
    """Receipt-grade result for one legal IX-Sally orchestration advance."""

    state: NinefoldRunState
    before_snapshot: RunStageSnapshot
    gate_decision: StageGateDecision
    kind: StageAdvanceKind
    detail: str
    processor_digest: DigestRecord | None = None

    def changed_state(self) -> bool:
        """Return whether the orchestration step changed the run state."""
        return self.state.digest() != self.before_snapshot.state_digest

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible orchestration result."""
        return {
            "state_digest": self.state.digest().value,
            "before_snapshot_digest": self.before_snapshot.digest().value,
            "gate_decision_digest": self.gate_decision.digest().value,
            "stage": self.before_snapshot.stage.value,
            "kind": self.kind.value,
            "detail": self.detail,
            "processor_digest": (
                {
                    "algorithm": self.processor_digest.algorithm,
                    "value": self.processor_digest.value,
                }
                if self.processor_digest is not None
                else None
            ),
            "changed_state": self.changed_state(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this orchestration result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StageOrchestrator:
    """Advances IX-Sally run state by exactly one legal stage at a time."""

    gate: RunStageGate
    authority_processor: AuthorityProcessor
    execution_planner: ExecutionPlanner
    execution_dispatcher: ExecutionDispatcher
    forge_result_processor: ForgeResultProcessor
    evidence_support_processor: EvidenceSupportProcessor
    chamber_closer: ChamberCloser

    @classmethod
    def create(cls) -> StageOrchestrator:
        """Create a stage orchestrator with the standard IX-Sally processors."""
        recorder = StateRecorder()
        return cls(
            gate=RunStageGate(),
            authority_processor=AuthorityProcessor(recorder),
            execution_planner=ExecutionPlanner(recorder),
            execution_dispatcher=ExecutionDispatcher(recorder),
            forge_result_processor=ForgeResultProcessor(recorder),
            evidence_support_processor=EvidenceSupportProcessor(recorder),
            chamber_closer=ChamberCloser(recorder=recorder, auditor=StateAuditor()),
        )

    def advance_once(
        self,
        *,
        state: NinefoldRunState,
        forge_results: Iterable[ForgeResultRecord] = (),
        chamber_close_summary: str = "IX-Sally chamber closed after staged work completed.",
    ) -> StageAdvanceResult:
        """Advance one legal stage and return a receipt-grade step result."""
        snapshot = RunStageSnapshot.from_state(state)
        decision = self.gate.require(state=state, expected_stage=snapshot.stage)
        normalized_results = tuple(forge_results)

        if normalized_results and snapshot.stage is not RunStage.FORGE_RESULT_PROCESSING:
            raise FoundationError("Forge results may only be processed at the Forge result stage")

        if snapshot.stage is RunStage.PROPOSAL_INTAKE:
            return self._unchanged_result(
                state=state,
                snapshot=snapshot,
                decision=decision,
                kind=StageAdvanceKind.WAITING_FOR_PROPOSAL,
                detail="No staged work is pending; Sally proposal intake is required.",
            )

        if snapshot.stage is RunStage.AUTHORITY_PROCESSING:
            result = self.authority_processor.process_all_proposed(state=state)
            return StageAdvanceResult(
                state=result.state,
                before_snapshot=snapshot,
                gate_decision=decision,
                kind=StageAdvanceKind.AUTHORITY_PROCESSED,
                detail="Processed proposed bounded actions through authority gates.",
                processor_digest=result.digest(),
            )

        if snapshot.stage is RunStage.EXECUTION_PLANNING:
            result = self.execution_planner.queue_all_authorized(state=state)
            return StageAdvanceResult(
                state=result.state,
                before_snapshot=snapshot,
                gate_decision=decision,
                kind=StageAdvanceKind.EXECUTION_PLANNED,
                detail="Queued authorized bounded actions for IX-Forge dispatch.",
                processor_digest=result.digest(),
            )

        if snapshot.stage is RunStage.FORGE_DISPATCH:
            result = self.execution_dispatcher.dispatch_all_queued(state=state)
            return StageAdvanceResult(
                state=result.state,
                before_snapshot=snapshot,
                gate_decision=decision,
                kind=StageAdvanceKind.EXECUTION_DISPATCHED,
                detail="Dispatched queued execution items to the Forge boundary.",
                processor_digest=result.digest(),
            )

        if snapshot.stage is RunStage.FORGE_RESULT_PROCESSING:
            if not normalized_results:
                return self._unchanged_result(
                    state=state,
                    snapshot=snapshot,
                    decision=decision,
                    kind=StageAdvanceKind.WAITING_FOR_FORGE_RESULTS,
                    detail="Dispatched execution items are waiting for supplied Forge results.",
                )

            result = self.forge_result_processor.process_results(
                state=state,
                results=normalized_results,
            )
            return StageAdvanceResult(
                state=result.state,
                before_snapshot=snapshot,
                gate_decision=decision,
                kind=StageAdvanceKind.FORGE_RESULTS_PROCESSED,
                detail="Processed supplied Forge results into action state.",
                processor_digest=result.digest(),
            )

        if snapshot.stage is RunStage.EVIDENCE_SUPPORT_REVIEW:
            result = self.evidence_support_processor.process_all_unreviewed(state=state)
            return StageAdvanceResult(
                state=result.state,
                before_snapshot=snapshot,
                gate_decision=decision,
                kind=StageAdvanceKind.EVIDENCE_SUPPORT_REVIEWED,
                detail="Reviewed unreviewed claims against recorded evidence.",
                processor_digest=result.digest(),
            )

        if snapshot.stage is RunStage.HUMAN_REVIEW:
            return self._unchanged_result(
                state=state,
                snapshot=snapshot,
                decision=decision,
                kind=StageAdvanceKind.HUMAN_REVIEW_REQUIRED,
                detail="Human review is required before autonomous orchestration can continue.",
            )

        if snapshot.stage is RunStage.CHAMBER_CLOSE_READY:
            close_result = self.chamber_closer.close_if_ready(
                state=state,
                summary=require_text(chamber_close_summary, field_name="chamber_close_summary"),
            )
            return self._chamber_close_result(
                snapshot=snapshot,
                decision=decision,
                close_result=close_result,
            )

        raise FoundationError(f"unsupported run stage: {snapshot.stage.value}")

    def _unchanged_result(
        self,
        *,
        state: NinefoldRunState,
        snapshot: RunStageSnapshot,
        decision: StageGateDecision,
        kind: StageAdvanceKind,
        detail: str,
    ) -> StageAdvanceResult:
        """Return an unchanged orchestration result."""
        return StageAdvanceResult(
            state=state,
            before_snapshot=snapshot,
            gate_decision=decision,
            kind=kind,
            detail=detail,
        )

    def _chamber_close_result(
        self,
        *,
        snapshot: RunStageSnapshot,
        decision: StageGateDecision,
        close_result: ChamberCloseResult,
    ) -> StageAdvanceResult:
        """Return a normalized chamber-close orchestration result."""
        return StageAdvanceResult(
            state=close_result.state,
            before_snapshot=snapshot,
            gate_decision=decision,
            kind=StageAdvanceKind.CHAMBER_CLOSE_ATTEMPTED,
            detail=close_result.summary,
            processor_digest=close_result.digest(),
        )
