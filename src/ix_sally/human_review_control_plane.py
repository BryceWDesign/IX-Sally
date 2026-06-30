"""Control-plane state for IX-Sally human-review ledgers."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle_ledger import HumanReviewBundleLedger
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_resume_ledger import HumanReviewResumeLedger
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneState:
    """Immutable aggregate of human-review handoff, decision, and resume ledgers."""

    handoff_ledger: HumanReviewBundleLedger
    decision_ledger: HumanReviewDecisionLedger
    resume_ledger: HumanReviewResumeLedger

    @classmethod
    def create(
        cls,
        *,
        handoff_ledger: HumanReviewBundleLedger | None = None,
        decision_ledger: HumanReviewDecisionLedger | None = None,
        resume_ledger: HumanReviewResumeLedger | None = None,
    ) -> HumanReviewControlPlaneState:
        """Create a human-review control-plane state with empty ledgers by default."""
        return cls(
            handoff_ledger=handoff_ledger or HumanReviewBundleLedger.create(()),
            decision_ledger=decision_ledger or HumanReviewDecisionLedger.create(()),
            resume_ledger=resume_ledger or HumanReviewResumeLedger.create(()),
        )

    def with_handoff_ledger(
        self,
        handoff_ledger: HumanReviewBundleLedger,
    ) -> HumanReviewControlPlaneState:
        """Return a new control-plane state with an updated handoff ledger."""
        return HumanReviewControlPlaneState.create(
            handoff_ledger=handoff_ledger,
            decision_ledger=self.decision_ledger,
            resume_ledger=self.resume_ledger,
        )

    def with_decision_ledger(
        self,
        decision_ledger: HumanReviewDecisionLedger,
    ) -> HumanReviewControlPlaneState:
        """Return a new control-plane state with an updated decision ledger."""
        return HumanReviewControlPlaneState.create(
            handoff_ledger=self.handoff_ledger,
            decision_ledger=decision_ledger,
            resume_ledger=self.resume_ledger,
        )

    def with_resume_ledger(
        self,
        resume_ledger: HumanReviewResumeLedger,
    ) -> HumanReviewControlPlaneState:
        """Return a new control-plane state with an updated resume ledger."""
        return HumanReviewControlPlaneState.create(
            handoff_ledger=self.handoff_ledger,
            decision_ledger=self.decision_ledger,
            resume_ledger=resume_ledger,
        )

    def handoff_count(self) -> int:
        """Return how many human-review handoffs have been recorded."""
        return len(self.handoff_ledger.entries)

    def decision_count(self) -> int:
        """Return how many human-review decisions have been recorded."""
        return len(self.decision_ledger.entries)

    def resume_count(self) -> int:
        """Return how many human-review resumes have been recorded."""
        return len(self.resume_ledger.entries)

    def has_active_handoffs(self) -> bool:
        """Return whether at least one human-review handoff has been recorded."""
        return self.handoff_count() > 0

    def has_recorded_decisions(self) -> bool:
        """Return whether at least one human-review decision has been recorded."""
        return self.decision_count() > 0

    def has_recorded_resumes(self) -> bool:
        """Return whether at least one human-review resume has been recorded."""
        return self.resume_count() > 0

    def latest_handoff_digest(self) -> str | None:
        """Return the latest human-review handoff entry digest, if present."""
        latest = self.handoff_ledger.latest()
        return latest.digest().value if latest is not None else None

    def latest_decision_digest(self) -> str | None:
        """Return the latest human-review decision entry digest, if present."""
        latest = self.decision_ledger.latest()
        return latest.digest().value if latest is not None else None

    def latest_resume_digest(self) -> str | None:
        """Return the latest human-review resume entry digest, if present."""
        latest = self.resume_ledger.latest()
        return latest.digest().value if latest is not None else None

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible control-plane state payload."""
        return {
            "handoff_ledger_digest": self.handoff_ledger.digest().value,
            "decision_ledger_digest": self.decision_ledger.digest().value,
            "resume_ledger_digest": self.resume_ledger.digest().value,
            "handoff_count": self.handoff_count(),
            "decision_count": self.decision_count(),
            "resume_count": self.resume_count(),
            "has_active_handoffs": self.has_active_handoffs(),
            "has_recorded_decisions": self.has_recorded_decisions(),
            "has_recorded_resumes": self.has_recorded_resumes(),
            "latest_handoff_digest": self.latest_handoff_digest(),
            "latest_decision_digest": self.latest_decision_digest(),
            "latest_resume_digest": self.latest_resume_digest(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this control-plane state."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneStatus:
    """Status summary for a human-review control-plane state."""

    state_digest: DigestRecord
    handoff_count: int
    decision_count: int
    resume_count: int
    approved_decision_count: int
    rejected_decision_count: int
    deferred_decision_count: int
    cleared_resume_count: int
    execution_planning_resume_count: int

    @classmethod
    def from_state(
        cls,
        state: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneStatus:
        """Create a status summary from human-review control-plane state."""
        return cls(
            state_digest=state.digest(),
            handoff_count=state.handoff_count(),
            decision_count=state.decision_count(),
            resume_count=state.resume_count(),
            approved_decision_count=len(state.decision_ledger.approved_entries()),
            rejected_decision_count=len(state.decision_ledger.rejected_entries()),
            deferred_decision_count=len(state.decision_ledger.deferred_entries()),
            cleared_resume_count=len(state.resume_ledger.cleared_entries()),
            execution_planning_resume_count=len(
                state.resume_ledger.entries_for_stage(RunStage.EXECUTION_PLANNING)
            ),
        )

    def has_unresumed_decisions(self) -> bool:
        """Return whether decisions exist without at least one cleared resume."""
        return self.decision_count > 0 and self.resume_count == 0

    def has_rejections(self) -> bool:
        """Return whether any human-review decision rejected a target."""
        return self.rejected_decision_count > 0

    def has_deferrals(self) -> bool:
        """Return whether any human-review decision deferred a target."""
        return self.deferred_decision_count > 0

    def has_successful_resume(self) -> bool:
        """Return whether at least one cleared resume has been recorded."""
        return self.cleared_resume_count > 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible control-plane status payload."""
        return {
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "handoff_count": self.handoff_count,
            "decision_count": self.decision_count,
            "resume_count": self.resume_count,
            "approved_decision_count": self.approved_decision_count,
            "rejected_decision_count": self.rejected_decision_count,
            "deferred_decision_count": self.deferred_decision_count,
            "cleared_resume_count": self.cleared_resume_count,
            "execution_planning_resume_count": self.execution_planning_resume_count,
            "has_unresumed_decisions": self.has_unresumed_decisions(),
            "has_rejections": self.has_rejections(),
            "has_deferrals": self.has_deferrals(),
            "has_successful_resume": self.has_successful_resume(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this control-plane status."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewControlPlaneSnapshot:
    """Digest-linked snapshot of all human-review control-plane ledgers."""

    state: HumanReviewControlPlaneState
    status: HumanReviewControlPlaneStatus

    @classmethod
    def from_state(
        cls,
        state: HumanReviewControlPlaneState,
    ) -> HumanReviewControlPlaneSnapshot:
        """Create a snapshot from human-review control-plane state."""
        return cls(
            state=state,
            status=HumanReviewControlPlaneStatus.from_state(state),
        )

    def require_consistent(self) -> None:
        """Raise if the snapshot status does not match the control-plane state."""
        if self.status.state_digest != self.state.digest():
            raise FoundationError("human-review control-plane snapshot digest mismatch")
        if self.status.handoff_count != self.state.handoff_count():
            raise FoundationError("human-review control-plane handoff count mismatch")
        if self.status.decision_count != self.state.decision_count():
            raise FoundationError("human-review control-plane decision count mismatch")
        if self.status.resume_count != self.state.resume_count():
            raise FoundationError("human-review control-plane resume count mismatch")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible control-plane snapshot payload."""
        self.require_consistent()
        return {
            "state_digest": self.state.digest().value,
            "status_digest": self.status.digest().value,
            "handoff_ledger_digest": self.state.handoff_ledger.digest().value,
            "decision_ledger_digest": self.state.decision_ledger.digest().value,
            "resume_ledger_digest": self.state.resume_ledger.digest().value,
            "status": self.status.to_payload(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this control-plane snapshot."""
        return DigestRecord.from_payload(self.to_payload())
