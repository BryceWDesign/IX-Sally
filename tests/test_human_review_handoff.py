

from __future__ import annotations

import pytest
from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.evidence_support import EvidenceSupportFinding, EvidenceSupportStatus
from ix_sally.foundation import FoundationError
from ix_sally.human_review_bundle_ledger import HumanReviewBundleLedger
from ix_sally.human_review_handoff import (
    HumanReviewHandoffCoordinator,
    HumanReviewHandoffReceipt,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Coordinate human-review handoff.",
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


def test_human_review_handoff_coordinator_appends_operator_bundle() -> None:
    state = _state().with_action(_review_action())
    ledger = HumanReviewBundleLedger.create(())

    result = HumanReviewHandoffCoordinator.create().handoff(
        state=state,
        ledger=ledger,
    )

    assert result.before_ledger == ledger
    assert result.after_ledger.next_sequence() == 2
    assert result.latest_entry() == result.ledger_entry
    assert result.ledger_entry.bundle_digest == result.bundle.digest()
    assert result.receipt.changed_ledger() is True
    assert result.receipt.requires_human_authority() is True


def test_human_review_handoff_coordinator_preserves_custom_authority_note() -> None:
    state = _state().with_action(_review_action())
    ledger = HumanReviewBundleLedger.create(())

    result = HumanReviewHandoffCoordinator.create().handoff(
        state=state,
        ledger=ledger,
        authority_note="Operator must approve the exact bounded action.",
    )

    assert result.bundle.packet.authority_note == (
        "Operator must approve the exact bounded action."
    )
    assert result.ledger_entry.authority_note == (
        "Operator must approve the exact bounded action."
    )
    assert result.receipt.authority_note == (
        "Operator must approve the exact bounded action."
    )


def test_human_review_handoff_coordinator_counts_mixed_targets() -> None:
    state = _state().with_action(_review_action()).with_evidence_support_finding(
        _unsupported_finding(),
    )

    result = HumanReviewHandoffCoordinator.create().handoff(
        state=state,
        ledger=HumanReviewBundleLedger.create(()),
    )

    assert result.target_count() == 2
    assert result.gateway_resolvable_count() == 1
    assert result.manual_investigation_count() == 1
    assert result.blocker_acknowledgment_count() == 0
    assert result.ledger_entry.target_count == 2


def test_human_review_handoff_coordinator_rejects_non_human_review_state() -> None:
    with pytest.raises(
        FoundationError,
        match="expected human_review but observed proposal_intake",
    ):
        HumanReviewHandoffCoordinator.create().handoff(
            state=_state(),
            ledger=HumanReviewBundleLedger.create(()),
        )


def test_human_review_handoff_coordinator_rejects_duplicate_bundle_on_same_ledger() -> None:
    state = _state().with_action(_review_action())
    coordinator = HumanReviewHandoffCoordinator.create()
    first = coordinator.handoff(
        state=state,
        ledger=HumanReviewBundleLedger.create(()),
    )

    with pytest.raises(FoundationError, match="duplicate human-review bundle digest"):
        coordinator.handoff(state=state, ledger=first.after_ledger)


def test_human_review_handoff_receipt_rejects_mismatched_counts() -> None:
    digest = DigestRecord.from_payload({"record": "human-review-handoff"})

    with pytest.raises(FoundationError, match="surfaced counts must equal"):
        HumanReviewHandoffReceipt.create(
            before_ledger_digest=digest,
            after_ledger_digest=digest,
            bundle_digest=digest,
            ledger_entry_digest=digest,
            state_digest=digest,
            target_count=2,
            gateway_resolvable_count=1,
            manual_investigation_count=0,
            blocker_acknowledgment_count=0,
            authority_note="Human authority required.",
        )


def test_human_review_handoff_result_payload_and_digest_are_stable() -> None:
    state = _state().with_action(_review_action())
    ledger = HumanReviewBundleLedger.create(())

    first = HumanReviewHandoffCoordinator.create().handoff(state=state, ledger=ledger)
    second = HumanReviewHandoffCoordinator.create().handoff(state=state, ledger=ledger)

    payload = first.to_payload()

    assert payload["target_count"] == 1
    assert payload["gateway_resolvable_count"] == 1
    assert payload["manual_investigation_count"] == 0
    assert payload["changed_ledger"] is True
    assert payload["requires_human_authority"] is True
    assert first.digest() == second.digest()
    assert first.receipt.digest() == second.receipt.digest()
