"""Command-line entry point for IX-Sally."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ix_sally import __version__
from ix_sally.digest import stable_json
from ix_sally.session_baseline import session_one_baseline_digest, session_one_baseline_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the IX-Sally command-line parser."""
    parser = argparse.ArgumentParser(
        prog="ix-sally",
        description="IX-Sally governed ninefold autonomy runtime.",
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

    sys.stdout.write(f"IX-Sally {__version__}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
