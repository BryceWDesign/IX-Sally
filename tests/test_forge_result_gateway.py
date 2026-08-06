from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.forge_result_gateway import (
    ForgeResultGateway,
    ForgeResultSubmissionReceipt,
)
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import FoundationError
from ix_sally.orchestration_loop import StageLoopRunner
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Submit Forge results through gateway.",
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
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "run tests"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _waiting_state() -> NinefoldRunState:
    loop_result = StageLoopRunner.create().run_until_stop(
        state=_state().with_action(_proposed_action()),
        max_steps=10,
    )
    assert loop_result.final_snapshot.stage is RunStage.FORGE_RESULT_PROCESSING
    return loop_result.state


def _forge_result(
    state: NinefoldRunState,
    *,
    status: ForgeResultStatus = ForgeResultStatus.PASSED,
) -> ForgeResultRecord:
    item = state.execution_queue.dispatched_items()[0]
    action = state.actions.require_action(item.action_id.value)

    if status is ForgeResultStatus.FAILED:
        return ForgeResultRecord.from_dispatched_item(
            item=item,
            action=action,
            status=status,
            summary="Forge execution failed.",
            failure_reason="The bounded check failed.",
        )

    return ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=status,
        summary="Forge execution passed.",
        observed_output="1 passed",
    )


def test_forge_result_gateway_accepts_results_only_at_forge_result_stage() -> None:
    state = _waiting_state()
    forge_result = _forge_result(state)

    result = ForgeResultGateway.create().submit(
        state=state,
        results=(forge_result,),
    )

    assert result.before_snapshot.stage is RunStage.FORGE_RESULT_PROCESSING
    assert result.next_snapshot().stage is RunStage.PROPOSAL_INTAKE
    assert result.state.executed_action_count() == 1
    assert result.state.passed_forge_result_count() == 1
    assert result.receipt.changed_state() is True


def test_forge_result_gateway_rejects_empty_submission() -> None:
    with pytest.raises(FoundationError, match="requires at least one result"):
        ForgeResultGateway.create().submit(state=_waiting_state(), results=())


def test_forge_result_gateway_blocks_submission_when_stage_is_not_ready() -> None:
    with pytest.raises(
        FoundationError,
        match="expected forge_result_processing but observed proposal_intake",
    ):
        ForgeResultGateway.create().submit(
            state=_state(),
            results=(_forge_result(_waiting_state()),),
        )


def test_forge_result_gateway_rejects_duplicate_result_for_same_queue_item() -> None:
    state = _waiting_state()
    forge_result = _forge_result(state)

    with pytest.raises(FoundationError, match="duplicate Forge result"):
        ForgeResultGateway.create().submit(
            state=state,
            results=(forge_result, forge_result),
        )


def test_forge_result_gateway_rejects_non_pending_queue_result() -> None:
    waiting = _waiting_state()
    forge_result = _forge_result(waiting)
    processed = ForgeResultGateway.create().submit(
        state=waiting,
        results=(forge_result,),
    )

    with pytest.raises(
        FoundationError,
        match="expected forge_result_processing but observed proposal_intake",
    ):
        ForgeResultGateway.create().submit(
            state=processed.state,
            results=(forge_result,),
        )


def test_forge_result_gateway_failed_result_routes_to_human_review() -> None:
    state = _waiting_state()
    forge_result = _forge_result(state, status=ForgeResultStatus.FAILED)

    result = ForgeResultGateway.create().submit(
        state=state,
        results=(forge_result,),
    )

    assert result.next_snapshot().stage is RunStage.HUMAN_REVIEW
    assert result.state.blocked_action_count() == 1
    assert result.state.failed_forge_result_count() == 1
    assert result.receipt.requires_human_review() is True


def test_forge_result_submission_receipt_rejects_invalid_counts() -> None:
    digest = DigestRecord.from_payload({"record": "forge-result-submission"})

    with pytest.raises(FoundationError, match="result_count must be positive"):
        ForgeResultSubmissionReceipt.create(
            before_state_digest=digest,
            after_state_digest=digest,
            gate_decision_digest=digest,
            processing_digest=digest,
            result_count=0,
            passed_count=0,
            human_review_count=0,
            detail="Invalid receipt.",
        )


def test_forge_result_submission_result_payload_and_digest_are_stable() -> None:
    state = _waiting_state()
    forge_result = _forge_result(state)

    first = ForgeResultGateway.create().submit(state=state, results=(forge_result,))
    second = ForgeResultGateway.create().submit(state=state, results=(forge_result,))

    payload = first.to_payload()

    assert payload["before_stage"] == RunStage.FORGE_RESULT_PROCESSING.value
    assert payload["next_stage"] == RunStage.PROPOSAL_INTAKE.value
    assert payload["result_count"] == 1
    assert payload["passed_count"] == 1
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
