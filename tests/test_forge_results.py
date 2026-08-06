from __future__ import annotations

import pytest

from ix_sally.actions import BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.digest import DigestRecord
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.forge_results import ForgeResultLedger, ForgeResultRecord, ForgeResultStatus
from ix_sally.foundation import CanonicalKey, FoundationError


def _authorized_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    action = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def _dispatched_item(
    *,
    action: BoundedActionRecord | None = None,
) -> tuple[BoundedActionRecord, ExecutionQueueItem]:
    selected_action = action or _authorized_action()
    return selected_action, ExecutionQueueItem.from_action(selected_action).dispatched()


def test_forge_result_from_dispatched_item_and_matching_action() -> None:
    action, item = _dispatched_item()

    result = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Tests passed.",
        observed_output="1 passed",
    )

    assert result.result_id.value == f"1-ix-forge-{action.action_id.value}-passed"
    assert result.cycle == 1
    assert result.queue_item_digest == item.digest()
    assert result.action_id == action.action_id
    assert result.action_digest == action.digest()
    assert result.executed_by is AgentRole.FORGE
    assert result.status is ForgeResultStatus.PASSED
    assert result.succeeded() is True
    assert result.requires_human_review() is False


def test_forge_result_rejects_non_dispatched_queue_item() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.from_action(action)

    with pytest.raises(FoundationError, match="require a dispatched execution queue item"):
        ForgeResultRecord.from_dispatched_item(
            item=item,
            action=action,
            status=ForgeResultStatus.PASSED,
            summary="Not dispatched.",
        )


def test_forge_result_rejects_mismatched_action_id() -> None:
    first_action, item = _dispatched_item()
    second_action = _authorized_action(description="Run another test.")

    assert first_action.action_id != second_action.action_id

    with pytest.raises(FoundationError, match="must match bounded action id"):
        ForgeResultRecord.from_dispatched_item(
            item=item,
            action=second_action,
            status=ForgeResultStatus.PASSED,
            summary="Wrong action.",
        )


def test_forge_result_rejects_negative_cycle() -> None:
    action, item = _dispatched_item()

    with pytest.raises(FoundationError, match="Forge result cycle must not be negative"):
        ForgeResultRecord.create(
            cycle=-1,
            queue_item_digest=item.digest(),
            action_id=action.action_id,
            action_digest=action.digest(),
            status=ForgeResultStatus.PASSED,
            summary="Invalid cycle.",
        )


def test_forge_result_rejects_non_sha256_digest() -> None:
    action, _item = _dispatched_item()

    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        ForgeResultRecord.create(
            cycle=1,
            queue_item_digest=DigestRecord(algorithm="sha1", value="abc"),
            action_id=action.action_id,
            action_digest=action.digest(),
            status=ForgeResultStatus.PASSED,
            summary="Invalid digest.",
        )


def test_failed_forge_result_requires_failure_reason() -> None:
    action, item = _dispatched_item()

    with pytest.raises(FoundationError, match="failed Forge results require"):
        ForgeResultRecord.create(
            cycle=1,
            queue_item_digest=item.digest(),
            action_id=action.action_id,
            action_digest=action.digest(),
            status=ForgeResultStatus.FAILED,
            summary="Tests failed.",
        )


def test_blocked_forge_result_requires_boundary_note() -> None:
    action, item = _dispatched_item()

    with pytest.raises(FoundationError, match="blocked Forge results require"):
        ForgeResultRecord.create(
            cycle=1,
            queue_item_digest=item.digest(),
            action_id=action.action_id,
            action_digest=action.digest(),
            status=ForgeResultStatus.BLOCKED,
            summary="Execution blocked.",
        )


def test_passed_forge_result_rejects_failure_reason() -> None:
    action, item = _dispatched_item()

    with pytest.raises(FoundationError, match="must not carry a failure reason"):
        ForgeResultRecord.create(
            cycle=1,
            queue_item_digest=item.digest(),
            action_id=action.action_id,
            action_digest=action.digest(),
            status=ForgeResultStatus.PASSED,
            summary="Tests passed.",
            failure_reason="Contradictory failure.",
        )


def test_forge_result_payload_is_stable() -> None:
    action, item = _dispatched_item()
    result = ForgeResultRecord.create(
        result_id=CanonicalKey.from_text("result-one", field_name="result_id"),
        cycle=1,
        queue_item_digest=item.digest(),
        action_id=action.action_id,
        action_digest=action.digest(),
        status=ForgeResultStatus.FAILED,
        summary="Tests failed.",
        observed_output="1 failed",
        failure_reason="Assertion failed.",
    )

    assert result.to_payload() == {
        "result_id": "result-one",
        "cycle": 1,
        "queue_item_digest": {
            "algorithm": "sha256",
            "value": item.digest().value,
        },
        "action_id": action.action_id.value,
        "action_digest": {
            "algorithm": "sha256",
            "value": action.digest().value,
        },
        "executed_by": "ix-forge",
        "status": "failed",
        "summary": "Tests failed.",
        "observed_output": "1 failed",
        "failure_reason": "Assertion failed.",
        "boundary_note": None,
        "succeeded": False,
        "failed": True,
        "blocked": False,
        "requires_human_review": True,
    }


def test_forge_result_ledger_filters_results() -> None:
    first_action, first_item = _dispatched_item(
        action=_authorized_action(description="Run passing tests.")
    )
    second_action, second_item = _dispatched_item(
        action=_authorized_action(description="Run failing tests.")
    )
    third_action, third_item = _dispatched_item(
        action=_authorized_action(description="Run blocked tests.")
    )
    passed = ForgeResultRecord.from_dispatched_item(
        item=first_item,
        action=first_action,
        status=ForgeResultStatus.PASSED,
        summary="Passed.",
    )
    failed = ForgeResultRecord.from_dispatched_item(
        item=second_item,
        action=second_action,
        status=ForgeResultStatus.FAILED,
        summary="Failed.",
        failure_reason="Assertion failed.",
    )
    blocked = ForgeResultRecord.from_dispatched_item(
        item=third_item,
        action=third_action,
        status=ForgeResultStatus.BLOCKED,
        summary="Blocked.",
        boundary_note="Boundary denied execution.",
    )

    ledger = ForgeResultLedger.create((passed, failed, blocked))

    assert ledger.passed_results() == (passed,)
    assert ledger.failed_results() == (failed,)
    assert ledger.blocked_results() == (blocked,)
    assert ledger.human_review_results() == (failed, blocked)
    assert ledger.to_payload()["human_review_count"] == 2


def test_forge_result_ledger_rejects_duplicate_result_ids() -> None:
    action, item = _dispatched_item()
    result = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Passed.",
    )

    with pytest.raises(FoundationError, match="duplicate Forge result id"):
        ForgeResultLedger.create((result, result))


def test_forge_result_digest_changes_when_status_changes() -> None:
    action, item = _dispatched_item()
    passed = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.PASSED,
        summary="Passed.",
    )
    failed = ForgeResultRecord.from_dispatched_item(
        item=item,
        action=action,
        status=ForgeResultStatus.FAILED,
        summary="Failed.",
        failure_reason="Assertion failed.",
    )

    assert passed.digest().value != failed.digest().value
