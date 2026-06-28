from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.evidence import EvidenceKind, EvidenceLedger, EvidenceRecord, EvidenceStatus
from ix_sally.foundation import CanonicalKey, FoundationError


def test_evidence_record_normalizes_summary_and_generates_id() -> None:
    record = EvidenceRecord.create(
        cycle=2,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.PASSED,
        summary="  pytest passed inside sandbox. ",
        subject_claim_id="Claim One",
        data={"exit_code": 0},
    )

    assert record.evidence_id.value == "ix-forge-2-test-result-pytest-passed-inside-sandbox"
    assert record.summary == "pytest passed inside sandbox."
    assert record.subject_claim_id == CanonicalKey.from_text("claim-one", field_name="claim_id")
    assert record.data == {"exit_code": 0}


def test_evidence_record_rejects_negative_cycle() -> None:
    with pytest.raises(FoundationError, match="evidence cycle must not be negative"):
        EvidenceRecord.create(
            cycle=-1,
            produced_by=AgentRole.FORGE,
            kind=EvidenceKind.EXECUTION_RECEIPT,
            status=EvidenceStatus.FAILED,
            summary="Invalid cycle.",
        )


def test_evidence_record_payload_is_stable() -> None:
    record = EvidenceRecord.create(
        evidence_id=CanonicalKey.from_text("test-receipt", field_name="evidence_id"),
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.EXECUTION_RECEIPT,
        status=EvidenceStatus.PASSED,
        summary="Command completed.",
        subject_claim_id="claim-one",
        data={"command": "pytest", "exit_code": 0},
    )

    assert record.to_payload() == {
        "evidence_id": "test-receipt",
        "cycle": 1,
        "produced_by": "ix-forge",
        "kind": "execution_receipt",
        "status": "passed",
        "summary": "Command completed.",
        "subject_claim_id": "claim-one",
        "data": {"command": "pytest", "exit_code": 0},
    }


def test_evidence_ledger_rejects_duplicate_evidence_ids() -> None:
    evidence_id = CanonicalKey.from_text("same-evidence", field_name="evidence_id")
    first = EvidenceRecord.create(
        evidence_id=evidence_id,
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.PASSED,
        summary="First record.",
    )
    second = EvidenceRecord.create(
        evidence_id=evidence_id,
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Second record.",
    )

    with pytest.raises(FoundationError, match="duplicate evidence id"):
        EvidenceLedger.create((first, second))


def test_evidence_ledger_appends_and_requires_record() -> None:
    record = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Cycle opened.",
    )
    ledger = EvidenceLedger.create(()).append(record)

    assert ledger.require_evidence(record.evidence_id.value) == record

    with pytest.raises(FoundationError, match="unknown evidence id"):
        ledger.require_evidence("missing-evidence")


def test_evidence_ledger_filters_by_status_and_claim() -> None:
    passed = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.PASSED,
        summary="Test passed.",
        subject_claim_id="claim-one",
    )
    failed = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.FAILED,
        summary="Test failed.",
        subject_claim_id="claim-one",
    )
    unrelated = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Unrelated observation.",
        subject_claim_id="claim-two",
    )
    ledger = EvidenceLedger.create((passed, failed, unrelated))

    assert ledger.by_status(EvidenceStatus.PASSED) == (passed,)
    assert ledger.for_claim("claim-one") == (passed, failed)
    assert ledger.passed_for_claim("claim-one") == (passed,)


def test_evidence_ledger_digest_changes_when_evidence_status_changes() -> None:
    first = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.PASSED,
        summary="Test passed.",
    )
    second = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.TEST_RESULT,
        status=EvidenceStatus.FAILED,
        summary="Test passed.",
    )

    assert EvidenceLedger.create((first,)).digest().value != EvidenceLedger.create(
        (second,)
    ).digest().value
