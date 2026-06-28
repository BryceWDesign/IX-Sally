from __future__ import annotations

import pytest

from ix_sally.foundation import (
    CanonicalKey,
    FoundationError,
    normalize_text,
    require_optional_text,
    require_text,
)


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  governed\n\nagent\t autonomy  ") == "governed agent autonomy"


def test_require_text_rejects_empty_values() -> None:
    with pytest.raises(FoundationError, match="agent_name must not be empty"):
        require_text("   ", field_name="agent_name")


def test_require_text_rejects_non_text_values() -> None:
    with pytest.raises(FoundationError, match="agent_name must be text"):
        require_text(17, field_name="agent_name")  # type: ignore[arg-type]


def test_optional_text_preserves_none() -> None:
    assert require_optional_text(None, field_name="description") is None


def test_optional_text_normalizes_present_value() -> None:
    assert require_optional_text("  evidence\n gate  ", field_name="description") == "evidence gate"


def test_canonical_key_from_text_is_stable_and_lowercase() -> None:
    key = CanonicalKey.from_text(" IX Sally: Evidence Gate ", field_name="role")

    assert key.value == "ix-sally-evidence-gate"
    assert str(key) == "ix-sally-evidence-gate"


def test_canonical_key_requires_alphanumeric_content() -> None:
    with pytest.raises(FoundationError, match="role must contain at least one alphanumeric"):
        CanonicalKey.from_text("---", field_name="role")
