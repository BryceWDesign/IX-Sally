"""Tamper-evident canonical persistence envelopes for IX-Sally cognitive state."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject, JsonValue, stable_json
from ix_sally.foundation import FoundationError, require_text

CURRENT_SNAPSHOT_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class CognitiveSnapshot:
    """Versioned canonical state payload with an independently verified digest."""

    schema_version: int
    repository: str
    state: JsonObject
    state_digest: DigestRecord

    @classmethod
    def create(
        cls,
        state: JsonObject,
        *,
        repository: str = "IX-Sally",
    ) -> CognitiveSnapshot:
        """Create a current-schema snapshot for exact state data."""
        return cls(
            schema_version=CURRENT_SNAPSHOT_SCHEMA,
            repository=require_text(repository, field_name="repository"),
            state=state,
            state_digest=DigestRecord.from_payload(state),
        )

    def __post_init__(self) -> None:
        """Reject unsupported schemas, wrong repository identity, and tampering."""
        if self.schema_version != CURRENT_SNAPSHOT_SCHEMA:
            raise FoundationError(
                f"unsupported cognitive snapshot schema: {self.schema_version}"
            )
        if self.repository != "IX-Sally":
            raise FoundationError(
                f"cognitive snapshot repository mismatch: {self.repository}"
            )
        self.state_digest.require_algorithm("sha256")
        actual = DigestRecord.from_payload(self.state)
        if actual != self.state_digest:
            raise FoundationError("cognitive snapshot state digest mismatch")

    def to_payload(self) -> JsonObject:
        """Return the complete canonical envelope payload."""
        return {
            "schema_version": self.schema_version,
            "repository": self.repository,
            "state": self.state,
            "state_digest": {
                "algorithm": self.state_digest.algorithm,
                "value": self.state_digest.value,
            },
        }

    def to_json(self) -> str:
        """Return deterministic compact JSON suitable for exact storage."""
        return stable_json(self.to_payload())

    @classmethod
    def from_json(cls, encoded: str) -> CognitiveSnapshot:
        """Parse and fully validate one persisted snapshot envelope."""
        if not isinstance(encoded, str) or not encoded.strip():
            raise FoundationError("encoded snapshot must be non-empty text")
        try:
            payload: JsonValue = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise FoundationError("cognitive snapshot is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise FoundationError("cognitive snapshot root must be an object")
        schema_version = payload.get("schema_version")
        repository = payload.get("repository")
        state = payload.get("state")
        digest_payload = payload.get("state_digest")
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise FoundationError("snapshot schema_version must be an integer")
        if not isinstance(repository, str):
            raise FoundationError("snapshot repository must be text")
        if not isinstance(state, dict):
            raise FoundationError("snapshot state must be an object")
        if not isinstance(digest_payload, dict):
            raise FoundationError("snapshot state_digest must be an object")
        algorithm = digest_payload.get("algorithm")
        value = digest_payload.get("value")
        if not isinstance(algorithm, str) or not isinstance(value, str):
            raise FoundationError("snapshot state_digest fields must be text")
        return cls(
            schema_version=schema_version,
            repository=repository,
            state=state,
            state_digest=DigestRecord(algorithm=algorithm, value=value),
        )
