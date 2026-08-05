

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
)
from ix_sally.human_review_complete_reentry_report import (
    CompleteHumanReviewReentryCloseoutFinding,
    CompleteHumanReviewReentryCloseoutReport,
    CompleteHumanReviewReentryCloseoutStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Report complete human-review reentry closeout.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run complete closeout-reported human-review reentry.",
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


def _complete_result(max_steps: int = 1):
    return CompleteHumanReviewReentryCoordinator.create().resume_audit_record_and_finalize(
        resume_operation=_resume_operation(),
        max_steps=max_steps,
    )


def test_complete_reentry_closeout_report_accepts_complete_result() -> None:
    result = _complete_result(max_steps=1)

    report = CompleteHumanReviewReentryCloseoutReport.from_result(result)

    assert report.closeout_status is CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    assert report.accepted() is True
    assert report.blocked() is False
    assert report.waiting_for_external_input() is False
    assert report.final_stage is RunStage.FORGE_DISPATCH
    assert report.reentry_count == 1
    assert report.reentry_audit_count == 1
    assert report.audited_reentry_count == 1
    assert report.complete_reentry_count == 1
    assert len(report.findings) == 6
    assert report.blocking_findings() == ()


def test_complete_reentry_closeout_report_tracks_waiting_external_input() -> None:
    result = _complete_result(max_steps=3)

    report = CompleteHumanReviewReentryCloseoutReport.from_result(result)

    assert report.closeout_status is (
        CompleteHumanReviewReentryCloseoutStatus.WAITING_FOR_EXTERNAL_INPUT
    )
    assert report.accepted() is False
    assert report.waiting_for_external_input() is True
    assert report.blocked() is False
    assert report.final_stage is RunStage.FORGE_RESULT_PROCESSING
    assert report.blocking_findings() == ()


def test_complete_reentry_closeout_payload_links_result_layers() -> None:
    result = _complete_result(max_steps=1)

    report = CompleteHumanReviewReentryCloseoutReport.from_result(result)
    payload = report.to_payload()

    assert payload["complete_reentry_result_digest"] == {
        "algorithm": result.digest().algorithm,
        "value": result.digest().value,
    }
    assert payload["complete_reentry_receipt_digest"] == {
        "algorithm": result.receipt.digest().algorithm,
        "value": result.receipt.digest().value,
    }
    assert payload["final_workflow_operation_digest"] == {
        "algorithm": result.final_workflow_operation.digest().algorithm,
        "value": result.final_workflow_operation.digest().value,
    }
    assert payload["closeout_status"] == CompleteHumanReviewReentryCloseoutStatus.ACCEPTED
    assert payload["finding_count"] == 6
    assert payload["blocking_finding_count"] == 0
    assert payload["accepted"] is True
    assert payload["blocked"] is False


def test_complete_reentry_closeout_report_rejects_invalid_step_counts() -> None:
    result = _complete_result(max_steps=1)

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        CompleteHumanReviewReentryCloseoutReport.create(
            complete_reentry_result_digest=result.digest(),
            complete_reentry_receipt_digest=result.receipt.digest(),
            final_workflow_operation_digest=result.final_workflow_operation.digest(),
            state_digest=result.state.digest(),
            control_plane_digest=result.control_plane.digest(),
            final_stage=result.final_stage(),
            reentry_status=result.reentry_status(),
            audit_status=result.audit_status(),
            report_status=result.report_status(),
            closeout_status=CompleteHumanReviewReentryCloseoutStatus.ACCEPTED,
            max_steps=0,
            executed_steps=0,
            reentry_count=1,
            reentry_audit_count=1,
            audited_reentry_count=1,
            complete_reentry_count=1,
            findings=(),
        )


def test_complete_reentry_closeout_report_requires_blocked_for_blocking_findings() -> None:
    result = _complete_result(max_steps=1)
    finding = CompleteHumanReviewReentryCloseoutFinding.create(
        message="Synthetic blocking finding.",
        blocking=True,
    )

    with pytest.raises(FoundationError, match="blocking findings must be blocked"):
        CompleteHumanReviewReentryCloseoutReport.create(
            complete_reentry_result_digest=result.digest(),
            complete_reentry_receipt_digest=result.receipt.digest(),
            final_workflow_operation_digest=result.final_workflow_operation.digest(),
            state_digest=result.state.digest(),
            control_plane_digest=result.control_plane.digest(),
            final_stage=result.final_stage(),
            reentry_status=result.reentry_status(),
            audit_status=result.audit_status(),
            report_status=result.report_status(),
            closeout_status=CompleteHumanReviewReentryCloseoutStatus.ACCEPTED,
            max_steps=1,
            executed_steps=1,
            reentry_count=1,
            reentry_audit_count=1,
            audited_reentry_count=1,
            complete_reentry_count=1,
            findings=(finding,),
        )


def test_complete_reentry_closeout_digest_is_stable() -> None:
    result = _complete_result(max_steps=1)

    first = CompleteHumanReviewReentryCloseoutReport.from_result(result)
    second = CompleteHumanReviewReentryCloseoutReport.from_result(result)

    assert first.digest() == second.digest()
