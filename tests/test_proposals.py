

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.claims import ClaimRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.proposals import ProposalAction, SallyProposalPacket


def test_proposal_action_normalizes_description_and_authority() -> None:
    action = ProposalAction.create(
        description="  Run bounded artifact inspection. ",
        intended_authority=" Tool Execution ",
        requires_tool=True,
    )

    assert action.action_id.value == "tool-execution-run-bounded-artifact-inspection"
    assert action.description == "Run bounded artifact inspection."
    assert action.intended_authority.value == "tool-execution"
    assert action.requires_tool is True
    assert action.requires_memory_write is False
    assert action.requires_human_boundary is True


def test_proposal_action_payload_is_stable() -> None:
    action = ProposalAction.create(
        action_id=CanonicalKey.from_text("action-one", field_name="action_id"),
        description="Inspect run state.",
        intended_authority="observation",
        requires_tool=False,
        requires_memory_write=False,
        requires_human_boundary=True,
    )

    assert action.to_payload() == {
        "action_id": "action-one",
        "description": "Inspect run state.",
        "intended_authority": "observation",
        "requires_tool": False,
        "requires_memory_write": False,
        "requires_human_boundary": True,
    }


def test_sally_proposal_packet_requires_non_negative_cycle() -> None:
    action = ProposalAction.create(
        description="Inspect run state.",
        intended_authority="observation",
    )

    with pytest.raises(FoundationError, match="proposal cycle must not be negative"):
        SallyProposalPacket.create(
            cycle=-1,
            goal_interpretation="Invalid cycle.",
            rationale="Invalid.",
            proposed_actions=(action,),
        )


def test_sally_proposal_packet_requires_at_least_one_action() -> None:
    with pytest.raises(FoundationError, match="proposal requires at least one bounded action"):
        SallyProposalPacket.create(
            cycle=1,
            goal_interpretation="No action.",
            rationale="No action exists.",
            proposed_actions=(),
        )


def test_sally_proposal_packet_rejects_claims_from_other_roles() -> None:
    action = ProposalAction.create(
        description="Inspect run state.",
        intended_authority="observation",
    )
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.BUTCH,
        statement="This claim should not be inside Sally proposal.",
    )

    with pytest.raises(FoundationError, match="claims must be authored by ix-sally"):
        SallyProposalPacket.create(
            cycle=1,
            goal_interpretation="Inspect safely.",
            rationale="Need bounded proposal.",
            proposed_actions=(action,),
            claims=(claim,),
        )


def test_sally_proposal_packet_rejects_claim_cycle_mismatch() -> None:
    action = ProposalAction.create(
        description="Inspect run state.",
        intended_authority="observation",
    )
    claim = ClaimRecord.create(
        cycle=2,
        author=AgentRole.SALLY,
        statement="This claim has the wrong cycle.",
    )

    with pytest.raises(FoundationError, match="claims must match proposal cycle"):
        SallyProposalPacket.create(
            cycle=1,
            goal_interpretation="Inspect safely.",
            rationale="Need bounded proposal.",
            proposed_actions=(action,),
            claims=(claim,),
        )


def test_sally_proposal_packet_tracks_tool_and_memory_requirements() -> None:
    tool_action = ProposalAction.create(
        description="Run a sandbox command.",
        intended_authority="tool-execution",
        requires_tool=True,
    )
    memory_action = ProposalAction.create(
        description="Stage a memory candidate.",
        intended_authority="memory-storage",
        requires_memory_write=True,
    )
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="The proposal requires later evidence.",
    )
    packet = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Create bounded chamber output.",
        rationale="The action must be proposed before any authority is exercised.",
        proposed_actions=(tool_action, memory_action),
        claims=(claim,),
    )

    assert packet.proposal_id.value == "ix-sally-1-create-bounded-chamber-output"
    assert packet.requires_tool_execution() is True
    assert packet.requires_memory_write() is True
    assert packet.claims == (claim,)


def test_sally_proposal_packet_converts_to_artifact() -> None:
    action = ProposalAction.create(
        description="Inspect run state.",
        intended_authority="observation",
    )
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="This is a proposed interpretation, not evidence.",
    )
    packet = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect safely.",
        rationale="The chamber needs a bounded first move.",
        proposed_actions=(action,),
        claims=(claim,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.SALLY
    assert artifact.kind is AgentArtifactKind.PROPOSAL
    assert artifact.summary == "IX-Sally proposed 1 bounded action(s)."
    assert artifact.referenced_digests == (claim.digest(),)
    assert artifact.data == packet.to_payload()


def test_sally_proposal_packet_digest_changes_when_action_changes() -> None:
    first_action = ProposalAction.create(
        description="Inspect run state.",
        intended_authority="observation",
    )
    second_action = ProposalAction.create(
        description="Inspect doctrine state.",
        intended_authority="observation",
    )
    first = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect safely.",
        rationale="The chamber needs a bounded first move.",
        proposed_actions=(first_action,),
    )
    second = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect safely.",
        rationale="The chamber needs a bounded first move.",
        proposed_actions=(second_action,),
    )

    assert first.digest().value != second.digest().value
