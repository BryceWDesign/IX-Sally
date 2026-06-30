from __future__ import annotations

import pytest

from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_audited_reentry_ledger import (
    AuditedHumanReviewReentryLedger,
    AuditedHumanReviewReentryLedgerEntry,
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


def _audited_reentry_ledger() -> AuditedHumanReviewReentryLedger:
    entry = AuditedHumanReviewReentryLedgerEntry.create(
        sequence=1,
        audited_reentry_result_digest=_digest("audited-result"),
        audited_reentry_receipt_digest=_digest("audited-receipt"),
        resume_operation_digest=_digest("resume-operation"),
        reentry_coordination_digest=_digest("reentry-coordination"),
        audit_report_digest=_digest("audit-report"),
        audit_workflow_operation_digest=_digest("audit-workflow"),
        before_state_digest=_digest("before-state"),
        after_state_digest=_digest("after-state"),
        before_control_plane_digest=_digest("before-control-plane"),
        reentry_control_plane_digest=_digest("reentry-control-plane"),
        after_control_plane_digest=_digest("after-control-plane"),
        final_stage=RunStage.FORGE_DISPATCH,
        reentry_status=HumanReviewReentryStatus.ADVANCED,
        audit_status=HumanReviewReentryAuditStatus.PASSED,
        report_status=HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED,
        max_steps=1,
        executed_steps=1,
    )
    return AuditedHumanReviewReentryLedger.create(()).append(entry)


def test_control_plane_state_defaults_to_empty_audited_reentry_ledger() -> None:
    state = HumanReviewControlPlaneState.create()

    assert state.audited_reentry_count() == 0
    assert state.has_recorded_audited_reentries() is False
    assert state.latest_audited_reentry_digest() is None
    assert state.to_payload()["audited_reentry_ledger_digest"] == (
        state.audited_reentry_ledger.digest().value
    )


def test_control_plane_state_tracks_audited_reentry_ledger() -> None:
    ledger = _audited_reentry_ledger()
    state = HumanReviewControlPlaneState.create().with_audited_reentry_ledger(ledger)

    assert state.audited_reentry_count() == 1
    assert state.has_recorded_audited_reentries() is True
    assert state.latest_audited_reentry_digest() == ledger.latest().digest().value
    assert state.to_payload()["audited_reentry_count"] == 1
    assert state.to_payload()["latest_audited_reentry_digest"] == (
        ledger.latest().digest().value
    )


def test_control_plane_status_tracks_audited_reentry_counts() -> None:
    state = HumanReviewControlPlaneState.create().with_audited_reentry_ledger(
        _audited_reentry_ledger()
    )

    status = HumanReviewControlPlaneStatus.from_state(state)

    assert status.audited_reentry_count == 1
    assert status.accepted_audited_reentry_count == 1
    assert status.failed_audited_reentry_count == 0
    assert status.waiting_audited_reentry_count == 0
    assert status.operator_attention_audited_reentry_count == 0
    assert status.changed_state_audited_reentry_count == 1
    assert status.has_audited_reentry() is True
    assert status.has_accepted_audited_reentry() is True
    assert status.has_failed_audited_reentry() is False
    assert status.audited_reentry_requires_operator_attention() is False
    assert status.to_payload()["audited_reentry_count"] == 1


def test_control_plane_snapshot_includes_audited_reentry_ledger_digest() -> None:
    state = HumanReviewControlPlaneState.create().with_audited_reentry_ledger(
        _audited_reentry_ledger()
    )

    snapshot = HumanReviewControlPlaneSnapshot.from_state(state)
    payload = snapshot.to_payload()

    assert payload["audited_reentry_ledger_digest"] == (
        state.audited_reentry_ledger.digest().value
    )
    assert payload["status"]["audited_reentry_count"] == 1


def test_control_plane_snapshot_rejects_audited_reentry_count_mismatch() -> None:
    state = HumanReviewControlPlaneState.create().with_audited_reentry_ledger(
        _audited_reentry_ledger()
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
        audited_reentry_count=0,
        accepted_audited_reentry_count=good_status.accepted_audited_reentry_count,
        failed_audited_reentry_count=good_status.failed_audited_reentry_count,
        waiting_audited_reentry_count=good_status.waiting_audited_reentry_count,
        operator_attention_audited_reentry_count=(
            good_status.operator_attention_audited_reentry_count
        ),
        changed_state_audited_reentry_count=(
            good_status.changed_state_audited_reentry_count
        ),
    )

    with pytest.raises(FoundationError, match="audited reentry count mismatch"):
        HumanReviewControlPlaneSnapshot(
            state=state,
            status=bad_status,
        ).require_consistent()
