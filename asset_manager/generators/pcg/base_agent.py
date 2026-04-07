"""
Base Agent — Abstract base class for all execution agents.
Each agent reads from and writes to SharedState.
"""

from abc import ABC, abstractmethod
from shared_state import SharedState
from typing import Any
import time


class BaseAgent(ABC):
    """
    All Tier 3 agents inherit from this.
    Each agent:
      1. Reads what it needs from shared_state
      2. Performs its computation
      3. Writes results back to shared_state
      4. Returns a status summary
    """

    name: str = "BaseAgent"

    def __init__(self):
        self.execution_time: float = 0.0

    def execute(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        """
        Execute the agent's task. Wraps _run with timing and error handling.
        Returns a result dict with status and any output metadata.
        """
        start = time.time()
        try:
            result = self._run(shared_state, params)
            self.execution_time = time.time() - start
            shared_state.log_agent_completion(self.name)
            return {
                "status": "completed",
                "agent": self.name,
                "execution_time": round(self.execution_time, 3),
                "details": result,
            }
        except Exception as e:
            self.execution_time = time.time() - start
            return {
                "status": "failed",
                "agent": self.name,
                "execution_time": round(self.execution_time, 3),
                "error": str(e),
            }

    @abstractmethod
    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        """Override this in each agent. Returns a dict of result metadata."""
        ...
