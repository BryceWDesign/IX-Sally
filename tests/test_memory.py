from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.memory import MemoryLedger, MemoryRecord, MemoryStatus


def test_memory_record_normalizes_content_and_generates_id() -> None:
    record = MemoryRecord.create(
        cycle=2,
        proposed_by=AgentRole.MNEMOSYNE,
        content="  Failed repair pattern should be quarantined.  ",
    )

    assert record.memory_id.value == ("ix-mnemosyne-2-failed-repair-pattern-should-be-quarantined")
    assert record.content == "Failed repair pattern should be quarantined."
    assert record.status is MemoryStatus.CANDIDATE
    assert record.is_truth_claim is False


def test_memory_record_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="memory cycle must not be negative"):
        MemoryRecord.create(
            cycle=-1,
            proposed_by=AgentRole.MNEMOSYNE,
            content="Invalid cycle.",
        )


def test_verified_memory_requires_evidence_digest() -> None:
    with pytest.raises(FoundationError, match="verified memory requires"):
        MemoryRecord.create(
            cycle=1,
            proposed_by=AgentRole.MNEMOSYNE,
            content="A verified lesson.",
            status=MemoryStatus.VERIFIED,
        )


def test_verified_memory_accepts_sha256_evidence_digest() -> None:
    evidence = DigestRecord.from_payload({"test": "passed"})
    record = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="A verified lesson.",
        status=MemoryStatus.VERIFIED,
        evidence_digests=(evidence,),
    )

    assert record.is_truth_claim is True
    assert record.evidence_digests == (evidence,)


def test_memory_record_rejects_non_sha256_evidence_digest() -> None:
    evidence = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        MemoryRecord.create(
            cycle=1,
            proposed_by=AgentRole.MNEMOSYNE,
            content="A verified lesson.",
            status=MemoryStatus.VERIFIED,
            evidence_digests=(evidence,),
        )


def test_blocked_memory_statuses_require_reason() -> None:
    with pytest.raises(FoundationError, match="reason must not be empty"):
        MemoryRecord.create(
            cycle=1,
            proposed_by=AgentRole.MNEMOSYNE,
            content="Unsafe memory.",
            status=MemoryStatus.QUARANTINED,
        )


def test_memory_record_with_status_preserves_memory_id() -> None:
    record = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="A memory candidate.",
    )
    quarantined = record.with_status(
        MemoryStatus.QUARANTINED,
        reason="Contradicted by evidence.",
    )

    assert quarantined.memory_id == record.memory_id
    assert quarantined.status is MemoryStatus.QUARANTINED
    assert quarantined.reason == "Contradicted by evidence."


def test_memory_record_payload_is_stable() -> None:
    evidence = DigestRecord.from_payload({"test": "passed"})
    record = MemoryRecord.create(
        memory_id=CanonicalKey.from_text("memory-one", field_name="memory_id"),
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="A verified memory.",
        status=MemoryStatus.VERIFIED,
        evidence_digests=(evidence,),
        reason="Evidence supports retention.",
    )

    assert record.to_payload() == {
        "memory_id": "memory-one",
        "cycle": 1,
        "proposed_by": "ix-mnemosyne",
        "content": "A verified memory.",
        "status": "verified",
        "evidence_digests": [
            {
                "algorithm": "sha256",
                "value": evidence.value,
            }
        ],
        "reason": "Evidence supports retention.",
    }


def test_memory_ledger_rejects_duplicate_memory_ids() -> None:
    memory_id = CanonicalKey.from_text("same-memory", field_name="memory_id")
    first = MemoryRecord.create(
        memory_id=memory_id,
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="First memory.",
    )
    second = MemoryRecord.create(
        memory_id=memory_id,
        cycle=1,
        proposed_by=AgentRole.SALLY,
        content="Second memory.",
    )

    with pytest.raises(FoundationError, match="duplicate memory id"):
        MemoryLedger.create((first, second))


def test_memory_ledger_filters_truth_and_blocked_records() -> None:
    evidence = DigestRecord.from_payload({"test": "passed"})
    verified = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Verified memory.",
        status=MemoryStatus.VERIFIED,
        evidence_digests=(evidence,),
    )
    quarantined = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Quarantined memory.",
        status=MemoryStatus.QUARANTINED,
        reason="Unsupported claim.",
    )
    candidate = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Candidate memory.",
    )
    ledger = MemoryLedger.create((verified, quarantined, candidate))

    assert ledger.truth_claims() == (verified,)
    assert ledger.blocked_records() == (quarantined,)
    assert ledger.by_status(MemoryStatus.CANDIDATE) == (candidate,)


def test_memory_ledger_appends_and_requires_record() -> None:
    record = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Candidate memory.",
    )
    ledger = MemoryLedger.create(()).append(record)

    assert ledger.require_memory(record.memory_id.value) == record

    with pytest.raises(FoundationError, match="unknown memory id"):
        ledger.require_memory("missing-memory")


def test_memory_ledger_digest_changes_when_memory_status_changes() -> None:
    candidate = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Candidate memory.",
    )
    rejected = candidate.with_status(
        MemoryStatus.REJECTED,
        reason="Human boundary rejected this memory.",
    )

    assert (
        MemoryLedger.create((candidate,)).digest().value
        != MemoryLedger.create((rejected,)).digest().value
    )
