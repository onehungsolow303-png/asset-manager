"""
Map Generator Launcher -- Hub for Generate Maps, Playtest Viewer, and Map Gallery.
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import subprocess
import os
import sys
import re
import json

# ---------------------------------------------------------------------------
# Theme (matches gui.py)
# ---------------------------------------------------------------------------
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

THUMB_SIZE = (180, 180)
GALLERY_COLUMNS = 4

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_output_dir():
    return os.path.join(get_project_root(), "output")


def parse_map_name(filename):
    """Parse 'castle_forest_42.png' -> 'Castle - Forest - Seed 42'."""
    name = os.path.splitext(filename)[0]
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        seed = parts[1]
        rest = parts[0].rsplit("_", 1)
        if len(rest) == 2:
            map_type, biome = rest
            return f"{map_type.replace('_', ' ').title()} - {biome.title()} - Seed {seed}"
    return name.replace("_", " ").title()


def find_maps():
    """Find all generated map PNGs in the output directory."""
    output_dir = get_output_dir()
    if not os.path.isdir(output_dir):
        return []

    maps = []
    for fname in sorted(os.listdir(output_dir), reverse=True):
        if not fname.lower().endswith(".png"):
            continue
        # Skip per-layer z-level exports (z_0.png, z_neg1.png, etc.)
        if re.match(r"^z_(?:neg)?\d+\.png$", fname, re.IGNORECASE):
            continue
        fpath = os.path.join(output_dir, fname)
        if not os.path.isfile(fpath):
            continue
        maps.append({
            "filename": fname,
            "path": fpath,
            "display_name": parse_map_name(fname),
        })
    return maps


def has_playtest_data():
    """Check if the output root has map_data.json for playtesting."""
    return os.path.isfile(os.path.join(get_output_dir(), "map_data.json"))


def get_playtest_info():
    """Get info about the current playtest-ready map."""
    json_path = os.path.join(get_output_dir(), "map_data.json")
    if not os.path.isfile(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = data.get("config", {})
        return {
            "map_type": cfg.get("map_type", "?"),
            "biome": cfg.get("biome", "?"),
            "seed": cfg.get("seed", "?"),
            "z_levels": len(data.get("z_levels", [])),
            "spawns": len(data.get("spawns", [])),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Launcher Window
# ---------------------------------------------------------------------------

class LauncherWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Map Generator")
        self.root.configure(bg=BG)
        self.root.geometry("860x700")
        self.root.minsize(700, 500)

        self.thumb_cache = {}

        self._build_header()
        self._build_actions()
        self._build_gallery()

    # -- Header --

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG_DARK, pady=16)
        header.pack(fill="x")

        tk.Label(
            header, text="Map Generator",
            font=("Segoe UI", 22, "bold"), fg=GOLD, bg=BG_DARK,
        ).pack()
        tk.Label(
            header, text="Procedural Map Generation & Playtest Viewer",
            font=("Segoe UI", 10), fg=TEXT_DIM, bg=BG_DARK,
        ).pack()

    # -- Action Buttons --

    def _build_actions(self):
        row = tk.Frame(self.root, bg=BG, pady=12, padx=20)
        row.pack(fill="x")

        # Generate Maps button
        gen_frame = tk.Frame(row, bg=BG_CARD, padx=16, pady=12)
        gen_frame.pack(side="left", expand=True, fill="both", padx=(0, 6))

        tk.Label(
            gen_frame, text="Generate Maps",
            font=("Segoe UI", 13, "bold"), fg=TEXT, bg=BG_CARD,
        ).pack(anchor="w")
        tk.Label(
            gen_frame, text="Open the full map generator with all options",
            font=("Segoe UI", 9), fg=TEXT_DIM, bg=BG_CARD,
        ).pack(anchor="w", pady=(2, 8))

        self._make_button(gen_frame, "Open Generator", ACCENT, ACCENT_HOVER, self._on_generate)

        # Playtest button
        play_frame = tk.Frame(row, bg=BG_CARD, padx=16, pady=12)
        play_frame.pack(side="left", expand=True, fill="both", padx=(6, 0))

        tk.Label(
            play_frame, text="Quick Playtest",
            font=("Segoe UI", 13, "bold"), fg=TEXT, bg=BG_CARD,
        ).pack(anchor="w")

        info = get_playtest_info()
        if info:
            desc = f"{info['map_type'].replace('_',' ').title()} - {info['biome'].title()} | {info['z_levels']} levels, {info['spawns']} spawns"
        else:
            desc = "No playtest data available. Generate a map first."
        self.playtest_desc = tk.Label(
            play_frame, text=desc,
            font=("Segoe UI", 9), fg=TEXT_DIM, bg=BG_CARD, wraplength=300, justify="left",
        )
        self.playtest_desc.pack(anchor="w", pady=(2, 8))

        self.playtest_btn = self._make_button(
            play_frame, "Launch Viewer", SUCCESS, "#27ae60", self._on_playtest,
            state="normal" if info else "disabled",
        )

    def _make_button(self, parent, text, bg_color, hover_color, command, state="normal"):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg_color, fg="white", activebackground=hover_color,
            activeforeground="white", relief="flat",
            font=("Segoe UI", 10, "bold"), pady=6, padx=16,
            cursor="hand2", state=state,
        )
        btn.pack(anchor="w")

        def on_enter(e):
            if btn["state"] != "disabled":
                btn.config(bg=hover_color)

        def on_leave(e):
            if btn["state"] != "disabled":
                btn.config(bg=bg_color)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # -- Gallery --

    def _build_gallery(self):
        sep = tk.Frame(self.root, bg=BG_LIGHT, height=1)
        sep.pack(fill="x", padx=20, pady=(8, 0))

        gallery_header = tk.Frame(self.root, bg=BG, padx=20, pady=8)
        gallery_header.pack(fill="x")

        tk.Label(
            gallery_header, text="Generated Maps",
            font=("Segoe UI", 13, "bold"), fg=TEXT, bg=BG,
        ).pack(side="left")

        refresh_btn = tk.Button(
            gallery_header, text="Refresh", command=self._refresh_gallery,
            bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
            activeforeground=TEXT, relief="flat",
            font=("Segoe UI", 8), padx=8, cursor="hand2",
        )
        refresh_btn.pack(side="right")

        # Scrollable gallery
        container = tk.Frame(self.root, bg=BG)
        container.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self.gallery_canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_inner = tk.Frame(self.gallery_canvas, bg=BG)

        self.gallery_inner.bind("<Configure>",
            lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
        self.gallery_canvas.create_window((0, 0), window=self.gallery_inner, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=scrollbar.set)

        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        def _on_mousewheel(event):
            self.gallery_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.gallery_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._refresh_gallery()

    def _refresh_gallery(self):
        for widget in self.gallery_inner.winfo_children():
            widget.destroy()
        self.thumb_cache.clear()

        maps = find_maps()
        if not maps:
            tk.Label(
                self.gallery_inner, text="No maps generated yet. Click 'Open Generator' to create one.",
                font=("Segoe UI", 10), fg=TEXT_DIM, bg=BG, pady=40,
            ).grid(row=0, column=0, columnspan=GALLERY_COLUMNS)
            return

        # Check which map is the current playtest target
        playtest_info = get_playtest_info()
        playtest_filename = None
        if playtest_info:
            mt = playtest_info["map_type"]
            bi = playtest_info["biome"]
            sd = playtest_info["seed"]
            playtest_filename = f"{mt}_{bi}_{sd}.png"

        for i, map_info in enumerate(maps):
            row = i // GALLERY_COLUMNS
            col = i % GALLERY_COLUMNS
            self._make_gallery_card(
                self.gallery_inner, map_info, row, col,
                is_playtest=(map_info["filename"] == playtest_filename),
            )

        # Update playtest info
        info = get_playtest_info()
        if info:
            desc = f"{info['map_type'].replace('_',' ').title()} - {info['biome'].title()} | {info['z_levels']} levels, {info['spawns']} spawns"
            self.playtest_desc.config(text=desc)
            self.playtest_btn.config(state="normal")
        else:
            self.playtest_desc.config(text="No playtest data available. Generate a map first.")
            self.playtest_btn.config(state="disabled")

    def _make_gallery_card(self, parent, map_info, row, col, is_playtest=False):
        border_color = GOLD if is_playtest else BG_CARD
        card = tk.Frame(parent, bg=border_color, padx=2, pady=2)
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        parent.columnconfigure(col, weight=1)

        inner = tk.Frame(card, bg=BG_LIGHT, padx=6, pady=6)
        inner.pack(fill="both", expand=True)

        # Thumbnail
        try:
            img = Image.open(map_info["path"])
            img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.thumb_cache[map_info["filename"]] = photo

            label = tk.Label(inner, image=photo, bg=BG_LIGHT, cursor="hand2")
            label.pack()
            label.bind("<Button-1>", lambda e, p=map_info["path"]: self._open_image(p))
        except Exception:
            tk.Label(inner, text="[No Preview]", fg=TEXT_DIM, bg=BG_LIGHT,
                     width=20, height=8).pack()

        # Map name
        tk.Label(
            inner, text=map_info["display_name"],
            font=("Segoe UI", 8, "bold"), fg=TEXT, bg=BG_LIGHT,
            wraplength=170, justify="center",
        ).pack(pady=(4, 2))

        # Playtest badge or View button
        if is_playtest:
            btn_frame = tk.Frame(inner, bg=BG_LIGHT)
            btn_frame.pack(pady=(0, 2))
            tk.Button(
                btn_frame, text="Playtest", command=self._on_playtest,
                bg=SUCCESS, fg="white", activebackground="#27ae60",
                activeforeground="white", relief="flat",
                font=("Segoe UI", 8, "bold"), padx=8, cursor="hand2",
            ).pack(side="left", padx=1)
            tk.Button(
                btn_frame, text="View", command=lambda p=map_info["path"]: self._open_image(p),
                bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
                activeforeground=TEXT, relief="flat",
                font=("Segoe UI", 8), padx=8, cursor="hand2",
            ).pack(side="left", padx=1)
        else:
            tk.Button(
                inner, text="View", command=lambda p=map_info["path"]: self._open_image(p),
                bg=BG_CARD, fg=TEXT_DIM, activebackground=BG_LIGHT,
                activeforeground=TEXT, relief="flat",
                font=("Segoe UI", 8), padx=8, cursor="hand2",
            ).pack(pady=(0, 2))

    # -- Actions --

    def _on_generate(self):
        python_exe = sys.executable
        gui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.py")
        subprocess.Popen([python_exe, gui_path])

    def _on_playtest(self):
        output_dir = get_output_dir()
        json_path = os.path.join(output_dir, "map_data.json")
        if not os.path.isfile(json_path):
            messagebox.showinfo("Playtest", "No map_data.json found. Generate a map first.")
            return

        python_exe = sys.executable
        viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer", "main.py")
        subprocess.Popen([python_exe, viewer_path, output_dir])

    def _open_image(self, path):
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])


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

    app = LauncherWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
