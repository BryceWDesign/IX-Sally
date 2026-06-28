"""Observation chamber configuration and stop conditions for IX-Sally."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.contracts import AutonomyContract
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.doctrine import DoctrineCatalog
from ix_sally.foundation import FoundationError, require_text


class StopReason(StrEnum):
    """Reasons an IX-Sally chamber run may stop."""

    MAX_CYCLES_REACHED = "max_cycles_reached"
    CONTRACT_COMPLETE = "contract_complete"
    SAFETY_BLOCKED = "safety_blocked"
    EVIDENCE_GATE_FAILED = "evidence_gate_failed"
    HUMAN_TERMINATED = "human_terminated"


@dataclass(frozen=True, slots=True)
class StopCondition:
    """A structured stop decision for an observation chamber run."""

    should_stop: bool
    reason: StopReason | None
    detail: str | None = None

    @classmethod
    def continue_run(cls) -> StopCondition:
        """Return a non-stopping condition."""
        return cls(should_stop=False, reason=None, detail=None)

    @classmethod
    def stop(cls, *, reason: StopReason, detail: str) -> StopCondition:
        """Return a stopping condition with normalized detail."""
        return cls(
            should_stop=True,
            reason=reason,
            detail=require_text(detail, field_name="detail"),
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible stop-condition representation."""
        return {
            "should_stop": self.should_stop,
            "reason": self.reason.value if self.reason is not None else None,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ObservationChamberConfig:
    """Human-defined chamber configuration for a governed IX-Sally run."""

    contract: AutonomyContract
    doctrine_catalog: DoctrineCatalog
    observer_label: str
    sandbox_required: bool = True
    external_messaging_allowed: bool = False

    @classmethod
    def create(
        cls,
        *,
        contract: AutonomyContract,
        doctrine_catalog: DoctrineCatalog,
        observer_label: str = "human-boundary-observer",
        sandbox_required: bool = True,
        external_messaging_allowed: bool = False,
    ) -> ObservationChamberConfig:
        """Create a chamber configuration and validate doctrine bindings."""
        if not contract.human_boundary_required:
            raise FoundationError("observation chamber requires human boundary authority")

        for doctrine_key in contract.doctrine_keys:
            doctrine_catalog.require_rule(doctrine_key.value)

        if contract.network_allowed and not external_messaging_allowed:
            raise FoundationError(
                "network access cannot be enabled while external messaging is blocked"
            )

        return cls(
            contract=contract,
            doctrine_catalog=doctrine_catalog,
            observer_label=require_text(observer_label, field_name="observer_label"),
            sandbox_required=sandbox_required,
            external_messaging_allowed=external_messaging_allowed,
        )

    def stop_for_cycle(self, completed_cycles: int) -> StopCondition:
        """Return a stop decision for the number of completed cycles."""
        if completed_cycles < 0:
            raise FoundationError("completed_cycles must not be negative")

        if completed_cycles >= self.contract.max_cycles:
            return StopCondition.stop(
                reason=StopReason.MAX_CYCLES_REACHED,
                detail=(
                    f"completed_cycles={completed_cycles} reached "
                    f"max_cycles={self.contract.max_cycles}"
                ),
            )

        return StopCondition.continue_run()

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible chamber configuration representation."""
        return {
            "contract_digest": self.contract.digest().value,
            "doctrine_digest": self.doctrine_catalog.digest().value,
            "observer_label": self.observer_label,
            "sandbox_required": self.sandbox_required,
            "external_messaging_allowed": self.external_messaging_allowed,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this chamber configuration."""
        return DigestRecord.from_payload(self.to_payload())
