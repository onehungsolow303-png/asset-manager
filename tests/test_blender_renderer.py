"""Tests for the headless Blender renderer wrapper.

These tests do NOT actually invoke Blender — they use monkeypatching
to swap subprocess.run with a fake that records the command and
returns success/failure as needed. This keeps the suite fast and
avoids requiring Blender to be installed in CI.

The one test that DOES probe for a real Blender install
(test_finds_blender_when_env_var_set) only verifies the executable
detection mechanism, not the rendering itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asset_manager.generators.blender_renderer import (
    RENDER_PRESETS,
    BlenderRenderer,
    BlenderRendererUnavailable,
)

# ─── Executable detection ──────────────────────────────────────────


def test_no_executable_when_nothing_found(monkeypatch, tmp_path):
    """With no env var, no PATH entry, and no Windows install paths,
    is_available() should return False."""
    monkeypatch.delenv("BLENDER_EXECUTABLE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    # Patch the Windows fallback list to point at non-existent paths
    monkeypatch.setattr(
        "asset_manager.generators.blender_renderer._WINDOWS_BLENDER_PATHS",
        [str(tmp_path / "nope/blender.exe")],
    )
    renderer = BlenderRenderer()
    assert renderer.is_available() is False
    assert renderer.blender_executable is None


def test_finds_blender_when_env_var_set(monkeypatch, tmp_path):
    fake = tmp_path / "blender.exe"
    fake.write_bytes(b"not a real blender")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(fake))
    renderer = BlenderRenderer()
    assert renderer.is_available() is True
    assert renderer.blender_executable == fake


def test_explicit_constructor_arg_wins(monkeypatch, tmp_path):
    fake_env = tmp_path / "env_blender.exe"
    fake_env.write_bytes(b"x")
    fake_arg = tmp_path / "arg_blender.exe"
    fake_arg.write_bytes(b"x")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(fake_env))
    renderer = BlenderRenderer(blender_executable=fake_arg)
    assert renderer.blender_executable == fake_arg


# ─── Render error paths ────────────────────────────────────────────


def test_render_raises_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("BLENDER_EXECUTABLE", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(
        "asset_manager.generators.blender_renderer._WINDOWS_BLENDER_PATHS",
        [],
    )
    renderer = BlenderRenderer()
    with pytest.raises(BlenderRendererUnavailable, match="not found"):
        renderer.render(tmp_path / "x.glb", tmp_path / "x.png")


def test_render_rejects_missing_mesh(monkeypatch, tmp_path):
    fake = tmp_path / "blender.exe"
    fake.write_bytes(b"x")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(fake))
    renderer = BlenderRenderer()
    with pytest.raises(BlenderRendererUnavailable, match="mesh not found"):
        renderer.render(tmp_path / "ghost.glb", tmp_path / "out.png")


def test_render_rejects_unsupported_extension(monkeypatch, tmp_path):
    fake = tmp_path / "blender.exe"
    fake.write_bytes(b"x")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(fake))
    mesh = tmp_path / "model.dae"
    mesh.write_bytes(b"fake collada")
    renderer = BlenderRenderer()
    with pytest.raises(BlenderRendererUnavailable, match="unsupported"):
        renderer.render(mesh, tmp_path / "out.png")


def test_render_rejects_unknown_preset(monkeypatch, tmp_path):
    fake = tmp_path / "blender.exe"
    fake.write_bytes(b"x")
    monkeypatch.setenv("BLENDER_EXECUTABLE", str(fake))
    mesh = tmp_path / "model.glb"
    mesh.write_bytes(b"fake glb")
    renderer = BlenderRenderer()
    with pytest.raises(BlenderRendererUnavailable, match="unknown preset"):
        renderer.render(mesh, tmp_path / "out.png", preset="moonshot")


# ─── Subprocess wrapping (mocked) ──────────────────────────────────


def test_render_invokes_blender_subprocess(monkeypatch, tmp_path):
    """Verify the subprocess invocation has the right shape: blender
    -b -noaudio -P <script>. We don't actually run blender — the mock
    captures the args, simulates a successful run, and writes a fake
    PNG so the post-render existence check passes."""
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_bytes(b"x")
    mesh = tmp_path / "model.glb"
    mesh.write_bytes(b"fake glb")
    out = tmp_path / "render.png"

    captured_cmds = []

    class FakeProc:
        returncode = 0
        stdout = "render done"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        # Simulate blender writing the output PNG
        Path(out).write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return FakeProc()

    monkeypatch.setattr("subprocess.run", fake_run)
    renderer = BlenderRenderer(blender_executable=fake_blender)

    result = renderer.render(mesh, out, preset="isometric_token")

    assert result == out
    assert out.exists()
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert str(fake_blender) in cmd
    assert "-b" in cmd
    assert "-noaudio" in cmd
    assert "-P" in cmd


def test_render_propagates_subprocess_failure(monkeypatch, tmp_path):
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_bytes(b"x")
    mesh = tmp_path / "model.glb"
    mesh.write_bytes(b"fake glb")

    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "blender exploded"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
    renderer = BlenderRenderer(blender_executable=fake_blender)

    with pytest.raises(BlenderRendererUnavailable, match="exited 1"):
        renderer.render(mesh, tmp_path / "out.png")


def test_render_raises_when_output_not_created(monkeypatch, tmp_path):
    """Even on a successful subprocess exit, if the output PNG doesn't
    exist (e.g. blender ran but the script failed silently), we raise."""
    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_bytes(b"x")
    mesh = tmp_path / "model.glb"
    mesh.write_bytes(b"fake glb")

    class FakeProc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
    renderer = BlenderRenderer(blender_executable=fake_blender)

    with pytest.raises(BlenderRendererUnavailable, match="not created"):
        renderer.render(mesh, tmp_path / "ghost.png")


def test_render_handles_subprocess_timeout(monkeypatch, tmp_path):
    import subprocess as sp

    fake_blender = tmp_path / "blender.exe"
    fake_blender.write_bytes(b"x")
    mesh = tmp_path / "model.glb"
    mesh.write_bytes(b"fake glb")

    def fake_run(*a, **k):
        raise sp.TimeoutExpired(cmd="blender", timeout=1)

    monkeypatch.setattr("subprocess.run", fake_run)
    renderer = BlenderRenderer(blender_executable=fake_blender, timeout=1)

    with pytest.raises(BlenderRendererUnavailable, match="timed out"):
        renderer.render(mesh, tmp_path / "out.png")


# ─── Preset table ──────────────────────────────────────────────────


def test_known_presets_present():
    """The four §9 presets from the spec must all be in RENDER_PRESETS."""
    for required in ("top_down_tile", "isometric_token", "portrait_bust", "icon_close"):
        assert required in RENDER_PRESETS
        preset = RENDER_PRESETS[required]
        assert preset.camera_type in ("ORTHO", "PERSP")
        assert len(preset.resolution) == 2
