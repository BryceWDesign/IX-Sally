"""Authority processing flow for IX-Sally bounded actions."""

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
            "authority_status": self.authority_decision.status.value,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this authority processing result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityBatchProcessingResult:
    """Result of processing all proposed bounded actions in ledger order."""

    state: NinefoldRunState
    processed: tuple[AuthorityProcessingResult, ...]

    def processed_count(self) -> int:
        """Return the number of processed actions."""
        return len(self.processed)

    def authorized_count(self) -> int:
        """Return how many processed actions were authorized."""
        return sum(1 for result in self.processed if result.authority_decision.allows_action())

    def human_review_count(self) -> int:
        """Return how many processed actions require human review."""
        return sum(
            1 for result in self.processed if result.authority_decision.requires_human_review()
        )

    def blocked_count(self) -> int:
        """Return how many processed actions block autonomous continuation."""
        return sum(1 for result in self.processed if result.updated_action.blocks_progress())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible authority batch result."""
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
        """Return a deterministic digest for this authority batch result."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AuthorityProcessor:
    """Processes bounded actions through contract and jurisdiction authority gates."""

    recorder: StateRecorder

    def process_action(
        self,
        *,
        state: NinefoldRunState,
        action: BoundedActionRecord,
    ) -> AuthorityProcessingResult:
        """Process one proposed action and update the run state."""
        try:
            existing = state.actions.require_action(action.action_id.value)
        except FoundationError as error:
            raise FoundationError("action does not match state ledger") from error

        if existing != action:
            raise FoundationError("action does not match state ledger")

        request = action.to_authority_request()
        decision = decide_authority_request(
            request=request,
            contract=state.runtime_kit.chamber.contract,
            jurisdiction_gate=state.runtime_kit.jurisdiction_gate,
        )
        updated_action = action.with_authority_decision(decision)

        updated_state = self.recorder.record_authority_decision(state, decision)
        updated_state = updated_state.replace_action(updated_action)
        updated_state = self.recorder.record_action_update(updated_state, updated_action)

        return AuthorityProcessingResult(
            state=updated_state,
            original_action=action,
            authority_decision=decision,
            updated_action=updated_action,
        )

    def process_all_proposed(self, *, state: NinefoldRunState) -> AuthorityBatchProcessingResult:
        """Process all currently proposed actions in ledger order."""
        current = state
        processed: list[AuthorityProcessingResult] = []

        for action in state.actions.proposed_actions():
            result = self.process_action(state=current, action=action)
            current = result.state
            processed.append(result)

        return AuthorityBatchProcessingResult(
            state=current,
            processed=tuple(processed),
        )
