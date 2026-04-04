"""
MapGenerator — Main entry point that ties all three tiers together.
Now supports Claude API for intelligent planning and Unity export pipeline.

Usage:
    gen = MapGenerator(api_key="sk-ant-...")  # or set ANTHROPIC_API_KEY env var
    result = gen.generate(
        goal="A forest village with a river and tavern",
        map_type="village",
        biome="forest",
        size="medium_encounter",
        seed=42,
        unity_export=True,
    )
"""

from planner import StrategicPlanner
from orchestrator import Orchestrator
from shared_state import SharedState, MapConfig
from llm_adapter import create_adapter
from typing import Optional


class MapGenerator:
    """
    Top-level API for the multi-agent map generation system.
    Supports both Claude-powered and template-based planning.
    Outputs: PNG preview + full Unity project files (scenes, scripts, terrain, tilemaps).
    """

    def __init__(self, api_key: str = None, verbose: bool = True):
        """
        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
                     If no key available, falls back to template-based planning.
            verbose: Print progress to stdout.
        """
        self.verbose = verbose
        llm = create_adapter(api_key=api_key, provider="claude")
        self.planner = StrategicPlanner(llm=llm)

    def generate(self, goal: str, map_type: str = "village",
                 biome: str = "forest", size: str = "standard",
                 seed: int = 42, output_path: str = None,
                 unity_export: bool = True,
                 output_dir: str = "/sessions/brave-busy-fermat/mnt/outputs/unity_export",
                 **kwargs) -> dict:
        """
        Generate a complete map from a natural language goal.

        Args:
            goal: Description of the desired map
            map_type: village, city, dungeon, cave, arena, wilderness, camp, outpost, open_world
            biome: forest, mountain, desert, swamp, plains, tundra, volcanic, cave, dungeon
            size: small_encounter, medium_encounter, large_encounter, standard, large, open_world
            seed: Random seed for reproducibility
            output_path: Override PNG output file path
            unity_export: Generate Unity project files (terrain, scenes, scripts, tilemaps)
            output_dir: Directory for Unity export files

        Returns:
            Dict with status, output_path, unity_files, and generation details
        """
        if self.verbose:
            print(f"\n{'#'*60}")
            print(f"  MAP GENERATOR (Unity Pipeline)")
            print(f"  Goal: {goal}")
            print(f"  Type: {map_type} | Biome: {biome} | Size: {size}")
            print(f"  Unity Export: {unity_export}")
            print(f"{'#'*60}")

        if output_path:
            kwargs["output_path"] = output_path
        kwargs["output_dir"] = output_dir

        # TIER 1: Strategic Planning (Claude API or templates)
        dag, config = self.planner.plan(
            goal=goal,
            map_type=map_type,
            biome=biome,
            size=size,
            seed=seed,
            unity_export=unity_export,
            **kwargs
        )

        if self.verbose:
            planned_by = config.get("planned_by", "template")
            print(f"\n[PLANNER] DAG created by: {planned_by}")
            print(dag)

        # Initialize shared state
        map_config = MapConfig(
            width=config["width"],
            height=config["height"],
            biome=config["biome"],
            map_type=config["map_type"],
            seed=config["seed"],
        )
        shared_state = SharedState(map_config)

        # TIER 2: Orchestration
        orchestrator = Orchestrator(shared_state, verbose=self.verbose)

        # TIER 3: Execution
        result = orchestrator.execute_dag(dag)

        # Gather output paths
        render_node = dag.nodes.get("render")
        output_file = None
        if render_node and render_node.result:
            details = render_node.result.get("details", {})
            output_file = details.get("output_path")

        unity_files = {}
        for unity_task in ["unity_terrain", "unity_scene", "unity_csharp", "unity_tilemap"]:
            node = dag.nodes.get(unity_task)
            if node and node.result:
                unity_files[unity_task] = node.result.get("details", {})

        return {
            **result,
            "output_path": output_file,
            "unity_files": unity_files,
            "config": config,
            "map_name": shared_state.metadata.get("map_name", "Untitled Map"),
        }

    def list_options(self) -> dict:
        """List all available map types, biomes, and sizes."""
        return {
            "map_types": self.planner.list_map_types(),
            "biomes": self.planner.list_biomes(),
            "sizes": self.planner.list_sizes(),
        }


if __name__ == "__main__":
    gen = MapGenerator(verbose=True)

    result = gen.generate(
        goal="A peaceful forest village with a winding river and scattered cottages",
        map_type="village",
        biome="forest",
        size="medium_encounter",
        seed=42,
        unity_export=True,
    )
    print(f"\nResult: {result['status']}")
    print(f"PNG Preview: {result.get('output_path')}")
    print(f"Map name: {result.get('map_name')}")
    print(f"Unity files:")
    for key, files in result.get("unity_files", {}).items():
        print(f"  {key}: {files.get('output_dir', files)}")
