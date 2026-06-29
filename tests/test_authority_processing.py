from __future__ import annotations

import pytest

from ix_sally.actions import ActionStatus, BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authority_processing import AuthorityProcessor
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state(
    *,
    allowed_tools: tuple[str, ...] = ("test-runner",),
    memory_writes_allowed: bool = False,
) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Process bounded authority.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=allowed_tools,
        memory_writes_allowed=memory_writes_allowed,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _tool_action(*, tool_key: str = "test-runner") -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key=tool_key,
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_bounded_action_ledger_replace_updates_existing_action() -> None:
    action = _tool_action()
    state = _state().with_action(action)
    updated_action = action.with_authority_decision(
        state.runtime_kit.require_authority(
            role=AgentRole.FORGE,
            authority="tool-execution",
        ).__class__(
            role=AgentRole.FORGE,
            authority=action.requested_authority,
            status=state.runtime_kit.evaluate_authority(
                role=AgentRole.FORGE,
                authority="tool-execution",
            ).status,
            reason="manual test decision",
        )
    )

    replaced = state.replace_action(updated_action)

    assert replaced.actions.require_action(action.action_id.value) == updated_action


def test_bounded_action_ledger_replace_rejects_unknown_action() -> None:
    action = _tool_action()
    state = _state()

    with pytest.raises(FoundationError, match="unknown bounded action id"):
        state.replace_action(action)


def test_authority_processor_allows_authorized_tool_action() -> None:
    action = _tool_action()
    state = _state().with_action(action)
    processor = AuthorityProcessor(StateRecorder())

    result = processor.process_action(state=state, action=action)

    assert result.original_action == action
    assert result.updated_action.status is ActionStatus.AUTHORIZED
    assert result.updated_action.allows_execution() is True
    assert result.authority_decision.allows_action() is True
    assert result.state.actions.require_action(action.action_id.value) == result.updated_action
    assert result.state.executable_action_count() == 1
    assert result.state.proposed_action_count() == 0


def test_authority_processor_denies_unallowed_tool_action() -> None:
    action = _tool_action(tool_key="network-client")
    state = _state().with_action(action)
    processor = AuthorityProcessor(StateRecorder())

    result = processor.process_action(state=state, action=action)

    assert result.updated_action.status is ActionStatus.DENIED
    assert result.updated_action.blocks_progress() is True
    assert result.authority_decision.denies_action() is True
    assert result.state.denied_authority_count() == 1
    assert result.state.blocked_action_count() == 1


def test_authority_processor_routes_human_review_action() -> None:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run reviewed tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )
    state = _state().with_action(action)
    processor = AuthorityProcessor(StateRecorder())

    result = processor.process_action(state=state, action=action)

    assert result.updated_action.status is ActionStatus.HUMAN_REVIEW_REQUIRED
    assert result.updated_action.requires_human_review() is True
    assert result.state.requires_human_review() is True
    assert result.state.human_review_authority_count() == 1


def test_authority_processor_rejects_action_not_matching_state_ledger() -> None:
    original = _tool_action()
    changed = BoundedActionRecord.create(
        action_id=original.action_id,
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Changed action.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "changed"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    state = _state().with_action(original)
    processor = AuthorityProcessor(StateRecorder())

    with pytest.raises(FoundationError, match="action does not match state ledger"):
        processor.process_action(state=state, action=changed)


def test_authority_processor_records_decision_and_action_events() -> None:
    action = _tool_action()
    state = _state().with_action(action)
    processor = AuthorityProcessor(StateRecorder())

    result = processor.process_action(state=state, action=action)
    event_types = [event.event_type for event in result.state.transcript.events]

    assert event_types == [
        RuntimeEventType.CHAMBER_OPENED,
        RuntimeEventType.JURISDICTION_DECIDED,
        RuntimeEventType.JURISDICTION_DECIDED,
    ]
    assert result.state.transcript.events[-2].payload["reference_type"] == "authority-decision"
    assert result.state.transcript.events[-1].payload["reference_type"] == "bounded-action"


def test_authority_processor_processes_all_proposed_actions() -> None:
    first = _tool_action(tool_key="test-runner")
    second = _tool_action(tool_key="network-client")
    state = _state().with_action(first).with_action(second)
    processor = AuthorityProcessor(StateRecorder())

    result = processor.process_all_proposed(state=state)

    assert result.processed_count() == 2
    assert result.authorized_count() == 1
    assert result.blocked_count() == 1
    assert result.human_review_count() == 0
    assert result.state.proposed_action_count() == 0
    assert result.state.executable_action_count() == 1
    assert result.state.blocked_action_count() == 1


def test_authority_batch_digest_changes_when_processing_changes() -> None:
    first = _tool_action(tool_key="test-runner")
    second = _tool_action(tool_key="network-client")
    processor = AuthorityProcessor(StateRecorder())

    allowed_result = processor.process_all_proposed(state=_state().with_action(first))
    denied_result = processor.process_all_proposed(state=_state().with_action(second))

    assert allowed_result.digest().value != denied_result.digest().value
