from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.claims import ClaimRecord
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence import EvidenceKind, EvidenceRecord, EvidenceStatus
from ix_sally.evidence_support import EvidenceSupportStatus, VerityEvidenceSupportReview
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_results import ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState
from ix_sally.state_audit import (
    StateAuditFinding,
    StateAuditReport,
    StateAuditSeverity,
    StateAuditor,
)


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Audit run state.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _proposed_action() -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "run tests"}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _authorized_action() -> BoundedActionRecord:
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def _failed_forge_result(action: BoundedActionRecord) -> ForgeResultRecord:
    item = ExecutionQueueItem.from_action(action).dispatched()
    return ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.FAILED,
        summary="Forge execution failed.",
        failure_reason="Assertion failed.",
    )


def _supported_finding_state() -> NinefoldRunState:
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


def test_state_audit_finding_payload_is_stable() -> None:
    finding = StateAuditFinding.create(
        finding_id=CanonicalKey.from_text("finding-one", field_name="finding_id"),
        severity=StateAuditSeverity.BLOCKING,
        summary="Action blocked.",
        detail="One action is blocked.",
        reference="actions.blocked",
    )

    assert finding.to_payload() == {
        "finding_id": "finding-one",
        "severity": "blocking",
        "summary": "Action blocked.",
        "detail": "One action is blocked.",
        "reference": "actions.blocked",
        "blocks_chamber_close": True,
    }


def test_state_audit_report_rejects_duplicate_finding_ids() -> None:
    finding = StateAuditFinding.create(
        finding_id=CanonicalKey.from_text("duplicate", field_name="finding_id"),
        severity=StateAuditSeverity.INFO,
        summary="Info.",
        detail="Detail.",
        reference="state",
    )

    with pytest.raises(FoundationError, match="duplicate state audit finding id"):
        StateAuditReport.create(
            state_digest=DigestRecord.from_payload({"state": "digest"}),
            findings=(finding, finding),
        )


def test_state_auditor_reports_ready_state_without_blockers() -> None:
    report = StateAuditor().audit(_supported_finding_state())

    assert report.ready_for_close() is True
    assert report.blocking_findings() == ()
    assert report.to_payload()["ready_for_close"] is True
    assert report.findings[0].severity is StateAuditSeverity.INFO


def test_state_auditor_blocks_on_proposed_actions() -> None:
    state = _state().with_action(_proposed_action())

    report = StateAuditor().audit(state)

    assert report.ready_for_close() is False
    assert report.blocking_findings()[0].reference == "actions.proposed"


def test_state_auditor_blocks_on_human_review_actions() -> None:
    action = _proposed_action()
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review required.",
        human_review_note="Boundary requires human approval.",
    )
    reviewed = action.with_authority_decision(decision)
    state = _state().with_action(reviewed)

    report = StateAuditor().audit(state)

    assert report.ready_for_close() is False
    assert any(finding.reference == "actions.human_review" for finding in report.findings)


def test_state_auditor_warns_on_queued_execution_items() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action)
    state = _state().with_action(action).with_execution_queue_item(item)

    report = StateAuditor().audit(state)

    assert report.ready_for_close() is True
    assert report.warning_findings()[0].reference == "execution_queue.queued"


def test_state_auditor_warns_when_dispatched_items_lack_results() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action).dispatched()
    state = _state().with_action(action).with_execution_queue_item(item)

    report = StateAuditor().audit(state)

    assert report.ready_for_close() is True
    assert any(finding.reference == "execution_queue.dispatched" for finding in report.findings)


def test_state_auditor_blocks_on_failed_forge_results() -> None:
    action = _authorized_action()
    result = _failed_forge_result(action)
    state = _state().with_action(action).with_forge_result(result)

    report = StateAuditor().audit(state)

    assert report.ready_for_close() is False
    assert any(finding.reference == "forge_results.failed" for finding in report.findings)


def test_state_auditor_blocks_on_unsupported_evidence_findings() -> None:
    claim = ClaimRecord.create(
        cycle=1,
        author=AgentRole.SALLY,
        statement="Forge tests passed.",
    )
    finding = VerityEvidenceSupportReview().review_claim(
        claim=claim,
        evidence_records=(),
    )

    assert finding.status is EvidenceSupportStatus.UNSUPPORTED

    state = _state().with_claim(claim).with_evidence_support_finding(finding)
    report = StateAuditor().audit(state)

    assert report.ready_for_close() is False
    assert any(
        finding.reference == "evidence_support.human_review"
        for finding in report.findings
    )


def test_state_audit_digest_changes_when_findings_change() -> None:
    ready = StateAuditor().audit(_supported_finding_state())
    blocked = StateAuditor().audit(_state().with_action(_proposed_action()))

    assert ready.digest().value != blocked.digest().value
