"""Bayesian active-choice learner for the CUC-1 causal environment."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from ix_sally.cuc1.contracts import (
    CausalHypothesis,
    ChoiceCandidate,
    ChoiceReceipt,
    Consequence,
    Direction,
    LearnedSkill,
    PublicObservation,
)
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _entropy(probabilities: tuple[float, ...]) -> float:
    """Return normalized base-two entropy for a categorical distribution."""
    active = tuple(value for value in probabilities if value > 0.0)
    if len(probabilities) <= 1:
        return 0.0
    raw = -sum(value * math.log2(value) for value in active)
    return raw / math.log2(len(probabilities))


@dataclass(slots=True)
class ChoiceUnderConsequenceAgent:
    """Learn hidden cue transformations through prediction and consequence."""

    information_gain_weight: float = 0.65
    novelty_weight: float = 0.1
    skill_threshold: float = 0.88
    success_likelihood: float = 0.97
    failure_likelihood: float = 0.03
    hypotheses_by_family: dict[str, tuple[CausalHypothesis, ...]] = field(default_factory=dict)
    action_counts: dict[Direction, int] = field(default_factory=dict)
    consequence_digests: dict[str, tuple[DigestRecord, ...]] = field(default_factory=dict)
    skills: dict[str, LearnedSkill] = field(default_factory=dict)
    choice_counter: int = 0

    def __post_init__(self) -> None:
        """Validate learner thresholds and likelihoods."""
        for name, value in {
            "information_gain_weight": self.information_gain_weight,
            "novelty_weight": self.novelty_weight,
            "skill_threshold": self.skill_threshold,
            "success_likelihood": self.success_likelihood,
            "failure_likelihood": self.failure_likelihood,
        }.items():
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"agent {name} must be bounded")
        if self.success_likelihood <= self.failure_likelihood:
            raise FoundationError("success likelihood must exceed failure likelihood")

    def hypotheses(self, family_id: str) -> tuple[CausalHypothesis, ...]:
        """Return or initialize the competing hypotheses for one family."""
        hypotheses = self.hypotheses_by_family.get(family_id)
        if hypotheses is None:
            probability = 1.0 / len(Direction)
            hypotheses = tuple(
                CausalHypothesis(
                    hypothesis_id=f"{family_id}-rotation-{turns}",
                    quarter_turns=turns,
                    probability=probability,
                )
                for turns in range(len(Direction))
            )
            self.hypotheses_by_family[family_id] = hypotheses
        return hypotheses

    def choose(self, observation: PublicObservation) -> ChoiceReceipt:
        """Choose an action using expected success, information, and novelty."""
        hypotheses = self.hypotheses(observation.family_id)
        probabilities = tuple(item.probability for item in hypotheses)
        prior_entropy = _entropy(probabilities)
        skill = self.skills.get(observation.family_id)
        candidates = tuple(
            self._score_candidate(
                observation=observation,
                action=action,
                hypotheses=hypotheses,
                prior_entropy=prior_entropy,
            )
            for action in observation.available_actions
        )
        if skill is not None and skill.confidence >= self.skill_threshold:
            selected = skill.apply(observation.cue)
            used_skill_id = skill.skill_id
        else:
            selected = max(
                candidates,
                key=lambda candidate: (candidate.score, -int(candidate.action)),
            ).action
            used_skill_id = None
        self.choice_counter += 1
        return ChoiceReceipt(
            choice_id=f"choice-{self.choice_counter}",
            observation_digest=observation.evidence_digest,
            candidates=candidates,
            selected_action=selected,
            prior_entropy=round(prior_entropy, 12),
            used_skill_id=used_skill_id,
        )

    def learn(
        self,
        *,
        observation: PublicObservation,
        choice: ChoiceReceipt,
        consequence: Consequence,
    ) -> None:
        """Update causal beliefs from evaluator-owned consequence evidence."""
        if choice.observation_digest != observation.evidence_digest:
            raise FoundationError("choice does not reference the supplied observation")
        if consequence.observation_digest != observation.evidence_digest:
            raise FoundationError("consequence does not reference the supplied observation")
        if consequence.selected_action is not choice.selected_action:
            raise FoundationError("consequence action differs from selected action")
        hypotheses = self.hypotheses(observation.family_id)
        unnormalized = []
        for hypothesis in hypotheses:
            predicted_success = hypothesis.predicts(observation.cue) is choice.selected_action
            consistent = predicted_success is consequence.succeeded
            likelihood = self.success_likelihood if consistent else self.failure_likelihood
            unnormalized.append(hypothesis.probability * likelihood)
        total = sum(unnormalized)
        if total <= 0.0:
            raise FoundationError("hypothesis update produced zero probability mass")
        updated = tuple(
            replace(hypothesis, probability=round(weight / total, 12))
            for hypothesis, weight in zip(hypotheses, unnormalized, strict=True)
        )
        normalization = sum(item.probability for item in updated)
        if normalization != 1.0:
            correction = 1.0 - normalization
            best_index = max(range(len(updated)), key=lambda index: updated[index].probability)
            updated_list = list(updated)
            updated_list[best_index] = replace(
                updated_list[best_index],
                probability=round(updated_list[best_index].probability + correction, 12),
            )
            updated = tuple(updated_list)
        self.hypotheses_by_family[observation.family_id] = updated
        previous_count = self.action_counts.get(choice.selected_action, 0)
        self.action_counts[choice.selected_action] = previous_count + 1
        current_evidence = self.consequence_digests.get(observation.family_id, ())
        self.consequence_digests[observation.family_id] = (
            *current_evidence,
            consequence.evaluator_digest,
        )
        self._promote_skill(observation.family_id)
        self._validate_used_skill(
            family_id=observation.family_id,
            choice=choice,
            consequence=consequence,
        )

    def _score_candidate(
        self,
        *,
        observation: PublicObservation,
        action: Direction,
        hypotheses: tuple[CausalHypothesis, ...],
        prior_entropy: float,
    ) -> ChoiceCandidate:
        """Build a transparent multi-objective candidate score."""
        expected_success = sum(
            hypothesis.probability
            for hypothesis in hypotheses
            if hypothesis.predicts(observation.cue) is action
        )
        information_gain = self._expected_information_gain(
            cue=observation.cue,
            action=action,
            hypotheses=hypotheses,
            prior_entropy=prior_entropy,
        )
        count = self.action_counts.get(action, 0)
        novelty = 1.0 / (1.0 + count)
        reversibility = 1.0
        cost = 0.05
        risk = 0.0
        score = (
            expected_success
            + self.information_gain_weight * information_gain
            + self.novelty_weight * novelty
            + 0.05 * reversibility
            - 0.05 * cost
            - risk
        )
        return ChoiceCandidate(
            action=action,
            expected_success=round(expected_success, 12),
            expected_information_gain=round(information_gain, 12),
            novelty=round(novelty, 12),
            reversibility=reversibility,
            cost=cost,
            risk=risk,
            score=round(score, 12),
        )

    def _expected_information_gain(
        self,
        *,
        cue: Direction,
        action: Direction,
        hypotheses: tuple[CausalHypothesis, ...],
        prior_entropy: float,
    ) -> float:
        """Calculate expected entropy reduction for success and failure outcomes."""
        success_probability = sum(
            hypothesis.probability
            for hypothesis in hypotheses
            if hypothesis.predicts(cue) is action
        )
        expected_entropy = 0.0
        for observed_success, outcome_probability in (
            (True, success_probability),
            (False, 1.0 - success_probability),
        ):
            if outcome_probability <= 0.0:
                continue
            weights = []
            for hypothesis in hypotheses:
                predicted_success = hypothesis.predicts(cue) is action
                consistent = predicted_success is observed_success
                likelihood = self.success_likelihood if consistent else self.failure_likelihood
                weights.append(hypothesis.probability * likelihood)
            total = sum(weights)
            posterior = tuple(weight / total for weight in weights)
            expected_entropy += outcome_probability * _entropy(posterior)
        return max(0.0, prior_entropy - expected_entropy)

    def _promote_skill(self, family_id: str) -> None:
        """Compile a sufficiently supported causal hypothesis into executable skill."""
        hypotheses = self.hypotheses(family_id)
        best = max(hypotheses, key=lambda item: item.probability)
        evidence = self.consequence_digests.get(family_id, ())
        if best.probability < self.skill_threshold or len(evidence) < 2:
            return
        existing = self.skills.get(family_id)
        self.skills[family_id] = LearnedSkill(
            skill_id=f"skill-{family_id}-rotation-{best.quarter_turns}",
            family_id=family_id,
            quarter_turns=best.quarter_turns,
            confidence=best.probability,
            source_consequence_digests=evidence,
            validation_uses=existing.validation_uses if existing else 0,
            validation_successes=existing.validation_successes if existing else 0,
        )

    def _validate_used_skill(
        self,
        *,
        family_id: str,
        choice: ChoiceReceipt,
        consequence: Consequence,
    ) -> None:
        """Update validation counters only when an existing skill selected the action."""
        skill = self.skills.get(family_id)
        if skill is None or choice.used_skill_id != skill.skill_id:
            return
        self.skills[family_id] = replace(
            skill,
            validation_uses=skill.validation_uses + 1,
            validation_successes=skill.validation_successes + int(consequence.succeeded),
        )

    def state_digest(self) -> DigestRecord:
        """Return a content digest for causal beliefs and executable skills."""
        return DigestRecord.from_payload(
            {
                "hypotheses": {
                    family: [item.to_payload() for item in hypotheses]
                    for family, hypotheses in sorted(self.hypotheses_by_family.items())
                },
                "skills": {
                    family: skill.to_payload() for family, skill in sorted(self.skills.items())
                },
                "choice_counter": self.choice_counter,
            }
        )
