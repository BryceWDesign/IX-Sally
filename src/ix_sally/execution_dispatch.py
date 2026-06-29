"""Execution dispatch flow for queued IX-Sally Forge items."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class ExecutionDispatchResult:
    """Result of dispatching one queued execution item."""

    state: NinefoldRunState
    original_item: ExecutionQueueItem
    dispatched_item: ExecutionQueueItem

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible execution dispatch result."""
        return {
            "state_digest": self.state.digest().value,
            "original_item_digest": self.original_item.digest().value,
            "dispatched_item_digest": self.dispatched_item.digest().value,
            "queue_id": self.dispatched_item.queue_id.value,
            "action_id": self.dispatched_item.action_id.value,
            "status": self.dispatched_item.status.value,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this dispatch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ExecutionDispatchBatchResult:
    """Result of dispatching all queued execution items in ledger order."""

    state: NinefoldRunState
    dispatched: tuple[ExecutionDispatchResult, ...]

    def dispatched_count(self) -> int:
        """Return the number of queue items dispatched."""
        return len(self.dispatched)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible batch dispatch result."""
        dispatched_payload: JsonArray = []
        for result in self.dispatched:
            dispatched_payload.append(result.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "dispatched_count": self.dispatched_count(),
            "dispatched": dispatched_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this batch dispatch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ExecutionDispatcher:
    """Dispatches queued IX-Sally execution items to the Forge boundary."""

    recorder: StateRecorder

    def dispatch_item(
        self,
        *,
        state: NinefoldRunState,
        item: ExecutionQueueItem,
    ) -> ExecutionDispatchResult:
        """Dispatch one queued execution item and record the queue-state transition."""
        existing = self._require_matching_item(state=state, item=item)
        dispatched = existing.dispatched()
        updated = self.recorder.replace_execution_queue_item(state, dispatched)

        return ExecutionDispatchResult(
            state=updated,
            original_item=existing,
            dispatched_item=dispatched,
        )

    def dispatch_all_queued(self, *, state: NinefoldRunState) -> ExecutionDispatchBatchResult:
        """Dispatch every currently queued execution item in ledger order."""
        current = state
        dispatched_results: list[ExecutionDispatchResult] = []

        for item in state.execution_queue.queued_items():
            result = self.dispatch_item(state=current, item=item)
            current = result.state
            dispatched_results.append(result)

        return ExecutionDispatchBatchResult(
            state=current,
            dispatched=tuple(dispatched_results),
        )

    def _require_matching_item(
        self,
        *,
        state: NinefoldRunState,
        item: ExecutionQueueItem,
    ) -> ExecutionQueueItem:
        """Return the matching queue item from state or raise if it differs."""
        for existing in state.execution_queue.items:
            if existing.queue_id == item.queue_id:
                if existing != item:
                    raise FoundationError("execution dispatcher item does not match state queue")
                return existing

        raise FoundationError(f"unknown execution queue item id: {item.queue_id.value}")
