"""CLI: watch a directory and detect when its size has stopped growing.

Used to detect when a long-running file move (like the user's 33GB
OneDrive→C:\\Pictures\\Assets relocation) has completed. The script
polls the destination folder size at a fixed interval and exits with
status 0 once the size has been stable for a configurable hold period.

Usage:
    python -m asset_manager.cli.watch_move <path> [--hold N] [--interval N] [--timeout N]

Defaults:
    --hold      30   seconds the size must stay constant before declaring done
    --interval  5    seconds between polls
    --timeout   3600 seconds (1 hour) max total wait

Exit codes:
    0   size stable for the hold period (move done)
    1   timeout exceeded before stability
    2   path does not exist or is not a directory

Why it doesn't use filesystem watch APIs:
    Cross-platform watch APIs (inotify on Linux, FSEvents on macOS,
    ReadDirectoryChangesW on Windows) are complex and have edge cases
    around recursive watches and high-throughput moves. Polling the
    total size is simpler, more reliable for "is it done copying yet"
    detection, and works the same on every OS.

The poll loop also prints a progress line so a human watching can
see growth in real time.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def total_size_bytes(root: Path) -> int:
    """Return the recursive size of every file under root.

    Errors on individual files (permission denied, mid-move) are
    swallowed silently — they're transient during a copy operation.
    """
    total = 0
    try:
        for path in root.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return total


def watch(
    root: Path,
    hold_seconds: float = 30.0,
    poll_interval: float = 5.0,
    timeout_seconds: float = 3600.0,
    verbose: bool = True,
) -> bool:
    """Poll root's size until stable for hold_seconds.

    Returns True if stability was reached within timeout, False on
    timeout. The verbose mode prints a progress line per poll.
    """
    if not root.exists():
        if verbose:
            print(f"ERROR: path does not exist: {root}", file=sys.stderr)
        return False
    if not root.is_dir():
        if verbose:
            print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return False

    started = time.monotonic()
    last_size = -1
    stable_since: float | None = None

    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            if verbose:
                print(
                    f"TIMEOUT: {timeout_seconds}s elapsed without stability",
                    file=sys.stderr,
                )
            return False

        current_size = total_size_bytes(root)
        size_mb = current_size / (1024 * 1024)

        if current_size == last_size:
            if stable_since is None:
                stable_since = time.monotonic()
            stable_for = time.monotonic() - stable_since
            if verbose:
                print(
                    f"  [{int(elapsed):>5}s] {size_mb:>9.1f} MB  "
                    f"(stable {int(stable_for)}s / {int(hold_seconds)}s)"
                )
            if stable_for >= hold_seconds:
                if verbose:
                    print(
                        f"DONE: size stable at {size_mb:.1f} MB "
                        f"after {int(elapsed)}s"
                    )
                return True
        else:
            stable_since = None
            if last_size >= 0:
                delta_mb = (current_size - last_size) / (1024 * 1024)
                if verbose:
                    print(
                        f"  [{int(elapsed):>5}s] {size_mb:>9.1f} MB  "
                        f"(+{delta_mb:.1f} MB)"
                    )
            else:
                if verbose:
                    print(f"  [{int(elapsed):>5}s] {size_mb:>9.1f} MB  (initial)")

        last_size = current_size
        time.sleep(poll_interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Watch a directory and exit when its total size stops growing"
    )
    parser.add_argument("path", help="Directory to watch")
    parser.add_argument(
        "--hold",
        type=float,
        default=30.0,
        help="Seconds the size must stay constant before declaring done (default 30)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between polls (default 5)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        help="Max total wait in seconds (default 3600 = 1 hour)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-poll progress lines (only final result)",
    )
    args = parser.parse_args(argv)

    root = Path(args.path)
    success = watch(
        root,
        hold_seconds=args.hold,
        poll_interval=args.interval,
        timeout_seconds=args.timeout,
        verbose=not args.quiet,
    )

    if not root.exists() or not root.is_dir():
        return 2
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
