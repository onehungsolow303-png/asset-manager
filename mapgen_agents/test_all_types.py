"""Test all map types to verify they generate without errors."""

from map_generator import MapGenerator
import time

gen = MapGenerator(verbose=False)

ALL_TYPES = [
    # Settlements
    ("village", "forest"), ("town", "forest"), ("city", "plains"),
    # Fortifications
    ("castle", "mountain"), ("fort", "forest"), ("tower", "mountain"),
    # Underground / Interior
    ("dungeon", "dungeon"), ("cave", "cave"), ("mine", "cave"),
    ("maze", "dungeon"), ("treasure_room", "dungeon"),
    # Religious / Burial
    ("crypt", "dungeon"), ("tomb", "dungeon"), ("graveyard", "forest"),
    ("temple", "plains"), ("church", "forest"),
    # Commercial / Industrial
    ("shop", "forest"), ("shopping_center", "plains"), ("factory", "plains"),
    # Waterfront
    ("dock", "plains"),
    # Combat
    ("arena", "desert"),
    # Field / Outdoor
    ("wilderness", "forest"), ("camp", "desert"), ("outpost", "tundra"),
    ("rest_area", "forest"), ("crash_site", "plains"),
    # Large scale
    ("biomes", "forest"), ("region", "forest"), ("open_world", "mountain"),
    ("world_box", "forest"),
]

results = []
total_start = time.time()

for map_type, biome in ALL_TYPES:
    start = time.time()
    try:
        result = gen.generate(
            goal=f"Test {map_type}",
            map_type=map_type,
            biome=biome,
            size="small_encounter",  # 256x256 for speed
            seed=42,
            unity_export=False,  # skip Unity export for speed
        )
        elapsed = time.time() - start
        status = result["status"]
        name = result.get("map_name", "?")
        print(f"  [{'OK' if status == 'completed' else 'FAIL'}] {map_type:16s} ({biome:8s}) - {elapsed:.1f}s - {name}")
        results.append((map_type, status))
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERR] {map_type:16s} ({biome:8s}) - {elapsed:.1f}s - {e}")
        results.append((map_type, "error"))

total = time.time() - total_start
passed = sum(1 for _, s in results if s == "completed")
failed = len(results) - passed

print(f"\n{'='*50}")
print(f"  {passed}/{len(results)} passed | {failed} failed | {total:.1f}s total")
print(f"{'='*50}")

if failed > 0:
    print("\nFailed:")
    for mt, s in results:
        if s != "completed":
            print(f"  - {mt}: {s}")
