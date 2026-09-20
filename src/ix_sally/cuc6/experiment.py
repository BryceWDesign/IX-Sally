"""CUC-6: bounded lifelong generalization and representational freedom.

CUC-6 asks whether experience in earlier worlds changes how later IX-Sally learns.  It
also requires deeper representation synthesis, active contradiction repair in lifelong
memory, structural transfer across unrelated surface domains, mixed raw-text grounding,
and coherent multi-goal attention.  It is evidence of bounded mechanisms, not AGI proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from ix_sally.cognition.goal_portfolio import GoalPortfolioManager
from ix_sally.cognition.goal_reasoning import GoalEvidence
from ix_sally.cognition.goals import GoalSpec
from ix_sally.cognition.knowledge_maintenance import ContextualKnowledgeEvidence, KnowledgeMaintenanceEngine
from ix_sally.cognition.lifelong import KnowledgeItem, LifelongKnowledgeStore
from ix_sally.cognition.lifetime_learning import LifetimeChallenge, LifetimeLearningEngine, LifetimeLearningReport
from ix_sally.cognition.online_meta import OnlineMetaProfile
from ix_sally.cognition.relational_transfer import RelationEdge, RelationalTransferEngine, RelationalWorld
from ix_sally.cognition.representation import RepresentationObservation
from ix_sally.cognition.representation_programs import InventedRepresentationProgram, RepresentationProgramInventor
from ix_sally.cognition.system import SallyCognitiveSystem
from ix_sally.cognition.text_grounding import TextOutcomeGrounder, TextOutcomeObservation
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.world_model import FactPattern
from ix_sally.digest import DigestRecord, JsonObject


def _world_observations(prefix: str, *, train: bool, permutation: int = 0) -> tuple[RepresentationObservation, ...]:
    ab = (-2.0, -1.0, 1.0, 2.0) if train else (-4.0, -3.0, 3.0, 4.0)
    cs = (-6.0, -3.0, -1.0, 1.0, 3.0, 6.0) if train else (-20.0, -7.0, -2.0, 2.0, 7.0, 20.0)
    observations: list[RepresentationObservation] = []
    for index, (a, b, c) in enumerate(product(ab, ab, cs)):
        base = (a, b, c)
        if permutation == 1:
            channels = (c, a, b)
        elif permutation == 2:
            channels = (b, c, a)
        else:
            channels = base
        consequence = channels[0] * channels[1] + channels[2] >= 0.0
        observations.append(
            RepresentationObservation(f"{prefix}-{index}", channels, consequence)
        )
    return tuple(observations)


def _lifetime_challenges(count: int = 12) -> tuple[LifetimeChallenge, ...]:
    return tuple(
        LifetimeChallenge(
            challenge_id=f"sealed-world-{index}",
            training=_world_observations(f"train-{index}", train=True, permutation=index % 3),
            holdout=_world_observations(f"holdout-{index}", train=False, permutation=index % 3),
        )
        for index in range(count)
    )


@dataclass(frozen=True, slots=True)
class CUC6Report:
    compositional_representation: InventedRepresentationProgram
    lifetime_learning: LifetimeLearningReport
    knowledge_context_split: bool
    relational_transfer: bool
    text_grounding: bool
    goal_portfolio_coherence: bool
    snapshot_meta_persistence: bool
    bounded_endurance_generations: int

    @property
    def demonstrated_count(self) -> int:
        flags = (
            self.compositional_representation.validation_accuracy == 1.0,
            self.compositional_representation.program.depth >= 2,
            self.lifetime_learning.later_learning_is_more_selective,
            self.knowledge_context_split,
            self.relational_transfer,
            self.text_grounding,
            self.goal_portfolio_coherence,
            self.snapshot_meta_persistence,
            self.bounded_endurance_generations >= 64,
        )
        return sum(flags)

    def to_payload(self) -> JsonObject:
        return {
            "release": "IX-Sally-v0.7.0",
            "experiment": "CUC-6-lifelong-generalization",
            "compositional_representation": self.compositional_representation.to_payload(),
            "lifetime_episodes": [item.to_payload() for item in self.lifetime_learning.episodes],
            "meta_profile_experiences": len(self.lifetime_learning.profile.experiences),
            "knowledge_context_split": self.knowledge_context_split,
            "relational_transfer": self.relational_transfer,
            "text_grounding": self.text_grounding,
            "goal_portfolio_coherence": self.goal_portfolio_coherence,
            "snapshot_meta_persistence": self.snapshot_meta_persistence,
            "bounded_endurance_generations": self.bounded_endurance_generations,
            "later_learning_is_more_selective": self.lifetime_learning.later_learning_is_more_selective,
            "demonstrated_count": self.demonstrated_count,
            "agi_certified": False,
            "claim_boundary": (
                "Bounded evidence that prior experience changes later learning, that Sally can synthesize multi-operation "
                "representations and maintain contradictory knowledge. This is not proof of AGI or unrestricted autonomy."
            ),
        }


def run_cuc6_experiment() -> CUC6Report:
    training = _world_observations("deep-train", train=True)
    holdout = _world_observations("deep-holdout", train=False)
    inventor = RepresentationProgramInventor()
    representation = inventor.invent(
        observations=training,
        max_depth=2,
        max_candidates=4096,
        minimum_improvement=0.10,
    )
    representation = inventor.validate(representation, observations=holdout)

    lifetime = LifetimeLearningEngine().run_lifetime(
        profile=OnlineMetaProfile(),
        challenges=_lifetime_challenges(),
        exploration_episodes=2,
    )

    source_item = KnowledgeItem(
        "overbroad-rule",
        DigestRecord.from_payload({"rule": "same prediction in all contexts"}),
        confidence=0.8,
        utility=0.7,
    )
    store = LifelongKnowledgeStore().integrate(source_item)
    evidence = (
        ContextualKnowledgeEvidence("overbroad-rule", "stable", True, True),
        ContextualKnowledgeEvidence("overbroad-rule", "stable", True, True),
        ContextualKnowledgeEvidence("overbroad-rule", "shifted", True, False),
        ContextualKnowledgeEvidence("overbroad-rule", "shifted", True, False),
    )
    maintenance = KnowledgeMaintenanceEngine().reconcile(store, evidence=evidence)
    knowledge_context_split = maintenance.contradiction_resolved and maintenance.split_concepts == ("overbroad-rule",)

    source_world = RelationalWorld(
        "industrial-control",
        (
            RelationEdge("sensor", "signals", "controller"),
            RelationEdge("controller", "drives", "actuator"),
            RelationEdge("bypass", "feeds", "actuator"),
        ),
    )
    target_world = RelationalWorld(
        "software-rendering",
        (
            RelationEdge("request", "calls", "adapter"),
            RelationEdge("adapter", "drives", "renderer"),
            RelationEdge("cache", "feeds", "renderer"),
        ),
    )
    transfer_engine = RelationalTransferEngine()
    schema = transfer_engine.learn(world=source_world, effective_node="controller")
    transferred = transfer_engine.transfer(schema, world=target_world)
    relational_transfer = transferred.inferred_node == "adapter" and transferred.structural_match

    text_features = TextOutcomeGrounder().discover(
        (
            TextOutcomeObservation("t1", "quiet glint corridor", True),
            TextOutcomeObservation("t2", "glint signal appears", True),
            TextOutcomeObservation("t3", "flat corridor dark", False),
            TextOutcomeObservation("t4", "quiet matte signal", False),
            TextOutcomeObservation("t5", "glint matte corridor", True),
            TextOutcomeObservation("t6", "dark flat signal", False),
        )
    )
    text_grounding = bool(text_features) and text_features[0].token == "glint"

    base = GoalSpec.create(
        goal_id="map-world",
        description="Reduce uncertainty about the unfamiliar world.",
        desired_state=FactPattern.create(
            subject="world", predicate="mapped", value=CognitiveValue.from_python(True)
        ),
        priority=0.9,
        utility=0.9,
        risk_limit=0.1,
    )
    dependent = GoalSpec.create(
        goal_id="exploit-map",
        description="Use the validated map to solve the world.",
        desired_state=FactPattern.create(
            subject="world", predicate="solved", value=CognitiveValue.from_python(True)
        ),
        priority=0.8,
        utility=0.9,
        risk_limit=0.1,
        dependency_ids=("map-world",),
    )
    stale = GoalSpec.create(
        goal_id="stale-goal",
        description="Goal whose premise no longer holds.",
        desired_state=FactPattern.create(
            subject="world", predicate="obsolete", value=CognitiveValue.from_python(True)
        ),
        priority=1.0,
        utility=0.8,
        risk_limit=0.1,
    )
    portfolio = GoalPortfolioManager().allocate(
        (base, dependent, stale),
        evidence=(
            GoalEvidence("map-world", 0.95, 0.9, 0.8),
            GoalEvidence("exploit-map", 0.9, 0.9, 0.3),
            GoalEvidence("stale-goal", 0.05, 0.8, 0.0),
        ),
        attention_budget=0.6,
        per_goal_cost={"map-world": 0.3, "exploit-map": 0.3, "stale-goal": 0.3},
    )
    goal_portfolio_coherence = (
        portfolio.selected_goal_ids == ("map-world", "exploit-map")
        and portfolio.abandoned_goal_ids == ("stale-goal",)
    )

    system = SallyCognitiveSystem.create()
    system.online_meta_profile = lifetime.profile
    system.lifelong_knowledge = maintenance.store
    # Exercise bounded long-duration maintenance and checkpoint recovery without pretending
    # wall-clock runtime itself establishes intelligence.
    for _ in range(64):
        system.lifelong_knowledge = system.lifelong_knowledge.advance_generation().consolidate(minimum_score=0.05)
    snapshot = system.snapshot()
    restored = SallyCognitiveSystem.from_snapshot(snapshot)
    snapshot_meta_persistence = (
        restored.online_meta_profile == system.online_meta_profile
        and restored.lifelong_knowledge == system.lifelong_knowledge
        and restored.state_payload() == system.state_payload()
    )

    return CUC6Report(
        compositional_representation=representation,
        lifetime_learning=lifetime,
        knowledge_context_split=knowledge_context_split,
        relational_transfer=relational_transfer,
        text_grounding=text_grounding,
        goal_portfolio_coherence=goal_portfolio_coherence,
        snapshot_meta_persistence=snapshot_meta_persistence,
        bounded_endurance_generations=64,
    )
