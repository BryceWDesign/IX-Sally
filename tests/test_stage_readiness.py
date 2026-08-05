

from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact, AgentArtifactKind
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.cycles import CycleCoordinationStatus, NinefoldCyclePacket
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage, RunStageCounts, RunStageSnapshot
from ix_sally.state import NinefoldRunState


def _state(*, max_cycles: int = 2) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Inspect stage readiness.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _authorized_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    action = _proposed_action(description=description)
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed by contract.",
    )
    return action.with_authority_decision(decision)


def _artifact(
    *,
    role: AgentRole,
    kind: AgentArtifactKind,
    data: JsonObject | None = None,
) -> AgentArtifact:
    return AgentArtifact.create(
        cycle=1,
        role=role,
        kind=kind,
        summary=f"{role.value} artifact.",
        data=data or {},
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
        cycle_goal="Complete readiness cycle.",
        artifacts=artifacts,
        status=CycleCoordinationStatus.COMPLETE,
    )


def test_stage_snapshot_routes_fresh_state_to_proposal_intake() -> None:
    snapshot = RunStageSnapshot.from_state(_state())

    assert snapshot.stage is RunStage.PROPOSAL_INTAKE
    assert snapshot.requires_human_review() is False
    assert snapshot.ready_for_chamber_close() is False
    assert snapshot.counts.completed_cycles == 0


def test_stage_snapshot_routes_proposed_actions_to_authority_processing() -> None:
    state = _state().with_action(_proposed_action())
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.AUTHORITY_PROCESSING
    assert snapshot.counts.proposed_actions == 1


def test_stage_snapshot_routes_unqueued_authorized_actions_to_execution_planning() -> None:
    state = _state().with_action(_authorized_action())
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.EXECUTION_PLANNING
    assert snapshot.counts.executable_actions == 1
    assert snapshot.counts.pending_execution_planning == 1


def test_stage_snapshot_routes_queued_items_to_forge_dispatch() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action)
    state = _state().with_action(action).with_execution_queue_item(item)
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.FORGE_DISPATCH
    assert snapshot.counts.pending_execution_planning == 0
    assert snapshot.counts.queued_executions == 1


def test_stage_snapshot_routes_dispatched_items_to_forge_result_processing() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action).dispatched()
    state = _state().with_action(action).with_execution_queue_item(item)
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.FORGE_RESULT_PROCESSING
    assert snapshot.counts.pending_forge_results == 1


def test_stage_snapshot_routes_unreviewed_claims_to_evidence_support_review() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
    )
    state = _state().with_claim(claim)
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.EVIDENCE_SUPPORT_REVIEW
    assert snapshot.counts.claims == 1
    assert snapshot.counts.unreviewed_claims == 1


def test_stage_counts_ignore_reviewed_claims() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
    )
    finding = EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=claim.digest(),
        status=EvidenceSupportStatus.SUPPORTED,
        rationale="Recorded evidence supports the claim.",
        evidence_digests=(DigestRecord.from_payload({"evidence": "passed"}),),
    )
    state = _state().with_claim(claim).with_evidence_support_finding(finding)
    counts = RunStageCounts.from_state(state)

    assert counts.unreviewed_claims == 0
    assert counts.evidence_support_findings == 1


def test_stage_snapshot_routes_human_review_before_other_work() -> None:
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Boundary review required.",
        human_review_note="Human boundary must approve this action.",
    )
    reviewed_action = action.with_authority_decision(decision)
    state = _state().with_action(reviewed_action).with_claim(
        ClaimRecord.create(
            cycle=1,
            author=AgentRole.SALLY,
            statement="Forge tests passed.",
        )
    )
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.HUMAN_REVIEW
    assert snapshot.requires_human_review() is True


def test_stage_snapshot_routes_stopped_clean_state_to_chamber_close_ready() -> None:
    state = _state(max_cycles=1).with_cycle(_complete_cycle())
    snapshot = RunStageSnapshot.from_state(state)

    assert snapshot.stage is RunStage.CHAMBER_CLOSE_READY
    assert snapshot.ready_for_chamber_close() is True
    assert snapshot.stop_condition_active is True
    assert snapshot.stop_reason == "max_cycles_reached"


def test_stage_snapshot_payload_and_digest_are_stable() -> None:
    state = _state().with_action(_proposed_action())
    snapshot = RunStageSnapshot.from_state(state)

    payload = snapshot.to_payload()

    assert payload["state_digest"]["value"] == state.digest().value
    assert payload["stage"] == RunStage.AUTHORITY_PROCESSING.value
    assert snapshot.digest() == RunStageSnapshot.from_state(state).digest()
