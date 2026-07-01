from __future__ import annotations

import pytest

from ix_sally.actions import ActionStatus, BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_result_processing import ForgeResultProcessor
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Process Forge results.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _authorized_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def _forge_result(
    *,
    action: BoundedActionRecord,
    status: ForgeResultStatus = ForgeResultStatus.PASSED,
) -> ForgeResultRecord:
    item = ExecutionQueueItem.from_action(action).dispatched()

    if status is ForgeResultStatus.FAILED:
        return ForgeResultRecord.from_dispatched_item(
            item=item,
            action=action,
            status=status,
            summary="Forge execution failed.",
            observed_output="1 failed",
            failure_reason="Assertion failed.",
        )

    if status is ForgeResultStatus.BLOCKED:
        return ForgeResultRecord.from_dispatched_item(
            item=item,
            action=action,
            status=status,
            summary="Forge execution blocked.",
            boundary_note="Boundary blocked execution.",
        )

    return ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=status,
        summary="Forge execution passed.",
        observed_output="1 passed",
    )


def test_bounded_action_can_be_marked_blocked_by_execution_result() -> None:
    action = _authorized_action()
    execution_digest = DigestRecord.from_payload({"forge_result": "failed"})

    blocked = action.with_blocking_result(
        execution_digest=execution_digest,
        boundary_note="Assertion failed.",
    )

    assert blocked.status is ActionStatus.BLOCKED
    assert blocked.execution_digest == execution_digest
    assert blocked.boundary_note == "Assertion failed."
    assert blocked.blocks_progress() is True


def test_bounded_action_rejects_blocking_result_before_authorization() -> None:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )

    with pytest.raises(FoundationError, match="only authorized bounded actions"):
        action.with_blocking_result(
            execution_digest=DigestRecord.from_payload({"forge_result": "failed"}),
            boundary_note="Assertion failed.",
        )


def test_forge_result_processor_records_passed_result_and_marks_action_executed() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.PASSED)
    state = _state().with_action(action)
    processor = ForgeResultProcessor(StateRecorder())

    processed = processor.process_result(state=state, result=result)

    assert processed.original_action == action
    assert processed.forge_result == result
    assert processed.updated_action.status is ActionStatus.EXECUTED
    assert processed.updated_action.execution_digest == result.digest()
    assert (
        processed.state.actions.require_action(action.action_id.value).status
        is ActionStatus.EXECUTED
    )
    assert processed.state.executed_action_count() == 1
    assert processed.state.passed_forge_result_count() == 1
    assert processed.state.requires_human_review() is False


def test_forge_result_processor_records_failed_result_and_blocks_action() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.FAILED)
    state = _state().with_action(action)
    processor = ForgeResultProcessor(StateRecorder())

    processed = processor.process_result(state=state, result=result)

    assert processed.updated_action.status is ActionStatus.BLOCKED
    assert processed.updated_action.boundary_note == "Assertion failed."
    assert processed.state.blocked_action_count() == 1
    assert processed.state.failed_forge_result_count() == 1
    assert processed.state.requires_human_review() is True


def test_forge_result_processor_records_blocked_result_and_blocks_action() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.BLOCKED)
    state = _state().with_action(action)
    processor = ForgeResultProcessor(StateRecorder())

    processed = processor.process_result(state=state, result=result)

    assert processed.updated_action.status is ActionStatus.BLOCKED
    assert processed.updated_action.boundary_note == "Boundary blocked execution."
    assert processed.state.blocked_action_count() == 1
    assert processed.state.blocked_forge_result_count() == 1
    assert processed.state.requires_human_review() is True


def test_forge_result_processor_records_expected_event_sequence() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.PASSED)
    state = _state().with_action(action)
    processor = ForgeResultProcessor(StateRecorder())

    processed = processor.process_result(state=state, result=result)

    assert [event.event_type for event in processed.state.transcript.events] == [
        RuntimeEventType.CHAMBER_OPENED,
        RuntimeEventType.AGENT_ARTIFACT_RECORDED,
        RuntimeEventType.JURISDICTION_DECIDED,
    ]
    assert processed.state.transcript.events[-2].payload["reference_type"] == "forge-result"
    assert processed.state.transcript.events[-1].payload["reference_type"] == "bounded-action"


def test_forge_result_processor_rejects_unknown_action() -> None:
    action = _authorized_action()
    result = _forge_result(action=action)
    processor = ForgeResultProcessor(StateRecorder())

    with pytest.raises(FoundationError, match="unknown bounded action id"):
        processor.process_result(state=_state(), result=result)


def test_forge_result_processor_rejects_stale_action_digest() -> None:
    action = _authorized_action()
    stale_result = _forge_result(action=action)
    changed_action = action.with_execution_digest(DigestRecord.from_payload({"other": "result"}))
    state = _state().with_action(changed_action)
    processor = ForgeResultProcessor(StateRecorder())

    with pytest.raises(FoundationError, match="action digest must match"):
        processor.process_result(state=state, result=stale_result)


def test_forge_result_processor_processes_result_batch() -> None:
    first_action = _authorized_action(description="Run passing tests.")
    second_action = _authorized_action(description="Run failing tests.")
    first_result = _forge_result(action=first_action, status=ForgeResultStatus.PASSED)
    second_result = _forge_result(action=second_action, status=ForgeResultStatus.FAILED)
    state = _state().with_action(first_action).with_action(second_action)
    processor = ForgeResultProcessor(StateRecorder())

    batch = processor.process_results(
        state=state,
        results=(first_result, second_result),
    )

    assert batch.processed_count() == 2
    assert batch.passed_count() == 1
    assert batch.human_review_count() == 1
    assert batch.state.executed_action_count() == 1
    assert batch.state.blocked_action_count() == 1
    assert batch.state.requires_human_review() is True


def test_forge_result_processing_digest_changes_when_result_changes() -> None:
    first_action = _authorized_action(description="Run passing tests.")
    second_action = _authorized_action(description="Run failing tests.")
    first_result = _forge_result(action=first_action, status=ForgeResultStatus.PASSED)
    second_result = _forge_result(action=second_action, status=ForgeResultStatus.FAILED)
    processor = ForgeResultProcessor(StateRecorder())

    first_processed = processor.process_result(
        state=_state().with_action(first_action),
        result=first_result,
    )
    second_processed = processor.process_result(
        state=_state().with_action(second_action),
        result=second_result,
    )

    assert first_processed.digest().value != second_processed.digest().value
