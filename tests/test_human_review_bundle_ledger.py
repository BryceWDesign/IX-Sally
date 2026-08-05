

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
from ix_sally.human_review_bundle_ledger import (
    HumanReviewBundleLedger,
    HumanReviewBundleLedgerEntry,
)
from ix_sally.runtime import NinefoldRuntimeKit
from ix_sally.state import NinefoldRunState


def _state() -> NinefoldRunState:
    contract = AutonomyContract.create(
        goal="Ledger human-review operator bundles.",
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


def _bundle(description: str = "Run human-boundary verification."):
    return HumanReviewBundleAssembler.create().assemble(
        state=_state().with_action(_review_action(description)),
    )


def test_human_review_bundle_ledger_entry_records_operator_bundle() -> None:
    bundle = _bundle()

    entry = HumanReviewBundleLedgerEntry.from_bundle(sequence=1, bundle=bundle)

    assert entry.sequence == 1
    assert entry.bundle_digest == bundle.digest()
    assert entry.receipt_digest == bundle.receipt.digest()
    assert entry.state_digest == bundle.snapshot.state_digest
    assert entry.target_count == 1
    assert entry.gateway_resolvable_count == 1
    assert entry.manual_investigation_count == 0
    assert entry.requires_human_authority() is True


def test_human_review_bundle_ledger_appends_bundle_at_next_sequence() -> None:
    bundle = _bundle()
    ledger = HumanReviewBundleLedger.create(())

    updated = ledger.append_bundle(bundle)

    assert updated.next_sequence() == 2
    assert updated.latest() is not None
    assert updated.latest().bundle_digest == bundle.digest()
    assert updated.gateway_resolvable_entries() == (updated.latest(),)


def test_human_review_bundle_ledger_rejects_duplicate_bundle_digest() -> None:
    bundle = _bundle()
    first = HumanReviewBundleLedgerEntry.from_bundle(sequence=1, bundle=bundle)
    duplicate = HumanReviewBundleLedgerEntry.from_bundle(sequence=2, bundle=bundle)

    with pytest.raises(FoundationError, match="duplicate human-review bundle digest"):
        HumanReviewBundleLedger.create((first, duplicate))


def test_human_review_bundle_ledger_rejects_duplicate_sequence() -> None:
    first = HumanReviewBundleLedgerEntry.from_bundle(
        sequence=1,
        bundle=_bundle("Run first human-boundary verification."),
    )
    second = HumanReviewBundleLedgerEntry.from_bundle(
        sequence=1,
        bundle=_bundle("Run second human-boundary verification."),
    )

    with pytest.raises(
        FoundationError,
        match="duplicate human-review bundle ledger sequence",
    ):
        HumanReviewBundleLedger.create((first, second))


def test_human_review_bundle_ledger_rejects_mismatched_counts() -> None:
    digest = DigestRecord.from_payload({"record": "bundle-ledger-entry"})

    with pytest.raises(FoundationError, match="surfaced counts must equal"):
        HumanReviewBundleLedgerEntry.create(
            sequence=1,
            bundle_digest=digest,
            receipt_digest=digest,
            state_digest=digest,
            snapshot_digest=digest,
            docket_digest=digest,
            packet_digest=digest,
            target_count=2,
            gateway_resolvable_count=1,
            manual_investigation_count=0,
            blocker_acknowledgment_count=0,
            authority_note="Human authority required.",
        )


def test_human_review_bundle_ledger_filters_manual_investigation_entries() -> None:
    state = _state().with_action(_review_action()).with_evidence_support_finding(
        _unsupported_finding(),
    )
    bundle = HumanReviewBundleAssembler.create().assemble(state=state)
    ledger = HumanReviewBundleLedger.create(()).append_bundle(bundle)

    assert len(ledger.gateway_resolvable_entries()) == 1
    assert len(ledger.manual_investigation_entries()) == 1
    assert len(ledger.blocker_acknowledgment_entries()) == 0
    assert ledger.latest() is not None
    assert ledger.latest().target_count == 2


def test_human_review_bundle_ledger_payload_and_digest_are_stable() -> None:
    bundle = _bundle()

    first = HumanReviewBundleLedger.create(()).append_bundle(bundle)
    second = HumanReviewBundleLedger.create(()).append_bundle(bundle)

    payload = first.to_payload()
    latest = first.latest()

    assert latest is not None
    assert payload["entry_count"] == 1
    assert payload["next_sequence"] == 2
    assert payload["latest_entry_digest"] == latest.digest().value
    assert payload["gateway_resolvable_entry_count"] == 1
    assert first.digest() == second.digest()
