"""Ninefold cycle packets for complete IX-Sally role coordination."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.agents import AgentRole
from ix_sally.artifacts import AgentArtifact
from ix_sally.digest import DigestRecord, JsonArray, JsonObject, JsonValue
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class CycleCoordinationStatus(StrEnum):
    """Coordination status for a complete IX-Sally ninefold cycle."""

    COMPLETE = "complete"
    BLOCKED = "blocked"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class NinefoldCyclePacket:
    """A complete coordinated cycle containing one artifact from each ninefold role."""

    cycle_id: CanonicalKey
    cycle: int
    cycle_goal: str
    artifacts: tuple[AgentArtifact, ...]
    status: CycleCoordinationStatus = CycleCoordinationStatus.COMPLETE

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        cycle_goal: str,
        artifacts: Iterable[AgentArtifact],
        status: CycleCoordinationStatus = CycleCoordinationStatus.COMPLETE,
        cycle_id: CanonicalKey | None = None,
    ) -> NinefoldCyclePacket:
        """Create a normalized ninefold cycle packet."""
        if cycle < 0:
            raise FoundationError("ninefold cycle must not be negative")

        normalized_goal = require_text(cycle_goal, field_name="cycle_goal")
        normalized_artifacts = tuple(artifacts)

        if not normalized_artifacts:
            raise FoundationError("ninefold cycle requires artifacts")

        seen_roles: set[AgentRole] = set()
        seen_artifact_ids: set[str] = set()

        for artifact in normalized_artifacts:
            if artifact.cycle != cycle:
                raise FoundationError("ninefold cycle artifacts must match packet cycle")

            if artifact.role in seen_roles:
                raise FoundationError(f"duplicate ninefold role artifact: {artifact.role.value}")
            seen_roles.add(artifact.role)

            if artifact.artifact_id.value in seen_artifact_ids:
                raise FoundationError(f"duplicate cycle artifact id: {artifact.artifact_id.value}")
            seen_artifact_ids.add(artifact.artifact_id.value)

        missing_roles = [role.value for role in AgentRole if role not in seen_roles]
        if missing_roles:
            joined = ", ".join(missing_roles)
            raise FoundationError(f"missing ninefold cycle role artifacts: {joined}")

        return cls(
            cycle_id=cycle_id
            or CanonicalKey.from_text(
                f"ninefold-cycle-{cycle}-{normalized_goal}",
                field_name="cycle_id",
            ),
            cycle=cycle,
            cycle_goal=normalized_goal,
            artifacts=normalized_artifacts,
            status=status,
        )

    def artifact_for_role(self, role: AgentRole) -> AgentArtifact:
        """Return the artifact emitted by a specific role."""
        for artifact in self.artifacts:
            if artifact.role is role:
                return artifact
        raise FoundationError(f"missing ninefold cycle role artifact: {role.value}")

    def artifact_digests(self) -> tuple[DigestRecord, ...]:
        """Return deterministic digests for all artifacts in the cycle."""
        return tuple(artifact.digest() for artifact in self.artifacts)

    def blocking_roles(self) -> tuple[AgentRole, ...]:
        """Return roles whose artifacts report a blocker."""
        blocking: list[AgentRole] = []
        for artifact in self.artifacts:
            if _payload_reports_blocker(artifact.data):
                blocking.append(artifact.role)
        return tuple(blocking)

    def terminated_by_roles(self) -> tuple[AgentRole, ...]:
        """Return roles whose artifacts report chamber termination."""
        terminated: list[AgentRole] = []
        for artifact in self.artifacts:
            if _payload_reports_termination(artifact.data):
                terminated.append(artifact.role)
        return tuple(terminated)

    def requires_human_review(self) -> bool:
        """Return whether any artifact reports a blocker or human review requirement."""
        for artifact in self.artifacts:
            if _payload_reports_human_review(artifact.data):
                return True
        return bool(self.blocking_roles())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible ninefold cycle representation."""
        artifact_payload: JsonArray = []
        for artifact in self.artifacts:
            artifact_payload.append(artifact.to_payload())

        blocking_roles_payload: JsonArray = []
        for role in self.blocking_roles():
            blocking_roles_payload.append(role.value)

        terminated_roles_payload: JsonArray = []
        for role in self.terminated_by_roles():
            terminated_roles_payload.append(role.value)

        return {
            "cycle_id": self.cycle_id.value,
            "cycle": self.cycle,
            "cycle_goal": self.cycle_goal,
            "status": self.status.value,
            "artifacts": artifact_payload,
            "artifact_count": len(self.artifacts),
            "blocking_roles": blocking_roles_payload,
            "terminated_by_roles": terminated_roles_payload,
            "requires_human_review": self.requires_human_review(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this ninefold cycle packet."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class NinefoldCycleLedger:
    """Immutable ledger of coordinated ninefold cycle packets."""

    cycles: tuple[NinefoldCyclePacket, ...]

    @classmethod
    def create(cls, cycles: Iterable[NinefoldCyclePacket]) -> NinefoldCycleLedger:
        """Create a cycle ledger and reject duplicate or non-monotonic cycle numbers."""
        normalized = tuple(cycles)
        seen_ids: set[str] = set()
        previous_cycle = -1

        for packet in normalized:
            if packet.cycle_id.value in seen_ids:
                raise FoundationError(f"duplicate ninefold cycle id: {packet.cycle_id.value}")
            seen_ids.add(packet.cycle_id.value)

            if packet.cycle < previous_cycle:
                raise FoundationError("ninefold cycle ledger must not move backward")
            previous_cycle = packet.cycle

        return cls(cycles=normalized)

    def append(self, packet: NinefoldCyclePacket) -> NinefoldCycleLedger:
        """Return a new ledger with an appended ninefold cycle packet."""
        return NinefoldCycleLedger.create((*self.cycles, packet))

    def require_cycle(self, cycle_id: str) -> NinefoldCyclePacket:
        """Return a cycle packet by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(cycle_id, field_name="cycle_id")
        for packet in self.cycles:
            if packet.cycle_id == requested:
                return packet
        raise FoundationError(f"unknown ninefold cycle id: {requested.value}")

    def blocked_cycles(self) -> tuple[NinefoldCyclePacket, ...]:
        """Return all cycle packets that report blockers."""
        return tuple(packet for packet in self.cycles if packet.blocking_roles())

    def human_review_cycles(self) -> tuple[NinefoldCyclePacket, ...]:
        """Return all cycle packets that require human review."""
        return tuple(packet for packet in self.cycles if packet.requires_human_review())

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible cycle ledger representation."""
        cycles_payload: JsonArray = []
        for packet in self.cycles:
            cycles_payload.append(packet.to_payload())

        return {
            "cycles": cycles_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this cycle ledger."""
        return DigestRecord.from_payload(self.to_payload())


def _payload_reports_blocker(payload: JsonObject) -> bool:
    """Return whether artifact payload data reports a blocker."""
    return _is_true(payload.get("has_blocker")) or _is_true(payload.get("blocks_progress"))


def _payload_reports_termination(payload: JsonObject) -> bool:
    """Return whether artifact payload data reports chamber termination."""
    return _is_true(payload.get("terminates_run"))


def _payload_reports_human_review(payload: JsonObject) -> bool:
    """Return whether artifact payload data reports human-review need."""
    return _is_true(payload.get("requires_human_review")) or _is_true(
        payload.get("has_blocker")
    )


def _is_true(value: JsonValue | None) -> bool:
    """Return True only for the JSON boolean true value."""
    return value is True
