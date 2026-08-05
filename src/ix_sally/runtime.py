"""Runtime integration kit for IX-Sally chamber construction."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.agents import AgentRole, AgentRoleDefinition, AgentRoleRegistry
from ix_sally.chamber import ObservationChamberConfig
from ix_sally.contracts import AutonomyContract
from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.doctrine import DoctrineCatalog, default_doctrine_catalog
from ix_sally.events import RuntimeEvent, RuntimeEventType
from ix_sally.foundation import FoundationError
from ix_sally.jurisdiction import JurisdictionDecision, JurisdictionGate, JurisdictionStatus


@dataclass(frozen=True, slots=True)
class NinefoldRuntimeKit:
    """Integrated runtime kit binding chamber, doctrine, roles, and jurisdiction gates."""

    chamber: ObservationChamberConfig
    role_registry: AgentRoleRegistry
    jurisdiction_gate: JurisdictionGate

    @classmethod
    def create(
        cls,
        *,
        contract: AutonomyContract,
        doctrine_catalog: DoctrineCatalog | None = None,
        role_registry: AgentRoleRegistry | None = None,
        observer_label: str = "human-boundary-observer",
        sandbox_required: bool = True,
        external_messaging_allowed: bool = False,
    ) -> NinefoldRuntimeKit:
        """Create a runtime kit with validated doctrine and complete ninefold roles."""
        selected_doctrine = doctrine_catalog or default_doctrine_catalog()
        selected_registry = role_registry or AgentRoleRegistry.create(())
        if role_registry is None:
            from ix_sally.agents import default_agent_role_registry

            selected_registry = default_agent_role_registry()

        selected_registry.require_complete_ninefold()

        chamber = ObservationChamberConfig.create(
            contract=contract,
            doctrine_catalog=selected_doctrine,
            observer_label=observer_label,
            sandbox_required=sandbox_required,
            external_messaging_allowed=external_messaging_allowed,
        )

        return cls(
            chamber=chamber,
            role_registry=selected_registry,
            jurisdiction_gate=JurisdictionGate(selected_registry),
        )

    def role_definition(self, role: AgentRole) -> AgentRoleDefinition:
        """Return the role definition bound into this runtime kit."""
        return self.role_registry.require_role(role)

    def evaluate_authority(self, *, role: AgentRole, authority: str) -> JurisdictionDecision:
        """Evaluate whether a role may exercise a requested authority."""
        return self.jurisdiction_gate.evaluate(role=role, authority=authority)

    def require_authority(self, *, role: AgentRole, authority: str) -> JurisdictionDecision:
        """Require allowed authority or raise a foundation error."""
        return self.jurisdiction_gate.require_allowed(role=role, authority=authority)

    def deny_if_authority_allowed(self, *, role: AgentRole, authority: str) -> None:
        """Raise when an authority is unexpectedly allowed for a role."""
        decision = self.evaluate_authority(role=role, authority=authority)
        if decision.status is JurisdictionStatus.ALLOWED:
            raise FoundationError(
                f"authority unexpectedly allowed for {role.value}: {decision.authority.value}"
            )

    def opening_event(self, *, sequence: int = 1) -> RuntimeEvent:
        """Create the deterministic opening transcript event for this runtime kit."""
        return RuntimeEvent.create(
            sequence=sequence,
            cycle=0,
            event_type=RuntimeEventType.CHAMBER_OPENED,
            summary=(
                "IX-Sally chamber opened with doctrine, ninefold roles, "
                "and jurisdiction gates."
            ),
            payload={
                "contract_digest": self.chamber.contract.digest().value,
                "doctrine_digest": self.chamber.doctrine_catalog.digest().value,
                "chamber_digest": self.chamber.digest().value,
                "role_registry_digest": self.role_registry.digest().value,
                "mode": self.chamber.contract.mode.value,
                "max_cycles": self.chamber.contract.max_cycles,
                "role_count": len(self.role_registry.definitions),
                "sandbox_required": self.chamber.sandbox_required,
            },
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible runtime-kit representation."""
        return {
            "contract_digest": self.chamber.contract.digest().value,
            "doctrine_digest": self.chamber.doctrine_catalog.digest().value,
            "chamber_digest": self.chamber.digest().value,
            "role_registry_digest": self.role_registry.digest().value,
            "observer_label": self.chamber.observer_label,
            "role_count": len(self.role_registry.definitions),
            "sandbox_required": self.chamber.sandbox_required,
            "external_messaging_allowed": self.chamber.external_messaging_allowed,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this integrated runtime kit."""
        return DigestRecord.from_payload(self.to_payload())
