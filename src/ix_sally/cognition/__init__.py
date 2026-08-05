"""Integrated cognitive architecture for the IX-Sally research runtime."""

from ix_sally.cognition.active_memory import (
    ActiveMemoryEntry,
    ActiveMemoryStatus,
    ActiveMemoryStore,
    MemoryLayer,
    MemoryRetrieval,
)
from ix_sally.cognition.adaptation import (
    AdaptationController,
    RegressionFinding,
    RegressionOutcome,
    RegressionReport,
)
from ix_sally.cognition.bytecode import BytecodeProgram, Instruction, OpCode
from ix_sally.cognition.compiler import IXCompiler, compile_ix_source
from ix_sally.cognition.curriculum import (
    Curriculum,
    CurriculumLedger,
    CurriculumSplit,
    CurriculumTask,
    CurriculumTrial,
    TrialStatus,
)
from ix_sally.cognition.episodes import (
    CognitiveEpisode,
    EpisodeLedger,
    EpisodeStep,
    EpisodeStepKind,
    EpisodeStepStatus,
)
from ix_sally.cognition.evaluation import (
    BenchmarkResult,
    CognitiveEvaluationReport,
    EvaluationCategory,
    run_core_evaluation,
)
from ix_sally.cognition.executive import (
    ExecutiveController,
    ExecutiveDecision,
    ExecutiveDecisionStatus,
)
from ix_sally.cognition.goals import GoalGraph, GoalSpec, GoalStatus
from ix_sally.cognition.governance_bridge import (
    CognitiveProposalBridge,
    CognitiveProposalBridgeReceipt,
    CognitiveProposalBridgeResult,
)
from ix_sally.cognition.learning import (
    LearningLedger,
    LearningOutcome,
    OutcomeStatus,
    SkillProfile,
    TransferEvaluation,
)
from ix_sally.cognition.metacognition import (
    CapabilityMeasure,
    ImprovementProposal,
    ImprovementStatus,
    SelfModel,
)
from ix_sally.cognition.ninefold import (
    NinefoldCognitiveCycle,
    NinefoldCoordinator,
    RoleFinding,
)
from ix_sally.cognition.persistence import CognitiveSnapshot
from ix_sally.cognition.planning import (
    ActionSpec,
    DeterministicPlanner,
    ExecutionPermission,
    FactEffect,
    Plan,
    PlanExecutionReceipt,
    PlanSimulator,
    PlanStatus,
)
from ix_sally.cognition.primitives import (
    PrimitiveExecution,
    PrimitiveExecutor,
    PrimitiveKind,
    PrimitiveOperation,
    PrimitiveRegistry,
    PrimitiveSpec,
    PrimitiveStatus,
    default_primitive_registry,
)
from ix_sally.cognition.storage import (
    SnapshotLoadResult,
    SnapshotRepository,
    SnapshotSaveReceipt,
    SnapshotSource,
)
from ix_sally.cognition.system import SallyCognitiveSystem
from ix_sally.cognition.uncertainty import (
    CalibrationBin,
    CalibrationObservation,
    CalibrationReport,
    UncertaintyLedger,
)
from ix_sally.cognition.values import (
    CognitiveScalar,
    CognitiveValue,
    CognitiveValueType,
    value_from_payload,
)
from ix_sally.cognition.vm import IXVirtualMachine, VMResult, VMStatus, VMTraceEntry
from ix_sally.cognition.workspace import (
    CognitiveWorkspace,
    WorkspaceItem,
    WorkspaceItemKind,
    WorkspaceItemStatus,
)
from ix_sally.cognition.world_model import (
    CausalRule,
    FactPattern,
    FactStatus,
    WorldFact,
    WorldModel,
)

__all__ = [
    "ActionSpec",
    "ActiveMemoryEntry",
    "ActiveMemoryStatus",
    "ActiveMemoryStore",
    "AdaptationController",
    "BenchmarkResult",
    "BytecodeProgram",
    "CalibrationBin",
    "CalibrationObservation",
    "CalibrationReport",
    "CapabilityMeasure",
    "CausalRule",
    "CognitiveEpisode",
    "CognitiveEvaluationReport",
    "CognitiveProposalBridge",
    "CognitiveProposalBridgeReceipt",
    "CognitiveProposalBridgeResult",
    "CognitiveScalar",
    "CognitiveSnapshot",
    "CognitiveValue",
    "CognitiveValueType",
    "CognitiveWorkspace",
    "Curriculum",
    "CurriculumLedger",
    "CurriculumSplit",
    "CurriculumTask",
    "CurriculumTrial",
    "DeterministicPlanner",
    "EpisodeLedger",
    "EpisodeStep",
    "EpisodeStepKind",
    "EpisodeStepStatus",
    "EvaluationCategory",
    "ExecutionPermission",
    "ExecutiveController",
    "ExecutiveDecision",
    "ExecutiveDecisionStatus",
    "FactEffect",
    "FactPattern",
    "FactStatus",
    "GoalGraph",
    "GoalSpec",
    "GoalStatus",
    "IXCompiler",
    "IXVirtualMachine",
    "ImprovementProposal",
    "ImprovementStatus",
    "Instruction",
    "LearningLedger",
    "LearningOutcome",
    "MemoryLayer",
    "MemoryRetrieval",
    "NinefoldCognitiveCycle",
    "NinefoldCoordinator",
    "OpCode",
    "OutcomeStatus",
    "Plan",
    "PlanExecutionReceipt",
    "PlanSimulator",
    "PlanStatus",
    "PrimitiveExecution",
    "PrimitiveExecutor",
    "PrimitiveKind",
    "PrimitiveOperation",
    "PrimitiveRegistry",
    "PrimitiveSpec",
    "PrimitiveStatus",
    "RegressionFinding",
    "RegressionOutcome",
    "RegressionReport",
    "RoleFinding",
    "SallyCognitiveSystem",
    "SelfModel",
    "SkillProfile",
    "SnapshotLoadResult",
    "SnapshotRepository",
    "SnapshotSaveReceipt",
    "SnapshotSource",
    "TransferEvaluation",
    "TrialStatus",
    "UncertaintyLedger",
    "VMResult",
    "VMStatus",
    "VMTraceEntry",
    "WorkspaceItem",
    "WorkspaceItemKind",
    "WorkspaceItemStatus",
    "WorldFact",
    "WorldModel",
    "compile_ix_source",
    "default_primitive_registry",
    "run_core_evaluation",
    "value_from_payload",
]
