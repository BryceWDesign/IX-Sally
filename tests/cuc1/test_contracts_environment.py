"""Contract and evaluator-boundary tests for CUC-1."""

from __future__ import annotations

import pytest

from ix_sally.cuc1 import Direction, IndependentCausalEnvironment
from ix_sally.foundation import FoundationError


def _environment() -> IndependentCausalEnvironment:
    return IndependentCausalEnvironment(
        environment_id="test-environment", family_id="rotation-test", seed=7
    )


def test_observation_contains_no_answer_or_rule() -> None:
    payload = _environment().reset(cue=Direction.NORTH, context="test").to_payload()
    forbidden = {
        "answer",
        "correct_action",
        "expected_action",
        "expected_operation",
        "quarter_turns",
        "reward",
        "rule",
        "target",
    }
    assert forbidden.isdisjoint(payload)


def test_environment_computes_consequence() -> None:
    environment = _environment()
    observation = environment.reset(cue=Direction.NORTH, context="test")
    consequence = environment.intervene(
        observation_id=observation.observation_id, action=Direction.SOUTH
    )
    assert consequence.succeeded
    assert consequence.reward == 1.0


def test_incorrect_intervention_fails() -> None:
    environment = _environment()
    observation = environment.reset(cue=Direction.NORTH, context="test")
    consequence = environment.intervene(
        observation_id=observation.observation_id, action=Direction.NORTH
    )
    assert not consequence.succeeded


def test_observation_cannot_be_consumed_twice() -> None:
    environment = _environment()
    observation = environment.reset(cue=Direction.NORTH, context="test")
    environment.intervene(observation_id=observation.observation_id, action=Direction.NORTH)
    with pytest.raises(FoundationError):
        environment.intervene(observation_id=observation.observation_id, action=Direction.SOUTH)


def test_rule_reveal_fails_with_active_observation() -> None:
    environment = _environment()
    environment.reset(cue=Direction.NORTH, context="test")
    with pytest.raises(FoundationError):
        environment.reveal_for_completed_evaluation()


def test_commitment_matches_post_run_reveal() -> None:
    environment = _environment()
    commitment = environment.rule_commitment()
    reveal = environment.reveal_for_completed_evaluation()
    assert reveal["rule_commitment"]["value"] == commitment.value
