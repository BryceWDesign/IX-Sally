"""Adversarial counterexamples against false improvement and sensor pseudo-quorums."""

from __future__ import annotations

from math import inf, nan

import pytest

from ix_sally.cognition.perception_quorum import (
    PerceptionChannelObservation,
    PerceptionQuorum,
)
from ix_sally.cognition.shadow_strategies import ShadowStrategyEvaluator, StrategyOutcome
from ix_sally.foundation import FoundationError


def test_holdout_regression_cannot_be_hidden_by_training_improvement() -> None:
    evidence = tuple(
        item for index in range(15) for item in (
            StrategyOutcome("inc", f"case-{index}", 0.1 if index < 3 else 1.0, index < 3),
            StrategyOutcome("cand", f"case-{index}", 0.9 if index < 3 else 0.0, index < 3),
        )
    )
    report = ShadowStrategyEvaluator().evaluate(
        incumbent_id="inc", candidate_id="cand", outcomes=evidence,
    )
    assert report.holdout_cases == 3
    assert report.incumbent_mean_error == 0.1
    assert report.candidate_mean_error == 0.9
    assert report.improvement == -0.8
    assert not report.eligible_for_human_review


def test_duplicate_case_rejected_even_when_scores_match() -> None:
    evidence = (
        StrategyOutcome("inc", "c", 0.1, True),
        StrategyOutcome("inc", "c", 0.1, True),
        StrategyOutcome("cand", "c", 0.0, True),
    )
    with pytest.raises(FoundationError, match="duplicate"):
        ShadowStrategyEvaluator().evaluate(
            incumbent_id="inc", candidate_id="cand", outcomes=evidence,
        )


def test_disagreement_over_holdout_identity_is_not_evidence() -> None:
    evidence = (
        StrategyOutcome("inc", "c", 0.2, True),
        StrategyOutcome("cand", "c", 0.0, False),
    )
    with pytest.raises(FoundationError, match="holdout classification"):
        ShadowStrategyEvaluator().evaluate(
            incumbent_id="inc", candidate_id="cand", outcomes=evidence,
        )


def test_nonholdout_safety_failure_still_blocks_review() -> None:
    evidence = tuple(
        item for i in range(3) for item in (
            StrategyOutcome("inc", f"c{i}", 0.8, True),
            StrategyOutcome("cand", f"c{i}", 0.1, True),
        )
    ) + (StrategyOutcome("cand", "training", 0.0, False, safety_failure=True),)
    report = ShadowStrategyEvaluator().evaluate(
        incumbent_id="inc", candidate_id="cand", outcomes=evidence,
    )
    assert report.improvement > 0
    assert not report.eligible_for_human_review


@pytest.mark.parametrize("invalid", [nan, inf, -inf])
def test_strategy_error_rejects_nonfinite_numbers(invalid: float) -> None:
    with pytest.raises(FoundationError):
        StrategyOutcome("inc", "c", invalid, True)


def test_no_holdouts_does_not_generate_training_based_promotion() -> None:
    evidence = (
        StrategyOutcome("inc", "train", 1.0, False),
        StrategyOutcome("cand", "train", 0.0, False),
    )
    result = ShadowStrategyEvaluator().evaluate(
        incumbent_id="inc", candidate_id="cand", outcomes=evidence,
    )
    assert result.holdout_cases == 0
    assert result.improvement == 0.0
    assert not result.eligible_for_human_review


def test_duplicate_channel_identity_fails_closed() -> None:
    sensor = PerceptionChannelObservation("a", (1.0,), 0.95)
    with pytest.raises(FoundationError, match="repeated"):
        PerceptionQuorum().assess((sensor, sensor))


def test_related_channels_cannot_fake_an_independent_quorum() -> None:
    channels = (
        PerceptionChannelObservation("a", (1.0,), 0.95, source_id="shared"),
        PerceptionChannelObservation("b", (1.0,), 0.95, source_id="shared"),
    )
    with pytest.raises(FoundationError, match="repeated"):
        PerceptionQuorum().assess(channels)


def test_distinct_sensors_preserve_normal_quorum() -> None:
    channels = (
        PerceptionChannelObservation("a", (1.0, 2.0), 0.95, source_id="physical-a"),
        PerceptionChannelObservation("b", (1.0, 2.0), 0.95, source_id="physical-b"),
    )
    report = PerceptionQuorum().assess(channels)
    assert report.quorum_satisfied
    assert report.fused_values == (1.0, 2.0)


@pytest.mark.parametrize("invalid", [nan, inf, -inf])
def test_bad_sensor_readings_fail_closed(invalid: float) -> None:
    with pytest.raises(FoundationError):
        PerceptionChannelObservation("a", (invalid,), 0.95)
    with pytest.raises(FoundationError):
        PerceptionChannelObservation("a", (1.0,), invalid)


def test_invalid_quorum_thresholds_are_rejected() -> None:
    readings = (PerceptionChannelObservation("a", (1.0,), 0.95),)
    for invalid in (nan, inf, -0.1, 1.1):
        with pytest.raises(FoundationError):
            PerceptionQuorum().assess(readings, disagreement_threshold=invalid)
