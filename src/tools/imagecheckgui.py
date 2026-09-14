"""
Launcher entrypoint for Standalone Meter Audit Tool (imagecheckgui).
Preserves backward compatibility for PyInstaller spec and desktop shortcuts.
"""
import sys
import os

# Ensure package imports resolve in both development and PyInstaller bundled mode
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_TOOLS_DIR)
_ROOT_DIR = os.path.dirname(_SRC_DIR)

for p in (_TOOLS_DIR, _SRC_DIR, _ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from tools.meter_audit.app import MeterAuditApp
except ImportError:
    from meter_audit.app import MeterAuditApp


def main():
    app = MeterAuditApp()

    def on_closing():
        app.prefetcher.stop()
        app.stop_keep_alive_timer()
        app.destroy()
        sys.exit(0)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
