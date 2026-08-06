"""Goal-graph and calibrated-uncertainty tests."""

from __future__ import annotations

import pytest

from ix_sally.cognition import CognitiveValue, FactPattern, FactStatus, WorldFact, WorldModel
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.uncertainty import CalibrationObservation, UncertaintyLedger
from ix_sally.digest import DigestRecord
from ix_sally.foundation import FoundationError


def _pattern(value: str) -> FactPattern:
    return FactPattern.create(
        subject="system",
        predicate="state",
        value=CognitiveValue.from_python(value),
    )


def _observed(value: str) -> WorldFact:
    return WorldFact.create(
        fact_id=f"state-{value}",
        subject="system",
        predicate="state",
        value=CognitiveValue.from_python(value),
        status=FactStatus.OBSERVED,
        confidence=1.0,
        evidence_digests=(DigestRecord.from_payload({"state": value}),),
    )


def _goal(
    goal_id: str,
    desired: str,
    *,
    priority: float,
    dependencies: tuple[str, ...] = (),
    status: GoalStatus = GoalStatus.PROPOSED,
) -> GoalSpec:
    return GoalSpec.create(
        goal_id=goal_id,
        description=f"Reach {desired} state.",
        desired_state=_pattern(desired),
        priority=priority,
        utility=0.8,
        risk_limit=0.2,
        dependency_ids=dependencies,
        status=status,
    )


def test_goal_graph_selects_highest_priority_eligible_goal() -> None:
    """Selection must respect dependencies before priority."""
    graph = GoalGraph.create(
        (
            _goal("foundation", "prepared", priority=0.4),
            _goal(
                "advanced",
                "complete",
                priority=1.0,
                dependencies=("foundation",),
            ),
            _goal("independent", "safe", priority=0.7),
        )
    )

    selected = graph.select(WorldModel())

    assert selected is not None
    assert selected.goal_id.value == "independent"


def test_goal_dependency_becomes_selectable_after_explicit_satisfaction() -> None:
    """A dependency transition must change eligibility without changing priority."""
    graph = GoalGraph.create(
        (
            _goal("foundation", "prepared", priority=0.4, status=GoalStatus.SATISFIED),
            _goal(
                "advanced",
                "complete",
                priority=1.0,
                dependencies=("foundation",),
            ),
        )
    )

    selected = graph.select(WorldModel())

    assert selected is not None
    assert selected.goal_id.value == "advanced"


def test_goal_graph_rejects_unknown_dependency() -> None:
    """Missing prerequisite goals must never be silently ignored."""
    with pytest.raises(FoundationError, match="unknown dependencies"):
        GoalGraph.create(
            (
                _goal(
                    "advanced",
                    "complete",
                    priority=1.0,
                    dependencies=("missing",),
                ),
            )
        )


def test_goal_graph_rejects_dependency_cycle() -> None:
    """Recursive goals must fail before executive selection."""
    with pytest.raises(FoundationError, match="dependency cycle"):
        GoalGraph.create(
            (
                _goal("one", "one", priority=0.5, dependencies=("two",)),
                _goal("two", "two", priority=0.5, dependencies=("one",)),
            )
        )


def test_goal_reconciliation_requires_world_state_match() -> None:
    """A goal becomes satisfied only from an exact world-model fact."""
    graph = GoalGraph.create((_goal("ready", "ready", priority=1.0),))
    model = WorldModel((_observed("ready"),), ())

    reconciled = graph.reconcile(model)

    assert reconciled.require("ready").status is GoalStatus.SATISFIED
    assert reconciled.select(model) is None


def test_blocked_goal_requires_reason() -> None:
    """Lifecycle blocking must retain an explicit explanation."""
    with pytest.raises(FoundationError, match="status reason"):
        GoalSpec.create(
            goal_id="blocked",
            description="Blocked goal.",
            desired_state=_pattern("blocked"),
            priority=0.5,
            utility=0.5,
            risk_limit=0.5,
            status=GoalStatus.BLOCKED,
        )


def _observation(
    observation_id: str,
    probability: float,
    observed: bool,
    *,
    capability: str = "planning",
) -> CalibrationObservation:
    return CalibrationObservation.create(
        observation_id=observation_id,
        capability_id=capability,
        predicted_probability=probability,
        observed=observed,
        evidence_digest=DigestRecord.from_payload(
            {"observation": observation_id, "observed": observed}
        ),
        context="Held-out deterministic evaluation.",
    )


def test_uncertainty_report_calculates_exact_brier_score() -> None:
    """Forecast quality must be measured from original probabilities."""
    ledger = UncertaintyLedger.create(
        (
            _observation("one", 0.8, True),
            _observation("two", 0.2, False),
        )
    )

    report = ledger.report(bin_count=5)

    assert report.observation_count == 2
    assert report.brier_score == 0.04
    assert report.expected_calibration_error == 0.2


def test_uncertainty_report_can_filter_capability() -> None:
    """Calibration for one capability must exclude unrelated forecasts."""
    ledger = UncertaintyLedger.create(
        (
            _observation("planning", 0.9, True),
            _observation("memory", 0.1, True, capability="memory"),
        )
    )

    report = ledger.report(capability_id="planning")

    assert report.observation_count == 1
    assert report.brier_score == 0.01


def test_uncertainty_ledger_rejects_duplicate_observation() -> None:
    """Repeated identifiers must not overwrite calibration evidence."""
    observation = _observation("same", 0.5, True)
    with pytest.raises(FoundationError, match="duplicate observations"):
        UncertaintyLedger((observation, observation))


def test_empty_calibration_report_is_explicit_zero_sample() -> None:
    """No data must remain distinguishable from perfect calibration."""
    report = UncertaintyLedger().report()

    assert report.observation_count == 0
    assert report.brier_score == 0.0
    assert report.bins == ()
