"""Validation-bound creation of reusable tools from constructed procedures."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_sally.cognition.open_choice import ActionPrimitive, ConstructedAction
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class ToolValidationCase:
    initial_state: int
    expected_state: int


@dataclass(frozen=True, slots=True)
class ForgedTool:
    """A validated learned procedure exposed as one reusable capability."""

    tool_id: str
    primitive_ids: tuple[str, ...]
    validation_cases: tuple[ToolValidationCase, ...]
    validation_accuracy: float
    source_action_id: str

    def __post_init__(self) -> None:
        require_text(self.tool_id, field_name="tool_id")
        if not self.primitive_ids:
            raise FoundationError("forged tool requires a learned procedure")
        if not self.validation_cases:
            raise FoundationError("forged tool requires validation cases")
        if not 0.0 <= self.validation_accuracy <= 1.0:
            raise FoundationError("tool validation accuracy must be between zero and one")

    def apply(self, state: int, primitives: Iterable[ActionPrimitive]) -> int:
        primitive_map = {item.primitive_id: item for item in primitives}
        current = state
        for primitive_id in self.primitive_ids:
            primitive = primitive_map.get(primitive_id)
            if primitive is None:
                raise FoundationError(f"forged tool references unknown primitive: {primitive_id}")
            current = primitive.apply(current)
        return current

    def as_action_primitive(self, primitives: Iterable[ActionPrimitive]) -> ActionPrimitive:
        if self.validation_accuracy != 1.0:
            raise FoundationError("only fully validated tools may be promoted")
        base = tuple(primitives)
        return ActionPrimitive(self.tool_id, lambda state: self.apply(state, base), cost=1.0)

    def to_payload(self) -> JsonObject:
        cases: JsonArray = [
            {"initial_state": item.initial_state, "expected_state": item.expected_state}
            for item in self.validation_cases
        ]
        return {
            "tool_id": self.tool_id,
            "primitive_ids": list(self.primitive_ids),
            "validation_cases": cases,
            "validation_accuracy": self.validation_accuracy,
            "source_action_id": self.source_action_id,
            "origin": "sally-tool-forge",
        }


class ToolForge:
    """Promote a discovered action into a reusable tool only after independent tests."""

    def forge(
        self,
        *,
        action: ConstructedAction,
        primitives: Iterable[ActionPrimitive],
        validation_cases: Iterable[ToolValidationCase],
    ) -> ForgedTool:
        base = tuple(primitives)
        cases = tuple(validation_cases)
        if not cases:
            raise FoundationError("tool forge requires held-out validation cases")
        primitive_map = {item.primitive_id: item for item in base}
        correct = 0
        for case in cases:
            state = case.initial_state
            for primitive_id in action.primitive_ids:
                primitive = primitive_map.get(primitive_id)
                if primitive is None:
                    raise FoundationError(f"unknown primitive while forging tool: {primitive_id}")
                state = primitive.apply(state)
            if state == case.expected_state:
                correct += 1
        accuracy = correct / len(cases)
        identity = DigestRecord.from_payload(
            {
                "action": action.action_id,
                "cases": [
                    {"initial": item.initial_state, "expected": item.expected_state}
                    for item in cases
                ],
            }
        )
        return ForgedTool(
            tool_id=f"tool-{identity.value[:16]}",
            primitive_ids=action.primitive_ids,
            validation_cases=cases,
            validation_accuracy=accuracy,
            source_action_id=action.action_id,
        )
