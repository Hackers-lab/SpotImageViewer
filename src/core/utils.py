import os
import sys
import tempfile
import subprocess
try:
    from core import database
except ImportError:
    import database
import json
import urllib.request
import threading
import ssl

def load_additional_folders():
    """Loads the list of additional network folders from the database."""
    return database.get_additional_folders()

def save_additional_folders(folders):
    """Saves the list of additional network folders to the database."""
    database.save_additional_folders(folders)

def load_note_options():
    """Loads note options from the database."""
    return database.get_note_options()

def add_note_option(option):
    """Adds a new note option to the database."""
    database.add_note_option(option)

def load_all_notes():
    """Loads all consumer notes from the database."""
    return database.get_all_notes()

def save_note(cid, note, remarks):
    """Saves a single consumer note to the database."""
    database.save_note(cid, note, remarks)

def delete_note(cid):
    """Deletes a consumer note from the database."""
    database.delete_note(cid)

def get_meter_number(consumer_id):
    """Retrieves a meter number for a given consumer ID from the database."""
    return database.get_meter_number(consumer_id)
    
def get_consumer_by_meter(meter_no):
    """Retrieves a consumer id for a given meter number from the database."""
    return database.get_consumer_by_meter(meter_no)


def get_consumer_profile(consumer_id):
    """Retrieves full profile details for a consumer from the database."""
    return database.get_consumer_profile(consumer_id)


def search_consumers_by_name(name_query, limit=200):
    """Search consumers by partial name, case-insensitive."""
    return database.search_consumers_by_name(name_query, limit=limit)


def search_consumers_by_mobile(mobile_number, limit=200):
    """Search consumers by exact 10-digit mobile number."""
    return database.search_consumers_by_mobile(mobile_number, limit=limit)


def get_all_consumer_profiles():
    """Return all consumer records for batch tools like fuzzy lookup."""
    return database.get_all_consumer_profiles()
    
def update_meter_mapping(mapping_dict):
    """Updates the meter mapping in the database."""
    database.update_meter_mapping(mapping_dict)

def save_search_history(key, val):
    try:
        d = database.get_info_value(
            "search_history",
            {"consumer_ids": [], "meter_numbers": [], "consumer_names": [], "mobile_numbers": []}
        )
        if key not in d:
            d[key] = []
        if val in d[key]: d[key].remove(val)
        d[key].append(val)
        if len(d[key]) > 10: d[key] = d[key][-10:]
        database.set_info_value("search_history", d)
    except:
        pass

def load_search_history(key):
    try:
        d = database.get_info_value(
            "search_history",
            {"consumer_ids": [], "meter_numbers": [], "consumer_names": [], "mobile_numbers": []}
        )
        return d.get(key, [])
    except:
        return []

def console_log(message):
    """Prints a message to the console with a timestamp."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_for_updates_background(current_version, update_url, finished_callback):
    def worker():
        try:
            # Create an unverified SSL context for compatibility across systems
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(update_url, context=context, timeout=5) as response:
                data = json.loads(response.read().decode())
            
            latest_version = data.get("version")
            
            # Convert version strings to comparable tuples of integers
            current_v_tuple = tuple(map(int, str(current_version).split('.')))
            latest_v_tuple = tuple(map(int, str(latest_version).split('.')))

            if latest_v_tuple > current_v_tuple:
                finished_callback("update_found", data)
            else:
                finished_callback("no_update", data)
        except Exception as e:
            console_log(f"Update check failed: {e}")
            finished_callback("error", {"error": str(e)})

    threading.Thread(target=worker, daemon=True).start()


def download_file_with_progress(url, dest_path, progress_callback=None):
    context = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"User-Agent": "SpotImageViewer-Updater"})
    with urllib.request.urlopen(req, context=context) as response:
        total_size = response.getheader('Content-Length')
        total_size = int(total_size) if total_size else None
        bytes_downloaded = 0
        chunk_size = 64 * 1024

        with open(dest_path, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                bytes_downloaded += len(chunk)
                if progress_callback and total_size:
                    progress_callback(bytes_downloaded, total_size)


def perform_self_update_async(update_payload, app_pid, finished_callback, progress_callback=None):
    """Download installer package and launch silent update."""
    def worker():
        try:
            download_url = (
                update_payload.get("installer_url")
                or update_payload.get("download_url")
                or ""
            )
            if not download_url:
                raise ValueError("No download URL in update metadata.")

            filename = os.path.basename(download_url.split("?")[0]) or "SpotImageViewer_Update.exe"
            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, filename)

            console_log(f"Downloading update from {download_url} to {installer_path}...")
            download_file_with_progress(download_url, installer_path, progress_callback)
            console_log("Download complete. Launching installer...")

            # Run updater script
            install_args = update_payload.get("install_args", "/VERYSILENT /NORESTART")
            launch_windows_installer(installer_path, app_pid, install_args)
            finished_callback("started", {"installer_path": installer_path})
        except Exception as e:
            console_log(f"Self-update failed: {e}")
            finished_callback("error", {"error": str(e)})

    threading.Thread(target=worker, daemon=True).start()


def launch_windows_installer(installer_path, app_pid, install_args=""):
    """
    Executes an installer after current application terminates.
    Creates a helper .cmd in temp directory to wait for PID, run installer, and exit.
    """
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, "spotimageviewer_run_update.cmd")
    
    if installer_path.lower().endswith(".zip"):
        # If installer is a zip package, extract it
        target_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        cmd_run = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path \'{installer_path}\' -DestinationPath \'{target_dir}\' -Force"'
    else:
        # Standard executable setup (Inno Setup / NSIS)
        clean_args = str(install_args).strip() if install_args else ""
        if clean_args:
            cmd_run = f'"{installer_path}" {clean_args}'
        else:
            cmd_run = f'start "" "{installer_path}"'

    batch_content = (
        "@echo off\n"
        f"timeout /t 1 /nobreak >nul\n"
        f":waitloop\n"
        f"tasklist /FI \"PID eq {app_pid}\" | find \"{app_pid}\" >nul\n"
        f"if not errorlevel 1 (\n"
        f"  timeout /t 1 /nobreak >nul\n"
        f"  goto waitloop\n"
        f")\n"
        f"{cmd_run}\n"
        f"del \"%~f0\"\n"
    )

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(batch_content)

    creation_flags = 0
    startupinfo = None
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    subprocess.Popen(
        ["cmd", "/c", script_path],
        creationflags=creation_flags,
        startupinfo=startupinfo,
    )
