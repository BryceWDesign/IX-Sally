

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
    HumanReviewControlPlaneCoordinator,
    HumanReviewControlPlaneOperationKind,
    HumanReviewControlPlaneOperationReceipt,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Record fully audited human-review reentry in the control plane.",
        mode=AutonomyMode.TEST,
        max_cycles=3,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run fully audited control-plane reentry verification.",
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


def _audited_reentry_result(max_steps: int = 1):
    return AuditedHumanReviewReentryCoordinator.create().resume_audit_and_record(
        resume_operation=_resume_operation(),
        max_steps=max_steps,
    )


def test_control_plane_coordinator_records_audited_reentry_operation() -> None:
    audited_reentry = _audited_reentry_result()

    result = HumanReviewControlPlaneCoordinator.create().record_audited_reentry(
        audited_reentry_result=audited_reentry,
        control_plane=audited_reentry.control_plane,
    )

    assert result.operation_kind() is (
        HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED
    )
    assert result.changed_control_plane() is True
    assert result.before_control_plane.audited_reentry_count() == 0
    assert result.after_control_plane.audited_reentry_count() == 1
    assert result.after_control_plane.latest_audited_reentry_digest() == (
        result.after_control_plane.audited_reentry_ledger.latest().digest().value
    )
    assert result.require_audited_reentry_result() == audited_reentry
    assert result.receipt.audited_reentry_count == 1


def test_control_plane_audited_reentry_operation_payload_links_result_digest() -> None:
    audited_reentry = _audited_reentry_result()

    result = HumanReviewControlPlaneCoordinator.create().record_audited_reentry(
        audited_reentry_result=audited_reentry,
        control_plane=audited_reentry.control_plane,
    )
    payload = result.to_payload()

    assert payload["operation_kind"] == (
        HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED.value
    )
    assert payload["audited_reentry_count"] == 1
    assert payload["audited_reentry_result_digest"] == audited_reentry.digest().value
    assert payload["reentry_count"] == 1
    assert payload["reentry_audit_count"] == 1


def test_control_plane_audited_reentry_operation_rejects_mismatched_control_plane() -> None:
    audited_reentry = _audited_reentry_result()

    with pytest.raises(FoundationError, match="audited reentry must match current"):
        HumanReviewControlPlaneCoordinator.create().record_audited_reentry(
            audited_reentry_result=audited_reentry,
            control_plane=HumanReviewControlPlaneState.create(),
        )


def test_control_plane_operation_result_requires_audited_reentry_result() -> None:
    run_state = _state().with_action(_review_action())
    handoff = HumanReviewControlPlaneCoordinator.create().record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )

    with pytest.raises(FoundationError, match="has no audited reentry result"):
        handoff.require_audited_reentry_result()


def test_control_plane_operation_receipt_rejects_negative_audited_reentry_count() -> None:
    digest = DigestRecord.from_payload(
        {"record": "control-plane-audited-reentry-operation"},
    )

    with pytest.raises(FoundationError, match="audited_reentry_count must not be negative"):
        HumanReviewControlPlaneOperationReceipt.create(
            operation_kind=HumanReviewControlPlaneOperationKind.AUDITED_REENTRY_RECORDED,
            before_control_plane_digest=digest,
            after_control_plane_digest=digest,
            operation_digest=digest,
            handoff_count=1,
            decision_count=1,
            resume_count=1,
            reentry_count=1,
            reentry_audit_count=1,
            audited_reentry_count=-1,
        )
