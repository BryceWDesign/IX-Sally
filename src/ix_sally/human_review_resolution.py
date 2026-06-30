"""Resolution audits for IX-Sally human-review operator bundles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text
from ix_sally.human_review_bundle import HumanReviewOperatorBundle
from ix_sally.human_review_decision_ledger import (
    HumanReviewDecisionLedger,
    HumanReviewDecisionLedgerEntry,
)
from ix_sally.human_review_docket import HumanReviewDocketTargetType
from ix_sally.human_review_gateway import HumanReviewTargetType
from ix_sally.human_review_packets import (
    HumanReviewPacketCard,
    HumanReviewResolutionMode,
)


class HumanReviewResolutionStatus(StrEnum):
    """Resolution status for one human-review packet card."""

    RESOLVED_BY_DECISION = "resolved_by_decision"
    PENDING_DECISION = "pending_decision"
    MANUAL_INVESTIGATION_REQUIRED = "manual_investigation_required"
    BLOCKER_ACKNOWLEDGED = "blocker_acknowledged"


@dataclass(frozen=True, slots=True)
class HumanReviewCardResolution:
    """Resolution audit result for one human-review packet card."""

    card_id: CanonicalKey
    target_type: HumanReviewDocketTargetType
    target_id: CanonicalKey
    card_digest: DigestRecord
    status: HumanReviewResolutionStatus
    rationale: str
    decision_entry_digest: DigestRecord | None = None
    decision_status: str | None = None

    @classmethod
    def create(
        cls,
        *,
        card_id: str,
        target_type: HumanReviewDocketTargetType,
        target_id: str,
        card_digest: DigestRecord,
        status: HumanReviewResolutionStatus,
        rationale: str,
        decision_entry_digest: DigestRecord | None = None,
        decision_status: str | None = None,
    ) -> HumanReviewCardResolution:
        """Create a normalized card-resolution audit result."""
        card_digest.require_algorithm("sha256")
        if decision_entry_digest is not None:
            decision_entry_digest.require_algorithm("sha256")

        return cls(
            card_id=CanonicalKey.from_text(card_id, field_name="card_id"),
            target_type=target_type,
            target_id=CanonicalKey.from_text(target_id, field_name="target_id"),
            card_digest=card_digest,
            status=status,
            rationale=require_text(rationale, field_name="rationale"),
            decision_entry_digest=decision_entry_digest,
            decision_status=decision_status,
        )

    @classmethod
    def from_card(
        cls,
        *,
        card: HumanReviewPacketCard,
        decision_entry: HumanReviewDecisionLedgerEntry | None,
    ) -> HumanReviewCardResolution:
        """Create a resolution audit result from a packet card and optional decision."""
        if card.resolution_mode is HumanReviewResolutionMode.GATEWAY_DECISION:
            if decision_entry is None:
                return cls.create(
                    card_id=card.card_id.value,
                    target_type=card.target_type,
                    target_id=card.target_id.value,
                    card_digest=card.digest(),
                    status=HumanReviewResolutionStatus.PENDING_DECISION,
                    rationale="Gateway-resolvable card has no recorded human decision.",
                )

            return cls.create(
                card_id=card.card_id.value,
                target_type=card.target_type,
                target_id=card.target_id.value,
                card_digest=card.digest(),
                status=HumanReviewResolutionStatus.RESOLVED_BY_DECISION,
                rationale="Gateway-resolvable card has a recorded human decision.",
                decision_entry_digest=decision_entry.digest(),
                decision_status=decision_entry.status.value,
            )

        if card.resolution_mode is HumanReviewResolutionMode.MANUAL_INVESTIGATION:
            return cls.create(
                card_id=card.card_id.value,
                target_type=card.target_type,
                target_id=card.target_id.value,
                card_digest=card.digest(),
                status=HumanReviewResolutionStatus.MANUAL_INVESTIGATION_REQUIRED,
                rationale="Card requires manual investigation outside the action gateway.",
            )

        return cls.create(
            card_id=card.card_id.value,
            target_type=card.target_type,
            target_id=card.target_id.value,
            card_digest=card.digest(),
            status=HumanReviewResolutionStatus.BLOCKER_ACKNOWLEDGED,
            rationale="Card documents a blocker that cannot be auto-resolved.",
        )

    def is_resolved(self) -> bool:
        """Return whether this card is resolved by a recorded human decision."""
        return self.status is HumanReviewResolutionStatus.RESOLVED_BY_DECISION

    def requires_operator_attention(self) -> bool:
        """Return whether this card still requires operator attention."""
        return self.status in {
            HumanReviewResolutionStatus.PENDING_DECISION,
            HumanReviewResolutionStatus.MANUAL_INVESTIGATION_REQUIRED,
            HumanReviewResolutionStatus.BLOCKER_ACKNOWLEDGED,
        }

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible card resolution."""
        return {
            "card_id": self.card_id.value,
            "target_type": self.target_type.value,
            "target_id": self.target_id.value,
            "card_digest": {
                "algorithm": self.card_digest.algorithm,
                "value": self.card_digest.value,
            },
            "status": self.status.value,
            "rationale": self.rationale,
            "decision_entry_digest": (
                {
                    "algorithm": self.decision_entry_digest.algorithm,
                    "value": self.decision_entry_digest.value,
                }
                if self.decision_entry_digest is not None
                else None
            ),
            "decision_status": self.decision_status,
            "is_resolved": self.is_resolved(),
            "requires_operator_attention": self.requires_operator_attention(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this card resolution."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class HumanReviewResolutionAudit:
    """Audit showing whether an operator bundle has recorded decisions."""

    bundle_digest: DigestRecord
    decision_ledger_digest: DigestRecord
    state_digest: DigestRecord
    resolutions: tuple[HumanReviewCardResolution, ...]

    @classmethod
    def create(
        cls,
        *,
        bundle_digest: DigestRecord,
        decision_ledger_digest: DigestRecord,
        state_digest: DigestRecord,
        resolutions: tuple[HumanReviewCardResolution, ...],
    ) -> HumanReviewResolutionAudit:
        """Create a normalized human-review resolution audit."""
        bundle_digest.require_algorithm("sha256")
        decision_ledger_digest.require_algorithm("sha256")
        state_digest.require_algorithm("sha256")

        if not resolutions:
            raise FoundationError("human-review resolution audit requires resolutions")

        seen_cards: set[str] = set()
        for resolution in resolutions:
            if resolution.card_id.value in seen_cards:
                raise FoundationError(
                    f"duplicate human-review resolution card: {resolution.card_id.value}"
                )
            seen_cards.add(resolution.card_id.value)

        return cls(
            bundle_digest=bundle_digest,
            decision_ledger_digest=decision_ledger_digest,
            state_digest=state_digest,
            resolutions=resolutions,
        )

    @classmethod
    def from_bundle(
        cls,
        *,
        bundle: HumanReviewOperatorBundle,
        decision_ledger: HumanReviewDecisionLedger,
    ) -> HumanReviewResolutionAudit:
        """Create a resolution audit from an operator bundle and decision ledger."""
        resolutions = tuple(
            HumanReviewCardResolution.from_card(
                card=card,
                decision_entry=_latest_decision_for_card(
                    card=card,
                    decision_ledger=decision_ledger,
                ),
            )
            for card in bundle.packet.cards
        )

        return cls.create(
            bundle_digest=bundle.digest(),
            decision_ledger_digest=decision_ledger.digest(),
            state_digest=bundle.snapshot.state_digest,
            resolutions=resolutions,
        )

    def resolved_count(self) -> int:
        """Return how many cards are resolved by recorded decisions."""
        return sum(1 for resolution in self.resolutions if resolution.is_resolved())

    def pending_decision_count(self) -> int:
        """Return how many gateway-resolvable cards still need decisions."""
        return sum(
            1
            for resolution in self.resolutions
            if resolution.status is HumanReviewResolutionStatus.PENDING_DECISION
        )

    def manual_investigation_count(self) -> int:
        """Return how many cards need manual investigation."""
        return sum(
            1
            for resolution in self.resolutions
            if resolution.status
            is HumanReviewResolutionStatus.MANUAL_INVESTIGATION_REQUIRED
        )

    def blocker_acknowledgment_count(self) -> int:
        """Return how many cards document unresolved blockers."""
        return sum(
            1
            for resolution in self.resolutions
            if resolution.status is HumanReviewResolutionStatus.BLOCKER_ACKNOWLEDGED
        )

    def requires_operator_attention(self) -> bool:
        """Return whether any card still requires operator attention."""
        return any(resolution.requires_operator_attention() for resolution in self.resolutions)

    def all_gateway_decisions_recorded(self) -> bool:
        """Return whether every gateway-resolvable card has a recorded decision."""
        return self.pending_decision_count() == 0

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible human-review resolution audit."""
        resolution_payload: JsonArray = []
        for resolution in self.resolutions:
            resolution_payload.append(resolution.to_payload())

        return {
            "bundle_digest": {
                "algorithm": self.bundle_digest.algorithm,
                "value": self.bundle_digest.value,
            },
            "decision_ledger_digest": {
                "algorithm": self.decision_ledger_digest.algorithm,
                "value": self.decision_ledger_digest.value,
            },
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
            "resolutions": resolution_payload,
            "card_count": len(self.resolutions),
            "resolved_count": self.resolved_count(),
            "pending_decision_count": self.pending_decision_count(),
            "manual_investigation_count": self.manual_investigation_count(),
            "blocker_acknowledgment_count": self.blocker_acknowledgment_count(),
            "requires_operator_attention": self.requires_operator_attention(),
            "all_gateway_decisions_recorded": self.all_gateway_decisions_recorded(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this human-review resolution audit."""
        return DigestRecord.from_payload(self.to_payload())


def _latest_decision_for_card(
    *,
    card: HumanReviewPacketCard,
    decision_ledger: HumanReviewDecisionLedger,
) -> HumanReviewDecisionLedgerEntry | None:
    """Return the latest matching decision entry for a gateway-resolvable card."""
    if (
        card.target_type is not HumanReviewDocketTargetType.BOUNDED_ACTION
        or card.resolution_mode is not HumanReviewResolutionMode.GATEWAY_DECISION
    ):
        return None

    entries = decision_ledger.entries_for_target(
        target_type=HumanReviewTargetType.BOUNDED_ACTION,
        target_id=card.target_id.value,
    )
    if not entries:
        return None

    return entries[-1]
