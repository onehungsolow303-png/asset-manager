"""
LLM Adapter — Provides a unified interface for LLM calls.
Currently supports Anthropic Claude API. Designed to be swappable.

Usage:
    adapter = ClaudeAdapter(api_key="sk-ant-...")
    result = adapter.generate(
        system="You are a fantasy map planner.",
        prompt="Decompose this goal into subtasks: forest village with a river",
    )
"""

import json
import os
from typing import Any, Optional
from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    """Abstract base for LLM backends."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        ...

    @abstractmethod
    def generate_json(self, prompt: str, system: str = "",
                      temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """Generate and parse a JSON response."""
        ...


class ClaudeAdapter(LLMAdapter):
    """
    Anthropic Claude API adapter.
    Requires: pip install anthropic
    Set ANTHROPIC_API_KEY env var or pass api_key directly.
    """

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Send a prompt to Claude and return the text response."""
        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def generate_json(self, prompt: str, system: str = "",
                      temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        """Generate a response and parse it as JSON."""
        full_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Respond with ONLY valid JSON. No markdown, no code fences, "
            "no explanation. Just the JSON object."
        )
        text = self.generate(full_prompt, system=system,
                             temperature=temperature, max_tokens=max_tokens)

        # Strip any markdown fences
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        return json.loads(text)


class MockLLMAdapter(LLMAdapter):
    """
    Fallback adapter that uses template-based generation when no API key is available.
    Useful for testing without incurring API costs.
    """

    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        return "[MockLLM] No API key configured. Using template-based generation."

    def generate_json(self, prompt: str, system: str = "",
                      temperature: float = 0.3, max_tokens: int = 4096) -> dict:
        return {"mock": True, "message": "No API key configured"}

    @property
    def available(self) -> bool:
        return True


def create_adapter(api_key: str = None, provider: str = "claude") -> LLMAdapter:
    """
    Factory function to create the right LLM adapter.
    Falls back to MockLLMAdapter if no API key is available.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    if provider == "claude" and key:
        return ClaudeAdapter(api_key=key)
    else:
        print("[LLM] No ANTHROPIC_API_KEY found. Using template-based fallback.")
        print("[LLM] Set ANTHROPIC_API_KEY env var to enable Claude-powered planning.")
        return MockLLMAdapter()


# ─── Prompt templates for map generation ───────────────────────────────────

PLANNER_SYSTEM_PROMPT = """You are an expert procedural map generation planner for a fantasy game engine.
Your job is to decompose a high-level map request into a precise DAG (directed acyclic graph) of subtasks.

Each subtask must specify:
- task_id: unique snake_case identifier
- agent_type: one of [TerrainAgent, WaterAgent, PathfindingAgent, StructureAgent, AssetAgent, LabelingAgent, RendererAgent, UnityTerrainExporter, UnitySceneExporter, UnityCSharpExporter, UnityTilemapExporter]
- params: dict of parameters for that agent
- depends_on: list of task_ids that must complete first

Available biomes: forest, mountain, desert, swamp, plains, tundra, volcanic, cave, dungeon
Available map types: village, city, dungeon, cave, arena, wilderness, camp, outpost, open_world

Constraints:
- TerrainAgent must always run first (no dependencies)
- WaterAgent depends on TerrainAgent (needs elevation data)
- PathfindingAgent depends on TerrainAgent and WaterAgent (avoids water)
- StructureAgent depends on PathfindingAgent (buildings near roads)
- AssetAgent depends on TerrainAgent and StructureAgent (avoids buildings)
- LabelingAgent depends on structures and water features
- RendererAgent depends on everything visual
- Unity exporters depend on RendererAgent (need complete state)

Respond with valid JSON only."""

LABELING_SYSTEM_PROMPT = """You are a fantasy world-builder and lore writer.
Given a map's features (biome, structures, water features, terrain), generate creative
and evocative names and short flavor text for each location.

Style guide:
- Names should feel like they belong in a fantasy RPG
- Each name should reflect the biome and terrain features nearby
- Flavor text should be 1-2 sentences max, evocative and mysterious
- Avoid generic names; make each one unique and memorable

Respond with valid JSON only."""


def build_planner_prompt(goal: str, map_type: str, biome: str,
                          size: tuple[int, int], seed: int) -> str:
    """Build the prompt for the strategic planner."""
    return f"""Decompose this map generation request into a task DAG:

Goal: {goal}
Map Type: {map_type}
Biome: {biome}
Size: {size[0]}x{size[1]}
Seed: {seed}

Return a JSON object with this structure:
{{
    "map_name": "A creative name for this map",
    "tasks": [
        {{
            "task_id": "terrain_base",
            "agent_type": "TerrainAgent",
            "params": {{"biome": "{biome}"}},
            "depends_on": []
        }},
        ...
    ]
}}

Include Unity export tasks at the end:
- UnityTerrainExporter (depends on terrain + water)
- UnitySceneExporter (depends on all placement agents)
- UnityCSharpExporter (depends on all agents)
- UnityTilemapExporter (depends on terrain + structures)"""


def build_labeling_prompt(biome: str, entities: list, paths: list,
                           map_type: str) -> str:
    """Build the prompt for the labeling agent."""
    entity_summary = []
    for e in entities[:20]:  # limit to avoid token overflow
        entity_summary.append({
            "type": e.entity_type,
            "position": e.position,
            "variant": e.variant,
            "current_name": e.metadata.get("name", "unnamed"),
        })

    path_summary = [{"type": p.path_type, "length": len(p.waypoints)} for p in paths]

    return f"""Generate names and flavor text for this {map_type} map in a {biome} biome.

Structures and features:
{json.dumps(entity_summary, indent=2)}

Paths:
{json.dumps(path_summary, indent=2)}

Return JSON:
{{
    "map_title": "Name for the whole map",
    "locations": [
        {{
            "entity_index": 0,
            "name": "The Whispering Oak Tavern",
            "flavor_text": "A warm hearth beckons weary travelers from the forest road."
        }},
        ...
    ],
    "water_features": [
        {{
            "path_index": 0,
            "name": "Silverbrook Creek",
            "flavor_text": "Crystal waters wind through mossy stones."
        }},
        ...
    ]
}}"""
