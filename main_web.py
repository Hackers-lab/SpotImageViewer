import os
import sys

# Ensure src and src/core are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
CORE_DIR = os.path.join(SRC_DIR, "core")
for p in [SRC_DIR, CORE_DIR, BASE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import webview
from core import database
from bridge.app_api import AppAPI

def main():
    # Initialize local database tables if needed
    database.init_db()

    # Instantiate the Python RPC Bridge
    api = AppAPI()

    # Path to local HTML single page application
    html_file = os.path.join(SRC_DIR, "ui_web", "index.html")

    # Create PyWebView window with native Edge WebView2 engine
    window = webview.create_window(
        title="Spot Image Viewer & Verification Studio (v19.4)",
        url=f"file:///{html_file.replace(os.sep, '/')}",
        js_api=api,
        width=1340,
        height=850,
        min_size=(1000, 680)
    )

    # Start the event loop
    webview.start(debug=False)

if __name__ == "__main__":
    main()
