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
from ix_sally.human_review_reentry_ledger import (
    HumanReviewReentryLedger,
    HumanReviewReentryLedgerEntry,
)
from ix_sally.orchestration_loop import StageLoopStopReason
from ix_sally.stage_readiness import RunStage


def _digest(label: str) -> DigestRecord:
    return DigestRecord.from_payload({"record": label})


def _reentry_ledger() -> HumanReviewReentryLedger:
    entry = HumanReviewReentryLedgerEntry.create(
        sequence=1,
        reentry_receipt_digest=_digest("reentry-receipt"),
        resume_operation_digest=_digest("resume-operation"),
        resume_certificate_digest=_digest("resume-certificate"),
        control_plane_digest=_digest("control-plane"),
        before_state_digest=_digest("before-state"),
        after_state_digest=_digest("after-state"),
        loop_digest=_digest("loop"),
        final_stage=RunStage.FORGE_RESULT_PROCESSING,
        stop_reason=StageLoopStopReason.EXTERNAL_INPUT_REQUIRED,
        executed_steps=3,
        status=HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT,
    )
    return HumanReviewReentryLedger.create(()).append(entry)


def test_control_plane_state_defaults_to_empty_reentry_ledger() -> None:
    state = HumanReviewControlPlaneState.create()

    assert state.reentry_count() == 0
    assert state.has_recorded_reentries() is False
    assert state.latest_reentry_digest() is None
    assert state.to_payload()["reentry_ledger_digest"] == state.reentry_ledger.digest().value


def test_control_plane_state_tracks_reentry_ledger() -> None:
    ledger = _reentry_ledger()
    state = HumanReviewControlPlaneState.create().with_reentry_ledger(ledger)

    assert state.reentry_count() == 1
    assert state.has_recorded_reentries() is True
    assert state.latest_reentry_digest() == ledger.latest().digest().value
    assert state.to_payload()["reentry_count"] == 1
    assert state.to_payload()["latest_reentry_digest"] == ledger.latest().digest().value


def test_control_plane_status_tracks_successful_reentry() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_ledger(_reentry_ledger())

    status = HumanReviewControlPlaneStatus.from_state(state)

    assert status.reentry_count == 1
    assert status.completed_reentry_count == 1
    assert status.waiting_reentry_count == 1
    assert status.has_successful_reentry() is True
    assert status.is_waiting_after_reentry() is True
    assert status.to_payload()["reentry_count"] == 1


def test_control_plane_snapshot_includes_reentry_ledger_digest() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_ledger(_reentry_ledger())

    snapshot = HumanReviewControlPlaneSnapshot.from_state(state)
    payload = snapshot.to_payload()

    assert payload["reentry_ledger_digest"] == state.reentry_ledger.digest().value
    assert payload["status"]["reentry_count"] == 1


def test_control_plane_snapshot_rejects_reentry_count_mismatch() -> None:
    state = HumanReviewControlPlaneState.create().with_reentry_ledger(_reentry_ledger())
    good_status = HumanReviewControlPlaneStatus.from_state(state)
    bad_status = HumanReviewControlPlaneStatus(
        state_digest=state.digest(),
        handoff_count=good_status.handoff_count,
        decision_count=good_status.decision_count,
        resume_count=good_status.resume_count,
        reentry_count=0,
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
    )

    with pytest.raises(FoundationError, match="reentry count mismatch"):
        HumanReviewControlPlaneSnapshot(state=state, status=bad_status).require_consistent()
