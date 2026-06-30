"""Stage-readiness snapshots for IX-Sally run-state orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.state import NinefoldRunState


class RunStage(StrEnum):
    """Deterministic next-stage labels for an IX-Sally run state."""

    PROPOSAL_INTAKE = "proposal_intake"
    AUTHORITY_PROCESSING = "authority_processing"
    EXECUTION_PLANNING = "execution_planning"
    FORGE_DISPATCH = "forge_dispatch"
    FORGE_RESULT_PROCESSING = "forge_result_processing"
    EVIDENCE_SUPPORT_REVIEW = "evidence_support_review"
    HUMAN_REVIEW = "human_review"
    CHAMBER_CLOSE_READY = "chamber_close_ready"


@dataclass(frozen=True, slots=True)
class RunStageCounts:
    """Count summary used to explain the next required IX-Sally stage."""

    proposed_actions: int
    executable_actions: int
    pending_execution_planning: int
    queued_executions: int
    dispatched_executions: int
    pending_forge_results: int
    claims: int
    unreviewed_claims: int
    evidence_support_findings: int
    human_review_required: bool
    completed_cycles: int

    @classmethod
    def from_state(cls, state: NinefoldRunState) -> RunStageCounts:
        """Create deterministic stage counts from a run state."""
        queued_action_ids = {item.action_id for item in state.execution_queue.items}
        executable_actions = state.actions.executable_actions()
        pending_execution_planning = sum(
            1 for action in executable_actions if action.action_id not in queued_action_ids
        )

        result_queue_digests = {
            result.queue_item_digest.value for result in state.forge_results.results
        }
        pending_forge_results = sum(
            1
            for item in state.execution_queue.dispatched_items()
            if item.digest().value not in result_queue_digests
        )

        reviewed_claim_digests = {
            finding.claim_digest.value for finding in state.evidence_support.findings
        }
        unreviewed_claims = sum(
            1 for claim in state.claims.claims if claim.digest().value not in reviewed_claim_digests
        )

        return cls(
            proposed_actions=state.proposed_action_count(),
            executable_actions=state.executable_action_count(),
            pending_execution_planning=pending_execution_planning,
            queued_executions=state.queued_execution_count(),
            dispatched_executions=state.dispatched_execution_count(),
            pending_forge_results=pending_forge_results,
            claims=len(state.claims.claims),
            unreviewed_claims=unreviewed_claims,
            evidence_support_findings=len(state.evidence_support.findings),
            human_review_required=state.requires_human_review(),
            completed_cycles=state.completed_cycles(),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible count representation."""
        return {
            "proposed_actions": self.proposed_actions,
            "executable_actions": self.executable_actions,
            "pending_execution_planning": self.pending_execution_planning,
            "queued_executions": self.queued_executions,
            "dispatched_executions": self.dispatched_executions,
            "pending_forge_results": self.pending_forge_results,
            "claims": self.claims,
            "unreviewed_claims": self.unreviewed_claims,
            "evidence_support_findings": self.evidence_support_findings,
            "human_review_required": self.human_review_required,
            "completed_cycles": self.completed_cycles,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for these stage counts."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class RunStageSnapshot:
    """Receipt-grade snapshot of what an IX-Sally run state must do next."""

    state_digest: DigestRecord
    stage: RunStage
    detail: str
    counts: RunStageCounts
    stop_condition_active: bool
    stop_reason: str | None

    @classmethod
    def from_state(cls, state: NinefoldRunState) -> RunStageSnapshot:
        """Create a deterministic next-stage snapshot from a run state."""
        state_digest = state.digest()
        counts = RunStageCounts.from_state(state)
        stop_condition = state.runtime_kit.chamber.stop_for_cycle(state.completed_cycles())
        stage, detail = _select_stage(counts=counts, stop_condition_active=stop_condition.should_stop)

        return cls(
            state_digest=state_digest,
            stage=stage,
            detail=detail,
            counts=counts,
            stop_condition_active=stop_condition.should_stop,
            stop_reason=stop_condition.reason.value if stop_condition.reason is not None else None,
        )

    def requires_human_review(self) -> bool:
        """Return whether the next stage is human review."""
        return self.stage is RunStage.HUMAN_REVIEW

    def ready_for_chamber_close(self) -> bool:
        """Return whether this state can advance to audit-gated chamber close."""
        return self.stage is RunStage.CHAMBER_CLOSE_READY

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible stage snapshot representation."""
        return {
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "stage": self.stage.value,
            "detail": self.detail,
            "counts": self.counts.to_payload(),
            "stop_condition_active": self.stop_condition_active,
            "stop_reason": self.stop_reason,
            "requires_human_review": self.requires_human_review(),
            "ready_for_chamber_close": self.ready_for_chamber_close(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this stage snapshot."""
        return DigestRecord.from_payload(self.to_payload())


def _select_stage(
    *,
    counts: RunStageCounts,
    stop_condition_active: bool,
) -> tuple[RunStage, str]:
    """Select the next stage and explanation from deterministic counts."""
    if counts.human_review_required:
        return (
            RunStage.HUMAN_REVIEW,
            "Run state contains a human-boundary or blocker record.",
        )

    if counts.proposed_actions > 0:
        return (
            RunStage.AUTHORITY_PROCESSING,
            "Proposed bounded actions require authority decisions.",
        )

    if counts.pending_execution_planning > 0:
        return (
            RunStage.EXECUTION_PLANNING,
            "Authorized bounded actions are not yet present in the execution queue.",
        )

    if counts.queued_executions > 0:
        return (
            RunStage.FORGE_DISPATCH,
            "Queued execution items require IX-Forge dispatch.",
        )

    if counts.pending_forge_results > 0:
        return (
            RunStage.FORGE_RESULT_PROCESSING,
            "Dispatched execution items require Forge result processing.",
        )

    if counts.unreviewed_claims > 0:
        return (
            RunStage.EVIDENCE_SUPPORT_REVIEW,
            "Recorded claims require IX-Verity evidence support review.",
        )

    if stop_condition_active:
        return (
            RunStage.CHAMBER_CLOSE_READY,
            "Chamber stop condition is active and no staged work is pending.",
        )

    return (
        RunStage.PROPOSAL_INTAKE,
        "No staged work is pending; the run can accept the next Sally proposal.",
    )
