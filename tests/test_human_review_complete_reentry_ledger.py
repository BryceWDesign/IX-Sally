from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_complete_reentry import (
    CompleteHumanReviewReentryCoordinator,
)
from ix_sally.human_review_complete_reentry_ledger import (
    CompleteHumanReviewReentryLedger,
    CompleteHumanReviewReentryLedgerEntry,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger complete audited human-review reentry results.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run ledgered complete human-review reentry.",
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


def _resume_operation(description: str = "Run ledgered complete human-review reentry."):
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


def _complete_result(
    description: str = "Run ledgered complete human-review reentry.",
    max_steps: int = 1,
):
    return CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )


def test_complete_reentry_ledger_entry_records_result() -> None:
    result = _complete_result()

    entry = CompleteHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=result,
    )

    assert entry.sequence == 1
    assert entry.complete_reentry_result_digest == result.digest()
    assert entry.complete_reentry_receipt_digest == result.receipt.digest()
    assert entry.final_stage is RunStage.FORGE_DISPATCH
    assert entry.reentry_status is HumanReviewReentryStatus.ADVANCED
    assert entry.audit_status is HumanReviewReentryAuditStatus.PASSED
    assert entry.report_status is (HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED)
    assert entry.changed_state() is True
    assert entry.recorded_reentry_and_audit() is True
    assert entry.recorded_complete_audited_reentry() is True
    assert entry.accepted() is True
    assert entry.failed() is False


def test_complete_reentry_ledger_appends_result_at_next_sequence() -> None:
    result = _complete_result()
    ledger = CompleteHumanReviewReentryLedger.create(())

    updated = ledger.append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.complete_reentry_result_digest == result.digest()
    assert updated.accepted_entries() == (latest,)
    assert updated.failed_entries() == ()
    assert updated.changed_state_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_DISPATCH) == (latest,)


def test_complete_reentry_ledger_tracks_waiting_external_input_result() -> None:
    result = _complete_result(max_steps=3)

    updated = CompleteHumanReviewReentryLedger.create(()).append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert latest.waiting_for_external_input() is True
    assert updated.waiting_entries() == (latest,)
    assert updated.accepted_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)


def test_complete_reentry_ledger_rejects_duplicate_result_digest() -> None:
    result = _complete_result()
    first = CompleteHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=result,
    )
    duplicate = CompleteHumanReviewReentryLedgerEntry.from_result(
        sequence=2,
        result=result,
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete human-review reentry result digest",
    ):
        CompleteHumanReviewReentryLedger.create((first, duplicate))


def test_complete_reentry_ledger_rejects_duplicate_sequence() -> None:
    first = CompleteHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_complete_result("Run first ledgered complete reentry."),
    )
    second = CompleteHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_complete_result("Run second ledgered complete reentry."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete human-review reentry ledger sequence",
    ):
        CompleteHumanReviewReentryLedger.create((first, second))


def test_complete_reentry_ledger_entry_rejects_invalid_step_counts() -> None:
    result = _complete_result()

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        CompleteHumanReviewReentryLedgerEntry.create(
            sequence=1,
            complete_reentry_result_digest=result.digest(),
            complete_reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            audited_reentry_result_digest=result.receipt.audited_reentry_result_digest,
            audited_reentry_receipt_digest=result.receipt.audited_reentry_receipt_digest,
            final_workflow_operation_digest=(result.receipt.final_workflow_operation_digest),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            audited_reentry_control_plane_digest=(
                result.receipt.audited_reentry_control_plane_digest
            ),
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            max_steps=0,
            executed_steps=0,
        )


def test_complete_reentry_ledger_payload_and_digest_are_stable() -> None:
    result = _complete_result()

    first = CompleteHumanReviewReentryLedger.create(()).append_result(result)
    second = CompleteHumanReviewReentryLedger.create(()).append_result(result)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["accepted_entry_count"] == 1
    assert payload["failed_entry_count"] == 0
    assert payload["changed_state_entry_count"] == 1
    assert payload["forge_dispatch_entry_count"] == 1
    assert first.digest() == second.digest()
