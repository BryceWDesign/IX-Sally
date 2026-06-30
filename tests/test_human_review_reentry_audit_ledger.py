from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_reentry import HumanReviewReentryStatus
from ix_sally.human_review_reentry_audit import (
    HumanReviewReentryAuditStatus,
    HumanReviewReentryAuditor,
)
from ix_sally.human_review_reentry_audit_ledger import (
    HumanReviewReentryAuditLedger,
    HumanReviewReentryAuditLedgerEntry,
)
from ix_sally.human_review_reentry_coordination import HumanReviewReentryCoordinator
from ix_sally.human_review_workflow import HumanReviewWorkflowKit
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.stage_readiness import RunStage
from ix_sally.state import NinefoldRunState


def _state(max_cycles: int = 3) -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger human-review reentry audit reports.",
        mode=AutonomyMode.TEST,
        max_cycles=max_cycles,
        allowed_tools=("test-runner",),
        doctrine_keys=("output-is-not-evidence",),
    )
    return NinefoldRunState.create(runtime_kit=NinefoldRuntimeKit.create(contract=contract))


def _review_action(
    description: str = "Run ledgered audited post-review verification.",
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


def _resume_operation(description: str = "Run ledgered audited post-review verification."):
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


def _audit_report(
    description: str = "Run ledgered audited post-review verification.",
    max_steps: int = 1,
):
    coordination = HumanReviewReentryCoordinator.create().resume_and_record(
        resume_operation=_resume_operation(description),
        max_steps=max_steps,
    )
    return HumanReviewReentryAuditor().audit(coordination)


def test_reentry_audit_ledger_entry_records_report() -> None:
    report = _audit_report()

    entry = HumanReviewReentryAuditLedgerEntry.from_report(
        sequence=1,
        report=report,
    )

    assert entry.sequence == 1
    assert entry.audit_report_digest == report.digest()
    assert entry.audit_status is HumanReviewReentryAuditStatus.PASSED
    assert entry.reentry_status is HumanReviewReentryStatus.ADVANCED
    assert entry.final_stage is RunStage.FORGE_DISPATCH
    assert entry.passed() is True
    assert entry.failed() is False
    assert entry.has_blocking_findings() is False
    assert entry.finding_count == len(report.findings)


def test_reentry_audit_ledger_appends_report_at_next_sequence() -> None:
    report = _audit_report()
    ledger = HumanReviewReentryAuditLedger.create(())

    updated = ledger.append_report(report)
    latest = updated.latest()

    assert latest is not None
    assert updated.next_sequence() == 2
    assert latest.audit_report_digest == report.digest()
    assert updated.passed_entries() == (latest,)
    assert updated.failed_entries() == ()
    assert updated.entries_for_stage(RunStage.FORGE_DISPATCH) == (latest,)
    assert updated.entries_for_reentry_status(HumanReviewReentryStatus.ADVANCED) == (
        latest,
    )


def test_reentry_audit_ledger_tracks_waiting_audit_report() -> None:
    report = _audit_report(max_steps=3)

    updated = HumanReviewReentryAuditLedger.create(()).append_report(report)
    latest = updated.latest()

    assert latest is not None
    assert latest.waiting_for_external_input() is True
    assert updated.waiting_entries() == (latest,)
    assert updated.entries_for_stage(RunStage.FORGE_RESULT_PROCESSING) == (latest,)
    assert updated.entries_for_reentry_status(
        HumanReviewReentryStatus.WAITING_FOR_EXTERNAL_INPUT
    ) == (latest,)


def test_reentry_audit_ledger_rejects_duplicate_report_digest() -> None:
    report = _audit_report()
    first = HumanReviewReentryAuditLedgerEntry.from_report(sequence=1, report=report)
    duplicate = HumanReviewReentryAuditLedgerEntry.from_report(sequence=2, report=report)

    with pytest.raises(
        FoundationError,
        match="duplicate human-review reentry audit report digest",
    ):
        HumanReviewReentryAuditLedger.create((first, duplicate))


def test_reentry_audit_ledger_rejects_duplicate_sequence() -> None:
    first = HumanReviewReentryAuditLedgerEntry.from_report(
        sequence=1,
        report=_audit_report("Run first ledgered audited verification."),
    )
    second = HumanReviewReentryAuditLedgerEntry.from_report(
        sequence=1,
        report=_audit_report("Run second ledgered audited verification."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review reentry audit ledger sequence",
    ):
        HumanReviewReentryAuditLedger.create((first, second))


def test_reentry_audit_ledger_entry_rejects_bad_finding_subtotals() -> None:
    report = _audit_report()

    with pytest.raises(FoundationError, match="finding subtotals must equal"):
        HumanReviewReentryAuditLedgerEntry.create(
            sequence=1,
            audit_report_digest=report.digest(),
            coordination_digest=report.coordination_digest,
            resume_operation_digest=report.resume_operation_digest,
            reentry_result_digest=report.reentry_result_digest,
            workflow_operation_digest=report.workflow_operation_digest,
            state_digest=report.state_digest,
            control_plane_digest=report.control_plane_digest,
            final_stage=report.final_stage,
            reentry_status=report.reentry_status,
            audit_status=report.status,
            finding_count=3,
            blocking_finding_count=0,
            warning_finding_count=0,
            info_finding_count=2,
        )


def test_reentry_audit_ledger_payload_and_digest_are_stable() -> None:
    report = _audit_report()

    first = HumanReviewReentryAuditLedger.create(()).append_report(report)
    second = HumanReviewReentryAuditLedger.create(()).append_report(report)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["passed_entry_count"] == 1
    assert payload["failed_entry_count"] == 0
    assert payload["forge_dispatch_entry_count"] == 1
    assert payload["advanced_reentry_entry_count"] == 1
    assert first.digest() == second.digest()
