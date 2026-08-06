from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record bounded action updates.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _action(*, description: str = "Run tests.") -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _authorized_action(action: BoundedActionRecord) -> BoundedActionRecord:
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def test_state_recorder_records_action_update_without_duplicate_append() -> None:
    recorder = StateRecorder()
    action = _action()
    updated_action = _authorized_action(action)
    state = _state().with_action(action).replace_action(updated_action)

    recorded = recorder.record_action_update(state, updated_action)

    assert len(recorded.actions.actions) == 1
    assert recorded.actions.require_action(action.action_id.value) == updated_action
    assert len(recorded.transcript.events) == 2

    event = recorded.transcript.events[-1]

    assert event.event_type is RuntimeEventType.JURISDICTION_DECIDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Updated bounded action from ix-forge: authorized."
    assert event.payload["reference_type"] == "bounded-action"
    assert event.payload["reference_digest"] == updated_action.digest().value


def test_state_recorder_rejects_action_update_that_does_not_match_ledger() -> None:
    recorder = StateRecorder()
    action = _action(description="Original action.")
    changed = _action(description="Changed action.")
    state = _state().with_action(action)

    with pytest.raises(FoundationError, match="bounded action update does not match"):
        recorder.record_action_update(state, changed)


def test_state_recorder_rejects_stale_action_update_payload() -> None:
    recorder = StateRecorder()
    action = _action()
    updated_action = _authorized_action(action)
    state = _state().with_action(action)

    with pytest.raises(FoundationError, match="bounded action update does not match"):
        recorder.record_action_update(state, updated_action)
