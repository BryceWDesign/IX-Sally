"""Blind evaluation interface suitable for challenge sets supplied by independent evaluators.

This module cannot make IX-Sally's own authors independent. It provides the machinery
needed for a third party to commit hidden challenges, run an agent against public inputs,
and reveal/score the targets afterward without changing the commitment.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class BlindChallenge:
    challenge_id: str
    public_input: tuple[int, ...]
    hidden_target: int
    evaluator_nonce: str

    def __post_init__(self) -> None:
        require_text(self.challenge_id, field_name="challenge_id")
        require_text(self.evaluator_nonce, field_name="evaluator_nonce")

    def commitment(self) -> DigestRecord:
        return DigestRecord.from_payload(
            {
                "challenge_id": self.challenge_id,
                "public_input": list(self.public_input),
                "hidden_target": self.hidden_target,
                "evaluator_nonce": self.evaluator_nonce,
            }
        )

    def public_payload(self) -> JsonObject:
        return {
            "challenge_id": self.challenge_id,
            "public_input": list(self.public_input),
            "commitment": {
                "algorithm": self.commitment().algorithm,
                "value": self.commitment().value,
            },
        }


@dataclass(frozen=True, slots=True)
class BlindEvaluationResult:
    total: int
    correct: int
    accuracy: float
    commitments_verified: bool
    predictions: tuple[tuple[str, int, int], ...]

    def to_payload(self) -> JsonObject:
        predictions: JsonArray = [
            {"challenge_id": item[0], "prediction": item[1], "target": item[2]}
            for item in self.predictions
        ]
        return {
            "total": self.total,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "commitments_verified": self.commitments_verified,
            "predictions": predictions,
        }


class BlindEvaluatorHarness:
    """Evaluate without exposing hidden targets to the agent callable."""

    def evaluate(
        self,
        *,
        challenges: Iterable[BlindChallenge],
        agent: Callable[[tuple[int, ...]], int],
        commitments: Iterable[DigestRecord] | None = None,
    ) -> BlindEvaluationResult:
        challenge_tuple = tuple(challenges)
        if not challenge_tuple:
            raise FoundationError("blind evaluation requires challenges")
        expected = tuple(item.commitment() for item in challenge_tuple)
        supplied = tuple(commitments) if commitments is not None else expected
        verified = supplied == expected
        if not verified:
            raise FoundationError("blind challenge commitment verification failed")
        predictions: list[tuple[str, int, int]] = []
        correct = 0
        for challenge in challenge_tuple:
            prediction = agent(challenge.public_input)
            predictions.append((challenge.challenge_id, prediction, challenge.hidden_target))
            correct += int(prediction == challenge.hidden_target)
        return BlindEvaluationResult(
            total=len(challenge_tuple),
            correct=correct,
            accuracy=correct / len(challenge_tuple),
            commitments_verified=True,
            predictions=tuple(predictions),
        )
