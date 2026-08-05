

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
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutReport,
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_complete_reentry_report_ledger import (
    CompleteHumanReviewReentryCloseoutLedger,
    CompleteHumanReviewReentryCloseoutLedgerEntry,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger complete human-review reentry closeout reports.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run ledgered complete closeout human-review reentry.",
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


def _resume_operation(
    description: str = "Run ledgered complete closeout human-review reentry.",
):
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


def _closeout_report(
    description: str = "Run ledgered complete closeout human-review reentry.",
    max_steps: int = 1,
) -> CompleteHumanReviewReentryCloseoutReport:
    result = CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )
    return CompleteHumanReviewReentryCloseoutReport.from_result(result)


def test_complete_reentry_closeout_ledger_entry_records_report() -> None:
    report = _closeout_report(max_steps=1)

    entry = CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
        sequence=1,
        report=report,
    )

    assert entry.sequence == 1
    assert entry.closeout_report_digest == report.digest()
    assert entry.complete_reentry_result_digest == (
        report.complete_reentry_result_digest
    )
    assert entry.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    assert entry.final_stage is RunStage.FORGE_DISPATCH
    assert entry.finding_count == 6
    assert entry.blocking_finding_count == 0
    assert entry.accepted() is True
    assert entry.waiting_for_external_input() is False
    assert entry.blocked() is False
    assert entry.has_blocking_findings() is False


def test_complete_reentry_closeout_ledger_appends_report() -> None:
    report = _closeout_report(max_steps=1)

    updated = CompleteHumanReviewReentryCloseoutLedger.create(()).append_report(report)
    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.closeout_report_digest == report.digest()
    assert updated.accepted_entries() == (latest,)
    assert updated.waiting_entries() == ()
    assert updated.blocked_entries() == ()
    assert updated.entries_for_stage(RunStage.FORGE_DISPATCH) == (latest,)
    assert updated.entries_for_closeout_status(
        CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    ) == (latest,)


def test_complete_reentry_closeout_ledger_tracks_waiting_external_input() -> None:
    report = _closeout_report(max_steps=3)

    updated = CompleteHumanReviewReentryCloseoutLedger.create(()).append_report(report)
    latest = updated.latest()

    assert latest is not None
    assert latest.waiting_for_external_input() is True
    assert updated.waiting_entries() == (latest,)
    assert updated.accepted_entries() == ()
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)
    assert updated.entries_for_closeout_status(
        CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
    ) == (latest,)


def test_complete_reentry_closeout_ledger_rejects_duplicate_report_digest() -> None:
    report = _closeout_report(max_steps=1)
    first = CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
        sequence=1,
        report=report,
    )
    duplicate = CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
        sequence=2,
        report=report,
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete reentry closeout report digest",
    ):
        CompleteHumanReviewReentryCloseoutLedger.create((first, duplicate))


def test_complete_reentry_closeout_ledger_rejects_duplicate_sequence() -> None:
    first = CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
        sequence=1,
        report=_closeout_report("Run first ledgered closeout reentry."),
    )
    second = CompleteHumanReviewReentryCloseoutLedgerEntry.from_report(
        sequence=1,
        report=_closeout_report("Run second ledgered closeout reentry."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate complete reentry closeout ledger sequence",
    ):
        CompleteHumanReviewReentryCloseoutLedger.create((first, second))


def test_complete_reentry_closeout_ledger_entry_rejects_invalid_counts() -> None:
    report = _closeout_report(max_steps=1)

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        CompleteHumanReviewReentryCloseoutLedgerEntry.create(
            sequence=1,
            closeout_report_digest=report.digest(),
            complete_reentry_result_digest=report.complete_reentry_result_digest,
            complete_reentry_receipt_digest=report.complete_reentry_receipt_digest,
            final_workflow_operation_digest=report.final_workflow_operation_digest,
            state_digest=report.state_digest,
            control_plane_digest=report.control_plane_digest,
            final_stage=report.final_stage,
            reentry_status=report.reentry_status,
            audit_status=report.audit_status,
            report_status=report.report_status,
            closeout_status=report.closeout_status,
            max_steps=0,
            executed_steps=0,
            reentry_count=report.reentry_count,
            reentry_audit_count=report.reentry_audit_count,
            audited_reentry_count=report.audited_reentry_count,
            complete_reentry_count=report.complete_reentry_count,
            finding_count=len(report.findings),
            blocking_finding_count=len(report.blocking_findings()),
        )


def test_complete_reentry_closeout_ledger_payload_and_digest_are_stable() -> None:
    report = _closeout_report(max_steps=1)

    first = CompleteHumanReviewReentryCloseoutLedger.create(()).append_report(report)
    second = CompleteHumanReviewReentryCloseoutLedger.create(()).append_report(report)
    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["accepted_entry_count"] == 1
    assert payload["waiting_entry_count"] == 0
    assert payload["blocked_entry_count"] == 0
    assert payload["blocking_finding_entry_count"] == 0
    assert payload["forge_dispatch_entry_count"] == 1
    assert first.digest() == second.digest()
