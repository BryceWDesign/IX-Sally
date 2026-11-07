"""Single-writer atomic research checkpoints for bounded cognitive experiments."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from ix_sally.cognition.developmental_learning import ResearchState
from ix_sally.foundation import FoundationError

_Result = TypeVar("_Result")


def advance_research_checkpoint(
    path: Path,
    transition: Callable[[ResearchState], tuple[ResearchState, _Result]],
    *,
    create_only: bool = False,
) -> _Result:
    """Validate, advance, sync and atomically replace one checkpoint.

    The sidecar lock is created exclusively, preventing cooperating writers from
    concurrently replacing each other's history. A stale lock fails closed and
    must be inspected before manual removal. No external execution is authorized.
    """
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write("IX-Sally research checkpoint write in progress\n")
    try:
        if create_only and path.exists():
            raise FoundationError("research checkpoint already exists")
        state = (
            ResearchState.from_json(path.read_text(encoding="utf-8"))
            if path.exists()
            else ResearchState()
        )
        updated, result = transition(state)
        if not isinstance(updated, ResearchState):
            raise FoundationError("checkpoint transition must return a research state")
        if not create_only and len(updated.episodes) <= len(state.episodes):
            raise FoundationError("checkpoint transition must extend evidence history")
        if not create_only and updated.episodes[: len(state.episodes)] != state.episodes:
            raise FoundationError("checkpoint transition cannot rewrite evidence history")
        if create_only and state.episodes:
            raise FoundationError("initial checkpoint requires empty research state")
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=path.name + ".",
                suffix=".pending",
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)
                temp.write(updated.to_json() + "\n")
                temp.flush()
                os.fsync(temp.fileno())
            temp_path.replace(path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return result
    finally:
        lock_path.unlink(missing_ok=True)
