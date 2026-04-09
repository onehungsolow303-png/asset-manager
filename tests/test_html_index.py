"""Tests for the HTML catalog index generator."""
from __future__ import annotations

from pathlib import Path

from asset_manager.library.html_index import regenerate_index
from asset_manager.library.manifest import make_manifest


class FakeCatalog:
    def __init__(self, entries: list[dict]) -> None:
        self._entries = entries

    def all(self) -> list[dict]:
        return list(self._entries)


def test_index_writes_html_file_with_count(tmp_path):
    catalog = FakeCatalog([
        make_manifest(asset_id="wolf", kind="creature_token", path="/x/wolf.png",
                       source="procedural", license="CC0"),
        make_manifest(asset_id="bandit", kind="creature_token", path="/x/bandit.png",
                       source="procedural", license="CC0"),
    ])
    out = tmp_path / "index.html"

    n = regenerate_index(catalog, out)

    assert n == 2
    assert out.exists()
    body = out.read_text(encoding="utf-8")
    assert "2 assets" in body
    assert "wolf" in body
    assert "bandit" in body


def test_index_creates_parent_directory(tmp_path):
    """Output path's parent must be created if it doesn't exist."""
    catalog = FakeCatalog([
        make_manifest(asset_id="wolf", kind="creature_token", path="/x/wolf.png"),
    ])
    out = tmp_path / "deep" / "nested" / "index.html"

    regenerate_index(catalog, out)

    assert out.exists()
    assert out.parent.exists()


def test_index_renders_image_assets_inline(tmp_path):
    # Write a real PNG so the thumbnailer can produce a thumbnail.
    # Pre-thumbnailing-rework, this test used a fake path because the
    # HTML referenced source file:// URIs directly. The new code
    # actually generates thumbnails, so the source must exist.
    from PIL import Image
    src = tmp_path / "wolf.png"
    Image.new("RGB", (64, 64), (200, 100, 50)).save(src, format="PNG")

    catalog = FakeCatalog([
        make_manifest(asset_id="wolf", kind="creature_token",
                       path=str(src), source="procedural"),
    ])
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    body = out.read_text(encoding="utf-8")
    # PNG should produce an <img> tag pointing at the generated thumbnail
    assert "<img" in body
    # The thumbnail should land under thumbs/ relative to the HTML
    assert (tmp_path / "thumbs").exists()


def test_index_renders_3d_assets_with_placeholder(tmp_path):
    catalog = FakeCatalog([
        make_manifest(asset_id="wizard", kind="character",
                       path="C:/packs/kaykit/wizard.glb", source="pack"),
    ])
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    body = out.read_text(encoding="utf-8")
    # GLB is not an image — should get a placeholder card with the extension
    assert "ext-placeholder" in body
    assert "GLB" in body


def test_index_includes_provenance_metadata(tmp_path):
    catalog = FakeCatalog([
        make_manifest(
            asset_id="garth_portrait",
            kind="portrait",
            path="/x/garth.png",
            source="ai_2d",
            license="Scenario_owned",
            cost_usd=0.04,
            pack_name=None,
        ),
    ])
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    body = out.read_text(encoding="utf-8")
    assert "garth_portrait" in body
    assert "ai_2d" in body
    assert "Scenario_owned" in body
    assert "0.0400" in body  # cost formatted to 4 decimal places


def test_index_handles_empty_catalog(tmp_path):
    catalog = FakeCatalog([])
    out = tmp_path / "index.html"

    n = regenerate_index(catalog, out)

    assert n == 0
    assert out.exists()
    assert "0 assets" in out.read_text(encoding="utf-8")


def test_index_escapes_html_in_asset_ids(tmp_path):
    """Defense against asset_ids containing < or > or & — even though our
    seed/import code never produces such IDs, malicious or hand-crafted
    manifests should not break the page."""
    catalog = FakeCatalog([
        make_manifest(asset_id="<script>alert('xss')</script>",
                       kind="evil", path="/x/evil.png"),
    ])
    out = tmp_path / "index.html"
    regenerate_index(catalog, out)

    body = out.read_text(encoding="utf-8")
    # The literal <script> tag must NOT appear unescaped — it should be
    # rendered as &lt;script&gt; so the browser shows it as text
    assert "<script>alert" not in body
    assert "&lt;script&gt;" in body
