from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.judgments import (
    EvidenceJudgmentStatus,
    VerityEvidenceJudgment,
    VerityJudgmentPacket,
)


def test_verity_evidence_judgment_normalizes_fields_and_generates_id() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})
    judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.PENDING_EVIDENCE,
        rationale="  Claim has no execution receipt yet. ",
        doctrine_key="Output Is Not Evidence",
    )

    assert judgment.judgment_id.value == (
        "ix-verity-1-pending-evidence-claim-has-no-execution-receipt-yet"
    )
    assert judgment.rationale == "Claim has no execution receipt yet."
    assert judgment.doctrine_key is not None
    assert judgment.doctrine_key.value == "output-is-not-evidence"
    assert judgment.supports_claim() is False
    assert judgment.blocks_claim() is False


def test_verity_evidence_judgment_rejects_negative_cycle() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})

    with pytest.raises(FoundationError, match="evidence judgment cycle must not be negative"):
        VerityEvidenceJudgment.create(
            cycle=-1,
            claim_digest=claim_digest,
            status=EvidenceJudgmentStatus.UNSUPPORTED,
            rationale="Invalid cycle.",
        )


def test_verity_evidence_judgment_rejects_non_sha256_claim_digest() -> None:
    claim_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        VerityEvidenceJudgment.create(
            cycle=1,
            claim_digest=claim_digest,
            status=EvidenceJudgmentStatus.UNSUPPORTED,
            rationale="Invalid digest.",
        )


def test_supported_judgment_requires_evidence_digest() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})

    with pytest.raises(FoundationError, match="supported evidence judgments require"):
        VerityEvidenceJudgment.create(
            cycle=1,
            claim_digest=claim_digest,
            status=EvidenceJudgmentStatus.SUPPORTED,
            rationale="Claim is supported.",
        )


def test_supported_judgment_accepts_sha256_evidence_digest() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})
    evidence_digest = DigestRecord.from_payload({"pytest": "passed"})
    judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.SUPPORTED,
        rationale="Execution receipt supports the claim.",
        evidence_digests=(evidence_digest,),
    )

    assert judgment.supports_claim() is True
    assert judgment.evidence_digests == (evidence_digest,)


def test_supported_judgment_rejects_non_sha256_evidence_digest() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})
    evidence_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        VerityEvidenceJudgment.create(
            cycle=1,
            claim_digest=claim_digest,
            status=EvidenceJudgmentStatus.SUPPORTED,
            rationale="Execution receipt supports the claim.",
            evidence_digests=(evidence_digest,),
        )


def test_blocked_judgment_requires_boundary_note() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "complete"})

    with pytest.raises(FoundationError, match="blocked evidence judgments require"):
        VerityEvidenceJudgment.create(
            cycle=1,
            claim_digest=claim_digest,
            status=EvidenceJudgmentStatus.BLOCKED,
            rationale="Claim exceeds authority.",
        )


def test_blocked_judgment_records_boundary_note() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "complete"})
    judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.BLOCKED,
        rationale="Claim exceeds authority.",
        boundary_note="Human boundary approval is required before completion can be claimed.",
    )

    assert judgment.blocks_claim() is True
    assert judgment.boundary_note == (
        "Human boundary approval is required before completion can be claimed."
    )


def test_verity_evidence_judgment_payload_is_stable() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})
    evidence_digest = DigestRecord.from_payload({"pytest": "passed"})
    judgment = VerityEvidenceJudgment.create(
        judgment_id=CanonicalKey.from_text("judgment-one", field_name="judgment_id"),
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.SUPPORTED,
        rationale="Evidence supports the claim.",
        evidence_digests=(evidence_digest,),
        doctrine_key="output-is-not-evidence",
    )

    assert judgment.to_payload() == {
        "judgment_id": "judgment-one",
        "cycle": 1,
        "claim_digest": {
            "algorithm": "sha256",
            "value": claim_digest.value,
        },
        "status": "supported",
        "rationale": "Evidence supports the claim.",
        "evidence_digests": [
            {
                "algorithm": "sha256",
                "value": evidence_digest.value,
            }
        ],
        "doctrine_key": "output-is-not-evidence",
        "boundary_note": None,
    }


def test_verity_judgment_packet_requires_judgment() -> None:
    with pytest.raises(FoundationError, match="requires at least one judgment"):
        VerityJudgmentPacket.create(
            cycle=1,
            review_summary="No judgments.",
            judgments=(),
        )


def test_verity_judgment_packet_rejects_cycle_mismatch() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "code works"})
    judgment = VerityEvidenceJudgment.create(
        cycle=2,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.UNSUPPORTED,
        rationale="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="judgments must match packet cycle"):
        VerityJudgmentPacket.create(
            cycle=1,
            review_summary="Review claim.",
            judgments=(judgment,),
        )


def test_verity_judgment_packet_counts_supported_and_blocked_judgments() -> None:
    supported_claim = DigestRecord.from_payload({"claim": "tests passed"})
    blocked_claim = DigestRecord.from_payload({"claim": "complete"})
    evidence_digest = DigestRecord.from_payload({"pytest": "passed"})
    supported = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=supported_claim,
        status=EvidenceJudgmentStatus.SUPPORTED,
        rationale="Receipt supports claim.",
        evidence_digests=(evidence_digest,),
    )
    blocked = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=blocked_claim,
        status=EvidenceJudgmentStatus.BLOCKED,
        rationale="Completion claim requires boundary approval.",
        boundary_note="Human boundary approval missing.",
    )
    packet = VerityJudgmentPacket.create(
        cycle=1,
        review_summary="Review executable and completion claims.",
        judgments=(supported, blocked),
    )

    assert packet.supported_count() == 1
    assert packet.blocked_count() == 1
    assert packet.has_blocker() is True


def test_verity_judgment_packet_converts_to_artifact() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "needs evidence"})
    judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.PENDING_EVIDENCE,
        rationale="Claim is pending evidence.",
    )
    packet = VerityJudgmentPacket.create(
        cycle=1,
        review_summary="Review pending claim.",
        judgments=(judgment,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.VERITY
    assert artifact.kind is AgentArtifactKind.EVIDENCE_JUDGMENT
    assert artifact.summary == "IX-Verity issued 1 evidence judgment(s)."
    assert artifact.referenced_digests == (judgment.digest(),)
    assert artifact.data == packet.to_payload()


def test_verity_judgment_packet_digest_changes_when_status_changes() -> None:
    claim_digest = DigestRecord.from_payload({"claim": "needs evidence"})
    first_judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.PENDING_EVIDENCE,
        rationale="Claim is pending evidence.",
    )
    second_judgment = VerityEvidenceJudgment.create(
        cycle=1,
        claim_digest=claim_digest,
        status=EvidenceJudgmentStatus.UNSUPPORTED,
        rationale="Claim is unsupported.",
    )
    first = VerityJudgmentPacket.create(
        cycle=1,
        review_summary="Review claim.",
        judgments=(first_judgment,),
    )
    second = VerityJudgmentPacket.create(
        cycle=1,
        review_summary="Review claim.",
        judgments=(second_judgment,),
    )

    assert first.digest().value != second.digest().value
