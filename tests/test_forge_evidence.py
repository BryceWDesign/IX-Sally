

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_evidence import ForgeEvidenceAdapter, ForgeEvidenceRecord
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Convert Forge results into evidence.",
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


def test_forge_evidence_adapter_creates_evidence_from_passed_result() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.PASSED)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    evidence = adapter.evidence_from_result(result)

    assert evidence.cycle == 1
    assert evidence.produced_by is AgentRole.FORGE
    assert evidence.kind is EvidenceKind.OBSERVATION
    assert evidence.status is EvidenceStatus.RECORDED
    assert evidence.summary == "Forge result passed: Forge execution passed. Output: 1 passed"


def test_forge_evidence_adapter_creates_evidence_from_failed_result() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.FAILED)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    evidence = adapter.evidence_from_result(result)

    assert evidence.summary == "Forge result failed: Forge execution failed. Output: 1 failed"


def test_forge_evidence_adapter_creates_evidence_from_blocked_result() -> None:
    action = _authorized_action()
    result = _forge_result(action=action, status=ForgeResultStatus.BLOCKED)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    evidence = adapter.evidence_from_result(result)

    assert evidence.summary == (
        "Forge result blocked: Forge execution blocked. Boundary: Boundary blocked execution."
    )


def test_forge_evidence_record_requires_matching_cycle() -> None:
    action = _authorized_action()
    result = _forge_result(action=action)
    evidence = EvidenceRecord.create(
        cycle=2,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="cycle must match"):
        ForgeEvidenceRecord.create(
            forge_result=result,
            evidence_record=evidence,
            evidence_summary=evidence.summary,
        )


def test_forge_evidence_record_requires_forge_producer() -> None:
    action = _authorized_action()
    result = _forge_result(action=action)
    evidence = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Wrong producer.",
    )

    with pytest.raises(FoundationError, match="produced by IX-Forge"):
        ForgeEvidenceRecord.create(
            forge_result=result,
            evidence_record=evidence,
            evidence_summary=evidence.summary,
        )


def test_forge_evidence_record_payload_is_stable() -> None:
    action = _authorized_action()
    result = _forge_result(action=action)
    adapter = ForgeEvidenceAdapter(StateRecorder())
    evidence = adapter.evidence_from_result(result)

    record = ForgeEvidenceRecord.create(
        forge_result=result,
        evidence_record=evidence,
        evidence_summary=evidence.summary,
    )

    assert record.to_payload() == {
        "forge_result_digest": {
            "algorithm": "sha256",
            "value": result.digest().value,
        },
        "evidence_record_digest": evidence.digest().value,
        "evidence_summary": "Forge result passed: Forge execution passed. Output: 1 passed",
        "evidence_status": "recorded",
        "evidence_kind": "observation",
    }


def test_forge_evidence_adapter_records_result_evidence() -> None:
    action = _authorized_action()
    result = _forge_result(action=action)
    state = _state().with_forge_result(result)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    processed = adapter.record_result_evidence(state=state, result=result)

    assert processed.evidence_count() == 1
    assert len(processed.state.evidence.records) == 1
    assert processed.state.evidence.records[0].summary == (
        "Forge result passed: Forge execution passed. Output: 1 passed"
    )
    assert processed.state.transcript.events[-1].event_type is RuntimeEventType.EVIDENCE_RECORDED


def test_forge_evidence_adapter_records_all_result_evidence_once() -> None:
    first_action = _authorized_action(description="Run passing tests.")
    second_action = _authorized_action(description="Run failing tests.")
    first_result = _forge_result(action=first_action, status=ForgeResultStatus.PASSED)
    second_result = _forge_result(action=second_action, status=ForgeResultStatus.FAILED)
    state = _state().with_forge_result(first_result).with_forge_result(second_result)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    first_pass = adapter.record_all_result_evidence(state=state)
    second_pass = adapter.record_all_result_evidence(state=first_pass.state)

    assert first_pass.evidence_count() == 2
    assert second_pass.evidence_count() == 0
    assert len(second_pass.state.evidence.records) == 2


def test_forge_evidence_processing_digest_changes_when_evidence_changes() -> None:
    first_action = _authorized_action(description="Run passing tests.")
    second_action = _authorized_action(description="Run blocked tests.")
    first_result = _forge_result(action=first_action, status=ForgeResultStatus.PASSED)
    second_result = _forge_result(action=second_action, status=ForgeResultStatus.BLOCKED)
    adapter = ForgeEvidenceAdapter(StateRecorder())

    first_processed = adapter.record_all_result_evidence(
        state=_state().with_forge_result(first_result),
    )
    second_processed = adapter.record_all_result_evidence(
        state=_state().with_forge_result(second_result),
    )

    assert first_processed.digest().value != second_processed.digest().value
