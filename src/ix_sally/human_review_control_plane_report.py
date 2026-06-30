"""Receipt-grade reports for IX-Sally human-review control-plane state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_control_plane import (
    HumanReviewControlPlaneSnapshot,
    HumanReviewControlPlaneState,
    HumanReviewControlPlaneStatus,
)
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


class HumanReviewControlPlaneReportStatus(StrEnum):
    """Operator-facing status for human-review control-plane reporting."""

    NO_HANDOFFS = "no_handoffs"
    HANDOFF_OPEN = "handoff_open"
    DECISION_OPEN = "decision_open"
    RESUME_RECORDED = "resume_recorded"
    REENTRY_RECORDED = "reentry_recorded"
    REENTRY_WAITING_FOR_EXTERNAL_INPUT = "reentry_waiting_for_external_input"
    REENTRY_AUDIT_PASSED = "reentry_audit_passed"
    REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT = (
        "reentry_audit_waiting_for_external_input"
    )
    REENTRY_AUDIT_FAILED = "reentry_audit_failed"
    AUDITED_REENTRY_ACCEPTED = "audited_reentry_accepted"
    AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT = (
        "audited_reentry_waiting_for_external_input"
    )
    AUDITED_REENTRY_FAILED = "audited_reentry_failed"
    COMPLETE_REENTRY_ACCEPTED = "complete_reentry_accepted"
    COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT = (
        "complete_reentry_waiting_for_external_input"
    )
    COMPLETE_REENTRY_FAILED = "complete_reentry_failed"
    COMPLETE_REENTRY_CLOSEOUT_ACCEPTED = "complete_reentry_closeout_accepted"
    COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT = (
        "complete_reentry_closeout_waiting_for_external_input"
    )
    COMPLETE_REENTRY_CLOSEOUT_BLOCKED = "complete_reentry_closeout_blocked"
    REJECTION_BLOCKED = "rejection_blocked"
    DEFERRAL_OPEN = "deferral_open"


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneReport:
    """Report tying run stage, human-review ledgers, and operator status together."""

    report_id: CanonicalKey
    run_state_digest: DigestRecord
    run_snapshot_digest: DigestRecord
    control_plane_snapshot_digest: DigestRecord
    control_plane_status_digest: DigestRecord
    run_stage: RunStage
    status: HumanReviewControlPlaneReportStatus
    rationale: str
    handoff_count: int
    decision_count: int
    resume_count: int
    approved_decision_count: int
    rejected_decision_count: int
    deferred_decision_count: int
    cleared_resume_count: int
    latest_handoff_digest: str | None
    latest_decision_digest: str | None
    latest_resume_digest: str | None
    reentry_count: int = 0
    completed_reentry_count: int = 0
    waiting_reentry_count: int = 0
    latest_reentry_digest: str | None = None
    reentry_audit_count: int = 0
    passed_reentry_audit_count: int = 0
    failed_reentry_audit_count: int = 0
    waiting_reentry_audit_count: int = 0
    blocking_reentry_audit_count: int = 0
    latest_reentry_audit_digest: str | None = None
    audited_reentry_count: int = 0
    accepted_audited_reentry_count: int = 0
    failed_audited_reentry_count: int = 0
    waiting_audited_reentry_count: int = 0
    operator_attention_audited_reentry_count: int = 0
    changed_state_audited_reentry_count: int = 0
    latest_audited_reentry_digest: str | None = None
    complete_reentry_count: int = 0
    accepted_complete_reentry_count: int = 0
    failed_complete_reentry_count: int = 0
    waiting_complete_reentry_count: int = 0
    operator_attention_complete_reentry_count: int = 0
    changed_state_complete_reentry_count: int = 0
    latest_complete_reentry_digest: str | None = None
    complete_reentry_closeout_count: int = 0
    accepted_complete_reentry_closeout_count: int = 0
    waiting_complete_reentry_closeout_count: int = 0
    blocked_complete_reentry_closeout_count: int = 0
    blocking_finding_complete_reentry_closeout_count: int = 0
    latest_complete_reentry_closeout_digest: str | None = None

    @classmethod
    def create(
        cls,
        *,
        run_state_digest: DigestRecord,
        run_snapshot_digest: DigestRecord,
        control_plane_snapshot_digest: DigestRecord,
        control_plane_status_digest: DigestRecord,
        run_stage: RunStage,
        status: HumanReviewControlPlaneReportStatus,
        rationale: str,
        handoff_count: int,
        decision_count: int,
        resume_count: int,
        approved_decision_count: int,
        rejected_decision_count: int,
        deferred_decision_count: int,
        cleared_resume_count: int,
        latest_handoff_digest: str | None,
        latest_decision_digest: str | None,
        latest_resume_digest: str | None,
        reentry_count: int = 0,
        completed_reentry_count: int = 0,
        waiting_reentry_count: int = 0,
        latest_reentry_digest: str | None = None,
        reentry_audit_count: int = 0,
        passed_reentry_audit_count: int = 0,
        failed_reentry_audit_count: int = 0,
        waiting_reentry_audit_count: int = 0,
        blocking_reentry_audit_count: int = 0,
        latest_reentry_audit_digest: str | None = None,
        audited_reentry_count: int = 0,
        accepted_audited_reentry_count: int = 0,
        failed_audited_reentry_count: int = 0,
        waiting_audited_reentry_count: int = 0,
        operator_attention_audited_reentry_count: int = 0,
        changed_state_audited_reentry_count: int = 0,
        latest_audited_reentry_digest: str | None = None,
        complete_reentry_count: int = 0,
        accepted_complete_reentry_count: int = 0,
        failed_complete_reentry_count: int = 0,
        waiting_complete_reentry_count: int = 0,
        operator_attention_complete_reentry_count: int = 0,
        changed_state_complete_reentry_count: int = 0,
        latest_complete_reentry_digest: str | None = None,
        complete_reentry_closeout_count: int = 0,
        accepted_complete_reentry_closeout_count: int = 0,
        waiting_complete_reentry_closeout_count: int = 0,
        blocked_complete_reentry_closeout_count: int = 0,
        blocking_finding_complete_reentry_closeout_count: int = 0,
        latest_complete_reentry_closeout_digest: str | None = None,
        report_id: CanonicalKey | None = None,
    ) -> HumanReviewControlPlaneReport:
        """Create a normalized human-review control-plane report."""
        for field_name, value in {
            "handoff_count": handoff_count,
            "decision_count": decision_count,
            "resume_count": resume_count,
            "approved_decision_count": approved_decision_count,
            "rejected_decision_count": rejected_decision_count,
            "deferred_decision_count": deferred_decision_count,
            "cleared_resume_count": cleared_resume_count,
            "reentry_count": reentry_count,
            "completed_reentry_count": completed_reentry_count,
            "waiting_reentry_count": waiting_reentry_count,
            "reentry_audit_count": reentry_audit_count,
            "passed_reentry_audit_count": passed_reentry_audit_count,
            "failed_reentry_audit_count": failed_reentry_audit_count,
            "waiting_reentry_audit_count": waiting_reentry_audit_count,
            "blocking_reentry_audit_count": blocking_reentry_audit_count,
            "audited_reentry_count": audited_reentry_count,
            "accepted_audited_reentry_count": accepted_audited_reentry_count,
            "failed_audited_reentry_count": failed_audited_reentry_count,
            "waiting_audited_reentry_count": waiting_audited_reentry_count,
            "operator_attention_audited_reentry_count": (
                operator_attention_audited_reentry_count
            ),
            "changed_state_audited_reentry_count": (
                changed_state_audited_reentry_count
            ),
            "complete_reentry_count": complete_reentry_count,
            "accepted_complete_reentry_count": accepted_complete_reentry_count,
            "failed_complete_reentry_count": failed_complete_reentry_count,
            "waiting_complete_reentry_count": waiting_complete_reentry_count,
            "operator_attention_complete_reentry_count": (
                operator_attention_complete_reentry_count
            ),
            "changed_state_complete_reentry_count": (
                changed_state_complete_reentry_count
            ),
            "complete_reentry_closeout_count": complete_reentry_closeout_count,
            "accepted_complete_reentry_closeout_count": (
                accepted_complete_reentry_closeout_count
            ),
            "waiting_complete_reentry_closeout_count": (
                waiting_complete_reentry_closeout_count
            ),
            "blocked_complete_reentry_closeout_count": (
                blocked_complete_reentry_closeout_count
            ),
            "blocking_finding_complete_reentry_closeout_count": (
                blocking_finding_complete_reentry_closeout_count
            ),
        }.items():
            if value < 0:
                raise FoundationError(
                    f"human-review control-plane report {field_name} "
                    "must not be negative"
                )

        if (
            approved_decision_count + rejected_decision_count + deferred_decision_count
            > decision_count
        ):
            raise FoundationError(
                "human-review control-plane report decision subtotals exceed "
                "decision_count"
            )
        if cleared_resume_count > resume_count:
            raise FoundationError(
                "human-review control-plane report cleared_resume_count exceeds "
                "resume_count"
            )
        if completed_reentry_count > reentry_count:
            raise FoundationError(
                "human-review control-plane report completed_reentry_count exceeds "
                "reentry_count"
            )
        if waiting_reentry_count > reentry_count:
            raise FoundationError(
                "human-review control-plane report waiting_reentry_count exceeds "
                "reentry_count"
            )
        if (
            passed_reentry_audit_count
            + failed_reentry_audit_count
            + waiting_reentry_audit_count
            > reentry_audit_count
        ):
            raise FoundationError(
                "human-review control-plane report reentry audit subtotals exceed "
                "reentry_audit_count"
            )
        if blocking_reentry_audit_count > reentry_audit_count:
            raise FoundationError(
                "human-review control-plane report blocking_reentry_audit_count "
                "exceeds reentry_audit_count"
            )
        if (
            accepted_audited_reentry_count
            + failed_audited_reentry_count
            > audited_reentry_count
        ):
            raise FoundationError(
                "human-review control-plane report audited reentry subtotals exceed "
                "audited_reentry_count"
            )
        if waiting_audited_reentry_count > accepted_audited_reentry_count:
            raise FoundationError(
                "human-review control-plane report waiting_audited_reentry_count "
                "exceeds accepted_audited_reentry_count"
            )
        if operator_attention_audited_reentry_count > audited_reentry_count:
            raise FoundationError(
                "human-review control-plane report "
                "operator_attention_audited_reentry_count exceeds audited_reentry_count"
            )
        if changed_state_audited_reentry_count > audited_reentry_count:
            raise FoundationError(
                "human-review control-plane report "
                "changed_state_audited_reentry_count exceeds audited_reentry_count"
            )
        if (
            accepted_complete_reentry_count + failed_complete_reentry_count
            > complete_reentry_count
        ):
            raise FoundationError(
                "human-review control-plane report complete reentry subtotals "
                "exceed complete_reentry_count"
            )
        if waiting_complete_reentry_count > accepted_complete_reentry_count:
            raise FoundationError(
                "human-review control-plane report waiting_complete_reentry_count "
                "exceeds accepted_complete_reentry_count"
            )
        if operator_attention_complete_reentry_count > complete_reentry_count:
            raise FoundationError(
                "human-review control-plane report "
                "operator_attention_complete_reentry_count exceeds "
                "complete_reentry_count"
            )
        if changed_state_complete_reentry_count > complete_reentry_count:
            raise FoundationError(
                "human-review control-plane report "
                "changed_state_complete_reentry_count exceeds complete_reentry_count"
            )
        if (
            accepted_complete_reentry_closeout_count
            + waiting_complete_reentry_closeout_count
            + blocked_complete_reentry_closeout_count
            > complete_reentry_closeout_count
        ):
            raise FoundationError(
                "human-review control-plane report complete closeout subtotals "
                "exceed complete_reentry_closeout_count"
            )
        if (
            blocking_finding_complete_reentry_closeout_count
            > complete_reentry_closeout_count
        ):
            raise FoundationError(
                "human-review control-plane report complete closeout blocking "
                "finding count exceeds complete_reentry_closeout_count"
            )

        run_state_digest.require_algorithm("sha256")
        run_snapshot_digest.require_algorithm("sha256")
        control_plane_snapshot_digest.require_algorithm("sha256")
        control_plane_status_digest.require_algorithm("sha256")
        normalized_rationale = require_text(rationale, field_name="rationale")

        return cls(
            report_id=report_id
            or CanonicalKey.from_text(
                f"human-review-control-plane-report-{run_state_digest.value[:16]}-"
                f"{control_plane_snapshot_digest.value[:16]}-{status.value}",
                field_name="report_id",
            ),
            run_state_digest=run_state_digest,
            run_snapshot_digest=run_snapshot_digest,
            control_plane_snapshot_digest=control_plane_snapshot_digest,
            control_plane_status_digest=control_plane_status_digest,
            run_stage=run_stage,
            status=status,
            rationale=normalized_rationale,
            handoff_count=handoff_count,
            decision_count=decision_count,
            resume_count=resume_count,
            approved_decision_count=approved_decision_count,
            rejected_decision_count=rejected_decision_count,
            deferred_decision_count=deferred_decision_count,
            cleared_resume_count=cleared_resume_count,
            latest_handoff_digest=latest_handoff_digest,
            latest_decision_digest=latest_decision_digest,
            latest_resume_digest=latest_resume_digest,
            reentry_count=reentry_count,
            completed_reentry_count=completed_reentry_count,
            waiting_reentry_count=waiting_reentry_count,
            latest_reentry_digest=latest_reentry_digest,
            reentry_audit_count=reentry_audit_count,
            passed_reentry_audit_count=passed_reentry_audit_count,
            failed_reentry_audit_count=failed_reentry_audit_count,
            waiting_reentry_audit_count=waiting_reentry_audit_count,
            blocking_reentry_audit_count=blocking_reentry_audit_count,
            latest_reentry_audit_digest=latest_reentry_audit_digest,
            audited_reentry_count=audited_reentry_count,
            accepted_audited_reentry_count=accepted_audited_reentry_count,
            failed_audited_reentry_count=failed_audited_reentry_count,
            waiting_audited_reentry_count=waiting_audited_reentry_count,
            operator_attention_audited_reentry_count=(
                operator_attention_audited_reentry_count
            ),
            changed_state_audited_reentry_count=(
                changed_state_audited_reentry_count
            ),
            latest_audited_reentry_digest=latest_audited_reentry_digest,
            complete_reentry_count=complete_reentry_count,
            accepted_complete_reentry_count=accepted_complete_reentry_count,
            failed_complete_reentry_count=failed_complete_reentry_count,
            waiting_complete_reentry_count=waiting_complete_reentry_count,
            operator_attention_complete_reentry_count=(
                operator_attention_complete_reentry_count
            ),
            changed_state_complete_reentry_count=changed_state_complete_reentry_count,
            latest_complete_reentry_digest=latest_complete_reentry_digest,
            complete_reentry_closeout_count=complete_reentry_closeout_count,
            accepted_complete_reentry_closeout_count=(
                accepted_complete_reentry_closeout_count
            ),
            waiting_complete_reentry_closeout_count=(
                waiting_complete_reentry_closeout_count
            ),
            blocked_complete_reentry_closeout_count=(
                blocked_complete_reentry_closeout_count
            ),
            blocking_finding_complete_reentry_closeout_count=(
                blocking_finding_complete_reentry_closeout_count
            ),
            latest_complete_reentry_closeout_digest=(
                latest_complete_reentry_closeout_digest
            ),
        )

    @classmethod
    def from_snapshots(
        cls,
        *,
        run_snapshot: RunStageSnapshot,
        control_plane_snapshot: HumanReviewControlPlaneSnapshot,
    ) -> HumanReviewControlPlaneReport:
        """Create a report from run and human-review control-plane snapshots."""
        control_plane_snapshot.require_consistent()
        control_status = control_plane_snapshot.status
        status, rationale = _select_report_status(control_status)

        return cls.create(
            run_state_digest=run_snapshot.state_digest,
            run_snapshot_digest=run_snapshot.digest(),
            control_plane_snapshot_digest=control_plane_snapshot.digest(),
            control_plane_status_digest=control_status.digest(),
            run_stage=run_snapshot.stage,
            status=status,
            rationale=rationale,
            handoff_count=control_status.handoff_count,
            decision_count=control_status.decision_count,
            resume_count=control_status.resume_count,
            approved_decision_count=control_status.approved_decision_count,
            rejected_decision_count=control_status.rejected_decision_count,
            deferred_decision_count=control_status.deferred_decision_count,
            cleared_resume_count=control_status.cleared_resume_count,
            reentry_count=control_status.reentry_count,
            completed_reentry_count=control_status.completed_reentry_count,
            waiting_reentry_count=control_status.waiting_reentry_count,
            reentry_audit_count=control_status.reentry_audit_count,
            passed_reentry_audit_count=control_status.passed_reentry_audit_count,
            failed_reentry_audit_count=control_status.failed_reentry_audit_count,
            waiting_reentry_audit_count=control_status.waiting_reentry_audit_count,
            blocking_reentry_audit_count=(
                control_status.blocking_reentry_audit_count
            ),
            audited_reentry_count=control_status.audited_reentry_count,
            accepted_audited_reentry_count=(
                control_status.accepted_audited_reentry_count
            ),
            failed_audited_reentry_count=(
                control_status.failed_audited_reentry_count
            ),
            waiting_audited_reentry_count=(
                control_status.waiting_audited_reentry_count
            ),
            operator_attention_audited_reentry_count=(
                control_status.operator_attention_audited_reentry_count
            ),
            changed_state_audited_reentry_count=(
                control_status.changed_state_audited_reentry_count
            ),
            complete_reentry_count=control_status.complete_reentry_count,
            accepted_complete_reentry_count=(
                control_status.accepted_complete_reentry_count
            ),
            failed_complete_reentry_count=control_status.failed_complete_reentry_count,
            waiting_complete_reentry_count=(
                control_status.waiting_complete_reentry_count
            ),
            operator_attention_complete_reentry_count=(
                control_status.operator_attention_complete_reentry_count
            ),
            changed_state_complete_reentry_count=(
                control_status.changed_state_complete_reentry_count
            ),
            complete_reentry_closeout_count=(
                control_status.complete_reentry_closeout_count
            ),
            accepted_complete_reentry_closeout_count=(
                control_status.accepted_complete_reentry_closeout_count
            ),
            waiting_complete_reentry_closeout_count=(
                control_status.waiting_complete_reentry_closeout_count
            ),
            blocked_complete_reentry_closeout_count=(
                control_status.blocked_complete_reentry_closeout_count
            ),
            blocking_finding_complete_reentry_closeout_count=(
                control_status.blocking_finding_complete_reentry_closeout_count
            ),
            latest_handoff_digest=control_plane_snapshot.state.latest_handoff_digest(),
            latest_decision_digest=control_plane_snapshot.state.latest_decision_digest(),
            latest_resume_digest=control_plane_snapshot.state.latest_resume_digest(),
            latest_reentry_digest=control_plane_snapshot.state.latest_reentry_digest(),
            latest_reentry_audit_digest=(
                control_plane_snapshot.state.latest_reentry_audit_digest()
            ),
            latest_audited_reentry_digest=(
                control_plane_snapshot.state.latest_audited_reentry_digest()
            ),
            latest_complete_reentry_digest=(
                control_plane_snapshot.state.latest_complete_reentry_digest()
            ),
            latest_complete_reentry_closeout_digest=(
                control_plane_snapshot.state.latest_complete_reentry_closeout_digest()
            ),
        )

    def requires_operator_attention(self) -> bool:
        """Return whether this report indicates unresolved operator work."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.HANDOFF_OPEN,
            HumanReviewControlPlaneReportStatus.DECISION_OPEN,
            HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED,
            HumanReviewControlPlaneReportStatus.DEFERRAL_OPEN,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_FAILED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
        }

    def cleared_resume_recorded(self) -> bool:
        """Return whether at least one cleared resume has been recorded."""
        return self.status is HumanReviewControlPlaneReportStatus.RESUME_RECORDED

    def reentry_recorded(self) -> bool:
        """Return whether at least one post-review reentry has been recorded."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.REENTRY_RECORDED,
            HumanReviewControlPlaneReportStatus.REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_FAILED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
        }

    def waiting_after_reentry(self) -> bool:
        """Return whether reentry advanced and then stopped for external input."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT,
        }

    def reentry_audit_recorded(self) -> bool:
        """Return whether at least one reentry audit has been recorded."""
        return self.reentry_audit_count > 0

    def reentry_audit_passed(self) -> bool:
        """Return whether the report status indicates a passed reentry audit."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED,
        }

    def reentry_audit_failed(self) -> bool:
        """Return whether the report status indicates a failed reentry audit."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_FAILED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
        }

    def audited_reentry_recorded(self) -> bool:
        """Return whether at least one audited reentry has been recorded."""
        return self.audited_reentry_count > 0

    def audited_reentry_accepted(self) -> bool:
        """Return whether the report status indicates accepted audited reentry."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT,
        }

    def audited_reentry_failed(self) -> bool:
        """Return whether the report status indicates failed audited reentry."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
        }

    def complete_reentry_recorded(self) -> bool:
        """Return whether at least one complete reentry has been recorded."""
        return self.complete_reentry_count > 0

    def complete_reentry_accepted(self) -> bool:
        """Return whether the report status indicates accepted complete reentry."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT,
        }

    def complete_reentry_failed(self) -> bool:
        """Return whether the report status indicates failed complete reentry."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
        }

    def complete_reentry_closeout_recorded(self) -> bool:
        """Return whether at least one complete reentry closeout is recorded."""
        return self.complete_reentry_closeout_count > 0

    def complete_reentry_closeout_accepted(self) -> bool:
        """Return whether complete reentry closeout has accepted status."""
        return self.status is (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED
        )

    def complete_reentry_closeout_blocked(self) -> bool:
        """Return whether complete reentry closeout has blocked status."""
        return self.status is (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED
        )

    def has_handoff(self) -> bool:
        """Return whether a handoff has been recorded."""
        return self.handoff_count > 0

    def has_decision(self) -> bool:
        """Return whether a decision has been recorded."""
        return self.decision_count > 0

    def has_resume(self) -> bool:
        """Return whether a resume has been recorded."""
        return self.resume_count > 0

    def has_reentry(self) -> bool:
        """Return whether a reentry has been recorded."""
        return self.reentry_count > 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible control-plane report."""
        return {
            "report_id": self.report_id.value,
            "run_state_digest": {
                "algorithm": self.run_state_digest.algorithm,
                "value": self.run_state_digest.value,
            },
            "run_snapshot_digest": {
                "algorithm": self.run_snapshot_digest.algorithm,
                "value": self.run_snapshot_digest.value,
            },
            "control_plane_snapshot_digest": {
                "algorithm": self.control_plane_snapshot_digest.algorithm,
                "value": self.control_plane_snapshot_digest.value,
            },
            "control_plane_status_digest": {
                "algorithm": self.control_plane_status_digest.algorithm,
                "value": self.control_plane_status_digest.value,
            },
            "run_stage": self.run_stage.value,
            "status": self.status.value,
            "rationale": self.rationale,
            "handoff_count": self.handoff_count,
            "decision_count": self.decision_count,
            "resume_count": self.resume_count,
            "reentry_count": self.reentry_count,
            "reentry_audit_count": self.reentry_audit_count,
            "audited_reentry_count": self.audited_reentry_count,
            "complete_reentry_count": self.complete_reentry_count,
            "complete_reentry_closeout_count": self.complete_reentry_closeout_count,
            "approved_decision_count": self.approved_decision_count,
            "rejected_decision_count": self.rejected_decision_count,
            "deferred_decision_count": self.deferred_decision_count,
            "cleared_resume_count": self.cleared_resume_count,
            "completed_reentry_count": self.completed_reentry_count,
            "waiting_reentry_count": self.waiting_reentry_count,
            "passed_reentry_audit_count": self.passed_reentry_audit_count,
            "failed_reentry_audit_count": self.failed_reentry_audit_count,
            "waiting_reentry_audit_count": self.waiting_reentry_audit_count,
            "blocking_reentry_audit_count": self.blocking_reentry_audit_count,
            "accepted_audited_reentry_count": self.accepted_audited_reentry_count,
            "failed_audited_reentry_count": self.failed_audited_reentry_count,
            "waiting_audited_reentry_count": self.waiting_audited_reentry_count,
            "operator_attention_audited_reentry_count": (
                self.operator_attention_audited_reentry_count
            ),
            "changed_state_audited_reentry_count": (
                self.changed_state_audited_reentry_count
            ),
            "accepted_complete_reentry_count": self.accepted_complete_reentry_count,
            "failed_complete_reentry_count": self.failed_complete_reentry_count,
            "waiting_complete_reentry_count": self.waiting_complete_reentry_count,
            "operator_attention_complete_reentry_count": (
                self.operator_attention_complete_reentry_count
            ),
            "changed_state_complete_reentry_count": (
                self.changed_state_complete_reentry_count
            ),
            "accepted_complete_reentry_closeout_count": (
                self.accepted_complete_reentry_closeout_count
            ),
            "waiting_complete_reentry_closeout_count": (
                self.waiting_complete_reentry_closeout_count
            ),
            "blocked_complete_reentry_closeout_count": (
                self.blocked_complete_reentry_closeout_count
            ),
            "blocking_finding_complete_reentry_closeout_count": (
                self.blocking_finding_complete_reentry_closeout_count
            ),
            "latest_handoff_digest": self.latest_handoff_digest,
            "latest_decision_digest": self.latest_decision_digest,
            "latest_resume_digest": self.latest_resume_digest,
            "latest_reentry_digest": self.latest_reentry_digest,
            "latest_reentry_audit_digest": self.latest_reentry_audit_digest,
            "latest_audited_reentry_digest": self.latest_audited_reentry_digest,
            "latest_complete_reentry_digest": self.latest_complete_reentry_digest,
            "latest_complete_reentry_closeout_digest": (
                self.latest_complete_reentry_closeout_digest
            ),
            "requires_operator_attention": self.requires_operator_attention(),
            "cleared_resume_recorded": self.cleared_resume_recorded(),
            "reentry_recorded": self.reentry_recorded(),
            "waiting_after_reentry": self.waiting_after_reentry(),
            "reentry_audit_recorded": self.reentry_audit_recorded(),
            "reentry_audit_passed": self.reentry_audit_passed(),
            "reentry_audit_failed": self.reentry_audit_failed(),
            "audited_reentry_recorded": self.audited_reentry_recorded(),
            "audited_reentry_accepted": self.audited_reentry_accepted(),
            "audited_reentry_failed": self.audited_reentry_failed(),
            "complete_reentry_recorded": self.complete_reentry_recorded(),
            "complete_reentry_accepted": self.complete_reentry_accepted(),
            "complete_reentry_failed": self.complete_reentry_failed(),
            "complete_reentry_closeout_recorded": (
                self.complete_reentry_closeout_recorded()
            ),
            "complete_reentry_closeout_accepted": (
                self.complete_reentry_closeout_accepted()
            ),
            "complete_reentry_closeout_blocked": (
                self.complete_reentry_closeout_blocked()
            ),
            "has_handoff": self.has_handoff(),
            "has_decision": self.has_decision(),
            "has_resume": self.has_resume(),
            "has_reentry": self.has_reentry(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review control-plane report."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneReporter:
    """Builds human-review control-plane reports from current run and ledger state."""

    def report(
        self,
        *,
        run_state: NinefoldRunState,
        control_plane: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneReport:
        """Return a receipt-grade report for the current run and control-plane state."""
        return HumanReviewControlPlaneReport.from_snapshots(
            run_snapshot=RunStageSnapshot.from_state(run_state),
            control_plane_snapshot=HumanReviewControlPlaneSnapshot.from_state(
                control_plane
            ),
        )


def _select_report_status(
    status: HumanReviewControlPlaneStatus,
) -> tuple[HumanReviewControlPlaneReportStatus, str]:
    """Select a deterministic report status from control-plane status counts."""
    if status.has_rejections():
        return (
            HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED,
            "At least one human-review decision rejected a target.",
        )

    if status.has_deferrals():
        return (
            HumanReviewControlPlaneReportStatus.DEFERRAL_OPEN,
            "At least one human-review decision deferred a target.",
        )

    if (
        status.has_blocked_complete_reentry_closeout()
        or status.complete_reentry_closeout_has_blocking_findings()
    ):
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_BLOCKED,
            "A complete human-review reentry closeout is blocked.",
        )

    if status.is_waiting_after_complete_reentry_closeout():
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT,
            "A complete human-review reentry closeout is waiting externally.",
        )

    if status.has_accepted_complete_reentry_closeout():
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED,
            "Complete human-review reentry closeout was accepted and recorded.",
        )

    if (
        status.complete_reentry_requires_operator_attention()
        or status.has_failed_complete_reentry()
    ):
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_FAILED,
            "A complete human-review reentry requires operator attention.",
        )

    if status.is_waiting_after_complete_reentry():
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            "A complete human-review reentry is valid and waiting externally.",
        )

    if status.has_accepted_complete_reentry():
        return (
            HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED,
            "Complete human-review reentry was accepted and recorded.",
        )

    if (
        status.audited_reentry_requires_operator_attention()
        or status.has_failed_audited_reentry()
    ):
        return (
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_FAILED,
            "A fully audited human-review reentry requires operator attention.",
        )

    if status.is_waiting_after_audited_reentry():
        return (
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            "A fully audited human-review reentry is valid and waiting externally.",
        )

    if status.has_accepted_audited_reentry():
        return (
            HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            "Fully audited human-review reentry was accepted and recorded.",
        )

    if status.has_blocking_reentry_audit() or status.has_failed_reentry_audit():
        return (
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_FAILED,
            "A human-review reentry audit has blocking or failed findings.",
        )

    if status.is_waiting_after_reentry_audit():
        return (
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT,
            "Human-review reentry audit passed for a run waiting on external input.",
        )

    if status.has_passed_reentry_audit():
        return (
            HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED,
            "Human-review reentry audit passed and was recorded.",
        )

    if status.is_waiting_after_reentry():
        return (
            HumanReviewControlPlaneReportStatus.REENTRY_WAITING_FOR_EXTERNAL_INPUT,
            "Human-review reentry advanced the run and now awaits external input.",
        )

    if status.has_successful_reentry():
        return (
            HumanReviewControlPlaneReportStatus.REENTRY_RECORDED,
            "Human-review reentry advanced staged orchestration after clearance.",
        )

    if status.has_successful_resume():
        return (
            HumanReviewControlPlaneReportStatus.RESUME_RECORDED,
            "Human-review clearance has been certified and recorded for resume.",
        )

    if status.has_unresumed_decisions():
        return (
            HumanReviewControlPlaneReportStatus.DECISION_OPEN,
            "Human-review decisions exist but no cleared resume is recorded.",
        )

    if status.handoff_count > 0:
        return (
            HumanReviewControlPlaneReportStatus.HANDOFF_OPEN,
            "A human-review handoff exists and awaits operator decision or clearance.",
        )

    return (
        HumanReviewControlPlaneReportStatus.NO_HANDOFFS,
        "No human-review handoff has been recorded.",
    )
