from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimLedger, ClaimRecord, ClaimStatus
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def test_claim_ledger_requires_existing_claim_by_id() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
    )
    ledger = ClaimLedger.create((claim,))

    assert ledger.require_claim(claim.claim_id.value) == claim


def test_claim_ledger_rejects_unknown_claim_id() -> None:
    ledger = ClaimLedger.create(())

    with pytest.raises(FoundationError, match="unknown claim id"):
        ledger.require_claim("missing-claim")


def test_claim_record_tracks_human_review_statuses() -> None:
    support = DigestRecord.from_payload({"forge": "passed"})
    supported = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
        status=ClaimStatus.SUPPORTED,
        support_digests=(support,),
    )
    unsupported = supported.with_status(ClaimStatus.UNSUPPORTED)
    contradicted = supported.with_status(ClaimStatus.CONTRADICTED)

    assert supported.requires_human_review() is False
    assert unsupported.requires_human_review() is True
    assert contradicted.requires_human_review() is True


def test_claim_ledger_filters_supported_and_human_review_claims() -> None:
    support = DigestRecord.from_payload({"forge": "passed"})
    supported = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
        status=ClaimStatus.SUPPORTED,
        support_digests=(support,),
    )
    partial = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Oracle forecast partially matched.",
        status=ClaimStatus.PARTIAL,
    )
    ledger = ClaimLedger.create((supported, partial))

    assert ledger.supported_claims() == (supported,)
    assert ledger.human_review_claims() == (partial,)
