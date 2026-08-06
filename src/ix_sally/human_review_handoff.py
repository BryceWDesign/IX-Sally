"""Coordinated human-review handoffs for IX-Sally operator review."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_bundle import (
    HumanReviewBundleAssembler,
    HumanReviewOperatorBundle,
)
from ix_sally.human_review_bundle_ledger import (
    HumanReviewBundleLedger,
    HumanReviewBundleLedgerEntry,
)
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewHandoffReceipt:
    """Compact receipt for a coordinated human-review handoff."""

    receipt_id: CanonicalKey
    before_ledger_digest: DigestRecord
    after_ledger_digest: DigestRecord
    bundle_digest: DigestRecord
    ledger_entry_digest: DigestRecord
    state_digest: DigestRecord
    target_count: int
    gateway_resolvable_count: int
    manual_investigation_count: int
    blocker_acknowledgment_count: int
    authority_note: str

    @classmethod
    def create(
        cls,
        *,
        before_ledger_digest: DigestRecord,
        after_ledger_digest: DigestRecord,
        bundle_digest: DigestRecord,
        ledger_entry_digest: DigestRecord,
        state_digest: DigestRecord,
        target_count: int,
        gateway_resolvable_count: int,
        manual_investigation_count: int,
        blocker_acknowledgment_count: int,
        authority_note: str,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewHandoffReceipt:
        """Create a normalized human-review handoff receipt."""
        if target_count <= 0:
            raise FoundationError("human-review handoff target_count must be positive")
        if gateway_resolvable_count < 0:
            raise FoundationError(
                "human-review handoff gateway_resolvable_count must not be negative"
            )
        if manual_investigation_count < 0:
            raise FoundationError(
                "human-review handoff manual_investigation_count must not be negative"
            )
        if blocker_acknowledgment_count < 0:
            raise FoundationError(
                "human-review handoff blocker_acknowledgment_count must not be negative"
            )

        surfaced_count = (
            gateway_resolvable_count + manual_investigation_count + blocker_acknowledgment_count
        )
        if surfaced_count != target_count:
            raise FoundationError("human-review handoff surfaced counts must equal target_count")

        before_ledger_digest.require_algorithm("sha256")
        after_ledger_digest.require_algorithm("sha256")
        bundle_digest.require_algorithm("sha256")
        ledger_entry_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        normalized_note = require_text(authority_note, field_name="authority_note")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-handoff-{state_digest.value[:16]}-"
                f"{bundle_digest.value[:16]}-{ledger_entry_digest.value[:16]}",
                field_name="receipt_id",
            ),
            before_ledger_digest=before_ledger_digest,
            after_ledger_digest=after_ledger_digest,
            bundle_digest=bundle_digest,
            ledger_entry_digest=ledger_entry_digest,
            state_digest=state_digest,
            target_count=target_count,
            gateway_resolvable_count=gateway_resolvable_count,
            manual_investigation_count=manual_investigation_count,
            blocker_acknowledgment_count=blocker_acknowledgment_count,
            authority_note=normalized_note,
        )

    @classmethod
    def from_handoff(
        cls,
        *,
        before_ledger: HumanReviewBundleLedger,
        after_ledger: HumanReviewBundleLedger,
        bundle: HumanReviewOperatorBundle,
        entry: HumanReviewBundleLedgerEntry,
    ) -> HumanReviewHandoffReceipt:
        """Create a handoff receipt from an assembled bundle and appended ledger entry."""
        return cls.create(
            before_ledger_digest=before_ledger.digest(),
            after_ledger_digest=after_ledger.digest(),
            bundle_digest=bundle.digest(),
            ledger_entry_digest=entry.digest(),
            state_digest=bundle.snapshot.state_digest,
            target_count=bundle.target_count(),
            gateway_resolvable_count=bundle.gateway_resolvable_count(),
            manual_investigation_count=bundle.manual_investigation_count(),
            blocker_acknowledgment_count=bundle.blocker_acknowledgment_count(),
            authority_note=bundle.packet.authority_note,
        )

    def changed_ledger(self) -> bool:
        """Return whether this handoff changed the human-review bundle ledger."""
        return self.before_ledger_digest != self.after_ledger_digest

    def requires_human_authority(self) -> bool:
        """Return whether this handoff requires human authority."""
        return True

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible handoff receipt."""
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
            "bundle_digest": {
                "algorithm": self.bundle_digest.algorithm,
                "value": self.bundle_digest.value,
            },
            "ledger_entry_digest": {
                "algorithm": self.ledger_entry_digest.algorithm,
                "value": self.ledger_entry_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "target_count": self.target_count,
            "gateway_resolvable_count": self.gateway_resolvable_count,
            "manual_investigation_count": self.manual_investigation_count,
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count,
            "authority_note": self.authority_note,
            "changed_ledger": self.changed_ledger(),
            "requires_human_authority": self.requires_human_authority(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review handoff receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewHandoffResult:
    """Result of assembling and recording a human-review handoff."""

    bundle: HumanReviewOperatorBundle
    before_ledger: HumanReviewBundleLedger
    after_ledger: HumanReviewBundleLedger
    ledger_entry: HumanReviewBundleLedgerEntry
    receipt: HumanReviewHandoffReceipt

    def latest_entry(self) -> HumanReviewBundleLedgerEntry:
        """Return the ledger entry produced by this handoff."""
        latest = self.after_ledger.latest()
        if latest is None:
            raise FoundationError("human-review handoff ledger has no latest entry")
        return latest

    def target_count(self) -> int:
        """Return how many human-review targets were surfaced."""
        return self.bundle.target_count()

    def gateway_resolvable_count(self) -> int:
        """Return how many surfaced cards can be resolved by the gateway."""
        return self.bundle.gateway_resolvable_count()

    def manual_investigation_count(self) -> int:
        """Return how many surfaced cards require manual investigation."""
        return self.bundle.manual_investigation_count()

    def blocker_acknowledgment_count(self) -> int:
        """Return how many surfaced cards document blockers."""
        return self.bundle.blocker_acknowledgment_count()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible handoff result."""
        return {
            "bundle_digest": self.bundle.digest().value,
            "before_ledger_digest": self.before_ledger.digest().value,
            "after_ledger_digest": self.after_ledger.digest().value,
            "ledger_entry_digest": self.ledger_entry.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "latest_entry_digest": self.latest_entry().digest().value,
            "target_count": self.target_count(),
            "gateway_resolvable_count": self.gateway_resolvable_count(),
            "manual_investigation_count": self.manual_investigation_count(),
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count(),
            "changed_ledger": self.receipt.changed_ledger(),
            "requires_human_authority": self.receipt.requires_human_authority(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review handoff result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewHandoffCoordinator:
    """Assembles active human-review bundles and records them in a handoff ledger."""

    assembler: HumanReviewBundleAssembler

    @classmethod
    def create(cls) -> HumanReviewHandoffCoordinator:
        """Create a standard human-review handoff coordinator."""
        return cls(assembler=HumanReviewBundleAssembler.create())

    def handoff(
        self,
        *,
        state: NinefoldRunState,
        ledger: HumanReviewBundleLedger,
        authority_note: str = (
            "Human authority is required before IX-Sally may treat these targets as resolved."
        ),
    ) -> HumanReviewHandoffResult:
        """Assemble and append one human-review handoff to the provided ledger."""
        bundle = self.assembler.assemble(
            state=state,
            authority_note=authority_note,
        )
        if bundle.snapshot.stage is not RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review handoff requires human_review stage")

        after_ledger = ledger.append_bundle(bundle)
        entry = after_ledger.latest()
        if entry is None:
            raise FoundationError("human-review handoff failed to append ledger entry")

        receipt = HumanReviewHandoffReceipt.from_handoff(
            before_ledger=ledger,
            after_ledger=after_ledger,
            bundle=bundle,
            entry=entry,
        )

        return HumanReviewHandoffResult(
            bundle=bundle,
            before_ledger=ledger,
            after_ledger=after_ledger,
            ledger_entry=entry,
            receipt=receipt,
        )
