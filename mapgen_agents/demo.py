"""
Demo script — Generates multiple map types to showcase the system.
"""

from map_generator import MapGenerator
import time


def main():
    gen = MapGenerator(verbose=True)

    demos = [
        {
            "goal": "A peaceful forest village with a river and cottages",
            "map_type": "village",
            "biome": "forest",
            "size": "medium_encounter",
            "seed": 42,
        },
        {
            "goal": "A dark dungeon with connected chambers and hidden treasures",
            "map_type": "dungeon",
            "biome": "dungeon",
            "size": "medium_encounter",
            "seed": 777,
        },
        {
            "goal": "A mountain outpost overlooking a valley",
            "map_type": "outpost",
            "biome": "mountain",
            "size": "medium_encounter",
            "seed": 123,
        },
        {
            "goal": "A vast desert wilderness with scattered oases",
            "map_type": "wilderness",
            "biome": "desert",
            "size": "medium_encounter",
            "seed": 555,
        },
    ]

    results = []
    total_start = time.time()

    for demo in demos:
        print(f"\n{'*'*60}")
        print(f"  Generating: {demo['map_type']} ({demo['biome']})")
        print(f"{'*'*60}")

        result = gen.generate(**demo)
        results.append(result)

        print(f"  -> Status: {result['status']}")
        print(f"  -> Output: {result.get('output_path', 'N/A')}")
        print(f"  -> Name: {result.get('map_name', 'N/A')}")

    total_time = time.time() - total_start

    print(f"\n{'='*60}")
    print(f"  DEMO COMPLETE")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Maps generated: {len(results)}")
    print(f"  Successful: {sum(1 for r in results if r['status'] == 'completed')}")
    print(f"{'='*60}")

    for r in results:
        if r.get("output_path"):
            print(f"  {r['config']['map_type']:12s} -> {r['output_path']}")


if __name__ == "__main__":
    main()
