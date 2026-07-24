"""Source-location primitives for the embedded IX language kernel."""

from __future__ import annotations

from dataclasses import dataclass

from ix_sally.digest import DigestRecord, JsonObject
from ix_sally.foundation import FoundationError, require_text


@dataclass(frozen=True, slots=True, order=True)
class SourcePosition:
    """One validated position in an IX source document."""

    line: int
    column: int
    offset: int

    def __post_init__(self) -> None:
        """Reject impossible source positions."""
        if self.line <= 0:
            raise FoundationError("source position line must be positive")
        if self.column <= 0:
            raise FoundationError("source position column must be positive")
        if self.offset < 0:
            raise FoundationError("source position offset must not be negative")

    @classmethod
    def start(cls) -> SourcePosition:
        """Return the first position in a source document."""
        return cls(line=1, column=1, offset=0)

    def advance(self, text: str) -> SourcePosition:
        """Return the position reached after consuming ``text``."""
        if not isinstance(text, str):
            raise FoundationError("source position advance text must be text")

        line = self.line
        column = self.column
        offset = self.offset

        for character in text:
            offset += 1
            if character == "\n":
                line += 1
                column = 1
            else:
                column += 1

        return SourcePosition(
            line=line,
            column=column,
            offset=offset,
        )

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible source position."""
        return {
            "line": self.line,
            "column": self.column,
            "offset": self.offset,
        }


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """A validated half-open range in one IX source document."""

    filename: str
    start: SourcePosition
    end: SourcePosition

    def __post_init__(self) -> None:
        """Normalize the filename and reject reversed ranges."""
        object.__setattr__(
            self,
            "filename",
            require_text(
                self.filename,
                field_name="filename",
            ),
        )
        if self.end < self.start:
            raise FoundationError(
                "source span end must not precede start"
            )

    @classmethod
    def point(
        cls,
        *,
        filename: str,
        line: int,
        column: int = 1,
        offset: int = 0,
    ) -> SourceSpan:
        """Create a zero-width span at one source position."""
        position = SourcePosition(
            line=line,
            column=column,
            offset=offset,
        )
        return cls(
            filename=filename,
            start=position,
            end=position,
        )

    @classmethod
    def covering(
        cls,
        *,
        filename: str,
        start: SourcePosition,
        text: str,
    ) -> SourceSpan:
        """Create a span covering ``text`` from ``start``."""
        if not isinstance(text, str):
            raise FoundationError("source span text must be text")

        return cls(
            filename=filename,
            start=start,
            end=start.advance(text),
        )

    def label(self) -> str:
        """Return a compact human-readable source label."""
        start = (
            f"{self.filename}:"
            f"{self.start.line}:"
            f"{self.start.column}"
        )

        if self.start == self.end:
            return start

        if self.start.line == self.end.line:
            return f"{start}-{self.end.column}"

        return (
            f"{start}-"
            f"{self.end.line}:"
            f"{self.end.column}"
        )

    def merge(self, other: SourceSpan) -> SourceSpan:
        """Return the smallest span containing this span and ``other``."""
        if self.filename != other.filename:
            raise FoundationError(
                "cannot merge source spans from different files"
            )

        return SourceSpan(
            filename=self.filename,
            start=min(self.start, other.start),
            end=max(self.end, other.end),
        )

    def contains(self, position: SourcePosition) -> bool:
        """Return whether ``position`` lies inside this half-open span."""
        if self.start == self.end:
            return position == self.start

        return self.start <= position < self.end

    def to_payload(self) -> JsonObject:
        """Return a stable JSON-compatible source span."""
        return {
            "filename": self.filename,
            "start": self.start.to_payload(),
            "end": self.end.to_payload(),
            "label": self.label(),
        }

    def digest(self) -> DigestRecord:
        """Return a deterministic digest for this source span."""
        return DigestRecord.from_payload(
            self.to_payload()
        )
