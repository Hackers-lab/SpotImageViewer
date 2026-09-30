"""
Unified Release & Version Bump Automation Utility.
Single Source of Truth: Updates config.py, update.json, regenerates index.html,
and optionally commits, tags, and pushes in a single atomic command.

Usage:
    python bump_version.py 20.58 "Release title and notes..." [--push]
"""

import sys
import os
import json
import re
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "src", "core", "config.py")
UPDATE_JSON_FILE = os.path.join(PROJECT_ROOT, "update.json")
BUILD_UI_SCRIPT = os.path.join(PROJECT_ROOT, "src", "ui_web", "build_ui.py")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("    python bump_version.py <NEW_VERSION> [\"Release notes...\"] [--push]")
        print("Example:")
        print("    python bump_version.py 20.58 \"Bug fixes and performance enhancements\" --push")
        sys.exit(1)

    new_version_str = sys.argv[1].strip().lstrip("vV")
    try:
        new_version_num = float(new_version_str)
    except ValueError:
        print(f"Error: Invalid version number '{new_version_str}'. Must be decimal like 20.58")
        sys.exit(1)

    release_notes = ""
    do_push = False

    for arg in sys.argv[2:]:
        if arg == "--push":
            do_push = True
        elif not release_notes:
            release_notes = arg.strip()

    if not release_notes:
        release_notes = f"Release v{new_version_str}: General improvements and feature enhancements."

    print("=" * 60)
    print(f"  Bumping Version to: v{new_version_str}")
    print("=" * 60)

    # 1. Update src/core/config.py
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config_content = f.read()

    new_config_content = re.sub(
        r'CURRENT_VERSION\s*=\s*[0-9]+(?:\.[0-9]+)?',
        f'CURRENT_VERSION = {new_version_num}',
        config_content
    )
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(new_config_content)
    print(f"✓ Updated src/core/config.py (CURRENT_VERSION = {new_version_num})")

    # 2. Update update.json
    with open(UPDATE_JSON_FILE, "r", encoding="utf-8") as f:
        update_data = json.load(f)

    old_version = update_data.get("version")
    old_notes = update_data.get("release_notes", "")

    # Archive previous version into previous_versions array if it's different
    if old_version and old_version != new_version_num:
        prev_list = update_data.setdefault("previous_versions", [])
        if not any(entry.get("version") == old_version for entry in prev_list):
            prev_list.insert(0, {
                "version": old_version,
                "release_notes": old_notes
            })

    update_data["version"] = new_version_num
    update_data["release_notes"] = f"V{new_version_str} — {release_notes}"
    update_data["download_url"] = f"https://github.com/Hackers-lab/SpotImageViewer/releases/download/v{new_version_str}/SpotImageViewer_Setup_v{new_version_str}.exe"
    update_data["installer_url"] = update_data["download_url"]
    update_data["zip_url"] = update_data["download_url"]
    update_data["launch_exe"] = f"SpotImageViewer\\SpotImageViewerV{new_version_str}.exe"
    update_data["sha256"] = ""

    with open(UPDATE_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(update_data, f, indent=2)
    print(f"✓ Updated update.json (version = {new_version_num}, download URLs & launch exe updated)")

    # 3. Rebuild index.html via build_ui.py
    try:
        subprocess.run([sys.executable, BUILD_UI_SCRIPT], check=True, cwd=PROJECT_ROOT)
        print("✓ Rebuilt Web UI (src/ui_web/index.html)")
    except Exception as e:
        print(f"! Warning: Failed to re-assemble index.html: {e}")

    # 4. Optional Git Commit, Tag & Push
    if do_push:
        print("\nCommitting, tagging, and pushing to GitHub...")
        subprocess.run(["git", "add", "src/core/config.py", "update.json", "src/ui_web/index.html"], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "commit", "-m", f"Release v{new_version_str}: {release_notes}"], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "tag", "-a", f"v{new_version_str}", "-m", f"Release v{new_version_str}"], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "push", "origin", "main"], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "push", "origin", f"v{new_version_str}"], check=True, cwd=PROJECT_ROOT)
        print(f"\n✓ Successfully tagged and pushed v{new_version_str} to GitHub!")
    else:
        print("\nAll files synchronized successfully!")
        print("To commit and tag manually, run:")
        print(f"    git add src/core/config.py update.json src/ui_web/index.html")
        print(f"    git commit -m \"Release v{new_version_str}: {release_notes}\"")
        print(f"    git tag -a v{new_version_str} -m \"Release v{new_version_str}\"")
        print(f"    git push origin main; git push origin v{new_version_str}")


if __name__ == "__main__":
    main()
