"""CUC-3 experiment for generative cognition beyond a supplied hypothesis catalog."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.cognition.invention import (
    ConceptInventor,
    InventedHypothesis,
    InventedPrimitive,
    TransformationExample,
)
from ix_sally.cognition.instrumental_goals import (
    InstrumentalGoalGenerator,
    InstrumentalGoalKind,
    InstrumentalGoalProposal,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.uncertainty import CalibrationObservation, UncertaintyLedger
from ix_sally.digest import DigestRecord, JsonObject


def _base_primitives() -> tuple[ActionPrimitive, ...]:
    return (
        ActionPrimitive("increment", lambda value: value + 1),
        ActionPrimitive("decrement", lambda value: value - 1),
        ActionPrimitive("double", lambda value: value * 2),
        ActionPrimitive("negate", lambda value: -value),
    )


@dataclass(frozen=True, slots=True)
class CUC3Report:
    """Evidence for invented hypotheses, invented primitives, and derived goals."""

    hypothesis: InventedHypothesis
    invented_primitive: InventedPrimitive
    holdout_input: int
    holdout_expected: int
    holdout_actual: int
    primitive_probe_input: int
    primitive_probe_output: int
    generated_goals: tuple[InstrumentalGoalProposal, ...]

    @property
    def hypothesis_invention_demonstrated(self) -> bool:
        return (
            self.hypothesis.origin == "sally-synthesized"
            and self.hypothesis.training_accuracy == 1.0
            and self.hypothesis.validation_accuracy == 1.0
            and self.holdout_actual == self.holdout_expected
        )

    @property
    def primitive_invention_demonstrated(self) -> bool:
        return (
            self.invented_primitive.origin == "sally-invented-abstraction"
            and self.invented_primitive.validation_accuracy == 1.0
            and self.primitive_probe_output == 11
        )

    @property
    def self_created_goals_demonstrated(self) -> bool:
        kinds = {item.kind for item in self.generated_goals}
        required = {
            InstrumentalGoalKind.SELF_IMPROVEMENT,
            InstrumentalGoalKind.INFORMATION_GATHERING,
            InstrumentalGoalKind.OPERATIONAL_CONTINUITY,
        }
        return required.issubset(kinds)

    def to_payload(self) -> JsonObject:
        return {
            "experiment": "CUC-3-generative-cognition",
            "invented_hypothesis": self.hypothesis.to_payload(),
            "hypothesis_invention_demonstrated": self.hypothesis_invention_demonstrated,
            "invented_primitive": self.invented_primitive.to_payload(),
            "primitive_invention_demonstrated": self.primitive_invention_demonstrated,
            "holdout": {
                "input": self.holdout_input,
                "expected": self.holdout_expected,
                "actual": self.holdout_actual,
            },
            "primitive_probe": {
                "input": self.primitive_probe_input,
                "output": self.primitive_probe_output,
            },
            "generated_goals": [item.to_payload() for item in self.generated_goals],
            "self_created_goals_demonstrated": self.self_created_goals_demonstrated,
            "agi_certified": False,
            "claim_boundary": (
                "Demonstrates bounded invention of compositional hypotheses and reusable "
                "abstractions plus evidence-triggered instrumental goal generation. It does "
                "not demonstrate AGI, consciousness, unrestricted self-modification, or "
                "unilateral external authority."
            ),
        }


def run_cuc3_experiment() -> CUC3Report:
    """Run one deterministic experiment without supplying a hypothesis catalog."""
    primitives = _base_primitives()
    inventor = ConceptInventor()
    training = (
        TransformationExample(1, 3),
        TransformationExample(2, 5),
        TransformationExample(4, 9),
    )
    hypothesis = inventor.invent_hypothesis(
        examples=training,
        primitives=primitives,
        max_depth=4,
    )
    holdout = TransformationExample(7, 15)
    hypothesis = inventor.validate_hypothesis(
        hypothesis,
        examples=(holdout,),
        primitives=primitives,
    )
    actual = hypothesis.apply(holdout.input_state, primitives)
    invented_primitive = inventor.promote_primitive(
        hypothesis,
        primitive_id="learned-double-plus-one",
        description=(
            "Learned abstraction discovered from examples: transform a state using a "
            "validated program rather than a predeclared hypothesis."
        ),
    )
    primitive_probe_input = 5
    primitive_probe_output = invented_primitive.apply(primitive_probe_input, primitives)

    evidence = DigestRecord.from_payload({"benchmark": "cuc3-search", "score": 0.2})
    self_model = SelfModel().update(
        CapabilityMeasure.create(
            capability_id="novel-search-efficiency",
            score=0.2,
            evidence_digests=(evidence,),
            limitation="Search over novel explanatory programs is still computationally costly.",
        )
    )
    calibration_evidence = DigestRecord.from_payload({"forecast": "cuc3-uncertainty"})
    uncertainty = UncertaintyLedger.create(
        (
            CalibrationObservation.create(
                observation_id="cuc3-calibration-1",
                capability_id="novel-search-efficiency",
                predicted_probability=0.9,
                observed=False,
                evidence_digest=calibration_evidence,
                context="Unexpected failure while exploring a novel transformation family.",
            ),
        )
    )
    generator = InstrumentalGoalGenerator()
    signals = generator.signals_from_state(
        self_model=self_model,
        uncertainty=uncertainty,
        continuity_risk=0.8,
        resource_pressure=0.7,
        integrity_anomaly=0.6,
    )
    generated_goals = generator.propose(signals)
    return CUC3Report(
        hypothesis=hypothesis,
        invented_primitive=invented_primitive,
        holdout_input=holdout.input_state,
        holdout_expected=holdout.output_state,
        holdout_actual=actual,
        primitive_probe_input=primitive_probe_input,
        primitive_probe_output=primitive_probe_output,
        generated_goals=generated_goals,
    )
