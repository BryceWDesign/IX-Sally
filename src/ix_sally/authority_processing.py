"""Authority processing flow for bounded IX-Sally actions."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.actions import BoundedActionRecord
from ix_sally.authorization import AuthorityDecision, decide_authority_request
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError
from ix_sally.recording import StateRecorder
from ix_sally.state import NinefoldRunState


@dataclass(frozen=True, slots=True)
class AuthorityProcessingResult:
    """Result of processing one bounded action through authority gates."""

    state: NinefoldRunState
    original_action: BoundedActionRecord
    authority_decision: AuthorityDecision
    updated_action: BoundedActionRecord

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible authority processing result."""
        return {
            "state_digest": self.state.digest().value,
            "original_action_digest": self.original_action.digest().value,
            "authority_decision_digest": self.authority_decision.digest().value,
            "updated_action_digest": self.updated_action.digest().value,
            "updated_action_status": self.updated_action.status.value,
            "allows_execution": self.updated_action.allows_execution(),
            "requires_human_review": self.updated_action.requires_human_review(),
            "blocks_progress": self.updated_action.blocks_progress(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this authority processing result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityBatchProcessingResult:
    """Result of processing all proposed bounded actions in a state."""

    state: NinefoldRunState
    processed: tuple[AuthorityProcessingResult, ...]

    def processed_count(self) -> int:
        """Return how many actions were processed."""
        return len(self.processed)

    def authorized_count(self) -> int:
        """Return how many processed actions became executable."""
        return sum(1 for result in self.processed if result.updated_action.allows_execution())

    def human_review_count(self) -> int:
        """Return how many processed actions require human review."""
        return sum(1 for result in self.processed if result.updated_action.requires_human_review())

    def blocked_count(self) -> int:
        """Return how many processed actions block progress."""
        return sum(1 for result in self.processed if result.updated_action.blocks_progress())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible batch result."""
        processed_payload: JsonArray = []
        for result in self.processed:
            processed_payload.append(result.to_payload())

        return {
            "state_digest": self.state.digest().value,
            "processed_count": self.processed_count(),
            "authorized_count": self.authorized_count(),
            "human_review_count": self.human_review_count(),
            "blocked_count": self.blocked_count(),
            "processed": processed_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this batch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityProcessor:
    """Processes proposed bounded actions through jurisdiction and contract gates."""

    recorder: StateRecorder

    def process_action(
        self,
        *,
        state: NinefoldRunState,
        action: BoundedActionRecord,
    ) -> AuthorityProcessingResult:
        """Process one bounded action through the authority gate."""
        existing = state.actions.require_action(action.action_id.value)
        if existing != action:
            raise FoundationError("authority processor action does not match state ledger")

        request = action.to_authority_request()
        decision = decide_authority_request(
            request=request,
            contract=state.runtime_kit.chamber.contract,
            jurisdiction_gate=state.runtime_kit.jurisdiction_gate,
        )
        updated_action = action.with_authority_decision(decision)

        updated_state = self.recorder.record_authority_decision(state, decision)
        updated_state = updated_state.replace_action(updated_action)
        updated_state = self.recorder.record_action(updated_state, updated_action)

        return AuthorityProcessingResult(
            state=updated_state,
            original_action=action,
            authority_decision=decision,
            updated_action=updated_action,
        )

    def process_all_proposed(self, *, state: NinefoldRunState) -> AuthorityBatchProcessingResult:
        """Process all currently proposed bounded actions in ledger order."""
        current = state
        results: list[AuthorityProcessingResult] = []

        for action in state.actions.proposed_actions():
            result = self.process_action(state=current, action=action)
            current = result.state
            results.append(result)

        return AuthorityBatchProcessingResult(
            state=current,
            processed=tuple(results),
        )
