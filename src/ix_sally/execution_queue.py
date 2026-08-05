"""Execution queue records for authorized IX-Sally bounded actions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.actions import BoundedActionLedger, BoundedActionRecord
from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class ExecutionQueueStatus(StrEnum):
    """Status assigned to a queued action before Forge execution."""

    QUEUED = "queued"
    DISPATCHED = "dispatched"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ExecutionQueueItem:
    """One authorized bounded action queued for IX-Forge execution."""

    queue_id: CanonicalKey
    cycle: int
    action_digest: DigestRecord
    action_id: CanonicalKey
    requested_authority: CanonicalKey
    dispatch_role: AgentRole
    description: str
    status: ExecutionQueueStatus = ExecutionQueueStatus.QUEUED
    skip_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        action_digest: DigestRecord,
        action_id: CanonicalKey,
        requested_authority: CanonicalKey,
        description: str,
        dispatch_role: AgentRole = AgentRole.FORGE,
        status: ExecutionQueueStatus = ExecutionQueueStatus.QUEUED,
        skip_reason: str | None = None,
        queue_id: CanonicalKey | None = None,
    ) -> ExecutionQueueItem:
        """Create a normalized execution queue item."""
        if cycle < 0:
            raise FoundationError("execution queue item cycle must not be negative")

        action_digest.require_algorithm("sha256")
        normalized_description = require_text(description, field_name="description")

        if status is ExecutionQueueStatus.SKIPPED and skip_reason is None:
            raise FoundationError("skipped execution queue items require a skip reason")

        if status is not ExecutionQueueStatus.SKIPPED and skip_reason is not None:
            raise FoundationError("only skipped execution queue items may carry a skip reason")

        return cls(
            queue_id=queue_id
            or CanonicalKey.from_text(
                f"{cycle}-{dispatch_role.value}-{action_id.value}",
                field_name="queue_id",
            ),
            cycle=cycle,
            action_digest=action_digest,
            action_id=action_id,
            requested_authority=requested_authority,
            dispatch_role=dispatch_role,
            description=normalized_description,
            status=status,
            skip_reason=skip_reason,
        )

    @classmethod
    def from_action(cls, action: BoundedActionRecord) -> ExecutionQueueItem:
        """Create a queue item from an authorized bounded action."""
        if not action.allows_execution():
            raise FoundationError("only authorized bounded actions may be queued for execution")

        return cls.create(
            cycle=action.cycle,
            action_digest=action.digest(),
            action_id=action.action_id,
            requested_authority=action.requested_authority,
            description=action.description,
        )

    def dispatched(self) -> ExecutionQueueItem:
        """Return this queue item marked as dispatched."""
        if self.status is not ExecutionQueueStatus.QUEUED:
            raise FoundationError("only queued execution items may be dispatched")

        return ExecutionQueueItem.create(
            queue_id=self.queue_id,
            cycle=self.cycle,
            action_digest=self.action_digest,
            action_id=self.action_id,
            requested_authority=self.requested_authority,
            dispatch_role=self.dispatch_role,
            description=self.description,
            status=ExecutionQueueStatus.DISPATCHED,
        )

    def skipped(self, *, reason: str) -> ExecutionQueueItem:
        """Return this queue item marked as skipped."""
        if self.status is ExecutionQueueStatus.DISPATCHED:
            raise FoundationError("dispatched execution items cannot be skipped")

        return ExecutionQueueItem.create(
            queue_id=self.queue_id,
            cycle=self.cycle,
            action_digest=self.action_digest,
            action_id=self.action_id,
            requested_authority=self.requested_authority,
            dispatch_role=self.dispatch_role,
            description=self.description,
            status=ExecutionQueueStatus.SKIPPED,
            skip_reason=require_text(reason, field_name="reason"),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible queue item representation."""
        return {
            "queue_id": self.queue_id.value,
            "cycle": self.cycle,
            "action_digest": {
                "algorithm": self.action_digest.algorithm,
                "value": self.action_digest.value,
            },
            "action_id": self.action_id.value,
            "requested_authority": self.requested_authority.value,
            "dispatch_role": self.dispatch_role.value,
            "description": self.description,
            "status": self.status.value,
            "skip_reason": self.skip_reason,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this queue item."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ExecutionQueue:
    """Immutable queue of authorized actions waiting for IX-Forge dispatch."""

    items: tuple[ExecutionQueueItem, ...]

    @classmethod
    def create(cls, items: Iterable[ExecutionQueueItem]) -> ExecutionQueue:
        """Create a queue and reject duplicate queue item identifiers."""
        normalized = tuple(items)
        seen: set[str] = set()

        for item in normalized:
            if item.queue_id.value in seen:
                raise FoundationError(f"duplicate execution queue item id: {item.queue_id.value}")
            seen.add(item.queue_id.value)

        return cls(items=normalized)

    @classmethod
    def from_action_ledger(cls, ledger: BoundedActionLedger) -> ExecutionQueue:
        """Queue every action currently authorized for execution."""
        return cls.create(
            ExecutionQueueItem.from_action(action)
            for action in ledger.executable_actions()
        )

    def append(self, item: ExecutionQueueItem) -> ExecutionQueue:
        """Return a new queue with an appended item."""
        return ExecutionQueue.create((*self.items, item))

    def replace(self, item: ExecutionQueueItem) -> ExecutionQueue:
        """Return a new queue with an existing queue item replaced."""
        replaced = False
        updated: list[ExecutionQueueItem] = []

        for existing in self.items:
            if existing.queue_id == item.queue_id:
                updated.append(item)
                replaced = True
            else:
                updated.append(existing)

        if not replaced:
            raise FoundationError(f"unknown execution queue item id: {item.queue_id.value}")

        return ExecutionQueue.create(tuple(updated))

    def queued_items(self) -> tuple[ExecutionQueueItem, ...]:
        """Return items still waiting for dispatch."""
        return tuple(item for item in self.items if item.status is ExecutionQueueStatus.QUEUED)

    def dispatched_items(self) -> tuple[ExecutionQueueItem, ...]:
        """Return items already dispatched."""
        return tuple(item for item in self.items if item.status is ExecutionQueueStatus.DISPATCHED)

    def skipped_items(self) -> tuple[ExecutionQueueItem, ...]:
        """Return skipped queue items."""
        return tuple(item for item in self.items if item.status is ExecutionQueueStatus.SKIPPED)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible execution queue representation."""
        item_payload: JsonArray = []
        for item in self.items:
            item_payload.append(item.to_payload())

        return {
            "items": item_payload,
            "queued_count": len(self.queued_items()),
            "dispatched_count": len(self.dispatched_items()),
            "skipped_count": len(self.skipped_items()),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this execution queue."""
        return DigestRecord.from_payload(self.to_payload())
