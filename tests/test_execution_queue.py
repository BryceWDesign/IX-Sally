

from __future__ import annotations

import pytest
from ix_sally.actions import ActionStatus, BoundedActionLedger, BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.authorization import AuthorityDecision, AuthorityDecisionStatus
from ix_sally.digest import DigestRecord
from ix_sally.execution_queue import ExecutionQueue, ExecutionQueueItem, ExecutionQueueStatus
from ix_sally.foundation import CanonicalKey, FoundationError


def _proposed_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    return BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description=description,
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": description}),
        tool_key="test-runner",
        requires_tool=True,
        requires_human_boundary=False,
    )


def _authorized_action(*, description: str = "Run tests.") -> BoundedActionRecord:
    action = _proposed_action(description=description)
    decision = AuthorityDecision.create(
        cycle=1,
        request_digest=action.to_authority_request().digest(),
        status=AuthorityDecisionStatus.ALLOWED,
        rationale="Allowed.",
    )
    return action.with_authority_decision(decision)


def test_execution_queue_item_from_authorized_action() -> None:
    action = _authorized_action()

    item = ExecutionQueueItem.from_action(action)

    assert item.queue_id.value == f"1-ix-forge-{action.action_id.value}"
    assert item.cycle == 1
    assert item.action_digest == action.digest()
    assert item.action_id == action.action_id
    assert item.requested_authority == action.requested_authority
    assert item.dispatch_role is AgentRole.FORGE
    assert item.description == "Run tests."
    assert item.status is ExecutionQueueStatus.QUEUED


def test_execution_queue_item_rejects_unauthorized_action() -> None:
    action = _proposed_action()

    with pytest.raises(FoundationError, match="only authorized bounded actions"):
        ExecutionQueueItem.from_action(action)


def test_execution_queue_item_rejects_negative_cycle() -> None:
    action_digest = DigestRecord.from_payload({"action": "run tests"})

    with pytest.raises(FoundationError, match="execution queue item cycle must not be negative"):
        ExecutionQueueItem.create(
            cycle=-1,
            action_digest=action_digest,
            action_id=CanonicalKey.from_text("action-one", field_name="action_id"),
            requested_authority=CanonicalKey.from_text(
                "tool-execution",
                field_name="requested_authority",
            ),
            description="Invalid cycle.",
        )


def test_execution_queue_item_rejects_non_sha256_digest() -> None:
    with pytest.raises(FoundationError, match="digest algorithm mismatch"):
        ExecutionQueueItem.create(
            cycle=1,
            action_digest=DigestRecord(algorithm="sha1", value="abc"),
            action_id=CanonicalKey.from_text("action-one", field_name="action_id"),
            requested_authority=CanonicalKey.from_text(
                "tool-execution",
                field_name="requested_authority",
            ),
            description="Invalid digest.",
        )


def test_skipped_queue_item_requires_skip_reason() -> None:
    action = _authorized_action()

    with pytest.raises(FoundationError, match="skipped execution queue items require"):
        ExecutionQueueItem.create(
            cycle=action.cycle,
            action_digest=action.digest(),
            action_id=action.action_id,
            requested_authority=action.requested_authority,
            description=action.description,
            status=ExecutionQueueStatus.SKIPPED,
        )


def test_non_skipped_queue_item_rejects_skip_reason() -> None:
    action = _authorized_action()

    with pytest.raises(FoundationError, match="only skipped execution queue items"):
        ExecutionQueueItem.create(
            cycle=action.cycle,
            action_digest=action.digest(),
            action_id=action.action_id,
            requested_authority=action.requested_authority,
            description=action.description,
            skip_reason="Not valid for queued item.",
        )


def test_execution_queue_item_dispatches_once() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())

    dispatched = item.dispatched()

    assert dispatched.status is ExecutionQueueStatus.DISPATCHED
    assert dispatched.queue_id == item.queue_id

    with pytest.raises(FoundationError, match="only queued execution items"):
        dispatched.dispatched()


def test_execution_queue_item_skips_queued_item() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())

    skipped = item.skipped(reason="Execution disabled by test.")

    assert skipped.status is ExecutionQueueStatus.SKIPPED
    assert skipped.skip_reason == "Execution disabled by test."

    with pytest.raises(FoundationError, match="dispatched execution items cannot be skipped"):
        item.dispatched().skipped(reason="Too late.")


def test_execution_queue_item_payload_is_stable() -> None:
    action = _authorized_action()
    item = ExecutionQueueItem.create(
        queue_id=CanonicalKey.from_text("queue-one", field_name="queue_id"),
        cycle=action.cycle,
        action_digest=action.digest(),
        action_id=action.action_id,
        requested_authority=action.requested_authority,
        description=action.description,
    )

    assert item.to_payload() == {
        "queue_id": "queue-one",
        "cycle": 1,
        "action_digest": {
            "algorithm": "sha256",
            "value": action.digest().value,
        },
        "action_id": action.action_id.value,
        "requested_authority": "tool-execution",
        "dispatch_role": "ix-forge",
        "description": "Run tests.",
        "status": "queued",
        "skip_reason": None,
    }


def test_execution_queue_from_action_ledger_queues_only_authorized_actions() -> None:
    authorized = _authorized_action(description="Run allowed tests.")
    proposed = _proposed_action(description="Still proposed.")
    denied = BoundedActionRecord.create(
        cycle=1,
        proposed_by=AgentRole.FORGE,
        description="Denied action.",
        requested_authority="tool-execution",
        proposal_action_digest=DigestRecord.from_payload({"proposal_action": "denied"}),
        status=ActionStatus.DENIED,
        boundary_note="Denied by contract.",
    )
    ledger = BoundedActionLedger.create((authorized, proposed, denied))

    queue = ExecutionQueue.from_action_ledger(ledger)

    assert len(queue.items) == 1
    assert queue.items[0].action_id == authorized.action_id
    assert queue.queued_items() == queue.items
    assert queue.dispatched_items() == ()
    assert queue.skipped_items() == ()


def test_execution_queue_replaces_existing_item() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())
    queue = ExecutionQueue.create((item,))

    updated = queue.replace(item.dispatched())

    assert updated.queued_items() == ()
    assert len(updated.dispatched_items()) == 1


def test_execution_queue_rejects_unknown_replacement() -> None:
    first = ExecutionQueueItem.from_action(_authorized_action(description="First action."))
    second = ExecutionQueueItem.from_action(_authorized_action(description="Second action."))
    queue = ExecutionQueue.create((first,))

    with pytest.raises(FoundationError, match="unknown execution queue item id"):
        queue.replace(second)


def test_execution_queue_rejects_duplicate_queue_ids() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())

    with pytest.raises(FoundationError, match="duplicate execution queue item id"):
        ExecutionQueue.create((item, item))


def test_execution_queue_digest_changes_when_item_status_changes() -> None:
    item = ExecutionQueueItem.from_action(_authorized_action())

    queued = ExecutionQueue.create((item,))
    dispatched = queued.replace(item.dispatched())

    assert queued.digest().value != dispatched.digest().value
