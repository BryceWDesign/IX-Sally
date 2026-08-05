

from __future__ import annotations

import pytest
from ix_sally.doctrine import (
    DoctrineCatalog,
    DoctrineRule,
    DoctrineSeverity,
    default_doctrine_catalog,
)
from ix_sally.foundation import CanonicalKey, FoundationError


def test_doctrine_rule_normalizes_title_and_statement() -> None:
    rule = DoctrineRule.create(
        title="  Output is not evidence  ",
        statement="  Claims require receipts.  ",
        severity=DoctrineSeverity.GATE,
    )

    assert rule.key.value == "output-is-not-evidence"
    assert rule.title == "Output is not evidence"
    assert rule.statement == "Claims require receipts."
    assert rule.severity is DoctrineSeverity.GATE


def test_doctrine_rule_payload_is_stable() -> None:
    rule = DoctrineRule.create(
        title="Memory is not truth",
        statement="Memory requires validation.",
        severity=DoctrineSeverity.GATE,
    )

    assert rule.to_payload() == {
        "key": "memory-is-not-truth",
        "title": "Memory is not truth",
        "statement": "Memory requires validation.",
        "severity": "gate",
    }


def test_doctrine_catalog_rejects_duplicate_keys() -> None:
    first = DoctrineRule.create(
        title="Output is not evidence",
        statement="First statement.",
        severity=DoctrineSeverity.GATE,
    )
    second = DoctrineRule.create(
        title="Output is not evidence",
        statement="Second statement.",
        severity=DoctrineSeverity.PROHIBITION,
    )

    with pytest.raises(FoundationError, match="duplicate doctrine rule key"):
        DoctrineCatalog.create((first, second))


def test_doctrine_catalog_requires_known_rule() -> None:
    rule = DoctrineRule.create(
        key=CanonicalKey.from_text("boundary-authority", field_name="key"),
        title="Human authority remains at the boundary",
        statement="The chamber is human-defined.",
        severity=DoctrineSeverity.GATE,
    )
    catalog = DoctrineCatalog.create((rule,))

    assert catalog.require_rule("Boundary Authority") == rule

    with pytest.raises(FoundationError, match="unknown doctrine rule"):
        catalog.require_rule("missing rule")


def test_default_doctrine_catalog_contains_load_bearing_rules() -> None:
    catalog = default_doctrine_catalog()
    keys = {rule.key.value for rule in catalog.rules}

    assert keys == {
        "output-is-not-evidence",
        "memory-is-not-truth",
        "generated-intent-is-not-permission-to-act",
        "self-revision-is-not-self-approval",
        "human-authority-remains-at-the-boundary",
    }


def test_catalog_digest_changes_when_rules_change() -> None:
    first = DoctrineCatalog.create(
        (
            DoctrineRule.create(
                title="Output is not evidence",
                statement="Claims require receipts.",
                severity=DoctrineSeverity.GATE,
            ),
        )
    )
    second = DoctrineCatalog.create(
        (
            DoctrineRule.create(
                title="Output is not evidence",
                statement="Claims require independent receipts.",
                severity=DoctrineSeverity.GATE,
            ),
        )
    )

    assert first.digest().value != second.digest().value
