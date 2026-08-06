from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record Forge results.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
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
    status: ForgeResultStatus = ForgeResultStatus.PASSED,
    description: str = "Run tests.",
) -> ForgeResultRecord:
    action = _authorized_action(description=description)
    item = ExecutionQueueItem.from_action(action).dispatched()

    if status is ForgeResultStatus.FAILED:
        return ForgeResultRecord.from_dispatched_item(
            item=item,
            action=action,
            status=status,
            summary="Forge execution failed.",
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


def test_run_state_starts_with_empty_forge_result_ledger() -> None:
    state = _state()

    assert len(state.forge_results.results) == 0
    assert state.passed_forge_result_count() == 0
    assert state.failed_forge_result_count() == 0
    assert state.blocked_forge_result_count() == 0
    assert state.human_review_forge_result_count() == 0
    assert state.to_payload()["forge_result_count"] == 0


def test_run_state_appends_passed_forge_result_immutably() -> None:
    state = _state()
    result = _forge_result(status=ForgeResultStatus.PASSED)

    updated = state.with_forge_result(result)

    assert len(state.forge_results.results) == 0
    assert len(updated.forge_results.results) == 1
    assert updated.passed_forge_result_count() == 1
    assert updated.failed_forge_result_count() == 0
    assert updated.requires_human_review() is False


def test_run_state_counts_failed_forge_result_as_human_review() -> None:
    state = _state()
    result = _forge_result(status=ForgeResultStatus.FAILED)

    updated = state.with_forge_result(result)

    assert updated.failed_forge_result_count() == 1
    assert updated.human_review_forge_result_count() == 1
    assert updated.requires_human_review() is True
    assert updated.to_payload()["human_review_forge_result_count"] == 1


def test_run_state_counts_blocked_forge_result_as_human_review() -> None:
    state = _state()
    result = _forge_result(status=ForgeResultStatus.BLOCKED)

    updated = state.with_forge_result(result)

    assert updated.blocked_forge_result_count() == 1
    assert updated.human_review_forge_result_count() == 1
    assert updated.requires_human_review() is True


def test_state_recorder_records_forge_result_and_event() -> None:
    recorder = StateRecorder()
    state = _state()
    result = _forge_result(status=ForgeResultStatus.PASSED)

    updated = recorder.record_forge_result(state, result)

    assert len(updated.forge_results.results) == 1
    assert len(updated.transcript.events) == 2

    event = updated.transcript.events[-1]

    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.FORGE
    assert event.summary == "Recorded Forge result from ix-forge: passed."
    assert event.payload["reference_type"] == "forge-result"
    assert event.payload["reference_digest"] == result.digest().value


def test_forge_result_state_digest_changes_when_result_is_recorded() -> None:
    state = _state()
    result = _forge_result(status=ForgeResultStatus.PASSED)

    updated = state.with_forge_result(result)

    assert state.digest().value != updated.digest().value
    assert (
        state.to_payload()["forge_result_ledger_digest"]
        != updated.to_payload()["forge_result_ledger_digest"]
    )
