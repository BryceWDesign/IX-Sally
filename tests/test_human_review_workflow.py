from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneOperationKind,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowReceipt,
    HumanReviewWorkflowStage,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Run human-review workflow kit.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action() -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run human-boundary verification.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "human boundary verification"},
        ),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=True,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human boundary is required.",
        human_review_note="Reviewer must approve the bounded action.",
    )
    return action.with_authority_decision(decision)


def test_workflow_kit_opens_handoff_with_report() -> None:
    run_state = _state().with_action(_review_action())

    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    assert handoff.receipt.workflow_stage is HumanReviewWorkflowStage.HANDOFF_READY
    assert handoff.operation_kind() is HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED
    assert handoff.control_plane.handoff_count() == 1
    assert handoff.report.status is HumanReviewControlPlaneReportStatus.HANDOFF_OPEN
    assert handoff.report.run_stage is RunStage.HUMAN_REVIEW
    assert handoff.require_handoff().target_count() == 1


def test_workflow_kit_records_action_decision_with_updated_state() -> None:
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

    assert decision.receipt.workflow_stage is HumanReviewWorkflowStage.DECISION_RECORDED
    assert decision.operation_kind() is HumanReviewControlPlaneOperationKind.DECISION_RECORDED
    assert decision.control_plane.decision_count() == 1
    assert decision.report.status is HumanReviewControlPlaneReportStatus.DECISION_OPEN
    assert decision.report.run_stage is RunStage.EXECUTION_PLANNING
    assert decision.run_state.actions.require_action(action.action_id.value).allows_execution()


def test_workflow_kit_assesses_clearance_without_mutating_control_plane() -> None:
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

    assert clearance.receipt.workflow_stage is HumanReviewWorkflowStage.CLEARANCE_ASSESSED
    assert clearance.cleared_to_resume() is True
    assert clearance.requires_operator_attention() is False
    assert clearance.control_plane == decision.control_plane
    assert clearance.report.status is HumanReviewControlPlaneReportStatus.DECISION_OPEN


def test_workflow_kit_records_resume_after_clearance() -> None:
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

    resume = kit.record_resume(clearance=clearance)

    assert resume.receipt.workflow_stage is HumanReviewWorkflowStage.RESUME_RECORDED
    assert resume.operation_kind() is HumanReviewControlPlaneOperationKind.RESUME_RECORDED
    assert resume.control_plane.resume_count() == 1
    assert resume.report.status is HumanReviewControlPlaneReportStatus.RESUME_RECORDED
    assert resume.report.cleared_resume_recorded() is True
    assert resume.require_resume().next_stage() is RunStage.EXECUTION_PLANNING


def test_workflow_kit_rejects_resume_when_clearance_not_cleared() -> None:
    run_state = _state().with_action(_review_action())
    kit = HumanReviewWorkflowKit.create()
    handoff = kit.open_handoff(run_state=run_state)
    clearance = kit.assess_clearance(
        run_state=run_state,
        control_plane=handoff.control_plane,
        handoff=handoff.require_handoff(),
    )

    assert clearance.cleared_to_resume() is False

    with pytest.raises(FoundationError, match="not cleared to resume"):
        kit.record_resume(clearance=clearance)


def test_workflow_receipt_rejects_invalid_operation_digest() -> None:
    good = DigestRecord.from_payload({"record": "workflow"})
    bad = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="expected digest algorithm sha256"):
        HumanReviewWorkflowReceipt.create(
            workflow_stage=HumanReviewWorkflowStage.HANDOFF_READY,
            run_state_digest=good,
            control_plane_digest=good,
            report_digest=good,
            operation_digest=bad,
            detail="Invalid workflow receipt.",
        )


def test_workflow_operation_payload_and_digest_are_stable() -> None:
    run_state = _state().with_action(_review_action())
    kit = HumanReviewWorkflowKit.create()

    first = kit.open_handoff(run_state=run_state)
    second = kit.open_handoff(run_state=run_state)

    payload = first.to_payload()

    assert payload["workflow_stage"] == HumanReviewWorkflowStage.HANDOFF_READY.value
    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.HANDOFF_RECORDED.value
    )
    assert payload["report_status"] == HumanReviewControlPlaneReportStatus.HANDOFF_OPEN.value
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
