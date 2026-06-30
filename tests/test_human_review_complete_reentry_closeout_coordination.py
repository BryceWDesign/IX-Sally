from __future__ import annotations

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.human_review_complete_reentry_closeout_coordination import (
    CompleteHumanReviewReentryCloseoutCoordinator,
)
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.human_review_workflow import (
    HumanReviewWorkflowKit,
    HumanReviewWorkflowStage,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Coordinate complete human-review reentry closeout.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run coordinated complete human-review reentry closeout.",
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


def test_closeout_coordinator_records_accepted_complete_reentry_closeout() -> None:
    result = (
        CompleteHumanReviewReentryCloseoutCoordinator.create()
        .resume_closeout_and_record(
            resume_operation=_resume_operation(),
            max_steps=1,
        )
    )

    assert result.accepted() is True
    assert result.waiting_for_external_input() is False
    assert result.blocked() is False
    assert result.requires_operator_attention() is False
    assert result.final_stage() is RunStage.FORGE_DISPATCH
    assert result.closeout_report.closeout_status is (
        CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    )
    assert result.closeout_workflow_operation.receipt.workflow_stage is (
        HumanReviewWorkflowStage.COMPLETE_REENTRY_CLOSEOUT_RECORDED
    )
    assert result.closeout_workflow_operation.report.status is (
        HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_ACCEPTED
    )
    assert result.control_plane.complete_reentry_count() == 1
    assert result.control_plane.complete_reentry_closeout_count() == 1


def test_closeout_coordinator_records_waiting_complete_reentry_closeout() -> None:
    result = (
        CompleteHumanReviewReentryCloseoutCoordinator.create()
        .resume_closeout_and_record(
            resume_operation=_resume_operation(),
            max_steps=3,
        )
    )

    assert result.accepted() is False
    assert result.waiting_for_external_input() is True
    assert result.blocked() is False
    assert result.final_stage() is RunStage.FORGE_RESULT_PROCESSING
    assert result.receipt.reentry_status is (
        HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
    )
    assert result.receipt.audit_status is (
        HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
    )
    assert result.closeout_report.closeout_status is (
        CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
    )
    assert result.closeout_workflow_operation.report.status is (
        HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_CLOSEOUT_WAITING_FOR_EXTERNAL_INPUT
    )


def test_closeout_coordination_receipt_links_layers() -> None:
    result = (
        CompleteHumanReviewReentryCloseoutCoordinator.create()
        .resume_closeout_and_record(
            resume_operation=_resume_operation(),
            max_steps=1,
        )
    )

    receipt = result.receipt

    assert receipt.complete_reentry_result_digest == (
        result.complete_reentry_result.digest()
    )
    assert receipt.complete_reentry_receipt_digest == (
        result.complete_reentry_result.receipt.digest()
    )
    assert receipt.closeout_report_digest == result.closeout_report.digest()
    assert receipt.closeout_workflow_operation_digest == (
        result.closeout_workflow_operation.digest()
    )
    assert receipt.recorded_complete_reentry() is True
    assert receipt.recorded_closeout() is True
    assert receipt.changed_state() is True
    assert receipt.report_status is (
        HumanReviewControlPlaneReportStatus.COMPLETE_REENTRY_ACCEPTED
    )


def test_closeout_coordination_payload_and_digest_are_stable() -> None:
    result = (
        CompleteHumanReviewReentryCloseoutCoordinator.create()
        .resume_closeout_and_record(
            resume_operation=_resume_operation(),
            max_steps=1,
        )
    )

    payload = result.to_payload()

    assert payload["closeout_status"] == CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    assert payload["accepted"] is True
    assert payload["blocked"] is False
    assert payload["complete_reentry_count"] == 1
    assert payload["complete_reentry_closeout_count"] == 1
    assert result.digest() == result.digest()
