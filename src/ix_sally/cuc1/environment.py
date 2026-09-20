"""Evaluator-owned hidden causal worlds for CUC-1."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ix_sally.cuc1.contracts import (
    Consequence,
    Direction,
    OutcomeStatus,
    PublicObservation,
    digest_payload,
)
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(slots=True)
class IndependentCausalEnvironment:
    """A sealed evaluator whose transition rule is absent from observations."""

    environment_id: str
    family_id: str
    seed: int
    _quarter_turns: int | None = field(default=None, repr=False)
    _episode_counter: int = field(default=0, init=False, repr=False)
    _active_observations: dict[str, PublicObservation] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Create a deterministic evaluator-private causal rule."""
        require_text(self.environment_id, field_name="environment_id")
        require_text(self.family_id, field_name="family_id")
        if self._quarter_turns is None:
            self._quarter_turns = random.Random(self.seed).randrange(len(Direction))
        if self._quarter_turns not in range(len(Direction)):
            raise FoundationError("environment rule must be in range 0..3")

    def reset(self, *, cue: Direction, context: str) -> PublicObservation:
        """Start one episode and expose only public state."""
        normalized_context = require_text(context, field_name="context")
        self._episode_counter += 1
        observation_id = f"{self.environment_id}-observation-{self._episode_counter}"
        evidence = DigestRecord.from_payload(
            {
                "environment_id": self.environment_id,
                "observation_id": observation_id,
                "family_id": self.family_id,
                "cue": cue.name.lower(),
                "context": normalized_context,
            }
        )
        observation = PublicObservation(
            observation_id=observation_id,
            family_id=self.family_id,
            cue=cue,
            context=normalized_context,
            available_actions=tuple(Direction),
            evidence_digest=evidence,
        )
        self._active_observations[observation_id] = observation
        return observation

    def intervene(
        self,
        *,
        observation_id: str,
        action: Direction,
    ) -> Consequence:
        """Apply one action and independently compute its consequence."""
        observation = self._active_observations.pop(observation_id, None)
        if observation is None:
            raise FoundationError("unknown or already consumed observation")
        if action not in observation.available_actions:
            raise FoundationError("action is outside the observation action surface")
        assert self._quarter_turns is not None
        correct_action = observation.cue.rotated(self._quarter_turns)
        succeeded = action is correct_action
        evaluator_payload: JsonObject = {
            "environment_id": self.environment_id,
            "family_id": self.family_id,
            "observation_digest": digest_payload(observation.evidence_digest),
            "selected_action": action.name.lower(),
            "status": "success" if succeeded else "failure",
            "rule_commitment": digest_payload(self.rule_commitment()),
        }
        return Consequence(
            consequence_id=f"{observation_id}-consequence",
            observation_digest=observation.evidence_digest,
            selected_action=action,
            status=OutcomeStatus.SUCCESS if succeeded else OutcomeStatus.FAILURE,
            reward=1.0 if succeeded else -0.25,
            terminal=True,
            evaluator_digest=DigestRecord.from_payload(evaluator_payload),
        )

    def rule_commitment(self) -> DigestRecord:
        """Commit to the hidden rule without exposing it to the agent."""
        return DigestRecord.from_payload(
            {
                "environment_id": self.environment_id,
                "family_id": self.family_id,
                "seed": self.seed,
                "quarter_turns": self._quarter_turns,
            }
        )

    def reveal_for_completed_evaluation(self) -> JsonObject:
        """Reveal evaluator configuration only for post-run reproducibility."""
        if self._active_observations:
            raise FoundationError("cannot reveal rule while observations remain active")
        return {
            "environment_id": self.environment_id,
            "family_id": self.family_id,
            "seed": self.seed,
            "quarter_turns": self._quarter_turns,
            "rule_commitment": digest_payload(self.rule_commitment()),
        }
