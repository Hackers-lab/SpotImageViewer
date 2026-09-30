import os
import sys
import threading
import time


class SplashScreen:
    """
    Ultra-sleek, modern Studio splash screen.
    Features:
    - Frosted dark canvas aesthetic (#0a0f1d / #0f172a / #1e293b)
    - Gradient accent highlight bar
    - Brand logo badge with glow container
    - Modern typography hierarchy using Segoe UI Variable / Segoe UI
    - Smooth animated custom glowing progress bar
    - Dynamic status pills and engine indicators
    - Zero external heavy dependencies (loads in <15ms)
    """

    def __init__(self, title="SPOT IMAGE VIEWER", version="v20.56"):
        self.title_text = title
        self.version_text = version
        self._root = None
        self._status_lbl = None
        self._progress_canvas = None
        self._progress_pos = 0.0
        self._progress_dir = 1
        self._animating = False
        self._closed = False
        self._thread = None
        self._ready_event = threading.Event()

    def start(self):
        """Starts the splash screen in a dedicated daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="siv-splash")
        self._thread.start()

    def _run(self):
        try:
            import tkinter as tk
            from tkinter import ttk

            root = tk.Tk()
            self._root = root
            root.title("Spot Image Viewer Studio")
            root.overrideredirect(True)
            root.attributes("-topmost", True)

            # Dimensions & screen centering
            w, h = 520, 260
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            root.geometry(f"{w}x{h}+{x}+{y}")
            root.configure(bg="#0b1120")

            # Main outer wrapper with subtle 1px border glow
            outer_border = tk.Frame(root, bg="#1e293b", bd=1)
            outer_border.pack(fill="both", expand=True, padx=1, pady=1)

            # Deep dark card background
            bg_card = tk.Frame(outer_border, bg="#0b1120")
            bg_card.pack(fill="both", expand=True)

            # Top gradient accent bar (Sky Blue to Indigo accent line)
            top_bar = tk.Canvas(bg_card, height=3, bg="#0b1120", bd=0, highlightthickness=0)
            top_bar.pack(fill="x", side="top")
            # Draw multi-stop gradient line
            segments = [
                (0.00, 0.20, "#0284c7"),
                (0.20, 0.50, "#38bdf8"),
                (0.50, 0.75, "#818cf8"),
                (0.75, 1.00, "#6366f1"),
            ]
            for start_f, end_f, color in segments:
                top_bar.create_rectangle(
                    int(w * start_f), 0, int(w * end_f), 3,
                    fill=color, outline=""
                )

            # Content container with generous breathing room
            content = tk.Frame(bg_card, bg="#0b1120")
            content.pack(fill="both", expand=True, padx=28, pady=(20, 22))

            # Header row: Icon Badge + App Meta
            header_row = tk.Frame(content, bg="#0b1120")
            header_row.pack(fill="x", anchor="w")

            # App icon box with rounded/glow appearance
            icon_box = tk.Canvas(header_row, width=44, height=44, bg="#0b1120", bd=0, highlightthickness=0)
            icon_box.pack(side="left", padx=(0, 16))

            # Draw glowing icon container
            icon_box.create_oval(2, 2, 42, 42, fill="#0f172a", outline="#1e293b", width=1)
            icon_box.create_oval(6, 6, 38, 38, fill="#0369a1", outline="#38bdf8", width=1)
            # Center icon symbol
            icon_box.create_text(22, 21, text="⚡", font=("Segoe UI", 16, "bold"), fill="#f0f9ff")

            # Try loading real app logo if PIL and file are available
            try:
                from PIL import Image, ImageTk
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                icon_path = os.path.join(base_dir, "assets", "spot_icon.png")
                if os.path.exists(icon_path):
                    im = Image.open(icon_path).convert("RGBA")
                    im = im.resize((32, 32), Image.Resampling.LANCZOS)
                    self._logo_photo = ImageTk.PhotoImage(im)
                    icon_box.delete("all")
                    icon_box.create_oval(1, 1, 43, 43, fill="#0f172a", outline="#38bdf8", width=1.5)
                    icon_box.create_image(22, 22, image=self._logo_photo)
            except Exception:
                pass

            # Title & category block
            title_block = tk.Frame(header_row, bg="#0b1120")
            title_block.pack(side="left", fill="x", expand=True)

            # Tagline badge + Edition
            meta_tag = tk.Label(
                title_block,
                text=f"{self.title_text}  •  {self.version_text.upper()}",
                fg="#38bdf8",
                bg="#0b1120",
                font=("Segoe UI", 8, "bold")
            )
            meta_tag.pack(anchor="w")

            # Main product name
            app_title = tk.Label(
                title_block,
                text="Verification & Studio",
                fg="#f8fafc",
                bg="#0b1120",
                font=("Segoe UI Variable Display", 15, "bold") if "Segoe UI Variable Display" in root.tk.call('font', 'families') else ("Segoe UI", 15, "bold")
            )
            app_title.pack(anchor="w", pady=(1, 0))

            # Sub-description
            sub_lbl = tk.Label(
                title_block,
                text="High-Performance Meter Verification & Batch Billing Engine",
                fg="#64748b",
                bg="#0b1120",
                font=("Segoe UI", 8)
            )
            sub_lbl.pack(anchor="w")

            # Divider line
            divider = tk.Frame(content, height=1, bg="#1e293b")
            divider.pack(fill="x", pady=(18, 16))

            # Bottom Section: Modern Custom Smooth Progress Track
            prog_frame = tk.Frame(content, bg="#0b1120")
            prog_frame.pack(fill="x")

            # Progress track canvas (custom ultra-smooth indeterminate glowing pill)
            track_w = 464
            track_h = 4
            self._progress_canvas = tk.Canvas(
                prog_frame,
                width=track_w,
                height=track_h,
                bg="#1e293b",
                bd=0,
                highlightthickness=0
            )
            self._progress_canvas.pack(fill="x", pady=(0, 10))

            # Status footer row (Left: status text, Right: secure engine badge)
            footer_row = tk.Frame(prog_frame, bg="#0b1120")
            footer_row.pack(fill="x")

            self._status_lbl = tk.Label(
                footer_row,
                text="Starting application engine...",
                fg="#94a3b8",
                bg="#0b1120",
                font=("Segoe UI", 8)
            )
            self._status_lbl.pack(side="left")

            engine_pill = tk.Label(
                footer_row,
                text="ENTERPRISE CORE",
                fg="#475569",
                bg="#0b1120",
                font=("Segoe UI", 7, "bold")
            )
            engine_pill.pack(side="right")

            # Start smooth progress animation
            self._animating = True
            self._animate_progress(track_w, track_h)

            # Auto close safety timeout (15s)
            root.after(15000, self.close)

            # Signal that window is active
            self._ready_event.set()

            root.mainloop()
        except Exception:
            pass
        finally:
            self._ready_event.set()
            self._root = None

    def _animate_progress(self, track_w, track_h):
        """Animates a glowing sliding indicator across the track."""
        if not self._animating or not self._root or not self._progress_canvas:
            return

        try:
            bar_len = 130
            speed = 7
            self._progress_pos += speed * self._progress_dir

            if self._progress_pos + bar_len >= track_w:
                self._progress_pos = track_w - bar_len
                self._progress_dir = -1
            elif self._progress_pos <= 0:
                self._progress_pos = 0
                self._progress_dir = 1

            self._progress_canvas.delete("bar")
            x1 = int(self._progress_pos)
            x2 = int(self._progress_pos + bar_len)

            # Glowing pill with bright core
            self._progress_canvas.create_rectangle(
                x1, 0, x2, track_h,
                fill="#38bdf8", outline="", tags="bar"
            )
            # Center bright highlight
            cx = (x1 + x2) // 2
            hl_len = 50
            self._progress_canvas.create_rectangle(
                cx - hl_len // 2, 0, cx + hl_len // 2, track_h,
                fill="#bae6fd", outline="", tags="bar"
            )

            if self._root:
                self._root.after(20, lambda: self._animate_progress(track_w, track_h))
        except Exception:
            pass

    def update_status(self, text):
        """Thread-safe status text update."""
        if self._closed or not self._root:
            return
        try:
            self._root.after(0, lambda: self._safe_set_status(text))
        except Exception:
            pass

    def _safe_set_status(self, text):
        if self._status_lbl and self._root:
            try:
                self._status_lbl.configure(text=text)
            except Exception:
                pass

    def close(self):
        """Thread-safe close and destroy with clean animation stop."""
        if self._closed:
            return
        self._closed = True
        self._animating = False
        root = self._root
        if root:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass


_global_splash = None

def show_splash(title="SPOT IMAGE VIEWER", version="v20.56"):
    global _global_splash
    if _global_splash is None:
        _global_splash = SplashScreen(title=title, version=version)
        _global_splash.start()
    return _global_splash

def close_splash():
    global _global_splash
    if _global_splash is not None:
        _global_splash.close()
        _global_splash = None
