"""Immutable ledger for IX-Sally human-review operator decisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.human_review_gateway import (
    HumanReviewDecisionStatus,
    HumanReviewSubmissionResult,
    HumanReviewTargetType,
)
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLedgerEntry:
    """One immutable ledger entry for a submitted human-review decision."""

    entry_id: CanonicalKey
    sequence: int
    decision_digest: DigestRecord
    receipt_digest: DigestRecord
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_action_digest: DigestRecord
    after_action_digest: DigestRecord
    target_type: HumanReviewTargetType
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
        sequence: int,
        decision_digest: DigestRecord,
        receipt_digest: DigestRecord,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_action_digest: DigestRecord,
        after_action_digest: DigestRecord,
        target_type: HumanReviewTargetType,
        target_id: str,
        reviewer: str,
        status: HumanReviewDecisionStatus,
        next_stage: RunStage,
        changed_state: bool,
        changed_action: bool,
        entry_id: CanonicalKey | None = None,
    ) -> HumanReviewDecisionLedgerEntry:
        """Create a normalized human-review decision ledger entry."""
        if sequence <= 0:
            raise FoundationError("human-review decision ledger sequence must be positive")
        if not reviewer.strip():
            raise FoundationError("human-review decision reviewer must not be empty")

        decision_digest.require_algorithm("sha256")
        receipt_digest.require_algorithm("sha256")
        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_action_digest.require_algorithm("sha256")
        after_action_digest.require_algorithm("sha256")

        normalized_target_id = CanonicalKey.from_text(
            target_id,
            field_name="target_id",
        )
        normalized_reviewer = reviewer.strip()

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"human-review-decision-ledger-{sequence}-"
                f"{decision_digest.value[:16]}-{receipt_digest.value[:16]}",
                field_name="entry_id",
            ),
            sequence=sequence,
            decision_digest=decision_digest,
            receipt_digest=receipt_digest,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_action_digest=before_action_digest,
            after_action_digest=after_action_digest,
            target_type=target_type,
            target_id=normalized_target_id,
            reviewer=normalized_reviewer,
            status=status,
            next_stage=next_stage,
            changed_state=changed_state,
            changed_action=changed_action,
        )

    @classmethod
    def from_submission(
        cls,
        *,
        sequence: int,
        submission: HumanReviewSubmissionResult,
    ) -> HumanReviewDecisionLedgerEntry:
        """Create a decision ledger entry from a human-review submission result."""
        return cls.create(
            sequence=sequence,
            decision_digest=submission.decision.digest(),
            receipt_digest=submission.receipt.digest(),
            before_state_digest=submission.before_snapshot.state_digest,
            after_state_digest=submission.state.digest(),
            before_action_digest=submission.before_action.digest(),
            after_action_digest=submission.after_action.digest(),
            target_type=submission.decision.target_type,
            target_id=submission.decision.target_id.value,
            reviewer=submission.decision.reviewer,
            status=submission.decision.status,
            next_stage=submission.next_snapshot().stage,
            changed_state=submission.receipt.changed_state(),
            changed_action=submission.receipt.changed_action(),
        )

    def approved_target(self) -> bool:
        """Return whether this entry approved the target."""
        return self.status is HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION

    def rejected_target(self) -> bool:
        """Return whether this entry rejected the target."""
        return self.status is HumanReviewDecisionStatus.REJECTED

    def deferred_target(self) -> bool:
        """Return whether this entry deferred the target."""
        return self.status is HumanReviewDecisionStatus.DEFERRED

    def target_key(self) -> tuple[str, str]:
        """Return a stable target key for grouping review decisions."""
        return (self.target_type.value, self.target_id.value)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review decision ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "decision_digest": {
                "algorithm": self.decision_digest.algorithm,
                "value": self.decision_digest.value,
            },
            "receipt_digest": {
                "algorithm": self.receipt_digest.algorithm,
                "value": self.receipt_digest.value,
            },
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "before_action_digest": {
                "algorithm": self.before_action_digest.algorithm,
                "value": self.before_action_digest.value,
            },
            "after_action_digest": {
                "algorithm": self.after_action_digest.algorithm,
                "value": self.after_action_digest.value,
            },
            "target_type": self.target_type.value,
            "target_id": self.target_id.value,
            "reviewer": self.reviewer,
            "status": self.status.value,
            "next_stage": self.next_stage.value,
            "changed_state": self.changed_state,
            "changed_action": self.changed_action,
            "approved_target": self.approved_target(),
            "rejected_target": self.rejected_target(),
            "deferred_target": self.deferred_target(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review decision ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLedger:
    """Immutable ledger of human-review operator decisions."""

    entries: tuple[HumanReviewDecisionLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[HumanReviewDecisionLedgerEntry],
    ) -> HumanReviewDecisionLedger:
        """Create a decision ledger and reject duplicate or out-of-order entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_decision_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate human-review decision ledger sequence: "
                    f"{entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate human-review decision ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.decision_digest.value in seen_decision_digests:
                raise FoundationError(
                    f"duplicate human-review decision digest: "
                    f"{entry.decision_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "human-review decision ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_decision_digests.add(entry.decision_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(
        self,
        entry: HumanReviewDecisionLedgerEntry,
    ) -> HumanReviewDecisionLedger:
        """Return a new ledger with an appended human-review decision entry."""
        return HumanReviewDecisionLedger.create((*self.entries, entry))

    def append_submission(
        self,
        submission: HumanReviewSubmissionResult,
    ) -> HumanReviewDecisionLedger:
        """Return a new ledger with a submission recorded at the next sequence."""
        return self.append(
            HumanReviewDecisionLedgerEntry.from_submission(
                sequence=self.next_sequence(),
                submission=submission,
            )
        )

    def latest(self) -> HumanReviewDecisionLedgerEntry | None:
        """Return the latest decision entry, if any."""
        if not self.entries:
            return None
        return self.entries[-1]

    def approved_entries(self) -> tuple[HumanReviewDecisionLedgerEntry, ...]:
        """Return entries that approved their targets."""
        return tuple(entry for entry in self.entries if entry.approved_target())

    def rejected_entries(self) -> tuple[HumanReviewDecisionLedgerEntry, ...]:
        """Return entries that rejected their targets."""
        return tuple(entry for entry in self.entries if entry.rejected_target())

    def deferred_entries(self) -> tuple[HumanReviewDecisionLedgerEntry, ...]:
        """Return entries that deferred their targets."""
        return tuple(entry for entry in self.entries if entry.deferred_target())

    def entries_for_target(
        self,
        *,
        target_type: HumanReviewTargetType,
        target_id: str,
    ) -> tuple[HumanReviewDecisionLedgerEntry, ...]:
        """Return decision entries for a specific review target."""
        key = (
            target_type.value,
            CanonicalKey.from_text(target_id, field_name="target_id").value,
        )
        return tuple(entry for entry in self.entries if entry.target_key() == key)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review decision ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "approved_count": len(self.approved_entries()),
            "rejected_count": len(self.rejected_entries()),
            "deferred_count": len(self.deferred_entries()),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review decision ledger."""
        return DigestRecord.from_payload(self.to_payload())
