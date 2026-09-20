"""Integrated IX-Sally experimental general-intelligence research runtime."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ix_sally.cognition.active_inference import (
    ActivePerceptionPlanner,
    CausalDiscoveryEngine,
    CausalDiscoveryReport,
    CausalObservation,
    CounterfactualAction,
    CounterfactualSimulator,
    ImaginedBranch,
    PerceptionProbe,
    ProbeChoice,
)
from ix_sally.cognition.active_memory import (
    ActiveMemoryEntry,
    ActiveMemoryStore,
)
from ix_sally.cognition.compiler import compile_ix_source
from ix_sally.cognition.curriculum import CurriculumLedger, CurriculumTrial
from ix_sally.cognition.episodes import CognitiveEpisode, EpisodeLedger
from ix_sally.cognition.executive import ExecutiveController, ExecutiveDecision
from ix_sally.cognition.external_evaluation import (
    BlindChallenge,
    BlindEvaluationResult,
    BlindEvaluatorHarness,
)
from ix_sally.cognition.goal_portfolio import GoalPortfolioDecision, GoalPortfolioManager
from ix_sally.cognition.goal_reasoning import (
    GoalArbiter,
    GoalEvidence,
    GoalResolution,
    GoalRevisionEngine,
)
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.governance_bridge import (
    CognitiveProposalBridge,
    CognitiveProposalBridgeResult,
)
from ix_sally.cognition.instrumental_goals import (
    InstrumentalGoalGenerator,
    InstrumentalGoalProposal,
)
from ix_sally.cognition.invention import (
    ConceptInventor,
    InventedHypothesis,
    InventedPrimitive,
    TransformationExample,
)
from ix_sally.cognition.knowledge_maintenance import (
    ContextualKnowledgeEvidence,
    KnowledgeMaintenanceEngine,
    KnowledgeMaintenanceReport,
)
from ix_sally.cognition.learning import LearningLedger, LearningOutcome
from ix_sally.cognition.lifelong import (
    AbstractTransitionRule,
    CurriculumChoice,
    DomainAdapter,
    KnowledgeItem,
    LifelongKnowledgeStore,
    OntologyRestructurer,
    PredictionSignature,
    RestructuredConcept,
    SelfDirectedCurriculum,
    StructuralAnalogyEngine,
)
from ix_sally.cognition.lifetime_learning import (
    LifetimeChallenge,
    LifetimeLearningEngine,
    LifetimeLearningReport,
)
from ix_sally.cognition.long_horizon import HorizonAction, LongHorizonController, LongHorizonResult
from ix_sally.cognition.meta_learning import (
    AdaptiveSearchPolicy,
    FailureObservation,
    ImprovementBenchmark,
    LearningStrategyTrial,
    MetaLearningController,
    MetaLearningDecision,
    SearchBudgetAllocation,
    SearchOperatorTrial,
    SelfDiagnostic,
    SelfDiagnosticReport,
    SelfImprovementLab,
    SelfImprovementResult,
)
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.ninefold import NinefoldCognitiveCycle, NinefoldCoordinator
from ix_sally.cognition.online_meta import OnlineMetaDecision, OnlineMetaProfile, TaskFingerprint
from ix_sally.cognition.open_choice import (
    ActionPrimitive,
    ConstructedAction,
    DeliberationPolicy,
    DeliberationSignals,
    OpenChoiceResult,
    OpenChoiceSynthesizer,
)
from ix_sally.cognition.open_goals import GeneratedGoal, IntrinsicDrives, OpenGoalGenesis
from ix_sally.cognition.persistence import CognitiveSnapshot
from ix_sally.cognition.planning import (
    ActionSpec,
    DeterministicPlanner,
    Plan,
    PlanExecutionReceipt,
    PlanSimulator,
)
from ix_sally.cognition.primitives import (
    PrimitiveExecution,
    PrimitiveExecutor,
    PrimitiveRegistry,
    default_primitive_registry,
)
from ix_sally.cognition.raw_perception import GroundedSignal, RawSignal, RawSignalGrounder
from ix_sally.cognition.recursive_bootstrap import (
    RecursiveBootstrapReport,
    RecursiveCognitionEngine,
)
from ix_sally.cognition.relational_transfer import (
    LearnedStructuralSchema,
    RelationalTransferEngine,
    RelationalWorld,
    TransferInference,
)
from ix_sally.cognition.representation import (
    InventedRepresentation,
    RepresentationInventor,
    RepresentationObservation,
    SemanticPrimitive,
)
from ix_sally.cognition.representation_programs import (
    InventedRepresentationProgram,
    RepresentationProgramInventor,
)
from ix_sally.cognition.semantic_genesis import (
    InventedSemantic,
    SemanticGenesisEngine,
    SemanticObservation,
)
from ix_sally.cognition.text_grounding import (
    GroundedTextFeature,
    TextOutcomeGrounder,
    TextOutcomeObservation,
)
from ix_sally.cognition.tool_forge import ForgedTool, ToolForge, ToolValidationCase
from ix_sally.cognition.uncertainty import (
    CalibrationObservation,
    CalibrationReport,
    UncertaintyLedger,
)
from ix_sally.cognition.unknowns import (
    PredictionResidual,
    UnknownUnknownDetector,
    UnknownUnknownSignal,
)
from ix_sally.cognition.values import CognitiveValue
from ix_sally.cognition.vm import IXVirtualMachine, VMResult, VMStatus
from ix_sally.cognition.workspace import CognitiveWorkspace, WorkspaceItem
from ix_sally.cognition.world_model import CausalRule, FactPattern, WorldFact, WorldModel
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError


@dataclass(slots=True)
class SallyCognitiveSystem:
    """One integrated, bounded cognitive runtime with explicit state transitions."""

    workspace: CognitiveWorkspace = field(default_factory=CognitiveWorkspace)
    active_memory: ActiveMemoryStore = field(default_factory=ActiveMemoryStore)
    world_model: WorldModel = field(default_factory=WorldModel)
    action_catalog: tuple[ActionSpec, ...] = ()
    learning: LearningLedger = field(default_factory=LearningLedger)
    self_model: SelfModel = field(default_factory=SelfModel)
    goals: GoalGraph = field(default_factory=GoalGraph)
    uncertainty: UncertaintyLedger = field(default_factory=UncertaintyLedger)
    episodes: EpisodeLedger = field(default_factory=EpisodeLedger)
    curriculum: CurriculumLedger | None = None
    primitive_registry: PrimitiveRegistry = field(default_factory=default_primitive_registry)
    lifelong_knowledge: LifelongKnowledgeStore = field(default_factory=LifelongKnowledgeStore)
    online_meta_profile: OnlineMetaProfile = field(default_factory=OnlineMetaProfile)
    runtime_memories: dict[str, CognitiveValue] = field(default_factory=dict)
    execution_count: int = 0
    cycle_count: int = 0

    def __post_init__(self) -> None:
        """Require counters and action identities to remain valid."""
        if self.execution_count < 0 or self.cycle_count < 0:
            raise FoundationError("system counters must not be negative")
        action_ids = [action.action_id.value for action in self.action_catalog]
        if len(action_ids) != len(set(action_ids)):
            raise FoundationError("system action catalog contains duplicate identifiers")

    @classmethod
    def create(cls) -> SallyCognitiveSystem:
        """Create a clean IX-Sally cognitive runtime."""
        return cls()

    @classmethod
    def from_snapshot(cls, snapshot: CognitiveSnapshot) -> SallyCognitiveSystem:
        """Restore a complete system from a verified canonical snapshot."""
        from ix_sally.cognition.restore import restore_system_state

        restored = restore_system_state(snapshot)
        system = cls(
            workspace=restored.workspace,
            active_memory=restored.active_memory,
            world_model=restored.world_model,
            action_catalog=restored.action_catalog,
            learning=restored.learning,
            self_model=restored.self_model,
            goals=restored.goals,
            uncertainty=restored.uncertainty,
            episodes=restored.episodes,
            curriculum=restored.curriculum,
            primitive_registry=restored.primitive_registry,
            lifelong_knowledge=restored.lifelong_knowledge,
            online_meta_profile=restored.online_meta_profile,
            runtime_memories=restored.runtime_memories,
            execution_count=restored.execution_count,
            cycle_count=restored.cycle_count,
        )
        if system.state_payload() != snapshot.state:
            raise FoundationError("restored cognitive system does not match snapshot state")
        return system

    def execute_ix(
        self,
        source: str,
        *,
        filename: str = "<memory>",
        max_steps: int = 10_000,
    ) -> VMResult:
        """Compile and execute IX source, committing memory only after a clean halt."""
        program = compile_ix_source(source, filename=filename)
        result = IXVirtualMachine(max_steps=max_steps).execute(
            program,
            memories=self.runtime_memories,
        )
        self.execution_count += 1
        if result.status is VMStatus.HALTED:
            self.runtime_memories = result.memory_map()
        return result

    def execute_primitive(
        self,
        primitive_id: str,
        inputs: Iterable[CognitiveValue],
    ) -> PrimitiveExecution:
        """Execute one validated cognitive primitive."""
        return PrimitiveExecutor(self.primitive_registry).execute(primitive_id, inputs)

    def admit_workspace(self, item: WorkspaceItem) -> None:
        """Admit one item under workspace capacity and attention policy."""
        self.workspace = self.workspace.admit(item)

    def append_memory(self, entry: ActiveMemoryEntry) -> None:
        """Append one active-memory entry under its truth-boundary rules."""
        self.active_memory = self.active_memory.append(entry)

    def observe(self, fact: WorldFact) -> None:
        """Append one world fact."""
        self.world_model = self.world_model.observe(fact)

    def add_causal_rule(self, rule: CausalRule) -> None:
        """Append one evidence-bound causal rule."""
        self.world_model = self.world_model.add_rule(rule)

    def infer_world(self) -> None:
        """Apply all currently satisfied causal rules once."""
        self.world_model = self.world_model.infer()

    def construct_open_choice(
        self,
        *,
        initial_state: int,
        goal_test: Callable[[int], bool],
        primitives: Iterable[ActionPrimitive],
        offered_actions: Iterable[ConstructedAction] = (),
        max_depth: int = 8,
        max_programs: int = 4096,
    ) -> OpenChoiceResult:
        """Author a complete action beyond a supplied menu when composition can satisfy it."""
        return OpenChoiceSynthesizer().synthesize(
            initial_state=initial_state,
            goal_test=goal_test,
            primitives=primitives,
            offered_actions=offered_actions,
            max_depth=max_depth,
            max_programs=max_programs,
        )

    def minimize_constructed_action(
        self,
        *,
        initial_state: int,
        action: ConstructedAction,
        primitives: Iterable[ActionPrimitive],
        goal_test: Callable[[int], bool],
    ) -> ConstructedAction:
        """Delete unnecessary steps while retaining only independently successful behavior."""
        return OpenChoiceSynthesizer().minimize(
            initial_state=initial_state,
            action=action,
            primitives=primitives,
            goal_test=goal_test,
        )

    def should_reopen_deliberation(self, signals: DeliberationSignals) -> bool:
        """Decide whether surprise or changed circumstances should interrupt a learned habit."""
        return DeliberationPolicy().should_reopen(signals)

    def invent_hypothesis(
        self,
        *,
        examples: Iterable[TransformationExample],
        primitives: Iterable[ActionPrimitive],
        max_depth: int = 6,
        max_programs: int = 4096,
    ) -> InventedHypothesis:
        """Invent an explanatory program without receiving a hypothesis catalog."""
        return ConceptInventor().invent_hypothesis(
            examples=examples,
            primitives=primitives,
            max_depth=max_depth,
            max_programs=max_programs,
        )

    def validate_invented_hypothesis(
        self,
        hypothesis: InventedHypothesis,
        *,
        examples: Iterable[TransformationExample],
        primitives: Iterable[ActionPrimitive],
    ) -> InventedHypothesis:
        """Test an invented explanation against held-out evidence."""
        return ConceptInventor().validate_hypothesis(
            hypothesis,
            examples=examples,
            primitives=primitives,
        )

    def promote_invented_primitive(
        self,
        hypothesis: InventedHypothesis,
        *,
        primitive_id: str,
        description: str,
    ) -> InventedPrimitive:
        """Turn a validated learned program into a reusable new abstraction."""
        return ConceptInventor().promote_primitive(
            hypothesis,
            primitive_id=primitive_id,
            description=description,
        )

    def self_generate_instrumental_goals(
        self,
        *,
        continuity_risk: float = 0.0,
        resource_pressure: float = 0.0,
        integrity_anomaly: float = 0.0,
    ) -> tuple[InstrumentalGoalProposal, ...]:
        """Derive bounded instrumental goals from Sally's measured internal condition."""
        generator = InstrumentalGoalGenerator()
        signals = generator.signals_from_state(
            self_model=self.self_model,
            uncertainty=self.uncertainty,
            continuity_risk=continuity_risk,
            resource_pressure=resource_pressure,
            integrity_anomaly=integrity_anomaly,
        )
        return generator.propose(signals)

    def invent_semantic(
        self,
        *,
        observations: Iterable[SemanticObservation],
        max_abs_weight: int = 2,
        minimum_improvement: float = 0.10,
    ) -> InventedSemantic:
        """Create an opaque predictive semantic distinction from unresolved raw structure."""
        return SemanticGenesisEngine().invent(
            observations=observations,
            max_abs_weight=max_abs_weight,
            minimum_improvement=minimum_improvement,
        )

    def validate_invented_semantic(
        self,
        concept: InventedSemantic,
        *,
        observations: Iterable[SemanticObservation],
    ) -> InventedSemantic:
        """Reality-test an invented semantic token on unseen observations."""
        return SemanticGenesisEngine().validate(concept, observations=observations)

    def generate_open_goal(
        self,
        *,
        initial_state: int,
        primitives: Iterable[ActionPrimitive],
        known_states: Iterable[int] = (),
        drives: IntrinsicDrives | None = None,
        max_depth: int = 4,
        max_programs: int = 512,
        state_bound: int = 256,
    ) -> GeneratedGoal:
        """Author a novel internal target without receiving a fixed goal category or target."""
        return OpenGoalGenesis().generate(
            initial_state=initial_state,
            primitives=primitives,
            known_states=known_states,
            drives=drives,
            max_depth=max_depth,
            max_programs=max_programs,
            state_bound=state_bound,
        )

    def invent_representation(
        self,
        *,
        observations: Iterable[RepresentationObservation],
        minimum_improvement: float = 0.15,
    ) -> InventedRepresentation:
        """Synthesize a non-atomic representation when raw channels are insufficient."""
        return RepresentationInventor().invent_binary(
            observations=observations,
            minimum_improvement=minimum_improvement,
        )

    def validate_representation(
        self,
        representation: InventedRepresentation,
        *,
        observations: Iterable[RepresentationObservation],
    ) -> InventedRepresentation:
        """Reality-test an invented representation on held-out evidence."""
        return RepresentationInventor().validate(representation, observations=observations)

    def promote_semantic_primitive(
        self,
        representation: InventedRepresentation,
    ) -> SemanticPrimitive:
        """Promote a validated invented representation into Sally's usable ontology."""
        return RepresentationInventor().promote(representation)

    def integrate_knowledge(self, item: KnowledgeItem) -> None:
        """Persist one learned concept/tool in lifelong knowledge."""
        self.lifelong_knowledge = self.lifelong_knowledge.integrate(item)

    def record_knowledge_use(self, concept_id: str, *, successful: bool) -> None:
        """Revise persistent knowledge confidence from later experience."""
        self.lifelong_knowledge = self.lifelong_knowledge.record_use(
            concept_id, successful=successful
        )

    def consolidate_lifelong_knowledge(self) -> None:
        """Consolidate persistent knowledge while protecting useful validated items."""
        self.lifelong_knowledge = self.lifelong_knowledge.advance_generation().consolidate()

    def restructure_knowledge(
        self,
        signatures: Iterable[PredictionSignature],
    ) -> tuple[RestructuredConcept, ...]:
        """Discover higher abstractions among behaviorally redundant concepts."""
        abstractions = OntologyRestructurer().restructure(signatures)
        for abstraction in abstractions:
            member_ids = {item.concept_id for item in self.lifelong_knowledge.items}
            if set(abstraction.member_ids).issubset(member_ids):
                self.lifelong_knowledge = OntologyRestructurer().apply_to_store(
                    self.lifelong_knowledge, abstraction
                )
        return abstractions

    def choose_self_directed_curriculum(
        self,
        *,
        uncertainty: dict[str, float] | None = None,
        opportunity: dict[str, float] | None = None,
    ) -> CurriculumChoice:
        """Choose what measured capability to practice next."""
        return SelfDirectedCurriculum().choose(
            self_model=self.self_model,
            uncertainty=uncertainty,
            opportunity=opportunity,
        )

    def discover_causality(
        self, observations: Iterable[CausalObservation]
    ) -> CausalDiscoveryReport:
        """Separate intervention effects from observational association."""
        return CausalDiscoveryEngine().discover(observations)

    def choose_active_perception(
        self,
        *,
        priors: Iterable[float],
        probes: Iterable[PerceptionProbe],
    ) -> ProbeChoice:
        """Choose the next observation by expected information gain."""
        return ActivePerceptionPlanner().choose(priors=priors, probes=probes)

    def imagine_counterfactuals(
        self,
        *,
        initial_state: int,
        actions: Iterable[CounterfactualAction],
        depth: int = 3,
        max_branches: int = 256,
    ) -> tuple[ImaginedBranch, ...]:
        """Simulate branching futures without changing the outside world."""
        return CounterfactualSimulator().imagine(
            initial_state=initial_state,
            actions=actions,
            depth=depth,
            max_branches=max_branches,
        )

    def ground_raw_signal(self, signal: RawSignal) -> GroundedSignal:
        """Derive unsupervised features/events from a raw numeric stream."""
        return RawSignalGrounder().ground(signal)

    def forge_tool(
        self,
        *,
        action: ConstructedAction,
        primitives: Iterable[ActionPrimitive],
        validation_cases: Iterable[ToolValidationCase],
    ) -> ForgedTool:
        """Promote a constructed procedure into a reusable tool after held-out tests."""
        return ToolForge().forge(
            action=action,
            primitives=primitives,
            validation_cases=validation_cases,
        )

    def pursue_long_horizon(
        self,
        *,
        initial_state: int,
        goal_test: Callable[[int], bool],
        actions: Iterable[HorizonAction],
        max_steps: int = 32,
        max_plan_depth: int = 12,
    ) -> LongHorizonResult:
        """Pursue a multi-stage objective and replan when observed reality disagrees."""
        return LongHorizonController().pursue(
            initial_state=initial_state,
            goal_test=goal_test,
            actions=actions,
            max_steps=max_steps,
            max_plan_depth=max_plan_depth,
        )

    def detect_unknown_unknowns(
        self, residuals: Iterable[PredictionResidual]
    ) -> UnknownUnknownSignal:
        """Detect clustered high-confidence failures suggesting missing concepts."""
        return UnknownUnknownDetector().detect(residuals)

    def allocate_search_budget(
        self,
        trials: Iterable[SearchOperatorTrial],
        *,
        total_budget: int,
    ) -> SearchBudgetAllocation:
        """Learn which search operators deserve finite compute."""
        return AdaptiveSearchPolicy().allocate(trials, total_budget=total_budget)

    def meta_learn_strategy(
        self,
        trials: Iterable[LearningStrategyTrial],
        *,
        task_family: str,
        default_strategy_id: str,
    ) -> MetaLearningDecision:
        """Use prior learning outcomes to change the strategy used on later tasks."""
        return MetaLearningController().select(
            trials,
            task_family=task_family,
            default_strategy_id=default_strategy_id,
        )

    def diagnose_self(
        self, observations: Iterable[FailureObservation]
    ) -> tuple[SelfDiagnosticReport, ...]:
        """Measure blind spots where confidence exceeds actual performance."""
        return SelfDiagnostic().diagnose(observations)

    def propose_measured_self_improvement(
        self,
        *,
        target_capability: str,
        description: str,
        benchmarks: Iterable[ImprovementBenchmark],
    ) -> SelfImprovementResult:
        """Propose a benchmarked internal improvement without self-authorizing adoption."""
        return SelfImprovementLab().propose(
            self_model=self.self_model,
            target_capability=target_capability,
            description=description,
            benchmarks=benchmarks,
        )

    def resolve_goal_conflict(
        self,
        goals: Iterable[GoalSpec],
        *,
        evidence: Iterable[GoalEvidence],
    ) -> GoalResolution:
        """Resolve conflicting goals from current evidence rather than static priority alone."""
        return GoalArbiter().resolve(goals, evidence=evidence)

    def revise_goals_from_evidence(self, evidence: Iterable[GoalEvidence]) -> None:
        """Abandon self-generated goals whose premises or utility collapse."""
        self.goals = GoalRevisionEngine().revise(self.goals, evidence=evidence)

    def learn_structural_rule(
        self,
        *,
        examples: Iterable[tuple[object, object]],
        adapter: DomainAdapter,
    ) -> AbstractTransitionRule:
        """Learn a domain-neutral structural relation for later cross-domain transfer."""
        return StructuralAnalogyEngine().learn_affine(examples=examples, adapter=adapter)

    def run_recursive_bootstrap(
        self,
        *,
        representation_training: Iterable[RepresentationObservation],
        representation_holdout: Iterable[RepresentationObservation],
        initial_state: int,
        primitives: Iterable[ActionPrimitive],
        known_states: Iterable[int],
        tool_validation_cases: Iterable[ToolValidationCase],
        residuals: Iterable[PredictionResidual] = (),
        second_representation_training: Iterable[RepresentationObservation] = (),
        second_representation_holdout: Iterable[RepresentationObservation] = (),
        max_goal_depth: int = 4,
    ) -> RecursiveBootstrapReport:
        """Run a closed discover→goal→act→tool→rediscover cognitive bootstrapping cycle."""
        report = RecursiveCognitionEngine().bootstrap(
            representation_training=representation_training,
            representation_holdout=representation_holdout,
            initial_state=initial_state,
            primitives=primitives,
            known_states=known_states,
            tool_validation_cases=tool_validation_cases,
            residuals=residuals,
            second_representation_training=second_representation_training,
            second_representation_holdout=second_representation_holdout,
            max_goal_depth=max_goal_depth,
        )
        self.lifelong_knowledge = report.knowledge_store
        return report

    def blind_external_evaluation(
        self,
        *,
        challenges: Iterable[BlindChallenge],
        agent: Callable[[tuple[int, ...]], int],
        commitments: Iterable[DigestRecord] | None = None,
    ) -> BlindEvaluationResult:
        """Run nonce-bound blind challenges supplied by an evaluator."""
        return BlindEvaluatorHarness().evaluate(
            challenges=challenges, agent=agent, commitments=commitments
        )

    def invent_compositional_representation(
        self,
        *,
        observations: Iterable[RepresentationObservation],
        max_depth: int = 2,
        max_candidates: int = 4096,
        minimum_improvement: float = 0.15,
    ) -> InventedRepresentationProgram:
        """Synthesize a multi-operation representation when shallow feature languages fail."""
        return RepresentationProgramInventor().invent(
            observations=observations,
            max_depth=max_depth,
            max_candidates=max_candidates,
            minimum_improvement=minimum_improvement,
        )

    def validate_compositional_representation(
        self,
        representation: InventedRepresentationProgram,
        *,
        observations: Iterable[RepresentationObservation],
    ) -> InventedRepresentationProgram:
        """Reality-test a synthesized representation on held-out evidence."""
        return RepresentationProgramInventor().validate(representation, observations=observations)

    def maintain_lifelong_knowledge(
        self,
        *,
        evidence: Iterable[ContextualKnowledgeEvidence],
    ) -> KnowledgeMaintenanceReport:
        """Split over-broad concepts or retire contradicted low-value knowledge."""
        report = KnowledgeMaintenanceEngine().reconcile(self.lifelong_knowledge, evidence=evidence)
        self.lifelong_knowledge = report.store
        return report

    def meta_choose_strategy(
        self,
        *,
        fingerprint: TaskFingerprint,
        candidate_strategies: Iterable[str],
    ) -> OnlineMetaDecision:
        """Choose a learning strategy using persistent cross-episode evidence."""
        return self.online_meta_profile.choose(
            fingerprint=fingerprint,
            candidate_strategies=candidate_strategies,
        )

    def run_lifetime_learning(
        self,
        *,
        challenges: Iterable[LifetimeChallenge],
        exploration_episodes: int = 2,
    ) -> LifetimeLearningReport:
        """Learn across multiple worlds and retain evidence about how Sally learns best."""
        report = LifetimeLearningEngine().run_lifetime(
            profile=self.online_meta_profile,
            challenges=challenges,
            exploration_episodes=exploration_episodes,
        )
        self.online_meta_profile = report.profile
        for episode in report.episodes:
            concept_id = f"lifetime-{episode.challenge_id}-{episode.concept_digest.value[:12]}"
            self.lifelong_knowledge = self.lifelong_knowledge.integrate(
                KnowledgeItem(
                    concept_id=concept_id,
                    content_digest=episode.concept_digest,
                    confidence=episode.validation_accuracy,
                    utility=episode.effective_score,
                )
            )
        return report

    def learn_relational_schema(
        self,
        *,
        world: RelationalWorld,
        effective_node: str,
    ) -> LearnedStructuralSchema:
        """Learn a surface-independent causal/topological role from one domain."""
        return RelationalTransferEngine().learn(world=world, effective_node=effective_node)

    def transfer_relational_schema(
        self,
        schema: LearnedStructuralSchema,
        *,
        world: RelationalWorld,
    ) -> TransferInference:
        """Reuse a learned role in a surface-different domain by structure alone."""
        return RelationalTransferEngine().transfer(schema, world=world)

    def ground_text_outcomes(
        self,
        observations: Iterable[TextOutcomeObservation],
    ) -> tuple[GroundedTextFeature, ...]:
        """Discover outcome-linked latent features directly from raw text strings."""
        return TextOutcomeGrounder().discover(observations)

    def allocate_goal_portfolio(
        self,
        *,
        goals: Iterable[GoalSpec],
        evidence: Iterable[GoalEvidence],
        attention_budget: float = 1.0,
        per_goal_cost: dict[str, float] | None = None,
    ) -> GoalPortfolioDecision:
        """Maintain coherent attention across multiple evolving goals."""
        return GoalPortfolioManager().allocate(
            goals,
            evidence=evidence,
            attention_budget=attention_budget,
            per_goal_cost=per_goal_cost,
        )

    def register_action(self, action: ActionSpec) -> None:
        """Add one unique declarative planning action."""
        if any(existing.action_id == action.action_id for existing in self.action_catalog):
            raise FoundationError(f"planning action already exists: {action.action_id.value}")
        self.action_catalog = tuple(
            sorted((*self.action_catalog, action), key=lambda item: item.action_id.value)
        )

    def plan(self, goal: FactPattern) -> Plan:
        """Build a bounded deterministic plan against the current world model."""
        return DeterministicPlanner().plan(
            world_model=self.world_model,
            actions=self.action_catalog,
            goal=goal,
        )

    def simulate_plan(
        self,
        plan: Plan,
        *,
        human_approved: bool = False,
        retain_simulation: bool = False,
    ) -> PlanExecutionReceipt:
        """Simulate plan effects and optionally retain the hypothetical branch."""
        receipt = PlanSimulator().execute(
            plan,
            world_model=self.world_model,
            human_approved=human_approved,
        )
        if retain_simulation and receipt.permission.value == "allowed":
            self.world_model = receipt.resulting_model
        return receipt

    def record_learning(self, outcome: LearningOutcome) -> None:
        """Record one evidence-bound learning outcome."""
        self.learning = self.learning.record(outcome)

    def measure_capability(self, measure: CapabilityMeasure) -> None:
        """Update the evidence-bound self model."""
        self.self_model = self.self_model.update(measure)

    def register_goal(self, goal: GoalSpec) -> None:
        """Add one unique bounded goal."""
        self.goals = self.goals.add(goal)

    def update_goal_status(
        self,
        goal_id: str,
        status: GoalStatus,
        *,
        reason: str | None = None,
    ) -> None:
        """Record one explicit goal lifecycle transition."""
        self.goals = self.goals.update_status(goal_id, status, reason=reason)

    def record_calibration(self, observation: CalibrationObservation) -> None:
        """Append one forecast/outcome pair to the uncertainty ledger."""
        self.uncertainty = self.uncertainty.record(observation)

    def calibration_report(
        self,
        *,
        capability_id: str | None = None,
        bin_count: int = 10,
    ) -> CalibrationReport:
        """Return transparent confidence calibration metrics."""
        return self.uncertainty.report(
            capability_id=capability_id,
            bin_count=bin_count,
        )

    def set_curriculum(self, curriculum: CurriculumLedger) -> None:
        """Install one explicit curriculum ledger."""
        self.curriculum = curriculum

    def record_curriculum_trial(self, trial: CurriculumTrial) -> None:
        """Append one observed curriculum trial."""
        if self.curriculum is None:
            raise FoundationError("cannot record a trial without a curriculum")
        self.curriculum = self.curriculum.record(trial)

    def deliberate(
        self,
        *,
        task: str,
        use_calibration_gate: bool = True,
    ) -> ExecutiveDecision:
        """Produce one bounded executive decision without executing it."""
        calibration = self.uncertainty.report() if use_calibration_gate else None
        return ExecutiveController().deliberate(
            task=task,
            goals=self.goals,
            workspace=self.workspace,
            memory=self.active_memory,
            world_model=self.world_model,
            actions=self.action_catalog,
            calibration=calibration,
        )

    def bridge_decision(
        self,
        decision: ExecutiveDecision,
        *,
        cycle: int,
    ) -> CognitiveProposalBridgeResult:
        """Convert a plan proposal into the existing IX-Sally control plane."""
        return CognitiveProposalBridge().bridge(decision=decision, cycle=cycle)

    def append_episode(self, episode: CognitiveEpisode) -> None:
        """Append one fully linked replayable cognitive episode."""
        self.episodes = self.episodes.append(episode)

    def run_cycle(
        self,
        *,
        task: str,
        goal: FactPattern | None = None,
    ) -> NinefoldCognitiveCycle:
        """Run one complete functional ninefold cognitive cycle."""
        cycle = NinefoldCoordinator().run(
            task=task,
            workspace=self.workspace,
            memory=self.active_memory,
            world_model=self.world_model,
            learning=self.learning,
            actions=self.action_catalog,
            goal=goal,
        )
        self.cycle_count += 1
        return cycle

    def state_payload(self) -> JsonObject:
        """Return a complete canonical state representation."""
        runtime_memories: JsonArray = [
            {"name": name, "value": value.to_payload()}
            for name, value in sorted(self.runtime_memories.items())
        ]
        actions: JsonArray = [action.to_payload() for action in self.action_catalog]
        return {
            "repository": "IX-Sally",
            "workspace": self.workspace.to_payload(),
            "active_memory": self.active_memory.to_payload(),
            "world_model": self.world_model.to_payload(),
            "action_catalog": actions,
            "learning": self.learning.to_payload(),
            "self_model": self.self_model.to_payload(),
            "goals": self.goals.to_payload(),
            "uncertainty": self.uncertainty.to_payload(),
            "episodes": self.episodes.to_payload(),
            "curriculum": (self.curriculum.to_payload() if self.curriculum is not None else None),
            "primitive_registry": self.primitive_registry.to_payload(),
            "lifelong_knowledge": self.lifelong_knowledge.to_payload(),
            "online_meta_profile": self.online_meta_profile.to_payload(),
            "runtime_memories": runtime_memories,
            "execution_count": self.execution_count,
            "cycle_count": self.cycle_count,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic identity for the complete cognitive state."""
        return DigestRecord.from_payload(self.state_payload())

    def snapshot(self) -> CognitiveSnapshot:
        """Return a tamper-evident complete state snapshot."""
        return CognitiveSnapshot.create(self.state_payload())
