

from __future__ import annotations

import pytest
from ix_sally.actions import ActionStatus, BoundedActionLedger, BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.digest import DigestRecord
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.proposals import ProposalAction


def _proposal_action() -> ProposalAction:
    return ProposalAction.create(
        description="Run tests.",
        intended_authority="tool-execution",
        requires_tool=True,
        requires_human_boundary=False,
    )


def test_bounded_action_record_normalizes_fields_and_generates_id() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="  Run tests. ",
        requested_authority=" Tool Execution ",
        proposal_action_digest=proposal_digest,
        tool_key=" Test Runner ",
        requires_tool=True,
        requires_human_boundary=False,
    )

    assert action.action_id.value == "ix-forge-1-tool-execution-run-tests"
    assert action.description == "Run tests."
    assert action.requested_authority.value == "tool-execution"
    assert action.tool_key is not None
    assert action.tool_key.value == "test-runner"
    assert action.status is ActionStatus.PROPOSED
    assert action.blocks_progress() is False


def test_bounded_action_record_rejects_negative_cycle() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})

    with pytest.raises(FoundationError, match="bounded action cycle must not be negative"):
        BoundedActionRecord.create(
            cycle=-1,
            proposed_by=AgentRole.FORGE,
            description="Invalid cycle.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
        )


def test_bounded_action_record_requires_tool_key_for_tool_action() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})

    with pytest.raises(FoundationError, match="bounded tool actions require a tool key"):
        BoundedActionRecord.create(
            cycle=1,
            proposed_by=AgentRole.FORGE,
            description="Run tests.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
            requires_tool=True,
        )


def test_bounded_action_record_rejects_non_sha256_digest() -> None:
    proposal_digest = DigestRecord(algorithm="sha1", value="abc")

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        BoundedActionRecord.create(
            cycle=1,
            proposed_by=AgentRole.FORGE,
            description="Run tests.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
        )


def test_denied_or_blocked_action_requires_boundary_note() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})

    with pytest.raises(FoundationError, match="denied or blocked bounded actions require"):
        BoundedActionRecord.create(
            cycle=1,
            proposed_by=AgentRole.FORGE,
            description="Run tests.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
            status=ActionStatus.DENIED,
        )


def test_authorized_action_requires_authority_decision_digest() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})

    with pytest.raises(FoundationError, match="authorized bounded actions require"):
        BoundedActionRecord.create(
            cycle=1,
            proposed_by=AgentRole.FORGE,
            description="Run tests.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
            status=ActionStatus.AUTHORIZED,
        )


def test_executed_action_requires_execution_digest() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    authority_digest = DigestRecord.from_payload({"authority": "allowed"})

    with pytest.raises(FoundationError, match="executed bounded actions require"):
        BoundedActionRecord.create(
            cycle=1,
            proposed_by=AgentRole.FORGE,
            description="Run tests.",
            requested_authority="tool-execution",
            proposal_action_digest=proposal_digest,
            status=ActionStatus.EXECUTED,
            authority_decision_digest=authority_digest,
        )


def test_bounded_action_record_from_proposal_action() -> None:
    proposal_action = _proposal_action()

    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.SALLY,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )

    assert action.action_id == proposal_action.action_id
    assert action.description == "Run tests."
    assert action.proposed_by is AgentRole.SALLY
    assert action.requested_authority.value == "tool-execution"
    assert action.proposal_action_digest == proposal_action.digest()
    assert action.requires_tool is True
    assert action.tool_key is not None
    assert action.tool_key.value == "test-runner"


def test_bounded_action_record_converts_to_authority_request() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )

    request = action.to_authority_request()

    assert request.cycle == 1
    assert request.requesting_role is AgentRole.FORGE
    assert request.action_digest == action.digest()
    assert request.requested_authority.value == "tool-execution"
    assert request.summary == "Run tests."
    assert request.tool_key is not None
    assert request.tool_key.value == "test-runner"
    assert request.requires_tool is True
    assert request.requires_human_boundary is False


def test_bounded_action_record_updates_from_allowed_authority_decision() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )

    updated = action.with_authority_decision(decision)

    assert updated.status is ActionStatus.AUTHORIZED
    assert updated.allows_execution() is True
    assert updated.authority_decision_digest == decision.digest()


def test_bounded_action_record_updates_from_human_review_decision() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.HUMAN_REVIEW_REQUIRED,
        rationale="Human review required.",
        human_review_note="Human boundary review is required.",
    )

    updated = action.with_authority_decision(decision)

    assert updated.status is ActionStatus.HUMAN_REVIEW_REQUIRED
    assert updated.requires_human_review() is True
    assert updated.blocks_progress() is True
    assert updated.boundary_note == "Human boundary review is required."


def test_bounded_action_record_updates_from_denied_authority_decision() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.DENIED,
        rationale="Denied.",
        contract_note="Tool is not allowed.",
    )

    updated = action.with_authority_decision(decision)

    assert updated.status is ActionStatus.DENIED
    assert updated.blocks_progress() is True
    assert updated.boundary_note == "Tool is not allowed."


def test_bounded_action_record_rejects_authority_decision_cycle_mismatch() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )
    decision = AuthorityDecision.create(
        cycle=2,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Wrong cycle.",
    )

    with pytest.raises(FoundationError, match="authority decision must match"):
        action.with_authority_decision(decision)


def test_bounded_action_record_marks_authorized_action_executed() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    authorized = action.with_authority_decision(decision)
    execution_digest = DigestRecord.from_payload({"execution": "passed"})

    executed = authorized.with_execution_digest(execution_digest)

    assert executed.status is ActionStatus.EXECUTED
    assert executed.execution_digest == execution_digest


def test_bounded_action_record_rejects_execution_before_authorization() -> None:
    proposal_action = _proposal_action()
    action = BoundedActionRecord.from_proposal_action(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        proposal_action=proposal_action,
        tool_key="test-runner",
    )

    with pytest.raises(FoundationError, match="only authorized bounded actions"):
        action.with_execution_digest(DigestRecord.from_payload({"execution": "passed"}))


def test_bounded_action_payload_is_stable() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    authority_digest = DigestRecord.from_payload({"authority": "allowed"})
    action = BoundedActionRecord.create(
        action_id=CanonicalKey.from_text("action-one", field_name="action_id"),
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
        status=ActionStatus.AUTHORIZED,
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
        authority_decision_digest=authority_digest,
    )

    assert action.to_payload() == {
        "action_id": "action-one",
        "cycle": 1,
        "proposed_by": "ix-forge",
        "description": "Run tests.",
        "requested_authority": "tool-execution",
        "proposal_action_digest": {
            "algorithm": "sha256",
            "value": proposal_digest.value,
        },
        "status": "authorized",
        "tool_key": "test-runner",
        "requires_tool": True,
        "requires_memory_write": False,
        "requires_human_boundary": False,
        "authority_decision_digest": {
            "algorithm": "sha256",
            "value": authority_digest.value,
        },
        "execution_digest": None,
        "boundary_note": None,
        "allows_execution": True,
        "requires_human_review": False,
        "blocks_progress": False,
    }


def test_bounded_action_ledger_filters_actions() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    authority_digest = DigestRecord.from_payload({"authority": "allowed"})
    authorized = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
        status=ActionStatus.AUTHORIZED,
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
        authority_decision_digest=authority_digest,
    )
    human = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run reviewed tests.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
        status=ActionStatus.HUMAN_REVIEW_REQUIRED,
        tool_key="test-runner",
        requires_tool=True,
        boundary_note="Human review required.",
    )
    ledger = BoundedActionLedger.create((authorized, human))

    assert ledger.executable_actions() == (authorized,)
    assert ledger.human_review_actions() == (human,)
    assert ledger.blocked_actions() == (human,)
    assert ledger.require_action(authorized.action_id.value) == authorized


def test_bounded_action_ledger_rejects_duplicate_action_ids() -> None:
    action_id = CanonicalKey.from_text("same-action", field_name="action_id")
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    first = BoundedActionRecord.create(
        action_id=action_id,
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="First action.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
    )
    second = BoundedActionRecord.create(
        action_id=action_id,
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Second action.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
    )

    with pytest.raises(FoundationError, match="duplicate bounded action id"):
        BoundedActionLedger.create((first, second))


def test_bounded_action_ledger_digest_changes_when_status_changes() -> None:
    proposal_digest = DigestRecord.from_payload({"proposal_action": "run tests"})
    proposed = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
    )
    denied = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Run tests.",
        requested_authority="tool-execution",
        proposal_action_digest=proposal_digest,
        status=ActionStatus.DENIED,
        boundary_note="Denied.",
    )

    assert (
        BoundedActionLedger.create((proposed,)).digest().value
        != BoundedActionLedger.create((denied,)).digest().value
    )
