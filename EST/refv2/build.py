"""
Build script for ERP Estimate Generator.
Creates a distributable ZIP using PyInstaller (one-folder mode).

Usage:  python build.py
Output: dist/ERP_Estimate_v5.0.zip
"""

import subprocess
import shutil
import sys
import os
import zipfile

APP_NAME = "ERP_Estimate"
VERSION  = "5.0"
DIST_DIR = "dist"
FOLDER   = f"{APP_NAME}_v{VERSION}"

# Data files to copy next to the exe
DATA_FILES = ["rules.json", "logo.svg", "HELP.html"]

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

# ── 1. Clean previous build ─────────────────────────────────────────────────
for d in ("build", "dist", f"{APP_NAME}.spec"):
    p = os.path.join(ROOT, d)
    if os.path.isdir(p):
        shutil.rmtree(p)
    elif os.path.isfile(p):
        os.remove(p)

print("=== Building with PyInstaller ===")

# ── 2. Run PyInstaller ──────────────────────────────────────────────────────
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", APP_NAME,
    "--icon", "logo.ico",
    # Hidden imports that PyInstaller might miss
    "--hidden-import", "openpyxl",
    "--hidden-import", "sqlite3",
    "app.py",
]

result = subprocess.run(cmd)
if result.returncode != 0:
    print("PyInstaller build failed!")
    sys.exit(1)

print("=== PyInstaller done ===")

# ── 3. Copy data files to dist folder ───────────────────────────────────────
exe_dir = os.path.join(ROOT, DIST_DIR, APP_NAME)
for fname in DATA_FILES:
    src = os.path.join(ROOT, fname)
    dst = os.path.join(exe_dir, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  Copied {fname}")
    else:
        print(f"  WARNING: {fname} not found, skipping")

# ── 4. Rename dist folder to versioned name ─────────────────────────────────
final_dir = os.path.join(ROOT, DIST_DIR, FOLDER)
if os.path.exists(final_dir):
    shutil.rmtree(final_dir)
os.rename(exe_dir, final_dir)

# ── 5. Create ZIP ───────────────────────────────────────────────────────────
zip_path = os.path.join(ROOT, DIST_DIR, f"{FOLDER}.zip")
print(f"=== Creating {zip_path} ===")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(final_dir):
        for fn in filenames:
            abs_file = os.path.join(dirpath, fn)
            arc_name = os.path.join(FOLDER, os.path.relpath(abs_file, final_dir))
            zf.write(abs_file, arc_name)

zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
print(f"=== Done! {zip_path} ({zip_size_mb:.1f} MB) ===")
