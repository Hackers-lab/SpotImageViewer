import os
import sys

# Support frozen PyInstaller bundle environment as well as development
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SRC_DIR = os.path.join(BASE_DIR, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
BRIDGE_DIR = os.path.join(SRC_DIR, "bridge")
for p in [BASE_DIR, SRC_DIR, CORE_DIR, BRIDGE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Fix openpyxl compat issue where numpy has no attribute 'short'
# Deferred to background thread — numpy import takes 150-500ms and is not needed
# until user triggers Excel import/export.
def _patch_numpy():
    try:
        import numpy as _np
        if not hasattr(_np, 'short'):
            _np.short = _np.int16
        if not hasattr(_np, 'ushort'):
            _np.ushort = _np.uint16
        if not hasattr(_np, 'int_'):
            _np.int_ = _np.int64
        if not hasattr(_np, 'uint_'):
            _np.uint_ = _np.uint64
    except Exception:
        pass

import webview
try:
    from core import config, database
    from bridge.app_api import AppAPI
except ImportError:
    import config, database
    from app_api import AppAPI

def main():
    import threading
    from core import perf_log
    perf_log.clear_log()
    perf_log.log_perf("PY_BOOT_START", details="Python process initialized, AppAPI ready")

    # Instantiate the Python RPC Bridge immediately
    api = AppAPI()

    # Patch numpy in background — saves 150-500ms startup time
    threading.Thread(target=_patch_numpy, daemon=True).start()

    # Initialize local database tables asynchronously so the WebView window opens immediately
    # without waiting for index or disk checks on huge (2M+) databases.
    # The init_db_ready event (in database module) is set when done, preventing
    # the startup deadlock where UI reads compete with schema migration locks.
    threading.Thread(target=database.init_db, daemon=True).start()

    # Path to local HTML single page application
    html_file = os.path.join(SRC_DIR, "ui_web", "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(BASE_DIR, "ui_web", "index.html")

    # Ensure webview storage path is accessible or fall back to an instance-specific directory
    storage_dir = os.path.join(config.BASE_DIR, "webview_storage")
    lock_file = os.path.join(storage_dir, "EBWebView", "lockfile")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "a+b"):
                pass
        except (IOError, OSError, PermissionError):
            import tempfile
            storage_dir = os.path.join(tempfile.gettempdir(), f"spot_webview_storage_{os.getpid()}")
            perf_log.log_perf("STORAGE_LOCKED", details="Fallback to temp storage to avoid 0x800700AA freeze")
    try:
        os.makedirs(storage_dir, exist_ok=True)
    except Exception:
        pass

    # Create PyWebView window with native Edge WebView2 engine and dark background
    perf_log.log_perf("WINDOW_CREATING", details="webview.create_window started")
    window = webview.create_window(
        title=f"Spot Image Viewer & Verification Studio (v{config.CURRENT_VERSION})",
        url=f"file:///{html_file.replace(os.sep, '/')}",
        js_api=api,
        width=1340,
        height=850,
        min_size=(1000, 680),
        maximized=True,
        background_color='#0f172a',
        hidden=True
    )
    perf_log.log_perf("WINDOW_CREATED", details="webview.create_window finished")
    api.set_window(window)

    def _on_loaded():
        perf_log.log_perf("WEBVIEW_EVENT_LOADED", details="PyWebView window.events.loaded fired")
        try:
            window.evaluate_js("if (typeof window.safeInitApp === 'function') { window.safeInitApp(); }")
        except Exception:
            pass

    window.events.loaded += _on_loaded

    # Fallback safety: ensure window is revealed within 2.5s even if JS initialization has a glitch
    import time
    def _safety_reveal():
        time.sleep(2.5)
        try:
            window.show()
        except Exception:
            pass
    threading.Thread(target=_safety_reveal, daemon=True).start()

    perf_log.log_perf("WEBVIEW_STARTING", details="Calling webview.start() event loop")
    webview.start(debug=False, private_mode=False, storage_path=storage_dir)

if __name__ == "__main__":
    main()
