"""IX-Sally governed autonomy habitat package."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ix_sally.actions import ActionStatus, BoundedActionLedger, BoundedActionRecord
    from ix_sally.agents import (
        AgentRole,
        AgentRoleDefinition,
        AgentRoleRegistry,
        default_agent_role_registry,
    )
    from ix_sally.artifacts import AgentArtifact, AgentArtifactKind, AgentArtifactLedger
    from ix_sally.authorization import (
        AuthorityDecision,
        AuthorityDecisionLedger,
        AuthorityDecisionStatus,
        AuthorityRequest,
        decide_authority_request,
    )
    from ix_sally.authority_processing import (
        AuthorityBatchProcessingResult,
        AuthorityProcessingResult,
        AuthorityProcessor,
    )
    from ix_sally.boundaries import BoundaryFinding, BoundarySeverity, SentinelBoundaryReport
    from ix_sally.chamber import ObservationChamberConfig, StopCondition, StopReason
    from ix_sally.chamber_closing import ChamberCloseResult, ChamberCloseStatus, ChamberCloser
    from ix_sally.claims import ClaimLedger, ClaimRecord, ClaimStatus
    from ix_sally.contracts import AutonomyContract, AutonomyMode
    from ix_sally.cycles import CycleCoordinationStatus, NinefoldCycleLedger, NinefoldCyclePacket
    from ix_sally.digest import DigestRecord
    from ix_sally.dockets import ClerkDocketEntry, ClerkDocketPacket, DocketEntryKind
    from ix_sally.doctrine import DoctrineCatalog, DoctrineRule, DoctrineSeverity
    from ix_sally.events import RuntimeEvent, RuntimeEventType, RuntimeTranscript
    from ix_sally.evidence import EvidenceKind, EvidenceLedger, EvidenceRecord, EvidenceStatus
    from ix_sally.evidence_support import (
        EvidenceSupportFinding,
        EvidenceSupportLedger,
        EvidenceSupportStatus,
        VerityEvidenceSupportReview,
    )
    from ix_sally.evidence_support_processing import (
        EvidenceSupportBatchProcessingResult,
        EvidenceSupportProcessingResult,
        EvidenceSupportProcessor,
    )
    from ix_sally.execution_dispatch import (
        ExecutionDispatchBatchResult,
        ExecutionDispatchResult,
        ExecutionDispatcher,
    )
    from ix_sally.execution_planning import ExecutionPlanner, ExecutionPlanningResult
    from ix_sally.execution_queue import ExecutionQueue, ExecutionQueueItem, ExecutionQueueStatus
    from ix_sally.executions import ExecutionStatus, ForgeExecutionPacket, ForgeExecutionReceipt
    from ix_sally.falsifications import (
        ButchFalsificationPacket,
        FalsificationFinding,
        FalsificationSeverity,
    )
    from ix_sally.forge_evidence import (
        ForgeEvidenceAdapter,
        ForgeEvidenceProcessingResult,
        ForgeEvidenceRecord,
    )
    from ix_sally.forge_result_processing import (
        ForgeResultBatchProcessingResult,
        ForgeResultProcessingResult,
        ForgeResultProcessor,
    )
    from ix_sally.forge_results import ForgeResultLedger, ForgeResultRecord, ForgeResultStatus
    from ix_sally.foundation import CanonicalKey, FoundationError
    from ix_sally.judgments import (
        EvidenceJudgmentStatus,
        VerityEvidenceJudgment,
        VerityJudgmentPacket,
    )
    from ix_sally.jurisdiction import JurisdictionDecision, JurisdictionGate, JurisdictionStatus
    from ix_sally.memory import MemoryLedger, MemoryRecord, MemoryStatus
    from ix_sally.memory_decisions import (
        MemoryDecisionAction,
        MnemosyneMemoryDecision,
        MnemosyneMemoryDecisionPacket,
    )
    from ix_sally.predictions import OraclePrediction, OraclePredictionPacket, PredictionStatus
    from ix_sally.proposal_intake import SallyProposalIntake, SallyProposalIntakeResult
    from ix_sally.proposals import ProposalAction, SallyProposalPacket
    from ix_sally.recording import StateRecorder
    from ix_sally.runtime import NinefoldRuntimeKit
    from ix_sally.session_baseline import (
        session_one_baseline_digest,
        session_one_baseline_payload,
        session_one_contract,
        session_one_runtime_kit,
    )
    from ix_sally.state import NinefoldRunState
    from ix_sally.state_audit import (
        StateAuditFinding,
        StateAuditReport,
        StateAuditSeverity,
        StateAuditor,
    )
    from ix_sally.transfer import TransferStatus, TransferTrial, TransferTrialPacket

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ActionStatus",
    "AgentArtifact",
    "AgentArtifactKind",
    "AgentArtifactLedger",
    "AgentRole",
    "AgentRoleDefinition",
    "AgentRoleRegistry",
    "AuthorityBatchProcessingResult",
    "AuthorityDecision",
    "AuthorityDecisionLedger",
    "AuthorityDecisionStatus",
    "AuthorityProcessingResult",
    "AuthorityProcessor",
    "AuthorityRequest",
    "AutonomyContract",
    "AutonomyMode",
    "BoundaryFinding",
    "BoundarySeverity",
    "BoundedActionLedger",
    "BoundedActionRecord",
    "ButchFalsificationPacket",
    "CanonicalKey",
    "ChamberCloseResult",
    "ChamberCloseStatus",
    "ChamberCloser",
    "ClaimLedger",
    "ClaimRecord",
    "ClaimStatus",
    "ClerkDocketEntry",
    "ClerkDocketPacket",
    "CycleCoordinationStatus",
    "DigestRecord",
    "DocketEntryKind",
    "DoctrineCatalog",
    "DoctrineRule",
    "DoctrineSeverity",
    "EvidenceJudgmentStatus",
    "EvidenceKind",
    "EvidenceLedger",
    "EvidenceRecord",
    "EvidenceStatus",
    "EvidenceSupportBatchProcessingResult",
    "EvidenceSupportFinding",
    "EvidenceSupportLedger",
    "EvidenceSupportProcessingResult",
    "EvidenceSupportProcessor",
    "EvidenceSupportStatus",
    "ExecutionDispatchBatchResult",
    "ExecutionDispatchResult",
    "ExecutionDispatcher",
    "ExecutionPlanner",
    "ExecutionPlanningResult",
    "ExecutionQueue",
    "ExecutionQueueItem",
    "ExecutionQueueStatus",
    "ExecutionStatus",
    "FalsificationFinding",
    "FalsificationSeverity",
    "ForgeEvidenceAdapter",
    "ForgeEvidenceProcessingResult",
    "ForgeEvidenceRecord",
    "ForgeExecutionPacket",
    "ForgeExecutionReceipt",
    "ForgeResultBatchProcessingResult",
    "ForgeResultLedger",
    "ForgeResultProcessingResult",
    "ForgeResultProcessor",
    "ForgeResultRecord",
    "ForgeResultStatus",
    "FoundationError",
    "JurisdictionDecision",
    "JurisdictionGate",
    "JurisdictionStatus",
    "MemoryDecisionAction",
    "MemoryLedger",
    "MemoryRecord",
    "MemoryStatus",
    "MnemosyneMemoryDecision",
    "MnemosyneMemoryDecisionPacket",
    "NinefoldCycleLedger",
    "NinefoldCyclePacket",
    "NinefoldRunState",
    "NinefoldRuntimeKit",
    "ObservationChamberConfig",
    "OraclePrediction",
    "OraclePredictionPacket",
    "PredictionStatus",
    "ProposalAction",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeTranscript",
    "SallyProposalIntake",
    "SallyProposalIntakeResult",
    "SallyProposalPacket",
    "SentinelBoundaryReport",
    "StateAuditFinding",
    "StateAuditReport",
    "StateAuditSeverity",
    "StateAuditor",
    "StateRecorder",
    "StopCondition",
    "StopReason",
    "TransferStatus",
    "TransferTrial",
    "TransferTrialPacket",
    "VerityEvidenceJudgment",
    "VerityEvidenceSupportReview",
    "VerityJudgmentPacket",
    "decide_authority_request",
    "default_agent_role_registry",
    "session_one_baseline_digest",
    "session_one_baseline_payload",
    "session_one_contract",
    "session_one_runtime_kit",
]

_LAZY_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "ActionStatus": ("ix_sally.actions", "ActionStatus"),
    "AgentArtifact": ("ix_sally.artifacts", "AgentArtifact"),
    "AgentArtifactKind": ("ix_sally.artifacts", "AgentArtifactKind"),
    "AgentArtifactLedger": ("ix_sally.artifacts", "AgentArtifactLedger"),
    "AgentRole": ("ix_sally.agents", "AgentRole"),
    "AgentRoleDefinition": ("ix_sally.agents", "AgentRoleDefinition"),
    "AgentRoleRegistry": ("ix_sally.agents", "AgentRoleRegistry"),
    "AuthorityBatchProcessingResult": (
        "ix_sally.authority_processing",
        "AuthorityBatchProcessingResult",
    ),
    "AuthorityDecision": ("ix_sally.authorization", "AuthorityDecision"),
    "AuthorityDecisionLedger": ("ix_sally.authorization", "AuthorityDecisionLedger"),
    "AuthorityDecisionStatus": ("ix_sally.authorization", "AuthorityDecisionStatus"),
    "AuthorityProcessingResult": (
        "ix_sally.authority_processing",
        "AuthorityProcessingResult",
    ),
    "AuthorityProcessor": ("ix_sally.authority_processing", "AuthorityProcessor"),
    "AuthorityRequest": ("ix_sally.authorization", "AuthorityRequest"),
    "AutonomyContract": ("ix_sally.contracts", "AutonomyContract"),
    "AutonomyMode": ("ix_sally.contracts", "AutonomyMode"),
    "BoundaryFinding": ("ix_sally.boundaries", "BoundaryFinding"),
    "BoundarySeverity": ("ix_sally.boundaries", "BoundarySeverity"),
    "BoundedActionLedger": ("ix_sally.actions", "BoundedActionLedger"),
    "BoundedActionRecord": ("ix_sally.actions", "BoundedActionRecord"),
    "ButchFalsificationPacket": (
        "ix_sally.falsifications",
        "ButchFalsificationPacket",
    ),
    "CanonicalKey": ("ix_sally.foundation", "CanonicalKey"),
    "ChamberCloseResult": ("ix_sally.chamber_closing", "ChamberCloseResult"),
    "ChamberCloseStatus": ("ix_sally.chamber_closing", "ChamberCloseStatus"),
    "ChamberCloser": ("ix_sally.chamber_closing", "ChamberCloser"),
    "ClaimLedger": ("ix_sally.claims", "ClaimLedger"),
    "ClaimRecord": ("ix_sally.claims", "ClaimRecord"),
    "ClaimStatus": ("ix_sally.claims", "ClaimStatus"),
    "ClerkDocketEntry": ("ix_sally.dockets", "ClerkDocketEntry"),
    "ClerkDocketPacket": ("ix_sally.dockets", "ClerkDocketPacket"),
    "CycleCoordinationStatus": ("ix_sally.cycles", "CycleCoordinationStatus"),
    "DigestRecord": ("ix_sally.digest", "DigestRecord"),
    "DocketEntryKind": ("ix_sally.dockets", "DocketEntryKind"),
    "DoctrineCatalog": ("ix_sally.doctrine", "DoctrineCatalog"),
    "DoctrineRule": ("ix_sally.doctrine", "DoctrineRule"),
    "DoctrineSeverity": ("ix_sally.doctrine", "DoctrineSeverity"),
    "EvidenceJudgmentStatus": ("ix_sally.judgments", "EvidenceJudgmentStatus"),
    "EvidenceKind": ("ix_sally.evidence", "EvidenceKind"),
    "EvidenceLedger": ("ix_sally.evidence", "EvidenceLedger"),
    "EvidenceRecord": ("ix_sally.evidence", "EvidenceRecord"),
    "EvidenceStatus": ("ix_sally.evidence", "EvidenceStatus"),
    "EvidenceSupportBatchProcessingResult": (
        "ix_sally.evidence_support_processing",
        "EvidenceSupportBatchProcessingResult",
    ),
    "EvidenceSupportFinding": (
        "ix_sally.evidence_support",
        "EvidenceSupportFinding",
    ),
    "EvidenceSupportLedger": (
        "ix_sally.evidence_support",
        "EvidenceSupportLedger",
    ),
    "EvidenceSupportProcessingResult": (
        "ix_sally.evidence_support_processing",
        "EvidenceSupportProcessingResult",
    ),
    "EvidenceSupportProcessor": (
        "ix_sally.evidence_support_processing",
        "EvidenceSupportProcessor",
    ),
    "EvidenceSupportStatus": (
        "ix_sally.evidence_support",
        "EvidenceSupportStatus",
    ),
    "ExecutionDispatchBatchResult": (
        "ix_sally.execution_dispatch",
        "ExecutionDispatchBatchResult",
    ),
    "ExecutionDispatchResult": (
        "ix_sally.execution_dispatch",
        "ExecutionDispatchResult",
    ),
    "ExecutionDispatcher": ("ix_sally.execution_dispatch", "ExecutionDispatcher"),
    "ExecutionPlanner": ("ix_sally.execution_planning", "ExecutionPlanner"),
    "ExecutionPlanningResult": (
        "ix_sally.execution_planning",
        "ExecutionPlanningResult",
    ),
    "ExecutionQueue": ("ix_sally.execution_queue", "ExecutionQueue"),
    "ExecutionQueueItem": ("ix_sally.execution_queue", "ExecutionQueueItem"),
    "ExecutionQueueStatus": ("ix_sally.execution_queue", "ExecutionQueueStatus"),
    "ExecutionStatus": ("ix_sally.executions", "ExecutionStatus"),
    "FalsificationFinding": (
        "ix_sally.falsifications",
        "FalsificationFinding",
    ),
    "FalsificationSeverity": (
        "ix_sally.falsifications",
        "FalsificationSeverity",
    ),
    "ForgeEvidenceAdapter": ("ix_sally.forge_evidence", "ForgeEvidenceAdapter"),
    "ForgeEvidenceProcessingResult": (
        "ix_sally.forge_evidence",
        "ForgeEvidenceProcessingResult",
    ),
    "ForgeEvidenceRecord": ("ix_sally.forge_evidence", "ForgeEvidenceRecord"),
    "ForgeExecutionPacket": ("ix_sally.executions", "ForgeExecutionPacket"),
    "ForgeExecutionReceipt": ("ix_sally.executions", "ForgeExecutionReceipt"),
    "ForgeResultBatchProcessingResult": (
        "ix_sally.forge_result_processing",
        "ForgeResultBatchProcessingResult",
    ),
    "ForgeResultLedger": ("ix_sally.forge_results", "ForgeResultLedger"),
    "ForgeResultProcessingResult": (
        "ix_sally.forge_result_processing",
        "ForgeResultProcessingResult",
    ),
    "ForgeResultProcessor": (
        "ix_sally.forge_result_processing",
        "ForgeResultProcessor",
    ),
    "ForgeResultRecord": ("ix_sally.forge_results", "ForgeResultRecord"),
    "ForgeResultStatus": ("ix_sally.forge_results", "ForgeResultStatus"),
    "FoundationError": ("ix_sally.foundation", "FoundationError"),
    "JurisdictionDecision": ("ix_sally.jurisdiction", "JurisdictionDecision"),
    "JurisdictionGate": ("ix_sally.jurisdiction", "JurisdictionGate"),
    "JurisdictionStatus": ("ix_sally.jurisdiction", "JurisdictionStatus"),
    "MemoryDecisionAction": ("ix_sally.memory_decisions", "MemoryDecisionAction"),
    "MemoryLedger": ("ix_sally.memory", "MemoryLedger"),
    "MemoryRecord": ("ix_sally.memory", "MemoryRecord"),
    "MemoryStatus": ("ix_sally.memory", "MemoryStatus"),
    "MnemosyneMemoryDecision": (
        "ix_sally.memory_decisions",
        "MnemosyneMemoryDecision",
    ),
    "MnemosyneMemoryDecisionPacket": (
        "ix_sally.memory_decisions",
        "MnemosyneMemoryDecisionPacket",
    ),
    "NinefoldCycleLedger": ("ix_sally.cycles", "NinefoldCycleLedger"),
    "NinefoldCyclePacket": ("ix_sally.cycles", "NinefoldCyclePacket"),
    "NinefoldRunState": ("ix_sally.state", "NinefoldRunState"),
    "NinefoldRuntimeKit": ("ix_sally.runtime", "NinefoldRuntimeKit"),
    "ObservationChamberConfig": (
        "ix_sally.chamber",
        "ObservationChamberConfig",
    ),
    "OraclePrediction": ("ix_sally.predictions", "OraclePrediction"),
    "OraclePredictionPacket": (
        "ix_sally.predictions",
        "OraclePredictionPacket",
    ),
    "PredictionStatus": ("ix_sally.predictions", "PredictionStatus"),
    "ProposalAction": ("ix_sally.proposals", "ProposalAction"),
    "RuntimeEvent": ("ix_sally.events", "RuntimeEvent"),
    "RuntimeEventType": ("ix_sally.events", "RuntimeEventType"),
    "RuntimeTranscript": ("ix_sally.events", "RuntimeTranscript"),
    "SallyProposalIntake": ("ix_sally.proposal_intake", "SallyProposalIntake"),
    "SallyProposalIntakeResult": (
        "ix_sally.proposal_intake",
        "SallyProposalIntakeResult",
    ),
    "SallyProposalPacket": ("ix_sally.proposals", "SallyProposalPacket"),
    "SentinelBoundaryReport": (
        "ix_sally.boundaries",
        "SentinelBoundaryReport",
    ),
    "StateAuditFinding": ("ix_sally.state_audit", "StateAuditFinding"),
    "StateAuditReport": ("ix_sally.state_audit", "StateAuditReport"),
    "StateAuditSeverity": ("ix_sally.state_audit", "StateAuditSeverity"),
    "StateAuditor": ("ix_sally.state_audit", "StateAuditor"),
    "StateRecorder": ("ix_sally.recording", "StateRecorder"),
    "StopCondition": ("ix_sally.chamber", "StopCondition"),
    "StopReason": ("ix_sally.chamber", "StopReason"),
    "TransferStatus": ("ix_sally.transfer", "TransferStatus"),
    "TransferTrial": ("ix_sally.transfer", "TransferTrial"),
    "TransferTrialPacket": ("ix_sally.transfer", "TransferTrialPacket"),
    "VerityEvidenceJudgment": (
        "ix_sally.judgments",
        "VerityEvidenceJudgment",
    ),
    "VerityEvidenceSupportReview": (
        "ix_sally.evidence_support",
        "VerityEvidenceSupportReview",
    ),
    "VerityJudgmentPacket": (
        "ix_sally.judgments",
        "VerityJudgmentPacket",
    ),
    "decide_authority_request": (
        "ix_sally.authorization",
        "decide_authority_request",
    ),
    "default_agent_role_registry": (
        "ix_sally.agents",
        "default_agent_role_registry",
    ),
    "session_one_baseline_digest": (
        "ix_sally.session_baseline",
        "session_one_baseline_digest",
    ),
    "session_one_baseline_payload": (
        "ix_sally.session_baseline",
        "session_one_baseline_payload",
    ),
    "session_one_contract": (
        "ix_sally.session_baseline",
        "session_one_contract",
    ),
    "session_one_runtime_kit": (
        "ix_sally.session_baseline",
        "session_one_runtime_kit",
    ),
}


def __getattr__(name: str) -> object:
    """Load a public package export only when it is first requested."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return package globals and lazy public exports for introspection."""
    return sorted(set(globals()) | set(__all__))
