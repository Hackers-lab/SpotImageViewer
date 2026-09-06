import sys
import os

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_SRC_DIR)

for p in (_ROOT_DIR, _SRC_DIR, os.path.join(_SRC_DIR, "core"), os.path.join(_SRC_DIR, "tools"), os.path.join(_SRC_DIR, "ui")):
    if p not in sys.path:
        sys.path.insert(0, p)
