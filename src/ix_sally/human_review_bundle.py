"""Operator bundles for IX-Sally human-review handoff."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_docket import HumanReviewDocket, HumanReviewDocketBuilder
from ix_sally.human_review_packets import HumanReviewPacket
from ix_sally.stage_readiness import RunStage, RunStageSnapshot
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class HumanReviewBundleReceipt:
    """Compact receipt for an assembled human-review operator bundle."""

    receipt_id: CanonicalKey
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
        state_digest: DigestRecord,
        snapshot_digest: DigestRecord,
        docket_digest: DigestRecord,
        packet_digest: DigestRecord,
        target_count: int,
        gateway_resolvable_count: int,
        manual_investigation_count: int,
        blocker_acknowledgment_count: int,
        authority_note: str,
        receipt_id: CanonicalKey | None = None,
    ) -> HumanReviewBundleReceipt:
        """Create a normalized human-review bundle receipt."""
        if target_count <= 0:
            raise FoundationError("human-review bundle target_count must be positive")
        if gateway_resolvable_count < 0:
            raise FoundationError(
                "human-review bundle gateway_resolvable_count must not be negative"
            )
        if manual_investigation_count < 0:
            raise FoundationError(
                "human-review bundle manual_investigation_count must not be negative"
            )
        if blocker_acknowledgment_count < 0:
            raise FoundationError(
                "human-review bundle blocker_acknowledgment_count must not be negative"
            )

        surfaced_count = (
            gateway_resolvable_count + manual_investigation_count + blocker_acknowledgment_count
        )
        if surfaced_count != target_count:
            raise FoundationError(
                "human-review bundle surfaced card counts must equal target_count"
            )

        state_digest.require_algorithm("sha256")
        snapshot_digest.require_algorithm("sha256")
        docket_digest.require_algorithm("sha256")
        packet_digest.require_algorithm("sha256")
        normalized_note = require_text(authority_note, field_name="authority_note")

        return cls(
            receipt_id=receipt_id
            or CanonicalKey.from_text(
                f"human-review-bundle-{state_digest.value[:16]}-"
                f"{packet_digest.value[:16]}-{target_count}",
                field_name="receipt_id",
            ),
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
    def from_parts(
        cls,
        *,
        snapshot: RunStageSnapshot,
        docket: HumanReviewDocket,
        packet: HumanReviewPacket,
    ) -> HumanReviewBundleReceipt:
        """Create a bundle receipt from assembled human-review parts."""
        return cls.create(
            state_digest=snapshot.state_digest,
            snapshot_digest=snapshot.digest(),
            docket_digest=docket.digest(),
            packet_digest=packet.digest(),
            target_count=len(docket.targets),
            gateway_resolvable_count=len(packet.gateway_resolvable_cards()),
            manual_investigation_count=len(packet.manual_investigation_cards()),
            blocker_acknowledgment_count=len(packet.blocker_acknowledgment_cards()),
            authority_note=packet.authority_note,
        )

    def requires_human_authority(self) -> bool:
        """Return whether the receipt represents a human-authority handoff."""
        return True

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible bundle receipt."""
        return {
            "receipt_id": self.receipt_id.value,
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
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this bundle receipt."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewOperatorBundle:
    """Complete operator handoff for an active IX-Sally human-review stage."""

    bundle_id: CanonicalKey
    snapshot: RunStageSnapshot
    docket: HumanReviewDocket
    packet: HumanReviewPacket
    receipt: HumanReviewBundleReceipt

    @classmethod
    def create(
        cls,
        *,
        snapshot: RunStageSnapshot,
        docket: HumanReviewDocket,
        packet: HumanReviewPacket,
        receipt: HumanReviewBundleReceipt,
        bundle_id: CanonicalKey | None = None,
    ) -> HumanReviewOperatorBundle:
        """Create a normalized human-review operator bundle."""
        if snapshot.stage is not RunStage.HUMAN_REVIEW:
            raise FoundationError("human-review operator bundle requires human_review stage")
        if docket.state_digest != snapshot.state_digest:
            raise FoundationError("human-review docket state digest does not match snapshot")
        if packet.state_digest != snapshot.state_digest:
            raise FoundationError("human-review packet state digest does not match snapshot")
        if receipt.state_digest != snapshot.state_digest:
            raise FoundationError("human-review receipt state digest does not match snapshot")
        if packet.docket_digest != docket.digest():
            raise FoundationError("human-review packet does not reference docket digest")
        if receipt.docket_digest != docket.digest():
            raise FoundationError("human-review receipt does not reference docket digest")
        if receipt.packet_digest != packet.digest():
            raise FoundationError("human-review receipt does not reference packet digest")

        return cls(
            bundle_id=bundle_id
            or CanonicalKey.from_text(
                f"human-review-operator-bundle-{snapshot.state_digest.value[:16]}-"
                f"{packet.digest().value[:16]}",
                field_name="bundle_id",
            ),
            snapshot=snapshot,
            docket=docket,
            packet=packet,
            receipt=receipt,
        )

    def gateway_resolvable_count(self) -> int:
        """Return how many cards can be resolved by the human-review gateway."""
        return len(self.packet.gateway_resolvable_cards())

    def manual_investigation_count(self) -> int:
        """Return how many cards require manual investigation."""
        return len(self.packet.manual_investigation_cards())

    def blocker_acknowledgment_count(self) -> int:
        """Return how many cards document blocking records."""
        return len(self.packet.blocker_acknowledgment_cards())

    def target_count(self) -> int:
        """Return how many human-review targets are surfaced."""
        return len(self.docket.targets)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible operator bundle."""
        return {
            "bundle_id": self.bundle_id.value,
            "snapshot_digest": self.snapshot.digest().value,
            "docket_digest": self.docket.digest().value,
            "packet_digest": self.packet.digest().value,
            "receipt_digest": self.receipt.digest().value,
            "stage": self.snapshot.stage.value,
            "target_count": self.target_count(),
            "gateway_resolvable_count": self.gateway_resolvable_count(),
            "manual_investigation_count": self.manual_investigation_count(),
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count(),
            "requires_human_authority": self.packet.requires_human_authority(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this operator bundle."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewBundleAssembler:
    """Assembles complete human-review operator bundles from run state."""

    docket_builder: HumanReviewDocketBuilder

    @classmethod
    def create(cls) -> HumanReviewBundleAssembler:
        """Create a standard human-review bundle assembler."""
        return cls(docket_builder=HumanReviewDocketBuilder.create())

    def assemble(
        self,
        *,
        state: NinefoldRunState,
        authority_note: str = (
            "Human authority is required before IX-Sally may treat these targets as resolved."
        ),
    ) -> HumanReviewOperatorBundle:
        """Assemble a docket, packet, and receipt for the active human-review stage."""
        snapshot = RunStageSnapshot.from_state(state)
        if snapshot.stage is not RunStage.HUMAN_REVIEW:
            raise FoundationError(
                f"human-review bundle expected human_review but observed {snapshot.stage.value}"
            )

        docket = self.docket_builder.build(state=state)
        packet = HumanReviewPacket.from_docket(
            docket,
            authority_note=authority_note,
        )
        receipt = HumanReviewBundleReceipt.from_parts(
            snapshot=snapshot,
            docket=docket,
            packet=packet,
        )

        return HumanReviewOperatorBundle.create(
            snapshot=snapshot,
            docket=docket,
            packet=packet,
            receipt=receipt,
        )
