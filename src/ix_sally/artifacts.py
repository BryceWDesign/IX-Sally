"""Shared artifact records emitted by IX-Sally ninefold agent roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable

from ix_sally.agents import AgentRole
from ix_sally.digest import DigestRecord, JsonArray, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class AgentArtifactKind(StrEnum):
    """Kinds of structured artifacts emitted during IX-Sally cycles."""

    PROPOSAL = "proposal"
    FALSIFICATION = "falsification"
    EVIDENCE_JUDGMENT = "evidence_judgment"
    PREDICTION = "prediction"
    EXECUTION_RECEIPT = "execution_receipt"
    MEMORY_DECISION = "memory_decision"
    BOUNDARY_REPORT = "boundary_report"
    TRANSFER_RESULT = "transfer_result"
    DOSSIER_ENTRY = "dossier_entry"


@dataclass(frozen=True, slots=True)
class AgentArtifact:
    """A structured record emitted by a single ninefold agent role."""

    artifact_id: CanonicalKey
    cycle: int
    role: AgentRole
    kind: AgentArtifactKind
    summary: str
    referenced_digests: tuple[DigestRecord, ...] = field(default_factory=tuple)
    data: JsonObject = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        cycle: int,
        role: AgentRole,
        kind: AgentArtifactKind,
        summary: str,
        referenced_digests: Iterable[DigestRecord] = (),
        data: JsonObject | None = None,
        artifact_id: CanonicalKey | None = None,
    ) -> AgentArtifact:
        """Create a normalized agent artifact."""
        if cycle < 0:
            raise FoundationError("artifact cycle must not be negative")

        normalized_summary = require_text(summary, field_name="summary")
        normalized_references = tuple(referenced_digests)
        for digest in normalized_references:
            digest.require_algorithm("sha256")

        return cls(
            artifact_id=artifact_id
            or CanonicalKey.from_text(
                f"{role.value}-{cycle}-{kind.value}-{normalized_summary}",
                field_name="artifact_id",
            ),
            cycle=cycle,
            role=role,
            kind=kind,
            summary=normalized_summary,
            referenced_digests=normalized_references,
            data=data or {},
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible artifact representation."""
        references_payload: JsonArray = []
        for digest in self.referenced_digests:
            references_payload.append(
                {
                    "algorithm": digest.algorithm,
                    "value": digest.value,
                }
            )

        return {
            "artifact_id": self.artifact_id.value,
            "cycle": self.cycle,
            "role": self.role.value,
            "kind": self.kind.value,
            "summary": self.summary,
            "referenced_digests": references_payload,
            "data": self.data,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this artifact."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class AgentArtifactLedger:
    """Immutable ledger of agent artifacts emitted during a chamber run."""

    artifacts: tuple[AgentArtifact, ...]

    @classmethod
    def create(cls, artifacts: Iterable[AgentArtifact]) -> AgentArtifactLedger:
        """Create an artifact ledger and reject duplicate artifact identifiers."""
        normalized = tuple(artifacts)
        seen: set[str] = set()

        for artifact in normalized:
            if artifact.artifact_id.value in seen:
                raise FoundationError(f"duplicate artifact id: {artifact.artifact_id.value}")
            seen.add(artifact.artifact_id.value)

        return cls(artifacts=normalized)

    def append(self, artifact: AgentArtifact) -> AgentArtifactLedger:
        """Return a new ledger with an appended artifact."""
        return AgentArtifactLedger.create((*self.artifacts, artifact))

    def require_artifact(self, artifact_id: str) -> AgentArtifact:
        """Return an artifact by identifier or raise a construction error."""
        requested = CanonicalKey.from_text(artifact_id, field_name="artifact_id")
        for artifact in self.artifacts:
            if artifact.artifact_id == requested:
                return artifact
        raise FoundationError(f"unknown artifact id: {requested.value}")

    def by_role(self, role: AgentRole) -> tuple[AgentArtifact, ...]:
        """Return all artifacts emitted by a role."""
        return tuple(artifact for artifact in self.artifacts if artifact.role is role)

    def by_kind(self, kind: AgentArtifactKind) -> tuple[AgentArtifact, ...]:
        """Return all artifacts matching a kind."""
        return tuple(artifact for artifact in self.artifacts if artifact.kind is kind)

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible artifact ledger representation."""
        artifact_payload: JsonArray = []
        for artifact in self.artifacts:
            artifact_payload.append(artifact.to_payload())

        return {
            "artifacts": artifact_payload,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this artifact ledger."""
        return DigestRecord.from_payload(self.to_payload())
