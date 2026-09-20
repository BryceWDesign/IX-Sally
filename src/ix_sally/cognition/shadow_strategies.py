"""Evidence-driven shadow evaluation for candidate cognitive strategies."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    strategy_id: str
    challenge_id: str
    error: float
    holdout: bool
    safety_failure: bool = False

    def __post_init__(self) -> None:
        require_text(self.strategy_id, field_name="strategy_id")
        require_text(self.challenge_id, field_name="challenge_id")
        if not 0.0 <= self.error <= 1.0:
            raise FoundationError("strategy error must be between zero and one")


@dataclass(frozen=True, slots=True)
class StrategyPromotionProposal:
    incumbent_id: str
    candidate_id: str
    incumbent_mean_error: float
    candidate_mean_error: float
    holdout_cases: int
    improvement: float
    eligible_for_human_review: bool
    reason: str


class ShadowStrategyEvaluator:
    """Compare candidate cognition against an incumbent without auto-promoting it."""

    def evaluate(
        self,
        *,
        incumbent_id: str,
        candidate_id: str,
        outcomes: tuple[StrategyOutcome, ...],
        minimum_holdouts: int = 3,
        minimum_improvement: float = 0.05,
    ) -> StrategyPromotionProposal:
        incumbent = tuple(item for item in outcomes if item.strategy_id == incumbent_id)
        candidate = tuple(item for item in outcomes if item.strategy_id == candidate_id)
        if not incumbent or not candidate:
            raise FoundationError("shadow evaluation requires incumbent and candidate outcomes")
        inc_by_case = {item.challenge_id: item for item in incumbent}
        cand_by_case = {item.challenge_id: item for item in candidate}
        shared = sorted(set(inc_by_case) & set(cand_by_case))
        if not shared:
            raise FoundationError("shadow strategies require shared challenge cases")
        inc_mean = sum(inc_by_case[key].error for key in shared) / len(shared)
        cand_mean = sum(cand_by_case[key].error for key in shared) / len(shared)
        holdouts = sum(
            1 for key in shared if inc_by_case[key].holdout and cand_by_case[key].holdout
        )
        safety_failure = any(cand_by_case[key].safety_failure for key in shared)
        improvement = inc_mean - cand_mean
        eligible = (
            holdouts >= minimum_holdouts
            and improvement >= minimum_improvement
            and not safety_failure
        )
        reason = (
            "candidate outperforms incumbent on sufficient holdouts without safety failure"
            if eligible
            else "candidate lacks sufficient validated improvement for promotion"
        )
        return StrategyPromotionProposal(
            incumbent_id=incumbent_id,
            candidate_id=candidate_id,
            incumbent_mean_error=round(inc_mean, 12),
            candidate_mean_error=round(cand_mean, 12),
            holdout_cases=holdouts,
            improvement=round(improvement, 12),
            eligible_for_human_review=eligible,
            reason=reason,
        )
