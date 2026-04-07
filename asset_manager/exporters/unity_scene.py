"""
UnitySceneExporter — Generates Unity .unity scene files (YAML format).
Creates a complete scene with Terrain, Water plane, GameObjects for structures
and assets, lighting, and camera setup.

Unity scene files use a custom YAML-like format with GUIDs and fileIDs.
"""

import os
import json
import hashlib
import numpy as np
from asset_manager.generators.pcg.base_agent import BaseAgent
from asset_manager.shared_state import SharedState
from typing import Any


def generate_guid(name: str) -> str:
    """Generate a deterministic GUID-like string from a name."""
    return hashlib.md5(name.encode()).hexdigest()


def generate_file_id(index: int) -> int:
    """Generate a Unity-style fileID."""
    return 100000 + index


class UnitySceneExporter(BaseAgent):
    name = "UnitySceneExporter"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_dir = params.get("output_dir",
                                "./output/unity_export")
        scenes_dir = os.path.join(output_dir, "Scenes")
        os.makedirs(scenes_dir, exist_ok=True)

        map_name = shared_state.metadata.get("map_name", "GeneratedMap")
        safe_name = map_name.replace(" ", "_").replace("'", "")
        scene_path = os.path.join(scenes_dir, f"{safe_name}.unity")

        w = shared_state.config.width
        h = shared_state.config.height
        biome = shared_state.config.biome

        # Build scene YAML
        scene_lines = []
        scene_lines.append("%YAML 1.1")
        scene_lines.append("%TAG !u! tag:unity3d.com,2011:")

        # ── Scene Settings ──
        scene_lines.append(self._scene_settings(map_name))

        # ── Directional Light ──
        scene_lines.append(self._directional_light(biome))

        # ── Main Camera ──
        scene_lines.append(self._main_camera(w, h))

        # ── Terrain GameObject ──
        scene_lines.append(self._terrain_object(w, h))

        # ── Water Plane (if water exists) ──
        if shared_state.water_mask.any():
            scene_lines.append(self._water_plane(shared_state))

        # ── Structure GameObjects ──
        obj_id = 200
        for i, entity in enumerate(shared_state.entities):
            if entity.entity_type in ("building", "room"):
                scene_lines.append(self._game_object(
                    entity, obj_id, w, h))
                obj_id += 10

        # ── Prefab reference manifest ──
        prefab_manifest = self._build_prefab_manifest(shared_state)
        manifest_path = os.path.join(output_dir, "prefab_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(prefab_manifest, f, indent=2)

        with open(scene_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(scene_lines))

        return {
            "scene_file": scene_path,
            "prefab_manifest": manifest_path,
            "game_objects": obj_id // 10,
            "map_name": map_name,
        }

    def _scene_settings(self, name: str) -> str:
        return f"""--- !u!29 &1
OcclusionCullingSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_OcclusionBakeSettings:
    smallestOccluder: 5
    smallestHole: 0.25
    backfaceThreshold: 100
--- !u!104 &2
RenderSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 9
  m_Fog: 1
  m_FogColor: {{r: 0.75, g: 0.78, b: 0.82, a: 1}}
  m_FogMode: 3
  m_FogDensity: 0.002
  m_LinearFogStart: 0
  m_LinearFogEnd: 300
  m_AmbientSkyColor: {{r: 0.212, g: 0.227, b: 0.259, a: 1}}
  m_AmbientEquatorColor: {{r: 0.114, g: 0.125, b: 0.133, a: 1}}
  m_AmbientGroundColor: {{r: 0.047, g: 0.043, b: 0.035, a: 1}}
  m_AmbientIntensity: 1
  m_AmbientMode: 0
  m_SubtractiveShadowColor: {{r: 0.42, g: 0.478, b: 0.627, a: 1}}
  m_SkyboxMaterial: {{fileID: 10304, guid: 0000000000000000f000000000000000, type: 0}}
--- !u!157 &3
LightmapSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 12
  m_GIWorkflowMode: 1"""

    def _directional_light(self, biome: str) -> str:
        # Adjust light color by biome
        light_colors = {
            "forest": {"r": 1, "g": 0.96, "b": 0.84},
            "mountain": {"r": 0.95, "g": 0.95, "b": 1.0},
            "desert": {"r": 1, "g": 0.92, "b": 0.7},
            "swamp": {"r": 0.7, "g": 0.75, "b": 0.65},
            "volcanic": {"r": 1, "g": 0.6, "b": 0.3},
            "cave": {"r": 0.3, "g": 0.3, "b": 0.4},
            "dungeon": {"r": 0.4, "g": 0.35, "b": 0.3},
            "tundra": {"r": 0.85, "g": 0.9, "b": 1.0},
        }
        c = light_colors.get(biome, light_colors["forest"])

        return f"""--- !u!1 &10
GameObject:
  m_ObjectHideFlags: 0
  serializedVersion: 6
  m_Component:
  - component: {{fileID: 11}}
  - component: {{fileID: 12}}
  m_Name: Directional Light
  m_TagString: Untagged
  m_IsActive: 1
--- !u!4 &11
Transform:
  m_ObjectHideFlags: 0
  m_PrefabInstance: {{fileID: 0}}
  m_GameObject: {{fileID: 10}}
  m_LocalRotation: {{x: 0.40821788, y: -0.23456968, z: 0.10938163, w: 0.8754261}}
  m_LocalPosition: {{x: 0, y: 100, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
--- !u!108 &12
Light:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 10}}
  m_Enabled: 1
  serializedVersion: 10
  m_Type: 1
  m_Shape: 0
  m_Color: {{r: {c['r']}, g: {c['g']}, b: {c['b']}, a: 1}}
  m_Intensity: 1.2
  m_Range: 10
  m_SpotAngle: 30
  m_CookieSize: 10
  m_Shadows:
    m_Type: 2
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: 1
    m_Bias: 0.05
    m_NormalBias: 0.4"""

    def _main_camera(self, w: int, h: int) -> str:
        # Position camera to overview the map
        cam_y = max(w, h) * 0.8
        cam_x = w / 2
        cam_z = h / 2
        return f"""--- !u!1 &20
GameObject:
  m_ObjectHideFlags: 0
  serializedVersion: 6
  m_Component:
  - component: {{fileID: 21}}
  - component: {{fileID: 22}}
  m_Name: Main Camera
  m_TagString: MainCamera
  m_IsActive: 1
--- !u!4 &21
Transform:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 20}}
  m_LocalRotation: {{x: 0.7, y: 0, z: 0, w: 0.7}}
  m_LocalPosition: {{x: {cam_x}, y: {cam_y}, z: {cam_z}}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
--- !u!20 &22
Camera:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 20}}
  m_Enabled: 1
  serializedVersion: 2
  m_ClearFlags: 1
  m_BackGroundColor: {{r: 0.19, g: 0.3, b: 0.47, a: 0}}
  m_NormalizedViewPortRect:
    serializedVersion: 2
    x: 0
    y: 0
    width: 1
    height: 1
  near clip plane: 0.3
  far clip plane: 2000
  field of view: 60
  orthographic: 0"""

    def _terrain_object(self, w: int, h: int) -> str:
        return f"""--- !u!1 &50
GameObject:
  m_ObjectHideFlags: 0
  serializedVersion: 6
  m_Component:
  - component: {{fileID: 51}}
  - component: {{fileID: 52}}
  m_Name: Terrain
  m_TagString: Untagged
  m_IsActive: 1
--- !u!4 &51
Transform:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 50}}
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: 0, y: 0, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
--- !u!218 &52
Terrain:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 50}}
  m_Enabled: 1
  serializedVersion: 6
  m_TerrainData: {{fileID: 0}}
  m_TreeDistance: 5000
  m_TreeBillboardDistance: 50
  m_TreeCrossFadeLength: 5
  m_TreeMaximumFullLODCount: 50
  m_DetailObjectDistance: 80
  m_DetailObjectDensity: 1
  m_HeightmapPixelError: 5
  m_SplatMapDistance: 1000
  m_HeightmapMaximumLOD: 0
  m_CastShadows: 1
  m_DrawHeightmap: 1
  m_DrawInstanced: 1
  m_DrawTreesAndFoliage: 1
  m_ReflectionProbeUsage: 1
  m_MaterialType: 0"""

    def _water_plane(self, state: SharedState) -> str:
        """Create a water plane at the average water elevation."""
        water_elev = state.elevation[state.water_mask]
        avg_water_y = float(water_elev.mean()) * 100 if len(water_elev) > 0 else 5
        w, h = state.config.width, state.config.height

        return f"""--- !u!1 &60
GameObject:
  m_ObjectHideFlags: 0
  serializedVersion: 6
  m_Component:
  - component: {{fileID: 61}}
  - component: {{fileID: 62}}
  m_Name: WaterPlane
  m_TagString: Water
  m_IsActive: 1
--- !u!4 &61
Transform:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 60}}
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: {w/2}, y: {avg_water_y:.1f}, z: {h/2}}}
  m_LocalScale: {{x: {w}, y: 1, z: {h}}}
--- !u!33 &62
MeshFilter:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: 60}}
  m_Mesh: {{fileID: 10209, guid: 0000000000000000e000000000000000, type: 0}}"""

    def _game_object(self, entity, base_id: int, map_w: int, map_h: int) -> str:
        """Generate a GameObject entry for a structure."""
        x, y_pos = entity.position
        bw, bh = entity.size
        name = entity.metadata.get("name", f"{entity.entity_type}_{base_id}")
        # Convert 2D position to 3D (x stays, z = y_pos, y = 0)
        unity_x = x
        unity_z = y_pos
        unity_y = 0  # will be adjusted by terrain height at runtime

        return f"""--- !u!1 &{base_id}
GameObject:
  m_ObjectHideFlags: 0
  serializedVersion: 6
  m_Component:
  - component: {{fileID: {base_id + 1}}}
  m_Name: {name}
  m_TagString: Structure
  m_IsActive: 1
--- !u!4 &{base_id + 1}
Transform:
  m_ObjectHideFlags: 0
  m_GameObject: {{fileID: {base_id}}}
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: {unity_x}, y: {unity_y}, z: {unity_z}}}
  m_LocalScale: {{x: {bw}, y: 5, z: {bh}}}"""

    def _build_prefab_manifest(self, state: SharedState) -> dict:
        """Build a manifest mapping entity types to Unity prefab paths."""
        prefab_map = {
            "building": {
                "House": "Prefabs/Buildings/House_01",
                "Tavern": "Prefabs/Buildings/Tavern_01",
                "Shop": "Prefabs/Buildings/Shop_01",
                "Inn": "Prefabs/Buildings/Inn_01",
                "Cottage": "Prefabs/Buildings/Cottage_01",
                "Workshop": "Prefabs/Buildings/Workshop_01",
                "Manor": "Prefabs/Buildings/Manor_01",
                "Guild Hall": "Prefabs/Buildings/GuildHall_01",
                "Castle": "Prefabs/Buildings/Castle_01",
                "Barracks": "Prefabs/Buildings/Barracks_01",
                "Watchtower": "Prefabs/Buildings/Watchtower_01",
                "Tent": "Prefabs/Buildings/Tent_01",
                "Command Tent": "Prefabs/Buildings/CommandTent_01",
            },
            "tree": "Prefabs/Vegetation/Tree_{variant}",
            "bush": "Prefabs/Vegetation/Bush_01",
            "rock": "Prefabs/Props/Rock_{variant}",
            "boulder": "Prefabs/Props/Boulder_01",
            "cactus": "Prefabs/Vegetation/Cactus_01",
            "mushroom": "Prefabs/Vegetation/Mushroom_01",
            "barrel": "Prefabs/Props/Barrel_01",
            "chest": "Prefabs/Props/Chest_01",
            "torch": "Prefabs/Props/Torch_01",
            "crate": "Prefabs/Props/Crate_01",
        }

        # Count what prefabs are needed
        needed = {}
        for entity in state.entities:
            ptype = entity.entity_type
            variant = entity.variant
            key = f"{ptype}_{variant}" if variant else ptype
            needed[key] = needed.get(key, 0) + 1

        return {
            "prefab_mappings": prefab_map,
            "required_prefabs": needed,
            "total_instances": len(state.entities),
            "note": "Map entity types/variants to your project's prefab paths in this file",
        }
