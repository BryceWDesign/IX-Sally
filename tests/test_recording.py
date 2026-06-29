from __future__ import annotations

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.cycles import NinefoldCyclePacket
from ix_sally.digest import DigestRecord
from ix_sally.events import RuntimeEventType
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.memory import MemoryRecord
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _runtime_state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Run recorder test.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=2,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _artifact(
    *,
    role: AgentRole,
    kind: AgentArtifactKind,
    cycle: int = 1,
) -> AgentArtifact:
    return AgentArtifact.create(
        cycle=cycle,
        role=role,
        kind=kind,
        summary=f"{role.value} artifact.",
    )


def _complete_cycle() -> NinefoldCyclePacket:
    artifacts = (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL),
        _artifact(role=AgentRole.BUTCH, kind=AgentArtifactKind.FALSIFICATION),
        _artifact(role=AgentRole.VERITY, kind=AgentArtifactKind.EVIDENCE_JUDGMENT),
        _artifact(role=AgentRole.ORACLE, kind=AgentArtifactKind.PREDICTION),
        _artifact(role=AgentRole.FORGE, kind=AgentArtifactKind.EXECUTION_RECEIPT),
        _artifact(role=AgentRole.MNEMOSYNE, kind=AgentArtifactKind.MEMORY_DECISION),
        _artifact(role=AgentRole.SENTINEL, kind=AgentArtifactKind.BOUNDARY_REPORT),
        _artifact(role=AgentRole.TRANSFER, kind=AgentArtifactKind.TRANSFER_RESULT),
        _artifact(role=AgentRole.CLERK, kind=AgentArtifactKind.DOSSIER_ENTRY),
    )
    return NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Complete recorder cycle.",
        artifacts=artifacts,
    )


def test_state_recorder_records_artifact_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    artifact = _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL)

    updated = recorder.record_artifact(state, artifact)

    assert len(updated.artifacts.artifacts) == 1
    assert len(updated.transcript.events) == 2
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.SALLY
    assert event.payload["reference_type"] == "agent-artifact"
    assert event.payload["reference_digest"] == artifact.digest().value


def test_state_recorder_records_claim_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="A bounded claim.",
    )

    updated = recorder.record_claim(state, claim)

    assert len(updated.claims.claims) == 1
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.AGENT_ARTIFACT_RECORDED
    assert event.actor is AgentRole.SALLY
    assert event.payload["reference_type"] == "claim-record"
    assert event.payload["reference_digest"] == claim.digest().value


def test_state_recorder_records_evidence_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    evidence = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Evidence recorded.",
    )

    updated = recorder.record_evidence(state, evidence)

    assert len(updated.evidence.records) == 1
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.EVIDENCE_RECORDED
    assert event.actor is AgentRole.CLERK
    assert event.payload["reference_type"] == "evidence-record"
    assert event.payload["reference_digest"] == evidence.digest().value


def test_state_recorder_records_memory_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    memory = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Memory candidate.",
    )

    updated = recorder.record_memory(state, memory)

    assert len(updated.memory.records) == 1
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.MEMORY_DECIDED
    assert event.actor is AgentRole.MNEMOSYNE
    assert event.payload["reference_type"] == "memory-record"
    assert event.payload["reference_digest"] == memory.digest().value


def test_state_recorder_records_authority_decision_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=DigestRecord.from_payload({"request": "tool"}),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review required.",
        human_review_note="Boundary review required.",
    )

    updated = recorder.record_authority_decision(state, decision)

    assert len(updated.authority_decisions.decisions) == 1
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.JURISDICTION_DECIDED
    assert event.actor is None
    assert event.payload["reference_type"] == "authority-decision"
    assert event.payload["reference_digest"] == decision.digest().value


def test_state_recorder_records_cycle_and_event() -> None:
    recorder = StateRecorder()
    state = _runtime_state()
    cycle = _complete_cycle()

    updated = recorder.record_cycle(state, cycle)

    assert len(updated.cycles.cycles) == 1
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.CYCLE_STOPPED
    assert event.actor is None
    assert event.payload["reference_type"] == "ninefold-cycle"
    assert event.payload["reference_digest"] == cycle.digest().value


def test_state_recorder_closes_chamber_with_state_digest() -> None:
    recorder = StateRecorder()
    state = _runtime_state()

    updated = recorder.close_chamber(state, summary="Chamber closed by test.")

    assert len(updated.transcript.events) == 2
    event = updated.transcript.events[-1]
    assert event.event_type is RuntimeEventType.CHAMBER_CLOSED
    assert event.summary == "Chamber closed by test."
    assert event.payload["state_digest"] == state.digest().value
    assert event.payload["completed_cycles"] == 0
    assert event.payload["requires_human_review"] is False
