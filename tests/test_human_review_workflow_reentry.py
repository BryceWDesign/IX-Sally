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
from ix_sally.human_review_reentry import HumanReviewReentryRunner
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowStage,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Expose certified human-review reentry through the workflow kit.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run certified workflow reentry verification.",
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


def test_workflow_kit_records_reentry_operation() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    operation = HumanReviewWorkflowKit.create().record_reentry(reentry_result=reentry)

    assert operation.receipt.workflow_stage is HumanReviewWorkflowStage.REENTRY_RECORDED
    assert operation.operation_kind() is (HumanReviewControlPlaneOperationKind.REENTRY_RECORDED)
    assert operation.require_reentry() == reentry
    assert operation.run_state == reentry.state
    assert operation.control_plane.reentry_count() == 1
    assert operation.report.status is (HumanReviewControlPlaneReportStatus.REENTRY_RECORDED)
    assert operation.report.has_reentry() is True
    assert operation.report.reentry_recorded() is True
    assert operation.report.requires_operator_attention() is False
    assert operation.run_state.queued_execution_count() == 1
    assert operation.run_state.dispatched_execution_count() == 0
    assert reentry.final_stage() is RunStage.FORGE_DISPATCH


def test_workflow_kit_reports_waiting_reentry_status() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=3,
    )

    operation = HumanReviewWorkflowKit.create().record_reentry(reentry_result=reentry)

    assert operation.report.status is (
        HumanReviewControlPlaneReportStatus.REENTRY_WAITING_FOR_EXTERNAL_INPUT
    )
    assert operation.report.run_stage is RunStage.FORGE_RESULT_PROCESSING
    assert operation.report.waiting_reentry_count == 1
    assert operation.report.waiting_after_reentry() is True
    assert operation.report.requires_operator_attention() is False
    assert operation.control_plane.latest_reentry_digest() is not None


def test_workflow_reentry_payload_links_report_and_operation() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    operation = HumanReviewWorkflowKit.create().record_reentry(reentry_result=reentry)
    payload = operation.to_payload()
    report_payload = operation.report.to_payload()

    assert payload["workflow_stage"] == HumanReviewWorkflowStage.REENTRY_RECORDED.value
    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.REENTRY_RECORDED.value
    )
    assert payload["report_status"] == (HumanReviewControlPlaneReportStatus.REENTRY_RECORDED.value)
    assert payload["reentry_count"] == 1
    assert report_payload["latest_reentry_digest"] == (
        operation.control_plane.latest_reentry_digest()
    )
    assert report_payload["reentry_recorded"] is True


def test_workflow_reentry_rejects_mismatched_control_plane() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    with pytest.raises(FoundationError, match="must match current control-plane state"):
        HumanReviewWorkflowKit.create().record_reentry(
            reentry_result=reentry,
            control_plane=HumanReviewControlPlaneState.create(),
        )


def test_workflow_operation_requires_reentry_result() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    with pytest.raises(FoundationError, match="has no reentry result"):
        handoff.require_reentry()
