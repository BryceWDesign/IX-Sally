"""Sally proposal intake flow for claims, artifacts, and bounded actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.proposals import ProposalAction, SallyProposalPacket
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class SallyProposalIntakeResult:
    """Result of recording a Sally proposal into the run state."""

    state: NinefoldRunState
    proposal_artifact: AgentArtifact
    bounded_actions: tuple[BoundedActionRecord, ...]

    def action_count(self) -> int:
        """Return the number of bounded actions produced by the proposal."""
        return len(self.bounded_actions)

    def claim_count(self) -> int:
        """Return the number of claims carried by the proposal."""
        return len(self.proposal_artifact.data.get("claims", []))

    def requires_human_review(self) -> bool:
        """Return whether any bounded action requires human boundary review."""
        return any(action.requires_human_boundary for action in self.bounded_actions)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible proposal intake result."""
        actions_payload: JsonArray = []
        for action in self.bounded_actions:
            actions_payload.append(action.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "proposal_artifact_digest": self.proposal_artifact.digest().value,
            "action_count": self.action_count(),
            "claim_count": self.claim_count(),
            "requires_human_review": self.requires_human_review(),
            "bounded_actions": actions_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this proposal intake result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class SallyProposalIntake:
    """Records a Sally proposal packet into IX-Sally run state."""

    recorder: StateRecorder

    def record(
        self,
        *,
        state: NinefoldRunState,
        proposal: SallyProposalPacket,
        tool_bindings: Mapping[str, str] | None = None,
    ) -> SallyProposalIntakeResult:
        """Record a proposal artifact, its claims, and its bounded action records."""
        self._require_cycle_can_accept(state=state, proposal=proposal)
        bindings = tool_bindings or {}

        proposal_artifact = proposal.to_artifact()
        updated = self.recorder.record_artifact(state, proposal_artifact)

        for claim in proposal.claims:
            updated = self.recorder.record_claim(updated, claim)

        bounded_actions: list[BoundedActionRecord] = []
        for proposal_action in proposal.proposed_actions:
            bounded_action = self._create_bounded_action(
                cycle=proposal.cycle,
                proposal_action=proposal_action,
                tool_bindings=bindings,
            )
            bounded_actions.append(bounded_action)
            updated = self.recorder.record_action(updated, bounded_action)

        return SallyProposalIntakeResult(
            state=updated,
            proposal_artifact=proposal_artifact,
            bounded_actions=tuple(bounded_actions),
        )

    def _require_cycle_can_accept(
        self,
        *,
        state: NinefoldRunState,
        proposal: SallyProposalPacket,
    ) -> None:
        """Reject a proposal that is outside the chamber cycle bounds."""
        if proposal.cycle < 1:
            raise FoundationError("Sally proposal intake requires cycle at least 1")

        stop_condition = state.runtime_kit.chamber.stop_for_cycle(state.completed_cycles())
        if stop_condition.should_stop:
            raise FoundationError("Sally proposal intake rejected because chamber is stopped")

        if proposal.cycle > state.runtime_kit.chamber.contract.max_cycles:
            raise FoundationError("Sally proposal cycle exceeds autonomy contract max_cycles")

    def _create_bounded_action(
        self,
        *,
        cycle: int,
        proposal_action: ProposalAction,
        tool_bindings: Mapping[str, str],
    ) -> BoundedActionRecord:
        """Create a bounded action from a proposal action and optional tool bindings."""
        tool_key = None
        if proposal_action.requires_tool:
            tool_key = tool_bindings.get(proposal_action.action_id.value)
            if tool_key is None:
                raise FoundationError(
                    f"tool binding missing for proposal action: {proposal_action.action_id.value}"
                )

        return BoundedActionRecord.from_proposal_action(
            cycle=cycle,
            proposed_by=AgentRole.SALLY,
            proposal_action=proposal_action,
            tool_key=tool_key,
        )
