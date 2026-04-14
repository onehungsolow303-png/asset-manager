"""Tests for the watch_move size-stability poller.

These tests run with very short hold/interval/timeout values so the
suite stays fast. The actual CLI is intended for multi-minute waits
on large copy operations.
"""

from __future__ import annotations

from pathlib import Path

from asset_manager.cli.watch_move import total_size_bytes, watch

# ─── total_size_bytes ──────────────────────────────────────────────


def test_total_size_empty_directory(tmp_path):
    assert total_size_bytes(tmp_path) == 0


def test_total_size_sums_all_files_recursively(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    (tmp_path / "b.txt").write_bytes(b"y" * 200)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_bytes(b"z" * 50)

    assert total_size_bytes(tmp_path) == 350


def test_total_size_handles_unusual_inputs(tmp_path):
    """The function should never raise on permission errors or other
    transient OS issues — it silently skips and continues. Tested
    here only against the happy path with normal files."""
    (tmp_path / "ok.txt").write_bytes(b"hi")
    assert total_size_bytes(tmp_path) >= 2


# ─── watch ──────────────────────────────────────────────────────────


def test_watch_returns_false_for_missing_path(tmp_path):
    result = watch(
        tmp_path / "nonexistent",
        hold_seconds=0.1,
        poll_interval=0.05,
        timeout_seconds=1.0,
        verbose=False,
    )
    assert result is False


def test_watch_returns_false_for_file_not_dir(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi")
    result = watch(
        f,
        hold_seconds=0.1,
        poll_interval=0.05,
        timeout_seconds=1.0,
        verbose=False,
    )
    assert result is False


def test_watch_returns_true_when_size_stable(tmp_path):
    """Empty directory has stable size of 0 from the start. The poller
    should declare success after hold_seconds elapses."""
    result = watch(
        tmp_path,
        hold_seconds=0.2,
        poll_interval=0.05,
        timeout_seconds=2.0,
        verbose=False,
    )
    assert result is True


def test_watch_times_out_when_size_keeps_changing(tmp_path, monkeypatch):
    """Simulate a directory whose size grows on every poll. The watcher
    should never declare stability and should time out."""
    counter = {"calls": 0}

    def fake_size(_root):
        counter["calls"] += 1
        return counter["calls"] * 1000  # always growing

    monkeypatch.setattr("asset_manager.cli.watch_move.total_size_bytes", fake_size)

    result = watch(
        tmp_path,
        hold_seconds=1.0,
        poll_interval=0.05,
        timeout_seconds=0.5,
        verbose=False,
    )
    assert result is False


def test_watch_succeeds_after_growth_stops(tmp_path, monkeypatch):
    """Simulate a directory that grows for a few polls then stops."""
    state = {"size": 0, "calls": 0}

    def fake_size(_root):
        state["calls"] += 1
        if state["calls"] <= 3:
            state["size"] += 1000
        return state["size"]

    monkeypatch.setattr("asset_manager.cli.watch_move.total_size_bytes", fake_size)

    result = watch(
        tmp_path,
        hold_seconds=0.15,
        poll_interval=0.05,
        timeout_seconds=2.0,
        verbose=False,
    )
    assert result is True
    assert state["size"] == 3000  # grew 3 times then stopped
