

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
    HumanReviewControlPlaneCoordinator,
    HumanReviewControlPlaneOperationKind,
    HumanReviewControlPlaneOperationReceipt,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryRunner
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record certified human-review reentry in the control plane.",
        mode=AutonomyMode.TEST,
        max_cycles=3,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run certified post-review verification.",
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


def test_control_plane_coordinator_records_reentry_operation() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    result = HumanReviewControlPlaneCoordinator.create().record_reentry(
        reentry_result=reentry,
        control_plane=resume.control_plane,
    )

    assert result.operation_kind() is HumanReviewControlPlaneOperationKind.REENTRY_RECORDED
    assert result.changed_control_plane() is True
    assert result.before_control_plane.reentry_count() == 0
    assert result.after_control_plane.reentry_count() == 1
    assert result.after_control_plane.latest_reentry_digest() == (
        result.after_control_plane.reentry_ledger.latest().digest().value
    )
    assert result.require_reentry_result() == reentry
    assert result.receipt.reentry_count == 1


def test_control_plane_reentry_operation_payload_links_reentry_digest() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    result = HumanReviewControlPlaneCoordinator.create().record_reentry(
        reentry_result=reentry,
        control_plane=resume.control_plane,
    )
    payload = result.to_payload()

    assert payload["operation_kind"] == HumanReviewControlPlaneOperationKind.REENTRY_RECORDED.value
    assert payload["reentry_count"] == 1
    assert payload["reentry_result_digest"] == reentry.digest().value
    assert payload["handoff_count"] == 1
    assert payload["decision_count"] == 1
    assert payload["resume_count"] == 1


def test_control_plane_reentry_operation_rejects_mismatched_control_plane() -> None:
    resume = _resume_operation()
    reentry = HumanReviewReentryRunner.create().resume_until_stop(
        resume_operation=resume,
        max_steps=1,
    )

    with pytest.raises(FoundationError, match="must match current control-plane state"):
        HumanReviewControlPlaneCoordinator.create().record_reentry(
            reentry_result=reentry,
            control_plane=HumanReviewControlPlaneState.create(),
        )


def test_control_plane_operation_result_requires_reentry_payload() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )

    with pytest.raises(FoundationError, match="has no reentry result"):
        handoff.require_reentry_result()


def test_control_plane_operation_receipt_rejects_negative_reentry_count() -> None:
    digest = DigestRecord.from_payload({"record": "control-plane-reentry-operation"})

    with pytest.raises(FoundationError, match="reentry_count must not be negative"):
        HumanReviewControlPlaneOperationReceipt.create(
            operation_kind=HumanReviewControlPlaneOperationKind.REENTRY_RECORDED,
            before_control_plane_digest=digest,
            after_control_plane_digest=digest,
            operation_digest=digest,
            handoff_count=1,
            decision_count=1,
            resume_count=1,
            reentry_count=-1,
        )
