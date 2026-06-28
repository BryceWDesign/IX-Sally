"""Session-one baseline report for IX-Sally's initial ninefold runtime."""

from __future__ import annotations

from ix_sally.agents import AgentRole, default_agent_role_registry
from ix_sally.contracts import AutonomyContract, AutonomyMode
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.doctrine import default_doctrine_catalog
from ix_sally.events import RuntimeEventType
from ix_sally.runtime import NinefoldRuntimeKit


def session_one_contract() -> AutonomyContract:
    """Return the baseline contract used to verify the session-one runtime."""
    return AutonomyContract.create(
        goal=(
            "Verify IX-Sally session-one foundation: doctrine, chamber, ninefold roles, "
            "jurisdiction, records, artifacts, cycles, and CLI baseline."
        ),
        mode=AutonomyMode.OBSERVE,
        max_cycles=1,
        allowed_tools=("test-runner",),
        doctrine_keys=(
            "output-is-not-evidence",
            "memory-is-not-truth",
            "generated-intent-is-not-permission-to-act",
            "self-revision-is-not-self-approval",
            "human-authority-remains-at-the-boundary",
        ),
    )


def session_one_runtime_kit() -> NinefoldRuntimeKit:
    """Return a fully composed session-one runtime kit."""
    return NinefoldRuntimeKit.create(
        contract=session_one_contract(),
        doctrine_catalog=default_doctrine_catalog(),
        role_registry=default_agent_role_registry(),
        observer_label="session-one-human-boundary-observer",
        sandbox_required=True,
        external_messaging_allowed=False,
    )


def session_one_baseline_payload() -> JsonObject:
    """Return a stable JSON-compatible session-one baseline payload."""
    kit = session_one_runtime_kit()
    opening_event = kit.opening_event()

    roles_payload: JsonArray = []
    for role in AgentRole:
        definition = kit.role_definition(role)
        roles_payload.append(
            {
                "role": definition.role.value,
                "title": definition.title,
                "prohibited_authorities": [
                    authority.value for authority in definition.prohibited_authorities
                ],
            }
        )

    return {
        "package": "ix-sally",
        "version": "0.1.0",
        "baseline": "session-one",
        "runtime": kit.to_payload(),
        "opening_event_type": opening_event.event_type.value,
        "opening_event_digest": opening_event.digest().value,
        "doctrine_rule_count": len(kit.chamber.doctrine_catalog.rules),
        "role_count": len(kit.role_registry.definitions),
        "roles": roles_payload,
        "contract_mode": kit.chamber.contract.mode.value,
        "max_cycles": kit.chamber.contract.max_cycles,
        "default_cli_event": RuntimeEventType.CHAMBER_OPENED.value,
        "session_one_complete": True,
    }


def session_one_baseline_digest() -> DigestRecord:
    """Return a deterministic digest for the session-one baseline payload."""
    return DigestRecord.from_payload(session_one_baseline_payload())
