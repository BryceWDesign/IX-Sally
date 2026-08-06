from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.execution_dispatch import ExecutionDispatcher
from ix_sally.execution_queue import ExecutionQueueItem, ExecutionQueueStatus
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Dispatch queued Forge items.",
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


def _queue_item(*, description: str = "Run tests.") -> ExecutionQueueItem:
    return ExecutionQueueItem.from_action(_authorized_action(description=description))


def test_execution_dispatcher_dispatches_one_queued_item() -> None:
    item = _queue_item()
    state = _state().with_execution_queue_item(item)
    dispatcher = ExecutionDispatcher(StateRecorder())

    result = dispatcher.dispatch_item(state=state, item=item)

    assert result.original_item == item
    assert result.dispatched_item.status is ExecutionQueueStatus.DISPATCHED
    assert result.state.queued_execution_count() == 0
    assert result.state.dispatched_execution_count() == 1
    assert result.state.execution_queue.items[0] == result.dispatched_item


def test_execution_dispatcher_records_dispatch_event() -> None:
    item = _queue_item()
    state = _state().with_execution_queue_item(item)
    dispatcher = ExecutionDispatcher(StateRecorder())

    result = dispatcher.dispatch_item(state=state, item=item)

    assert len(result.state.transcript.events) == 2

    event = result.state.transcript.events[-1]

    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Updated execution queue item for ix-forge: dispatched."
    assert event.payload["reference_type"] == "execution-queue-item"
    assert event.payload["reference_digest"] == result.dispatched_item.digest().value


def test_execution_dispatcher_rejects_unknown_queue_item() -> None:
    item = _queue_item()
    dispatcher = ExecutionDispatcher(StateRecorder())

    with pytest.raises(FoundationError, match="unknown execution queue item id"):
        dispatcher.dispatch_item(state=_state(), item=item)


def test_execution_dispatcher_rejects_mismatched_queue_item() -> None:
    original = _queue_item(description="Run tests.")
    changed = original.skipped(reason="Skipped elsewhere.")
    state = _state().with_execution_queue_item(original)
    dispatcher = ExecutionDispatcher(StateRecorder())

    with pytest.raises(FoundationError, match="item does not match state queue"):
        dispatcher.dispatch_item(state=state, item=changed)


def test_execution_dispatcher_rejects_item_that_is_not_queued() -> None:
    dispatched = _queue_item().dispatched()
    state = _state().with_execution_queue_item(dispatched)
    dispatcher = ExecutionDispatcher(StateRecorder())

    with pytest.raises(FoundationError, match="only queued execution items may be dispatched"):
        dispatcher.dispatch_item(state=state, item=dispatched)


def test_execution_dispatcher_dispatches_all_queued_items() -> None:
    first = _queue_item(description="Run tests.")
    second = _queue_item(description="Run static checks.")
    state = _state().with_execution_queue_item(first).with_execution_queue_item(second)
    dispatcher = ExecutionDispatcher(StateRecorder())

    result = dispatcher.dispatch_all_queued(state=state)

    assert result.dispatched_count() == 2
    assert result.state.queued_execution_count() == 0
    assert result.state.dispatched_execution_count() == 2
    assert [dispatch.dispatched_item.action_id for dispatch in result.dispatched] == [
        first.action_id,
        second.action_id,
    ]


def test_execution_dispatcher_ignores_already_dispatched_items_in_batch() -> None:
    first = _queue_item(description="Run tests.")
    second = _queue_item(description="Run static checks.")
    state = _state().with_execution_queue_item(first.dispatched()).with_execution_queue_item(second)
    dispatcher = ExecutionDispatcher(StateRecorder())

    result = dispatcher.dispatch_all_queued(state=state)

    assert result.dispatched_count() == 1
    assert result.state.dispatched_execution_count() == 2
    assert result.dispatched[0].dispatched_item.action_id == second.action_id


def test_execution_dispatch_digest_changes_when_dispatched_item_changes() -> None:
    first = _queue_item(description="Run tests.")
    second = _queue_item(description="Run static checks.")
    dispatcher = ExecutionDispatcher(StateRecorder())

    first_result = dispatcher.dispatch_item(
        state=_state().with_execution_queue_item(first),
        item=first,
    )
    second_result = dispatcher.dispatch_item(
        state=_state().with_execution_queue_item(second),
        item=second,
    )

    assert first_result.digest().value != second_result.digest().value


def test_execution_batch_dispatch_digest_changes_when_batch_changes() -> None:
    first = _queue_item(description="Run tests.")
    second = _queue_item(description="Run static checks.")
    dispatcher = ExecutionDispatcher(StateRecorder())

    first_result = dispatcher.dispatch_all_queued(
        state=_state().with_execution_queue_item(first),
    )
    second_result = dispatcher.dispatch_all_queued(
        state=_state().with_execution_queue_item(first).with_execution_queue_item(second),
    )

    assert first_result.digest().value != second_result.digest().value
