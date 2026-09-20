"""Active choice and causal learning tests for CUC-1."""

from __future__ import annotations

import pytest

from ix_sally.cuc1 import ChoiceUnderConsequenceAgent, Direction
from ix_sally.cuc1.environment import IndependentCausalEnvironment
from ix_sally.foundation import FoundationError


def _agent_and_environment() -> tuple[ChoiceUnderConsequenceAgent, IndependentCausalEnvironment]:
    return ChoiceUnderConsequenceAgent(), IndependentCausalEnvironment(
        environment_id="agent-test", family_id="rotation-test", seed=7
    )


def _run_trial(
    agent: ChoiceUnderConsequenceAgent,
    environment: IndependentCausalEnvironment,
    cue: Direction,
) -> bool:
    observation = environment.reset(cue=cue, context="agent-test")
    choice = agent.choose(observation)
    consequence = environment.intervene(
        observation_id=observation.observation_id,
        action=choice.selected_action,
    )
    agent.learn(observation=observation, choice=choice, consequence=consequence)
    return consequence.succeeded


def test_uniform_prior_has_four_hypotheses() -> None:
    agent, _ = _agent_and_environment()
    hypotheses = agent.hypotheses("rotation-test")
    assert len(hypotheses) == 4
    assert sum(item.probability for item in hypotheses) == pytest.approx(1.0)


def test_choice_scores_every_available_action() -> None:
    agent, environment = _agent_and_environment()
    observation = environment.reset(cue=Direction.NORTH, context="test")
    choice = agent.choose(observation)
    assert {item.action for item in choice.candidates} == set(Direction)
    assert all(item.expected_information_gain > 0.0 for item in choice.candidates)


def test_failed_trial_changes_hypothesis_distribution() -> None:
    agent, environment = _agent_and_environment()
    before = agent.hypotheses("rotation-test")
    _run_trial(agent, environment, Direction.NORTH)
    after = agent.hypotheses("rotation-test")
    assert before != after
    assert sum(item.probability for item in after) == pytest.approx(1.0)


def test_multiple_consequences_create_executable_skill() -> None:
    agent, environment = _agent_and_environment()
    for cue in (Direction.NORTH, Direction.EAST, Direction.SOUTH):
        _run_trial(agent, environment, cue)
    skill = agent.skills["rotation-test"]
    assert skill.apply(Direction.WEST) is Direction.EAST
    assert skill.confidence >= agent.skill_threshold


def test_skill_is_used_on_new_cue() -> None:
    agent, environment = _agent_and_environment()
    for cue in (Direction.NORTH, Direction.EAST, Direction.SOUTH):
        _run_trial(agent, environment, cue)
    observation = environment.reset(cue=Direction.WEST, context="held-out")
    choice = agent.choose(observation)
    assert choice.used_skill_id is not None
    assert choice.selected_action is Direction.EAST


def test_mismatched_consequence_is_rejected() -> None:
    agent, environment = _agent_and_environment()
    observation = environment.reset(cue=Direction.NORTH, context="test")
    choice = agent.choose(observation)
    consequence = environment.intervene(
        observation_id=observation.observation_id,
        action=choice.selected_action,
    )
    other = environment.reset(cue=Direction.EAST, context="other")
    with pytest.raises(FoundationError):
        agent.learn(observation=other, choice=choice, consequence=consequence)
