"""
DAG Engine — Defines task graphs, validates them (no cycles), and resolves execution order.
"""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Any


@dataclass
class TaskNode:
    """A single task in the DAG"""
    task_id: str
    agent_type: str              # which agent class handles this
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"      # pending, running, completed, failed
    result: Any = None
    error: str = ""
    retries: int = 0
    max_retries: int = 3


class TaskDAG:
    """
    Directed Acyclic Graph of tasks.
    Supports topological sorting, parallel level detection, and cycle validation.
    """

    def __init__(self):
        self.nodes: dict[str, TaskNode] = {}

    def add_task(self, task: TaskNode):
        self.nodes[task.task_id] = task

    def validate(self) -> tuple[bool, str]:
        """Check for cycles and missing dependencies. Returns (valid, error_message)."""
        # Check missing dependencies
        for node in self.nodes.values():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    return False, f"Task '{node.task_id}' depends on unknown task '{dep}'"

        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for dep in self.nodes[node_id].depends_on:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node_id)
            return False

        for nid in self.nodes:
            if nid not in visited:
                if has_cycle(nid):
                    return False, "Cycle detected in task DAG"

        return True, ""

    def topological_sort(self) -> list[list[str]]:
        """
        Returns tasks grouped by execution level.
        Tasks in the same level can run in parallel.
        """
        in_degree = {nid: 0 for nid in self.nodes}
        dependents = defaultdict(list)

        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                dependents[dep].append(nid)
                in_degree[nid] += 1

        # BFS by levels
        levels = []
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])

        while queue:
            level = list(queue)
            levels.append(level)
            next_queue = deque()
            for nid in level:
                for dependent in dependents[nid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)
            queue = next_queue

        return levels

    def get_ready_tasks(self) -> list[str]:
        """Get tasks whose dependencies are all completed."""
        ready = []
        for nid, node in self.nodes.items():
            if node.status != "pending":
                continue
            deps_met = all(
                self.nodes[dep].status == "completed"
                for dep in node.depends_on
            )
            if deps_met:
                ready.append(nid)
        return ready

    def mark_completed(self, task_id: str, result: Any = None):
        self.nodes[task_id].status = "completed"
        self.nodes[task_id].result = result

    def mark_failed(self, task_id: str, error: str):
        node = self.nodes[task_id]
        node.retries += 1
        if node.retries < node.max_retries:
            node.status = "pending"  # will be retried
        else:
            node.status = "failed"
            node.error = error

    def mark_running(self, task_id: str):
        self.nodes[task_id].status = "running"

    def is_complete(self) -> bool:
        return all(n.status in ("completed", "failed") for n in self.nodes.values())

    def has_failures(self) -> bool:
        return any(n.status == "failed" for n in self.nodes.values())

    def __repr__(self):
        lines = ["TaskDAG:"]
        for level_idx, level in enumerate(self.topological_sort()):
            lines.append(f"  Level {level_idx}: {level}")
        return "\n".join(lines)
