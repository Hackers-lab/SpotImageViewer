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

import logging
import time

class StreamTee:
    def __init__(self, stream, filepath):
        self.stream = stream
        self.filepath = filepath
        self.encoding = getattr(stream, "encoding", "utf-8") or "utf-8"
        self._file = None

    def _get_file(self):
        if self._file is None or self._file.closed:
            try:
                self._file = open(self.filepath, "a", encoding="utf-8", buffering=1)
            except Exception:
                self._file = None
        return self._file

    def write(self, s):
        try:
            if self.stream:
                self.stream.write(s)
                self.stream.flush()
        except Exception:
            pass
        try:
            f = self._get_file()
            if f and s:
                f.write(s)
                f.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self.stream:
                self.stream.flush()
        except Exception:
            pass
        try:
            f = self._get_file()
            if f:
                f.flush()
        except Exception:
            pass

    def fileno(self):
        if hasattr(self.stream, "fileno"):
            try:
                return self.stream.fileno()
            except Exception:
                pass
        return 1

    def isatty(self):
        if hasattr(self.stream, "isatty"):
            try:
                return self.stream.isatty()
            except Exception:
                pass
        return False

    @property
    def buffer(self):
        return getattr(self.stream, "buffer", self.stream)

def setup_logging():
    try:
        import logging
        log_file_path = os.path.join(BASE_DIR, "app_debug.log")
        sys.stdout = StreamTee(sys.stdout, log_file_path)
        sys.stderr = StreamTee(sys.stderr, log_file_path)

        # Route pywebview logger through sys.stderr (StreamTee)
        wv_logger = logging.getLogger('pywebview')
        wv_logger.handlers.clear()
        wv_stream_handler = logging.StreamHandler(sys.stderr)
        wv_stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
        wv_logger.addHandler(wv_stream_handler)
        wv_logger.setLevel(logging.WARNING)

        print(f"=== SpotImageViewer Studio Session Started: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    except Exception:
        pass

def main():
    import threading

    setup_logging()

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

    # Create PyWebView window with native Edge WebView2 engine
    window = webview.create_window(
        title="Spot Image Viewer & Verification Studio (v20.51)",
        url=f"file:///{html_file.replace(os.sep, '/')}",
        js_api=api,
        width=1340,
        height=850,
        min_size=(1000, 680),
        maximized=True
    )
    api.set_window(window)

    def _on_loaded():
        try:
            window.evaluate_js("if (typeof window.safeInitApp === 'function') { window.safeInitApp(); }")
        except Exception:
            pass

    window.events.loaded += _on_loaded

    # Start the event loop with persistent local storage
    storage_dir = os.path.join(config.BASE_DIR, "webview_storage")
    try:
        os.makedirs(storage_dir, exist_ok=True)
    except Exception:
        pass
    webview.start(debug=False, private_mode=False, storage_path=storage_dir)

if __name__ == "__main__":
    main()
