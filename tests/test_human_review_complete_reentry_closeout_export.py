from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_complete_reentry_closeout_coordination import (
    CompleteHumanReviewReentryCloseoutCoordinator,
)
from ix_sally.human_review_complete_reentry_closeout_export import (
    CompleteHumanReviewReentryCloseoutExportArtifact,
    CompleteHumanReviewReentryCloseoutExportPacket,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Export complete human-review reentry closeout evidence.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run exported complete human-review reentry closeout.",
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


def _coordination_result(max_steps: int = 1):
    return CompleteHumanReviewReentryCloseoutCoordinator.create().resume_closeout_and_record(
        resume_operation=_resume_operation(),
        max_steps=max_steps,
    )


def test_complete_reentry_closeout_export_packet_links_all_layers() -> None:
    result = _coordination_result(max_steps=1)

    packet = CompleteHumanReviewReentryCloseoutExportPacket.from_result(result)

    assert packet.coordination_result_digest == result.digest()
    assert packet.coordination_receipt_digest == result.receipt.digest()
    assert packet.closeout_report_digest == result.closeout_report.digest()
    assert packet.closeout_workflow_operation_digest == (
        result.closeout_workflow_operation.digest()
    )
    assert packet.final_state_digest == result.state.digest()
    assert packet.final_control_plane_digest == result.control_plane.digest()
    assert packet.accepted is True
    assert packet.waiting_for_external_input is False
    assert packet.blocked is False
    assert packet.complete() is True
    assert packet.exportable_without_operator() is True
    assert len(packet.required_artifacts()) == 6


def test_complete_reentry_closeout_export_packet_tracks_waiting_result() -> None:
    result = _coordination_result(max_steps=3)

    packet = CompleteHumanReviewReentryCloseoutExportPacket.from_result(result)

    assert packet.accepted is False
    assert packet.waiting_for_external_input is True
    assert packet.blocked is False
    assert packet.requires_operator_attention is False
    assert packet.complete() is True
    assert packet.exportable_without_operator() is True


def test_complete_reentry_closeout_export_payload_is_stable() -> None:
    result = _coordination_result(max_steps=1)

    first = CompleteHumanReviewReentryCloseoutExportPacket.from_result(result)
    second = CompleteHumanReviewReentryCloseoutExportPacket.from_result(result)
    payload = first.to_payload()

    assert payload["artifact_count"] == 6
    assert payload["required_artifact_count"] == 6
    assert payload["missing_required_artifact_labels"] == []
    assert payload["complete"] is True
    assert payload["exportable_without_operator"] is True
    assert first.digest() == second.digest()


def test_complete_reentry_closeout_export_rejects_conflicting_statuses() -> None:
    digest = DigestRecord.from_payload({"record": "conflicting-closeout-export"})
    artifacts = tuple(
        CompleteHumanReviewReentryCloseoutExportArtifact.create(
            label=f"artifact {index}",
            digest=DigestRecord.from_payload({"artifact": index}),
        )
        for index in range(6)
    )

    with pytest.raises(FoundationError, match="both accepted and blocked"):
        CompleteHumanReviewReentryCloseoutExportPacket.create(
            coordination_result_digest=digest,
            coordination_receipt_digest=digest,
            closeout_report_digest=digest,
            closeout_workflow_operation_digest=digest,
            final_state_digest=digest,
            final_control_plane_digest=digest,
            closeout_ledger_digest=digest,
            coordination_ledger_digest=digest,
            accepted=True,
            waiting_for_external_input=False,
            blocked=True,
            requires_operator_attention=True,
            artifacts=artifacts,
        )


def test_complete_reentry_closeout_export_requires_artifacts() -> None:
    digest = DigestRecord.from_payload({"record": "missing-closeout-export-artifacts"})

    with pytest.raises(FoundationError, match="requires at least six required"):
        CompleteHumanReviewReentryCloseoutExportPacket.create(
            coordination_result_digest=digest,
            coordination_receipt_digest=digest,
            closeout_report_digest=digest,
            closeout_workflow_operation_digest=digest,
            final_state_digest=digest,
            final_control_plane_digest=digest,
            closeout_ledger_digest=digest,
            coordination_ledger_digest=digest,
            accepted=True,
            waiting_for_external_input=False,
            blocked=False,
            requires_operator_attention=False,
            artifacts=(),
        )
