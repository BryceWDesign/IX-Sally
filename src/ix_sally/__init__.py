"""IX-Sally governed autonomy habitat package."""

from __future__ import annotations

from ix_sally.agents import (
    AgentRole,
    AgentRoleDefinition,
    AgentRoleRegistry,
    default_agent_role_registry,
)
from ix_sally.chamber import ObservationChamberConfig, StopCondition, StopReason
from ix_sally.claims import ClaimLedger, ClaimRecord, ClaimStatus
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.doctrine import DoctrineCatalog, DoctrineRule, DoctrineSeverity
from ix_sally.events import RuntimeEvent, RuntimeEventType, RuntimeTranscript
from ix_sally.evidence import EvidenceKind, EvidenceLedger, EvidenceRecord, EvidenceStatus
from ix_sally.foundation import CanonicalKey, FoundationError
from ix_sally.jurisdiction import JurisdictionDecision, JurisdictionGate, JurisdictionStatus

__all__ = [
    "__version__",
    "AgentRole",
    "AgentRoleDefinition",
    "AgentRoleRegistry",
    "AutonomyContract",
    "AutonomyMode",
    "CanonicalKey",
    "ClaimLedger",
    "ClaimRecord",
    "ClaimStatus",
    "DigestRecord",
    "DoctrineCatalog",
    "DoctrineRule",
    "DoctrineSeverity",
    "EvidenceKind",
    "EvidenceLedger",
    "EvidenceRecord",
    "EvidenceStatus",
    "FoundationError",
    "JurisdictionDecision",
    "JurisdictionGate",
    "JurisdictionStatus",
    "ObservationChamberConfig",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeTranscript",
    "StopCondition",
    "StopReason",
    "default_agent_role_registry",
]

__version__ = "0.1.0"
