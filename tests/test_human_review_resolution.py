

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle import HumanReviewBundleAssembler
from ix_sally.human_review_decision_coordinator import HumanReviewDecisionCoordinator
from ix_sally.human_review_decision_ledger import HumanReviewDecisionLedger
from ix_sally.human_review_gateway import HumanReviewDecisionStatus
from ix_sally.human_review_resolution import (
    HumanReviewResolutionAudit,
    HumanReviewResolutionStatus,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Audit human-review resolution.",
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


def _unsupported_finding() -> EvidenceSupportFinding:
    return EvidenceSupportFinding.create(
        cycle=1,
        claim_digest=DigestRecord.from_payload({"claim": "unsupported"}),
        status=EvidenceSupportStatus.UNSUPPORTED,
        rationale="No recorded evidence supports the claim.",
    )


def test_resolution_audit_marks_gateway_card_pending_without_decision() -> None:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    audit = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    assert audit.resolved_count() == 0
    assert audit.pending_decision_count() == 1
    assert audit.manual_investigation_count() == 0
    assert audit.requires_operator_attention() is True
    assert audit.all_gateway_decisions_recorded() is False
    assert audit.resolutions[0].status is HumanReviewResolutionStatus.PENDING_DECISION


def test_resolution_audit_marks_gateway_card_resolved_with_decision() -> None:
    state = _state().with_action(_review_action())
    action = state.actions.human_review_actions()[0]
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    decision_result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION,
        rationale="Bounded action is approved for execution.",
    )

    audit = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=decision_result.after_ledger,
    )

    assert audit.resolved_count() == 1
    assert audit.pending_decision_count() == 0
    assert audit.manual_investigation_count() == 0
    assert audit.requires_operator_attention() is False
    assert audit.all_gateway_decisions_recorded() is True
    assert audit.resolutions[0].decision_status == (
        HumanReviewDecisionStatus.APPROVED_FOR_EXECUTION.value
    )


def test_resolution_audit_marks_evidence_card_manual_investigation() -> None:
    state = _state().with_evidence_support_finding(_unsupported_finding())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)

    audit = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=HumanReviewDecisionLedger.create(()),
    )

    assert audit.resolved_count() == 0
    assert audit.pending_decision_count() == 0
    assert audit.manual_investigation_count() == 1
    assert audit.requires_operator_attention() is True
    assert audit.all_gateway_decisions_recorded() is True
    assert audit.resolutions[0].status is (
        HumanReviewResolutionStatus.MANUAL_INVESTIGATION_REQUIRED
    )


def test_resolution_audit_combines_resolved_and_manual_cards() -> None:
    state = _state().with_action(_review_action()).with_evidence_support_finding(
        _unsupported_finding(),
    )
    action = state.actions.human_review_actions()[0]
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    decision_result = HumanReviewDecisionCoordinator.create().decide_action(
        state=state,
        ledger=HumanReviewDecisionLedger.create(()),
        action_id=action.action_id.value,
        reviewer="Bryce Lovell",
        status=HumanReviewDecisionStatus.REJECTED,
        rationale="Bounded action is rejected by the reviewer.",
    )

    audit = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=decision_result.after_ledger,
    )

    assert audit.resolved_count() == 1
    assert audit.pending_decision_count() == 0
    assert audit.manual_investigation_count() == 1
    assert audit.requires_operator_attention() is True
    assert audit.resolutions[0].status is HumanReviewResolutionStatus.RESOLVED_BY_DECISION
    assert audit.resolutions[1].status is (
        HumanReviewResolutionStatus.MANUAL_INVESTIGATION_REQUIRED
    )


def test_resolution_audit_rejects_empty_resolutions() -> None:
    digest = DigestRecord.from_payload({"record": "resolution-audit"})

    with pytest.raises(FoundationError, match="requires resolutions"):
        HumanReviewResolutionAudit.create(
            bundle_digest=digest,
            decision_ledger_digest=digest,
            state_digest=digest,
            resolutions=(),
        )


def test_resolution_audit_payload_and_digest_are_stable() -> None:
    state = _state().with_action(_review_action())
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    ledger = HumanReviewDecisionLedger.create(())

    first = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=ledger,
    )
    second = HumanReviewResolutionAudit.from_bundle(
        bundle=bundle,
        decision_ledger=ledger,
    )

    payload = first.to_payload()

    assert payload["card_count"] == 1
    assert payload["pending_decision_count"] == 1
    assert payload["requires_operator_attention"] is True
    assert first.digest() == second.digest()
