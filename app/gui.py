import os
import sys
from pathlib import Path
from typing import Optional
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Ensure the parent directory is in the path to find the 'oppsie' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import oppsie

# Modern dark theme colors
COLORS = {
    "bg": "#0D0D0D",
    "surface": "#1A1A1A",
    "surface_light": "#2A2A2A",
    "accent": "#00E5FF",
    "accent_hover": "#00B8D4",
    "text_main": "#E0E0E0",
    "text_dim": "#888888",
    "text_accent": "#000000",
}

def load_image_from_path(path: str | os.PathLike) -> Image.Image:
    cleaned_path = Path(str(path).strip().strip('"').strip("'").strip()).resolve()
    if cleaned_path.suffix.lower() == ".oppsie":
        with open(cleaned_path, "rb") as handle:
            return oppsie.decode(handle.read())
    return Image.open(cleaned_path)

class OppsieViewerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Oppsie | Image Viewer")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(600, 400)

        # Image state
        self.image: Optional[Image.Image] = None
        self.photo = None
        self.zoom_scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_data = {"x": 0, "y": 0}
        self.status_var = tk.StringVar(value="Ready – Open an image to start")

        self._setup_style()
        self._build_ui()
        self._bind_shortcuts()

    def _setup_style(self) -> None:
        """Configure ttk styles for a modern look."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Toolbar.TFrame", background=COLORS["surface"])
        style.configure("Status.TLabel", background=COLORS["bg"], foreground=COLORS["text_dim"],
                        font=("Consolas", 9), anchor="w")
        style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["text_main"],
                        font=("Segoe UI", 12, "bold"), anchor="w")

    def _build_ui(self) -> None:
        # --- Toolbar ---
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", height=50)
        toolbar.pack(fill=tk.X, side=tk.TOP, pady=(0, 10))
        toolbar.pack_propagate(False)

        # Buttons: using tk.Button for full colour control
        btn_open = self._make_tool_button(toolbar, "Open", self.open_file)
        btn_open.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        btn_zoom_in = self._make_tool_button(toolbar, "+ Zoom In", self.zoom_in)
        btn_zoom_in.pack(side=tk.LEFT, padx=2, pady=8)

        btn_zoom_out = self._make_tool_button(toolbar, "- Zoom Out", self.zoom_out)
        btn_zoom_out.pack(side=tk.LEFT, padx=2, pady=8)

        btn_fit = self._make_tool_button(toolbar, "Fit", self.fit_to_window)
        btn_fit.pack(side=tk.LEFT, padx=2, pady=8)

        btn_reset = self._make_tool_button(toolbar, "Reset", self.reset_view)
        btn_reset.pack(side=tk.LEFT, padx=2, pady=8)

        # Spacer to push right-aligned info (optional)
        spacer = tk.Frame(toolbar, bg=COLORS["surface"])
        spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # --- Main Canvas ---
        self.canvas = tk.Canvas(
            self.root,
            bg=COLORS["bg"],
            highlightthickness=2,
            highlightbackground=COLORS["surface_light"],
            relief=tk.FLAT,
            cursor="hand2"  # indicates draggable
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        # Bind mouse events
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # --- Status Bar ---
        self.status_label = ttk.Label(self.root, style="Status.TLabel", textvariable=self.status_var)
        self.status_label.pack(fill=tk.X, padx=20, pady=(0, 15))

    def _make_tool_button(self, parent, text, command):
        """Helper to create a consistent flat button with hover effects."""
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLORS["surface_light"],
            fg=COLORS["text_main"],
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
            activebackground=COLORS["accent"],
            activeforeground=COLORS["text_accent"],
            borderwidth=0,
            highlightthickness=0
        )
        # Hover effect using events
        def on_enter(e):
            btn.config(bg=COLORS["accent"], fg=COLORS["text_accent"])
        def on_leave(e):
            btn.config(bg=COLORS["surface_light"], fg=COLORS["text_main"])
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<plus>", lambda e: self.zoom_in())
        self.root.bind("<KP_Add>", lambda e: self.zoom_in())
        self.root.bind("<minus>", lambda e: self.zoom_out())
        self.root.bind("<KP_Subtract>", lambda e: self.zoom_out())
        self.root.bind("<0>", lambda e: self.fit_to_window())
        self.root.bind("<r>", lambda e: self.reset_view())
        self.root.bind("<R>", lambda e: self.reset_view())

    # --- Zoom / Pan / Fit / Reset ---
    def zoom_in(self) -> None:
        if self.image:
            self.zoom_scale *= 1.1
            self._display_image()

    def zoom_out(self) -> None:
        if self.image:
            self.zoom_scale *= 0.9
            self._display_image()

    def fit_to_window(self) -> None:
        if not self.image:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            return
        base_w, base_h = self.image.size
        scale_w = (canvas_w - 20) / base_w   # small margin
        scale_h = (canvas_h - 20) / base_h
        self.zoom_scale = min(scale_w, scale_h, 5.0)  # cap to avoid extreme zoom
        self.pan_x = 0
        self.pan_y = 0
        self._display_image()

    def reset_view(self) -> None:
        if self.image:
            self.zoom_scale = 1.0
            self.pan_x = 0
            self.pan_y = 0
            self._display_image()

    # --- File Open ---
    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Image or .oppsie file",
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.bmp *.webp *.gif *.oppsie"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            self.image = load_image_from_path(path)
            self._current_path = path  # store for status
            self.zoom_scale = 1.0
            self.pan_x = 0
            self.pan_y = 0
            self._display_image()
            # Update status with image info
            w, h = self.image.size
            self.status_var.set(f"File: {Path(path).name}  |  {w}x{h}  |  Zoom: 100%  |  Pan: (0, 0)")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open file:\n{exc}")

    # --- Display & Events ---
    def _display_image(self) -> None:
        if not self.image:
            return

        base_w, base_h = self.image.size
        new_w = max(1, int(base_w * self.zoom_scale))
        new_h = max(1, int(base_h * self.zoom_scale))

        display_img = self.image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(display_img)

        self.canvas.delete("all")
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Center with pan offset
        self.canvas.create_image(
            (canvas_w // 2) + self.pan_x,
            (canvas_h // 2) + self.pan_y,
            image=self.photo,
            anchor=tk.CENTER
        )

        # Update status with zoom and pan info
        zoom_percent = int(round(self.zoom_scale * 100))
        self.status_var.set(
            f"File: {self._get_filename()}  |  {base_w}x{base_h}  |  Zoom: {zoom_percent}%  |  Pan: ({self.pan_x}, {self.pan_y})"
        )

    def _get_filename(self) -> str:
        if hasattr(self, '_current_path') and self._current_path:
            return Path(self._current_path).name
        return "Untitled"

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Redraw image when canvas size changes."""
        if self.image:
            self._display_image()

    def _on_drag_start(self, event: tk.Event) -> None:
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self.image:
            return
        delta_x = event.x - self.drag_data["x"]
        delta_y = event.y - self.drag_data["y"]
        self.pan_x += delta_x
        self.pan_y += delta_y
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self._display_image()

    def _on_zoom(self, event: tk.Event) -> None:
        if not self.image:
            return
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_scale *= factor
        self._display_image()

    # --- Run ---
    def run(self) -> None:
        self.root.mainloop()

if __name__ == "__main__":
    app = OppsieViewerApp()
    app.run()