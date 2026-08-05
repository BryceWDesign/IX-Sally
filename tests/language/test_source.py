"""Tests for IX language source-location primitives."""

from __future__ import annotations

import pytest
from ix_sally.foundation import FoundationError
from ix_sally.language.source import (
    SourcePosition,
    SourceSpan,
)


def test_source_position_advances_across_lines() -> None:
    """Offsets, lines, and columns must advance deterministically."""
    start = SourcePosition.start()

    end = start.advance("alpha\nbeta")

    assert end == SourcePosition(
        line=2,
        column=5,
        offset=10,
    )


def test_source_position_rejects_invalid_coordinates() -> None:
    """Impossible source coordinates must fail at construction."""
    with pytest.raises(
        FoundationError,
        match="line must be positive",
    ):
        SourcePosition(
            line=0,
            column=1,
            offset=0,
        )

    with pytest.raises(
        FoundationError,
        match="column must be positive",
    ):
        SourcePosition(
            line=1,
            column=0,
            offset=0,
        )

    with pytest.raises(
        FoundationError,
        match="offset must not be negative",
    ):
        SourcePosition(
            line=1,
            column=1,
            offset=-1,
        )


def test_source_span_covers_and_labels_single_line_text() -> None:
    """A covering span must preserve half-open source coordinates."""
    span = SourceSpan.covering(
        filename="agent.ix",
        start=SourcePosition(
            line=3,
            column=5,
            offset=20,
        ),
        text="remember",
    )

    assert span.end == SourcePosition(
        line=3,
        column=13,
        offset=28,
    )
    assert span.label() == "agent.ix:3:5-13"
    assert (
        span.contains(
            SourcePosition(
                line=3,
                column=5,
                offset=20,
            )
        )
        is True
    )
    assert (
        span.contains(
            SourcePosition(
                line=3,
                column=13,
                offset=28,
            )
        )
        is False
    )


def test_source_span_merges_ranges_from_same_file() -> None:
    """Merging spans must return the smallest containing range."""
    first = SourceSpan.covering(
        filename="agent.ix",
        start=SourcePosition(
            line=1,
            column=1,
            offset=0,
        ),
        text="let",
    )
    second = SourceSpan.covering(
        filename="agent.ix",
        start=SourcePosition(
            line=2,
            column=1,
            offset=4,
        ),
        text="print",
    )

    merged = first.merge(second)

    assert merged.start == first.start
    assert merged.end == second.end
    assert merged.label() == "agent.ix:1:1-2:6"


def test_source_span_rejects_cross_file_merge() -> None:
    """Source ranges from different documents must never be merged."""
    first = SourceSpan.point(
        filename="first.ix",
        line=1,
    )
    second = SourceSpan.point(
        filename="second.ix",
        line=1,
    )

    with pytest.raises(
        FoundationError,
        match="different files",
    ):
        first.merge(second)
