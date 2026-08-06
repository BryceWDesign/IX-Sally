"""Command-line entry point for IX-Sally."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ix_sally.digest import stable_json
from ix_sally.session_baseline import (
    session_one_baseline_digest,
    session_one_baseline_payload,
)
from ix_sally.version import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the IX-Sally command-line parser."""
    parser = argparse.ArgumentParser(
        prog="ix-sally",
        description="IX-Sally governed cognitive and ninefold autonomy runtime.",
    )
    parser.add_argument(
        "--runtime-baseline",
        action="store_true",
        help="Print the deterministic session-one runtime baseline as JSON.",
    )
    parser.add_argument(
        "--baseline-digest",
        action="store_true",
        help="Print the deterministic session-one baseline SHA-256 digest.",
    )
    parser.add_argument(
        "--cognitive-evaluation",
        action="store_true",
        help="Run the built-in cognitive capability suite and print its report as JSON.",
    )
    parser.add_argument(
        "--execute-ix",
        type=Path,
        metavar="FILE",
        help="Compile and execute one UTF-8 IX source file in the bounded local VM.",
    )
    parser.add_argument(
        "--empty-cognitive-snapshot",
        action="store_true",
        help="Print a canonical snapshot for a clean cognitive runtime.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the IX-Sally command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.runtime_baseline:
        sys.stdout.write(f"{stable_json(session_one_baseline_payload())}\n")
        return 0

    if args.baseline_digest:
        digest = session_one_baseline_digest()
        sys.stdout.write(f"{digest.algorithm}:{digest.value}\n")
        return 0

    if args.cognitive_evaluation:
        from ix_sally.cognition.evaluation import run_core_evaluation

        report = run_core_evaluation()
        sys.stdout.write(f"{stable_json(report.to_payload())}\n")
        return 0 if report.passed() == len(report.results) else 1

    if args.execute_ix is not None:
        from ix_sally.cognition.system import SallyCognitiveSystem

        try:
            source = args.execute_ix.read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(f"could not read IX source file: {exc}")
        result = SallyCognitiveSystem.create().execute_ix(
            source,
            filename=str(args.execute_ix),
        )
        sys.stdout.write(f"{stable_json(result.to_payload())}\n")
        return 0 if result.status.value == "halted" else 1

    if args.empty_cognitive_snapshot:
        from ix_sally.cognition.system import SallyCognitiveSystem

        sys.stdout.write(f"{SallyCognitiveSystem.create().snapshot().to_json()}\n")
        return 0

    sys.stdout.write(f"IX-Sally {__version__}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
