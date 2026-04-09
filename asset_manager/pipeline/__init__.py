"""asset_manager.pipeline — cross-generator orchestration.

This package collapses what the Development_Tool_Master_Prompt.docx
described as a separate 11-agent project into a small set of focused
Python modules in Asset Manager:

  source_decision.py — the deterministic protocol router (cache → library
                       → procedural → local AI → cloud AI). Cost-aware
                       fallback chain with a per-session budget ceiling.

  style_audit.py     — quality checker that validates new assets against
                       the style_bible BEFORE catalog registration.
                       Replaces the "quality-checker agent" from the spec.

  lora_trainer.py    — LoRA training driver for the local Stable Diffusion
                       path. Reads a curated subset of the user's D&D
                       library and trains a style LoRA on RTX 5090.

The agent hierarchy from the DevTool spec collapses into ordinary
Python orchestration in these modules. Claude Code's existing agent
system handles creative work when it's actually needed.
"""
