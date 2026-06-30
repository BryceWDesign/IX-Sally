"""Coordinated human-review decisions for IX-Sally operator authority."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_decision_ledger import (
    HumanReviewDecisionLedger,
    HumanReviewDecisionLedgerEntry,
)
from ix_sally.human_review_gateway import (
    HumanReviewDecisionStatus,
    HumanReviewGateway,
    HumanReviewSubmissionResult,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionCoordinationReceipt:
    """Compact receipt for a coordinated human-review decision."""

    receipt_id: CanonicalKey
    before_ledger_digest: DigestRecord
    after_ledger_digest: DigestRecord
    submission_digest: DigestRecord
    ledger_entry_digest: DigestRecord
    decision_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    target_id: CanonicalKey
    reviewer: str
    status: HumanReviewDecisionStatus
    next_stage: RunStage
    changed_state: bool
    changed_action: bool

    @classmethod
    def create(
        cls,
        *,
        before_ledger_digest: DigestRecord,
        after_ledger_digest: DigestRecord,
        submission_digest: DigestRecord,
        ledger_entry_digest: DigestRecord,
        decision_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        target_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        next_stage: RunStage,
        changed_state: bool,
        changed_action: bool,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewDecisionCoordinationReceipt:
        """Create a normalized human-review decision coordination receipt."""
        before_ledger_digest.require_algorithm("sha256")
        after_ledger_digest.require_algorithm("sha256")
        submission_digest.require_algorithm("sha256")
        ledger_entry_digest.require_algorithm("sha256")
        decision_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")

        normalized_target_id = CanonicalKey.from_text(
            target_id,
            field_name="target_id",
        )
        normalized_reviewer = require_text(reviewer, field_name="reviewer")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-decision-coordination-"
                f"{decision_digest.value[:16]}-{ledger_entry_digest.value[:16]}",
                field_name="receipt_id",
            ),
            before_ledger_digest=before_ledger_digest,
            after_ledger_digest=after_ledger_digest,
            submission_digest=submission_digest,
            ledger_entry_digest=ledger_entry_digest,
            decision_digest=decision_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            target_id=normalized_target_id,
            reviewer=normalized_reviewer,
            status=status,
            next_stage=next_stage,
            changed_state=changed_state,
            changed_action=changed_action,
        )

    @classmethod
    def from_coordination(
        cls,
        *,
        before_ledger: HumanReviewDecisionLedger,
        after_ledger: HumanReviewDecisionLedger,
        submission: HumanReviewSubmissionResult,
        entry: HumanReviewDecisionLedgerEntry,
    ) -> HumanReviewDecisionCoordinationReceipt:
        """Create a coordination receipt from a submission and appended ledger entry."""
        return cls.create(
            before_ledger_digest=before_ledger.digest(),
            after_ledger_digest=after_ledger.digest(),
            submission_digest=submission.digest(),
            ledger_entry_digest=entry.digest(),
            decision_digest=submission.decision.digest(),
            before_state_digest=submission.before_snapshot.state_digest,
            after_state_digest=submission.state.digest(),
            target_id=submission.decision.target_id.value,
            reviewer=submission.decision.reviewer,
            status=submission.decision.status,
            next_stage=submission.next_snapshot().stage,
            changed_state=submission.receipt.changed_state(),
            changed_action=submission.receipt.changed_action(),
        )

    def changed_ledger(self) -> bool:
        """Return whether this coordination changed the decision ledger."""
        return self.before_ledger_digest != self.after_ledger_digest

    def approved_target(self) -> bool:
        """Return whether this coordination approved the review target."""
        return self.status is HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION

    def rejected_target(self) -> bool:
        """Return whether this coordination rejected the review target."""
        return self.status is HumanReviewDecisionStatus.REJECTED

    def deferred_target(self) -> bool:
        """Return whether this coordination deferred the review target."""
        return self.status is HumanReviewDecisionStatus.DEFERRED

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "before_ledger_digest": {
                "algorithm": self.before_ledger_digest.algorithm,
                "value": self.before_ledger_digest.value,
            },
            "after_ledger_digest": {
                "algorithm": self.after_ledger_digest.algorithm,
                "value": self.after_ledger_digest.value,
            },
            "submission_digest": {
                "algorithm": self.submission_digest.algorithm,
                "value": self.submission_digest.value,
            },
            "ledger_entry_digest": {
                "algorithm": self.ledger_entry_digest.algorithm,
                "value": self.ledger_entry_digest.value,
            },
            "decision_digest": {
                "algorithm": self.decision_digest.algorithm,
                "value": self.decision_digest.value,
            },
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "target_id": self.target_id.value,
            "reviewer": self.reviewer,
            "status": self.status.value,
            "next_stage": self.next_stage.value,
            "changed_state": self.changed_state,
            "changed_action": self.changed_action,
            "changed_ledger": self.changed_ledger(),
            "approved_target": self.approved_target(),
            "rejected_target": self.rejected_target(),
            "deferred_target": self.deferred_target(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionCoordinationResult:
    """Result of applying and ledgering one human-review decision."""

    submission: HumanReviewSubmissionResult
    before_ledger: HumanReviewDecisionLedger
    after_ledger: HumanReviewDecisionLedger
    ledger_entry: HumanReviewDecisionLedgerEntry
    receipt: HumanReviewDecisionCoordinationReceipt

    @property
    def state(self) -> NinefoldRunState:
        """Return the run state after the human-review decision."""
        return self.submission.state

    def latest_entry(self) -> HumanReviewDecisionLedgerEntry:
        """Return the ledger entry produced by this coordination."""
        latest = self.after_ledger.latest()
        if latest is None:
            raise FoundationError("human-review decision ledger has no latest entry")
        return latest

    def approved_target(self) -> bool:
        """Return whether the decision approved the target."""
        return self.ledger_entry.approved_target()

    def rejected_target(self) -> bool:
        """Return whether the decision rejected the target."""
        return self.ledger_entry.rejected_target()

    def deferred_target(self) -> bool:
        """Return whether the decision deferred the target."""
        return self.ledger_entry.deferred_target()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible coordination result."""
        return {
            "state_digest": self.state.digest().value,
            "submission_digest": self.submission.digest().value,
            "before_ledger_digest": self.before_ledger.digest().value,
            "after_ledger_digest": self.after_ledger.digest().value,
            "ledger_entry_digest": self.ledger_entry.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "latest_entry_digest": self.latest_entry().digest().value,
            "target_id": self.ledger_entry.target_id.value,
            "reviewer": self.ledger_entry.reviewer,
            "status": self.ledger_entry.status.value,
            "next_stage": self.ledger_entry.next_stage.value,
            "changed_state": self.ledger_entry.changed_state,
            "changed_action": self.ledger_entry.changed_action,
            "changed_ledger": self.receipt.changed_ledger(),
            "approved_target": self.approved_target(),
            "rejected_target": self.rejected_target(),
            "deferred_target": self.deferred_target(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this coordination result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionCoordinator:
    """Applies human-review decisions and records them in a decision ledger."""

    gateway: HumanReviewGateway

    @classmethod
    def create(cls) -> HumanReviewDecisionCoordinator:
        """Create a standard human-review decision coordinator."""
        return cls(gateway=HumanReviewGateway.create())

    def decide_action(
        self,
        *,
        state: NinefoldRunState,
        ledger: HumanReviewDecisionLedger,
        action_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        rationale: str,
    ) -> HumanReviewDecisionCoordinationResult:
        """Apply one human-review action decision and append it to the ledger."""
        submission = self.gateway.decide_action(
            state=state,
            action_id=action_id,
            reviewer=reviewer,
            status=status,
            rationale=rationale,
        )
        after_ledger = ledger.append_submission(submission)
        entry = after_ledger.latest()
        if entry is None:
            raise FoundationError(
                "human-review decision coordination failed to append ledger entry"
            )

        receipt = HumanReviewDecisionCoordinationReceipt.from_coordination(
            before_ledger=ledger,
            after_ledger=after_ledger,
            submission=submission,
            entry=entry,
        )

        return HumanReviewDecisionCoordinationResult(
            submission=submission,
            before_ledger=ledger,
            after_ledger=after_ledger,
            ledger_entry=entry,
            receipt=receipt,
        )
