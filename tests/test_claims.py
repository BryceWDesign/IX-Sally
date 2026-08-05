

from __future__ import annotations

import pytest
from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimLedger, ClaimRecord, ClaimStatus
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError


def test_claim_record_normalizes_statement_and_generates_id() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="  This patch is ready for review. ",
    )

    assert claim.claim_id.value == "ix-sally-1-this-patch-is-ready-for-review"
    assert claim.statement == "This patch is ready for review."
    assert claim.status is ClaimStatus.PROPOSED


def test_claim_record_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="claim cycle must not be negative"):
        ClaimRecord.create(
            cycle=-1,
            author=AgentRole.SALLY,
            statement="Invalid cycle.",
        )


def test_supported_claim_requires_support_digest() -> None:
    with pytest.raises(FoundationError, match="supported claims require"):
        ClaimRecord.create(
            cycle=1,
            author=AgentRole.VERITY,
            statement="The evidence supports the claim.",
            status=ClaimStatus.SUPPORTED,
        )


def test_supported_claim_accepts_sha256_support_digest() -> None:
    support = DigestRecord.from_payload({"test": "passed"})
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.VERITY,
        statement="The evidence supports the claim.",
        status=ClaimStatus.SUPPORTED,
        support_digests=(support,),
    )

    assert claim.support_digests == (support,)
    assert claim.to_payload()["support_digests"] == [
        {
            "algorithm": "sha256",
            "value": support.value,
        }
    ]


def test_claim_record_rejects_non_sha256_support_digest() -> None:
    support = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        ClaimRecord.create(
            cycle=1,
            author=AgentRole.VERITY,
            statement="The evidence supports the claim.",
            status=ClaimStatus.SUPPORTED,
            support_digests=(support,),
        )


def test_claim_record_with_status_preserves_claim_id() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.BUTCH,
        statement="The plan lacks evidence.",
    )
    blocked = claim.with_status(ClaimStatus.BLOCKED)

    assert blocked.claim_id == claim.claim_id
    assert blocked.status is ClaimStatus.BLOCKED
    assert blocked.statement == claim.statement


def test_claim_ledger_rejects_duplicate_claim_ids() -> None:
    claim_id = CanonicalKey.from_text("same-claim", field_name="claim_id")
    first = ClaimRecord.create(
        claim_id=claim_id,
        cycle=1,
        author=AgentRole.SALLY,
        statement="First claim.",
    )
    second = ClaimRecord.create(
        claim_id=claim_id,
        cycle=1,
        author=AgentRole.BUTCH,
        statement="Second claim.",
    )

    with pytest.raises(FoundationError, match="duplicate claim id"):
        ClaimLedger.create((first, second))


def test_claim_ledger_appends_and_requires_claim() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="A bounded proposal exists.",
    )
    ledger = ClaimLedger.create(()).append(claim)

    assert ledger.require_claim(claim.claim_id.value) == claim

    with pytest.raises(FoundationError, match="unknown claim id"):
        ledger.require_claim("missing-claim")


def test_claim_ledger_filters_by_status() -> None:
    proposed = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="A proposed claim.",
    )
    unsupported = ClaimRecord.create(
        cycle=1,
        author=AgentRole.VERITY,
        statement="An unsupported claim.",
        status=ClaimStatus.UNSUPPORTED,
    )
    ledger = ClaimLedger.create((proposed, unsupported))

    assert ledger.by_status(ClaimStatus.PROPOSED) == (proposed,)
    assert ledger.by_status(ClaimStatus.UNSUPPORTED) == (unsupported,)


def test_claim_ledger_digest_changes_when_claim_status_changes() -> None:
    proposed = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="A proposed claim.",
    )
    blocked = proposed.with_status(ClaimStatus.BLOCKED)

    assert (
        ClaimLedger.create((proposed,)).digest().value
        != ClaimLedger.create((blocked,)).digest().value
    )
