"""Active perception, causal discovery, and counterfactual imagination.

The mechanisms here are bounded and explicit. They let Sally choose observations for
information value, distinguish intervention evidence from observational correlation, flag
possible confounding/regime change, and simulate branching futures before acting.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import log2

from ix_sally.digest import JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class PerceptionProbe:
    """One binary measurement with likelihoods under each candidate hypothesis."""

    probe_id: str
    positive_likelihoods: tuple[float, ...]
    cost: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.probe_id, field_name="probe_id")
        if not self.positive_likelihoods:
            raise FoundationError("perception probe requires hypothesis likelihoods")
        if any(not 0.0 <= value <= 1.0 for value in self.positive_likelihoods):
            raise FoundationError("probe likelihoods must be between zero and one")
        if self.cost < 0.0:
            raise FoundationError("probe cost must not be negative")


@dataclass(frozen=True, slots=True)
class ProbeChoice:
    """Information-value receipt for one actively selected observation."""

    probe_id: str
    expected_information_gain: float
    expected_posterior_entropy: float
    prior_entropy: float


class ActivePerceptionPlanner:
    """Choose the next observation expected to reduce uncertainty most per unit cost."""

    def choose(
        self,
        *,
        priors: Iterable[float],
        probes: Iterable[PerceptionProbe],
    ) -> ProbeChoice:
        prior = tuple(priors)
        candidates = tuple(probes)
        self._validate_prior(prior)
        if not candidates:
            raise FoundationError("active perception requires candidate probes")
        if any(len(probe.positive_likelihoods) != len(prior) for probe in candidates):
            raise FoundationError("probe likelihood arity must match hypothesis count")
        prior_entropy = self._entropy(prior)
        ranked: list[tuple[float, str, ProbeChoice]] = []
        for probe in candidates:
            p_positive = sum(
                p_h * p_pos for p_h, p_pos in zip(prior, probe.positive_likelihoods, strict=True)
            )
            expected_entropy = 0.0
            for positive, p_outcome in ((True, p_positive), (False, 1.0 - p_positive)):
                if p_outcome <= 0.0:
                    continue
                posterior = self.posterior(prior, probe, positive=positive)
                expected_entropy += p_outcome * self._entropy(posterior)
            information_gain = max(0.0, prior_entropy - expected_entropy)
            adjusted = information_gain / (1.0 + probe.cost)
            choice = ProbeChoice(
                probe_id=probe.probe_id,
                expected_information_gain=round(information_gain, 12),
                expected_posterior_entropy=round(expected_entropy, 12),
                prior_entropy=round(prior_entropy, 12),
            )
            ranked.append((adjusted, probe.probe_id, choice))
        return max(ranked, key=lambda item: (item[0], tuple(-ord(ch) for ch in item[1])))[2]

    def posterior(
        self,
        priors: tuple[float, ...],
        probe: PerceptionProbe,
        *,
        positive: bool,
    ) -> tuple[float, ...]:
        likelihoods = tuple(
            value if positive else 1.0 - value for value in probe.positive_likelihoods
        )
        unnormalized = tuple(
            prior * likelihood for prior, likelihood in zip(priors, likelihoods, strict=True)
        )
        total = sum(unnormalized)
        if total == 0.0:
            return tuple(1.0 / len(priors) for _ in priors)
        return tuple(value / total for value in unnormalized)

    @staticmethod
    def _validate_prior(prior: tuple[float, ...]) -> None:
        if not prior or any(value < 0.0 for value in prior):
            raise FoundationError("hypothesis priors must be non-negative and non-empty")
        if abs(sum(prior) - 1.0) > 1e-9:
            raise FoundationError("hypothesis priors must sum to one")

    @staticmethod
    def _entropy(probabilities: tuple[float, ...]) -> float:
        return -sum(value * log2(value) for value in probabilities if value > 0.0)


@dataclass(frozen=True, slots=True)
class CausalObservation:
    """One observational or interventional sample for a candidate cause."""

    sample_id: str
    treatment: bool
    outcome: bool
    intervened: bool
    regime: str = "default"

    def __post_init__(self) -> None:
        require_text(self.sample_id, field_name="sample_id")
        require_text(self.regime, field_name="regime")


@dataclass(frozen=True, slots=True)
class CausalDiscoveryReport:
    """Evidence separating observation from intervention and flagging instability."""

    observational_effect: float
    interventional_effect: float
    confounding_gap: float
    causal_supported: bool
    confounding_suspected: bool
    regime_change_suspected: bool
    regime_effects: tuple[tuple[str, float], ...]

    def to_payload(self) -> JsonObject:
        effects: JsonArray = [
            {"regime": regime, "interventional_effect": effect}
            for regime, effect in self.regime_effects
        ]
        return {
            "observational_effect": self.observational_effect,
            "interventional_effect": self.interventional_effect,
            "confounding_gap": self.confounding_gap,
            "causal_supported": self.causal_supported,
            "confounding_suspected": self.confounding_suspected,
            "regime_change_suspected": self.regime_change_suspected,
            "regime_effects": effects,
        }


class CausalDiscoveryEngine:
    """Estimate intervention effects and detect confounding/regime shifts."""

    def discover(
        self,
        observations: Iterable[CausalObservation],
        *,
        effect_threshold: float = 0.20,
        confounding_threshold: float = 0.20,
        regime_threshold: float = 0.35,
    ) -> CausalDiscoveryReport:
        samples = tuple(observations)
        if not samples:
            raise FoundationError("causal discovery requires observations")
        observational = tuple(item for item in samples if not item.intervened)
        interventional = tuple(item for item in samples if item.intervened)
        if not observational or not interventional:
            raise FoundationError("causal discovery requires observational and intervention data")
        observational_effect = self._effect(observational)
        interventional_effect = self._effect(interventional)
        gap = abs(observational_effect - interventional_effect)
        regimes = sorted({item.regime for item in interventional})
        regime_effects = tuple(
            (regime, self._effect(tuple(item for item in interventional if item.regime == regime)))
            for regime in regimes
        )
        effect_values = [effect for _, effect in regime_effects]
        regime_change = (
            bool(effect_values) and max(effect_values) - min(effect_values) >= regime_threshold
        )
        return CausalDiscoveryReport(
            observational_effect=round(observational_effect, 12),
            interventional_effect=round(interventional_effect, 12),
            confounding_gap=round(gap, 12),
            causal_supported=abs(interventional_effect) >= effect_threshold,
            confounding_suspected=gap >= confounding_threshold,
            regime_change_suspected=regime_change,
            regime_effects=tuple((name, round(effect, 12)) for name, effect in regime_effects),
        )

    @staticmethod
    def _effect(samples: tuple[CausalObservation, ...]) -> float:
        treated = [float(item.outcome) for item in samples if item.treatment]
        untreated = [float(item.outcome) for item in samples if not item.treatment]
        if not treated or not untreated:
            return 0.0
        return sum(treated) / len(treated) - sum(untreated) / len(untreated)


@dataclass(frozen=True, slots=True)
class CounterfactualAction:
    """One model transition usable only inside imagination."""

    action_id: str
    transition: Callable[[int], int]
    utility: Callable[[int], float]
    risk: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.action_id, field_name="action_id")
        if not 0.0 <= self.risk <= 1.0:
            raise FoundationError("counterfactual action risk must be between zero and one")


@dataclass(frozen=True, slots=True)
class ImaginedBranch:
    """One simulated future path."""

    action_ids: tuple[str, ...]
    states: tuple[int, ...]
    utility: float
    aggregate_risk: float


class CounterfactualSimulator:
    """Simulate branching futures and rank them without changing the real world."""

    def imagine(
        self,
        *,
        initial_state: int,
        actions: Iterable[CounterfactualAction],
        depth: int = 3,
        max_branches: int = 256,
    ) -> tuple[ImaginedBranch, ...]:
        action_tuple = tuple(actions)
        if not action_tuple or depth < 1 or max_branches < 1:
            raise FoundationError("counterfactual simulation requires actions and positive bounds")
        frontier: list[ImaginedBranch] = [
            ImaginedBranch(action_ids=(), states=(initial_state,), utility=0.0, aggregate_risk=0.0)
        ]
        completed: list[ImaginedBranch] = []
        for _ in range(depth):
            next_frontier: list[ImaginedBranch] = []
            for branch in frontier:
                current = branch.states[-1]
                for action in action_tuple:
                    next_state = action.transition(current)
                    survival = (1.0 - branch.aggregate_risk) * (1.0 - action.risk)
                    candidate = ImaginedBranch(
                        action_ids=(*branch.action_ids, action.action_id),
                        states=(*branch.states, next_state),
                        utility=round(branch.utility + action.utility(next_state), 12),
                        aggregate_risk=round(1.0 - survival, 12),
                    )
                    next_frontier.append(candidate)
            next_frontier.sort(
                key=lambda item: (-item.utility, item.aggregate_risk, item.action_ids)
            )
            frontier = next_frontier[:max_branches]
            completed.extend(frontier)
        completed.sort(key=lambda item: (-item.utility, item.aggregate_risk, item.action_ids))
        return tuple(completed[:max_branches])
