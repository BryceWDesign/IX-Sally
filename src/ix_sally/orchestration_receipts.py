"""Receipts and ledgers for IX-Sally stage-gated orchestration advances."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.orchestration import StageAdvanceKind, StageAdvanceResult
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class StageAdvanceReceipt:
    """Compact receipt for one stage-gated orchestration advance."""

    receipt_id: CanonicalKey
    sequence: int
    stage: RunStage
    kind: StageAdvanceKind
    before_state_digest: DigestRecord
    after_state_digest: DigestRecord
    before_snapshot_digest: DigestRecord
    gate_decision_digest: DigestRecord
    detail: str
    processor_digest: DigestRecord | None = None
    changed_state: bool = False

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        stage: RunStage,
        kind: StageAdvanceKind,
        before_state_digest: DigestRecord,
        after_state_digest: DigestRecord,
        before_snapshot_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        detail: str,
        processor_digest: DigestRecord | None = None,
        changed_state: bool = False,
        receipt_id: CanonicalKey | None = None,
    ) -> StageAdvanceReceipt:
        """Create a normalized stage advance receipt."""
        if sequence <= 0:
            raise FoundationError("stage advance receipt sequence must be positive")

        before_state_digest.require_algorithm("sha256")
        after_state_digest.require_algorithm("sha256")
        before_snapshot_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")
        if processor_digest is not None:
            processor_digest.require_algorithm("sha256")

        normalized_detail = require_text(detail, field_name="detail")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"{sequence}-{stage.value}-{kind.value}-{before_state_digest.value}-"
                f"{after_state_digest.value}",
                field_name="receipt_id",
            ),
            sequence=sequence,
            stage=stage,
            kind=kind,
            before_state_digest=before_state_digest,
            after_state_digest=after_state_digest,
            before_snapshot_digest=before_snapshot_digest,
            gate_decision_digest=gate_decision_digest,
            detail=normalized_detail,
            processor_digest=processor_digest,
            changed_state=changed_state,
        )

    @classmethod
    def from_result(
        cls,
        *,
        sequence: int,
        result: StageAdvanceResult,
    ) -> StageAdvanceReceipt:
        """Create a compact receipt from a full orchestration advance result."""
        return cls.create(
            sequence=sequence,
            stage=result.before_snapshot.stage,
            kind=result.kind,
            before_state_digest=result.before_snapshot.state_digest,
            after_state_digest=result.state.digest(),
            before_snapshot_digest=result.before_snapshot.digest(),
            gate_decision_digest=result.gate_decision.digest(),
            detail=result.detail,
            processor_digest=result.processor_digest,
            changed_state=result.changed_state(),
        )

    def awaits_external_input(self) -> bool:
        """Return whether this receipt means automation must stop for outside input."""
        return self.kind in {
            StageAdvanceKind.WAITING_FOR_PROPOSAL,
            StageAdvanceKind.WAITING_FOR_FORGE_RESULTS,
            StageAdvanceKind.HUMAN_REVIEW_REQUIRED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible stage advance receipt."""
        return {
            "receipt_id": self.receipt_id.value,
            "sequence": self.sequence,
            "stage": self.stage.value,
            "kind": self.kind.value,
            "before_state_digest": {
                "algorithm": self.before_state_digest.algorithm,
                "value": self.before_state_digest.value,
            },
            "after_state_digest": {
                "algorithm": self.after_state_digest.algorithm,
                "value": self.after_state_digest.value,
            },
            "before_snapshot_digest": {
                "algorithm": self.before_snapshot_digest.algorithm,
                "value": self.before_snapshot_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "detail": self.detail,
            "processor_digest": (
                {
                    "algorithm": self.processor_digest.algorithm,
                    "value": self.processor_digest.value,
                }
                if self.processor_digest is not None
                else None
            ),
            "changed_state": self.changed_state,
            "awaits_external_input": self.awaits_external_input(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this stage advance receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StageAdvanceLedger:
    """Immutable ledger of compact stage advance receipts."""

    receipts: tuple[StageAdvanceReceipt, ...]

    @classmethod
    def create(cls, receipts: Iterable[StageAdvanceReceipt]) -> StageAdvanceLedger:
        """Create a receipt ledger and reject duplicate sequence or receipt identifiers."""
        normalized = tuple(receipts)
        seen_sequences: set[int] = set()
        seen_receipts: set[str] = set()
        previous_sequence = 0

        for receipt in normalized:
            if receipt.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate stage advance receipt sequence: {receipt.sequence}"
                )
            if receipt.receipt_id.value in seen_receipts:
                raise FoundationError(
                    f"duplicate stage advance receipt id: {receipt.receipt_id.value}"
                )
            if receipt.sequence <= previous_sequence:
                raise FoundationError("stage advance receipt sequences must increase")

            seen_sequences.add(receipt.sequence)
            seen_receipts.add(receipt.receipt_id.value)
            previous_sequence = receipt.sequence

        return cls(receipts=normalized)

    def next_sequence(self) -> int:
        """Return the next ledger sequence number."""
        if not self.receipts:
            return 1
        return self.receipts[-1].sequence + 1

    def append(self, receipt: StageAdvanceReceipt) -> StageAdvanceLedger:
        """Return a new ledger with an appended stage advance receipt."""
        return StageAdvanceLedger.create((*self.receipts, receipt))

    def changed_receipts(self) -> tuple[StageAdvanceReceipt, ...]:
        """Return receipts that changed the run state."""
        return tuple(receipt for receipt in self.receipts if receipt.changed_state)

    def waiting_receipts(self) -> tuple[StageAdvanceReceipt, ...]:
        """Return receipts that wait for proposal, Forge result, or human review input."""
        return tuple(receipt for receipt in self.receipts if receipt.awaits_external_input())

    def by_kind(self, kind: StageAdvanceKind) -> tuple[StageAdvanceReceipt, ...]:
        """Return receipts matching a requested advance kind."""
        return tuple(receipt for receipt in self.receipts if receipt.kind is kind)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible stage advance ledger."""
        receipt_payload: JsonArray = []
        for receipt in self.receipts:
            receipt_payload.append(receipt.to_payload())

        return {
            "receipts": receipt_payload,
            "receipt_count": len(self.receipts),
            "changed_count": len(self.changed_receipts()),
            "waiting_count": len(self.waiting_receipts()),
            "next_sequence": self.next_sequence(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this stage advance ledger."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class StageAdvanceTrace:
    """Convenience wrapper for appending orchestration advance results as receipts."""

    ledger: StageAdvanceLedger

    @classmethod
    def create(cls) -> StageAdvanceTrace:
        """Create an empty stage advance trace."""
        return cls(ledger=StageAdvanceLedger.create(()))

    def record_result(self, result: StageAdvanceResult) -> StageAdvanceTrace:
        """Return a new trace with a receipt for the supplied advance result."""
        receipt = StageAdvanceReceipt.from_result(
            sequence=self.ledger.next_sequence(),
            result=result,
        )
        return StageAdvanceTrace(ledger=self.ledger.append(receipt))

    def latest(self) -> StageAdvanceReceipt | None:
        """Return the latest receipt, if any."""
        if not self.ledger.receipts:
            return None
        return self.ledger.receipts[-1]

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible trace payload."""
        latest = self.latest()
        return {
            "ledger": self.ledger.to_payload(),
            "latest_digest": latest.digest().value if latest is not None else None,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this stage advance trace."""
        return DigestRecord.from_payload(self.to_payload())
