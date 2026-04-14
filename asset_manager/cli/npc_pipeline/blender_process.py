"""
Blender headless script for processing Tripo3D GLB NPC models.

Imports a GLB, analyzes mesh bounding boxes to label parts semantically
(head, torso, arms, legs, weapon, etc.), applies basic PBR material
placeholders per part category, and exports a processed GLB.

Usage (headless):
    blender --background --python blender_process.py -- <input.glb> <output_dir>

The script:
1. Imports the GLB file
2. Analyzes each mesh part's bounding box center + extents
3. Classifies parts into semantic categories by spatial position
4. Renames meshes from "meshes[N]" to "{category}_{index}"
5. Assigns color-coded materials per category for visual identification
6. Exports processed GLB with labeled parts
"""

import json
import math
import sys
from pathlib import Path

try:
    import bpy
    import mathutils
except ImportError:
    # bpy/mathutils only available inside Blender's embedded Python.
    # Guard so asset_manager import tests don't fail outside Blender.
    bpy = None  # type: ignore[assignment]
    mathutils = None  # type: ignore[assignment]

# ── Part classification by spatial analysis ──────────────────────────

# Categories and their expected vertical zones (normalized 0=feet, 1=top)
CATEGORIES = {
    "head": {"y_min": 0.82, "y_max": 1.0, "priority": 1},
    "hair": {"y_min": 0.90, "y_max": 1.0, "priority": 2},  # top of head
    "neck": {"y_min": 0.78, "y_max": 0.85, "priority": 3},
    "shoulder": {"y_min": 0.68, "y_max": 0.82, "priority": 4},
    "upper_body": {"y_min": 0.55, "y_max": 0.78, "priority": 5},
    "arm": {"y_min": 0.35, "y_max": 0.75, "priority": 6},  # wide X spread
    "hand": {"y_min": 0.25, "y_max": 0.55, "priority": 7},  # far from center X
    "belt": {"y_min": 0.45, "y_max": 0.55, "priority": 8},
    "lower_body": {"y_min": 0.25, "y_max": 0.50, "priority": 9},
    "leg": {"y_min": 0.05, "y_max": 0.35, "priority": 10},
    "foot": {"y_min": 0.0, "y_max": 0.10, "priority": 11},
    "weapon": {"y_min": 0.0, "y_max": 1.0, "priority": 12},  # detached
    "accessory": {"y_min": 0.0, "y_max": 1.0, "priority": 13},  # fallback
}

# Material colors per category (R, G, B, A) — realistic PBR base colors
CATEGORY_COLORS = {
    "head": (0.82, 0.66, 0.52, 1.0),  # warm skin tone
    "hair": (0.15, 0.1, 0.07, 1.0),  # dark brown hair
    "neck": (0.78, 0.62, 0.48, 1.0),  # skin slightly darker
    "shoulder": (0.45, 0.43, 0.42, 1.0),  # dark iron
    "upper_body": (0.35, 0.22, 0.12, 1.0),  # worn leather
    "arm": (0.48, 0.46, 0.44, 1.0),  # chainmail
    "hand": (0.82, 0.66, 0.52, 1.0),  # skin
    "belt": (0.25, 0.16, 0.08, 1.0),  # dark leather
    "lower_body": (0.30, 0.18, 0.10, 1.0),  # leather pants
    "leg": (0.45, 0.43, 0.42, 1.0),  # iron greaves
    "foot": (0.25, 0.20, 0.15, 1.0),  # dark boots
    "weapon": (0.65, 0.63, 0.60, 1.0),  # polished steel
    "accessory": (0.72, 0.58, 0.20, 1.0),  # gold accent
    "cape": (0.45, 0.08, 0.08, 1.0),  # deep crimson
    "shield": (0.50, 0.48, 0.45, 1.0),  # worn steel
}


def get_mesh_bounds(obj):
    """Get world-space bounding box center and dimensions for a mesh object."""
    bbox_corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [c.x for c in bbox_corners]
    ys = [c.y for c in bbox_corners]
    zs = [c.z for c in bbox_corners]

    center = mathutils.Vector(
        (
            (min(xs) + max(xs)) / 2,
            (min(ys) + max(ys)) / 2,
            (min(zs) + max(zs)) / 2,
        )
    )
    dims = mathutils.Vector(
        (
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
        )
    )
    return center, dims, min(zs), max(zs)


def get_model_bounds(mesh_objects):
    """Get overall model bounds from all meshes."""
    all_min_z = float("inf")
    all_max_z = float("-inf")
    all_min_x = float("inf")
    all_max_x = float("inf")

    for obj in mesh_objects:
        _, _, min_z, max_z = get_mesh_bounds(obj)
        bbox_corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
        xs = [c.x for c in bbox_corners]
        all_min_z = min(all_min_z, min_z)
        all_max_z = max(all_max_z, max_z)
        all_min_x = min(all_min_x, min(xs))
        all_max_x = max(all_max_x, max(xs))

    return all_min_z, all_max_z, all_min_x, all_max_x


def is_detached(obj, mesh_objects, model_center_x, threshold=0.3):
    """Check if a mesh is likely detached from the main body (weapon/accessory)."""
    center, dims, _, _ = get_mesh_bounds(obj)

    # Elongated shape (one dimension much larger) suggests weapon
    max_dim = max(dims.x, dims.y, dims.z)
    min_dim = min(dims.x, dims.y, dims.z)
    elongation = max_dim / min_dim if min_dim > 0.001 else 1

    if elongation > 5:
        return "weapon"

    return None


def classify_part(obj, mesh_objects, model_min_z, model_max_z, model_center_x):
    """Classify a mesh part based on spatial analysis."""
    center, dims, min_z, max_z = get_mesh_bounds(obj)
    model_height = model_max_z - model_min_z
    if model_height < 0.001:
        return "accessory"

    # Normalize vertical position (0=feet, 1=top of head)
    # Note: in Blender Z is up for imported GLBs with bottom-center pivot
    norm_center = (center.z - model_min_z) / model_height
    norm_bottom = (min_z - model_min_z) / model_height
    norm_top = (max_z - model_min_z) / model_height

    # Check if detached (weapon)
    detached = is_detached(obj, mesh_objects, model_center_x)
    if detached:
        return detached

    # Vertical classification
    if norm_bottom > 0.85:
        return "hair" if dims.x * dims.y * dims.z < 0.001 else "head"
    if norm_bottom > 0.75:
        return "head"
    if norm_bottom > 0.68 and norm_top < 0.85:
        return "neck" if dims.z < model_height * 0.08 else "shoulder"
    if norm_center > 0.55 and norm_bottom > 0.45:
        # Check X spread for arms vs torso
        if abs(center.x - model_center_x) > model_height * 0.15:
            return "arm"
        return "upper_body"
    if norm_center > 0.42 and norm_center < 0.55:
        if dims.z < model_height * 0.1:
            return "belt"
        if abs(center.x - model_center_x) > model_height * 0.12:
            return "hand"
        return "upper_body"
    if norm_center > 0.2 and norm_center < 0.45:
        return "lower_body"
    if norm_center > 0.08 and norm_center < 0.25:
        return "leg"
    if norm_top < 0.12:
        return "foot"

    return "accessory"


def create_category_material(category_name):
    """Create a PBR material with realistic metallic/roughness per category."""
    mat_name = f"NPC_{category_name}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            color = CATEGORY_COLORS.get(category_name, (0.5, 0.5, 0.5, 1.0))
            bsdf.inputs["Base Color"].default_value = color
            # Skin parts — soft, non-metallic
            if category_name in ("head", "hand", "neck"):
                bsdf.inputs["Metallic"].default_value = 0.0
                bsdf.inputs["Roughness"].default_value = 0.65
            # Metal armor — highly reflective
            elif category_name in ("weapon", "shoulder", "arm", "leg", "shield"):
                bsdf.inputs["Metallic"].default_value = 0.9
                bsdf.inputs["Roughness"].default_value = 0.25
            # Leather — matte, non-metallic
            elif category_name in ("upper_body", "belt", "lower_body", "foot"):
                bsdf.inputs["Metallic"].default_value = 0.0
                bsdf.inputs["Roughness"].default_value = 0.8
            # Hair — slight sheen
            elif category_name == "hair":
                bsdf.inputs["Metallic"].default_value = 0.0
                bsdf.inputs["Roughness"].default_value = 0.5
            # Cape/cloth — very matte
            elif category_name == "cape":
                bsdf.inputs["Metallic"].default_value = 0.0
                bsdf.inputs["Roughness"].default_value = 0.9
            # Accessory/gold — highly metallic, polished
            elif category_name == "accessory":
                bsdf.inputs["Metallic"].default_value = 0.95
                bsdf.inputs["Roughness"].default_value = 0.2
            else:
                bsdf.inputs["Metallic"].default_value = 0.1
                bsdf.inputs["Roughness"].default_value = 0.6
    return mat


# ── Auto-rigging + skeletal animation ─────────────────────────────


def create_simple_armature(model_height):
    """Create a basic humanoid armature scaled to the model.

    Builds a spine chain, left/right arms, left/right legs, and a head bone.
    All proportions are relative to *model_height* so the rig fits any mesh.
    """
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "Armature"

    # Get the base bone (created by armature_add)
    edit_bones = armature.data.edit_bones

    # Remove default bone
    for b in list(edit_bones):
        edit_bones.remove(b)

    h = model_height

    # ── Spine chain ──
    root = edit_bones.new("Root")
    root.head = (0, 0, 0)
    root.tail = (0, 0, h * 0.1)

    spine = edit_bones.new("Spine")
    spine.head = (0, 0, h * 0.1)
    spine.tail = (0, 0, h * 0.4)
    spine.parent = root

    chest = edit_bones.new("Chest")
    chest.head = (0, 0, h * 0.4)
    chest.tail = (0, 0, h * 0.6)
    chest.parent = spine

    neck = edit_bones.new("Neck")
    neck.head = (0, 0, h * 0.6)
    neck.tail = (0, 0, h * 0.7)
    neck.parent = chest

    head_bone = edit_bones.new("Head")
    head_bone.head = (0, 0, h * 0.7)
    head_bone.tail = (0, 0, h * 0.9)
    head_bone.parent = neck

    # ── Arms (left / right) ──
    for side, x_sign in [("L", 1), ("R", -1)]:
        shoulder = edit_bones.new(f"Shoulder.{side}")
        shoulder.head = (0, 0, h * 0.58)
        shoulder.tail = (x_sign * h * 0.15, 0, h * 0.58)
        shoulder.parent = chest

        upper_arm = edit_bones.new(f"UpperArm.{side}")
        upper_arm.head = (x_sign * h * 0.15, 0, h * 0.58)
        upper_arm.tail = (x_sign * h * 0.3, 0, h * 0.4)
        upper_arm.parent = shoulder

        lower_arm = edit_bones.new(f"LowerArm.{side}")
        lower_arm.head = (x_sign * h * 0.3, 0, h * 0.4)
        lower_arm.tail = (x_sign * h * 0.4, 0, h * 0.25)
        lower_arm.parent = upper_arm

        hand = edit_bones.new(f"Hand.{side}")
        hand.head = (x_sign * h * 0.4, 0, h * 0.25)
        hand.tail = (x_sign * h * 0.45, 0, h * 0.2)
        hand.parent = lower_arm

    # ── Legs (left / right) ──
    for side, x_sign in [("L", 1), ("R", -1)]:
        upper_leg = edit_bones.new(f"UpperLeg.{side}")
        upper_leg.head = (x_sign * h * 0.08, 0, h * 0.1)
        upper_leg.tail = (x_sign * h * 0.08, 0.02, h * 0.05)
        upper_leg.parent = root

        lower_leg = edit_bones.new(f"LowerLeg.{side}")
        lower_leg.head = upper_leg.tail
        lower_leg.tail = (x_sign * h * 0.08, -0.01, 0)
        lower_leg.parent = upper_leg

        foot = edit_bones.new(f"Foot.{side}")
        foot.head = lower_leg.tail
        foot.tail = (x_sign * h * 0.08, -h * 0.05, 0)
        foot.parent = lower_leg

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def parent_meshes_to_armature(armature):
    """Parent all mesh objects to the armature with automatic weights.

    Falls back to envelope weights when auto-weights fail (e.g. non-manifold
    meshes from Tripo3D).
    """
    bpy.ops.object.select_all(action="DESELECT")

    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    for mesh_obj in meshes:
        mesh_obj.select_set(True)

    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError:
        # Auto weights can fail on complex / non-manifold meshes — fall back
        bpy.ops.object.parent_set(type="ARMATURE_ENVELOPE")


def _key_bone(armature, bone_name, frame, rotation_euler=None, location=None):
    """Insert a keyframe on a single pose bone."""
    bone = armature.pose.bones.get(bone_name)
    if not bone:
        return
    if rotation_euler is not None:
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = rotation_euler
        bone.keyframe_insert(data_path="rotation_euler", frame=frame)
    if location is not None:
        bone.location = location
        bone.keyframe_insert(data_path="location", frame=frame)


def _reset_pose(armature):
    """Zero-out all pose bone transforms."""
    for bone in armature.pose.bones:
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = (0, 0, 0)
        bone.location = (0, 0, 0)


def create_animations(armature, model_height):
    """Create 4 basic animation actions: Idle, Attack, Hit, Death.

    Each action is stored as a separate Blender Action with ``use_fake_user``
    so it survives garbage collection and exports as a separate GLB animation
    clip.
    """
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")

    h = model_height  # noqa: F841 — kept for readability in keyframe math

    def kb(bone_name, frame, rotation_euler=None, location=None):
        _key_bone(armature, bone_name, frame, rotation_euler, location)

    # ── IDLE (48 frames, looping gentle sway) ────────────────────
    action = bpy.data.actions.new("Idle")
    armature.animation_data_create()
    armature.animation_data.action = action

    _reset_pose(armature)
    kb("Spine", 1, rotation_euler=(0, 0, 0))
    kb("Chest", 1, rotation_euler=(0, 0, 0))
    kb("Head", 1, rotation_euler=(0, 0, 0))

    kb("Spine", 12, rotation_euler=(math.radians(2), 0, 0))
    kb("Chest", 12, rotation_euler=(math.radians(-1), 0, math.radians(1)))

    kb("Spine", 24, rotation_euler=(0, 0, 0))
    kb("Chest", 24, rotation_euler=(0, 0, 0))

    kb("Spine", 36, rotation_euler=(math.radians(-2), 0, 0))
    kb("Chest", 36, rotation_euler=(math.radians(1), 0, math.radians(-1)))

    kb("Spine", 48, rotation_euler=(0, 0, 0))
    kb("Chest", 48, rotation_euler=(0, 0, 0))

    action.use_fake_user = True

    # ── ATTACK (18 frames, forward lunge + arm swing) ────────────
    action = bpy.data.actions.new("Attack")
    armature.animation_data.action = action

    _reset_pose(armature)
    kb("Root", 1, location=(0, 0, 0))
    kb("Chest", 1, rotation_euler=(0, 0, 0))
    kb("UpperArm.R", 1, rotation_euler=(0, 0, 0))

    # Windup (lean back)
    kb("Chest", 4, rotation_euler=(math.radians(-15), 0, 0))
    kb("UpperArm.R", 4, rotation_euler=(math.radians(-60), 0, 0))

    # Strike (lunge forward + arm swing)
    kb("Root", 8, location=(0, -0.3, 0))
    kb("Chest", 8, rotation_euler=(math.radians(20), 0, 0))
    kb("UpperArm.R", 8, rotation_euler=(math.radians(45), 0, 0))

    # Recovery
    kb("Root", 14, location=(0, -0.1, 0))
    kb("Chest", 14, rotation_euler=(math.radians(5), 0, 0))
    kb("UpperArm.R", 14, rotation_euler=(math.radians(10), 0, 0))

    kb("Root", 18, location=(0, 0, 0))
    kb("Chest", 18, rotation_euler=(0, 0, 0))
    kb("UpperArm.R", 18, rotation_euler=(0, 0, 0))

    action.use_fake_user = True

    # ── HIT (12 frames, recoil) ──────────────────────────────────
    action = bpy.data.actions.new("Hit")
    armature.animation_data.action = action

    _reset_pose(armature)
    kb("Root", 1, location=(0, 0, 0))
    kb("Chest", 1, rotation_euler=(0, 0, 0))

    # Impact recoil
    kb("Root", 3, location=(0, 0.15, 0))
    kb("Chest", 3, rotation_euler=(math.radians(-10), 0, math.radians(5)))

    # Recovery
    kb("Root", 8, location=(0, 0.05, 0))
    kb("Chest", 8, rotation_euler=(math.radians(-3), 0, 0))

    kb("Root", 12, location=(0, 0, 0))
    kb("Chest", 12, rotation_euler=(0, 0, 0))

    action.use_fake_user = True

    # ── DEATH (24 frames, fall backward) ─────────────────────────
    action = bpy.data.actions.new("Death")
    armature.animation_data.action = action

    _reset_pose(armature)
    kb("Root", 1, location=(0, 0, 0), rotation_euler=(0, 0, 0))
    kb("Spine", 1, rotation_euler=(0, 0, 0))
    kb("Head", 1, rotation_euler=(0, 0, 0))

    # Stagger
    kb("Spine", 6, rotation_euler=(math.radians(-15), 0, math.radians(5)))
    kb("Head", 6, rotation_euler=(math.radians(-10), 0, 0))

    # Fall
    kb("Root", 16, rotation_euler=(math.radians(-80), 0, 0))
    kb("Root", 16, location=(0, 0.3, -h * 0.3))
    kb("Spine", 16, rotation_euler=(math.radians(-10), 0, 0))

    # Ground
    kb("Root", 24, rotation_euler=(math.radians(-90), 0, 0))
    kb("Root", 24, location=(0, 0.4, -h * 0.4))

    action.use_fake_user = True

    bpy.ops.object.mode_set(mode="OBJECT")
    print("[NPC Pipeline] Created 4 animations (Idle/Attack/Hit/Death)")


def process_glb(input_path, output_dir):
    """Main processing function."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name = input_path.stem
    print(f"[NPC Pipeline] Processing: {model_name}")

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Import GLB
    bpy.ops.import_scene.gltf(filepath=str(input_path))

    # Gather mesh objects
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    print(f"[NPC Pipeline] Found {len(mesh_objects)} mesh parts")

    if not mesh_objects:
        print("[NPC Pipeline] ERROR: No mesh objects found!")
        return None

    # Get overall model bounds
    model_min_z, model_max_z, model_min_x, model_max_x = get_model_bounds(mesh_objects)
    model_center_x = (model_min_x + model_max_x) / 2

    # Classify and rename each part
    category_counts = {}
    part_manifest = []

    for obj in mesh_objects:
        category = classify_part(obj, mesh_objects, model_min_z, model_max_z, model_center_x)

        # Count for unique naming
        idx = category_counts.get(category, 0)
        category_counts[category] = idx + 1

        new_name = f"{category}_{idx}"
        old_name = obj.name
        obj.name = new_name

        # Apply category material
        mat = create_category_material(category)
        obj.data.materials.clear()
        obj.data.materials.append(mat)

        # Record bounds for manifest
        center, dims, _, _ = get_mesh_bounds(obj)
        part_manifest.append(
            {
                "name": new_name,
                "original_name": old_name,
                "category": category,
                "center": [round(c, 4) for c in center],
                "dimensions": [round(d, 4) for d in dims],
                "vertex_count": len(obj.data.vertices),
                "face_count": len(obj.data.polygons),
            }
        )

        print(f"  {old_name} -> {new_name} ({len(obj.data.vertices)} verts)")

    # Export processed GLB
    output_glb = output_dir / f"{model_name}.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
    )
    print(f"[NPC Pipeline] Exported: {output_glb}")

    # Write manifest JSON
    manifest = {
        "model_name": model_name,
        "source_file": str(input_path),
        "total_parts": len(mesh_objects),
        "categories": {k: v for k, v in sorted(category_counts.items())},
        "parts": part_manifest,
    }

    manifest_path = output_dir / f"{model_name}.manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[NPC Pipeline] Manifest: {manifest_path}")

    return manifest


# ── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    # Args come after "--" in Blender CLI
    argv = sys.argv
    try:
        idx = argv.index("--")
        args = argv[idx + 1 :]
    except ValueError:
        args = []

    if len(args) < 2:
        print("Usage: blender --background --python blender_process.py -- <input.glb> <output_dir>")
        sys.exit(1)

    input_glb = args[0]
    output_dir = args[1]

    result = process_glb(input_glb, output_dir)
    if result:
        print(
            f"[NPC Pipeline] Done: {result['total_parts']} parts in {len(result['categories'])} categories"
        )
    else:
        print("[NPC Pipeline] FAILED")
        sys.exit(1)
