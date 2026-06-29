from __future__ import annotations

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.chamber import StopReason
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.cycles import CycleCoordinationStatus, NinefoldCyclePacket
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.events import RuntimeEvent, RuntimeEventType
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.memory import MemoryRecord
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _runtime_kit() -> NinefoldRuntimeKit:
    contract = AutonomyContract.create(
        goal="Run a bounded state test.",
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRuntimeKit.create(contract=contract)


def _artifact(
    *,
    role: AgentRole,
    kind: AgentArtifactKind,
    cycle: int = 1,
    data: JsonObject | None = None,
) -> AgentArtifact:
    return AgentArtifact.create(
        cycle=cycle,
        role=role,
        kind=kind,
        summary=f"{role.value} artifact.",
        data=data or {},
    )


def _complete_cycle(*, blocked: bool = False) -> NinefoldCyclePacket:
    sentinel_data: JsonObject = {"has_blocker": True} if blocked else {}
    artifacts = (
        _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL),
        _artifact(role=AgentRole.BUTCH, kind=AgentArtifactKind.FALSIFICATION),
        _artifact(role=AgentRole.VERITY, kind=AgentArtifactKind.EVIDENCE_JUDGMENT),
        _artifact(role=AgentRole.ORACLE, kind=AgentArtifactKind.PREDICTION),
        _artifact(role=AgentRole.FORGE, kind=AgentArtifactKind.EXECUTION_RECEIPT),
        _artifact(role=AgentRole.MNEMOSYNE, kind=AgentArtifactKind.MEMORY_DECISION),
        _artifact(
            role=AgentRole.SENTINEL,
            kind=AgentArtifactKind.BOUNDARY_REPORT,
            data=sentinel_data,
        ),
        _artifact(role=AgentRole.TRANSFER, kind=AgentArtifactKind.TRANSFER_RESULT),
        _artifact(role=AgentRole.CLERK, kind=AgentArtifactKind.DOSSIER_ENTRY),
    )
    return NinefoldCyclePacket.create(
        cycle=1,
        cycle_goal="Complete state cycle.",
        artifacts=artifacts,
        status=CycleCoordinationStatus.BLOCKED if blocked else CycleCoordinationStatus.COMPLETE,
    )


def _human_review_decision() -> AuthorityDecision:
    return AuthorityDecision.create(
        cycle=1,
        request_digest=DigestRecord.from_payload({"request": "tool"}),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review required.",
        human_review_note="Boundary review required.",
    )


def test_run_state_create_opens_transcript() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())

    assert len(state.transcript.events) == 1
    assert state.transcript.events[0].event_type is RuntimeEventType.CHAMBER_OPENED
    assert state.next_event_sequence() == 2
    assert state.completed_cycles() == 0
    assert state.requires_human_review() is False


def test_run_state_appends_event_immutably() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    event = RuntimeEvent.create(
        sequence=state.next_event_sequence(),
        cycle=1,
        event_type=RuntimeEventType.CYCLE_STARTED,
        summary="Cycle started.",
    )

    updated = state.with_event(event)

    assert len(state.transcript.events) == 1
    assert len(updated.transcript.events) == 2
    assert updated.transcript.events[-1] == event


def test_run_state_appends_artifact_claim_evidence_and_memory() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    artifact = _artifact(role=AgentRole.SALLY, kind=AgentArtifactKind.PROPOSAL)
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="A bounded claim.",
    )
    evidence = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.CLERK,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Evidence recorded.",
    )
    memory = MemoryRecord.create(
        cycle=1,
        proposed_by=AgentRole.MNEMOSYNE,
        content="Memory candidate.",
    )

    updated = (
        state.with_artifact(artifact)
        .with_claim(claim)
        .with_evidence(evidence)
        .with_memory(memory)
    )

    assert len(updated.artifacts.artifacts) == 1
    assert len(updated.claims.claims) == 1
    assert len(updated.evidence.records) == 1
    assert len(updated.memory.records) == 1


def test_run_state_appends_authority_decision() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    decision = _human_review_decision()

    updated = state.with_authority_decision(decision)

    assert len(state.authority_decisions.decisions) == 0
    assert len(updated.authority_decisions.decisions) == 1
    assert updated.requires_human_review() is True
    assert updated.human_review_authority_count() == 1


def test_run_state_appends_cycle_and_reports_stop_condition() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    updated = state.with_cycle(_complete_cycle())

    assert updated.completed_cycles() == 1
    assert updated.stop_condition_payload() == {
        "should_stop": True,
        "reason": StopReason.MAX_CYCLES_REACHED.value,
        "detail": "completed_cycles=1 reached max_cycles=1",
    }


def test_run_state_detects_human_review_cycles() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    updated = state.with_cycle(_complete_cycle(blocked=True))

    assert updated.requires_human_review() is True
    assert updated.to_payload()["requires_human_review"] is True


def test_run_state_payload_records_ledger_counts_and_digests() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())

    payload = state.to_payload()

    assert payload["runtime_digest"] == state.runtime_kit.digest().value
    assert payload["transcript_digest"] == state.transcript.digest().value
    assert payload["artifact_ledger_digest"] == state.artifacts.digest().value
    assert payload["claim_ledger_digest"] == state.claims.digest().value
    assert payload["evidence_ledger_digest"] == state.evidence.digest().value
    assert payload["memory_ledger_digest"] == state.memory.digest().value
    assert (
        payload["authority_decision_ledger_digest"]
        == state.authority_decisions.digest().value
    )
    assert payload["cycle_ledger_digest"] == state.cycles.digest().value
    assert payload["event_count"] == 1
    assert payload["artifact_count"] == 0
    assert payload["claim_count"] == 0
    assert payload["evidence_count"] == 0
    assert payload["memory_count"] == 0
    assert payload["authority_decision_count"] == 0
    assert payload["completed_cycles"] == 0


def test_run_state_digest_changes_when_state_changes() -> None:
    state = NinefoldRunState.create(runtime_kit=_runtime_kit())
    event = RuntimeEvent.create(
        sequence=state.next_event_sequence(),
        cycle=1,
        event_type=RuntimeEventType.CYCLE_STARTED,
        summary="Cycle started.",
    )

    updated = state.with_event(event)

    assert state.digest().value != updated.digest().value
