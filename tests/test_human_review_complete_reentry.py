

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_complete_reentry import (
    CompleteHumanReviewReentryCoordinator,
    CompleteHumanReviewReentryReceipt,
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
        goal="Run complete audited human-review reentry.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run complete audited post-review verification.",
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


def test_complete_reentry_coordinator_records_final_audited_result() -> None:
    resume = _resume_operation()

    result = CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=resume,
        max_steps=1,
    )

    assert result.final_workflow_operation.receipt.workflow_stage is (
        HumanReviewWorkflowStage.AUDITED_REENTRY_RECORDED
    )
    assert result.reentry_status() is HumanReviewReentryStatus.ADVANCED
    assert result.audit_status() is HumanReviewReentryAuditStatus.PASSED
    assert result.report_status() is (
        HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED
    )
    assert result.final_stage() is RunStage.FORGE_DISPATCH
    assert result.changed_state() is True
    assert result.accepted() is True
    assert result.requires_operator_attention() is False
    assert result.control_plane.reentry_count() == 1
    assert result.control_plane.reentry_audit_count() == 1
    assert result.control_plane.audited_reentry_count() == 1


def test_complete_reentry_coordinator_tracks_waiting_external_input() -> None:
    resume = _resume_operation()

    result = CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=resume,
        max_steps=3,
    )

    assert result.reentry_status() is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
    assert result.audit_status() is HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
    assert result.report_status() is (
        HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_WAITING_FOR_EXTERNAL_INPUT
    )
    assert result.final_stage() is RunStage.FORGE_RESULT_PROCESSING
    assert result.accepted() is True
    assert result.receipt.waiting_for_external_input() is True
    assert result.requires_operator_attention() is False
    assert result.control_plane.latest_audited_reentry_digest() is not None


def test_complete_reentry_payload_links_all_layers() -> None:
    resume = _resume_operation()

    result = CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=resume,
        max_steps=1,
    )
    payload = result.to_payload()
    receipt_payload = result.receipt.to_payload()

    assert payload["resume_operation_digest"] == resume.digest().value
    assert payload["audited_reentry_result_digest"] == (
        result.audited_reentry_result.digest().value
    )
    assert payload["final_workflow_operation_digest"] == (
        result.final_workflow_operation.digest().value
    )
    assert payload["audited_reentry_count"] == 1
    assert payload["accepted"] is True
    assert receipt_payload["recorded_reentry_and_audit"] is True
    assert receipt_payload["recorded_complete_audited_reentry"] is True


def test_complete_reentry_coordinator_rejects_non_resume_operation() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    with pytest.raises(FoundationError, match="requires resume-recorded operation"):
        CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
            resume_operation=handoff,
            max_steps=1,
        )


def test_complete_reentry_receipt_rejects_invalid_step_counts() -> None:
    digest = DigestRecord.from_payload({"record": "complete-reentry"})

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        CompleteHumanReviewReentryReceipt.create(
            resume_operation_digest=digest,
            audited_reentry_result_digest=digest,
            audited_reentry_receipt_digest=digest,
            final_workflow_operation_digest=digest,
            before_state_digest=digest,
            after_state_digest=digest,
            before_control_plane_digest=digest,
            audited_reentry_control_plane_digest=digest,
            after_control_plane_digest=digest,
            final_stage=RunStage.EXECUTION_PLANNING,
            reentry_status=HumanReviewReentryStatus.ADVANCED,
            audit_status=HumanReviewReentryAuditStatus.PASSED,
            report_status=HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            max_steps=0,
            executed_steps=0,
        )

    with pytest.raises(FoundationError, match="executed_steps exceeds max_steps"):
        CompleteHumanReviewReentryReceipt.create(
            resume_operation_digest=digest,
            audited_reentry_result_digest=digest,
            audited_reentry_receipt_digest=digest,
            final_workflow_operation_digest=digest,
            before_state_digest=digest,
            after_state_digest=digest,
            before_control_plane_digest=digest,
            audited_reentry_control_plane_digest=digest,
            after_control_plane_digest=digest,
            final_stage=RunStage.EXECUTION_PLANNING,
            reentry_status=HumanReviewReentryStatus.ADVANCED,
            audit_status=HumanReviewReentryAuditStatus.PASSED,
            report_status=HumanReviewControlPlaneReportStatus.AUDITED_REENTRY_ACCEPTED,
            max_steps=1,
            executed_steps=2,
        )
