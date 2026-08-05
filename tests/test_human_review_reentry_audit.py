

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import (
    HumanReviewReentryAuditFinding,
    HumanReviewReentryAuditReport,
    HumanReviewReentryAuditSeverity,
    HumanReviewReentryAuditStatus,
    HumanReviewReentryAuditor,
)
from ix_sally.human_review_reentry_coordination import HumanReviewReentryCoordinator
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Audit certified human-review reentry coordination.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run audited post-review verification.",
) -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": description},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human boundary approval is required before the tool run.",
        human_review_note="Reviewer must approve the bounded tool action.",
    )
    return action.with_authority_decision(decision)


def _resume_operation():
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    kit = HumanReviewWorkflowKit.create()
    handoff = kit.open_handoff(run_state=run_state)
    decision = kit.record_action_decision(
        run_state=run_state,
        control_plane=handoff.control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    clearance = kit.assess_clearance(
        run_state=decision.run_state,
        control_plane=decision.control_plane,
        handoff=handoff.require_handoff(),
    )
    return kit.record_resume(clearance=clearance)


def test_reentry_auditor_passes_recorded_reentry_coordination() -> None:
    resume = _resume_operation()
    coordination = HumanReviewReentryCoordinator.create().resume_and_record(
        resume_operation=resume,
        max_steps=1,
    )

    report = HumanReviewReentryAuditor().audit(coordination)

    assert report.status is HumanReviewReentryAuditStatus.PASSED
    assert report.passed() is True
    assert report.failed() is False
    assert report.has_blocking_findings() is False
    assert report.has_warnings() is False
    assert report.final_stage is RunStage.FORGE_DISPATCH
    assert report.reentry_status is HumanReviewReentryStatus.ADVANCED
    assert report.control_plane_digest == coordination.control_plane.digest()


def test_reentry_auditor_marks_waiting_external_input_without_blocking() -> None:
    resume = _resume_operation()
    coordination = HumanReviewReentryCoordinator.create().resume_and_record(
        resume_operation=resume,
        max_steps=3,
    )

    report = HumanReviewReentryAuditor().audit(coordination)

    assert report.status is HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
    assert report.waiting_for_external_input() is True
    assert report.passed() is False
    assert report.failed() is False
    assert report.has_blocking_findings() is False
    assert report.final_stage is RunStage.FORGE_RESULT_PROCESSING


def test_reentry_audit_payload_links_coordination_records() -> None:
    resume = _resume_operation()
    coordination = HumanReviewReentryCoordinator.create().resume_and_record(
        resume_operation=resume,
        max_steps=1,
    )

    report = HumanReviewReentryAuditor().audit(coordination)
    payload = report.to_payload()

    assert payload["coordination_digest"]["value"] == coordination.digest().value
    assert payload["resume_operation_digest"]["value"] == resume.digest().value
    assert payload["reentry_result_digest"]["value"] == coordination.reentry_result.digest().value
    assert payload["workflow_operation_digest"]["value"] == (
        coordination.workflow_operation.digest().value
    )
    assert payload["status"] == HumanReviewReentryAuditStatus.PASSED.value
    assert payload["blocking_finding_count"] == 0
    assert payload["info_finding_count"] >= 1


def test_reentry_audit_report_rejects_status_that_does_not_match_findings() -> None:
    digest = DigestRecord.from_payload({"record": "bad-reentry-audit"})
    blocking = HumanReviewReentryAuditFinding.create(
        severity=HumanReviewReentryAuditSeverity.BLOCKING,
        code="blocking-finding",
        detail="This finding must force a failed audit status.",
    )

    with pytest.raises(FoundationError, match="status does not match findings"):
        HumanReviewReentryAuditReport.create(
            coordination_digest=digest,
            resume_operation_digest=digest,
            reentry_result_digest=digest,
            workflow_operation_digest=digest,
            state_digest=digest,
            control_plane_digest=digest,
            final_stage=RunStage.EXECUTION_PLANNING,
            reentry_status=HumanReviewReentryStatus.ADVANCED,
            status=HumanReviewReentryAuditStatus.PASSED,
            findings=(blocking,),
        )


def test_reentry_audit_finding_rejects_empty_code() -> None:
    with pytest.raises(FoundationError, match="code must not be empty"):
        HumanReviewReentryAuditFinding.create(
            severity=HumanReviewReentryAuditSeverity.INFO,
            code=" ",
            detail="Invalid empty code.",
        )
