"""Execution planning flow for authorized IX-Sally bounded actions."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.actions import BoundedActionRecord
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.execution_queue import ExecutionQueueItem
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class ExecutionPlanningResult:
    """Result of queueing authorized bounded actions for IX-Forge."""

    state: NinefoldRunState
    queued_items: tuple[ExecutionQueueItem, ...]
    skipped_actions: tuple[BoundedActionRecord, ...]

    def queued_count(self) -> int:
        """Return the number of newly queued execution items."""
        return len(self.queued_items)

    def skipped_count(self) -> int:
        """Return the number of authorized actions skipped because they were already queued."""
        return len(self.skipped_actions)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible execution planning result."""
        queued_payload: JsonArray = []
        for item in self.queued_items:
            queued_payload.append(item.to_payload())

        skipped_payload: JsonArray = []
        for action in self.skipped_actions:
            skipped_payload.append(action.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "queued_count": self.queued_count(),
            "skipped_count": self.skipped_count(),
            "queued_items": queued_payload,
            "skipped_actions": skipped_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this execution planning result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class ExecutionPlanner:
    """Plans IX-Forge execution queue entries from authorized bounded actions."""

    recorder: StateRecorder

    def queue_action(
        self,
        *,
        state: NinefoldRunState,
        action: BoundedActionRecord,
    ) -> ExecutionPlanningResult:
        """Queue one authorized bounded action for execution."""
        try:
            existing = state.actions.require_action(action.action_id.value)
        except FoundationError as error:
            raise FoundationError("action does not match state ledger") from error

        if existing != action:
            raise FoundationError("action does not match state ledger")

        if not action.allows_execution():
            raise FoundationError("only authorized bounded actions may be queued for execution")

        if self._is_action_already_queued(state=state, action=action):
            return ExecutionPlanningResult(
                state=state,
                queued_items=(),
                skipped_actions=(action,),
            )

        item = ExecutionQueueItem.from_action(action)
        updated = self.recorder.record_execution_queue_item(state, item)

        return ExecutionPlanningResult(
            state=updated,
            queued_items=(item,),
            skipped_actions=(),
        )

    def queue_all_authorized(self, *, state: NinefoldRunState) -> ExecutionPlanningResult:
        """Queue every authorized bounded action not already present in the execution queue."""
        current = state
        queued: list[ExecutionQueueItem] = []
        skipped: list[BoundedActionRecord] = []

        for action in state.actions.executable_actions():
            result = self.queue_action(state=current, action=action)
            current = result.state
            queued.extend(result.queued_items)
            skipped.extend(result.skipped_actions)

        return ExecutionPlanningResult(
            state=current,
            queued_items=tuple(queued),
            skipped_actions=tuple(skipped),
        )

    def _is_action_already_queued(
        self,
        *,
        state: NinefoldRunState,
        action: BoundedActionRecord,
    ) -> bool:
        """Return whether an action already has an execution queue item."""
        return any(item.action_id == action.action_id for item in state.execution_queue.items)
