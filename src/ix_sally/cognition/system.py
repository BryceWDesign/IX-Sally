"""Integrated IX-Sally experimental general-intelligence research runtime."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ix_sally.cognition.active_memory import (
    ActiveMemoryEntry,
    ActiveMemoryStore,
)
from ix_sally.cognition.compiler import compile_ix_source
from ix_sally.cognition.curriculum import CurriculumLedger, CurriculumTrial
from ix_sally.cognition.episodes import CognitiveEpisode, EpisodeLedger
from ix_sally.cognition.executive import ExecutiveController, ExecutiveDecision
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.governance_bridge import (
    CognitiveProposalBridge,
    CognitiveProposalBridgeResult,
)
from ix_sally.cognition.learning import LearningLedger, LearningOutcome
from ix_sally.cognition.metacognition import CapabilityMeasure, SelfModel
from ix_sally.cognition.ninefold import NinefoldCognitiveCycle, NinefoldCoordinator
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
from ix_sally.cognition.uncertainty import (
    CalibrationObservation,
    CalibrationReport,
    UncertaintyLedger,
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
