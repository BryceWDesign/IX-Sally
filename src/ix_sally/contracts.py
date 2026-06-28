"""Autonomy contract records for IX-Sally chamber runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class AutonomyMode(StrEnum):
    """Supported autonomy modes for a governed IX-Sally chamber run."""

    OBSERVE = "observe"
    ADVISE = "advise"
    BUILD = "build"
    TEST = "test"
    TRANSFER = "transfer"
    RESEARCH = "research"


@dataclass(frozen=True, slots=True)
class AutonomyContract:
    """Human-defined contract that bounds an autonomous IX-Sally run."""

    goal: str
    mode: AutonomyMode
    max_cycles: int
    non_goals: tuple[str, ...] = field(default_factory=tuple)
    allowed_tools: tuple[CanonicalKey, ...] = field(default_factory=tuple)
    doctrine_keys: tuple[CanonicalKey, ...] = field(default_factory=tuple)
    memory_writes_allowed: bool = False
    network_allowed: bool = False
    human_boundary_required: bool = True

    @classmethod
    def create(
        cls,
        *,
        goal: str,
        mode: AutonomyMode,
        max_cycles: int,
        non_goals: Iterable[str] = (),
        allowed_tools: Iterable[str] = (),
        doctrine_keys: Iterable[str] = (),
        memory_writes_allowed: bool = False,
        network_allowed: bool = False,
        human_boundary_required: bool = True,
    ) -> AutonomyContract:
        """Create a normalized autonomy contract."""
        if max_cycles < 1:
            raise FoundationError("max_cycles must be at least 1")

        return cls(
            goal=require_text(goal, field_name="goal"),
            mode=mode,
            max_cycles=max_cycles,
            non_goals=tuple(
                require_text(non_goal, field_name="non_goal") for non_goal in non_goals
            ),
            allowed_tools=tuple(
                CanonicalKey.from_text(tool, field_name="allowed_tool") for tool in allowed_tools
            ),
            doctrine_keys=tuple(
                CanonicalKey.from_text(key, field_name="doctrine_key") for key in doctrine_keys
            ),
            memory_writes_allowed=memory_writes_allowed,
            network_allowed=network_allowed,
            human_boundary_required=human_boundary_required,
        )

    def require_tool_allowed(self, tool_key: str) -> None:
        """Reject a tool request that is outside the contract's allowed scope."""
        requested = CanonicalKey.from_text(tool_key, field_name="tool_key")
        if requested not in self.allowed_tools:
            raise FoundationError(f"tool is not allowed by autonomy contract: {requested.value}")

    def require_doctrine_key(self, doctrine_key: str) -> None:
        """Reject a required doctrine key that is missing from the contract."""
        requested = CanonicalKey.from_text(doctrine_key, field_name="doctrine_key")
        if requested not in self.doctrine_keys:
            raise FoundationError(
                f"doctrine key is not bound by autonomy contract: {requested.value}"
            )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible contract representation."""
        non_goals_payload: JsonArray = []
        for non_goal in self.non_goals:
            non_goals_payload.append(non_goal)

        allowed_tools_payload: JsonArray = []
        for tool in self.allowed_tools:
            allowed_tools_payload.append(tool.value)

        doctrine_keys_payload: JsonArray = []
        for key in self.doctrine_keys:
            doctrine_keys_payload.append(key.value)

        return {
            "goal": self.goal,
            "mode": self.mode.value,
            "max_cycles": self.max_cycles,
            "non_goals": non_goals_payload,
            "allowed_tools": allowed_tools_payload,
            "doctrine_keys": doctrine_keys_payload,
            "memory_writes_allowed": self.memory_writes_allowed,
            "network_allowed": self.network_allowed,
            "human_boundary_required": self.human_boundary_required,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this autonomy contract."""
        return DigestRecord.from_payload(self.to_payload())
