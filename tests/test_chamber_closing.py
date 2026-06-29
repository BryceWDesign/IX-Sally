from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.chamber_closing import ChamberCloseStatus, ChamberCloser
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.evidence_support import VerityEvidenceSupportReview
from ix_sally.events import RuntimeEventType
from ix_sally.recording import StateRecorder
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState
from ix_sally.state_audit import StateAuditor


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Close chamber under audit.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _ready_state() -> NinefoldRunState:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
    )
    evidence = EvidenceRecord.create(
        cycle=1,
        produced_by=AgentRole.FORGE,
        kind=EvidenceKind.OBSERVATION,
        status=EvidenceStatus.RECORDED,
        summary="Forge result passed: tests passed.",
    )
    finding = VerityEvidenceSupportReview().review_claim(
        claim=claim,
        evidence_records=(evidence,),
    )
    return _state().with_claim(claim).with_evidence(evidence).with_evidence_support_finding(finding)


def _proposed_action_state() -> NinefoldRunState:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    return _state().with_action(action)


def test_chamber_closer_closes_ready_state() -> None:
    closer = ChamberCloser(StateRecorder(), StateAuditor())
    state = _ready_state()

    result = closer.close_if_ready(
        state=state,
        summary="Chamber closed after audit passed.",
    )

    assert result.status is ChamberCloseStatus.CLOSED
    assert result.closed() is True
    assert result.blocked() is False
    assert result.audit_report.ready_for_close() is True
    assert len(result.state.transcript.events) == len(state.transcript.events) + 1

    event = result.state.transcript.events[-1]

    assert event.event_type is RuntimeEventType.CHAMBER_CLOSED
    assert event.summary == "Chamber closed after audit passed."
    assert event.payload["completed_cycles"] == state.completed_cycles()


def test_chamber_closer_blocks_state_with_audit_blockers() -> None:
    closer = ChamberCloser(StateRecorder(), StateAuditor())
    state = _proposed_action_state()

    result = closer.close_if_ready(
        state=state,
        summary="Attempt close.",
    )

    assert result.status is ChamberCloseStatus.BLOCKED
    assert result.closed() is False
    assert result.blocked() is True
    assert result.audit_report.ready_for_close() is False
    assert result.state == state
    assert len(result.state.transcript.events) == len(state.transcript.events)


def test_chamber_close_result_payload_is_stable_for_blocked_close() -> None:
    closer = ChamberCloser(StateRecorder(), StateAuditor())
    state = _proposed_action_state()

    result = closer.close_if_ready(
        state=state,
        summary="Attempt close.",
    )

    assert result.to_payload() == {
        "state_digest": state.digest().value,
        "audit_report_digest": result.audit_report.digest().value,
        "status": "blocked",
        "summary": "Chamber close blocked by state audit.",
        "closed": False,
        "blocked": True,
        "blocking_count": len(result.audit_report.blocking_findings()),
        "warning_count": len(result.audit_report.warning_findings()),
        "ready_for_close": False,
    }


def test_chamber_close_result_digest_changes_when_status_changes() -> None:
    closer = ChamberCloser(StateRecorder(), StateAuditor())

    closed = closer.close_if_ready(
        state=_ready_state(),
        summary="Chamber closed after audit passed.",
    )
    blocked = closer.close_if_ready(
        state=_proposed_action_state(),
        summary="Attempt close.",
    )

    assert closed.digest().value != blocked.digest().value
