from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneOperationKind,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditor
from ix_sally.human_review_reentry_coordination import HumanReviewReentryCoordinator
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowStage,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Expose human-review reentry audit recording through workflow kit.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run workflow-audited post-review verification.",
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


def _coordination(max_steps: int = 1):
    return HumanReviewReentryCoordinator.create().resume_and_record(
        resume_operation=_resume_operation(),
        max_steps=max_steps,
    )


def test_workflow_kit_records_reentry_audit_operation() -> None:
    coordination = _coordination(max_steps=1)
    audit_report = HumanReviewReentryAuditor().audit(coordination)

    operation = HumanReviewWorkflowKit.create().record_reentry_audit(
        run_state=coordination.state,
        audit_report=audit_report,
        control_plane=coordination.control_plane,
    )

    assert operation.receipt.workflow_stage is (HumanReviewWorkflowStage.REENTRY_AUDIT_RECORDED)
    assert operation.operation_kind() is (
        HumanReviewControlPlaneOperationKind.REENTRY_AUDIT_RECORDED
    )
    assert operation.require_reentry_audit_report() == audit_report
    assert operation.run_state == coordination.state
    assert operation.control_plane.reentry_count() == 1
    assert operation.control_plane.reentry_audit_count() == 1
    assert operation.report.status is HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED
    assert operation.report.reentry_audit_recorded() is True
    assert operation.report.reentry_audit_passed() is True
    assert operation.report.requires_operator_attention() is False


def test_workflow_kit_records_waiting_reentry_audit_status() -> None:
    coordination = _coordination(max_steps=3)
    audit_report = HumanReviewReentryAuditor().audit(coordination)

    operation = HumanReviewWorkflowKit.create().record_reentry_audit(
        run_state=coordination.state,
        audit_report=audit_report,
        control_plane=coordination.control_plane,
    )

    assert operation.report.status is (
        HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT
    )
    assert operation.report.run_stage is RunStage.FORGE_RESULT_PROCESSING
    assert operation.report.waiting_reentry_audit_count == 1
    assert operation.report.waiting_after_reentry() is True
    assert operation.report.requires_operator_attention() is False
    assert operation.control_plane.latest_reentry_audit_digest() is not None


def test_workflow_reentry_audit_payload_links_report_and_operation() -> None:
    coordination = _coordination(max_steps=1)
    audit_report = HumanReviewReentryAuditor().audit(coordination)

    operation = HumanReviewWorkflowKit.create().record_reentry_audit(
        run_state=coordination.state,
        audit_report=audit_report,
        control_plane=coordination.control_plane,
    )
    payload = operation.to_payload()
    report_payload = operation.report.to_payload()

    assert payload["workflow_stage"] == (HumanReviewWorkflowStage.REENTRY_AUDIT_RECORDED.value)
    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.REENTRY_AUDIT_RECORDED.value
    )
    assert payload["report_status"] == (
        HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED.value
    )
    assert payload["reentry_audit_count"] == 1
    assert report_payload["latest_reentry_audit_digest"] == (
        operation.control_plane.latest_reentry_audit_digest()
    )
    assert report_payload["reentry_audit_recorded"] is True


def test_workflow_reentry_audit_rejects_mismatched_control_plane() -> None:
    coordination = _coordination(max_steps=1)
    audit_report = HumanReviewReentryAuditor().audit(coordination)

    with pytest.raises(FoundationError, match="reentry audit must match current"):
        HumanReviewWorkflowKit.create().record_reentry_audit(
            run_state=coordination.state,
            audit_report=audit_report,
            control_plane=HumanReviewControlPlaneState.create(),
        )


def test_workflow_reentry_audit_rejects_mismatched_run_state() -> None:
    coordination = _coordination(max_steps=1)
    audit_report = HumanReviewReentryAuditor().audit(coordination)
    other_state = _state(max_cycles=4)

    with pytest.raises(FoundationError, match="run state must match audit report"):
        HumanReviewWorkflowKit.create().record_reentry_audit(
            run_state=other_state,
            audit_report=audit_report,
            control_plane=coordination.control_plane,
        )


def test_workflow_operation_requires_reentry_audit_report() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    with pytest.raises(FoundationError, match="has no reentry audit report"):
        handoff.require_reentry_audit_report()
