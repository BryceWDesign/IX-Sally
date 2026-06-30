"""Human-boundary decision gateway for IX-Sally staged orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.actions import ActionStatus, BoundedActionRecord
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.events import RuntimeEvent, RuntimeEventType
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.stage_gate import RunStageGate, StageGateDecision
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


class HumanReviewDecisionStatus(StrEnum):
    """Human-boundary decision status for an unresolved action."""

    APPROVED_FOR_EXECUTION = "approved_for_execution"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class HumanReviewTargetType(StrEnum):
    """Supported human-review target kinds."""

    BOUNDED_ACTION = "bounded_action"


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    """One human-boundary decision over a review-bound target."""

    decision_id: CanonicalKey
    cycle: int
    reviewer: str
    target_type: HumanReviewTargetType
    target_id: CanonicalKey
    target_digest: DigestRecord
    status: HumanReviewDecisionStatus
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        reviewer: str,
        target_type: HumanReviewTargetType,
        target_id: str,
        target_digest: DigestRecord,
        status: HumanReviewDecisionStatus,
        rationale: str,
        decision_id: CanonicalKey | None = None,
    ) -> HumanReviewDecision:
        """Create a normalized human-review decision."""
        if cycle < 0:
            raise FoundationError("human-review decision cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_reviewer = require_text(reviewer, field_name="reviewer")
        normalized_target_id = CanonicalKey.from_text(target_id, field_name="target_id")
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            decision_id=decision_id
            or CanonicalKey.from_text(
                f"human-review-{cycle}-{target_type.value}-{normalized_target_id.value}-"
                f"{status.value}-{normalized_reviewer}-{normalized_rationale}",
                field_name="decision_id",
            ),
            cycle=cycle,
            reviewer=normalized_reviewer,
            target_type=target_type,
            target_id=normalized_target_id,
            target_digest=target_digest,
            status=status,
            rationale=normalized_rationale,
        )

    def approves_target(self) -> bool:
        """Return whether this decision approves the target for the next stage."""
        return self.status is HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION

    def rejects_target(self) -> bool:
        """Return whether this decision rejects the target."""
        return self.status is HumanReviewDecisionStatus.REJECTED

    def defers_target(self) -> bool:
        """Return whether this decision leaves the target unresolved."""
        return self.status is HumanReviewDecisionStatus.DEFERRED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review decision."""
        return {
            "decision_id": self.decision_id.value,
            "cycle": self.cycle,
            "reviewer": self.reviewer,
            "target_type": self.target_type.value,
            "target_id": self.target_id.value,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "status": self.status.value,
            "rationale": self.rationale,
            "approves_target": self.approves_target(),
            "rejects_target": self.rejects_target(),
            "defers_target": self.defers_target(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review decision."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewSubmissionReceipt:
    """Compact receipt for a human-boundary action decision."""

    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_action_digest: DigestRecord
    after_action_digest: DigestRecord
    gate_decision_digest: DigestRecord
    human_decision_digest: DigestRecord
    status: HumanReviewDecisionStatus
    detail: str

    @classmethod
    def create(
        cls,
        *,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_action_digest: DigestRecord,
        after_action_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        human_decision_digest: DigestRecord,
        status: HumanReviewDecisionStatus,
        detail: str,
    ) -> HumanReviewSubmissionReceipt:
        """Create a normalized human-review submission receipt."""
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_action_digest.require_algorithm("sha256")
        after_action_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")
        human_decision_digest.require_algorithm("sha256")

        return cls(
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_action_digest=before_action_digest,
            after_action_digest=after_action_digest,
            gate_decision_digest=gate_decision_digest,
            human_decision_digest=human_decision_digest,
            status=status,
            detail=require_text(detail, field_name="detail"),
        )

    def changed_state(self) -> bool:
        """Return whether the human-review submission changed the run state."""
        return self.before_state_digest != self.after_state_digest

    def changed_action(self) -> bool:
        """Return whether the human-review submission changed the target action."""
        return self.before_action_digest != self.after_action_digest

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review submission receipt."""
        return {
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "before_action_digest": {
                "algorithm": self.before_action_digest.algorithm,
                "value": self.before_action_digest.value,
            },
            "after_action_digest": {
                "algorithm": self.after_action_digest.algorithm,
                "value": self.after_action_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "human_decision_digest": {
                "algorithm": self.human_decision_digest.algorithm,
                "value": self.human_decision_digest.value,
            },
            "status": self.status.value,
            "detail": self.detail,
            "changed_state": self.changed_state(),
            "changed_action": self.changed_action(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review submission receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewSubmissionResult:
    """Result of submitting a human-boundary action decision."""

    state: NinefoldRunState
    before_snapshot: RunStageSnapshot
    gate_decision: StageGateDecision
    decision: HumanReviewDecision
    before_action: BoundedActionRecord
    after_action: BoundedActionRecord
    receipt: HumanReviewSubmissionReceipt

    def next_snapshot(self) -> RunStageSnapshot:
        """Return the next stage snapshot after the human-review decision."""
        return RunStageSnapshot.from_state(self.state)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review submission result."""
        return {
            "state_digest": self.state.digest().value,
            "before_snapshot_digest": self.before_snapshot.digest().value,
            "before_stage": self.before_snapshot.stage.value,
            "next_snapshot_digest": self.next_snapshot().digest().value,
            "next_stage": self.next_snapshot().stage.value,
            "gate_decision_digest": self.gate_decision.digest().value,
            "human_decision_digest": self.decision.digest().value,
            "before_action_digest": self.before_action.digest().value,
            "after_action_digest": self.after_action.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "decision_status": self.decision.status.value,
            "changed_state": self.receipt.changed_state(),
            "changed_action": self.receipt.changed_action(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review submission result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewGateway:
    """Accepts human-boundary decisions only when human review is active."""

    gate: RunStageGate

    @classmethod
    def create(cls) -> HumanReviewGateway:
        """Create a human-review gateway."""
        return cls(gate=RunStageGate())

    def decide_action(
        self,
        *,
        state: NinefoldRunState,
        action_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        rationale: str,
    ) -> HumanReviewSubmissionResult:
        """Apply a human-boundary decision to a review-bound bounded action."""
        before_snapshot = RunStageSnapshot.from_state(state)
        gate_decision = self.gate.require(
            state=state,
            expected_stage=RunStage.HUMAN_REVIEW,
        )
        before_action = state.actions.require_action(action_id)
        if not before_action.requires_human_review():
            raise FoundationError("bounded action is not waiting for human review")

        decision = HumanReviewDecision.create(
            cycle=before_action.cycle,
            reviewer=reviewer,
            target_type=HumanReviewTargetType.BOUNDED_ACTION,
            target_id=before_action.action_id.value,
            target_digest=before_action.digest(),
            status=status,
            rationale=rationale,
        )
        after_action = self._apply_decision_to_action(
            action=before_action,
            decision=decision,
        )
        updated_state = self._record_decision_event(
            state=(
                state
                if after_action == before_action
                else state.replace_action(after_action)
            ),
            before_action=before_action,
            after_action=after_action,
            decision=decision,
        )
        receipt = HumanReviewSubmissionReceipt.create(
            before_state_digest=before_snapshot.state_digest,
            after_state_digest=updated_state.digest(),
            before_action_digest=before_action.digest(),
            after_action_digest=after_action.digest(),
            gate_decision_digest=gate_decision.digest(),
            human_decision_digest=decision.digest(),
            status=status,
            detail=self._receipt_detail(decision),
        )

        return HumanReviewSubmissionResult(
            state=updated_state,
            before_snapshot=before_snapshot,
            gate_decision=gate_decision,
            decision=decision,
            before_action=before_action,
            after_action=after_action,
            receipt=receipt,
        )

    def _apply_decision_to_action(
        self,
        *,
        action: BoundedActionRecord,
        decision: HumanReviewDecision,
    ) -> BoundedActionRecord:
        """Return the bounded action after applying the human decision."""
        if action.authority_decision_digest is None:
            raise FoundationError(
                "human-review actions require an authority decision digest"
            )

        if decision.approves_target():
            return BoundedActionRecord.create(
                action_id=action.action_id,
                cycle=action.cycle,
                proposed_by=action.proposed_by,
                description=action.description,
                requested_authority=action.requested_authority.value,
                proposal_action_digest=action.proposal_action_digest,
                status=ActionStatus.AUTHORIZED,
                tool_key=action.tool_key.value if action.tool_key is not None else None,
                requires_tool=action.requires_tool,
                requires_memory_write=action.requires_memory_write,
                requires_human_boundary=action.requires_human_boundary,
                authority_decision_digest=action.authority_decision_digest,
                execution_digest=action.execution_digest,
                boundary_note=f"human approved: {decision.rationale}",
            )

        if decision.rejects_target():
            return BoundedActionRecord.create(
                action_id=action.action_id,
                cycle=action.cycle,
                proposed_by=action.proposed_by,
                description=action.description,
                requested_authority=action.requested_authority.value,
                proposal_action_digest=action.proposal_action_digest,
                status=ActionStatus.DENIED,
                tool_key=action.tool_key.value if action.tool_key is not None else None,
                requires_tool=action.requires_tool,
                requires_memory_write=action.requires_memory_write,
                requires_human_boundary=action.requires_human_boundary,
                authority_decision_digest=action.authority_decision_digest,
                execution_digest=action.execution_digest,
                boundary_note=f"human rejected: {decision.rationale}",
            )

        return action

    def _record_decision_event(
        self,
        *,
        state: NinefoldRunState,
        before_action: BoundedActionRecord,
        after_action: BoundedActionRecord,
        decision: HumanReviewDecision,
    ) -> NinefoldRunState:
        """Record the human-boundary decision in the runtime transcript."""
        event = RuntimeEvent.create(
            sequence=state.next_event_sequence(),
            cycle=decision.cycle,
            event_type=RuntimeEventType.JURISDICTION_DECIDED,
            summary=f"Recorded human-boundary decision: {decision.status.value}.",
            payload={
                "human_decision_digest": decision.digest().value,
                "human_decision_algorithm": decision.digest().algorithm,
                "before_action_digest": before_action.digest().value,
                "after_action_digest": after_action.digest().value,
                "target_type": decision.target_type.value,
                "target_id": decision.target_id.value,
                "status": decision.status.value,
            },
        )
        return state.with_event(event)

    def _receipt_detail(self, decision: HumanReviewDecision) -> str:
        """Return a deterministic receipt detail string for a human decision."""
        if decision.approves_target():
            return "Human boundary approved the bounded action for execution planning."

        if decision.rejects_target():
            return "Human boundary rejected the bounded action and kept the run blocked."

        return "Human boundary deferred the bounded action and kept review open."
