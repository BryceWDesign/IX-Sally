"""Command-line entry point for IX-Sally."""

from __future__ import annotations

import sys

from ix_sally import __version__


def main() -> int:
    """Report package identity for the initial scaffold."""
    sys.stdout.write(f"IX-Sally {__version__}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
