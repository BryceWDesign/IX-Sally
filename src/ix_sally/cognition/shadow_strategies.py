"""Paired, holdout-only evaluation for candidate cognitive strategies."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

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
        if not isfinite(self.error) or not 0.0 <= self.error <= 1.0:
            raise FoundationError("strategy error must be finite and between zero and one")


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
    """Evaluate paired unseen cases; never grant implementation authority."""

    def evaluate(
        self,
        *,
        incumbent_id: str,
        candidate_id: str,
        outcomes: tuple[StrategyOutcome, ...],
        minimum_holdouts: int = 3,
        minimum_improvement: float = 0.05,
    ) -> StrategyPromotionProposal:
        if incumbent_id == candidate_id:
            raise FoundationError("incumbent and candidate must be different strategies")
        if minimum_holdouts < 1:
            raise FoundationError("minimum_holdouts must be positive")
        if not isfinite(minimum_improvement) or not 0.0 <= minimum_improvement <= 1.0:
            raise FoundationError("minimum_improvement must be finite and in [0, 1]")
        incumbent = tuple(item for item in outcomes if item.strategy_id == incumbent_id)
        candidate = tuple(item for item in outcomes if item.strategy_id == candidate_id)
        if not incumbent or not candidate:
            raise FoundationError("shadow evaluation requires incumbent and candidate outcomes")
        if len({item.challenge_id for item in incumbent}) != len(incumbent):
            raise FoundationError("duplicate incumbent challenge evidence")
        if len({item.challenge_id for item in candidate}) != len(candidate):
            raise FoundationError("duplicate candidate challenge evidence")
        inc_by_case = {item.challenge_id: item for item in incumbent}
        cand_by_case = {item.challenge_id: item for item in candidate}
        shared = sorted(set(inc_by_case) & set(cand_by_case))
        if not shared:
            raise FoundationError("shadow strategies require shared challenge cases")
        if any(inc_by_case[key].holdout != cand_by_case[key].holdout for key in shared):
            raise FoundationError("inconsistent holdout classification across paired cases")
        # Non-holdout observations cannot influence the promotion improvement.
        holdout_keys = tuple(key for key in shared if inc_by_case[key].holdout)
        count = len(holdout_keys)
        inc_mean = sum(inc_by_case[key].error for key in holdout_keys) / count if count else 0.0
        cand_mean = sum(cand_by_case[key].error for key in holdout_keys) / count if count else 0.0
        improvement = inc_mean - cand_mean
        safety_failure = any(item.safety_failure for item in candidate)
        eligible = (
            count >= minimum_holdouts
            and improvement >= minimum_improvement
            and not safety_failure
        )
        if safety_failure:
            reason = "candidate has a recorded safety failure"
        elif count < minimum_holdouts:
            reason = "insufficient paired held-out evidence"
        elif not eligible:
            reason = "candidate does not improve on paired held-out cases"
        else:
            reason = "paired held-out improvement supports human review only"
        return StrategyPromotionProposal(
            incumbent_id=incumbent_id,
            candidate_id=candidate_id,
            incumbent_mean_error=round(inc_mean, 12),
            candidate_mean_error=round(cand_mean, 12),
            holdout_cases=count,
            improvement=round(improvement, 12),
            eligible_for_human_review=eligible,
            reason=reason,
        )
