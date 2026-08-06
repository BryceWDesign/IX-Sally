from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_complete_reentry_closeout_coordination import (
    CompleteHumanReviewReentryCloseoutCoordinator,
)
from ix_sally.human_review_complete_reentry_closeout_coordination_ledger import (
    CompleteHumanReviewReentryCloseoutCoordinationLedger,
    CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry,
)
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger complete human-review reentry closeout coordination.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run ledgered complete closeout coordination.",
) -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": description},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human boundary approval is required before the tool run.",
        human_review_note="Reviewer must approve the bounded tool action.",
    )
    return action.with_authority_decision(decision)


def _resume_operation(description: str = "Run ledgered complete closeout coordination."):
    run_state = _state().with_action(_review_action(description))
    action = run_state.actions.human_review_actions()[0]
    kit = HumanReviewWorkflowKit.create()
    handoff = kit.open_handoff(run_state=run_state)
    decision = kit.record_action_decision(
        run_state=run_state,
        control_plane=handoff.control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    clearance = kit.assess_clearance(
        run_state=decision.run_state,
        control_plane=decision.control_plane,
        handoff=handoff.require_handoff(),
    )
    return kit.record_resume(clearance=clearance)


def _coordination_result(
    description: str = "Run ledgered complete closeout coordination.",
    max_steps: int = 1,
):
    return CompleteHumanReviewReentryCloseoutCoordinator.create().resume_closeout_and_record(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )


def test_closeout_coordination_ledger_entry_records_result() -> None:
    result = _coordination_result(max_steps=1)

    entry = CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
        sequence=1,
        result=result,
    )

    assert entry.sequence == 1
    assert entry.coordination_result_digest == result.digest()
    assert entry.coordination_receipt_digest == result.receipt.digest()
    assert entry.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    assert entry.final_stage is RunStage.FORGE_DISPATCH
    assert entry.changed_state() is True
    assert entry.recorded_complete_reentry() is True
    assert entry.recorded_closeout() is True
    assert entry.accepted() is True
    assert entry.waiting_for_external_input() is False
    assert entry.blocked() is False


def test_closeout_coordination_ledger_appends_result() -> None:
    result = _coordination_result(max_steps=1)

    updated = CompleteHumanReviewReentryCloseoutCoordinationLedger.create(()).append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.coordination_result_digest == result.digest()
    assert updated.accepted_entries() == (latest,)
    assert updated.waiting_entries() == ()
    assert updated.blocked_entries() == ()
    assert updated.changed_state_entries() == (latest,)
    assert updated.recorded_closeout_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_DISPATCH) == (latest,)


def test_closeout_coordination_ledger_tracks_waiting_result() -> None:
    result = _coordination_result(max_steps=3)

    updated = CompleteHumanReviewReentryCloseoutCoordinationLedger.create(()).append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert latest.waiting_for_external_input() is True
    assert updated.waiting_entries() == (latest,)
    assert updated.accepted_entries() == ()
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)
    assert updated.entries_for_closeout_status(
        CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
    ) == (latest,)


def test_closeout_coordination_ledger_rejects_duplicate_result_digest() -> None:
    result = _coordination_result(max_steps=1)
    first = CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
        sequence=1,
        result=result,
    )
    duplicate = CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
        sequence=2,
        result=result,
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete reentry closeout coordination result digest",
    ):
        CompleteHumanReviewReentryCloseoutCoordinationLedger.create((first, duplicate))


def test_closeout_coordination_ledger_rejects_duplicate_sequence() -> None:
    first = CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
        sequence=1,
        result=_coordination_result("Run first closeout coordination."),
    )
    second = CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.from_result(
        sequence=1,
        result=_coordination_result("Run second closeout coordination."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete reentry closeout coordination ledger sequence",
    ):
        CompleteHumanReviewReentryCloseoutCoordinationLedger.create((first, second))


def test_closeout_coordination_ledger_entry_rejects_invalid_steps() -> None:
    result = _coordination_result(max_steps=1)

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        CompleteHumanReviewReentryCloseoutCoordinationLedgerEntry.create(
            sequence=1,
            coordination_result_digest=result.digest(),
            coordination_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            complete_reentry_result_digest=(result.receipt.complete_reentry_result_digest),
            complete_reentry_receipt_digest=(result.receipt.complete_reentry_receipt_digest),
            closeout_report_digest=result.receipt.closeout_report_digest,
            closeout_workflow_operation_digest=(result.receipt.closeout_workflow_operation_digest),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            closeout_control_plane_digest=result.receipt.closeout_control_plane_digest,
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            closeout_status=result.receipt.closeout_status,
            max_steps=0,
            executed_steps=0,
        )


def test_closeout_coordination_ledger_payload_and_digest_are_stable() -> None:
    result = _coordination_result(max_steps=1)

    first = CompleteHumanReviewReentryCloseoutCoordinationLedger.create(()).append_result(result)
    second = CompleteHumanReviewReentryCloseoutCoordinationLedger.create(()).append_result(result)
    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["accepted_entry_count"] == 1
    assert payload["waiting_entry_count"] == 0
    assert payload["blocked_entry_count"] == 0
    assert payload["changed_state_entry_count"] == 1
    assert payload["recorded_closeout_entry_count"] == 1
    assert first.digest() == second.digest()
