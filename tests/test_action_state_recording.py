from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record bounded actions.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_run_state_appends_action_immutably() -> None:
    state = _state()
    action = _proposed_action()

    updated = state.with_action(action)

    assert len(state.actions.actions) == 0
    assert len(updated.actions.actions) == 1
    assert updated.actions.require_action(action.action_id.value) == action
    assert updated.to_payload()["action_count"] == 1


def test_run_state_counts_executable_actions() -> None:
    state = _state()
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    authorized = action.with_authority_decision(decision)

    updated = state.with_action(authorized)

    assert updated.executable_action_count() == 1
    assert updated.blocked_action_count() == 0
    assert updated.human_review_action_count() == 0
    assert updated.to_payload()["executable_action_count"] == 1


def test_run_state_counts_human_review_actions() -> None:
    state = _state()
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review required.",
        human_review_note="Human boundary review required.",
    )
    human_review = action.with_authority_decision(decision)

    updated = state.with_action(human_review)

    assert updated.requires_human_review() is True
    assert updated.blocked_action_count() == 1
    assert updated.human_review_action_count() == 1
    assert updated.to_payload()["requires_human_review"] is True


def test_state_recorder_records_bounded_action_and_event() -> None:
    recorder = StateRecorder()
    state = _state()
    action = _proposed_action()

    updated = recorder.record_action(state, action)

    assert len(updated.actions.actions) == 1
    assert len(updated.transcript.events) == 2

    event = updated.transcript.events[-1]

    assert event.event_type is RuntimeEventType.JURISDICTION_DECIDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Recorded bounded action from ix-forge: proposed."
    assert event.payload["reference_type"] == "bounded-action"
    assert event.payload["reference_digest"] == action.digest().value


def test_state_digest_changes_when_action_is_recorded() -> None:
    state = _state()
    updated = state.with_action(_proposed_action())

    assert state.digest().value != updated.digest().value
