"""
Independent native splash screen displayed during initial application startup.
Runs in a background thread to provide instant visual feedback while the Edge WebView2
runtime and PyWebView event loop initialize.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk


class SplashScreen:
    def __init__(self, title="SPOT IMAGE VIEWER", version="v20.55"):
        self.title_text = title
        self.version_text = version
        self._root = None
        self._status_lbl = None
        self._closed = False
        self._thread = None
        self._ready_event = threading.Event()

    def start(self):
        """Starts the splash screen in a dedicated daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="siv-splash")
        self._thread.start()

    def _run(self):
        try:
            root = tk.Tk()
            self._root = root
            root.overrideredirect(True)
            root.attributes('-topmost', True)

            # Center on primary monitor
            w, h = 460, 210
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            root.geometry(f"{w}x{h}+{x}+{y}")
            root.configure(bg="#0f172a")

            # Border container
            border = tk.Frame(root, bg="#334155", bd=1)
            border.pack(fill="both", expand=True, padx=1, pady=1)

            inner = tk.Frame(border, bg="#0f172a")
            inner.pack(fill="both", expand=True, padx=24, pady=22)

            # Header badge
            badge_frame = tk.Frame(inner, bg="#0f172a")
            badge_frame.pack(anchor="w")

            badge = tk.Label(
                badge_frame,
                text="⚡ " + self.title_text,
                fg="#38bdf8",
                bg="#0f172a",
                font=("Segoe UI", 10, "bold")
            )
            badge.pack(side="left")

            # Main Title
            title = tk.Label(
                inner,
                text="Verification & Analysis Studio",
                fg="#f8fafc",
                bg="#0f172a",
                font=("Segoe UI", 15, "bold")
            )
            title.pack(anchor="w", pady=(4, 0))

            # Subtitle
            sub = tk.Label(
                inner,
                text=f"Production Suite {self.version_text}  •  WBSEDCL",
                fg="#64748b",
                bg="#0f172a",
                font=("Segoe UI", 9)
            )
            sub.pack(anchor="w", pady=(0, 16))

            # Progress Bar
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass

            style.configure(
                "Splash.Horizontal.TProgressbar",
                troughcolor="#1e293b",
                bordercolor="#0f172a",
                background="#38bdf8",
                lightcolor="#38bdf8",
                darkcolor="#0284c7",
                thickness=4
            )

            pb = ttk.Progressbar(
                inner,
                style="Splash.Horizontal.TProgressbar",
                mode="indeterminate",
                length=410
            )
            pb.pack(fill="x", pady=(0, 10))
            pb.start(10)

            # Status message
            self._status_lbl = tk.Label(
                inner,
                text="Starting application engine...",
                fg="#94a3b8",
                bg="#0f172a",
                font=("Segoe UI", 9)
            )
            self._status_lbl.pack(anchor="w")

            # Safety auto-close after 12 seconds so splash never hangs if unhandled exception occurs
            root.after(12000, self.close)

            # Signal that splash window is created
            self._ready_event.set()

            root.mainloop()
        except Exception:
            pass
        finally:
            self._ready_event.set()
            self._root = None

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
        """Thread-safe close and destroy."""
        if self._closed:
            return
        self._closed = True
        root = self._root
        if root:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass


_global_splash = None

def show_splash(title="SPOT IMAGE VIEWER", version="v20.55"):
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
