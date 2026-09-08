import os
import sys

# Support frozen PyInstaller bundle environment as well as development
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SRC_DIR = os.path.join(BASE_DIR, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
BRIDGE_DIR = os.path.join(SRC_DIR, "bridge")
for p in [BASE_DIR, SRC_DIR, CORE_DIR, BRIDGE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Fix openpyxl compat issue where numpy has no attribute 'short'
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
    # Initialize local database tables if needed
    database.init_db()

    # Instantiate the Python RPC Bridge
    api = AppAPI()

    # Path to local HTML single page application
    html_file = os.path.join(SRC_DIR, "ui_web", "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join(BASE_DIR, "ui_web", "index.html")

    # Create PyWebView window with native Edge WebView2 engine
    window = webview.create_window(
        title="Spot Image Viewer & Verification Studio (v20.31)",
        url=f"file:///{html_file.replace(os.sep, '/')}",
        js_api=api,
        width=1340,
        height=850,
        min_size=(1000, 680),
        maximized=True
    )
    api.set_window(window)

    # Start the event loop with persistent local storage
    storage_dir = os.path.join(config.BASE_DIR, "webview_storage")
    try:
        os.makedirs(storage_dir, exist_ok=True)
    except Exception:
        pass
    webview.start(debug=False, private_mode=False, storage_path=storage_dir)

if __name__ == "__main__":
    main()
