"""IX-Sally governed autonomy habitat package."""

from __future__ import annotations

from ix_sally.chamber import ObservationChamberConfig, StopCondition, StopReason
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord
from ix_sally.doctrine import DoctrineCatalog, DoctrineRule, DoctrineSeverity
from ix_sally.foundation import CanonicalKey, FoundationError

__all__ = [
    "__version__",
    "AutonomyContract",
    "AutonomyMode",
    "CanonicalKey",
    "DigestRecord",
    "DoctrineCatalog",
    "DoctrineRule",
    "DoctrineSeverity",
    "FoundationError",
    "ObservationChamberConfig",
    "StopCondition",
    "StopReason",
]

__version__ = "0.1.0"
