"""Bridge cognitive plan proposals into the existing IX-Sally control plane."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimRecord, ClaimStatus
from ix_sally.cognition.executive import ExecutiveDecision
from ix_sally.cognition.planning import ActionSpec
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.proposals import ProposalAction, SallyProposalPacket


@dataclass(frozen=True, slots=True)
class CognitiveProposalBridgeReceipt:
    """Receipt linking one executive decision to a control-plane proposal packet."""

    bridge_id: CanonicalKey
    executive_decision_digest: DigestRecord
    proposal_digest: DigestRecord
    action_links: tuple[tuple[CanonicalKey, CanonicalKey], ...]

    def to_payload(self) -> JsonObject:
        """Return a canonical bridge receipt."""
        links: JsonArray = [
            {
                "cognitive_action_id": cognitive.value,
                "proposal_action_id": proposal.value,
            }
            for cognitive, proposal in self.action_links
        ]
        return {
            "bridge_id": self.bridge_id.value,
            "executive_decision_digest": {
                "algorithm": self.executive_decision_digest.algorithm,
                "value": self.executive_decision_digest.value,
            },
            "proposal_digest": {
                "algorithm": self.proposal_digest.algorithm,
                "value": self.proposal_digest.value,
            },
            "action_links": links,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic bridge receipt identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CognitiveProposalBridgeResult:
    """Control-plane proposal and its explicit cognitive provenance receipt."""

    proposal: SallyProposalPacket
    receipt: CognitiveProposalBridgeReceipt

    def to_payload(self) -> JsonObject:
        """Return a canonical bridge result."""
        return {
            "proposal": self.proposal.to_payload(),
            "receipt": self.receipt.to_payload(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic bridge-result identity."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class CognitiveProposalBridge:
    """Convert approved-for-governance cognition into proposals, never execution."""

    intended_authority: str = "cognitive-plan-execution"

    def bridge(
        self,
        *,
        decision: ExecutiveDecision,
        cycle: int,
    ) -> CognitiveProposalBridgeResult:
        """Convert a plan-ready decision into the existing proposal schema."""
        if cycle < 0:
            raise FoundationError("proposal bridge cycle must not be negative")
        selected_goal = decision.selected_goal
        plan = decision.plan
        if not decision.may_enter_governance() or plan is None or selected_goal is None:
            raise FoundationError(
                "only plan-ready executive decisions may enter proposal governance"
            )
        proposal_actions = tuple(self._proposal_action(action) for action in plan.actions)
        claim_status = (
            ClaimStatus.PARTIAL
            if decision.status.value == "requires_human"
            else ClaimStatus.SUPPORTED
        )
        support = (
            decision.evidence_digests
            if claim_status is ClaimStatus.SUPPORTED
            else (decision.digest(),)
        )
        claim = ClaimRecord.create(
            cycle=cycle,
            author=AgentRole.SALLY,
            statement=(
                "The bounded planner found a declarative action sequence for the "
                f"selected goal {selected_goal.goal_id.value}."
            ),
            status=claim_status,
            support_digests=support,
        )
        proposal = SallyProposalPacket.create(
            cycle=cycle,
            goal_interpretation=selected_goal.description,
            rationale=decision.rationale,
            proposed_actions=proposal_actions,
            claims=(claim,),
        )
        decision_digest = decision.digest()
        links = tuple(
            (action.action_id, proposal_action.action_id)
            for action, proposal_action in zip(
                plan.actions,
                proposal_actions,
                strict=True,
            )
        )
        bridge_seed = DigestRecord.from_payload(
            {
                "decision": decision_digest.value,
                "proposal": proposal.digest().value,
            }
        )
        receipt = CognitiveProposalBridgeReceipt(
            bridge_id=CanonicalKey.from_text(
                f"cognitive-proposal-bridge-{bridge_seed.value[:24]}",
                field_name="bridge_id",
            ),
            executive_decision_digest=decision_digest,
            proposal_digest=proposal.digest(),
            action_links=links,
        )
        return CognitiveProposalBridgeResult(proposal=proposal, receipt=receipt)

    def _proposal_action(self, action: ActionSpec) -> ProposalAction:
        """Convert one declarative action while preserving authority boundaries."""
        return ProposalAction.create(
            action_id=action.action_id,
            description=action.description,
            intended_authority=self.intended_authority,
            requires_tool=False,
            requires_memory_write=False,
            requires_human_boundary=action.authority_required,
        )
