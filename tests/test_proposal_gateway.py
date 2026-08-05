

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.proposal_gateway import (
    SallyProposalGateway,
    SallyProposalSubmissionReceipt,
)
from ix_sally.proposals import ProposalAction, SallyProposalPacket
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Submit proposal through gateway.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposal(
    *,
    requires_tool: bool = False,
    requires_human_boundary: bool = False,
    with_claim: bool = False,
) -> SallyProposalPacket:
    action = ProposalAction.create(
        description="Run the bounded verification step.",
        intended_authority="tool-execution",
        requires_tool=requires_tool,
        requires_memory_write=False,
        requires_human_boundary=requires_human_boundary,
    )
    claims = ()
    if with_claim:
        claims = (
            ClaimRecord.create(
                cycle=1,
                author=AgentRole.SALLY,
                statement="The verification step has been proposed, not proven.",
            ),
        )

    return SallyProposalPacket.create(
        cycle=1,
        goal_interpretation="Verify the next bounded step.",
        rationale="A proposal is required before action authority can be evaluated.",
        proposed_actions=(action,),
        claims=claims,
    )


def _proposed_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Existing proposed action.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "existing"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_proposal_gateway_accepts_proposal_only_at_proposal_intake_stage() -> None:
    state = _state()
    proposal = _proposal()

    result = SallyProposalGateway.create().submit(state=state, proposal=proposal)

    assert result.before_snapshot.stage is RunStage.PROPOSAL_INTAKE
    assert result.next_snapshot().stage is RunStage.AUTHORITY_PROCESSING
    assert result.state.proposed_action_count() == 1
    assert len(result.state.artifacts.artifacts) == 1
    assert result.receipt.changed_state() is True


def test_proposal_gateway_records_claims_and_actions_in_one_submission() -> None:
    state = _state()
    proposal = _proposal(with_claim=True)

    result = SallyProposalGateway.create().submit(state=state, proposal=proposal)

    assert result.intake_result.action_count() == 1
    assert result.intake_result.claim_count() == 1
    assert len(result.state.claims.claims) == 1
    assert result.receipt.action_count == 1
    assert result.receipt.claim_count == 1


def test_proposal_gateway_passes_tool_bindings_to_intake() -> None:
    state = _state()
    proposal = _proposal(requires_tool=True)
    action_id = proposal.proposed_actions[0].action_id.value

    result = SallyProposalGateway.create().submit(
        state=state,
        proposal=proposal,
        tool_bindings={action_id: "test-runner"},
    )

    action = result.state.actions.require_action(action_id)

    assert action.tool_key is not None
    assert action.tool_key.value == "test-runner"
    assert action.requires_tool is True


def test_proposal_gateway_rejects_missing_tool_binding() -> None:
    state = _state()
    proposal = _proposal(requires_tool=True)

    with pytest.raises(FoundationError, match="tool binding missing"):
        SallyProposalGateway.create().submit(state=state, proposal=proposal)


def test_proposal_gateway_blocks_submission_when_next_stage_is_not_intake() -> None:
    state = _state().with_action(_proposed_action())

    with pytest.raises(
        FoundationError,
        match="expected proposal_intake but observed authority_processing",
    ):
        SallyProposalGateway.create().submit(state=state, proposal=_proposal())


def test_proposal_submission_receipt_rejects_negative_counts() -> None:
    digest = DigestRecord.from_payload({"record": "receipt"})

    with pytest.raises(FoundationError, match="action_count must not be negative"):
        SallyProposalSubmissionReceipt.create(
            before_state_digest=digest,
            after_state_digest=digest,
            proposal_digest=digest,
            proposal_artifact_digest=digest,
            gate_decision_digest=digest,
            intake_digest=digest,
            action_count=-1,
            claim_count=0,
            requires_human_review=False,
            detail="Invalid receipt.",
        )


def test_proposal_submission_result_payload_and_digest_are_stable() -> None:
    state = _state()
    proposal = _proposal(with_claim=True)

    first = SallyProposalGateway.create().submit(state=state, proposal=proposal)
    second = SallyProposalGateway.create().submit(state=state, proposal=proposal)

    payload = first.to_payload()

    assert payload["before_stage"] == RunStage.PROPOSAL_INTAKE.value
    assert payload["next_stage"] == RunStage.AUTHORITY_PROCESSING.value
    assert payload["action_count"] == 1
    assert payload["claim_count"] == 1
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
