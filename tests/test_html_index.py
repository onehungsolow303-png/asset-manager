"""Tests for the HTML catalog index generator.

After the JSON-embedded refactor for pagination, the HTML output
contains a JSON array of asset records (CATALOG = [...]) instead
of pre-rendered DOM nodes. JS pagination renders cards on demand.

These tests validate the JSON shape rather than the rendered HTML
markup, since the cards aren't in the static HTML anymore.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from asset_manager.library.html_index import regenerate_index
from asset_manager.library.manifest import make_manifest


class FakeCatalog:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = entries

    def all(self) -> list[dict]:
        return list(self._entries)


def _extract_catalog_json(html_body: str) -> list[dict]:
    """Pull the embedded `const CATALOG = [...];` array out of the HTML."""
    m = re.search(r"const CATALOG = (\[.*?\]);", html_body, re.DOTALL)
    assert m is not None, "no embedded CATALOG array found in HTML"
    return json.loads(m.group(1))


# ─── Basic write + count ───────────────────────────────────────────


def test_index_writes_html_file_with_count(tmp_path):
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="wolf",
                kind="creature_token",
                path="/x/wolf.png",
                source="procedural",
                license="CC0",
            ),
            make_manifest(
                asset_id="bandit",
                kind="creature_token",
                path="/x/bandit.png",
                source="procedural",
                license="CC0",
            ),
        ]
    )
    out = tmp_path / "index.html"

    n = regenerate_index(catalog, out)

    assert n == 2
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "2 assets" in body  # title or count display
    # Both asset IDs should appear in the embedded JSON
    records = _extract_catalog_json(body)
    ids = {r["id"] for r in records}
    assert ids == {"wolf", "bandit"}


def test_index_creates_parent_directory(tmp_path):
    """Output path's parent must be created if it doesn't exist."""
    catalog = FakeCatalog(
        [
            make_manifest(asset_id="wolf", kind="creature_token", path="/x/wolf.png"),
        ]
    )
    out = tmp_path / "deep" / "nested" / "index.html"

    regenerate_index(catalog, out)

    assert out.exists()
    assert out.parent.exists()


# ─── Thumbnail integration ─────────────────────────────────────────


def test_index_records_thumbnail_for_real_image(tmp_path):
    """Real PNG sources get a thumbnail rendered and a thumb path
    in the embedded JSON."""
    from PIL import Image

    src = tmp_path / "wolf.png"
    Image.new("RGB", (64, 64), (200, 100, 50)).save(src, format="PNG")

    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="wolf", kind="creature_token", path=str(src), source="procedural"
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    wolf = records[0]
    assert wolf["id"] == "wolf"
    assert wolf["thumb"] is not None
    assert wolf["thumb"].startswith("thumbs/")
    assert wolf["thumb_state"] == "ok"
    # The thumbnail file should land under thumbs/ relative to the HTML
    assert (tmp_path / "thumbs").exists()


def test_index_records_thumb_state_for_3d_assets(tmp_path):
    """3D assets get thumb=None and a thumb_state describing the extension
    so the JS renders the placeholder card."""
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="wizard",
                kind="character",
                path="C:/packs/kaykit/wizard.glb",
                source="pack",
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    assert records[0]["thumb"] is None
    assert records[0]["thumb_state"] == "ext_glb"


def test_index_records_failed_thumb_for_corrupt_image(tmp_path):
    """Sources that look like images but can't be loaded by PIL get
    thumb_state='failed' so the JS shows the broken-image placeholder."""
    src = tmp_path / "corrupt.png"
    src.write_bytes(b"this is not a valid png")
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="corrupt", kind="creature_token", path=str(src), source="procedural"
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    assert records[0]["thumb"] is None
    assert records[0]["thumb_state"] == "failed"


# ─── Provenance fields ─────────────────────────────────────────────


def test_index_includes_provenance_metadata(tmp_path):
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="garth_portrait",
                kind="portrait",
                path="/x/garth.png",
                source="ai_2d",
                license="Scenario_owned",
                cost_usd=0.04,
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    g = records[0]
    assert g["id"] == "garth_portrait"
    assert g["kind"] == "portrait"
    assert g["source"] == "ai_2d"
    assert g["license"] == "Scenario_owned"
    assert g["cost_usd"] == 0.04


def test_index_carries_redistribution_flag(tmp_path):
    """The redistribution flag drives the must-replace JS filter, so
    it must end up in the embedded JSON."""
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="restricted", kind="portrait", path="/x/r.png", redistribution=False
            ),
            make_manifest(asset_id="safe", kind="portrait", path="/x/s.png", redistribution=True),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in records}
    assert by_id["restricted"]["redistribution"] is False
    assert by_id["safe"]["redistribution"] is True


def test_index_carries_tags_array(tmp_path):
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="wolf",
                kind="creature_token",
                path="/x/wolf.png",
                tags=["wolf", "forest", "predator"],
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    records = _extract_catalog_json(out.read_text(encoding="utf-8"))
    assert records[0]["tags"] == ["wolf", "forest", "predator"]


# ─── Empty catalog ────────────────────────────────────────────────


def test_index_handles_empty_catalog(tmp_path):
    catalog = FakeCatalog([])
    out = tmp_path / "index.html"

    n = regenerate_index(catalog, out)

    assert n == 0
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "0 assets" in body
    records = _extract_catalog_json(body)
    assert records == []


# ─── HTML escaping in JS context ────────────────────────────────────


def test_index_escapes_special_chars_in_json(tmp_path):
    """The catalog JSON is embedded inside a <script> tag, so any
    unescaped </script> sequence in an asset_id would break the page.
    JSON encoding handles this — the test verifies it's actually
    happening end-to-end."""
    catalog = FakeCatalog(
        [
            make_manifest(
                asset_id="evil</script><script>alert('xss')</script>",
                kind="evil",
                path="/x/evil.png",
            ),
        ]
    )
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    body = out.read_text(encoding="utf-8")
    # The literal closing-script tag must NOT appear inside the embedded
    # JSON. JSON encoding renders < as \u003c (or escapes the slash).
    # Either way, the raw </script> string must not appear as a
    # standalone closing tag inside the script section.
    # We check that there's exactly ONE </script> tag in the document
    # (the closing one for the main script block). The asset_id with
    # the malicious payload should be JSON-encoded so its </script>
    # bytes are escaped.
    script_close_count = body.count("</script>")
    # The HTML has exactly one real script block, so should have exactly
    # one </script> closing tag.
    assert script_close_count == 1
