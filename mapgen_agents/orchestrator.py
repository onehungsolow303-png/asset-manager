"""
Orchestrator (Mid-Tier) — The Project Manager agent.
Receives a TaskDAG, resolves execution order, dispatches to low-level agents,
manages shared state, and handles errors with retries.
"""

import time
from typing import Any
from dag_engine import TaskDAG, TaskNode
from shared_state import SharedState, MapConfig
from base_agent import BaseAgent

# Import all agents
import sys
sys.path.insert(0, 'agents')
from agents.terrain_agent import TerrainAgent
from agents.water_agent import WaterAgent
from agents.pathfinding_agent import PathfindingAgent
from agents.structure_agent import StructureAgent
from agents.asset_agent import AssetAgent
from agents.labeling_agent import LabelingAgent
from agents.renderer_agent import RendererAgent
from agents.unity_terrain_exporter import UnityTerrainExporter
from agents.unity_scene_exporter import UnitySceneExporter
from agents.unity_csharp_exporter import UnityCSharpExporter
from agents.unity_tilemap_exporter import UnityTilemapExporter


# Agent registry: maps agent type strings to classes
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "TerrainAgent": TerrainAgent,
    "WaterAgent": WaterAgent,
    "PathfindingAgent": PathfindingAgent,
    "StructureAgent": StructureAgent,
    "AssetAgent": AssetAgent,
    "LabelingAgent": LabelingAgent,
    "RendererAgent": RendererAgent,
    "UnityTerrainExporter": UnityTerrainExporter,
    "UnitySceneExporter": UnitySceneExporter,
    "UnityCSharpExporter": UnityCSharpExporter,
    "UnityTilemapExporter": UnityTilemapExporter,
}


class Orchestrator:
    """
    Mid-tier Project Manager.
    Coordinates the execution of a TaskDAG against a SharedState.
    """

    def __init__(self, shared_state: SharedState, verbose: bool = True, on_progress=None):
        self.shared_state = shared_state
        self.verbose = verbose
        self.on_progress = on_progress  # callable(event_dict) or None
        self.execution_log: list[dict] = []
        self.total_time: float = 0.0

    def execute_dag(self, dag: TaskDAG) -> dict:
        """
        Execute all tasks in the DAG in dependency order.
        Returns a summary of the execution.
        """
        # Validate DAG
        valid, error = dag.validate()
        if not valid:
            return {"status": "failed", "error": f"DAG validation failed: {error}"}

        # Get execution levels
        levels = dag.topological_sort()
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  ORCHESTRATOR: Executing {len(dag.nodes)} tasks in {len(levels)} levels")
            print(f"{'='*60}")

        start_time = time.time()

        for level_idx, level in enumerate(levels):
            if self.on_progress:
                self.on_progress({
                    "event": "level_start",
                    "level": level_idx,
                    "total_levels": len(levels),
                    "tasks": level,
                })

            if self.verbose:
                print(f"\n--- Level {level_idx}: {level} ---")

            for task_id in level:
                node = dag.nodes[task_id]
                result = self._execute_task(node)
                self.execution_log.append(result)

                if result["status"] == "completed":
                    dag.mark_completed(task_id, result)
                    if self.verbose:
                        print(f"  [OK] {task_id} ({result.get('execution_time', '?')}s)")
                        if result.get("details"):
                            for k, v in result["details"].items():
                                print(f"       {k}: {v}")
                    if self.on_progress:
                        self.on_progress({
                            "event": "task_complete",
                            "task_id": task_id,
                            "agent": node.agent_type,
                            "level": level_idx,
                            "total_levels": len(levels),
                            "details": result.get("details", {}),
                            "elapsed": result.get("execution_time", 0),
                        })
                else:
                    # Retry logic
                    retried = False
                    for attempt in range(node.max_retries):
                        if self.verbose:
                            print(f"  [RETRY {attempt+1}] {task_id}: {result.get('error', 'unknown error')}")
                        result = self._execute_task(node)
                        if result["status"] == "completed":
                            dag.mark_completed(task_id, result)
                            retried = True
                            break

                    if not retried:
                        dag.mark_failed(task_id, result.get("error", "unknown"))
                        if self.verbose:
                            print(f"  [FAILED] {task_id}: {result.get('error', 'unknown')}")

        self.total_time = time.time() - start_time

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  ORCHESTRATOR: Complete in {self.total_time:.2f}s")
            print(f"  State: {self.shared_state.summary()}")
            print(f"{'='*60}\n")

        tasks_completed = sum(1 for n in dag.nodes.values() if n.status == "completed")
        tasks_failed = sum(1 for n in dag.nodes.values() if n.status == "failed")

        if self.on_progress:
            self.on_progress({
                "event": "complete",
                "total_time": self.total_time,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
            })

        return {
            "status": "completed" if not dag.has_failures() else "partial",
            "total_time": round(self.total_time, 2),
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "state_summary": self.shared_state.summary(),
        }

    def _execute_task(self, node: TaskNode) -> dict:
        """Dispatch a single task to its agent and return the result."""
        agent_cls = AGENT_REGISTRY.get(node.agent_type)
        if agent_cls is None:
            return {
                "status": "failed",
                "agent": node.agent_type,
                "error": f"Unknown agent type: {node.agent_type}",
            }

        agent = agent_cls()
        dag_node_status = "running"
        return agent.execute(self.shared_state, node.params)
