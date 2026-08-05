"""Immutable ledger for IX-Sally human-review operator bundles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_bundle import HumanReviewOperatorBundle
from ix_sally.stage_readiness import RunStage


@dataclass(frozen=True, slots=True)
class HumanReviewBundleLedgerEntry:
    """One immutable ledger entry for a human-review operator bundle handoff."""

    entry_id: CanonicalKey
    sequence: int
    bundle_digest: DigestRecord
    receipt_digest: DigestRecord
    state_digest: DigestRecord
    snapshot_digest: DigestRecord
    docket_digest: DigestRecord
    packet_digest: DigestRecord
    target_count: int
    gateway_resolvable_count: int
    manual_investigation_count: int
    blocker_acknowledgment_count: int
    authority_note: str

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        bundle_digest: DigestRecord,
        receipt_digest: DigestRecord,
        state_digest: DigestRecord,
        snapshot_digest: DigestRecord,
        docket_digest: DigestRecord,
        packet_digest: DigestRecord,
        target_count: int,
        gateway_resolvable_count: int,
        manual_investigation_count: int,
        blocker_acknowledgment_count: int,
        authority_note: str,
        entry_id: CanonicalKey | None = None,
    ) -> HumanReviewBundleLedgerEntry:
        """Create a normalized human-review bundle ledger entry."""
        if sequence <= 0:
            raise FoundationError("human-review bundle ledger sequence must be positive")
        if target_count <= 0:
            raise FoundationError("human-review bundle ledger target_count must be positive")
        if gateway_resolvable_count < 0:
            raise FoundationError(
                "human-review bundle ledger gateway_resolvable_count must not be negative"
            )
        if manual_investigation_count < 0:
            raise FoundationError(
                "human-review bundle ledger manual_investigation_count must not be negative"
            )
        if blocker_acknowledgment_count < 0:
            raise FoundationError(
                "human-review bundle ledger blocker_acknowledgment_count must not be negative"
            )

        surfaced_count = (
            gateway_resolvable_count
            + manual_investigation_count
            + blocker_acknowledgment_count
        )
        if surfaced_count != target_count:
            raise FoundationError(
                "human-review bundle ledger surfaced counts must equal target_count"
            )

        bundle_digest.require_algorithm("sha256")
        receipt_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        snapshot_digest.require_algorithm("sha256")
        docket_digest.require_algorithm("sha256")
        packet_digest.require_algorithm("sha256")
        normalized_note = require_text(authority_note, field_name="authority_note")

        return cls(
            entry_id=entry_id
            or CanonicalKey.from_text(
                f"human-review-bundle-ledger-{sequence}-"
                f"{bundle_digest.value[:16]}-{receipt_digest.value[:16]}",
                field_name="entry_id",
            ),
            sequence=sequence,
            bundle_digest=bundle_digest,
            receipt_digest=receipt_digest,
            state_digest=state_digest,
            snapshot_digest=snapshot_digest,
            docket_digest=docket_digest,
            packet_digest=packet_digest,
            target_count=target_count,
            gateway_resolvable_count=gateway_resolvable_count,
            manual_investigation_count=manual_investigation_count,
            blocker_acknowledgment_count=blocker_acknowledgment_count,
            authority_note=normalized_note,
        )

    @classmethod
    def from_bundle(
        cls,
        *,
        sequence: int,
        bundle: HumanReviewOperatorBundle,
    ) -> HumanReviewBundleLedgerEntry:
        """Create a ledger entry from an assembled human-review operator bundle."""
        if bundle.snapshot.stage is not RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review bundle ledger entry requires human_review stage")

        return cls.create(
            sequence=sequence,
            bundle_digest=bundle.digest(),
            receipt_digest=bundle.receipt.digest(),
            state_digest=bundle.snapshot.state_digest,
            snapshot_digest=bundle.snapshot.digest(),
            docket_digest=bundle.docket.digest(),
            packet_digest=bundle.packet.digest(),
            target_count=bundle.target_count(),
            gateway_resolvable_count=bundle.gateway_resolvable_count(),
            manual_investigation_count=bundle.manual_investigation_count(),
            blocker_acknowledgment_count=bundle.blocker_acknowledgment_count(),
            authority_note=bundle.packet.authority_note,
        )

    def requires_human_authority(self) -> bool:
        """Return whether this ledger entry represents a human-authority handoff."""
        return True

    def has_gateway_resolvable_cards(self) -> bool:
        """Return whether the entry includes cards resolvable by the gateway."""
        return self.gateway_resolvable_count > 0

    def has_manual_investigation_cards(self) -> bool:
        """Return whether the entry includes cards needing manual investigation."""
        return self.manual_investigation_count > 0

    def has_blocker_acknowledgment_cards(self) -> bool:
        """Return whether the entry includes blocker-only cards."""
        return self.blocker_acknowledgment_count > 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review bundle ledger entry."""
        return {
            "entry_id": self.entry_id.value,
            "sequence": self.sequence,
            "bundle_digest": {
                "algorithm": self.bundle_digest.algorithm,
                "value": self.bundle_digest.value,
            },
            "receipt_digest": {
                "algorithm": self.receipt_digest.algorithm,
                "value": self.receipt_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "snapshot_digest": {
                "algorithm": self.snapshot_digest.algorithm,
                "value": self.snapshot_digest.value,
            },
            "docket_digest": {
                "algorithm": self.docket_digest.algorithm,
                "value": self.docket_digest.value,
            },
            "packet_digest": {
                "algorithm": self.packet_digest.algorithm,
                "value": self.packet_digest.value,
            },
            "target_count": self.target_count,
            "gateway_resolvable_count": self.gateway_resolvable_count,
            "manual_investigation_count": self.manual_investigation_count,
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count,
            "authority_note": self.authority_note,
            "requires_human_authority": self.requires_human_authority(),
            "has_gateway_resolvable_cards": self.has_gateway_resolvable_cards(),
            "has_manual_investigation_cards": self.has_manual_investigation_cards(),
            "has_blocker_acknowledgment_cards": self.has_blocker_acknowledgment_cards(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review bundle ledger entry."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewBundleLedger:
    """Immutable ledger of human-review operator bundle handoffs."""

    entries: tuple[HumanReviewBundleLedgerEntry, ...]

    @classmethod
    def create(
        cls,
        entries: Iterable[HumanReviewBundleLedgerEntry],
    ) -> HumanReviewBundleLedger:
        """Create a ledger and reject duplicate or out-of-order bundle entries."""
        normalized = tuple(entries)
        seen_sequences: set[int] = set()
        seen_entry_ids: set[str] = set()
        seen_bundle_digests: set[str] = set()
        previous_sequence = 0

        for entry in normalized:
            if entry.sequence in seen_sequences:
                raise FoundationError(
                    f"duplicate human-review bundle ledger sequence: {entry.sequence}"
                )
            if entry.entry_id.value in seen_entry_ids:
                raise FoundationError(
                    f"duplicate human-review bundle ledger entry id: "
                    f"{entry.entry_id.value}"
                )
            if entry.bundle_digest.value in seen_bundle_digests:
                raise FoundationError(
                    f"duplicate human-review bundle digest: {entry.bundle_digest.value}"
                )
            if entry.sequence <= previous_sequence:
                raise FoundationError(
                    "human-review bundle ledger sequences must increase"
                )

            seen_sequences.add(entry.sequence)
            seen_entry_ids.add(entry.entry_id.value)
            seen_bundle_digests.add(entry.bundle_digest.value)
            previous_sequence = entry.sequence

        return cls(entries=normalized)

    def next_sequence(self) -> int:
        """Return the next ledger sequence number."""
        if not self.entries:
            return 1
        return self.entries[-1].sequence + 1

    def append(self, entry: HumanReviewBundleLedgerEntry) -> HumanReviewBundleLedger:
        """Return a new ledger with an appended bundle entry."""
        return HumanReviewBundleLedger.create((*self.entries, entry))

    def append_bundle(self, bundle: HumanReviewOperatorBundle) -> HumanReviewBundleLedger:
        """Return a new ledger with a bundle recorded at the next sequence."""
        return self.append(
            HumanReviewBundleLedgerEntry.from_bundle(
                sequence=self.next_sequence(),
                bundle=bundle,
            )
        )

    def latest(self) -> HumanReviewBundleLedgerEntry | None:
        """Return the latest bundle entry, if any."""
        if not self.entries:
            return None
        return self.entries[-1]

    def gateway_resolvable_entries(self) -> tuple[HumanReviewBundleLedgerEntry, ...]:
        """Return entries that include gateway-resolvable cards."""
        return tuple(entry for entry in self.entries if entry.has_gateway_resolvable_cards())

    def manual_investigation_entries(self) -> tuple[HumanReviewBundleLedgerEntry, ...]:
        """Return entries that include manual-investigation cards."""
        return tuple(entry for entry in self.entries if entry.has_manual_investigation_cards())

    def blocker_acknowledgment_entries(self) -> tuple[HumanReviewBundleLedgerEntry, ...]:
        """Return entries that include blocker-only cards."""
        return tuple(
            entry for entry in self.entries if entry.has_blocker_acknowledgment_cards()
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review bundle ledger."""
        entry_payload: JsonArray = []
        for entry in self.entries:
            entry_payload.append(entry.to_payload())

        latest = self.latest()

        return {
            "entries": entry_payload,
            "entry_count": len(self.entries),
            "next_sequence": self.next_sequence(),
            "latest_entry_digest": latest.digest().value if latest is not None else None,
            "gateway_resolvable_entry_count": len(self.gateway_resolvable_entries()),
            "manual_investigation_entry_count": len(self.manual_investigation_entries()),
            "blocker_acknowledgment_entry_count": len(
                self.blocker_acknowledgment_entries()
            ),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review bundle ledger."""
        return DigestRecord.from_payload(self.to_payload())
