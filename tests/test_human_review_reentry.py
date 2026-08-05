

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import (
    HumanReviewReentryReceipt,
    HumanReviewReentryRunner,
    HumanReviewReentryStatus,
)
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.orchestration_loop import StageLoopStopReason
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Resume staged orchestration after human review.",
        mode=AutonomyMode.TEST,
        max_cycles=3,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action() -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        description="Run a post-review verification step.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload(
            {"proposal_action": "post-review verification"},
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


def test_reentry_runner_resumes_certified_human_review_operation() -> None:
    resume = _resume_operation()

    result = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=3,
    )

    assert result.status() is HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
    assert result.receipt.stop_reason is StageLoopStopReason.EXTERNAL_INPUT_REQUIRED
    assert result.final_stage() is RunStage.FORGE_RESULT_PROCESSING
    assert result.loop_result.forge_results_consumed == 0
    assert result.loop_result.executed_steps() == 3
    assert result.changed_state() is True
    assert result.state.dispatched_execution_count() == 1


def test_reentry_receipt_records_resume_certificate_and_loop_digest() -> None:
    resume = _resume_operation()

    result = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )
    receipt_payload = result.receipt.to_payload()

    assert result.receipt.status is HumanReviewReentryStatus.ADVANCED
    assert result.receipt.changed_state() is True
    assert receipt_payload["resume_certificate_digest"]["algorithm"] == "sha256"
    assert receipt_payload["loop_digest"]["value"] == result.loop_result.digest().value
    assert receipt_payload["final_stage"] == RunStage.FORGE_DISPATCH.value


def test_reentry_runner_rejects_non_resume_workflow_operation() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewWorkflowKit.create().open_handoff(run_state=run_state)

    with pytest.raises(FoundationError, match="requires a resume-recorded operation"):
        HumanReviewReentryRunner.create().resume_until_stop(
            resume_operation=handoff,
            max_steps=1,
        )


def test_reentry_receipt_rejects_negative_executed_steps() -> None:
    good = DigestRecord.from_payload({"record": "reentry"})

    with pytest.raises(FoundationError, match="executed_steps must not be negative"):
        HumanReviewReentryReceipt.create(
            resume_operation_digest=good,
            resume_certificate_digest=good,
            control_plane_digest=good,
            before_state_digest=good,
            after_state_digest=good,
            loop_digest=good,
            final_stage=RunStage.EXECUTION_PLANNING,
            stop_reason=StageLoopStopReason.STEP_LIMIT_REACHED,
            executed_steps=-1,
            status=HumanReviewReentryStatus.STEP_LIMIT_REACHED,
        )
