"""Deterministic JSON encoding and digest records for IX-Sally."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TypeAlias

from ix_sally.foundation import FoundationError, require_text

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonArray: TypeAlias = list["JsonValue"]
JsonObject: TypeAlias = dict[str, "JsonValue"]
JsonValue: TypeAlias = JsonPrimitive | JsonArray | JsonObject


@dataclass(frozen=True, slots=True)
class DigestRecord:
    """A deterministic digest over canonical JSON payload data."""

    algorithm: str
    value: str

    @classmethod
    def from_payload(cls, payload: JsonValue) -> DigestRecord:
        """Create a SHA-256 digest record from canonical JSON payload data."""
        return cls(algorithm="sha256", value=stable_digest(payload))

    def require_algorithm(self, expected_algorithm: str) -> None:
        """Reject a digest that does not use the expected algorithm."""
        expected = require_text(expected_algorithm, field_name="expected_algorithm").lower()
        if self.algorithm.lower() != expected:
            raise FoundationError(
                f"digest algorithm mismatch: expected digest algorithm {expected}, "
                f"got {self.algorithm.lower()}"
            )


def stable_json(payload: JsonValue) -> str:
    """Encode payload data as stable JSON for repeatable receipts and records."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_digest(payload: JsonValue) -> str:
    """Return a deterministic SHA-256 hex digest for canonical JSON payload data."""
    encoded = stable_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
