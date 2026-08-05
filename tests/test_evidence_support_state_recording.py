

from __future__ import annotations

from ix_sally.agents import AgentRole
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.events import RuntimeEventType
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.evidence_support import (
    EvidenceSupportFinding,
    EvidenceSupportStatus,
    VerityEvidenceSupportReview,
)
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record evidence support state.",
        mode=AutonomyMode.TEST,
        max_cycles=1,
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


def _supported_finding() -> EvidenceSupportFinding:
    claim = _claim()
    evidence = _evidence()
    return VerityEvidenceSupportReview().review_claim(
        claim=claim,
        evidence_records=(evidence,),
    )


def _unsupported_finding() -> EvidenceSupportFinding:
    return EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=_claim(statement="No evidence exists.").digest(),
        status=EvidenceSupportStatus.UNSUPPORTED,
        rationale="No recorded same-cycle evidence supports the claim.",
    )


def test_run_state_starts_with_empty_evidence_support_ledger() -> None:
    state = _state()

    assert len(state.evidence_support.findings) == 0
    assert state.supported_evidence_finding_count() == 0
    assert state.human_review_evidence_finding_count() == 0
    assert state.to_payload()["evidence_support_finding_count"] == 0


def test_run_state_appends_supported_evidence_finding_immutably() -> None:
    state = _state()
    finding = _supported_finding()

    updated = state.with_evidence_support_finding(finding)

    assert len(state.evidence_support.findings) == 0
    assert len(updated.evidence_support.findings) == 1
    assert updated.supported_evidence_finding_count() == 1
    assert updated.human_review_evidence_finding_count() == 0
    assert updated.requires_human_review() is False


def test_run_state_counts_unsupported_finding_as_human_review() -> None:
    state = _state()
    finding = _unsupported_finding()

    updated = state.with_evidence_support_finding(finding)

    assert updated.supported_evidence_finding_count() == 0
    assert updated.human_review_evidence_finding_count() == 1
    assert updated.requires_human_review() is True
    assert updated.to_payload()["human_review_evidence_finding_count"] == 1


def test_state_recorder_records_evidence_support_finding_and_event() -> None:
    recorder = StateRecorder()
    state = _state()
    finding = _supported_finding()

    updated = recorder.record_evidence_support_finding(state, finding)

    assert len(updated.evidence_support.findings) == 1
    assert len(updated.transcript.events) == 2

    event = updated.transcript.events[-1]

    assert event.event_type is RuntimeEventType.EVIDENCE_RECORDED
    assert event.actor is AgentRole.VERITY
    assert event.summary == "Recorded evidence support finding: supported."
    assert event.payload["reference_type"] == "evidence-support-finding"
    assert event.payload["reference_digest"] == finding.digest().value


def test_evidence_support_state_digest_changes_when_finding_is_recorded() -> None:
    state = _state()
    finding = _supported_finding()

    updated = state.with_evidence_support_finding(finding)

    assert state.digest().value != updated.digest().value
    assert (
        state.to_payload()["evidence_support_ledger_digest"]
        != updated.to_payload()["evidence_support_ledger_digest"]
    )
