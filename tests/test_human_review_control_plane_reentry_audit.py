from __future__ import annotations

import pytest

from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_control_plane import (
    HumanReviewControlPlaneSnapshot,
    HumanReviewControlPlaneState,
    HumanReviewControlPlaneStatus,
)
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.human_review_reentry_audit_ledger import (
    HumanReviewReentryAuditLedger,
    HumanReviewReentryAuditLedgerEntry,
)
from ix_sally.stage_readiness import RunStage


def _digest(label: str) -> DigestRecord:
    return DigestRecord.from_payload({"record": label})


def _reentry_audit_ledger() -> HumanReviewReentryAuditLedger:
    entry = HumanReviewReentryAuditLedgerEntry.create(
        sequence=1,
        audit_report_digest=_digest("audit-report"),
        coordination_digest=_digest("coordination"),
        resume_operation_digest=_digest("resume-operation"),
        reentry_result_digest=_digest("reentry-result"),
        workflow_operation_digest=_digest("workflow-operation"),
        state_digest=_digest("state"),
        control_plane_digest=_digest("control-plane"),
        final_stage=RunStage.FORGE_DISPATCH,
        reentry_status=HumanReviewReentryStatus.ADVANCED,
        audit_status=HumanReviewReentryAuditStatus.PASSED,
        finding_count=6,
        blocking_finding_count=0,
        warning_finding_count=0,
        info_finding_count=6,
    )
    return HumanReviewReentryAuditLedger.create(()).append(entry)


def test_control_plane_state_defaults_to_empty_reentry_audit_ledger() -> None:
    state = HumanReviewControlPlaneState.create()

    assert state.reentry_audit_count() == 0
    assert state.has_recorded_reentry_audits() is False
    assert state.latest_reentry_audit_digest() is None
    assert state.to_payload()["reentry_audit_ledger_digest"] == (
        state.reentry_audit_ledger.digest().value
    )


def test_control_plane_state_tracks_reentry_audit_ledger() -> None:
    ledger = _reentry_audit_ledger()
    state = HumanReviewControlPlaneState.create().with_reentry_audit_ledger(ledger)

    assert state.reentry_audit_count() == 1
    assert state.has_recorded_reentry_audits() is True
    assert state.latest_reentry_audit_digest() == ledger.latest().digest().value
    assert state.to_payload()["reentry_audit_count"] == 1
    assert state.to_payload()["latest_reentry_audit_digest"] == (ledger.latest().digest().value)


def test_control_plane_status_tracks_reentry_audit_counts() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_audit_ledger(_reentry_audit_ledger())

    status = HumanReviewControlPlaneStatus.from_state(state)

    assert status.reentry_audit_count == 1
    assert status.passed_reentry_audit_count == 1
    assert status.failed_reentry_audit_count == 0
    assert status.waiting_reentry_audit_count == 0
    assert status.blocking_reentry_audit_count == 0
    assert status.has_reentry_audit() is True
    assert status.has_passed_reentry_audit() is True
    assert status.has_failed_reentry_audit() is False
    assert status.has_blocking_reentry_audit() is False
    assert status.to_payload()["reentry_audit_count"] == 1


def test_control_plane_snapshot_includes_reentry_audit_ledger_digest() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_audit_ledger(_reentry_audit_ledger())

    snapshot = HumanReviewControlPlaneSnapshot.from_state(state)
    payload = snapshot.to_payload()

    assert payload["reentry_audit_ledger_digest"] == (state.reentry_audit_ledger.digest().value)
    assert payload["status"]["reentry_audit_count"] == 1


def test_control_plane_snapshot_rejects_reentry_audit_count_mismatch() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_audit_ledger(_reentry_audit_ledger())
    good_status = HumanReviewControlPlaneStatus.from_state(state)
    bad_status = HumanReviewControlPlaneStatus(
        state_digest=state.digest(),
        handoff_count=good_status.handoff_count,
        decision_count=good_status.decision_count,
        resume_count=good_status.resume_count,
        reentry_count=good_status.reentry_count,
        reentry_audit_count=0,
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
    )

    with pytest.raises(FoundationError, match="reentry audit count mismatch"):
        HumanReviewControlPlaneSnapshot(
            state=state,
            status=bad_status,
        ).require_consistent()
