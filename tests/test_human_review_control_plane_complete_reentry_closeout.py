from __future__ import annotations

import pytest

from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_complete_reentry_report_ledger import (
    CompleteHumanReviewReentryCloseoutLedger,
    CompleteHumanReviewReentryCloseoutLedgerEntry,
)
from ix_sally.human_review_control_plane import (
    HumanReviewControlPlaneSnapshot,
    HumanReviewControlPlaneState,
    HumanReviewControlPlaneStatus,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.stage_readiness import RunStage


def _digest(label: str) -> DigestRecord:
    return DigestRecord.from_payload({"record": label})


def _closeout_ledger() -> CompleteHumanReviewReentryCloseoutLedger:
    entry = CompleteHumanReviewReentryCloseoutLedgerEntry.create(
        sequence=1,
        closeout_report_digest=_digest("closeout-report"),
        complete_reentry_result_digest=_digest("complete-result"),
        complete_reentry_receipt_digest=_digest("complete-receipt"),
        final_workflow_operation_digest=_digest("final-workflow"),
        state_digest=_digest("state"),
        control_plane_digest=_digest("control-plane"),
        final_stage=RunStage.FORGE_DISPATCH,
        reentry_status=HumanReviewReentryStatus.ADVANCED,
        audit_status=HumanReviewReentryAuditStatus.PASSED,
        report_status=HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
        closeout_status=CompleteHumanReviewReentryCloseoutStatus.ACCEPTED,
        max_steps=1,
        executed_steps=1,
        reentry_count=1,
        reentry_audit_count=1,
        audited_reentry_count=1,
        complete_reentry_count=1,
        finding_count=6,
        blocking_finding_count=0,
    )
    return CompleteHumanReviewReentryCloseoutLedger.create(()).append(entry)


def test_control_plane_state_defaults_to_empty_closeout_ledger() -> None:
    state = HumanReviewControlPlaneState.create()

    assert state.complete_reentry_closeout_count() == 0
    assert state.has_recorded_complete_reentry_closeouts() is False
    assert state.latest_complete_reentry_closeout_digest() is None
    assert state.to_payload()["complete_reentry_closeout_ledger_digest"] == (
        state.complete_reentry_closeout_ledger.digest().value
    )


def test_control_plane_state_tracks_closeout_ledger() -> None:
    ledger = _closeout_ledger()
    state = HumanReviewControlPlaneState.create().with_complete_reentry_closeout_ledger(ledger)

    assert state.complete_reentry_closeout_count() == 1
    assert state.has_recorded_complete_reentry_closeouts() is True
    assert state.latest_complete_reentry_closeout_digest() == (ledger.latest().digest().value)
    assert state.to_payload()["complete_reentry_closeout_count"] == 1
    assert state.to_payload()["latest_complete_reentry_closeout_digest"] == (
        ledger.latest().digest().value
    )


def test_control_plane_status_tracks_closeout_counts() -> None:
    state = HumanReviewControlPlaneState.create().with_complete_reentry_closeout_ledger(
        _closeout_ledger()
    )

    status = HumanReviewControlPlaneStatus.from_state(state)

    assert status.complete_reentry_closeout_count == 1
    assert status.accepted_complete_reentry_closeout_count == 1
    assert status.waiting_complete_reentry_closeout_count == 0
    assert status.blocked_complete_reentry_closeout_count == 0
    assert status.blocking_finding_complete_reentry_closeout_count == 0
    assert status.has_complete_reentry_closeout() is True
    assert status.has_accepted_complete_reentry_closeout() is True
    assert status.has_blocked_complete_reentry_closeout() is False
    assert status.complete_reentry_closeout_has_blocking_findings() is False
    assert status.to_payload()["complete_reentry_closeout_count"] == 1


def test_control_plane_snapshot_includes_closeout_ledger_digest() -> None:
    state = HumanReviewControlPlaneState.create().with_complete_reentry_closeout_ledger(
        _closeout_ledger()
    )

    snapshot = HumanReviewControlPlaneSnapshot.from_state(state)
    payload = snapshot.to_payload()

    assert payload["complete_reentry_closeout_ledger_digest"] == (
        state.complete_reentry_closeout_ledger.digest().value
    )
    assert payload["status"]["complete_reentry_closeout_count"] == 1


def test_control_plane_snapshot_rejects_closeout_count_mismatch() -> None:
    state = HumanReviewControlPlaneState.create().with_complete_reentry_closeout_ledger(
        _closeout_ledger()
    )
    good_status = HumanReviewControlPlaneStatus.from_state(state)
    bad_status = HumanReviewControlPlaneStatus(
        state_digest=state.digest(),
        handoff_count=good_status.handoff_count,
        decision_count=good_status.decision_count,
        resume_count=good_status.resume_count,
        reentry_count=good_status.reentry_count,
        reentry_audit_count=good_status.reentry_audit_count,
        approved_decision_count=good_status.approved_decision_count,
        rejected_decision_count=good_status.rejected_decision_count,
        deferred_decision_count=good_status.deferred_decision_count,
        cleared_resume_count=good_status.cleared_resume_count,
        execution_planning_resume_count=good_status.execution_planning_resume_count,
        completed_reentry_count=good_status.completed_reentry_count,
        waiting_reentry_count=good_status.waiting_reentry_count,
        passed_reentry_audit_count=good_status.passed_reentry_audit_count,
        failed_reentry_audit_count=good_status.failed_reentry_audit_count,
        waiting_reentry_audit_count=good_status.waiting_reentry_audit_count,
        blocking_reentry_audit_count=good_status.blocking_reentry_audit_count,
        audited_reentry_count=good_status.audited_reentry_count,
        accepted_audited_reentry_count=good_status.accepted_audited_reentry_count,
        failed_audited_reentry_count=good_status.failed_audited_reentry_count,
        waiting_audited_reentry_count=good_status.waiting_audited_reentry_count,
        operator_attention_audited_reentry_count=(
            good_status.operator_attention_audited_reentry_count
        ),
        changed_state_audited_reentry_count=(good_status.changed_state_audited_reentry_count),
        complete_reentry_count=good_status.complete_reentry_count,
        accepted_complete_reentry_count=good_status.accepted_complete_reentry_count,
        failed_complete_reentry_count=good_status.failed_complete_reentry_count,
        waiting_complete_reentry_count=good_status.waiting_complete_reentry_count,
        operator_attention_complete_reentry_count=(
            good_status.operator_attention_complete_reentry_count
        ),
        changed_state_complete_reentry_count=(good_status.changed_state_complete_reentry_count),
        complete_reentry_closeout_count=0,
        accepted_complete_reentry_closeout_count=(
            good_status.accepted_complete_reentry_closeout_count
        ),
        waiting_complete_reentry_closeout_count=(
            good_status.waiting_complete_reentry_closeout_count
        ),
        blocked_complete_reentry_closeout_count=(
            good_status.blocked_complete_reentry_closeout_count
        ),
        blocking_finding_complete_reentry_closeout_count=(
            good_status.blocking_finding_complete_reentry_closeout_count
        ),
    )

    with pytest.raises(FoundationError, match="closeout count mismatch"):
        HumanReviewControlPlaneSnapshot(
            state=state,
            status=bad_status,
        ).require_consistent()
