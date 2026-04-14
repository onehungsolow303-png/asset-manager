"""Headless Blender renderer.

Wraps `blender -b -P script.py` to convert 3D meshes (GLB/FBX/OBJ) into
2D PNG sprites at any camera angle and lighting setup. The output is
the bridge between Tripo3D's 3D mesh outputs and Forever engine's 2D
Tilemap/Sprite renderer — render once headlessly, ship the PNGs.

Why subprocess instead of `import bpy`:
    Blender's bpy is bundled with Blender itself, not installable via
    pip. Some platforms have a `bpy` PyPI package, but it's fragile
    and version-locked. The robust path used by Blenderless and most
    automation pipelines is to subprocess `blender -b -P script.py`,
    let Blender handle its own Python environment, and capture the
    output via files on disk.

What this module does:
    1. Detects the Blender executable on disk (BLENDER_EXECUTABLE env
       var or common Windows install paths)
    2. Generates a Python script per render request that:
         - Loads the input mesh (GLB / FBX / OBJ via the appropriate importer)
         - Sets up an orthographic or perspective camera per preset
         - Adds a 3-light rig (key + fill + rim)
         - Renders to a target PNG path
         - Quits Blender
    3. Subprocesses Blender with the script
    4. Returns the output path on success or raises on any failure

Render presets (see RENDER_PRESETS dict):
    top_down_tile     ortho 90deg, 32x32, three-point top, no outline
    isometric_token   ortho 54.7deg + 45deg, 64x64, three-point iso
    portrait_bust     persp 85deg + 5deg tilt, 128x128, key/fill/rim
    icon_close        ortho 30deg, 32x32, icon flat lighting

These mirror the presets in the Development_Tool_Master_Prompt.docx §9
"Scene Presets" table. Each is a small dict of {camera, lighting,
resolution, post_process} that the script generator interprets.

NOT IN THIS BATCH:
    - Cel-shading post-process (Freestyle outlines + color ramps)
    - Pixel-downsample post-process for sprite sheets
    - Material library + texture baking
    - Animation rendering to sprite sheets

Those land in a future batch when we have actual 3D assets to render.
For now, this module ships the executable detection, the script
generator, the subprocess wrapper, and a simple "render single mesh
to single PNG" code path.

Failure modes (all GatewayUnavailable):
    - Blender not found on disk
    - Input mesh file doesn't exist
    - Unsupported input extension
    - Subprocess returns non-zero exit code
    - Output PNG not created
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# Windows install paths to probe in priority order. The user can override
# any of these by setting the BLENDER_EXECUTABLE env var.
_WINDOWS_BLENDER_PATHS = [
    "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.1/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.0/blender.exe",
]


class BlenderRendererUnavailable(Exception):
    """Raised when the renderer can't service a request (no Blender,
    bad input mesh, render failure)."""


@dataclass
class RenderPreset:
    """Camera + lighting + resolution + post-process for one preset."""

    name: str
    camera_type: str  # "ORTHO" | "PERSP"
    camera_rotation_deg: tuple[float, float, float]
    camera_distance: float
    resolution: tuple[int, int]
    lighting_rig: str  # "three_point_top" | "three_point_iso" | "key_fill_rim" | "icon_flat"


# Mirrors §9 of Development_Tool_Master_Prompt.docx
RENDER_PRESETS: dict[str, RenderPreset] = {
    "top_down_tile": RenderPreset(
        name="top_down_tile",
        camera_type="ORTHO",
        camera_rotation_deg=(90.0, 0.0, 0.0),
        camera_distance=5.0,
        resolution=(32, 32),
        lighting_rig="three_point_top",
    ),
    "isometric_token": RenderPreset(
        name="isometric_token",
        camera_type="ORTHO",
        camera_rotation_deg=(54.7, 0.0, 45.0),
        camera_distance=5.0,
        resolution=(64, 64),
        lighting_rig="three_point_iso",
    ),
    "portrait_bust": RenderPreset(
        name="portrait_bust",
        camera_type="PERSP",
        camera_rotation_deg=(85.0, 0.0, 5.0),
        camera_distance=2.5,
        resolution=(128, 128),
        lighting_rig="key_fill_rim",
    ),
    "icon_close": RenderPreset(
        name="icon_close",
        camera_type="ORTHO",
        camera_rotation_deg=(30.0, 0.0, 30.0),
        camera_distance=3.0,
        resolution=(32, 32),
        lighting_rig="icon_flat",
    ),
}


_SUPPORTED_INPUT_EXTENSIONS = {".glb", ".gltf", ".fbx", ".obj"}


class BlenderRenderer:
    """Headless Blender wrapper for 3D-to-2D rendering."""

    def __init__(
        self,
        blender_executable: str | Path | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._blender = self._find_blender(blender_executable)
        self._timeout = float(timeout)

    @property
    def blender_executable(self) -> Path | None:
        return self._blender

    def is_available(self) -> bool:
        """Returns True if a Blender executable was found on disk."""
        return self._blender is not None

    def render(
        self,
        mesh_path: Path,
        out_path: Path,
        preset: str = "isometric_token",
        background_alpha: bool = True,
    ) -> Path:
        """Render a 3D mesh to a 2D PNG using the named preset.

        Args:
            mesh_path: input GLB / FBX / OBJ
            out_path: where the output PNG should land
            preset: key from RENDER_PRESETS
            background_alpha: render with transparent background

        Returns:
            out_path on success.

        Raises:
            BlenderRendererUnavailable on any failure.
        """
        if not self.is_available():
            raise BlenderRendererUnavailable(
                "Blender executable not found. Set BLENDER_EXECUTABLE "
                "env var or install Blender 4.x."
            )

        mesh_path = Path(mesh_path)
        if not mesh_path.exists():
            raise BlenderRendererUnavailable(f"mesh not found: {mesh_path}")
        if mesh_path.suffix.lower() not in _SUPPORTED_INPUT_EXTENSIONS:
            raise BlenderRendererUnavailable(
                f"unsupported mesh extension: {mesh_path.suffix}. "
                f"Supported: {sorted(_SUPPORTED_INPUT_EXTENSIONS)}"
            )

        if preset not in RENDER_PRESETS:
            raise BlenderRendererUnavailable(
                f"unknown preset: {preset!r}. Known: {sorted(RENDER_PRESETS.keys())}"
            )

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate the bpy script as a temp file, then subprocess
        # blender -b -P script.py. We could pipe via stdin but a temp
        # file is easier to debug if something goes wrong.
        script_text = self._build_script(
            mesh_path=mesh_path,
            out_path=out_path,
            preset=RENDER_PRESETS[preset],
            background_alpha=background_alpha,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(script_text)
            script_path = Path(tmp.name)

        try:
            cmd = [
                str(self._blender),
                "-b",  # background mode (no GUI)
                "-noaudio",  # don't init audio (faster)
                "-P",
                str(script_path),
            ]
            logger.info("[blender_renderer] running: %s", " ".join(cmd))
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                )
            except subprocess.TimeoutExpired as e:
                raise BlenderRendererUnavailable(
                    f"blender render timed out after {self._timeout}s"
                ) from e
            except OSError as e:
                raise BlenderRendererUnavailable(f"blender subprocess failed to start: {e}") from e

            if proc.returncode != 0:
                raise BlenderRendererUnavailable(
                    f"blender exited {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}"
                )
        finally:
            try:
                script_path.unlink()
            except OSError:
                pass

        if not out_path.exists():
            raise BlenderRendererUnavailable(
                f"blender ran but {out_path} was not created. "
                f"stdout tail: {proc.stdout[-300:] if proc.stdout else '(empty)'}"
            )

        return out_path

    # ── Internals ─────────────────────────────────────────────────

    @staticmethod
    def _find_blender(override: str | Path | None) -> Path | None:
        """Locate the Blender executable.

        Resolution order:
            1. Explicit constructor arg
            2. BLENDER_EXECUTABLE env var
            3. `blender` on PATH
            4. Common Windows install paths
        """
        if override is not None:
            p = Path(override)
            if p.exists() and p.is_file():
                return p

        env = os.environ.get("BLENDER_EXECUTABLE")
        if env:
            p = Path(env)
            if p.exists() and p.is_file():
                return p

        which = shutil.which("blender")
        if which:
            return Path(which)

        if os.name == "nt":
            for candidate in _WINDOWS_BLENDER_PATHS:
                p = Path(candidate)
                if p.exists():
                    return p

        return None

    @staticmethod
    def _build_script(
        mesh_path: Path,
        out_path: Path,
        preset: RenderPreset,
        background_alpha: bool,
    ) -> str:
        """Build the bpy script that loads the mesh and renders it.

        The generated script is intentionally simple — clear the default
        scene, import the mesh, set up camera + lighting per the preset,
        render to the output path, quit Blender.

        Path strings are inserted via repr() so backslashes and quotes
        in Windows paths don't break the script.
        """
        ext = mesh_path.suffix.lower()
        # Map extension to the bpy importer call
        if ext in (".glb", ".gltf"):
            import_call = f"bpy.ops.import_scene.gltf(filepath={repr(str(mesh_path))})"
        elif ext == ".fbx":
            import_call = f"bpy.ops.import_scene.fbx(filepath={repr(str(mesh_path))})"
        elif ext == ".obj":
            import_call = f"bpy.ops.wm.obj_import(filepath={repr(str(mesh_path))})"
        else:
            # Should be unreachable — render() validates extensions first
            raise BlenderRendererUnavailable(f"no importer for {ext}")

        rx, ry, rz = preset.camera_rotation_deg
        res_x, res_y = preset.resolution

        return textwrap.dedent(f"""\
            import bpy
            import math

            # Clear default scene (cube, camera, light)
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)

            # Import mesh
            {import_call}

            # Frame scene — find imported objects, compute centroid
            imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            if not imported:
                raise SystemExit('no mesh imported')

            # Add camera
            bpy.ops.object.camera_add()
            cam = bpy.context.object
            cam.rotation_mode = 'XYZ'
            cam.rotation_euler = (
                math.radians({rx}),
                math.radians({ry}),
                math.radians({rz}),
            )
            # Position camera back along its local -Z axis at distance
            cam.location = (0.0, 0.0, {preset.camera_distance})
            cam.data.type = '{preset.camera_type}'
            if cam.data.type == 'ORTHO':
                cam.data.ortho_scale = 2.5
            bpy.context.scene.camera = cam

            # Three-light rig (simple key + fill + rim — preset variants
            # are deferred to a future batch)
            for name, loc, energy in [
                ('key',  (4, -4, 5),  500),
                ('fill', (-3, -2, 3), 200),
                ('rim',  (0, 5, 4),   300),
            ]:
                bpy.ops.object.light_add(type='POINT', location=loc)
                light = bpy.context.object
                light.name = name
                light.data.energy = energy

            # Render settings
            scene = bpy.context.scene
            scene.render.resolution_x = {res_x}
            scene.render.resolution_y = {res_y}
            scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGBA' if {background_alpha} else 'RGB'
            scene.render.film_transparent = {background_alpha}
            scene.render.filepath = {repr(str(out_path))}

            bpy.ops.render.render(write_still=True)
        """)
