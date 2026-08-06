from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.foundation import FoundationError
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_gate import RunStageGate, StageGateDecision, StageGateStatus
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Gate run stages.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _authorized_action() -> BoundedActionRecord:
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed by contract.",
    )
    return action.with_authority_decision(decision)


def test_run_stage_gate_allows_observed_stage() -> None:
    gate = RunStageGate()
    state = _state()

    decision = gate.evaluate(state=state, expected_stage=RunStage.PROPOSAL_INTAKE)

    assert decision.status is StageGateStatus.ALLOWED
    assert decision.allows_entry() is True
    assert decision.blocks_entry() is False
    assert decision.observed_stage is RunStage.PROPOSAL_INTAKE


def test_run_stage_gate_blocks_mismatched_stage_without_mutating_state() -> None:
    gate = RunStageGate()
    state = _state()
    before_digest = state.digest()

    decision = gate.evaluate(state=state, expected_stage=RunStage.AUTHORITY_PROCESSING)

    assert decision.status is StageGateStatus.BLOCKED
    assert decision.allows_entry() is False
    assert decision.blocks_entry() is True
    assert decision.observed_stage is RunStage.PROPOSAL_INTAKE
    assert state.digest() == before_digest


def test_run_stage_gate_require_raises_with_expected_and_observed_stage() -> None:
    gate = RunStageGate()

    with pytest.raises(
        FoundationError,
        match="expected authority_processing but observed proposal_intake",
    ):
        gate.require(state=_state(), expected_stage=RunStage.AUTHORITY_PROCESSING)


def test_run_stage_gate_allows_authority_processing_when_actions_are_proposed() -> None:
    gate = RunStageGate()
    state = _state().with_action(_proposed_action())

    decision = gate.require(state=state, expected_stage=RunStage.AUTHORITY_PROCESSING)

    assert decision.status is StageGateStatus.ALLOWED
    assert decision.observed_stage is RunStage.AUTHORITY_PROCESSING


def test_run_stage_gate_allows_forge_dispatch_only_when_queue_is_ready() -> None:
    gate = RunStageGate()
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action)
    state = _state().with_action(action).with_execution_queue_item(item)

    decision = gate.require(state=state, expected_stage=RunStage.FORGE_DISPATCH)

    assert decision.status is StageGateStatus.ALLOWED
    assert decision.observed_stage is RunStage.FORGE_DISPATCH


def test_stage_gate_decision_from_snapshot_has_stable_payload_and_digest() -> None:
    snapshot = RunStageSnapshot.from_state(_state())

    first = StageGateDecision.from_snapshot(
        snapshot=snapshot,
        expected_stage=RunStage.PROPOSAL_INTAKE,
    )
    second = StageGateDecision.from_snapshot(
        snapshot=snapshot,
        expected_stage=RunStage.PROPOSAL_INTAKE,
    )

    assert first.to_payload()["expected_stage"] == RunStage.PROPOSAL_INTAKE.value
    assert first.to_payload()["observed_stage"] == RunStage.PROPOSAL_INTAKE.value
    assert first.to_payload()["allows_entry"] is True
    assert first.digest() == second.digest()
