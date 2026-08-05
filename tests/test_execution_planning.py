

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.execution_planning import ExecutionPlanner
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Plan authorized execution.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action(
    *,
    description: str = "Run tests.",
    requires_human_boundary: bool = False,
) -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=requires_human_boundary,
    )


def _authorized_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    action = _proposed_action(description=description)
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def test_execution_planner_queues_single_authorized_action() -> None:
    action = _authorized_action()
    state = _state().with_action(action)
    planner = ExecutionPlanner(StateRecorder())

    result = planner.queue_action(state=state, action=action)

    assert result.queued_count() == 1
    assert result.skipped_count() == 0
    assert len(result.state.execution_queue.items) == 1
    assert result.state.execution_queue.items[0].action_id == action.action_id
    assert result.state.queued_execution_count() == 1


def test_execution_planner_records_queue_event() -> None:
    action = _authorized_action()
    state = _state().with_action(action)
    planner = ExecutionPlanner(StateRecorder())

    result = planner.queue_action(state=state, action=action)

    assert len(result.state.transcript.events) == 2

    event = result.state.transcript.events[-1]

    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.FORGE
    assert event.payload["reference_type"] == "execution-queue-item"
    assert event.payload["reference_digest"] == result.queued_items[0].digest().value


def test_execution_planner_rejects_action_not_matching_state_ledger() -> None:
    original = _authorized_action(description="Original action.")
    changed = _authorized_action(description="Changed action.")
    state = _state().with_action(original)
    planner = ExecutionPlanner(StateRecorder())

    with pytest.raises(FoundationError, match="action does not match state ledger"):
        planner.queue_action(state=state, action=changed)


def test_execution_planner_rejects_unauthorized_action() -> None:
    action = _proposed_action()
    state = _state().with_action(action)
    planner = ExecutionPlanner(StateRecorder())

    with pytest.raises(FoundationError, match="only authorized bounded actions"):
        planner.queue_action(state=state, action=action)


def test_execution_planner_skips_action_already_queued() -> None:
    action = _authorized_action()
    planner = ExecutionPlanner(StateRecorder())

    first = planner.queue_action(state=_state().with_action(action), action=action)
    second = planner.queue_action(state=first.state, action=action)

    assert first.queued_count() == 1
    assert second.queued_count() == 0
    assert second.skipped_count() == 1
    assert second.skipped_actions == (action,)
    assert second.state == first.state


def test_execution_planner_queues_all_authorized_actions() -> None:
    first = _authorized_action(description="Run allowed tests.")
    second = _authorized_action(description="Run allowed static checks.")
    proposed = _proposed_action(description="Still waiting for authority.")
    state = _state().with_action(first).with_action(second).with_action(proposed)
    planner = ExecutionPlanner(StateRecorder())

    result = planner.queue_all_authorized(state=state)

    assert result.queued_count() == 2
    assert result.skipped_count() == 0
    assert result.state.queued_execution_count() == 2
    assert [item.action_id for item in result.queued_items] == [
        first.action_id,
        second.action_id,
    ]


def test_execution_planner_batch_skips_existing_queue_items() -> None:
    first = _authorized_action(description="Run allowed tests.")
    second = _authorized_action(description="Run allowed static checks.")
    state = _state().with_action(first).with_action(second)
    planner = ExecutionPlanner(StateRecorder())

    first_batch = planner.queue_all_authorized(state=state)
    second_batch = planner.queue_all_authorized(state=first_batch.state)

    assert first_batch.queued_count() == 2
    assert second_batch.queued_count() == 0
    assert second_batch.skipped_count() == 2
    assert second_batch.state == first_batch.state


def test_execution_planning_digest_changes_when_queue_changes() -> None:
    first = _authorized_action(description="Run allowed tests.")
    second = _authorized_action(description="Run allowed static checks.")
    planner = ExecutionPlanner(StateRecorder())

    first_result = planner.queue_all_authorized(state=_state().with_action(first))
    second_result = planner.queue_all_authorized(state=_state().with_action(second))

    assert first_result.digest().value != second_result.digest().value
