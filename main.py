import sys
import os

# Add root and src package directories to sys.path so all imports resolve seamlessly
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
for p in (_ROOT, _SRC, os.path.join(_SRC, "core"), os.path.join(_SRC, "tools"), os.path.join(_SRC, "ui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.ui.main_gui import run_app

if __name__ == "__main__":
    run_app()
   