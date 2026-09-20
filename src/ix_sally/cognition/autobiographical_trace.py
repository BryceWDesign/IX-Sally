"""Replayable autobiographical epistemic traces for causal introspection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_sally.foundation import FoundationError, require_text


class TraceKind(StrEnum):
    OBSERVATION = "observation"
    PREDICTION = "prediction"
    DELTA = "delta"
    ASSUMPTION = "assumption"
    GOAL = "goal"
    DIRECTIVE = "directive"
    ACTION_PROPOSAL = "action-proposal"
    RECOVERY = "recovery"
    LEARNING = "learning"


@dataclass(frozen=True, slots=True)
class EpistemicTraceEntry:
    sequence: int
    kind: TraceKind
    object_id: str
    description: str
    parent_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise FoundationError("trace sequence must not be negative")
        require_text(self.object_id, field_name="object_id")
        require_text(self.description, field_name="description")


class AutobiographicalEpistemicTrace:
    """Append-only reasoning history retaining causal parent links."""

    def __init__(self) -> None:
        self._entries: list[EpistemicTraceEntry] = []
        self._ids: set[str] = set()

    def append(
        self,
        *,
        kind: TraceKind,
        object_id: str,
        description: str,
        parent_ids: tuple[str, ...] = (),
    ) -> EpistemicTraceEntry:
        if object_id in self._ids:
            raise FoundationError(f"duplicate trace object id: {object_id}")
        unknown = tuple(parent for parent in parent_ids if parent not in self._ids)
        if unknown:
            raise FoundationError(f"trace parents must already exist: {unknown}")
        entry = EpistemicTraceEntry(
            sequence=len(self._entries),
            kind=kind,
            object_id=object_id,
            description=description,
            parent_ids=parent_ids,
        )
        self._entries.append(entry)
        self._ids.add(object_id)
        return entry

    def lineage(self, object_id: str) -> tuple[EpistemicTraceEntry, ...]:
        if object_id not in self._ids:
            raise FoundationError(f"unknown trace object: {object_id}")
        by_id = {item.object_id: item for item in self._entries}
        visited: set[str] = set()
        ordered: list[EpistemicTraceEntry] = []

        def walk(identifier: str) -> None:
            if identifier in visited:
                return
            entry = by_id[identifier]
            for parent in entry.parent_ids:
                walk(parent)
            visited.add(identifier)
            ordered.append(entry)

        walk(object_id)
        return tuple(ordered)

    def entries(self) -> tuple[EpistemicTraceEntry, ...]:
        return tuple(self._entries)
