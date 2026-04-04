"""
Map Generator GUI -- Tkinter desktop app with real-time preview,
seed gallery, generation history, and per-map output folders.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import threading
import time
import os
import sys
import random
import json
from pathlib import Path

from map_generator import MapGenerator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAP_TYPES = {
    "Settlements": ["village", "town", "city"],
    "Fortifications": ["castle", "fort", "tower"],
    "Underground": ["dungeon", "cave", "mine", "maze", "treasure_room"],
    "Religious/Burial": ["crypt", "tomb", "graveyard", "temple", "church"],
    "Commercial": ["shop", "shopping_center", "factory"],
    "Interior": ["tavern", "prison", "library", "throne_room"],
    "Waterfront": ["dock", "harbor"],
    "Combat": ["arena"],
    "Field/Outdoor": ["wilderness", "camp", "outpost", "rest_area", "crash_site"],
    "Large Scale": ["biomes", "region", "open_world", "world_box"],
}

FLAT_TYPES = []
for _types in MAP_TYPES.values():
    FLAT_TYPES.extend(_types)

BIOMES = [
    "forest", "mountain", "desert", "swamp", "plains",
    "tundra", "volcanic", "cave", "dungeon",
    "jungle", "underwater", "sky",
]

SIZES = {
    "small_encounter (256)": "small_encounter",
    "medium_encounter (512)": "medium_encounter",
    "large_encounter (768)": "large_encounter",
    "standard (512)": "standard",
    "large (1024)": "large",
    "region (1024)": "region",
    "open_world (1536)": "open_world",
}

GOAL_PRESETS = {
    "village": "A peaceful village with cottages and a market square",
    "town": "A bustling medieval town with walls and a central keep",
    "city": "A sprawling city with districts, walls, and a grand cathedral",
    "castle": "A fortified castle with towers, a courtyard, and a moat",
    "fort": "A military fort with barracks and watchtowers",
    "tower": "A lonely wizard's tower rising above the landscape",
    "dungeon": "A dark dungeon with connected chambers and hidden treasures",
    "cave": "A deep cave system with underground rivers and crystals",
    "mine": "An abandoned mine with rail tracks and collapsed tunnels",
    "maze": "A hedge maze with dead ends and a hidden center",
    "treasure_room": "A glittering treasure vault filled with gold and gems",
    "crypt": "An ancient crypt beneath a ruined chapel",
    "tomb": "A sealed pharaoh's tomb with traps and treasures",
    "graveyard": "A haunted graveyard shrouded in mist",
    "temple": "A sacred temple with columns and an inner sanctum",
    "church": "A small stone church with a bell tower and graveyard",
    "shop": "A cozy general store filled with goods",
    "shopping_center": "A market district with stalls and shops",
    "factory": "A steam-powered factory with machinery and warehouses",
    "tavern": "A lively tavern with a roaring fireplace and ale barrels",
    "prison": "A grim prison with cells and guard posts",
    "library": "A grand library with towering shelves and reading halls",
    "throne_room": "A majestic throne room with banners and a gilded seat",
    "dock": "A busy dock with ships, warehouses, and fishing nets",
    "harbor": "A large harbor with multiple piers and a lighthouse",
    "arena": "A gladiator arena stained with old battles",
    "wilderness": "A vast untamed wilderness with scattered ruins",
    "camp": "A traveler's camp with tents around a fire",
    "outpost": "A mountain outpost overlooking a valley",
    "rest_area": "A roadside rest stop with a well and benches",
    "crash_site": "A mysterious crash site with scattered debris",
    "biomes": "A map showing multiple biome transitions",
    "region": "A large region with villages, rivers, and forests",
    "open_world": "An expansive open world with varied terrain",
    "world_box": "A sandbox world with everything",
}

# Color scheme
BG = "#1a1a2e"
BG_LIGHT = "#16213e"
BG_CARD = "#0f3460"
BG_DARK = "#0d1117"
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT = "#eaeaea"
TEXT_DIM = "#8899aa"
GOLD = "#d4a03c"
SUCCESS = "#2ecc71"
ENTRY_BG = "#233554"
PROGRESS_BG = "#1a2744"
PROGRESS_FG = "#4dabf7"
GALLERY_BG = "#111827"
HISTORY_SEL = "#1e3a5f"


# ---------------------------------------------------------------------------
# History tracker
# ---------------------------------------------------------------------------
class GenerationHistory:
    """Tracks generated maps with thumbnails for the history panel."""

    def __init__(self, max_items=50):
        self.items = []  # list of dicts
        self.max_items = max_items

    def add(self, result, params, elapsed):
        entry = {
            "map_name": result.get("map_name", "Untitled"),
            "map_type": params.get("map_type", "?"),
            "biome": params.get("biome", "?"),
            "seed": params.get("seed", 0),
            "size": params.get("size", "?"),
            "elapsed": elapsed,
            "output_path": result.get("output_path", ""),
            "timestamp": time.strftime("%H:%M:%S"),
            "status": result.get("status", "unknown"),
        }
        self.items.insert(0, entry)
        if len(self.items) > self.max_items:
            self.items.pop()
        return entry


# ---------------------------------------------------------------------------
# Main GUI
# ---------------------------------------------------------------------------
class MapGeneratorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Map Generator")
        self.root.geometry("1280x860")
        self.root.minsize(1000, 700)
        self.root.configure(bg=BG)

        self.generator = MapGenerator(verbose=False)
        self.generating = False
        self.last_result = None
        self.preview_image = None
        self.history = GenerationHistory()
        self.gallery_mode = False
        self.gallery_images = []  # list of (seed, PIL.Image, result)
        self._gallery_tk_images = []  # prevent GC

        # Current view mode: "preview" or "gallery"
        self.view_mode = "preview"

        self._setup_styles()
        self._build_ui()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("Dark.TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=GOLD,
                         font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=TEXT_DIM,
                         font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT,
                         font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=BG_CARD, foreground=GOLD,
                         font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=SUCCESS,
                         font=("Segoe UI", 10))
        style.configure("Progress.TLabel", background=BG, foreground=PROGRESS_FG,
                         font=("Segoe UI", 9))
        style.configure("TCombobox", fieldbackground=ENTRY_BG, foreground=TEXT,
                         background=BG_CARD, selectbackground=ACCENT)
        style.configure("TCheckbutton", background=BG_CARD, foreground=TEXT,
                         font=("Segoe UI", 10))
        style.map("TCombobox",
                   fieldbackground=[("readonly", ENTRY_BG)],
                   foreground=[("readonly", TEXT)])
        style.configure("History.TLabel", background=BG_DARK, foreground=TEXT_DIM,
                         font=("Segoe UI", 8))

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(12, 4))
        ttk.Label(header, text="Map Generator", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Procedural maps for Unity",
                  style="Subtitle.TLabel").pack(side="left", padx=(12, 0), pady=(10, 0))

        # Main 3-column layout: controls | preview | history
        content = ttk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        # Left panel -- controls (fixed width)
        left = ttk.Frame(content, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        self._build_config_card(left)
        self._build_goal_card(left)
        self._build_actions(left)
        self._build_progress_bar(left)
        self._build_status(left)

        # Right panel -- history (fixed width)
        right = ttk.Frame(content, width=200, style="Dark.TFrame")
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        self._build_history_panel(right)

        # Center panel -- preview / gallery (fills remaining space)
        center = ttk.Frame(content)
        center.pack(side="left", fill="both", expand=True)
        self._build_preview(center)

    def _build_config_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.pack(fill="x", pady=(0, 6))

        ttk.Label(card, text="Configuration", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Map Type with category grouping
        ttk.Label(card, text="Map Type", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 6))
        self.map_type_var = tk.StringVar(value="village")
        self.type_combo = ttk.Combobox(card, textvariable=self.map_type_var,
                                        values=FLAT_TYPES, state="readonly", width=20)
        self.type_combo.grid(row=1, column=1, sticky="ew", pady=2)
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_changed)

        # Biome
        ttk.Label(card, text="Biome", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 6))
        self.biome_var = tk.StringVar(value="forest")
        self.biome_combo = ttk.Combobox(card, textvariable=self.biome_var,
                                         values=BIOMES, state="readonly", width=20)
        self.biome_combo.grid(row=2, column=1, sticky="ew", pady=2)

        # Size
        ttk.Label(card, text="Size", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 6))
        self.size_display_var = tk.StringVar(value="standard (512)")
        self.size_combo = ttk.Combobox(card, textvariable=self.size_display_var,
                                        values=list(SIZES.keys()), state="readonly", width=20)
        self.size_combo.grid(row=3, column=1, sticky="ew", pady=2)

        # Seed
        ttk.Label(card, text="Seed", style="Card.TLabel").grid(
            row=4, column=0, sticky="w", padx=(0, 6))
        seed_frame = ttk.Frame(card, style="Card.TFrame")
        seed_frame.grid(row=4, column=1, sticky="ew", pady=2)
        self.seed_var = tk.StringVar(value=str(random.randint(1, 99999)))
        self.seed_entry = tk.Entry(seed_frame, textvariable=self.seed_var, width=10,
                                    bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                                    relief="flat", font=("Segoe UI", 10))
        self.seed_entry.pack(side="left", fill="x", expand=True)
        tk.Button(seed_frame, text="Dice", command=self._randomize_seed,
                  bg=BG_LIGHT, fg=TEXT_DIM, relief="flat",
                  font=("Segoe UI", 8), padx=6, cursor="hand2").pack(side="left", padx=(4, 0))

        # Unity export checkbox
        self.unity_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text="Unity Export", variable=self.unity_var,
                         style="TCheckbutton").grid(row=5, column=0, columnspan=2,
                                                      sticky="w", pady=(4, 0))

        card.columnconfigure(1, weight=1)

    def _build_goal_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.pack(fill="x", pady=(0, 6))

        ttk.Label(card, text="Goal Description", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 4))

        self.goal_text = tk.Text(card, height=3, bg=ENTRY_BG, fg=TEXT,
                                  insertbackground=TEXT, relief="flat", wrap="word",
                                  font=("Segoe UI", 10), padx=8, pady=4)
        self.goal_text.pack(fill="x")
        self.goal_text.insert("1.0", GOAL_PRESETS["village"])

    def _build_actions(self, parent):
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 6))

        # Main generate button
        self.generate_btn = tk.Button(
            actions, text="Generate Map", command=self._on_generate,
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            activeforeground="white", relief="flat",
            font=("Segoe UI", 12, "bold"), pady=8, cursor="hand2",
        )
        self.generate_btn.pack(fill="x")

        # Secondary buttons row
        btn_row = ttk.Frame(actions)
        btn_row.pack(fill="x", pady=(4, 0))

        self.gallery_btn = tk.Button(
            btn_row, text="Seed Gallery (3x3)", command=self._on_gallery,
            bg=BG_CARD, fg=GOLD, activebackground=BG_LIGHT,
            activeforeground=GOLD, relief="flat",
            font=("Segoe UI", 9), pady=3, cursor="hand2",
        )
        self.gallery_btn.pack(fill="x", pady=(0, 2))

        self.playtest_btn = tk.Button(
            btn_row, text="Playtest", command=self._on_playtest,
            bg=BG_CARD, fg=GOLD, activebackground=BG_LIGHT,
            activeforeground=GOLD, relief="flat",
            font=("Segoe UI", 9, "bold"), pady=3, cursor="hand2",
        )
        self.playtest_btn.pack(fill="x", pady=(2, 0))

        btn_row2 = ttk.Frame(actions)
        btn_row2.pack(fill="x", pady=(0, 0))

        tk.Button(
            btn_row2, text="Open Folder", command=self._open_output,
            bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
            activeforeground=TEXT, relief="flat",
            font=("Segoe UI", 9), pady=3, cursor="hand2",
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))

        tk.Button(
            btn_row2, text="Save As...", command=self._save_as,
            bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
            activeforeground=TEXT, relief="flat",
            font=("Segoe UI", 9), pady=3, cursor="hand2",
        ).pack(side="left", fill="x", expand=True, padx=(2, 0))

    def _build_progress_bar(self, parent):
        prog_frame = ttk.Frame(parent)
        prog_frame.pack(fill="x", pady=(0, 4))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = tk.Canvas(prog_frame, height=8, bg=PROGRESS_BG,
                                       highlightthickness=0)
        self.progress_bar.pack(fill="x")

        self.progress_label = ttk.Label(prog_frame, text="", style="Progress.TLabel")
        self.progress_label.pack(anchor="w")

    def _build_status(self, parent):
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var,
                  style="Status.TLabel").pack(anchor="w")

        self.info_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.info_var,
                  style="Subtitle.TLabel").pack(anchor="w")

        # Log
        self.log_text = tk.Text(parent, height=6, bg=BG_LIGHT, fg=TEXT_DIM,
                                 relief="flat", font=("Consolas", 8), padx=6, pady=4,
                                 state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _build_preview(self, parent):
        self.preview_card = ttk.Frame(parent, style="Card.TFrame", padding=6)
        self.preview_card.pack(fill="both", expand=True)

        # Header with view mode tabs
        preview_header = ttk.Frame(self.preview_card, style="Card.TFrame")
        preview_header.pack(fill="x", pady=(0, 4))
        ttk.Label(preview_header, text="Preview", style="CardTitle.TLabel").pack(
            side="left")

        self.preview_canvas = tk.Canvas(self.preview_card, bg="#0a0a1a",
                                         highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

        # Placeholder
        self.preview_canvas.create_text(
            400, 300, text="Generate a map to see preview\n\nor use Seed Gallery to explore variations",
            fill=TEXT_DIM, font=("Segoe UI", 13), justify="center", tags="placeholder",
        )

    def _build_history_panel(self, parent):
        ttk.Label(parent, text="History", style="CardTitle.TLabel",
                  background=BG_DARK).pack(anchor="w", padx=8, pady=(8, 4))

        # Scrollable history list
        hist_container = ttk.Frame(parent, style="Dark.TFrame")
        hist_container.pack(fill="both", expand=True, padx=4)

        self.history_canvas = tk.Canvas(hist_container, bg=BG_DARK,
                                         highlightthickness=0, width=180)
        scrollbar = ttk.Scrollbar(hist_container, orient="vertical",
                                   command=self.history_canvas.yview)
        self.history_inner = ttk.Frame(self.history_canvas, style="Dark.TFrame")

        self.history_inner.bind("<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.create_window((0, 0), window=self.history_inner, anchor="nw")
        self.history_canvas.configure(yscrollcommand=scrollbar.set)

        self.history_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Clear button
        tk.Button(parent, text="Clear History", command=self._clear_history,
                  bg=BG_DARK, fg=TEXT_DIM, relief="flat",
                  font=("Segoe UI", 8), cursor="hand2").pack(pady=(4, 8))

    # ------------------------------------------------------------------
    # Progress updates (called from worker thread via root.after)
    # ------------------------------------------------------------------
    def _update_progress(self, event):
        etype = event.get("event", "")
        if etype == "level_start":
            level = event.get("level", 0)
            total = event.get("total_levels", 1)
            tasks = event.get("tasks", [])
            pct = level / total
            self.progress_var.set(pct)
            self._draw_progress_bar(pct)
            self.progress_label.config(
                text=f"Level {level+1}/{total}: {', '.join(tasks)}")
        elif etype == "task_complete":
            agent = event.get("agent", "")
            task_id = event.get("task_id", "")
            elapsed = event.get("elapsed", 0)
            self._log(f"  {task_id} ({agent}) {elapsed:.2f}s")

            # Live preview: after terrain or render, update the canvas
            level = event.get("level", 0)
            total = event.get("total_levels", 1)
            pct = (level + 1) / total
            self._draw_progress_bar(pct)

            if agent in ("TerrainAgent", "WaterAgent", "StructureAgent",
                         "AssetAgent", "RendererAgent"):
                self._request_live_preview()

        elif etype == "complete":
            self._draw_progress_bar(1.0)
            self.progress_label.config(text="Complete")

    def _draw_progress_bar(self, pct):
        c = self.progress_bar
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 2:
            return
        fill_w = int(w * min(pct, 1.0))
        c.create_rectangle(0, 0, fill_w, h, fill=PROGRESS_FG, outline="")

    def _request_live_preview(self):
        """Build a live preview from the current shared_state terrain_color."""
        if not hasattr(self, '_live_shared_state') or self._live_shared_state is None:
            return
        try:
            ss = self._live_shared_state
            img = Image.fromarray(ss.terrain_color, "RGB")
            self.preview_image = img
            self._update_preview()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_type_changed(self, event=None):
        mt = self.map_type_var.get()
        if mt in GOAL_PRESETS:
            self.goal_text.delete("1.0", "end")
            self.goal_text.insert("1.0", GOAL_PRESETS[mt])

    def _randomize_seed(self):
        self.seed_var.set(str(random.randint(1, 99999)))

    def _on_canvas_resize(self, event=None):
        if self.view_mode == "gallery":
            self._render_gallery()
        elif self.preview_image is not None:
            self._update_preview()

    def _get_params(self):
        return {
            "goal": self.goal_text.get("1.0", "end").strip(),
            "map_type": self.map_type_var.get(),
            "biome": self.biome_var.get(),
            "size": SIZES.get(self.size_display_var.get(), "standard"),
            "seed": int(self.seed_var.get()) if self.seed_var.get().isdigit() else random.randint(1, 99999),
            "unity_export": self.unity_var.get(),
        }

    # ------------------------------------------------------------------
    # Single map generation
    # ------------------------------------------------------------------
    def _on_generate(self):
        if self.generating:
            return
        self.view_mode = "preview"
        self.generating = True
        self._live_shared_state = None
        self.generate_btn.config(text="Generating...", bg=TEXT_DIM, state="disabled")
        self.gallery_btn.config(state="disabled")
        self.playtest_btn.config(state="disabled")
        self.status_var.set("Generating...")
        self.info_var.set("")
        self._log_clear()
        self._draw_progress_bar(0)
        self.progress_label.config(text="Starting...")

        params = self._get_params()
        self._log(f"Map: {params['map_type']} | Biome: {params['biome']} | Seed: {params['seed']}")
        self._log("")

        thread = threading.Thread(target=self._generate_worker, args=(params,), daemon=True)
        thread.start()

    def _generate_worker(self, params):
        start = time.time()
        try:
            def on_progress(event):
                self.root.after(0, self._update_progress, event)

            result = self.generator.generate(
                goal=params["goal"],
                map_type=params["map_type"],
                biome=params["biome"],
                size=params["size"],
                seed=params["seed"],
                unity_export=params["unity_export"],
                on_progress=on_progress,
            )

            # Store shared_state ref for live preview
            ss = result.get("shared_state")
            if ss:
                self._live_shared_state = ss

            elapsed = time.time() - start
            self.root.after(0, self._on_generate_done, result, params, elapsed)
        except Exception as e:
            elapsed = time.time() - start
            self.root.after(0, self._on_generate_error, str(e), elapsed)

    def _on_generate_done(self, result, params, elapsed):
        self.generating = False
        self.last_result = result
        self.generate_btn.config(text="Generate Map", bg=ACCENT, state="normal")
        self.gallery_btn.config(state="normal")
        self.playtest_btn.config(state="normal")

        map_name = result.get("map_name", "Untitled")
        output_path = result.get("output_path", "")
        state_info = result.get("state_summary", {})
        entities = state_info.get("entities", 0) if isinstance(state_info, dict) else 0

        self.status_var.set(f"Done -- {map_name}")
        self.info_var.set(f"{elapsed:.1f}s | {entities} entities | seed {params['seed']}")

        self._log(f"Name: {map_name}")
        self._log(f"Time: {elapsed:.1f}s")
        self._log(f"Output: {output_path}")

        # Add to history
        entry = self.history.add(result, params, elapsed)
        self._add_history_item(entry, output_path)

        # Show final preview
        if output_path and os.path.exists(output_path):
            self.preview_image = Image.open(output_path)
            self._update_preview()

    def _on_generate_error(self, error_msg, elapsed):
        self.generating = False
        self.generate_btn.config(text="Generate Map", bg=ACCENT, state="normal")
        self.gallery_btn.config(state="normal")
        self.playtest_btn.config(state="normal")
        self.status_var.set("Error")
        self.info_var.set(f"Failed after {elapsed:.1f}s")
        self._log(f"ERROR: {error_msg}")
        self._draw_progress_bar(0)

    # ------------------------------------------------------------------
    # Seed Gallery (3x3 grid)
    # ------------------------------------------------------------------
    def _on_gallery(self):
        if self.generating:
            return
        self.view_mode = "gallery"
        self.generating = True
        self.generate_btn.config(text="Gallery...", bg=TEXT_DIM, state="disabled")
        self.gallery_btn.config(state="disabled")
        self.playtest_btn.config(state="disabled")
        self.status_var.set("Generating seed gallery...")
        self.info_var.set("9 variations with different seeds")
        self._log_clear()
        self._log("Seed Gallery: generating 9 maps...")
        self._draw_progress_bar(0)
        self.gallery_images = []
        self._gallery_tk_images = []

        params = self._get_params()
        base_seed = params["seed"]

        # Generate 9 seeds spread around the base seed
        seeds = [base_seed + i * 1000 for i in range(9)]

        thread = threading.Thread(target=self._gallery_worker, args=(params, seeds), daemon=True)
        thread.start()

    def _gallery_worker(self, base_params, seeds):
        start = time.time()
        results = []
        for i, seed in enumerate(seeds):
            try:
                params = {**base_params, "seed": seed, "unity_export": False}
                # Use small size for gallery thumbnails
                params["size"] = "small_encounter"

                result = self.generator.generate(
                    goal=params["goal"],
                    map_type=params["map_type"],
                    biome=params["biome"],
                    size=params["size"],
                    seed=seed,
                    unity_export=False,
                )
                output_path = result.get("output_path", "")
                img = None
                if output_path and os.path.exists(output_path):
                    img = Image.open(output_path)
                results.append((seed, img, result))

                pct = (i + 1) / 9
                self.root.after(0, self._draw_progress_bar, pct)
                self.root.after(0, self._log, f"  Seed {seed}: {result.get('map_name', '?')}")
            except Exception as e:
                results.append((seed, None, {"status": "failed", "error": str(e)}))
                self.root.after(0, self._log, f"  Seed {seed}: FAILED - {e}")

        elapsed = time.time() - start
        self.root.after(0, self._on_gallery_done, results, elapsed)

    def _on_gallery_done(self, results, elapsed):
        self.generating = False
        self.generate_btn.config(text="Generate Map", bg=ACCENT, state="normal")
        self.gallery_btn.config(state="normal")
        self.playtest_btn.config(state="normal")
        self.gallery_images = results
        self.status_var.set(f"Gallery complete -- {len(results)} maps")
        self.info_var.set(f"{elapsed:.1f}s total | Click a thumbnail to select")
        self._render_gallery()

    def _render_gallery(self):
        """Draw the 3x3 gallery grid on the preview canvas."""
        self.preview_canvas.delete("all")
        self._gallery_tk_images = []

        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 50 or ch < 50 or not self.gallery_images:
            return

        cols, rows = 3, 3
        pad = 6
        cell_w = (cw - pad * (cols + 1)) // cols
        cell_h = (ch - pad * (rows + 1)) // rows
        thumb_size = min(cell_w, cell_h)

        for idx, (seed, img, result) in enumerate(self.gallery_images[:9]):
            row = idx // cols
            col = idx % cols
            cx = pad + col * (cell_w + pad) + cell_w // 2
            cy = pad + row * (cell_h + pad) + cell_h // 2

            if img is not None:
                thumb = img.resize((thumb_size, thumb_size), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(thumb)
                self._gallery_tk_images.append(tk_img)
                item_id = self.preview_canvas.create_image(cx, cy, image=tk_img, anchor="center")
                # Click to select
                self.preview_canvas.tag_bind(item_id, "<Button-1>",
                    lambda e, s=seed, i=img, r=result: self._on_gallery_click(s, i, r))
            else:
                self.preview_canvas.create_rectangle(
                    cx - thumb_size//2, cy - thumb_size//2,
                    cx + thumb_size//2, cy + thumb_size//2,
                    fill="#2a2a3e", outline=TEXT_DIM)

            # Seed label under thumbnail
            name = result.get("map_name", f"Seed {seed}") if result else f"Seed {seed}"
            label_y = cy + thumb_size // 2 + 10
            self.preview_canvas.create_text(cx, label_y, text=f"{name}\nseed: {seed}",
                                             fill=TEXT_DIM, font=("Segoe UI", 8),
                                             justify="center")

    def _on_gallery_click(self, seed, img, result):
        """User clicked a gallery thumbnail -- switch to preview mode with that map."""
        self.view_mode = "preview"
        self.seed_var.set(str(seed))
        self.last_result = result
        if img:
            self.preview_image = img
            self._update_preview()
        map_name = result.get("map_name", "?")
        self.status_var.set(f"Selected: {map_name} (seed {seed})")
        self.info_var.set("Click Generate to create full-size with Unity export")

    # ------------------------------------------------------------------
    # Preview rendering
    # ------------------------------------------------------------------
    def _update_preview(self):
        if self.preview_image is None:
            return

        self.preview_canvas.delete("all")
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        img_w, img_h = self.preview_image.size
        scale = min(cw / img_w, ch / img_h, 1.0)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        resized = self.preview_image.resize((new_w, new_h), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(resized)
        self.preview_canvas.create_image(cw // 2, ch // 2, image=self._tk_image, anchor="center")

    # ------------------------------------------------------------------
    # History panel
    # ------------------------------------------------------------------
    def _add_history_item(self, entry, output_path):
        """Add a clickable entry to the history sidebar."""
        frame = tk.Frame(self.history_inner, bg=BG_DARK, cursor="hand2")
        frame.pack(fill="x", padx=2, pady=2)

        # Thumbnail
        thumb_label = tk.Label(frame, bg=BG_DARK)
        thumb_label.pack(side="left", padx=(4, 6), pady=4)

        if output_path and os.path.exists(output_path):
            try:
                img = Image.open(output_path)
                img = img.resize((48, 48), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(img)
                thumb_label.config(image=tk_img)
                thumb_label._img_ref = tk_img  # prevent GC
            except Exception:
                thumb_label.config(text="?", fg=TEXT_DIM, font=("Segoe UI", 14))
        else:
            thumb_label.config(text="?", fg=TEXT_DIM, font=("Segoe UI", 14))

        # Info
        info_frame = tk.Frame(frame, bg=BG_DARK)
        info_frame.pack(side="left", fill="x", expand=True, pady=4)

        name_lbl = tk.Label(info_frame, text=entry["map_name"],
                             bg=BG_DARK, fg=TEXT, font=("Segoe UI", 9, "bold"),
                             anchor="w")
        name_lbl.pack(fill="x")

        detail_text = f"{entry['map_type']} | {entry['biome']} | {entry['elapsed']:.1f}s"
        tk.Label(info_frame, text=detail_text,
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI", 7),
                 anchor="w").pack(fill="x")

        tk.Label(info_frame, text=f"seed {entry['seed']} | {entry['timestamp']}",
                 bg=BG_DARK, fg=TEXT_DIM, font=("Segoe UI", 7),
                 anchor="w").pack(fill="x")

        # Click to load
        def on_click(e, path=output_path, ent=entry):
            if path and os.path.exists(path):
                self.preview_image = Image.open(path)
                self.view_mode = "preview"
                self._update_preview()
                self.status_var.set(f"Viewing: {ent['map_name']}")
                self.seed_var.set(str(ent["seed"]))

        for widget in [frame, thumb_label, name_lbl, info_frame]:
            widget.bind("<Button-1>", on_click)

        # Hover highlight
        def on_enter(e):
            frame.config(bg=HISTORY_SEL)
            for child in frame.winfo_children():
                try:
                    child.config(bg=HISTORY_SEL)
                    for sub in child.winfo_children():
                        try:
                            sub.config(bg=HISTORY_SEL)
                        except Exception:
                            pass
                except Exception:
                    pass

        def on_leave(e):
            frame.config(bg=BG_DARK)
            for child in frame.winfo_children():
                try:
                    child.config(bg=BG_DARK)
                    for sub in child.winfo_children():
                        try:
                            sub.config(bg=BG_DARK)
                        except Exception:
                            pass
                except Exception:
                    pass

        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)

    def _clear_history(self):
        self.history = GenerationHistory()
        for widget in self.history_inner.winfo_children():
            widget.destroy()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def _open_output(self):
        output_dir = os.path.abspath("./output")
        if os.path.isdir(output_dir):
            os.startfile(output_dir)
        else:
            messagebox.showinfo("Output", "No output directory yet. Generate a map first.")

    def _save_as(self):
        if self.preview_image is None:
            messagebox.showinfo("Save", "No map to save. Generate a map first.")
            return
        default_name = "map.png"
        if self.last_result:
            default_name = f"{self.last_result.get('map_name', 'map')}.png"
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
            initialfile=default_name,
        )
        if path:
            self.preview_image.save(path, quality=95)
            self._log(f"Saved: {path}")

    def _on_playtest(self):
        """Launch the pygame viewer for the last generated map."""
        if self.last_result is None:
            messagebox.showinfo("Playtest", "Generate a map first.")
            return
        output_path = self.last_result.get("output_path", "")
        if not output_path:
            messagebox.showinfo("Playtest", "No output path found.")
            return
        map_dir = os.path.dirname(os.path.abspath(output_path))
        if not os.path.exists(os.path.join(map_dir, "map_data.json")):
            messagebox.showinfo("Playtest", "map_data.json not found. Regenerate the map.")
            return

        import subprocess
        viewer_path = os.path.join(os.path.dirname(__file__), "viewer", "main.py")
        python_exe = sys.executable
        subprocess.Popen([python_exe, viewer_path, map_dir])
        self._log("Launched playtest viewer")

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _log_clear(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    root.iconname("Map Generator")

    # Dark title bar on Windows 11
    try:
        from ctypes import windll, c_int, byref, sizeof
        HWND = windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        windll.dwmapi.DwmSetWindowAttribute(
            HWND, DWMWA_USE_IMMERSIVE_DARK_MODE,
            byref(c_int(1)), sizeof(c_int))
    except Exception:
        pass

    app = MapGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
