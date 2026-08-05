

from __future__ import annotations

import pytest
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_docket import (
    HumanReviewDocket,
    HumanReviewDocketSeverity,
    HumanReviewDocketTarget,
    HumanReviewDocketTargetType,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_packets import (
    HumanReviewPacket,
    HumanReviewPacketCard,
    HumanReviewResolutionMode,
)


def _digest(label: str) -> DigestRecord:
    return DigestRecord.from_payload({"record": label})


def _target(
    *,
    target_type: HumanReviewDocketTargetType = HumanReviewDocketTargetType.BOUNDED_ACTION,
    target_id: str = "review-action",
    severity: HumanReviewDocketSeverity = HumanReviewDocketSeverity.REVIEW_REQUIRED,
    source_status: str = "human_review_required",
) -> HumanReviewDocketTarget:
    return HumanReviewDocketTarget.create(
        target_type=target_type,
        target_id=target_id,
        cycle=1,
        target_digest=_digest(target_id),
        source_status=source_status,
        severity=severity,
        summary="Review this target.",
        rationale="Human authority is required.",
    )


def _docket(
    *targets: HumanReviewDocketTarget,
) -> HumanReviewDocket:
    digest = _digest("docket")
    return HumanReviewDocket.create(
        state_digest=digest,
        snapshot_digest=digest,
        gate_decision_digest=digest,
        targets=targets,
    )


def test_packet_card_exposes_gateway_decisions_for_review_action() -> None:
    card = HumanReviewPacketCard.from_target(_target())

    assert card.resolution_mode is HumanReviewResolutionMode.GATEWAY_DECISION
    assert card.can_be_resolved_by_gateway() is True
    assert card.decision_options == (
        HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value,
        HumanReviewDecisionStatus.REJECTED.value,
        HumanReviewDecisionStatus.DEFERRED.value,
    )


def test_packet_card_marks_blocker_as_acknowledgment_only() -> None:
    card = HumanReviewPacketCard.from_target(
        _target(
            target_id="blocked-action",
            severity=HumanReviewDocketSeverity.BLOCKER,
            source_status="denied",
        )
    )

    assert card.resolution_mode is HumanReviewResolutionMode.BLOCKER_ACKNOWLEDGMENT
    assert card.acknowledges_blocker_only() is True
    assert card.decision_options == ()


def test_packet_card_marks_evidence_target_as_manual_investigation() -> None:
    card = HumanReviewPacketCard.from_target(
        _target(
            target_type=HumanReviewDocketTargetType.EVIDENCE_SUPPORT_FINDING,
            target_id="unsupported-claim",
            severity=HumanReviewDocketSeverity.REVIEW_REQUIRED,
            source_status="unsupported",
        )
    )

    assert card.resolution_mode is HumanReviewResolutionMode.MANUAL_INVESTIGATION
    assert card.requires_manual_investigation() is True
    assert card.can_be_resolved_by_gateway() is False


def test_human_review_packet_assembles_counts_from_docket() -> None:
    docket = _docket(
        _target(target_id="review-action"),
        _target(
            target_type=HumanReviewDocketTargetType.EVIDENCE_SUPPORT_FINDING,
            target_id="unsupported-claim",
            source_status="unsupported",
        ),
        _target(
            target_id="denied-action",
            severity=HumanReviewDocketSeverity.BLOCKER,
            source_status="denied",
        ),
    )

    packet = HumanReviewPacket.from_docket(docket)
    payload = packet.to_payload()

    assert payload["card_count"] == 3
    assert payload["gateway_resolvable_count"] == 1
    assert payload["manual_investigation_count"] == 1
    assert payload["blocker_acknowledgment_count"] == 1
    assert packet.requires_human_authority() is True


def test_human_review_packet_rejects_duplicate_cards() -> None:
    card = HumanReviewPacketCard.from_target(_target())
    digest = _digest("packet")

    with pytest.raises(FoundationError, match="duplicate human-review packet card"):
        HumanReviewPacket.create(
            docket_digest=digest,
            state_digest=digest,
            snapshot_digest=digest,
            gate_decision_digest=digest,
            cards=(card, card),
            authority_note="Human authority required.",
        )


def test_human_review_packet_card_rejects_duplicate_decision_options() -> None:
    with pytest.raises(FoundationError, match="decision options must be unique"):
        HumanReviewPacketCard.create(
            target_type=HumanReviewDocketTargetType.BOUNDED_ACTION,
            target_id="review-action",
            cycle=1,
            severity=HumanReviewDocketSeverity.REVIEW_REQUIRED,
            source_status="human_review_required",
            summary="Review this target.",
            rationale="Human authority required.",
            target_digest=_digest("review-action"),
            resolution_mode=HumanReviewResolutionMode.GATEWAY_DECISION,
            decision_options=("deferred", "deferred"),
            warning="Human decision required.",
        )


def test_human_review_packet_payload_and_digest_are_stable() -> None:
    docket = _docket(_target(target_id="review-action"))

    first = HumanReviewPacket.from_docket(docket)
    second = HumanReviewPacket.from_docket(docket)

    payload = first.to_payload()

    assert payload["requires_human_authority"] is True
    assert payload["gateway_resolvable_count"] == 1
    assert payload["cards"][0]["target_id"] == "review-action"
    assert first.digest() == second.digest()
