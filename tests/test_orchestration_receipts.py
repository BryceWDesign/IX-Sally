

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.orchestration import StageAdvanceKind, StageOrchestrator
from ix_sally.orchestration_receipts import (
    StageAdvanceLedger,
    StageAdvanceReceipt,
    StageAdvanceTrace,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record orchestration receipts.",
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
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_stage_advance_receipt_records_waiting_result_without_state_copy() -> None:
    state = _state()
    result = StageOrchestrator.create().advance_once(state=state)

    receipt = StageAdvanceReceipt.from_result(sequence=1, result=result)

    assert receipt.sequence == 1
    assert receipt.stage is RunStage.PROPOSAL_INTAKE
    assert receipt.kind is StageAdvanceKind.WAITING_FOR_PROPOSAL
    assert receipt.before_state_digest == state.digest()
    assert receipt.after_state_digest == state.digest()
    assert receipt.changed_state is False
    assert receipt.awaits_external_input() is True


def test_stage_advance_receipt_records_changed_authority_result() -> None:
    state = _state().with_action(_proposed_action())
    result = StageOrchestrator.create().advance_once(state=state)

    receipt = StageAdvanceReceipt.from_result(sequence=1, result=result)

    assert receipt.stage is RunStage.AUTHORITY_PROCESSING
    assert receipt.kind is StageAdvanceKind.AUTHORITY_PROCESSED
    assert receipt.before_state_digest == state.digest()
    assert receipt.after_state_digest == result.state.digest()
    assert receipt.changed_state is True
    assert receipt.processor_digest is not None
    assert receipt.awaits_external_input() is False


def test_stage_advance_receipt_rejects_non_positive_sequence() -> None:
    result = StageOrchestrator.create().advance_once(state=_state())

    with pytest.raises(FoundationError, match="sequence must be positive"):
        StageAdvanceReceipt.from_result(sequence=0, result=result)


def test_stage_advance_ledger_enforces_increasing_unique_sequences() -> None:
    result = StageOrchestrator.create().advance_once(state=_state())
    first = StageAdvanceReceipt.from_result(sequence=1, result=result)
    duplicate = StageAdvanceReceipt.from_result(sequence=1, result=result)

    with pytest.raises(FoundationError, match="duplicate stage advance receipt sequence"):
        StageAdvanceLedger.create((first, duplicate))


def test_stage_advance_ledger_filters_waiting_and_changed_receipts() -> None:
    orchestrator = StageOrchestrator.create()
    waiting_result = orchestrator.advance_once(state=_state())
    waiting = StageAdvanceReceipt.from_result(sequence=1, result=waiting_result)
    authority = StageAdvanceReceipt.from_result(
        sequence=2,
        result=orchestrator.advance_once(state=_state().with_action(_proposed_action())),
    )
    ledger = StageAdvanceLedger.create((waiting, authority))

    assert ledger.next_sequence() == 3
    assert ledger.waiting_receipts() == (waiting,)
    assert ledger.changed_receipts() == (authority,)
    assert ledger.by_kind(StageAdvanceKind.AUTHORITY_PROCESSED) == (authority,)


def test_stage_advance_trace_records_results_in_sequence() -> None:
    orchestrator = StageOrchestrator.create()
    first = orchestrator.advance_once(state=_state())
    second = orchestrator.advance_once(state=_state().with_action(_proposed_action()))

    trace = StageAdvanceTrace.create().record_result(first).record_result(second)

    assert trace.latest() is not None
    assert trace.latest().sequence == 2
    assert trace.ledger.next_sequence() == 3
    assert trace.ledger.changed_receipts()[0].kind is StageAdvanceKind.AUTHORITY_PROCESSED


def test_stage_advance_trace_payload_and_digest_are_stable() -> None:
    result = StageOrchestrator.create().advance_once(state=_state())
    first = StageAdvanceTrace.create().record_result(result)
    second = StageAdvanceTrace.create().record_result(result)

    assert first.to_payload()["ledger"]["receipt_count"] == 1
    latest = first.latest()

    assert latest is not None
    assert first.to_payload()["latest_digest"] == latest.digest().value
    assert first.digest() == second.digest()
