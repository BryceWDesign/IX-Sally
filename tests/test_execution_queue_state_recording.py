from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.execution_queue import ExecutionQueue, ExecutionQueueItem, ExecutionQueueStatus
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record execution queue state.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _authorized_action() -> BoundedActionRecord:
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
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def test_run_state_starts_with_empty_execution_queue() -> None:
    state = _state()

    assert len(state.execution_queue.items) == 0
    assert state.queued_execution_count() == 0
    assert state.dispatched_execution_count() == 0
    assert state.skipped_execution_count() == 0
    assert state.to_payload()["execution_queue_count"] == 0


def test_run_state_appends_execution_queue_item_immutably() -> None:
    state = _state()
    item = ExecutionQueueItem.from_action(_authorized_action())

    updated = state.with_execution_queue_item(item)

    assert len(state.execution_queue.items) == 0
    assert len(updated.execution_queue.items) == 1
    assert updated.queued_execution_count() == 1
    assert updated.to_payload()["queued_execution_count"] == 1


def test_run_state_replaces_execution_queue_item_immutably() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())
    state = _state().with_execution_queue_item(item)

    updated = state.replace_execution_queue_item(item.dispatched())

    assert state.queued_execution_count() == 1
    assert updated.queued_execution_count() == 0
    assert updated.dispatched_execution_count() == 1


def test_run_state_replaces_complete_execution_queue() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())
    queue = ExecutionQueue.create((item,))

    updated = _state().with_execution_queue(queue)

    assert updated.execution_queue == queue
    assert updated.queued_execution_count() == 1
    assert updated.to_payload()["execution_queue_digest"] == queue.digest().value


def test_state_recorder_records_execution_queue_item_and_event() -> None:
    recorder = StateRecorder()
    state = _state()
    item = ExecutionQueueItem.from_action(_authorized_action())

    updated = recorder.record_execution_queue_item(state, item)

    assert len(updated.execution_queue.items) == 1
    assert len(updated.transcript.events) == 2

    event = updated.transcript.events[-1]

    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Recorded execution queue item for ix-forge: queued."
    assert event.payload["reference_type"] == "execution-queue-item"
    assert event.payload["reference_digest"] == item.digest().value


def test_state_recorder_replaces_execution_queue_item_and_event() -> None:
    recorder = StateRecorder()
    item = ExecutionQueueItem.from_action(_authorized_action())
    state = _state().with_execution_queue_item(item)

    updated = recorder.replace_execution_queue_item(state, item.dispatched())

    assert updated.queued_execution_count() == 0
    assert updated.dispatched_execution_count() == 1

    event = updated.transcript.events[-1]

    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Updated execution queue item for ix-forge: dispatched."
    assert event.payload["reference_type"] == "execution-queue-item"


def test_execution_queue_state_digest_changes_when_queue_item_changes() -> None:
    state = _state()
    item = ExecutionQueueItem.from_action(_authorized_action())

    queued = state.with_execution_queue_item(item)
    dispatched = queued.replace_execution_queue_item(item.dispatched())

    assert state.digest().value != queued.digest().value
    assert queued.digest().value != dispatched.digest().value


def test_execution_queue_skipped_count_is_reported() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())
    skipped = item.skipped(reason="Execution disabled by boundary test.")
    state = _state().with_execution_queue_item(skipped)

    assert state.skipped_execution_count() == 1
    assert state.to_payload()["skipped_execution_count"] == 1
    assert state.execution_queue.items[0].status is ExecutionQueueStatus.SKIPPED
