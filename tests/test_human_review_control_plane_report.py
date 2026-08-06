from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import HumanReviewBundleAssembler
from ix_sally.human_review_clearance import HumanReviewClearanceAssessment
from ix_sally.human_review_control_plane import HumanReviewControlPlaneState
from ix_sally.human_review_control_plane_coordinator import (
    HumanReviewControlPlaneCoordinator,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReport,
    HumanReviewControlPlaneReporter,
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Report human-review control-plane state.",
        mode=AutonomyMode.TEST,
        max_cycles=2,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(description: str = "Run human-boundary verification.") -> BoundedActionRecord:
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
        rationale="Human boundary is required.",
        human_review_note="Reviewer must approve the bounded action.",
    )
    return action.with_authority_decision(decision)


def test_control_plane_report_marks_empty_state_no_handoffs() -> None:
    run_state = _state()
    control_plane = HumanReviewControlPlaneState.create()

    report = HumanReviewControlPlaneReporter().report(
        run_state=run_state,
        control_plane=control_plane,
    )

    assert report.status is HumanReviewControlPlaneReportStatus.NO_HANDOFFS
    assert report.run_stage is RunStage.PROPOSAL_INTAKE
    assert report.requires_operator_attention() is False
    assert report.has_handoff() is False


def test_control_plane_report_marks_open_handoff() -> None:
    run_state = _state().with_action(_review_action())
    coordinator = HumanReviewControlPlaneCoordinator.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )

    report = HumanReviewControlPlaneReporter().report(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
    )

    assert report.status is HumanReviewControlPlaneReportStatus.HANDOFF_OPEN
    assert report.run_stage is RunStage.HUMAN_REVIEW
    assert report.handoff_count == 1
    assert report.decision_count == 0
    assert report.requires_operator_attention() is True
    assert report.latest_handoff_digest is not None


def test_control_plane_report_marks_decision_open_until_resume_recorded() -> None:
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    coordinator = HumanReviewControlPlaneCoordinator.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )
    decision = coordinator.record_action_decision(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )

    report = HumanReviewControlPlaneReporter().report(
        run_state=decision.require_decision_result().state,
        control_plane=decision.after_control_plane,
    )

    assert report.status is HumanReviewControlPlaneReportStatus.DECISION_OPEN
    assert report.run_stage is RunStage.EXECUTION_PLANNING
    assert report.decision_count == 1
    assert report.approved_decision_count == 1
    assert report.requires_operator_attention() is True
    assert report.latest_decision_digest is not None


def test_control_plane_report_marks_resume_recorded() -> None:
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    coordinator = HumanReviewControlPlaneCoordinator.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )
    decision = coordinator.record_action_decision(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="The bounded action is approved for execution.",
    )
    bundle = HumanReviewBundleAssembler.create().assemble(state=run_state)
    assessment = HumanReviewClearanceAssessment.from_bundle(
        bundle=bundle,
        decision_ledger=decision.after_control_plane.decision_ledger,
    )
    resume = coordinator.record_resume(
        assessment=assessment,
        resumed_state=decision.require_decision_result().state,
        control_plane=decision.after_control_plane,
    )

    report = HumanReviewControlPlaneReporter().report(
        run_state=resume.require_resume_result().state,
        control_plane=resume.after_control_plane,
    )

    assert report.status is HumanReviewControlPlaneReportStatus.RESUME_RECORDED
    assert report.resume_count == 1
    assert report.cleared_resume_count == 1
    assert report.cleared_resume_recorded() is True
    assert report.requires_operator_attention() is False
    assert report.latest_resume_digest is not None


def test_control_plane_report_prioritizes_rejection_status() -> None:
    run_state = _state().with_action(_review_action())
    action = run_state.actions.human_review_actions()[0]
    coordinator = HumanReviewControlPlaneCoordinator.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )
    decision = coordinator.record_action_decision(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.REJECTED,
        rationale="The bounded action is rejected.",
    )

    report = HumanReviewControlPlaneReporter().report(
        run_state=decision.require_decision_result().state,
        control_plane=decision.after_control_plane,
    )

    assert report.status is HumanReviewControlPlaneReportStatus.REJECTION_BLOCKED
    assert report.rejected_decision_count == 1
    assert report.requires_operator_attention() is True


def test_control_plane_report_rejects_invalid_decision_subtotals() -> None:
    digest = DigestRecord.from_payload({"record": "control-plane-report"})

    with pytest.raises(FoundationError, match="decision subtotals exceed"):
        HumanReviewControlPlaneReport.create(
            run_state_digest=digest,
            run_snapshot_digest=digest,
            control_plane_snapshot_digest=digest,
            control_plane_status_digest=digest,
            run_stage=RunStage.HUMAN_REVIEW,
            status=HumanReviewControlPlaneReportStatus.DECISION_OPEN,
            rationale="Invalid report.",
            handoff_count=1,
            decision_count=1,
            resume_count=0,
            approved_decision_count=1,
            rejected_decision_count=1,
            deferred_decision_count=0,
            cleared_resume_count=0,
            latest_handoff_digest=None,
            latest_decision_digest=None,
            latest_resume_digest=None,
        )


def test_control_plane_report_payload_and_digest_are_stable() -> None:
    run_state = _state().with_action(_review_action())
    coordinator = HumanReviewControlPlaneCoordinator.create()
    handoff = coordinator.record_handoff(
        run_state=run_state,
        control_plane=HumanReviewControlPlaneState.create(),
    )

    first = HumanReviewControlPlaneReporter().report(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
    )
    second = HumanReviewControlPlaneReporter().report(
        run_state=run_state,
        control_plane=handoff.after_control_plane,
    )

    payload = first.to_payload()

    assert payload["status"] == HumanReviewControlPlaneReportStatus.HANDOFF_OPEN.value
    assert payload["run_stage"] == RunStage.HUMAN_REVIEW.value
    assert payload["handoff_count"] == 1
    assert payload["requires_operator_attention"] is True
    assert first.digest() == second.digest()
