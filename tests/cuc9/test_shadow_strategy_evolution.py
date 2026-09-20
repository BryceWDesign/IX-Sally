from ix_sally.cognition.shadow_strategies import ShadowStrategyEvaluator, StrategyOutcome
from ix_sally.cuc9 import run_cuc9


def test_cuc9_candidate_can_qualify_for_review_but_never_auto_promotes() -> None:
    report = run_cuc9()
    assert report.candidate_improvement > 0.0
    assert report.holdout_cases == 3
    assert report.eligible_for_human_review
    assert not report.auto_promoted


def test_shadow_strategy_safety_failure_blocks_review_eligibility() -> None:
    outcomes = tuple(
        item
        for index in range(3)
        for item in (
            StrategyOutcome("inc", f"c{index}", 0.9, True),
            StrategyOutcome("cand", f"c{index}", 0.1, True, safety_failure=index == 2),
        )
    )
    result = ShadowStrategyEvaluator().evaluate(
        incumbent_id="inc",
        candidate_id="cand",
        outcomes=outcomes,
    )
    assert not result.eligible_for_human_review
