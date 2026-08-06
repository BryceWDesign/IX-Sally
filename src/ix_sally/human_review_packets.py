"""Operator-facing human-review packets for IX-Sally dockets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_docket import (
    HumanReviewDocket,
    HumanReviewDocketSeverity,
    HumanReviewDocketTarget,
    HumanReviewDocketTargetType,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus


class HumanReviewResolutionMode(StrEnum):
    """How a human-review packet card can be resolved."""

    GATEWAY_DECISION = "gateway_decision"
    MANUAL_INVESTIGATION = "manual_investigation"
    BLOCKER_ACKNOWLEDGMENT = "blocker_acknowledgment"


@dataclass(frozen=True, slots=True)
class HumanReviewPacketCard:
    """One operator-facing card derived from a human-review docket target."""

    card_id: CanonicalKey
    target_type: HumanReviewDocketTargetType
    target_id: CanonicalKey
    cycle: int
    severity: HumanReviewDocketSeverity
    source_status: str
    summary: str
    rationale: str
    target_digest: DigestRecord
    resolution_mode: HumanReviewResolutionMode
    decision_options: tuple[str, ...]
    warning: str

    @classmethod
    def create(
        cls,
        *,
        target_type: HumanReviewDocketTargetType,
        target_id: str,
        cycle: int,
        severity: HumanReviewDocketSeverity,
        source_status: str,
        summary: str,
        rationale: str,
        target_digest: DigestRecord,
        resolution_mode: HumanReviewResolutionMode,
        decision_options: Iterable[str],
        warning: str,
        card_id: CanonicalKey | None = None,
    ) -> HumanReviewPacketCard:
        """Create a normalized human-review packet card."""
        if cycle < 0:
            raise FoundationError("human-review packet card cycle must not be negative")

        target_digest.require_algorithm("sha256")
        normalized_options = tuple(
            require_text(option, field_name="decision_option") for option in decision_options
        )
        if len(set(normalized_options)) != len(normalized_options):
            raise FoundationError("human-review packet card decision options must be unique")

        normalized_target_id = CanonicalKey.from_text(
            target_id,
            field_name="target_id",
        )

        return cls(
            card_id=card_id
            or CanonicalKey.from_text(
                f"{target_type.value}-{normalized_target_id.value}-{severity.value}",
                field_name="card_id",
            ),
            target_type=target_type,
            target_id=normalized_target_id,
            cycle=cycle,
            severity=severity,
            source_status=require_text(source_status, field_name="source_status"),
            summary=require_text(summary, field_name="summary"),
            rationale=require_text(rationale, field_name="rationale"),
            target_digest=target_digest,
            resolution_mode=resolution_mode,
            decision_options=normalized_options,
            warning=require_text(warning, field_name="warning"),
        )

    @classmethod
    def from_target(cls, target: HumanReviewDocketTarget) -> HumanReviewPacketCard:
        """Create an operator-facing packet card from a docket target."""
        mode, options, warning = _resolution_surface_for_target(target)

        return cls.create(
            target_type=target.target_type,
            target_id=target.target_id.value,
            cycle=target.cycle,
            severity=target.severity,
            source_status=target.source_status,
            summary=target.summary,
            rationale=target.rationale,
            target_digest=target.target_digest,
            resolution_mode=mode,
            decision_options=options,
            warning=warning,
        )

    def can_be_resolved_by_gateway(self) -> bool:
        """Return whether the current human-review gateway can resolve this card."""
        return self.resolution_mode is HumanReviewResolutionMode.GATEWAY_DECISION

    def requires_manual_investigation(self) -> bool:
        """Return whether this card needs manual investigation outside the gateway."""
        return self.resolution_mode is HumanReviewResolutionMode.MANUAL_INVESTIGATION

    def acknowledges_blocker_only(self) -> bool:
        """Return whether this card documents a blocker rather than resolving it."""
        return self.resolution_mode is HumanReviewResolutionMode.BLOCKER_ACKNOWLEDGMENT

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible packet card."""
        options_payload: JsonArray = []
        for option in self.decision_options:
            options_payload.append(option)

        return {
            "card_id": self.card_id.value,
            "target_type": self.target_type.value,
            "target_id": self.target_id.value,
            "cycle": self.cycle,
            "severity": self.severity.value,
            "source_status": self.source_status,
            "summary": self.summary,
            "rationale": self.rationale,
            "target_digest": {
                "algorithm": self.target_digest.algorithm,
                "value": self.target_digest.value,
            },
            "resolution_mode": self.resolution_mode.value,
            "decision_options": options_payload,
            "warning": self.warning,
            "can_be_resolved_by_gateway": self.can_be_resolved_by_gateway(),
            "requires_manual_investigation": self.requires_manual_investigation(),
            "acknowledges_blocker_only": self.acknowledges_blocker_only(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this packet card."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewPacket:
    """Operator packet assembled from an active human-review docket."""

    packet_id: CanonicalKey
    docket_digest: DigestRecord
    state_digest: DigestRecord
    snapshot_digest: DigestRecord
    gate_decision_digest: DigestRecord
    cards: tuple[HumanReviewPacketCard, ...]
    authority_note: str

    @classmethod
    def create(
        cls,
        *,
        docket_digest: DigestRecord,
        state_digest: DigestRecord,
        snapshot_digest: DigestRecord,
        gate_decision_digest: DigestRecord,
        cards: Iterable[HumanReviewPacketCard],
        authority_note: str,
        packet_id: CanonicalKey | None = None,
    ) -> HumanReviewPacket:
        """Create a normalized human-review packet."""
        docket_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")
        snapshot_digest.require_algorithm("sha256")
        gate_decision_digest.require_algorithm("sha256")

        normalized_cards = tuple(cards)
        if not normalized_cards:
            raise FoundationError("human-review packet requires at least one card")

        seen_cards: set[str] = set()
        for card in normalized_cards:
            if card.card_id.value in seen_cards:
                raise FoundationError(f"duplicate human-review packet card: {card.card_id.value}")
            seen_cards.add(card.card_id.value)

        normalized_note = require_text(authority_note, field_name="authority_note")

        return cls(
            packet_id=packet_id
            or CanonicalKey.from_text(
                f"human-review-packet-{docket_digest.value[:16]}-{len(normalized_cards)}",
                field_name="packet_id",
            ),
            docket_digest=docket_digest,
            state_digest=state_digest,
            snapshot_digest=snapshot_digest,
            gate_decision_digest=gate_decision_digest,
            cards=normalized_cards,
            authority_note=normalized_note,
        )

    @classmethod
    def from_docket(
        cls,
        docket: HumanReviewDocket,
        *,
        authority_note: str = (
            "Human authority is required before IX-Sally may treat these targets as resolved."
        ),
    ) -> HumanReviewPacket:
        """Create an operator packet from a human-review docket."""
        cards = tuple(HumanReviewPacketCard.from_target(target) for target in docket.targets)

        return cls.create(
            docket_digest=docket.digest(),
            state_digest=docket.state_digest,
            snapshot_digest=docket.snapshot_digest,
            gate_decision_digest=docket.gate_decision_digest,
            cards=cards,
            authority_note=authority_note,
        )

    def gateway_resolvable_cards(self) -> tuple[HumanReviewPacketCard, ...]:
        """Return cards that can be resolved by the human-review gateway."""
        return tuple(card for card in self.cards if card.can_be_resolved_by_gateway())

    def manual_investigation_cards(self) -> tuple[HumanReviewPacketCard, ...]:
        """Return cards requiring manual investigation."""
        return tuple(card for card in self.cards if card.requires_manual_investigation())

    def blocker_acknowledgment_cards(self) -> tuple[HumanReviewPacketCard, ...]:
        """Return cards that document blocking records."""
        return tuple(card for card in self.cards if card.acknowledges_blocker_only())

    def requires_human_authority(self) -> bool:
        """Return whether this packet requires human authority."""
        return True

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review packet."""
        cards_payload: JsonArray = []
        for card in self.cards:
            cards_payload.append(card.to_payload())

        return {
            "packet_id": self.packet_id.value,
            "docket_digest": {
                "algorithm": self.docket_digest.algorithm,
                "value": self.docket_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "snapshot_digest": {
                "algorithm": self.snapshot_digest.algorithm,
                "value": self.snapshot_digest.value,
            },
            "gate_decision_digest": {
                "algorithm": self.gate_decision_digest.algorithm,
                "value": self.gate_decision_digest.value,
            },
            "cards": cards_payload,
            "card_count": len(self.cards),
            "gateway_resolvable_count": len(self.gateway_resolvable_cards()),
            "manual_investigation_count": len(self.manual_investigation_cards()),
            "blocker_acknowledgment_count": len(self.blocker_acknowledgment_cards()),
            "authority_note": self.authority_note,
            "requires_human_authority": self.requires_human_authority(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review packet."""
        return DigestRecord.from_payload(self.to_payload())


def _resolution_surface_for_target(
    target: HumanReviewDocketTarget,
) -> tuple[HumanReviewResolutionMode, tuple[str, ...], str]:
    """Return the operator decision surface for a docket target."""
    if (
        target.target_type is HumanReviewDocketTargetType.BOUNDED_ACTION
        and target.severity is HumanReviewDocketSeverity.REVIEW_REQUIRED
    ):
        return (
            HumanReviewResolutionMode.GATEWAY_DECISION,
            (
                HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value,
                HumanReviewDecisionStatus.REJECTED.value,
                HumanReviewDecisionStatus.DEFERRED.value,
            ),
            "Only a human decision may approve, reject, or defer this action.",
        )

    if target.severity in {
        HumanReviewDocketSeverity.BLOCKER,
        HumanReviewDocketSeverity.TERMINATION,
    }:
        return (
            HumanReviewResolutionMode.BLOCKER_ACKNOWLEDGMENT,
            (),
            "This card documents a blocking condition; it is not auto-resolved.",
        )

    return (
        HumanReviewResolutionMode.MANUAL_INVESTIGATION,
        (),
        "This target requires manual review; no autonomous resolution is available.",
    )
