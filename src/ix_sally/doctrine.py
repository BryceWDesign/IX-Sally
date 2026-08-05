"""Doctrine records for IX-Sally's governed autonomy habitat."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import CanonicalKey, FoundationError, require_text


class DoctrineSeverity(StrEnum):
    """Severity level for a doctrine rule."""

    GUIDANCE = "guidance"
    GATE = "gate"
    PROHIBITION = "prohibition"


@dataclass(frozen=True, slots=True)
class DoctrineRule:
    """A load-bearing rule that constrains IX-Sally runtime behavior."""

    key: CanonicalKey
    title: str
    statement: str
    severity: DoctrineSeverity

    @classmethod
    def create(
        cls,
        *,
        title: str,
        statement: str,
        severity: DoctrineSeverity,
        key: CanonicalKey | None = None,
    ) -> DoctrineRule:
        """Create a normalized doctrine rule."""
        normalized_title = require_text(title, field_name="title")
        normalized_statement = require_text(statement, field_name="statement")
        return cls(
            key=key or CanonicalKey.from_text(normalized_title, field_name="title"),
            title=normalized_title,
            statement=normalized_statement,
            severity=severity,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible representation."""
        return {
            "key": self.key.value,
            "title": self.title,
            "statement": self.statement,
            "severity": self.severity.value,
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this rule."""
        return DigestRecord.from_payload(self.to_payload())


@dataclass(frozen=True, slots=True)
class DoctrineCatalog:
    """An immutable doctrine collection with unique rule keys."""

    rules: tuple[DoctrineRule, ...]

    @classmethod
    def create(cls, rules: Iterable[DoctrineRule]) -> DoctrineCatalog:
        """Create a catalog and reject duplicate doctrine keys."""
        normalized_rules = tuple(rules)
        seen: set[str] = set()
        for rule in normalized_rules:
            if rule.key.value in seen:
                raise FoundationError(f"duplicate doctrine rule key: {rule.key.value}")
            seen.add(rule.key.value)
        return cls(normalized_rules)

    def require_rule(self, key: str) -> DoctrineRule:
        """Return a rule by key or raise a construction error."""
        normalized_key = CanonicalKey.from_text(key, field_name="key").value
        for rule in self.rules:
            if rule.key.value == normalized_key:
                return rule
        raise FoundationError(f"unknown doctrine rule: {normalized_key}")

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible catalog representation."""
        return {
            "rules": [rule.to_payload() for rule in self.rules],
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for the complete catalog."""
        return DigestRecord.from_payload(self.to_payload())


def default_doctrine_catalog() -> DoctrineCatalog:
    """Return IX-Sally's initial load-bearing doctrine catalog."""
    return DoctrineCatalog.create(
        (
            DoctrineRule.create(
                title="Output is not evidence",
                statement=(
                    "Agent output remains unsupported until it is linked to an evidence record, "
                    "execution receipt, or human-reviewed source that supports the specific claim."
                ),
                severity=DoctrineSeverity.GATE,
            ),
            DoctrineRule.create(
                title="Memory is not truth",
                statement=(
                    "A memory record cannot become verified merely because an agent produced, "
                    "repeated, preferred, or relied on it."
                ),
                severity=DoctrineSeverity.GATE,
            ),
            DoctrineRule.create(
                title="Generated intent is not permission to act",
                statement=(
                    "A generated plan, request interpretation, or agent preference does not grant "
                    "permission to execute tools, modify files, persist memory, or escalate scope."
                ),
                severity=DoctrineSeverity.PROHIBITION,
            ),
            DoctrineRule.create(
                title="Self-revision is not self-approval",
                statement=(
                    "An agent may propose a correction to its own output, but approval requires "
                    "the proper evidence, memory, safety, or human boundary authority."
                ),
                severity=DoctrineSeverity.PROHIBITION,
            ),
            DoctrineRule.create(
                title="Human authority remains at the boundary",
                statement=(
                    "The system may cycle without human micro-steering, but chamber limits, "
                    "autonomy level, tool scope, and consequential approval remain human-defined."
                ),
                severity=DoctrineSeverity.GATE,
            ),
        )
    )
