"""Tests for the LICENSES.md regenerator CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.cli.regen_licenses import (
    BEGIN_MARKER,
    END_MARKER,
    build_packs_table,
    regenerate_licenses_md,
)


def _write_packs_yaml(path: Path, packs: list[dict]) -> Path:
    import yaml

    path.write_text(yaml.safe_dump({"packs": packs}), encoding="utf-8")
    return path


def _write_licenses_md_with_markers(path: Path, body_above: str, body_below: str) -> Path:
    content = (
        f"{body_above}\n\n"
        f"{BEGIN_MARKER}\n"
        f"| placeholder | placeholder | placeholder | placeholder | placeholder |\n"
        f"{END_MARKER}\n\n"
        f"{body_below}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ─── build_packs_table ─────────────────────────────────────────────


def test_build_packs_table_renders_rows(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "pack_a",
                "pack_name": "Pack A",
                "author": "Alice",
                "license_code": "CC0",
                "redistribution": True,
                "status": "imported",
            },
            {
                "pack_id": "pack_b",
                "pack_name": "Pack B",
                "author": "Bob",
                "license_code": "Synty_standard",
                "redistribution": False,
                "status": "planned",
            },
        ],
    )

    table = build_packs_table(yaml_path)
    assert "| Pack A |" in table
    assert "| Pack B |" in table
    assert "Alice" in table
    assert "**NO**" in table  # Pack B is restricted
    assert "YES" in table  # Pack A is OK to redistribute


def test_build_packs_table_handles_empty_packs(tmp_path):
    yaml_path = _write_packs_yaml(tmp_path / "packs.yaml", [])
    table = build_packs_table(yaml_path)
    assert "no packs registered" in table


def test_build_packs_table_raises_on_missing_yaml(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_packs_table(tmp_path / "ghost.yaml")


def test_build_packs_table_sorts_by_pack_id(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "zebra",
                "pack_name": "Z",
                "author": "z",
                "license_code": "x",
                "redistribution": True,
                "status": "x",
            },
            {
                "pack_id": "apple",
                "pack_name": "A",
                "author": "a",
                "license_code": "x",
                "redistribution": True,
                "status": "x",
            },
        ],
    )
    table = build_packs_table(yaml_path)
    apple_idx = table.index("| A |")
    zebra_idx = table.index("| Z |")
    assert apple_idx < zebra_idx


def test_build_packs_table_escapes_pipes_in_pack_name(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "p",
                "pack_name": "Has | Pipe",
                "author": "a",
                "license_code": "CC0",
                "redistribution": True,
                "status": "x",
            },
        ],
    )
    table = build_packs_table(yaml_path)
    # Escaped pipe should NOT break the table row
    assert "Has \\| Pipe" in table


# ─── regenerate_licenses_md ────────────────────────────────────────


def test_regenerate_replaces_markers_section(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "p1",
                "pack_name": "Test Pack",
                "author": "Test Author",
                "license_code": "CC0",
                "redistribution": True,
                "status": "imported",
            },
        ],
    )
    md_path = _write_licenses_md_with_markers(
        tmp_path / "LICENSES.md",
        "# Header\nSome prose above.",
        "## Definitions\nSome prose below.",
    )

    changed, msg = regenerate_licenses_md(yaml_path, md_path)
    assert changed is True

    body = md_path.read_text(encoding="utf-8")
    assert "Test Pack" in body
    assert "# Header" in body  # prose above preserved
    assert "## Definitions" in body  # prose below preserved
    assert "placeholder" not in body  # old table replaced


def test_regenerate_is_idempotent(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "p1",
                "pack_name": "Test Pack",
                "author": "Test",
                "license_code": "CC0",
                "redistribution": True,
                "status": "x",
            },
        ],
    )
    md_path = _write_licenses_md_with_markers(
        tmp_path / "LICENSES.md",
        "# H",
        "## D",
    )

    regenerate_licenses_md(yaml_path, md_path)
    changed_2, msg_2 = regenerate_licenses_md(yaml_path, md_path)
    assert changed_2 is False
    assert "up to date" in msg_2


def test_regenerate_check_only_does_not_write(tmp_path):
    yaml_path = _write_packs_yaml(
        tmp_path / "packs.yaml",
        [
            {
                "pack_id": "p1",
                "pack_name": "New Pack",
                "author": "x",
                "license_code": "CC0",
                "redistribution": True,
                "status": "x",
            },
        ],
    )
    md_path = _write_licenses_md_with_markers(
        tmp_path / "LICENSES.md",
        "# H",
        "## D",
    )
    original = md_path.read_text(encoding="utf-8")

    changed, msg = regenerate_licenses_md(yaml_path, md_path, check_only=True)
    assert changed is True  # would change
    assert "OUT OF DATE" in msg
    # File on disk untouched
    assert md_path.read_text(encoding="utf-8") == original


def test_regenerate_fails_when_md_missing(tmp_path):
    yaml_path = _write_packs_yaml(tmp_path / "packs.yaml", [])
    changed, msg = regenerate_licenses_md(yaml_path, tmp_path / "ghost.md")
    assert changed is False
    assert "not found" in msg


def test_regenerate_fails_when_markers_missing(tmp_path):
    yaml_path = _write_packs_yaml(tmp_path / "packs.yaml", [])
    md_path = tmp_path / "no_markers.md"
    md_path.write_text("# Header\nNo markers here.", encoding="utf-8")

    changed, msg = regenerate_licenses_md(yaml_path, md_path)
    assert changed is False
    assert "missing required markers" in msg
