

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import FoundationError
from ix_sally.orchestration import StageAdvanceKind, StageOrchestrator
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Advance one gated stage.",
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


def test_stage_orchestrator_waits_for_proposal_on_fresh_state() -> None:
    state = _state()
    result = StageOrchestrator.create().advance_once(state=state)

    assert result.kind is StageAdvanceKind.WAITING_FOR_PROPOSAL
    assert result.before_snapshot.stage is RunStage.PROPOSAL_INTAKE
    assert result.changed_state() is False
    assert result.state == state


def test_stage_orchestrator_processes_authority_stage_once() -> None:
    state = _state().with_action(_proposed_action())
    result = StageOrchestrator.create().advance_once(state=state)

    assert result.kind is StageAdvanceKind.AUTHORITY_PROCESSED
    assert result.before_snapshot.stage is RunStage.AUTHORITY_PROCESSING
    assert result.changed_state() is True
    assert result.state.executable_action_count() == 1
    assert len(result.state.authority_decisions.decisions) == 1


def test_stage_orchestrator_plans_authorized_execution_once() -> None:
    orchestrator = StageOrchestrator.create()
    authority_result = orchestrator.advance_once(state=_state().with_action(_proposed_action()))

    planning_result = orchestrator.advance_once(state=authority_result.state)

    assert planning_result.kind is StageAdvanceKind.EXECUTION_PLANNED
    assert planning_result.before_snapshot.stage is RunStage.EXECUTION_PLANNING
    assert planning_result.state.queued_execution_count() == 1


def test_stage_orchestrator_dispatches_queued_execution_once() -> None:
    orchestrator = StageOrchestrator.create()
    authority_result = orchestrator.advance_once(state=_state().with_action(_proposed_action()))
    planning_result = orchestrator.advance_once(state=authority_result.state)

    dispatch_result = orchestrator.advance_once(state=planning_result.state)

    assert dispatch_result.kind is StageAdvanceKind.EXECUTION_DISPATCHED
    assert dispatch_result.before_snapshot.stage is RunStage.FORGE_DISPATCH
    assert dispatch_result.state.dispatched_execution_count() == 1


def test_stage_orchestrator_waits_for_forge_results_without_mutation() -> None:
    orchestrator = StageOrchestrator.create()
    authority_result = orchestrator.advance_once(state=_state().with_action(_proposed_action()))
    planning_result = orchestrator.advance_once(state=authority_result.state)
    dispatch_result = orchestrator.advance_once(state=planning_result.state)

    waiting_result = orchestrator.advance_once(state=dispatch_result.state)

    assert waiting_result.kind is StageAdvanceKind.WAITING_FOR_FORGE_RESULTS
    assert waiting_result.before_snapshot.stage is RunStage.FORGE_RESULT_PROCESSING
    assert waiting_result.changed_state() is False


def test_stage_orchestrator_processes_supplied_forge_results() -> None:
    orchestrator = StageOrchestrator.create()
    authority_result = orchestrator.advance_once(state=_state().with_action(_proposed_action()))
    planning_result = orchestrator.advance_once(state=authority_result.state)
    dispatch_result = orchestrator.advance_once(state=planning_result.state)
    item = dispatch_result.state.execution_queue.dispatched_items()[0]
    action = dispatch_result.state.actions.require_action(item.action_id.value)
    forge_result = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Tests passed inside Forge.",
        observed_output="1 passed",
    )

    processed_result = orchestrator.advance_once(
        state=dispatch_result.state,
        forge_results=(forge_result,),
    )

    assert processed_result.kind is StageAdvanceKind.FORGE_RESULTS_PROCESSED
    assert processed_result.state.executed_action_count() == 1
    assert processed_result.state.passed_forge_result_count() == 1


def test_stage_orchestrator_rejects_off_stage_forge_results() -> None:
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed for test.",
    )
    authorized = action.with_authority_decision(decision)
    queued = ExecutionQueueItem.from_action(authorized).dispatched()
    forged = ForgeResultRecord.from_dispatched_item(
        item=queued,
        action=authorized,
        status=ForgeResultStatus.PASSED,
        summary="Tests passed.",
    )

    with pytest.raises(FoundationError, match="only be processed at the Forge result stage"):
        StageOrchestrator.create().advance_once(state=_state(), forge_results=(forged,))


def test_stage_advance_result_payload_and_digest_are_stable() -> None:
    state = _state()
    first = StageOrchestrator.create().advance_once(state=state)
    second = StageOrchestrator.create().advance_once(state=state)

    assert first.to_payload()["kind"] == StageAdvanceKind.WAITING_FOR_PROPOSAL.value
    assert first.to_payload()["changed_state"] is False
    assert first.digest() == second.digest()
