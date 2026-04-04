#!/usr/bin/env python3
"""
CLI interface for the Map Generator multi-agent system.

Usage:
    python cli.py --goal "A dark forest with ruins" --type dungeon --biome forest
    python cli.py --list
    python cli.py --batch --biome mountain
    python cli.py --goal "Peaceful village" --type village --size large --seed 42 --verbose
"""

import argparse
import random
import sys
import time
import os

from map_generator import MapGenerator


# ── Valid options ──

MAP_TYPES = [
    "village", "town", "city",
    "castle", "fort", "tower",
    "dungeon", "cave", "mine", "maze", "treasure_room",
    "crypt", "tomb", "graveyard",
    "temple", "church",
    "shop", "shopping_center", "factory",
    "dock",
    "arena",
    "wilderness", "camp", "outpost", "rest_area", "crash_site",
    "biomes", "region", "open_world", "world_box",
]

BIOMES = [
    "forest", "mountain", "desert", "swamp", "plains",
    "tundra", "volcanic", "cave", "dungeon",
]

SIZES = {
    "small_encounter": 256,
    "medium_encounter": 512,
    "large_encounter": 768,
    "standard": 512,
    "large": 1024,
    "region": 1024,
    "open_world": 1536,
}

# Default goals for batch mode
BATCH_GOALS = {
    "village": "A quaint village with scattered homes and a central well",
    "town": "A bustling town with markets and a town square",
    "city": "A sprawling city with districts and a grand plaza",
    "castle": "A fortified castle on a hilltop with a moat",
    "fort": "A military fort with barracks and watchtowers",
    "tower": "A lonely wizard tower surrounded by arcane gardens",
    "dungeon": "A dark dungeon with twisting corridors and traps",
    "cave": "A natural cave system with underground pools",
    "mine": "An abandoned mine with collapsed tunnels and ore veins",
    "maze": "A bewildering hedge maze with a hidden center",
    "treasure_room": "A vault filled with gold and guarded by traps",
    "crypt": "An ancient crypt with burial chambers and undead",
    "tomb": "A pharaoh's tomb with sealed chambers and treasures",
    "graveyard": "A fog-shrouded graveyard with crumbling headstones",
    "temple": "A sacred temple with an altar and meditation gardens",
    "church": "A stone church with stained glass and a bell tower",
    "shop": "A cozy shop with shelves of goods and a back room",
    "shopping_center": "A grand bazaar with multiple vendor stalls",
    "factory": "An industrial factory with smokestacks and machinery",
    "dock": "A harbor dock with warehouses and moored ships",
    "arena": "A gladiatorial arena with tiered seating and gates",
    "wilderness": "Untamed wilderness with dense vegetation and wildlife",
    "camp": "A traveler's camp with tents around a fire pit",
    "outpost": "A frontier outpost on the edge of civilization",
    "rest_area": "A roadside rest area with a shelter and stream",
    "crash_site": "A mysterious crash site with scattered debris",
    "biomes": "A world showcase with diverse biome regions",
    "region": "A regional map with settlements and trade routes",
    "open_world": "A vast open world with varied terrain and points of interest",
    "world_box": "A sandbox world with oceans, continents, and civilizations",
}


def print_options():
    """Print all available map types, biomes, and sizes."""
    print("\n" + "=" * 60)
    print("  MAP GENERATOR -- Available Options")
    print("=" * 60)

    print("\n  Map Types (30):")
    print("  " + "-" * 40)

    categories = {
        "Settlements":       ["village", "town", "city"],
        "Fortifications":    ["castle", "fort", "tower"],
        "Underground":       ["dungeon", "cave", "mine", "maze", "treasure_room"],
        "Religious/Burial":  ["crypt", "tomb", "graveyard", "temple", "church"],
        "Commercial":        ["shop", "shopping_center", "factory"],
        "Waterfront":        ["dock"],
        "Combat":            ["arena"],
        "Field/Outdoor":     ["wilderness", "camp", "outpost", "rest_area", "crash_site"],
        "Large Scale":       ["biomes", "region", "open_world", "world_box"],
    }
    for category, types in categories.items():
        print(f"    {category:20s}  {', '.join(types)}")

    print(f"\n  Biomes ({len(BIOMES)}):")
    print("  " + "-" * 40)
    print(f"    {', '.join(BIOMES)}")

    print(f"\n  Sizes ({len(SIZES)}):")
    print("  " + "-" * 40)
    for name, px in SIZES.items():
        print(f"    {name:20s}  {px}x{px}")

    print()


def format_time(seconds):
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def print_result_summary(result, elapsed, args):
    """Print a formatted summary of the generation result."""
    status = result.get("status", "unknown")
    map_name = result.get("map_name", "Untitled Map")
    output_path = result.get("output_path", "N/A")
    config = result.get("config", {})
    unity_files = result.get("unity_files", {})

    # Count entities from the result details if available
    entities_placed = 0
    node_results = result.get("node_results", {})
    for node_id, node_result in node_results.items():
        if isinstance(node_result, dict):
            details = node_result.get("details", {})
            entities_placed += details.get("entities_placed", 0)
            entities_placed += details.get("buildings_placed", 0)
            entities_placed += details.get("labels_created", 0)

    print(f"\n{'=' * 60}")
    print(f"  GENERATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Status:         {status}")
    print(f"  Map Name:       {map_name}")
    print(f"  Type:           {config.get('map_type', args.type)}")
    print(f"  Biome:          {config.get('biome', args.biome)}")
    print(f"  Size:           {config.get('width', '?')}x{config.get('height', '?')}")
    print(f"  Seed:           {config.get('seed', args.seed)}")
    print(f"  Planned By:     {config.get('planned_by', 'template')}")
    print(f"  Time Taken:     {format_time(elapsed)}")

    if entities_placed > 0:
        print(f"  Entities:       {entities_placed}")

    if output_path and output_path != "N/A":
        print(f"  PNG Output:     {output_path}")

    if unity_files:
        print(f"  Unity Files:")
        for key, details in unity_files.items():
            out_dir = details.get("output_dir", str(details))
            print(f"    {key:20s} -> {out_dir}")

    print(f"{'=' * 60}\n")


def run_single(args):
    """Generate a single map."""
    gen = MapGenerator(verbose=not args.quiet)

    start = time.time()
    result = gen.generate(
        goal=args.goal,
        map_type=args.type,
        biome=args.biome,
        size=args.size,
        seed=args.seed,
        output_dir=args.output_dir,
        unity_export=not args.no_unity,
    )
    elapsed = time.time() - start

    print_result_summary(result, elapsed, args)
    return result


def run_batch(args):
    """Generate one map for every map type."""
    gen = MapGenerator(verbose=args.verbose)

    results = []
    total_start = time.time()
    failed = 0

    print(f"\n{'#' * 60}")
    print(f"  BATCH MODE -- Generating all {len(MAP_TYPES)} map types")
    print(f"  Biome: {args.biome}  |  Size: {args.size}")
    print(f"{'#' * 60}")

    for i, map_type in enumerate(MAP_TYPES, 1):
        goal = BATCH_GOALS.get(map_type, f"A {map_type} map")
        seed = args.seed + i  # Different seed per map for variety

        print(f"\n  [{i:2d}/{len(MAP_TYPES)}] {map_type}")

        start = time.time()
        try:
            result = gen.generate(
                goal=goal,
                map_type=map_type,
                biome=args.biome,
                size=args.size,
                seed=seed,
                output_dir=args.output_dir,
                unity_export=not args.no_unity,
            )
            elapsed = time.time() - start
            results.append((map_type, result, elapsed))

            status = result.get("status", "unknown")
            output = result.get("output_path", "N/A")
            print(f"         Status: {status}  ({format_time(elapsed)})")
            if output:
                print(f"         Output: {output}")

        except Exception as e:
            elapsed = time.time() - start
            failed += 1
            results.append((map_type, {"status": "error", "error": str(e)}, elapsed))
            print(f"         FAILED: {e}  ({format_time(elapsed)})")

    total_elapsed = time.time() - total_start
    succeeded = len(results) - failed

    print(f"\n{'=' * 60}")
    print(f"  BATCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total Maps:     {len(MAP_TYPES)}")
    print(f"  Succeeded:      {succeeded}")
    print(f"  Failed:         {failed}")
    print(f"  Total Time:     {format_time(total_elapsed)}")
    print(f"  Avg Per Map:    {format_time(total_elapsed / len(MAP_TYPES))}")
    print(f"{'=' * 60}")

    # Summary table
    print(f"\n  {'Type':<20s} {'Status':<12s} {'Time':>8s}  Output")
    print(f"  {'-'*20} {'-'*12} {'-'*8}  {'-'*30}")
    for map_type, result, elapsed in results:
        status = result.get("status", "unknown")
        output = result.get("output_path", "")
        output_short = os.path.basename(output) if output else ""
        print(f"  {map_type:<20s} {status:<12s} {format_time(elapsed):>8s}  {output_short}")

    print()
    return results


def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="mapgen",
        description="Map Generator -- Multi-agent procedural map generation with Unity export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python cli.py --goal "A dark forest with ruins" --type dungeon --biome forest
  python cli.py --goal "Peaceful village by a river" --type village --size large --seed 42
  python cli.py --goal "Desert arena" --type arena --biome desert --no-unity
  python cli.py --batch --biome mountain --size small_encounter
  python cli.py --list
""",
    )

    # Primary arguments
    parser.add_argument(
        "--goal", "-g",
        type=str,
        help="Natural language description of the map to generate (required unless --list or --batch)",
    )
    parser.add_argument(
        "--type", "-t",
        type=str,
        default="village",
        choices=MAP_TYPES,
        metavar="TYPE",
        help=f"Map type (default: village). Use --list to see all options.",
    )
    parser.add_argument(
        "--biome", "-b",
        type=str,
        default="forest",
        choices=BIOMES,
        metavar="BIOME",
        help=f"Biome (default: forest). Use --list to see all options.",
    )
    parser.add_argument(
        "--size", "-s",
        type=str,
        default="standard",
        choices=list(SIZES.keys()),
        metavar="SIZE",
        help=f"Map size preset (default: standard). Use --list to see all options.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: random)",
    )

    # Output options
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--no-unity",
        action="store_true",
        help="Skip Unity export (only generate PNG preview)",
    )

    # Modes
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Show all available map types, biomes, and sizes",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Generate one map for every map type",
    )

    # Verbosity
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Show detailed progress output",
    )
    verbosity.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress progress output (only show final summary)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # --list: show options and exit
    if args.list:
        print_options()
        return 0

    # Default seed to random if not specified
    if args.seed is None:
        args.seed = random.randint(1, 999999)

    # --batch mode
    if args.batch:
        run_batch(args)
        return 0

    # Single generation requires --goal
    if not args.goal:
        parser.error("--goal is required (or use --list / --batch)")

    # Validate type (argparse choices handles this, but be safe)
    if args.type not in MAP_TYPES:
        parser.error(f"Unknown map type '{args.type}'. Use --list to see options.")

    result = run_single(args)

    if result.get("status") == "completed":
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
