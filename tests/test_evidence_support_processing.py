from __future__ import annotations

import pytest

from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.evidence_support import EvidenceSupportStatus
from ix_sally.evidence_support_processing import EvidenceSupportProcessor
from ix_sally.events import RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Process claim evidence support.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _claim(*, statement: str = "Forge tests passed.") -> ClaimRecord:
    return ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement=statement,
    )


def _evidence(*, summary: str = "Forge result passed: tests passed.") -> EvidenceRecord:
    return EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary=summary,
    )


def test_evidence_support_processor_reviews_and_records_supported_claim() -> None:
    claim = _claim()
    evidence = _evidence()
    state = _state().with_claim(claim).with_evidence(evidence)
    processor = EvidenceSupportProcessor(StateRecorder())

    result = processor.process_claim(state=state, claim=claim)

    assert result.claim == claim
    assert result.finding.status is EvidenceSupportStatus.SUPPORTED
    assert result.finding.supports_claim() is True
    assert result.state.supported_evidence_finding_count() == 1
    assert result.state.requires_human_review() is False


def test_evidence_support_processor_records_expected_event() -> None:
    claim = _claim()
    evidence = _evidence()
    state = _state().with_claim(claim).with_evidence(evidence)
    processor = EvidenceSupportProcessor(StateRecorder())

    result = processor.process_claim(state=state, claim=claim)

    event = result.state.transcript.events[-1]

    assert event.event_type is RuntimeEventType.EVIDENCE_RECORDED
    assert event.actor is AgentRole.VERITY
    assert event.summary == "Recorded evidence support finding: supported."
    assert event.payload["reference_type"] == "evidence-support-finding"


def test_evidence_support_processor_rejects_claim_not_in_state() -> None:
    claim = _claim()
    processor = EvidenceSupportProcessor(StateRecorder())

    with pytest.raises(FoundationError, match="unknown claim id"):
        processor.process_claim(state=_state(), claim=claim)


def test_evidence_support_processor_rejects_stale_claim_payload() -> None:
    claim = _claim(statement="Forge tests passed.")
    changed = _claim(statement="Forge tests failed.")
    state = _state().with_claim(claim)
    processor = EvidenceSupportProcessor(StateRecorder())

    with pytest.raises(FoundationError, match="claim does not match state ledger"):
        processor.process_claim(state=state, claim=changed)


def test_evidence_support_processor_rejects_duplicate_claim_review() -> None:
    claim = _claim()
    evidence = _evidence()
    state = _state().with_claim(claim).with_evidence(evidence)
    processor = EvidenceSupportProcessor(StateRecorder())

    first = processor.process_claim(state=state, claim=claim)

    with pytest.raises(FoundationError, match="already has an evidence support finding"):
        processor.process_claim(state=first.state, claim=claim)


def test_evidence_support_processor_processes_all_unreviewed_claims() -> None:
    first = _claim(statement="Forge tests passed.")
    second = _claim(statement="Oracle prediction recorded.")
    evidence = _evidence(summary="Forge result passed: tests passed.")
    state = _state().with_claim(first).with_claim(second).with_evidence(evidence)
    processor = EvidenceSupportProcessor(StateRecorder())

    result = processor.process_all_unreviewed(state=state)

    assert result.processed_count() == 2
    assert result.supported_count() == 1
    assert result.human_review_count() == 1
    assert result.state.supported_evidence_finding_count() == 1
    assert result.state.human_review_evidence_finding_count() == 1
    assert result.state.requires_human_review() is True


def test_evidence_support_processor_skips_already_reviewed_claims_in_batch() -> None:
    first = _claim(statement="Forge tests passed.")
    second = _claim(statement="Oracle prediction recorded.")
    evidence = _evidence(summary="Forge result passed: tests passed.")
    state = _state().with_claim(first).with_claim(second).with_evidence(evidence)
    processor = EvidenceSupportProcessor(StateRecorder())

    first_pass = processor.process_claim(state=state, claim=first)
    second_pass = processor.process_all_unreviewed(state=first_pass.state)

    assert second_pass.processed_count() == 1
    assert second_pass.processed[0].claim == second


def test_evidence_support_processing_digest_changes_when_review_changes() -> None:
    claim = _claim()
    supporting = _evidence(summary="Forge result passed: tests passed.")
    contradicting = _evidence(summary="Forge tests failed with assertion failure.")
    processor = EvidenceSupportProcessor(StateRecorder())

    supported = processor.process_claim(
        state=_state().with_claim(claim).with_evidence(supporting),
        claim=claim,
    )
    contradicted = processor.process_claim(
        state=_state().with_claim(claim).with_evidence(contradicting),
        claim=claim,
    )

    assert supported.digest().value != contradicted.digest().value
