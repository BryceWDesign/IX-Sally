

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_audited_reentry import (
    AuditedHumanReviewReentryCoordinator,
)
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneOperationKind,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowStage,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Expose fully audited human-review reentry through workflow kit.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run workflow-recorded audited human-review reentry.",
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


def _audited_result(max_steps: int = 1):
    return AuditedHumanReviewReentryCoordinator.create().resume_audit_and_record(
        resume_operation=_resume_operation(),
        max_steps=max_steps,
    )


def test_workflow_kit_records_audited_reentry_operation() -> None:
    audited_reentry = _audited_result(max_steps=1)

    operation = HumanReviewWorkflowKit.create().record_audited_reentry(
        audited_reentry_result=audited_reentry,
    )

    assert operation.receipt.workflow_stage is (
        HumanReviewWorkflowStage.AUDITED_REENTRY_RECORDED
    )
    assert operation.operation_kind() is (
        HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED
    )
    assert operation.require_audited_reentry_result() == audited_reentry
    assert operation.run_state == audited_reentry.state
    assert operation.control_plane.reentry_count() == 1
    assert operation.control_plane.reentry_audit_count() == 1
    assert operation.control_plane.audited_reentry_count() == 1
    assert operation.report.status is (
        HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED
    )
    assert operation.report.audited_reentry_recorded() is True
    assert operation.report.audited_reentry_accepted() is True
    assert operation.report.requires_operator_attention() is False


def test_workflow_kit_records_waiting_audited_reentry_status() -> None:
    audited_reentry = _audited_result(max_steps=3)

    operation = HumanReviewWorkflowKit.create().record_audited_reentry(
        audited_reentry_result=audited_reentry,
    )

    assert operation.report.status is (
        HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT
    )
    assert operation.report.run_stage is RunStage.FORGE_RESULT_PROCESSING
    assert operation.report.waiting_audited_reentry_count == 1
    assert operation.report.waiting_after_reentry() is True
    assert operation.report.audited_reentry_accepted() is True
    assert operation.report.requires_operator_attention() is False
    assert operation.control_plane.latest_audited_reentry_digest() is not None


def test_workflow_audited_reentry_payload_links_result_and_report() -> None:
    audited_reentry = _audited_result(max_steps=1)

    operation = HumanReviewWorkflowKit.create().record_audited_reentry(
        audited_reentry_result=audited_reentry,
    )
    payload = operation.to_payload()
    report_payload = operation.report.to_payload()

    assert payload["workflow_stage"] == (
        HumanReviewWorkflowStage.AUDITED_REENTRY_RECORDED.value
    )
    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED.value
    )
    assert payload["report_status"] == (
        HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED.value
    )
    assert payload["audited_reentry_count"] == 1
    assert report_payload["latest_audited_reentry_digest"] == (
        operation.control_plane.latest_audited_reentry_digest()
    )
    assert report_payload["audited_reentry_recorded"] is True


def test_workflow_audited_reentry_rejects_mismatched_control_plane() -> None:
    audited_reentry = _audited_result(max_steps=1)

    with pytest.raises(FoundationError, match="audited reentry must match current"):
        HumanReviewWorkflowKit.create().record_audited_reentry(
            audited_reentry_result=audited_reentry,
            control_plane=HumanReviewControlPlaneState.create(),
        )


def test_workflow_operation_requires_audited_reentry_result() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    with pytest.raises(FoundationError, match="has no audited reentry result"):
        handoff.require_audited_reentry_result()
