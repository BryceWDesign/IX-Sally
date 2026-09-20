"""End-to-end Choice Under Consequence experiment and evidence report."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ix_sally.cuc1.agent import ChoiceUnderConsequenceAgent
from ix_sally.cuc1.contracts import (
    ChoiceReceipt,
    Consequence,
    Direction,
    LearnedSkill,
    PublicObservation,
    digest_payload,
)
from ix_sally.cuc1.environment import IndependentCausalEnvironment
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError


@dataclass(frozen=True, slots=True)
class TrialRecord:
    """One complete observation-choice-consequence learning event."""

    observation: PublicObservation
    choice: ChoiceReceipt
    consequence: Consequence
    state_before: DigestRecord
    state_after: DigestRecord

    def __post_init__(self) -> None:
        """Require state change evidence for a learning trial."""
        self.state_before.require_algorithm("sha256")
        self.state_after.require_algorithm("sha256")

    @property
    def changed_agent(self) -> bool:
        """Return whether the consequence changed cognitive state."""
        return self.state_before != self.state_after

    def to_payload(self) -> JsonObject:
        """Return a canonical trial payload."""
        return {
            "observation": self.observation.to_payload(),
            "choice": self.choice.to_payload(),
            "consequence": self.consequence.to_payload(),
            "state_before": digest_payload(self.state_before),
            "state_after": digest_payload(self.state_after),
            "changed_agent": self.changed_agent,
        }


@dataclass(frozen=True, slots=True)
class CounterfactualBehaviorProof:
    """Proof that measured experience changed a later held-out choice."""

    observation_digest: DigestRecord
    pre_learning_action: Direction
    post_learning_action: Direction
    post_learning_used_skill_id: str | None
    post_learning_succeeded: bool
    behavior_changed: bool

    def __post_init__(self) -> None:
        """Validate content-addressed observation evidence."""
        self.observation_digest.require_algorithm("sha256")
        if self.behavior_changed is not (self.pre_learning_action is not self.post_learning_action):
            raise FoundationError("counterfactual behavior flag is inconsistent")

    def to_payload(self) -> JsonObject:
        """Return a canonical counterfactual proof."""
        return {
            "observation_digest": digest_payload(self.observation_digest),
            "pre_learning_action": self.pre_learning_action.name.lower(),
            "post_learning_action": self.post_learning_action.name.lower(),
            "post_learning_used_skill_id": self.post_learning_used_skill_id,
            "post_learning_succeeded": self.post_learning_succeeded,
            "behavior_changed": self.behavior_changed,
        }


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Frozen baseline outcome on the same causal family."""

    baseline_id: str
    successes: int
    trials: int

    @property
    def success_rate(self) -> float:
        """Return measured baseline accuracy."""
        return round(self.successes / self.trials, 12) if self.trials else 0.0

    def to_payload(self) -> JsonObject:
        """Return a canonical baseline payload."""
        return {
            "baseline_id": self.baseline_id,
            "successes": self.successes,
            "trials": self.trials,
            "success_rate": self.success_rate,
        }


@dataclass(frozen=True, slots=True)
class CUC1Report:
    """Falsifiable report for acquired and transferred causal competence."""

    experiment_id: str
    environment_commitment: DigestRecord
    training_trials: tuple[TrialRecord, ...]
    held_out_trial: TrialRecord
    learned_skill: LearnedSkill | None
    counterfactual_proof: CounterfactualBehaviorProof
    baselines: tuple[BaselineResult, ...]
    evaluator_reveal: JsonObject
    leakage_checks_passed: bool

    def __post_init__(self) -> None:
        """Validate report evidence and non-empty trial inventory."""
        self.environment_commitment.require_algorithm("sha256")
        if not self.training_trials:
            raise FoundationError("CUC-1 report requires training trials")

    @property
    def training_success_rate(self) -> float:
        """Return observed training success rate."""
        successes = sum(trial.consequence.succeeded for trial in self.training_trials)
        return round(successes / len(self.training_trials), 12)

    @property
    def transfer_succeeded(self) -> bool:
        """Return whether executable learning transferred to the held-out cue."""
        return (
            self.held_out_trial.consequence.succeeded
            and self.held_out_trial.choice.used_skill_id is not None
        )

    @property
    def acquired_competence(self) -> bool:
        """Return whether CUC-1's strict learning claim is supported."""
        return (
            self.leakage_checks_passed
            and self.learned_skill is not None
            and all(trial.changed_agent for trial in self.training_trials)
            and self.counterfactual_proof.behavior_changed
            and self.counterfactual_proof.post_learning_succeeded
            and self.transfer_succeeded
        )

    @property
    def classification(self) -> str:
        """Return the bounded experiment classification."""
        return (
            "causal-skill-acquisition-observed"
            if self.acquired_competence
            else "causal-skill-acquisition-not-established"
        )

    def to_payload(self) -> JsonObject:
        """Return a complete machine-readable evidence report."""
        training: JsonArray = [trial.to_payload() for trial in self.training_trials]
        baselines: JsonArray = [baseline.to_payload() for baseline in self.baselines]
        return {
            "experiment_id": self.experiment_id,
            "classification": self.classification,
            "acquired_competence": self.acquired_competence,
            "agi_certified": False,
            "environment_commitment": digest_payload(self.environment_commitment),
            "training_trials": training,
            "training_success_rate": self.training_success_rate,
            "held_out_trial": self.held_out_trial.to_payload(),
            "transfer_succeeded": self.transfer_succeeded,
            "learned_skill": self.learned_skill.to_payload() if self.learned_skill else None,
            "counterfactual_proof": self.counterfactual_proof.to_payload(),
            "baselines": baselines,
            "evaluator_reveal": self.evaluator_reveal,
            "leakage_checks_passed": self.leakage_checks_passed,
            "limitations": [
                "CUC-1 is a bounded causal-learning experiment, not an AGI test.",
                "The environment uses a four-hypothesis rotation family.",
                "Transfer is within one causal family across held-out observations.",
                "Independent external replication has not been performed.",
            ],
        }

    def digest(self) -> DigestRecord:
        """Return a content address for the complete experiment."""
        return DigestRecord.from_payload(self.to_payload())


def _run_learning_trial(
    *,
    agent: ChoiceUnderConsequenceAgent,
    environment: IndependentCausalEnvironment,
    cue: Direction,
    context: str,
) -> TrialRecord:
    """Run one complete closed-loop learning event."""
    observation = environment.reset(cue=cue, context=context)
    state_before = agent.state_digest()
    choice = agent.choose(observation)
    consequence = environment.intervene(
        observation_id=observation.observation_id,
        action=choice.selected_action,
    )
    agent.learn(observation=observation, choice=choice, consequence=consequence)
    state_after = agent.state_digest()
    return TrialRecord(
        observation=observation,
        choice=choice,
        consequence=consequence,
        state_before=state_before,
        state_after=state_after,
    )


def _run_baselines(*, seed: int, quarter_turns: int) -> tuple[BaselineResult, ...]:
    """Evaluate frozen random and fixed-action baselines on all directions."""
    cues = tuple(Direction)
    random_source = random.Random(seed + 10_000)
    random_successes = sum(
        random_source.choice(tuple(Direction)) is cue.rotated(quarter_turns) for cue in cues
    )
    fixed_successes = sum(Direction.NORTH is cue.rotated(quarter_turns) for cue in cues)
    return (
        BaselineResult("uniform-random", random_successes, len(cues)),
        BaselineResult("fixed-north", fixed_successes, len(cues)),
    )


def _public_payload_is_sealed(observation: PublicObservation) -> bool:
    """Reject answer-bearing fields from the complete agent-visible payload."""
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
    return forbidden.isdisjoint(observation.to_payload())


def run_cuc1_experiment(*, seed: int = 7) -> CUC1Report:
    """Run the deterministic first Choice Under Consequence experiment."""
    experiment_id = f"cuc1-seed-{seed}"
    family_id = "rotation-causality-v1"
    environment = IndependentCausalEnvironment(
        environment_id=f"{experiment_id}-environment",
        family_id=family_id,
        seed=seed,
    )
    agent = ChoiceUnderConsequenceAgent()
    pre_learning_agent = ChoiceUnderConsequenceAgent()

    training_trials = tuple(
        _run_learning_trial(
            agent=agent,
            environment=environment,
            cue=cue,
            context=f"training-context-{index}",
        )
        for index, cue in enumerate(
            (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.NORTH),
            start=1,
        )
    )

    held_out_observation = environment.reset(
        cue=Direction.WEST,
        context="held-out-transfer-context",
    )
    pre_learning_choice = pre_learning_agent.choose(held_out_observation)
    held_out_before = agent.state_digest()
    held_out_choice = agent.choose(held_out_observation)
    held_out_consequence = environment.intervene(
        observation_id=held_out_observation.observation_id,
        action=held_out_choice.selected_action,
    )
    agent.learn(
        observation=held_out_observation,
        choice=held_out_choice,
        consequence=held_out_consequence,
    )
    held_out_trial = TrialRecord(
        observation=held_out_observation,
        choice=held_out_choice,
        consequence=held_out_consequence,
        state_before=held_out_before,
        state_after=agent.state_digest(),
    )
    skill = agent.skills.get(family_id)
    reveal = environment.reveal_for_completed_evaluation()
    quarter_turns = reveal["quarter_turns"]
    if not isinstance(quarter_turns, int):
        raise FoundationError("evaluator reveal has an invalid rule")
    proof = CounterfactualBehaviorProof(
        observation_digest=held_out_observation.evidence_digest,
        pre_learning_action=pre_learning_choice.selected_action,
        post_learning_action=held_out_choice.selected_action,
        post_learning_used_skill_id=held_out_choice.used_skill_id,
        post_learning_succeeded=held_out_consequence.succeeded,
        behavior_changed=(
            pre_learning_choice.selected_action is not held_out_choice.selected_action
        ),
    )
    leakage_checks_passed = all(
        _public_payload_is_sealed(trial.observation) for trial in training_trials
    ) and _public_payload_is_sealed(held_out_observation)
    return CUC1Report(
        experiment_id=experiment_id,
        environment_commitment=environment.rule_commitment(),
        training_trials=training_trials,
        held_out_trial=held_out_trial,
        learned_skill=skill,
        counterfactual_proof=proof,
        baselines=_run_baselines(seed=seed, quarter_turns=quarter_turns),
        evaluator_reveal=reveal,
        leakage_checks_passed=leakage_checks_passed,
    )
