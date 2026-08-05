"""World-model, causal inference, planning, and authority tests."""

from __future__ import annotations

from ix_sally.cognition import (
    ActionSpec,
    CausalRule,
    CognitiveValue,
    DeterministicPlanner,
    ExecutionPermission,
    FactEffect,
    FactPattern,
    FactStatus,
    PlanSimulator,
    PlanStatus,
    WorldFact,
    WorldModel,
)
from ix_sally.digest import DigestRecord


def _observed(
    fact_id: str,
    subject: str,
    predicate: str,
    value: object,
) -> WorldFact:
    assert isinstance(value, str | int | float | bool | type(None))
    return WorldFact.create(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,
        value=CognitiveValue.from_python(value),
        status=FactStatus.OBSERVED,
        confidence=1.0,
        evidence_digests=(DigestRecord.from_payload({"fact": fact_id}),),
    )


def test_world_model_preserves_prediction_status() -> None:
    """Rule output must remain predicted until separately observed or inferred."""
    evidence = DigestRecord.from_payload({"study": "heat"})
    model = WorldModel(
        facts=(_observed("hot", "room", "temperature", "hot"),),
        rules=(
            CausalRule.create(
                rule_id="heat-implies-cooling",
                conditions=(
                    FactPattern.create(
                        subject="room",
                        predicate="temperature",
                        value=CognitiveValue.from_python("hot"),
                    ),
                ),
                effect_subject="room",
                effect_predicate="needs-cooling",
                effect_value=CognitiveValue.from_python(True),
                confidence=0.9,
                evidence_digests=(evidence,),
            ),
        ),
    )

    prediction = model.predict()[0]

    assert prediction.status is FactStatus.PREDICTED
    assert prediction.predicate.value == "needs-cooling"
    assert model.state().get(("room", "needs-cooling")) is None


def test_world_inference_adds_derived_fact_with_provenance() -> None:
    """Inference must add an inferred fact and retain source identities."""
    source = _observed("hot", "room", "temperature", "hot")
    rule = CausalRule.create(
        rule_id="heat-implies-cooling",
        conditions=(
            FactPattern.create(
                subject="room",
                predicate="temperature",
                value=CognitiveValue.from_python("hot"),
            ),
        ),
        effect_subject="room",
        effect_predicate="needs-cooling",
        effect_value=CognitiveValue.from_python(True),
        confidence=0.8,
        evidence_digests=(DigestRecord.from_payload({"rule": "validated"}),),
    )

    inferred = WorldModel((source,), (rule,)).infer()
    fact = inferred.state()[("room", "needs-cooling")]

    assert fact.status is FactStatus.INFERRED
    assert fact.derived_from[0].value == "hot"


def test_counterfactual_branch_does_not_mutate_original_model() -> None:
    """Hypothetical assumptions must remain isolated from observed state."""
    original = WorldModel((_observed("door", "door", "state", "closed"),), ())
    hypothetical = WorldFact.create(
        fact_id="door-open-assumption",
        subject="door",
        predicate="state",
        value=CognitiveValue.from_python("open"),
        status=FactStatus.HYPOTHETICAL,
        confidence=0.5,
    )

    branch = original.counterfactual((hypothetical,))

    assert original.state()[("door", "state")].value == CognitiveValue.from_python("closed")
    assert branch.state()[("door", "state")].value == CognitiveValue.from_python("open")


def test_planner_finds_shortest_stable_action_sequence() -> None:
    """Breadth-first search must return the shortest exact-state plan."""
    model = WorldModel((_observed("start", "device", "state", "off"),), ())
    actions = (
        ActionSpec.create(
            action_id="power-on",
            description="Power on the device.",
            preconditions=(
                FactPattern.create(
                    subject="device",
                    predicate="state",
                    value=CognitiveValue.from_python("off"),
                ),
            ),
            effects=(
                FactEffect.create(
                    subject="device",
                    predicate="state",
                    value=CognitiveValue.from_python("on"),
                ),
            ),
            cost=1.0,
            risk=0.1,
        ),
        ActionSpec.create(
            action_id="ready-device",
            description="Place the powered device into ready state.",
            preconditions=(
                FactPattern.create(
                    subject="device",
                    predicate="state",
                    value=CognitiveValue.from_python("on"),
                ),
            ),
            effects=(
                FactEffect.create(
                    subject="device",
                    predicate="state",
                    value=CognitiveValue.from_python("ready"),
                ),
            ),
            cost=1.0,
            risk=0.1,
        ),
    )
    goal = FactPattern.create(
        subject="device",
        predicate="state",
        value=CognitiveValue.from_python("ready"),
    )

    plan = DeterministicPlanner().plan(
        world_model=model,
        actions=actions,
        goal=goal,
    )

    assert plan.status is PlanStatus.FOUND
    assert tuple(action.action_id.value for action in plan.actions) == (
        "power-on",
        "ready-device",
    )


def test_planner_reports_already_satisfied_goal() -> None:
    """No-op goals must not create unnecessary action theater."""
    model = WorldModel((_observed("ready", "device", "state", "ready"),), ())
    goal = FactPattern.create(
        subject="device",
        predicate="state",
        value=CognitiveValue.from_python("ready"),
    )

    plan = DeterministicPlanner().plan(world_model=model, actions=(), goal=goal)

    assert plan.status is PlanStatus.ALREADY_SATISFIED
    assert not plan.actions


def test_plan_simulator_blocks_human_boundary_without_approval() -> None:
    """Authority-required action must not run merely because a plan exists."""
    model = WorldModel()
    action = ActionSpec.create(
        action_id="external-change",
        description="Simulated external change.",
        preconditions=(),
        effects=(
            FactEffect.create(
                subject="outside",
                predicate="changed",
                value=CognitiveValue.from_python(True),
            ),
        ),
        cost=0.0,
        risk=0.2,
        authority_required=True,
    )
    goal = FactPattern.create(
        subject="outside",
        predicate="changed",
        value=CognitiveValue.from_python(True),
    )
    plan = DeterministicPlanner().plan(
        world_model=model,
        actions=(action,),
        goal=goal,
    )

    receipt = PlanSimulator().execute(plan, world_model=model)

    assert receipt.permission is ExecutionPermission.REQUIRES_HUMAN
    assert receipt.resulting_model == model


def test_approved_plan_execution_remains_hypothetical() -> None:
    """Even approved local simulation must not claim an observed outside-world change."""
    model = WorldModel()
    action = ActionSpec.create(
        action_id="simulate-change",
        description="Simulated change.",
        preconditions=(),
        effects=(
            FactEffect.create(
                subject="simulation",
                predicate="state",
                value=CognitiveValue.from_python("changed"),
            ),
        ),
        cost=0.0,
        risk=0.1,
    )
    goal = FactPattern.create(
        subject="simulation",
        predicate="state",
        value=CognitiveValue.from_python("changed"),
    )
    plan = DeterministicPlanner().plan(
        world_model=model,
        actions=(action,),
        goal=goal,
    )

    receipt = PlanSimulator().execute(plan, world_model=model, human_approved=True)

    assert receipt.permission is ExecutionPermission.ALLOWED
    fact = receipt.resulting_model.state()[("simulation", "state")]
    assert fact.status is FactStatus.HYPOTHETICAL
