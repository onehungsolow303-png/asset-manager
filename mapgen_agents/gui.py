"""
Map Generator GUI -- Tkinter-based desktop application for procedural map generation.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import time
import os
import sys
import random

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

BIOMES = [
    "forest", "mountain", "desert", "swamp", "plains",
    "tundra", "volcanic", "cave", "dungeon",
    "jungle", "underwater", "sky",
]

SIZES = {
    "small_encounter (256x256)": "small_encounter",
    "medium_encounter (512x512)": "medium_encounter",
    "large_encounter (768x768)": "large_encounter",
    "standard (512x512)": "standard",
    "large (1024x1024)": "large",
    "region (1024x1024)": "region",
    "open_world (1536x1536)": "open_world",
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
ACCENT = "#e94560"
ACCENT_HOVER = "#ff6b81"
TEXT = "#eaeaea"
TEXT_DIM = "#8899aa"
GOLD = "#d4a03c"
SUCCESS = "#2ecc71"
ENTRY_BG = "#233554"


class MapGeneratorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Map Generator")
        self.root.geometry("1100x780")
        self.root.minsize(900, 650)
        self.root.configure(bg=BG)

        self.generator = MapGenerator(verbose=False)
        self.generating = False
        self.last_result = None
        self.preview_image = None

        self._setup_styles()
        self._build_ui()

    # ------------------------------------------------------------------
    # Style setup
    # ------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=GOLD,
                         font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=TEXT_DIM,
                         font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT,
                         font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=BG_CARD, foreground=GOLD,
                         font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background=BG, foreground=SUCCESS,
                         font=("Segoe UI", 10))
        style.configure("TCombobox", fieldbackground=ENTRY_BG, foreground=TEXT,
                         background=BG_CARD, selectbackground=ACCENT)
        style.configure("TCheckbutton", background=BG_CARD, foreground=TEXT,
                         font=("Segoe UI", 10))
        style.map("TCombobox",
                   fieldbackground=[("readonly", ENTRY_BG)],
                   foreground=[("readonly", TEXT)])

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=20, pady=(15, 5))
        ttk.Label(header, text="Map Generator", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Procedural maps for Unity",
                  style="Subtitle.TLabel").pack(side="left", padx=(12, 0), pady=(8, 0))

        # Main content: left controls + right preview
        content = ttk.Frame(self.root)
        content.pack(fill="both", expand=True, padx=20, pady=10)

        # Left panel -- controls
        left = ttk.Frame(content)
        left.pack(side="left", fill="y", padx=(0, 10))

        self._build_config_card(left)
        self._build_goal_card(left)
        self._build_actions(left)
        self._build_status(left)

        # Right panel -- preview
        right = ttk.Frame(content)
        right.pack(side="left", fill="both", expand=True)
        self._build_preview(right)

    def _build_config_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 8))

        ttk.Label(card, text="Configuration", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        # Map Type
        ttk.Label(card, text="Map Type", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8))
        self.map_type_var = tk.StringVar(value="village")
        all_types = []
        for types in MAP_TYPES.values():
            all_types.extend(types)
        self.type_combo = ttk.Combobox(card, textvariable=self.map_type_var,
                                        values=all_types, state="readonly", width=18)
        self.type_combo.grid(row=1, column=1, sticky="w", pady=2)
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_changed)

        # Biome
        ttk.Label(card, text="Biome", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8))
        self.biome_var = tk.StringVar(value="forest")
        self.biome_combo = ttk.Combobox(card, textvariable=self.biome_var,
                                         values=BIOMES, state="readonly", width=18)
        self.biome_combo.grid(row=2, column=1, sticky="w", pady=2)

        # Size
        ttk.Label(card, text="Size", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 8))
        self.size_display_var = tk.StringVar(value="standard (512x512)")
        self.size_combo = ttk.Combobox(card, textvariable=self.size_display_var,
                                        values=list(SIZES.keys()), state="readonly", width=24)
        self.size_combo.grid(row=3, column=1, sticky="w", pady=2)

        # Seed
        ttk.Label(card, text="Seed", style="Card.TLabel").grid(
            row=4, column=0, sticky="w", padx=(0, 8))
        seed_frame = ttk.Frame(card, style="Card.TFrame")
        seed_frame.grid(row=4, column=1, sticky="w", pady=2)
        self.seed_var = tk.StringVar(value=str(random.randint(1, 99999)))
        self.seed_entry = tk.Entry(seed_frame, textvariable=self.seed_var, width=12,
                                    bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                                    relief="flat", font=("Segoe UI", 10))
        self.seed_entry.pack(side="left")
        randomize_btn = tk.Button(seed_frame, text="Dice", command=self._randomize_seed,
                                   bg=BG_LIGHT, fg=TEXT_DIM, relief="flat",
                                   font=("Segoe UI", 8), padx=6, cursor="hand2")
        randomize_btn.pack(side="left", padx=(4, 0))

        # Unity export checkbox
        self.unity_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text="Unity Export", variable=self.unity_var,
                         style="TCheckbutton").grid(row=5, column=0, columnspan=2,
                                                      sticky="w", pady=(6, 0))

    def _build_goal_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 8))

        ttk.Label(card, text="Goal Description", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6))

        self.goal_text = tk.Text(card, height=4, width=36, bg=ENTRY_BG, fg=TEXT,
                                  insertbackground=TEXT, relief="flat", wrap="word",
                                  font=("Segoe UI", 10), padx=8, pady=6)
        self.goal_text.pack(fill="x")
        self.goal_text.insert("1.0", GOAL_PRESETS["village"])

    def _build_actions(self, parent):
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(0, 8))

        self.generate_btn = tk.Button(
            actions, text="Generate Map", command=self._on_generate,
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            activeforeground="white", relief="flat",
            font=("Segoe UI", 12, "bold"), padx=20, pady=8, cursor="hand2",
        )
        self.generate_btn.pack(fill="x")

        btn_row = ttk.Frame(actions)
        btn_row.pack(fill="x", pady=(6, 0))

        self.open_btn = tk.Button(
            btn_row, text="Open Output Folder", command=self._open_output,
            bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
            activeforeground=TEXT, relief="flat",
            font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2",
        )
        self.open_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.save_btn = tk.Button(
            btn_row, text="Save Map As...", command=self._save_as,
            bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
            activeforeground=TEXT, relief="flat",
            font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2",
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(3, 0))

    def _build_status(self, parent):
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                       style="Status.TLabel")
        self.status_label.pack(anchor="w")

        self.info_var = tk.StringVar(value="")
        self.info_label = ttk.Label(status_frame, textvariable=self.info_var,
                                     style="Subtitle.TLabel")
        self.info_label.pack(anchor="w")

        # Log area
        self.log_text = tk.Text(parent, height=8, width=36, bg=BG_LIGHT, fg=TEXT_DIM,
                                 relief="flat", font=("Consolas", 8), padx=6, pady=4,
                                 state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _build_preview(self, parent):
        preview_card = ttk.Frame(parent, style="Card.TFrame", padding=8)
        preview_card.pack(fill="both", expand=True)

        ttk.Label(preview_card, text="Preview", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 6))

        self.preview_canvas = tk.Canvas(preview_card, bg="#0a0a1a",
                                         highlightthickness=0)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

        # Placeholder text
        self.preview_canvas.create_text(
            300, 250, text="Generate a map to see preview",
            fill=TEXT_DIM, font=("Segoe UI", 14), tags="placeholder",
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_type_changed(self, event=None):
        map_type = self.map_type_var.get()
        if map_type in GOAL_PRESETS:
            self.goal_text.delete("1.0", "end")
            self.goal_text.insert("1.0", GOAL_PRESETS[map_type])

    def _randomize_seed(self):
        self.seed_var.set(str(random.randint(1, 99999)))

    def _on_canvas_resize(self, event=None):
        if self.preview_image is not None:
            self._update_preview()

    def _on_generate(self):
        if self.generating:
            return
        self.generating = True
        self.generate_btn.config(text="Generating...", bg=TEXT_DIM, state="disabled")
        self.status_var.set("Generating...")
        self.info_var.set("")
        self._log_clear()

        # Gather params
        params = {
            "goal": self.goal_text.get("1.0", "end").strip(),
            "map_type": self.map_type_var.get(),
            "biome": self.biome_var.get(),
            "size": SIZES.get(self.size_display_var.get(), "standard"),
            "seed": int(self.seed_var.get()) if self.seed_var.get().isdigit() else 42,
            "unity_export": self.unity_var.get(),
            "output_dir": "./output/unity_export",
        }

        self._log(f"Map: {params['map_type']} | Biome: {params['biome']}")
        self._log(f"Size: {params['size']} | Seed: {params['seed']}")
        self._log(f"Goal: {params['goal'][:60]}...")
        self._log("")

        thread = threading.Thread(target=self._generate_worker, args=(params,), daemon=True)
        thread.start()

    def _generate_worker(self, params):
        start = time.time()
        try:
            result = self.generator.generate(**params)
            elapsed = time.time() - start
            self.root.after(0, self._on_generate_done, result, elapsed)
        except Exception as e:
            elapsed = time.time() - start
            self.root.after(0, self._on_generate_error, str(e), elapsed)

    def _on_generate_done(self, result, elapsed):
        self.generating = False
        self.last_result = result
        self.generate_btn.config(text="Generate Map", bg=ACCENT, state="normal")

        status = result.get("status", "unknown")
        map_name = result.get("map_name", "Untitled")
        output_path = result.get("output_path", "")
        config = result.get("config", {})
        state_info = result.get("state", {})

        entities = state_info.get("entities", 0) if isinstance(state_info, dict) else 0

        self.status_var.set(f"Done -- {map_name}")
        self.info_var.set(f"{elapsed:.1f}s | {entities} entities | {status}")

        self._log(f"Status: {status}")
        self._log(f"Name: {map_name}")
        self._log(f"Time: {elapsed:.1f}s")
        self._log(f"Entities: {entities}")
        self._log(f"Output: {output_path}")

        completed = result.get("agents_completed", [])
        if completed:
            self._log(f"Agents: {len(completed)} completed")

        unity_files = result.get("unity_files", {})
        if unity_files:
            self._log(f"Unity exports: {len(unity_files)}")

        # Load and show preview
        if output_path and os.path.exists(output_path):
            self.preview_image = Image.open(output_path)
            self._update_preview()

    def _on_generate_error(self, error_msg, elapsed):
        self.generating = False
        self.generate_btn.config(text="Generate Map", bg=ACCENT, state="normal")
        self.status_var.set("Error")
        self.info_var.set(f"Failed after {elapsed:.1f}s")
        self._log(f"ERROR: {error_msg}")

    def _update_preview(self):
        if self.preview_image is None:
            return

        self.preview_canvas.delete("all")

        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            return

        img_w, img_h = self.preview_image.size
        scale = min(canvas_w / img_w, canvas_h / img_h, 1.0)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        resized = self.preview_image.resize((new_w, new_h), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(resized)

        x = canvas_w // 2
        y = canvas_h // 2
        self.preview_canvas.create_image(x, y, image=self._tk_image, anchor="center")

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
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
            initialfile=f"{self.last_result.get('map_name', 'map')}.png" if self.last_result else "map.png",
        )
        if path:
            self.preview_image.save(path, quality=95)
            self._log(f"Saved: {path}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
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

    # Set dark title bar on Windows 11
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
