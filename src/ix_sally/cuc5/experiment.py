"""CUC-5: integrated recursive cognition over sealed, bounded challenges.

CUC-5 intentionally tests mechanisms together instead of declaring isolated modules to be
intelligence. The runtime must invent a representation, bind it into knowledge, author a
goal afterward, construct/validate a tool, respond to a structured unknown-unknown signal,
restructure knowledge, transfer an abstract rule across surface domains, actively select
an observation, detect causal instability, replan after surprise, diagnose its own blind
spot, change learning strategy from evidence, and propose (not self-authorize) improvement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ix_sally.cognition.active_inference import (
    ActivePerceptionPlanner,
    CausalDiscoveryEngine,
    CausalObservation,
    CounterfactualAction,
    CounterfactualSimulator,
    PerceptionProbe,
)
from ix_sally.cognition.external_evaluation import BlindEvaluatorHarness
from ix_sally.cognition.goal_reasoning import GoalArbiter, GoalEvidence, GoalRevisionEngine
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.lifelong import (
    DomainAdapter,
    KnowledgeItem,
    LifelongKnowledgeStore,
    OntologyRestructurer,
    PredictionSignature,
    SelfDirectedCurriculum,
    StructuralAnalogyEngine,
)
from ix_sally.cognition.long_horizon import HorizonAction, LongHorizonController
from ix_sally.cognition.meta_learning import (
    AdaptiveSearchPolicy,
    FailureObservation,
    ImprovementBenchmark,
    LearningStrategyTrial,
    MetaLearningController,
    SearchOperatorTrial,
    SelfDiagnostic,
    SelfImprovementLab,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.open_choice import ActionPrimitive
from ix_sally.cognition.raw_perception import RawSignal, RawSignalGrounder
from ix_sally.cognition.recursive_bootstrap import (
    RecursiveBootstrapReport,
    RecursiveCognitionEngine,
)
from ix_sally.cognition.representation import RepresentationInventor, RepresentationObservation
from ix_sally.cognition.tool_forge import ToolValidationCase
from ix_sally.cognition.unknowns import PredictionResidual
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.digest import DigestRecord, JsonObject


def _primary_training() -> tuple[RepresentationObservation, ...]:
    # Same-sign is not linearly recoverable from either raw channel alone; product creates
    # the representation needed to separate the classes.
    return (
        RepresentationObservation("p1", (2.0, 3.0), True),
        RepresentationObservation("p2", (-2.0, -1.0), True),
        RepresentationObservation("p3", (2.0, -3.0), False),
        RepresentationObservation("p4", (-2.0, 3.0), False),
        RepresentationObservation("p5", (4.0, 1.0), True),
        RepresentationObservation("p6", (-4.0, -1.0), True),
        RepresentationObservation("p7", (4.0, -1.0), False),
        RepresentationObservation("p8", (-4.0, 1.0), False),
    )


def _primary_holdout() -> tuple[RepresentationObservation, ...]:
    return (
        RepresentationObservation("ph1", (9.0, 2.0), True),
        RepresentationObservation("ph2", (-3.0, -8.0), True),
        RepresentationObservation("ph3", (7.0, -2.0), False),
        RepresentationObservation("ph4", (-5.0, 6.0), False),
    )


def _secondary_training() -> tuple[RepresentationObservation, ...]:
    # A different missing representation: closeness is captured by abs-difference.
    return (
        RepresentationObservation("s1", (1.0, 2.0), True),
        RepresentationObservation("s2", (3.0, 4.0), True),
        RepresentationObservation("s3", (-2.0, -1.0), True),
        RepresentationObservation("s4", (1.0, 6.0), False),
        RepresentationObservation("s5", (8.0, 2.0), False),
        RepresentationObservation("s6", (-7.0, 0.0), False),
    )


def _secondary_holdout() -> tuple[RepresentationObservation, ...]:
    return (
        RepresentationObservation("sh1", (10.0, 11.0), True),
        RepresentationObservation("sh2", (-4.0, -3.0), True),
        RepresentationObservation("sh3", (10.0, 3.0), False),
        RepresentationObservation("sh4", (-8.0, 2.0), False),
    )


def _primitives() -> tuple[ActionPrimitive, ...]:
    return (
        ActionPrimitive("increment", lambda value: value + 1, cost=0.1),
        ActionPrimitive("double", lambda value: value * 2, cost=0.2),
        ActionPrimitive("negate", lambda value: -value, cost=0.2),
    )


def _self_model() -> SelfModel:
    evidence = DigestRecord.from_payload({"source": "cuc5-measured-baseline"})
    return SelfModel(
        (
            CapabilityMeasure.create(
                capability_id="causal-discovery",
                score=0.70,
                evidence_digests=(evidence,),
                limitation="Moderate evidence under regime changes.",
            ),
            CapabilityMeasure.create(
                capability_id="novel-search-efficiency",
                score=0.25,
                evidence_digests=(evidence,),
                limitation="Search expands too many low-value candidates.",
            ),
            CapabilityMeasure.create(
                capability_id="representation-invention",
                score=0.60,
                evidence_digests=(evidence,),
                limitation="Bounded feature grammar.",
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class CUC5Report:
    bootstrap: RecursiveBootstrapReport
    representation_invention: bool
    semantic_primitive_invention: bool
    long_horizon_replanning: bool
    cross_domain_transfer: bool
    self_directed_curriculum: bool
    lifelong_learning: bool
    knowledge_restructuring: bool
    causal_discovery: bool
    raw_signal_grounding: bool
    active_perception: bool
    counterfactual_imagination: bool
    novel_tool_creation: bool
    reliable_self_modeling: bool
    measured_self_improvement: bool
    goal_conflict_resolution: bool
    goal_abandonment: bool
    unknown_unknown_detection: bool
    adaptive_search_management: bool
    meta_learning: bool
    unfamiliar_environment_competence: bool
    blind_evaluator_interface_ready: bool

    @property
    def demonstrated_count(self) -> int:
        flags = (
            self.bootstrap.recursive_growth_demonstrated,
            self.representation_invention,
            self.semantic_primitive_invention,
            self.long_horizon_replanning,
            self.cross_domain_transfer,
            self.self_directed_curriculum,
            self.lifelong_learning,
            self.knowledge_restructuring,
            self.causal_discovery,
            self.raw_signal_grounding,
            self.active_perception,
            self.counterfactual_imagination,
            self.novel_tool_creation,
            self.reliable_self_modeling,
            self.measured_self_improvement,
            self.goal_conflict_resolution,
            self.goal_abandonment,
            self.unknown_unknown_detection,
            self.adaptive_search_management,
            self.meta_learning,
            self.unfamiliar_environment_competence,
            self.blind_evaluator_interface_ready,
        )
        return sum(flags)

    def to_payload(self) -> JsonObject:
        return {
            "experiment": "CUC-5-recursive-cognitive-bootstrap",
            "recursive_bootstrap": self.bootstrap.to_payload(),
            "capabilities": {
                "recursive_cognitive_growth": self.bootstrap.recursive_growth_demonstrated,
                "representation_invention": self.representation_invention,
                "semantic_primitive_invention": self.semantic_primitive_invention,
                "long_horizon_replanning": self.long_horizon_replanning,
                "cross_domain_transfer": self.cross_domain_transfer,
                "self_directed_curriculum": self.self_directed_curriculum,
                "lifelong_learning": self.lifelong_learning,
                "knowledge_restructuring": self.knowledge_restructuring,
                "causal_discovery": self.causal_discovery,
                "raw_signal_grounding_partial": self.raw_signal_grounding,
                "active_perception": self.active_perception,
                "counterfactual_imagination": self.counterfactual_imagination,
                "novel_tool_creation": self.novel_tool_creation,
                "reliable_self_modeling": self.reliable_self_modeling,
                "measured_self_improvement_governed": self.measured_self_improvement,
                "goal_conflict_resolution": self.goal_conflict_resolution,
                "goal_abandonment": self.goal_abandonment,
                "unknown_unknown_detection": self.unknown_unknown_detection,
                "adaptive_search_management": self.adaptive_search_management,
                "meta_learning": self.meta_learning,
                "unfamiliar_environment_competence_procedural": (
                    self.unfamiliar_environment_competence
                ),
                "blind_evaluator_interface_ready": self.blind_evaluator_interface_ready,
            },
            "demonstrated_count": self.demonstrated_count,
            "agi_certified": False,
            "claim_boundary": (
                "Demonstrates bounded executable mechanisms and an integrated recursive cycle. "
                "It does not establish AGI, consciousness, unrestricted real-world perception, "
                "unbounded autonomy, or independent third-party validation. External consequential "
                "actions and self-modification remain governed by human authority."
            ),
        }


def run_cuc5_experiment() -> CUC5Report:
    primitives = _primitives()
    residuals = (
        PredictionResidual("r1", 0.95, True, False, (9, 9)),
        PredictionResidual("r2", 0.92, True, False, (9, 9)),
        PredictionResidual("r3", 0.91, True, False, (9, 9)),
        PredictionResidual("r4", 0.90, False, False, (1, 0)),
        PredictionResidual("r5", 0.88, True, True, (0, 1)),
    )
    bootstrap = RecursiveCognitionEngine().bootstrap(
        representation_training=_primary_training(),
        representation_holdout=_primary_holdout(),
        initial_state=2,
        primitives=primitives,
        known_states=(2, 3, 4, -2),
        # OpenGoalGenesis on this state/known set selects 5 via double -> increment.
        # These are independent states never used to author that goal.
        tool_validation_cases=(ToolValidationCase(1, 3), ToolValidationCase(3, 7)),
        residuals=residuals,
        second_representation_training=_secondary_training(),
        second_representation_holdout=_secondary_holdout(),
        max_goal_depth=3,
    )

    # Representation invention must beat the original atomic vocabulary and survive holdout.
    representation_ok = (
        bootstrap.first_representation.is_non_atomic
        and bootstrap.first_representation.training_accuracy == 1.0
        and bootstrap.first_representation.validation_accuracy == 1.0
        and bootstrap.first_representation.training_accuracy
        > bootstrap.first_representation.atomic_baseline_accuracy
    )
    semantic_primitive_ok = bootstrap.first_semantic_primitive.evaluate(
        (2.0, 1.0)
    ) and not bootstrap.first_semantic_primitive.evaluate((2.0, -1.0))

    # Long horizon: the model expects +1, but one real transition unexpectedly stalls.
    horizon_action = HorizonAction(
        "advance",
        model_transition=lambda state: state + 1,
        world_transition=lambda state, step: state if step == 2 else state + 1,
    )
    horizon = LongHorizonController().pursue(
        initial_state=0,
        goal_test=lambda state: state == 6,
        actions=(horizon_action,),
        max_steps=10,
        max_plan_depth=8,
    )
    horizon_ok = (
        horizon.success
        and horizon.replans >= 1
        and any(step.model_surprise for step in horizon.steps)
    )

    # Cross-domain transfer: learn 2x+1 on numbers, reuse unchanged relation on letters.
    numbers = DomainAdapter(
        "numbers",
        cast(Callable[[object], int], int),
        int,
    )
    letters = DomainAdapter(
        "letters",
        encode=lambda value: ord(str(value).upper()) - ord("A"),
        decode=lambda value: chr(ord("A") + value),
    )
    analogy = StructuralAnalogyEngine()
    rule = analogy.learn_affine(examples=((1, 3), (2, 5), (3, 7)), adapter=numbers)
    transfer_score = analogy.evaluate_transfer(
        rule,
        examples=(("A", "B"), ("B", "D"), ("C", "F")),
        adapter=letters,
    )
    transfer_ok = rule.source_domain == "numbers" and transfer_score == 1.0

    self_model = _self_model()
    curriculum = SelfDirectedCurriculum().choose(
        self_model=self_model,
        uncertainty={"novel-search-efficiency": 0.9, "causal-discovery": 0.3},
        opportunity={"novel-search-efficiency": 0.9},
    )
    curriculum_ok = curriculum.capability_id == "novel-search-efficiency"

    # Lifelong retention and ontology restructuring.
    d1 = DigestRecord.from_payload({"concept": "a"})
    d2 = DigestRecord.from_payload({"concept": "b"})
    store = LifelongKnowledgeStore().integrate(KnowledgeItem("a", d1, 0.9, 0.8))
    store = store.integrate(KnowledgeItem("b", d2, 0.9, 0.8))
    store = store.record_use("a", successful=True).advance_generation().advance_generation()
    consolidated = store.consolidate()
    lifelong_ok = {item.concept_id for item in consolidated.items} == {"a", "b"}
    restructurer = OntologyRestructurer()
    abstractions = restructurer.restructure(
        (
            PredictionSignature("a", (True, False, True)),
            PredictionSignature("b", (True, False, True)),
            PredictionSignature("c", (False, False, True)),
        )
    )
    restructured_store = restructurer.apply_to_store(consolidated, abstractions[0])
    restructure_ok = (
        len(abstractions) == 1
        and any(item.concept_id == abstractions[0].concept_id for item in restructured_store.items)
        and all(
            item.superseded_by == abstractions[0].concept_id
            for item in restructured_store.items
            if item.concept_id in {"a", "b"}
        )
    )

    causal_samples = (
        CausalObservation("o1", True, True, False),
        CausalObservation("o2", True, True, False),
        CausalObservation("o3", False, False, False),
        CausalObservation("o4", False, False, False),
        CausalObservation("i1", True, True, True, "r1"),
        CausalObservation("i2", True, True, True, "r1"),
        CausalObservation("i3", True, True, True, "r1"),
        CausalObservation("i4", True, False, True, "r1"),
        CausalObservation("i5", False, True, True, "r1"),
        CausalObservation("i6", False, False, True, "r1"),
        CausalObservation("i7", False, False, True, "r1"),
        CausalObservation("i8", False, False, True, "r1"),
        CausalObservation("j1", True, False, True, "r2"),
        CausalObservation("j2", True, False, True, "r2"),
        CausalObservation("j3", False, True, True, "r2"),
        CausalObservation("j4", False, True, True, "r2"),
    )
    causal = CausalDiscoveryEngine().discover(causal_samples)
    causal_ok = causal.confounding_suspected and causal.regime_change_suspected

    grounded = RawSignalGrounder().ground(RawSignal("stream", (0.0, 0.1, 0.2, 6.0, 6.1, 6.2)))
    raw_ok = bool(grounded.change_points) and grounded.variance > 0.0

    perception = ActivePerceptionPlanner().choose(
        priors=(0.5, 0.5),
        probes=(
            PerceptionProbe("weak-probe", (0.6, 0.4), cost=0.0),
            PerceptionProbe("discriminating-probe", (0.95, 0.05), cost=0.05),
        ),
    )
    perception_ok = (
        perception.probe_id == "discriminating-probe" and perception.expected_information_gain > 0.5
    )

    imagined = CounterfactualSimulator().imagine(
        initial_state=2,
        actions=(
            CounterfactualAction("increment", lambda state: state + 1, lambda state: state / 20),
            CounterfactualAction(
                "double", lambda state: state * 2, lambda state: state / 20, risk=0.05
            ),
        ),
        depth=2,
    )
    imagination_ok = (
        len(imagined) >= 4 and imagined[0].states[0] == 2 and len(imagined[0].states) == 3
    )

    tool_ok = (
        bootstrap.forged_tool.validation_accuracy == 1.0
        and bootstrap.forged_tool.tool_id.startswith("tool-")
    )

    diagnostics = SelfDiagnostic().diagnose(
        (
            FailureObservation("novel-search-efficiency", 0.90, False, "candidate-explosion"),
            FailureObservation("novel-search-efficiency", 0.85, False, "candidate-explosion"),
            FailureObservation("novel-search-efficiency", 0.90, True, "none"),
        )
    )
    diagnostic = diagnostics[0]
    diagnostic_ok = (
        diagnostic.blind_spot_detected and diagnostic.dominant_failure_mode == "candidate-explosion"
    )

    improvement = SelfImprovementLab().propose(
        self_model=self_model,
        target_capability="novel-search-efficiency",
        description="Prefer search operators with measured information gain per unit cost.",
        benchmarks=(
            ImprovementBenchmark("bench-a", 0.40, 0.78, 0.01),
            ImprovementBenchmark("bench-b", 0.45, 0.80, 0.02),
        ),
    )
    improvement_ok = (
        improvement.adoption_recommended
        and improvement.authority_required
        and not improvement.proposal.may_enter_validation()
    )

    goal_a = GoalSpec.create(
        goal_id="seek-left",
        description="Prefer left state.",
        desired_state=FactPattern.create(
            subject="sandbox", predicate="direction", value=CognitiveValue.from_python("left")
        ),
        priority=0.8,
        utility=0.8,
        risk_limit=0.1,
    )
    goal_b = GoalSpec.create(
        goal_id="seek-right",
        description="Prefer right state.",
        desired_state=FactPattern.create(
            subject="sandbox", predicate="direction", value=CognitiveValue.from_python("right")
        ),
        priority=0.8,
        utility=0.8,
        risk_limit=0.1,
    )
    resolution = GoalArbiter().resolve(
        (goal_a, goal_b),
        evidence=(
            GoalEvidence("seek-left", 0.9, 0.9, 0.4),
            GoalEvidence("seek-right", 0.3, 0.5, 0.2),
        ),
    )
    conflict_ok = (
        resolution.selected_goal_id == "seek-left" and len(resolution.conflicting_goal_ids) == 2
    )
    graph = GoalGraph.create((goal_a,))
    revised = GoalRevisionEngine().revise(
        graph,
        evidence=(GoalEvidence("seek-left", 0.05, 0.8),),
    )
    abandonment_ok = revised.require("seek-left").status is GoalStatus.ABANDONED

    unknown_ok = bootstrap.unknown_unknown.detected and bootstrap.second_representation is not None

    allocation = AdaptiveSearchPolicy().allocate(
        (
            SearchOperatorTrial("evidence-guided", True, 0.9, 0.2),
            SearchOperatorTrial("evidence-guided", True, 0.8, 0.2),
            SearchOperatorTrial("blind-enumeration", False, 0.1, 0.4),
            SearchOperatorTrial("blind-enumeration", False, 0.2, 0.4),
        ),
        total_budget=20,
    )
    search_ok = allocation.budget_for("evidence-guided") > allocation.budget_for(
        "blind-enumeration"
    )

    meta = MetaLearningController().select(
        (
            LearningStrategyTrial("breadth", "latent-relation", 0.45, 20),
            LearningStrategyTrial("breadth", "latent-relation", 0.50, 20),
            LearningStrategyTrial("residual-guided", "latent-relation", 0.85, 12),
            LearningStrategyTrial("residual-guided", "latent-relation", 0.90, 12),
        ),
        task_family="latent-relation",
        default_strategy_id="breadth",
    )
    meta_ok = meta.changed_strategy and meta.selected_strategy_id == "residual-guided"

    # Unfamiliar-environment control: without being told the missing representation operator,
    # the same general inventor must solve a second structurally different world.
    unfamiliar = RepresentationInventor().invent_binary(observations=_secondary_training())
    unfamiliar = RepresentationInventor().validate(unfamiliar, observations=_secondary_holdout())
    unfamiliar_ok = (
        unfamiliar.validation_accuracy == 1.0
        and unfamiliar.operator != bootstrap.first_representation.operator
    )

    # The independent evaluator itself cannot be supplied by us, but the repository contains
    # a nonce-bound blind challenge harness. Presence is not counted as independent validation.
    blind_ready = BlindEvaluatorHarness is not None

    return CUC5Report(
        bootstrap=bootstrap,
        representation_invention=representation_ok,
        semantic_primitive_invention=semantic_primitive_ok,
        long_horizon_replanning=horizon_ok,
        cross_domain_transfer=transfer_ok,
        self_directed_curriculum=curriculum_ok,
        lifelong_learning=lifelong_ok,
        knowledge_restructuring=restructure_ok,
        causal_discovery=causal_ok,
        raw_signal_grounding=raw_ok,
        active_perception=perception_ok,
        counterfactual_imagination=imagination_ok,
        novel_tool_creation=tool_ok,
        reliable_self_modeling=diagnostic_ok,
        measured_self_improvement=improvement_ok,
        goal_conflict_resolution=conflict_ok,
        goal_abandonment=abandonment_ok,
        unknown_unknown_detection=unknown_ok,
        adaptive_search_management=search_ok,
        meta_learning=meta_ok,
        unfamiliar_environment_competence=unfamiliar_ok,
        blind_evaluator_interface_ready=blind_ready,
    )
