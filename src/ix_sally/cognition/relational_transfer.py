"""Surface-independent structural analogy across unrelated domains."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Iterable

from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True)
class RelationEdge:
    source: str
    relation: str
    target: str

    def __post_init__(self) -> None:
        require_text(self.source, field_name="source")
        require_text(self.relation, field_name="relation")
        require_text(self.target, field_name="target")
        if self.source == self.target:
            raise FoundationError("structural transfer does not admit self edges")


@dataclass(frozen=True, slots=True)
class RelationalWorld:
    domain_id: str
    edges: tuple[RelationEdge, ...]

    def __post_init__(self) -> None:
        require_text(self.domain_id, field_name="domain_id")
        if not self.edges:
            raise FoundationError("relational world requires edges")

    @property
    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted({edge.source for edge in self.edges} | {edge.target for edge in self.edges}))


@dataclass(frozen=True, slots=True)
class StructuralRole:
    indegree: int
    outdegree: int
    distance_from_source: int
    distance_to_sink: int


@dataclass(frozen=True, slots=True)
class LearnedStructuralSchema:
    source_domain: str
    effective_role: StructuralRole
    graph_signature: tuple[tuple[int, int, int, int], ...]


@dataclass(frozen=True, slots=True)
class TransferInference:
    target_domain: str
    inferred_node: str
    matched_role: StructuralRole
    structural_match: bool


class RelationalTransferEngine:
    """Learn which topological role mattered in one domain and transfer it by structure."""

    def learn(self, *, world: RelationalWorld, effective_node: str) -> LearnedStructuralSchema:
        roles = self._roles(world)
        if effective_node not in roles:
            raise FoundationError("effective node is not present in source world")
        signature = tuple(sorted((r.indegree, r.outdegree, r.distance_from_source, r.distance_to_sink) for r in roles.values()))
        return LearnedStructuralSchema(world.domain_id, roles[effective_node], signature)

    def transfer(self, schema: LearnedStructuralSchema, *, world: RelationalWorld) -> TransferInference:
        roles = self._roles(world)
        signature = tuple(sorted((r.indegree, r.outdegree, r.distance_from_source, r.distance_to_sink) for r in roles.values()))
        matches = sorted(node for node, role in roles.items() if role == schema.effective_role)
        if signature != schema.graph_signature or len(matches) != 1:
            raise FoundationError("target world does not contain one unambiguous learned structural role")
        node = matches[0]
        return TransferInference(world.domain_id, node, roles[node], True)

    def _roles(self, world: RelationalWorld) -> dict[str, StructuralRole]:
        nodes = world.nodes
        outgoing: dict[str, list[str]] = {node: [] for node in nodes}
        incoming: dict[str, list[str]] = {node: [] for node in nodes}
        for edge in world.edges:
            outgoing[edge.source].append(edge.target)
            incoming[edge.target].append(edge.source)
        sources = [node for node in nodes if not incoming[node]]
        sinks = [node for node in nodes if not outgoing[node]]
        if not sources or not sinks:
            raise FoundationError("relational transfer requires an acyclic source-to-sink structure")
        from_source = self._distances(sources, outgoing)
        to_sink = self._distances(sinks, incoming)
        if set(from_source) != set(nodes) or set(to_sink) != set(nodes):
            raise FoundationError("all relational nodes must connect source to sink")
        return {
            node: StructuralRole(
                indegree=len(incoming[node]),
                outdegree=len(outgoing[node]),
                distance_from_source=from_source[node],
                distance_to_sink=to_sink[node],
            )
            for node in nodes
        }

    @staticmethod
    def _distances(starts: Iterable[str], adjacency: dict[str, list[str]]) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque((node, 0) for node in starts)
        while queue:
            node, distance = queue.popleft()
            if node in distances and distances[node] <= distance:
                continue
            distances[node] = distance
            for neighbor in adjacency[node]:
                queue.append((neighbor, distance + 1))
        return distances
