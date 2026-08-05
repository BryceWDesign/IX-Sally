

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
from ix_sally.human_review_audited_reentry_ledger import (
    AuditedHumanReviewReentryLedger,
    AuditedHumanReviewReentryLedgerEntry,
)
from ix_sally.human_review_control_plane_report import (
    HumanReviewControlPlaneReportStatus,
)
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import HumanReviewReentryAuditStatus
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger fully audited human-review reentry results.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run ledgered audited human-review reentry.",
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


def _resume_operation(
    description: str = "Run ledgered audited human-review reentry.",
):
    run_state = _state().with_action(_review_action(description))
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


def _audited_result(
    description: str = "Run ledgered audited human-review reentry.",
    max_steps: int = 1,
):
    return AuditedHumanReviewReentryCoordinator.create().resume_audit_and_record(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )


def test_audited_reentry_ledger_entry_records_result() -> None:
    result = _audited_result()

    entry = AuditedHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=result,
    )

    assert entry.sequence == 1
    assert entry.audited_reentry_result_digest == result.digest()
    assert entry.audited_reentry_receipt_digest == result.receipt.digest()
    assert entry.final_stage is RunStage.FORGE_DISPATCH
    assert entry.reentry_status is HumanReviewReentryStatus.ADVANCED
    assert entry.audit_status is HumanReviewReentryAuditStatus.PASSED
    assert entry.report_status is HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_PASSED
    assert entry.changed_state() is True
    assert entry.recorded_reentry() is True
    assert entry.recorded_audit() is True
    assert entry.accepted() is True
    assert entry.failed() is False
    assert entry.requires_operator_attention() is False


def test_audited_reentry_ledger_appends_result_at_next_sequence() -> None:
    result = _audited_result()
    ledger = AuditedHumanReviewReentryLedger.create(())

    updated = ledger.append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.audited_reentry_result_digest == result.digest()
    assert updated.accepted_entries() == (latest,)
    assert updated.failed_entries() == ()
    assert updated.changed_state_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_DISPATCH) == (latest,)
    assert updated.entries_for_audit_status(HumanReviewReentryAuditStatus.PASSED) == (
        latest,
    )
    assert updated.entries_for_reentry_status(HumanReviewReentryStatus.ADVANCED) == (
        latest,
    )


def test_audited_reentry_ledger_tracks_waiting_external_input_result() -> None:
    result = _audited_result(max_steps=3)

    updated = AuditedHumanReviewReentryLedger.create(()).append_result(result)
    latest = updated.latest()

    assert latest is not None
    assert latest.waiting_for_external_input() is True
    assert updated.waiting_entries() == (latest,)
    assert updated.accepted_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)
    assert updated.entries_for_audit_status(
        HumanReviewReentryAuditStatus.WAITING_FOR_EXTERNAL_INPUT
    ) == (latest,)
    assert updated.entries_for_report_status(
        HumanReviewControlPlaneReportStatus.REENTRY_AUDIT_WAITING_FOR_EXTERNAL_INPUT
    ) == (latest,)


def test_audited_reentry_ledger_rejects_duplicate_result_digest() -> None:
    result = _audited_result()
    first = AuditedHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=result,
    )
    duplicate = AuditedHumanReviewReentryLedgerEntry.from_result(
        sequence=2,
        result=result,
    )

    with pytest.raises(
        FoundationError,
        match="duplicate audited human-review reentry result digest",
    ):
        AuditedHumanReviewReentryLedger.create((first, duplicate))


def test_audited_reentry_ledger_rejects_duplicate_sequence() -> None:
    first = AuditedHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_audited_result("Run first ledgered audited reentry."),
    )
    second = AuditedHumanReviewReentryLedgerEntry.from_result(
        sequence=1,
        result=_audited_result("Run second ledgered audited reentry."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate audited human-review reentry ledger sequence",
    ):
        AuditedHumanReviewReentryLedger.create((first, second))


def test_audited_reentry_ledger_entry_rejects_invalid_step_counts() -> None:
    result = _audited_result()

    with pytest.raises(FoundationError, match="max_steps must be positive"):
        AuditedHumanReviewReentryLedgerEntry.create(
            sequence=1,
            audited_reentry_result_digest=result.digest(),
            audited_reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            reentry_coordination_digest=result.receipt.reentry_coordination_digest,
            audit_report_digest=result.receipt.audit_report_digest,
            audit_workflow_operation_digest=(
                result.receipt.audit_workflow_operation_digest
            ),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            reentry_control_plane_digest=result.receipt.reentry_control_plane_digest,
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            max_steps=0,
            executed_steps=0,
        )

    with pytest.raises(FoundationError, match="executed_steps exceeds max_steps"):
        AuditedHumanReviewReentryLedgerEntry.create(
            sequence=1,
            audited_reentry_result_digest=result.digest(),
            audited_reentry_receipt_digest=result.receipt.digest(),
            resume_operation_digest=result.receipt.resume_operation_digest,
            reentry_coordination_digest=result.receipt.reentry_coordination_digest,
            audit_report_digest=result.receipt.audit_report_digest,
            audit_workflow_operation_digest=(
                result.receipt.audit_workflow_operation_digest
            ),
            before_state_digest=result.receipt.before_state_digest,
            after_state_digest=result.receipt.after_state_digest,
            before_control_plane_digest=result.receipt.before_control_plane_digest,
            reentry_control_plane_digest=result.receipt.reentry_control_plane_digest,
            after_control_plane_digest=result.receipt.after_control_plane_digest,
            final_stage=result.receipt.final_stage,
            reentry_status=result.receipt.reentry_status,
            audit_status=result.receipt.audit_status,
            report_status=result.receipt.report_status,
            max_steps=1,
            executed_steps=2,
        )


def test_audited_reentry_ledger_payload_and_digest_are_stable() -> None:
    result = _audited_result()

    first = AuditedHumanReviewReentryLedger.create(()).append_result(result)
    second = AuditedHumanReviewReentryLedger.create(()).append_result(result)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["accepted_entry_count"] == 1
    assert payload["failed_entry_count"] == 0
    assert payload["changed_state_entry_count"] == 1
    assert payload["forge_dispatch_entry_count"] == 1
    assert payload["passed_audit_entry_count"] == 1
    assert payload["advanced_reentry_entry_count"] == 1
    assert first.digest() == second.digest()
