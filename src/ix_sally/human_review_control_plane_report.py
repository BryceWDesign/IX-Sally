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
        }.items():
            if value < 0:
                raise FoundationError(
                    f"human-review control-plane report {field_name} must not be negative"
                )

        if approved_decision_count + rejected_decision_count + deferred_decision_count > decision_count:
            raise FoundationError(
                "human-review control-plane report decision subtotals exceed decision_count"
            )
        if cleared_resume_count > resume_count:
            raise FoundationError(
                "human-review control-plane report cleared_resume_count exceeds resume_count"
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
            latest_handoff_digest=control_plane_snapshot.state.latest_handoff_digest(),
            latest_decision_digest=control_plane_snapshot.state.latest_decision_digest(),
            latest_resume_digest=control_plane_snapshot.state.latest_resume_digest(),
        )

    def requires_operator_attention(self) -> bool:
        """Return whether this report indicates unresolved operator work."""
        return self.status in {
            HumanReviewControlPlaneReportStatus.HANDOFF_OPEN,
            HumanReviewControlPlaneReportStatus.DECISION_OPEN,
            HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED,
            HumanReviewControlPlaneReportStatus.DEFERRAL_OPEN,
        }

    def cleared_resume_recorded(self) -> bool:
        """Return whether at least one cleared resume has been recorded."""
        return self.status is HumanReviewControlPlaneReportStatus.RESUME_RECORDED

    def has_handoff(self) -> bool:
        """Return whether a handoff has been recorded."""
        return self.handoff_count > 0

    def has_decision(self) -> bool:
        """Return whether a decision has been recorded."""
        return self.decision_count > 0

    def has_resume(self) -> bool:
        """Return whether a resume has been recorded."""
        return self.resume_count > 0

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
            "approved_decision_count": self.approved_decision_count,
            "rejected_decision_count": self.rejected_decision_count,
            "deferred_decision_count": self.deferred_decision_count,
            "cleared_resume_count": self.cleared_resume_count,
            "latest_handoff_digest": self.latest_handoff_digest,
            "latest_decision_digest": self.latest_decision_digest,
            "latest_resume_digest": self.latest_resume_digest,
            "requires_operator_attention": self.requires_operator_attention(),
            "cleared_resume_recorded": self.cleared_resume_recorded(),
            "has_handoff": self.has_handoff(),
            "has_decision": self.has_decision(),
            "has_resume": self.has_resume(),
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
            control_plane_snapshot=HumanReviewControlPlaneSnapshot.from_state(control_plane),
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
