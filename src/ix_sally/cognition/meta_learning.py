"""Adaptive search, self-diagnosis, meta-learning, and governed self-improvement."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.cognition.metacognition import ImprovementProposal, SelfModel
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class SearchOperatorTrial:
    """Observed value of one candidate-generation operator."""

    operator_id: str
    success: bool
    information_gain: float
    cost: float

    def __post_init__(self) -> None:
        require_text(self.operator_id, field_name="operator_id")
        if not 0.0 <= self.information_gain <= 1.0:
            raise FoundationError("operator information_gain must be between zero and one")
        if self.cost < 0.0:
            raise FoundationError("operator cost must not be negative")


@dataclass(frozen=True, slots=True)
class SearchBudgetAllocation:
    """Learned distribution of finite search effort."""

    allocations: tuple[tuple[str, int], ...]

    def budget_for(self, operator_id: str) -> int:
        for name, budget in self.allocations:
            if name == operator_id:
                return budget
        return 0


class AdaptiveSearchPolicy:
    """Allocate more computation to operators with better evidenced value per cost."""

    def allocate(
        self,
        trials: Iterable[SearchOperatorTrial],
        *,
        total_budget: int,
        minimum_each: int = 1,
    ) -> SearchBudgetAllocation:
        evidence = tuple(trials)
        if total_budget < 1 or minimum_each < 0:
            raise FoundationError("search budget values are invalid")
        operators = sorted({item.operator_id for item in evidence})
        if not operators:
            raise FoundationError("adaptive search requires operator evidence")
        if total_budget < minimum_each * len(operators):
            raise FoundationError("search budget cannot satisfy minimum allocation")
        scores: dict[str, float] = {}
        for operator in operators:
            relevant = [item for item in evidence if item.operator_id == operator]
            success_rate = sum(item.success for item in relevant) / len(relevant)
            mean_gain = sum(item.information_gain for item in relevant) / len(relevant)
            mean_cost = sum(item.cost for item in relevant) / len(relevant)
            scores[operator] = (0.6 * success_rate + 0.4 * mean_gain) / (1.0 + mean_cost)
        allocations = dict.fromkeys(operators, minimum_each)
        remaining = total_budget - sum(allocations.values())
        if remaining:
            score_total = sum(scores.values())
            if score_total == 0.0:
                for index in range(remaining):
                    allocations[operators[index % len(operators)]] += 1
            else:
                fractions = {
                    operator: remaining * score / score_total for operator, score in scores.items()
                }
                floors = {operator: int(value) for operator, value in fractions.items()}
                for operator, value in floors.items():
                    allocations[operator] += value
                leftover = remaining - sum(floors.values())
                ranking = sorted(
                    operators,
                    key=lambda op: (-(fractions[op] - floors[op]), -scores[op], op),
                )
                for operator in ranking[:leftover]:
                    allocations[operator] += 1
        return SearchBudgetAllocation(tuple(sorted(allocations.items())))


@dataclass(frozen=True, slots=True)
class LearningStrategyTrial:
    """Performance of one learning strategy on one task family."""

    strategy_id: str
    task_family: str
    score: float
    samples_used: int

    def __post_init__(self) -> None:
        require_text(self.strategy_id, field_name="strategy_id")
        require_text(self.task_family, field_name="task_family")
        if not 0.0 <= self.score <= 1.0 or self.samples_used < 1:
            raise FoundationError("learning strategy trial metrics are invalid")


@dataclass(frozen=True, slots=True)
class MetaLearningDecision:
    """Evidence that previous learning changed how future learning is performed."""

    task_family: str
    selected_strategy_id: str
    prior_default_strategy_id: str
    selected_mean_score: float
    default_mean_score: float
    changed_strategy: bool


class MetaLearningController:
    """Learn which learning strategy works best for a task family."""

    def select(
        self,
        trials: Iterable[LearningStrategyTrial],
        *,
        task_family: str,
        default_strategy_id: str,
    ) -> MetaLearningDecision:
        family = require_text(task_family, field_name="task_family")
        default = require_text(default_strategy_id, field_name="default_strategy_id")
        relevant = tuple(item for item in trials if item.task_family == family)
        if not relevant:
            raise FoundationError("meta-learning requires strategy evidence for the task family")
        grouped: dict[str, list[float]] = {}
        for trial in relevant:
            grouped.setdefault(trial.strategy_id, []).append(trial.score)
        if default not in grouped:
            raise FoundationError("default strategy must have comparison evidence")
        means = {key: sum(values) / len(values) for key, values in grouped.items()}
        selected = max(means, key=lambda key: (means[key], tuple(-ord(ch) for ch in key)))
        return MetaLearningDecision(
            task_family=family,
            selected_strategy_id=selected,
            prior_default_strategy_id=default,
            selected_mean_score=round(means[selected], 12),
            default_mean_score=round(means[default], 12),
            changed_strategy=selected != default,
        )


@dataclass(frozen=True, slots=True)
class FailureObservation:
    """One self-model calibration observation."""

    capability_id: str
    predicted_success: float
    actual_success: bool
    failure_mode: str

    def __post_init__(self) -> None:
        require_text(self.capability_id, field_name="capability_id")
        require_text(self.failure_mode, field_name="failure_mode")
        if not 0.0 <= self.predicted_success <= 1.0:
            raise FoundationError("predicted_success must be between zero and one")


@dataclass(frozen=True, slots=True)
class SelfDiagnosticReport:
    """Measured blind spots and confidence calibration for the self model."""

    capability_id: str
    empirical_success: float
    mean_predicted_success: float
    calibration_error: float
    dominant_failure_mode: str | None
    blind_spot_detected: bool


class SelfDiagnostic:
    """Measure what Sally falsely thinks she knows, not only what she can do."""

    def diagnose(
        self,
        observations: Iterable[FailureObservation],
        *,
        blind_spot_threshold: float = 0.25,
    ) -> tuple[SelfDiagnosticReport, ...]:
        items = tuple(observations)
        if not items:
            raise FoundationError("self diagnosis requires observations")
        capabilities = sorted({item.capability_id for item in items})
        reports: list[SelfDiagnosticReport] = []
        for capability in capabilities:
            relevant = [item for item in items if item.capability_id == capability]
            empirical = sum(item.actual_success for item in relevant) / len(relevant)
            predicted = sum(item.predicted_success for item in relevant) / len(relevant)
            error = abs(predicted - empirical)
            failures = [item.failure_mode for item in relevant if not item.actual_success]
            dominant = None
            if failures:
                dominant = max(sorted(set(failures)), key=failures.count)
            reports.append(
                SelfDiagnosticReport(
                    capability_id=capability,
                    empirical_success=round(empirical, 12),
                    mean_predicted_success=round(predicted, 12),
                    calibration_error=round(error, 12),
                    dominant_failure_mode=dominant,
                    blind_spot_detected=predicted - empirical >= blind_spot_threshold,
                )
            )
        return tuple(reports)


@dataclass(frozen=True, slots=True)
class ImprovementBenchmark:
    """Measured baseline and candidate performance for a proposed internal change."""

    benchmark_id: str
    baseline_score: float
    candidate_score: float
    unrelated_regression: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.benchmark_id, field_name="benchmark_id")
        for name, value in (
            ("baseline_score", self.baseline_score),
            ("candidate_score", self.candidate_score),
            ("unrelated_regression", self.unrelated_regression),
        ):
            if not 0.0 <= value <= 1.0:
                raise FoundationError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class SelfImprovementResult:
    """Governed self-improvement evidence; candidate may be proposed but not self-authorized."""

    proposal: ImprovementProposal
    measured_gain: float
    regression: float
    adoption_recommended: bool
    authority_required: bool = True

    def to_payload(self) -> JsonObject:
        return {
            "proposal": self.proposal.to_payload(),
            "measured_gain": self.measured_gain,
            "regression": self.regression,
            "adoption_recommended": self.adoption_recommended,
            "authority_required": self.authority_required,
        }


class SelfImprovementLab:
    """Turn measured weakness and benchmarked improvement into a proposal only."""

    def propose(
        self,
        *,
        self_model: SelfModel,
        target_capability: str,
        description: str,
        benchmarks: Iterable[ImprovementBenchmark],
        max_regression: float = 0.05,
    ) -> SelfImprovementResult:
        target = require_text(target_capability, field_name="target_capability")
        relevant_measure = next(
            (item for item in self_model.measures if item.capability_id.value == target),
            None,
        )
        if relevant_measure is None:
            raise FoundationError("self-improvement target must exist in evidence-bound self model")
        measured = tuple(benchmarks)
        if not measured:
            raise FoundationError("self-improvement proposal requires benchmark evidence")
        gain = sum(item.candidate_score - item.baseline_score for item in measured) / len(measured)
        regression = max(item.unrelated_regression for item in measured)
        evidence = tuple(
            DigestRecord.from_payload(
                {
                    "benchmark_id": item.benchmark_id,
                    "baseline_score": item.baseline_score,
                    "candidate_score": item.candidate_score,
                    "unrelated_regression": item.unrelated_regression,
                }
            )
            for item in measured
        )
        identity = DigestRecord.from_payload(
            {
                "target": target,
                "description": description,
                "evidence": [item.value for item in evidence],
            }
        )
        proposal = ImprovementProposal.create(
            proposal_id=f"self-improvement-{identity.value[:16]}",
            target_capability=target,
            description=require_text(description, field_name="description"),
            expected_benefit=max(0.0, min(1.0, gain)),
            regression_risk=regression,
            evidence_digests=evidence,
        )
        return SelfImprovementResult(
            proposal=proposal,
            measured_gain=round(gain, 12),
            regression=round(regression, 12),
            adoption_recommended=gain > 0.0 and regression <= max_regression,
        )
