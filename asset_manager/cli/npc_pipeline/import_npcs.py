"""
NPC Model Import Pipeline — Orchestrator

Scans the NPC source folder for new/updated GLB models, runs Blender
headless processing on each, copies results to Unity project, and
registers them in the Asset Manager catalog.

Tracks processed files in a manifest to avoid re-processing unchanged models.

Usage:
    python -m asset_manager.cli.npc_pipeline.import_npcs
    python -m asset_manager.cli.npc_pipeline.import_npcs --force  # reprocess all
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────

NPC_SOURCE_DIR = Path("C:/Pictures/Assets/NPCs")
BLENDER_OUTPUT_DIR = Path("C:/Dev/Asset Manager/asset_manager/cli/npc_pipeline/_processed")
UNITY_NPC_DIR = Path("C:/Dev/Forever engine/Assets/GeneratedModels/NPCs")
PIPELINE_DIR = Path(__file__).parent
BLENDER_SCRIPT = PIPELINE_DIR / "blender_process.py"
STATE_FILE = PIPELINE_DIR / "_import_state.json"

# Blender executable — try common locations
BLENDER_PATHS = [
    "C:/Dev/tools/blender-4.4.0-windows-x64/blender.exe",  # portable install
    "blender",  # in PATH
    "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 4.3/blender.exe",
    "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe",
]


def find_blender() -> str | None:
    """Find Blender executable."""
    for path in BLENDER_PATHS:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                print(f"[Pipeline] Found Blender: {path} ({version})")
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def file_hash(path: Path) -> str:
    """Quick hash of file for change detection (size + mtime)."""
    stat = path.stat()
    return hashlib.md5(f"{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()


def load_state() -> dict:
    """Load processing state from disk."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}, "last_run": None}


def save_state(state: dict):
    """Persist processing state."""
    state["last_run"] = datetime.now(UTC).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def scan_new_models(state: dict, force: bool = False) -> list[Path]:
    """Find GLB files that are new or changed since last processing."""
    if not NPC_SOURCE_DIR.exists():
        print(f"[Pipeline] Source directory not found: {NPC_SOURCE_DIR}")
        return []

    new_models = []
    for glb in sorted(NPC_SOURCE_DIR.rglob("*.glb")):
        # Use relative path as key to handle subdirectories (e.g. Monsters/)
        rel_key = str(glb.relative_to(NPC_SOURCE_DIR))
        fhash = file_hash(glb)
        if (
            force
            or rel_key not in state["processed"]
            or state["processed"][rel_key]["hash"] != fhash
        ):
            new_models.append(glb)

    return new_models


def process_model(blender_exe: str, glb_path: Path) -> dict | None:
    """Run Blender headless processing on a single GLB."""
    model_name = glb_path.stem
    output_dir = BLENDER_OUTPUT_DIR / model_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[Pipeline] Processing: {glb_path.name}")
    print(f"  Output: {output_dir}")

    cmd = [
        blender_exe,
        "--background",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        str(glb_path),
        str(output_dir),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max per model
        )

        # Print Blender output (filtered to our log lines)
        for line in result.stdout.split("\n"):
            if "[NPC Pipeline]" in line:
                print(f"  {line.strip()}")

        if result.returncode != 0:
            print(f"  ERROR: Blender exited with code {result.returncode}")
            for line in result.stderr.split("\n")[-10:]:
                if line.strip():
                    print(f"  STDERR: {line.strip()}")
            return None

        # Read the manifest
        manifest_path = output_dir / f"{model_name}.manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        else:
            print("  ERROR: No manifest generated")
            return None

    except subprocess.TimeoutExpired:
        print("  ERROR: Blender timed out after 300s")
        return None


def copy_to_unity(model_name: str, processed_dir: Path) -> bool:
    """Copy processed GLB and manifest to Unity project."""
    unity_model_dir = UNITY_NPC_DIR / model_name
    unity_model_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src_file in processed_dir.iterdir():
        if src_file.suffix in (".glb", ".json"):
            dst = unity_model_dir / src_file.name
            shutil.copy2(src_file, dst)
            copied += 1
            print(f"  Copied: {dst}")

    return copied > 0


def register_in_catalog(model_name: str, manifest: dict) -> bool:
    """Register the model in Asset Manager's catalog."""
    try:
        # Parse race, gender, class from filename
        parts = model_name.lower().split()
        race = parts[0] if len(parts) > 0 else "unknown"
        gender = parts[1] if len(parts) > 1 else "unknown"
        char_class = parts[2] if len(parts) > 2 else "unknown"

        # Build tags
        tags = [race, gender, char_class, "npc", "3d", "tripo", "parts"]
        tags = list(set(tags))  # deduplicate

        glb_path = UNITY_NPC_DIR / model_name / f"{model_name}.glb"

        cmd = [
            sys.executable,
            "-m",
            "asset_manager.cli.register_3d_model",
            model_name.replace(" ", "_").lower(),
            str(glb_path),
            "--kind",
            "character",
            "--tags",
            ",".join(tags),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="C:/Dev/Asset Manager",
        )

        if result.returncode == 0:
            print(f"  Registered in catalog: {model_name}")
            return True
        else:
            print(f"  Catalog registration failed: {result.stderr.strip()[:200]}")
            return False

    except Exception as e:
        print(f"  Catalog registration error: {e}")
        return False


def run_pipeline(force: bool = False):
    """Main pipeline execution."""
    print("=" * 60)
    print("[Pipeline] NPC Model Import Pipeline")
    print(f"[Pipeline] Source: {NPC_SOURCE_DIR}")
    print(f"[Pipeline] Unity target: {UNITY_NPC_DIR}")
    print(f"[Pipeline] Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Find Blender
    blender_exe = find_blender()
    if not blender_exe:
        print(
            "[Pipeline] ERROR: Blender not found! Install via: winget install BlenderFoundation.Blender"
        )
        sys.exit(1)

    # Ensure directories exist
    BLENDER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UNITY_NPC_DIR.mkdir(parents=True, exist_ok=True)

    # Load state and scan for new models
    state = load_state()
    new_models = scan_new_models(state, force=force)

    if not new_models:
        print("[Pipeline] No new or changed models to process.")
        return

    print(f"[Pipeline] Found {len(new_models)} model(s) to process")

    # Process each model
    success = 0
    failed = 0

    for glb_path in new_models:
        model_name = glb_path.stem.strip()  # Strip trailing spaces from filenames
        rel_key = str(glb_path.relative_to(NPC_SOURCE_DIR))

        # Determine if this is a monster (in Monsters/ subfolder) vs NPC
        is_monster = "Monsters" in str(glb_path.relative_to(NPC_SOURCE_DIR))
        unity_base = Path("C:/Dev/Forever engine/Assets/GeneratedModels")
        unity_subdir = unity_base / ("Monsters" if is_monster else "NPCs")
        unity_subdir.mkdir(parents=True, exist_ok=True)

        # 1. Run Blender processing
        manifest = process_model(blender_exe, glb_path)
        if not manifest:
            failed += 1
            continue

        # 2. Copy to Unity (monsters to Monsters/, NPCs to NPCs/)
        processed_dir = BLENDER_OUTPUT_DIR / model_name
        unity_model_dir = unity_subdir / model_name
        unity_model_dir.mkdir(parents=True, exist_ok=True)
        for src_file in processed_dir.iterdir():
            if src_file.suffix in (".glb", ".json"):
                dst = unity_model_dir / src_file.name
                shutil.copy2(src_file, dst)
                print(f"  Copied: {dst}")

        # 3. Register in catalog
        register_in_catalog(model_name, manifest)

        # 4. Update state
        state["processed"][rel_key] = {
            "hash": file_hash(glb_path),
            "processed_at": datetime.now(UTC).isoformat(),
            "parts": manifest.get("total_parts", 0),
            "categories": manifest.get("categories", {}),
        }
        save_state(state)
        success += 1

    # Summary
    print("\n" + "=" * 60)
    print(
        f"[Pipeline] Complete: {success} processed, {failed} failed, "
        f"{len(state['processed'])} total in catalog"
    )
    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NPC Model Import Pipeline")
    parser.add_argument("--force", action="store_true", help="Reprocess all models")
    args = parser.parse_args()
    run_pipeline(force=args.force)
