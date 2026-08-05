

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifactKind
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.memory import MemoryStatus
from ix_sally.memory_decisions import (
    MemoryDecisionAction,
    MnemosyneMemoryDecision,
    MnemosyneMemoryDecisionPacket,
)


def test_mnemosyne_memory_decision_normalizes_fields_and_generates_id() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.KEEP_PENDING,
        rationale="  Candidate lacks enough evidence for truth use. ",
    )

    assert decision.decision_id.value == (
        "ix-mnemosyne-1-keep-pending-candidate-lacks-enough-evidence-for-truth-use"
    )
    assert decision.rationale == "Candidate lacks enough evidence for truth use."
    assert decision.resulting_status is MemoryStatus.PENDING_EVIDENCE
    assert decision.writes_verified_memory() is False
    assert decision.blocks_memory() is False


def test_mnemosyne_memory_decision_rejects_negative_cycle() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})

    with pytest.raises(FoundationError, match="memory decision cycle must not be negative"):
        MnemosyneMemoryDecision.create(
            cycle=-1,
            memory_digest=memory_digest,
            action=MemoryDecisionAction.KEEP_PENDING,
            rationale="Invalid cycle.",
        )


def test_mnemosyne_memory_decision_rejects_non_sha256_memory_digest() -> None:
    memory_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        MnemosyneMemoryDecision.create(
            cycle=1,
            memory_digest=memory_digest,
            action=MemoryDecisionAction.KEEP_PENDING,
            rationale="Invalid digest.",
        )


def test_verified_memory_decision_requires_evidence_digest() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})

    with pytest.raises(FoundationError, match="verified memory decisions require"):
        MnemosyneMemoryDecision.create(
            cycle=1,
            memory_digest=memory_digest,
            action=MemoryDecisionAction.VERIFY,
            rationale="Candidate can be learned.",
        )


def test_verified_memory_decision_accepts_sha256_evidence_digest() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    evidence_digest = DigestRecord.from_payload({"evidence": "passed"})
    decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.VERIFY,
        rationale="Evidence supports verified memory.",
        evidence_digests=(evidence_digest,),
    )

    assert decision.resulting_status is MemoryStatus.VERIFIED
    assert decision.writes_verified_memory() is True
    assert decision.evidence_digests == (evidence_digest,)


def test_memory_decision_rejects_non_sha256_evidence_digest() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    evidence_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        MnemosyneMemoryDecision.create(
            cycle=1,
            memory_digest=memory_digest,
            action=MemoryDecisionAction.VERIFY,
            rationale="Invalid evidence digest.",
            evidence_digests=(evidence_digest,),
        )


def test_blocking_memory_decision_requires_boundary_note() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})

    with pytest.raises(FoundationError, match="blocking memory decisions require"):
        MnemosyneMemoryDecision.create(
            cycle=1,
            memory_digest=memory_digest,
            action=MemoryDecisionAction.QUARANTINE,
            rationale="Candidate is unsafe to learn.",
        )


def test_blocking_memory_decision_records_boundary_note() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.REJECT,
        rationale="Candidate was rejected by boundary policy.",
        boundary_note="Human boundary rejected this memory candidate.",
    )

    assert decision.resulting_status is MemoryStatus.REJECTED
    assert decision.blocks_memory() is True
    assert decision.boundary_note == "Human boundary rejected this memory candidate."


def test_mnemosyne_memory_decision_payload_is_stable() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    evidence_digest = DigestRecord.from_payload({"evidence": "passed"})
    decision = MnemosyneMemoryDecision.create(
        decision_id=CanonicalKey.from_text("decision-one", field_name="decision_id"),
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.VERIFY,
        rationale="Evidence supports verified memory.",
        evidence_digests=(evidence_digest,),
    )

    assert decision.to_payload() == {
        "decision_id": "decision-one",
        "cycle": 1,
        "memory_digest": {
            "algorithm": "sha256",
            "value": memory_digest.value,
        },
        "action": "verify",
        "resulting_status": "verified",
        "rationale": "Evidence supports verified memory.",
        "evidence_digests": [
            {
                "algorithm": "sha256",
                "value": evidence_digest.value,
            }
        ],
        "boundary_note": None,
        "writes_verified_memory": True,
        "blocks_memory": False,
    }


def test_mnemosyne_memory_packet_requires_decision() -> None:
    with pytest.raises(FoundationError, match="requires at least one decision"):
        MnemosyneMemoryDecisionPacket.create(
            cycle=1,
            memory_review_summary="No decisions.",
            decisions=(),
        )


def test_mnemosyne_memory_packet_rejects_cycle_mismatch() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    decision = MnemosyneMemoryDecision.create(
        cycle=2,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.KEEP_PENDING,
        rationale="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="memory decisions must match packet cycle"):
        MnemosyneMemoryDecisionPacket.create(
            cycle=1,
            memory_review_summary="Review memory.",
            decisions=(decision,),
        )


def test_mnemosyne_memory_packet_counts_verified_and_blocked_decisions() -> None:
    verified_digest = DigestRecord.from_payload({"memory": "verified"})
    rejected_digest = DigestRecord.from_payload({"memory": "rejected"})
    evidence_digest = DigestRecord.from_payload({"evidence": "passed"})
    verified = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=verified_digest,
        action=MemoryDecisionAction.VERIFY,
        rationale="Evidence supports verified memory.",
        evidence_digests=(evidence_digest,),
    )
    rejected = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=rejected_digest,
        action=MemoryDecisionAction.REJECT,
        rationale="Candidate should not be learned.",
        boundary_note="Rejected by boundary policy.",
    )
    packet = MnemosyneMemoryDecisionPacket.create(
        cycle=1,
        memory_review_summary="Review memory candidates.",
        decisions=(verified, rejected),
    )

    assert packet.verified_count() == 1
    assert packet.blocked_count() == 1
    assert packet.has_blocker() is True


def test_mnemosyne_memory_packet_converts_to_artifact() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.KEEP_PENDING,
        rationale="Candidate remains pending evidence.",
    )
    packet = MnemosyneMemoryDecisionPacket.create(
        cycle=1,
        memory_review_summary="Review memory candidate.",
        decisions=(decision,),
    )

    artifact = packet.to_artifact()

    assert artifact.role is AgentRole.MNEMOSYNE
    assert artifact.kind is AgentArtifactKind.MEMORY_DECISION
    assert artifact.summary == "IX-Mnemosyne issued 1 memory decision(s)."
    assert artifact.referenced_digests == (decision.digest(),)
    assert artifact.data == packet.to_payload()


def test_mnemosyne_memory_packet_digest_changes_when_decision_changes() -> None:
    memory_digest = DigestRecord.from_payload({"memory": "candidate"})
    first_decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.STAGE_CANDIDATE,
        rationale="Stage the memory candidate.",
    )
    second_decision = MnemosyneMemoryDecision.create(
        cycle=1,
        memory_digest=memory_digest,
        action=MemoryDecisionAction.KEEP_PENDING,
        rationale="Keep the memory pending evidence.",
    )
    first = MnemosyneMemoryDecisionPacket.create(
        cycle=1,
        memory_review_summary="Review memory candidate.",
        decisions=(first_decision,),
    )
    second = MnemosyneMemoryDecisionPacket.create(
        cycle=1,
        memory_review_summary="Review memory candidate.",
        decisions=(second_decision,),
    )

    assert first.digest().value != second.digest().value
