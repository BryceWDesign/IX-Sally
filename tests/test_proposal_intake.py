from __future__ import annotations

import pytest

from ix_sally.actions import ActionStatus
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.events import RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.proposal_intake import SallyProposalIntake
from ix_sally.proposals import ProposalAction, SallyProposalPacket
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state(*, max_cycles: int = 2) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Intake Sally proposal.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=max_cycles,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def test_sally_proposal_intake_records_artifact_claims_actions_and_events() -> None:
    state = _state()
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="This proposal requires later evidence.",
    )
    inspect_action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
        requires_human_boundary=False,
    )
    tool_action = ProposalAction.create(
        description="Run bounded tests.",
        intended_authority="tool-execution",
        requires_tool=True,
        requires_human_boundary=False,
    )
    proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect and test bounded state.",
        rationale="The chamber needs recorded proposal intake.",
        proposed_actions=(inspect_action, tool_action),
        claims=(claim,),
    )
    intake = SallyProposalIntake(StateRecorder())

    result = intake.record(
        state=state,
        proposal=proposal,
        tool_bindings={tool_action.action_id.value: "test-runner"},
    )

    assert result.proposal_artifact.role is AgentRole.SALLY
    assert result.proposal_artifact.kind is AgentArtifactKind.PROPOSAL
    assert result.action_count() == 2
    assert result.claim_count() == 1
    assert len(result.state.artifacts.artifacts) == 1
    assert len(result.state.claims.claims) == 1
    assert len(result.state.actions.actions) == 2
    assert result.state.actions.actions[0].status is ActionStatus.PROPOSED
    assert result.state.actions.actions[1].tool_key is not None
    assert result.state.actions.actions[1].tool_key.value == "test-runner"


def test_sally_proposal_intake_records_expected_event_sequence() -> None:
    state = _state()
    action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
        requires_human_boundary=False,
    )
    proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect bounded state.",
        rationale="The chamber needs recorded proposal intake.",
        proposed_actions=(action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    result = intake.record(state=state, proposal=proposal)

    assert [event.event_type for event in result.state.transcript.events] == [
        RuntimeEventType.CHAMBER_OPENED,
        RuntimeEventType.AGENT_ARTIFACT_RECORDED,
        RuntimeEventType.JURISDICTION_DECIDED,
    ]
    assert result.state.transcript.events[-1].payload["reference_type"] == "bounded-action"


def test_sally_proposal_intake_requires_tool_binding_for_tool_action() -> None:
    state = _state()
    tool_action = ProposalAction.create(
        description="Run bounded tests.",
        intended_authority="tool-execution",
        requires_tool=True,
        requires_human_boundary=False,
    )
    proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Test bounded state.",
        rationale="The chamber needs a tool binding before action intake.",
        proposed_actions=(tool_action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    with pytest.raises(FoundationError, match="tool binding missing"):
        intake.record(state=state, proposal=proposal)


def test_sally_proposal_intake_rejects_cycle_zero() -> None:
    state = _state()
    action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
    )
    proposal = SallyProposalPacket.create(
        cycle=0,
        goal_interpretation="Invalid intake cycle.",
        rationale="Cycle zero is the chamber opening cycle.",
        proposed_actions=(action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    with pytest.raises(FoundationError, match="requires cycle at least 1"):
        intake.record(state=state, proposal=proposal)


def test_sally_proposal_intake_rejects_stopped_chamber() -> None:
    state = _state(max_cycles=0)
    action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
    )
    proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect stopped chamber.",
        rationale="This should be rejected.",
        proposed_actions=(action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    with pytest.raises(FoundationError, match="chamber is stopped"):
        intake.record(state=state, proposal=proposal)


def test_sally_proposal_intake_rejects_cycle_beyond_contract_limit() -> None:
    state = _state(max_cycles=1)
    action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
    )
    proposal = SallyProposalPacket.create(
        cycle=2,
        goal_interpretation="Inspect beyond cycle limit.",
        rationale="This should be rejected.",
        proposed_actions=(action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    with pytest.raises(FoundationError, match="cycle exceeds autonomy contract max_cycles"):
        intake.record(state=state, proposal=proposal)


def test_sally_proposal_intake_result_digest_changes_when_state_changes() -> None:
    state = _state()
    first_action = ProposalAction.create(
        description="Inspect chamber state.",
        intended_authority="observation",
    )
    second_action = ProposalAction.create(
        description="Inspect doctrine state.",
        intended_authority="observation",
    )
    first_proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect bounded state.",
        rationale="The chamber needs recorded proposal intake.",
        proposed_actions=(first_action,),
    )
    second_proposal = SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Inspect bounded state.",
        rationale="The chamber needs recorded proposal intake.",
        proposed_actions=(second_action,),
    )
    intake = SallyProposalIntake(StateRecorder())

    first = intake.record(state=state, proposal=first_proposal)
    second = intake.record(state=state, proposal=second_proposal)

    assert first.digest().value != second.digest().value
