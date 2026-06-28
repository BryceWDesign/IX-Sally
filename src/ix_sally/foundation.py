"""Foundational validation and normalization helpers for IX-Sally."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE_PATTERN = re.compile(r"\s+")
_KEY_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


class FoundationError(ValueError):
    """Raised when foundational IX-Sally values violate strict construction rules."""


@dataclass(frozen=True, slots=True)
class CanonicalKey:
    """A lowercase stable key used for internal identifiers and record types."""

    value: str

    @classmethod
    def from_text(cls, value: str, *, field_name: str) -> CanonicalKey:
        """Create a canonical key from human-readable text."""
        text = require_text(value, field_name=field_name).lower()
        collapsed = _KEY_SEPARATOR_PATTERN.sub("-", text).strip("-")
        if not collapsed:
            raise FoundationError(f"{field_name} must contain at least one alphanumeric character")
        return cls(collapsed)

    def __str__(self) -> str:
        return self.value


def normalize_text(value: str) -> str:
    """Return text with leading/trailing and repeated internal whitespace removed."""
    return _WHITESPACE_PATTERN.sub(" ", value.strip())


def require_text(value: str, *, field_name: str) -> str:
    """Normalize text and reject empty values."""
    if not isinstance(value, str):
        raise FoundationError(f"{field_name} must be text")

    normalized = normalize_text(value)
    if not normalized:
        raise FoundationError(f"{field_name} must not be empty")

    return normalized


def require_optional_text(value: str | None, *, field_name: str) -> str | None:
    """Normalize optional text while preserving an omitted value as None."""
    if value is None:
        return None
    return require_text(value, field_name=field_name)
