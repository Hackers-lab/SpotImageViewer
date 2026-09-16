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

def _cleanup_stale_webview_processes():
    """
    If no other active SpotImageViewer process is running,
    terminate any lingering msedgewebview2.exe processes using our storage_dir
    so the warm profile cache can be reused immediately without lock contention.
    """
    try:
        import psutil
        current_pid = os.getpid()
        other_active = []
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            if p.pid == current_pid:
                continue
            name = (p.info['name'] or '').lower()
            cmdline = p.info['cmdline'] or []
            if 'python' in name and any('main.py' in arg or 'main_web.py' in arg for arg in cmdline):
                other_active.append(p.pid)
            elif 'spotimageviewer' in name:
                other_active.append(p.pid)

        if not other_active:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if p.info['name'] and 'msedgewebview2' in p.info['name'].lower():
                        cmd = ' '.join(p.info['cmdline'] or [])
                        if 'spotbillfiles' in cmd.lower() or 'spot_webview' in cmd.lower():
                            p.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception:
        pass


def main():
    import threading
    from core import perf_log
    perf_log.clear_log()
    perf_log.log_perf("PY_BOOT_START", details="Python process initialized, AppAPI ready")

    # Launch independent native splash screen immediately (<50ms)
    try:
        from ui_splash import show_splash, close_splash
        splash = show_splash(version=f"v{config.CURRENT_VERSION}")
        perf_log.log_perf("SPLASH_SHOWN", details="Independent native splash screen active")
    except Exception:
        splash = None
        def close_splash(): pass

    # Instantiate the Python RPC Bridge immediately
    api = AppAPI()

    # Clean up stale WebView2 zombies so lockfile is free and warm cache is used
    _cleanup_stale_webview_processes()

    # Patch numpy in background — saves 150-500ms startup time
    threading.Thread(target=_patch_numpy, daemon=True).start()

    # Initialize local database tables asynchronously so the WebView window opens immediately
    # without waiting for index or disk checks on huge (2M+) databases.
    # The init_db_ready event (in database module) is set when done, preventing
    # the startup deadlock where UI reads compete with schema migration locks.
    if splash:
        splash.update_status("Initializing database & services...")
    threading.Thread(target=database.init_db, daemon=True).start()

    # Ensure modular HTML partials are assembled if updated (<2ms)
    try:
        from ui_web.build_ui import assemble_index_html
        assemble_index_html()
    except Exception:
        pass

    # Path to local HTML single page application
    html_file = os.path.join(SRC_DIR, "ui_web", "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(BASE_DIR, "ui_web", "index.html")

    # Ensure webview storage path is accessible or fall back to a persistent warm alternate directory
    storage_dir = os.path.join(config.BASE_DIR, "webview_storage")
    lock_file = os.path.join(storage_dir, "EBWebView", "lockfile")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "a+b"):
                pass
        except (IOError, OSError, PermissionError):
            import tempfile
            storage_dir = os.path.join(tempfile.gettempdir(), "spot_webview_cache_alt")
            perf_log.log_perf("STORAGE_LOCKED", details="Using persistent warm alternate cache to prevent 0x800700AA")
    try:
        os.makedirs(storage_dir, exist_ok=True)
    except Exception:
        pass

    # Create PyWebView window with native Edge WebView2 engine and dark background
    if splash:
        splash.update_status("Starting WebView2 engine...")
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
            window.show()
            perf_log.log_perf("WINDOW_SHOWN", details="App window revealed on loaded event")
        except Exception:
            pass
        try:
            close_splash()
        except Exception:
            pass
        try:
            window.evaluate_js("if (typeof window.safeInitApp === 'function') { window.safeInitApp(); }")
        except Exception:
            pass

    window.events.loaded += _on_loaded

    def _on_closed():
        try:
            close_splash()
        except Exception:
            pass
        try:
            import psutil
            parent = psutil.Process(os.getpid())
            for child in parent.children(recursive=True):
                if 'msedgewebview2' in child.name().lower():
                    child.terminate()
        except Exception:
            pass

    window.events.closed += _on_closed

    # Fallback safety: ensure window is revealed within 3.5s even if JS initialization has a glitch
    import time
    def _safety_reveal():
        time.sleep(3.5)
        try:
            window.show()
        except Exception:
            pass
        try:
            close_splash()
        except Exception:
            pass
    threading.Thread(target=_safety_reveal, daemon=True).start()

    perf_log.log_perf("WEBVIEW_STARTING", details="Calling webview.start() event loop")
    webview.start(debug=False, private_mode=False, storage_path=storage_dir)

if __name__ == "__main__":
    main()
