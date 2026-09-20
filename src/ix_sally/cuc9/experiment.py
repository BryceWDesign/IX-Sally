"""CUC-9: reality-scored shadow strategies with human-authorized promotion only."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.shadow_strategies import ShadowStrategyEvaluator, StrategyOutcome
from ix_sally.digest import JsonObject


@dataclass(frozen=True, slots=True)
class CUC9Report:
    candidate_improvement: float
    holdout_cases: int
    eligible_for_human_review: bool
    auto_promoted: bool

    def to_payload(self) -> JsonObject:
        return {
            "candidate_improvement": self.candidate_improvement,
            "holdout_cases": self.holdout_cases,
            "eligible_for_human_review": self.eligible_for_human_review,
            "auto_promoted": self.auto_promoted,
        }


def run_cuc9() -> CUC9Report:
    outcomes = (
        StrategyOutcome("incumbent", "h1", 0.40, True),
        StrategyOutcome("candidate", "h1", 0.15, True),
        StrategyOutcome("incumbent", "h2", 0.35, True),
        StrategyOutcome("candidate", "h2", 0.10, True),
        StrategyOutcome("incumbent", "h3", 0.45, True),
        StrategyOutcome("candidate", "h3", 0.20, True),
    )
    proposal = ShadowStrategyEvaluator().evaluate(
        incumbent_id="incumbent",
        candidate_id="candidate",
        outcomes=outcomes,
    )
    return CUC9Report(
        candidate_improvement=proposal.improvement,
        holdout_cases=proposal.holdout_cases,
        eligible_for_human_review=proposal.eligible_for_human_review,
        auto_promoted=False,
    )
