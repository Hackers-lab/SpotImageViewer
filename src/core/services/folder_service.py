import os
import time
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    from core import config, database
except ImportError:
    import config, database

_path_pool = ThreadPoolExecutor(max_workers=4)

def path_accessible(p, timeout=1.0):
    """
    Resilient path check with strict timeout.
    Uses a daemon thread so it NEVER hangs on unreachable network shares.
    """
    if not p:
        return False
    # Fast-path ONLY for local C: drive
    if len(p) >= 2 and p[0].upper() == 'C' and p[1] == ':':
        try:
            return os.path.exists(p)
        except Exception:
            return False

    try:
        future = _path_pool.submit(os.path.exists, p)
        return future.result(timeout=timeout)
    except Exception:
        return False


class FolderIndexerService:
    """
    Manages registered local and network image directories and orchestrates
    bulk SQLite indexing of spot billing meter photos.
    """

    def __init__(self):
        self._indexing_state = {
            "running": False,
            "scanned": 0,
            "total": 0,
            "files_seen": 0,
            "new_added": 0,
            "elapsed": 0,
            "speed": 0,
            "eta_seconds": None,
            "current_folder": "",
            "error": None
        }
        self._folder_check_running = False

        # Pre-seed cache from persisted baseline so initial response is instant
        baseline = database.get_info_value("folder_baseline_stats", {}) or {}
        total_baseline = sum(item.get("file_count", 0) for item in baseline.values()) if baseline else 0
        indexed_total = database.get_total_image_count()
        self._cached_folder_check_result = {
            "success": True,
            "has_changes": False,
            "current_files": total_baseline,
            "disk_files": total_baseline,
            "indexed_count": indexed_total,
            "indexed_images": indexed_total,
            "diff": 0,
            "changed_folders": [],
            "changed_folder_names": [],
            "mode": self.get_auto_index_mode()
        }

    def get_indexing_status(self):
        return {"success": True, **self._indexing_state}

    @staticmethod
    def get_folder_status():
        """Returns accessibility status of primary and all registered network folders."""
        try:
            folders = []
            primary_path = config.IMAGE_FOLDER
            folders.append({
                "path": primary_path,
                "accessible": path_accessible(primary_path),
                "is_primary": True
            })

            for p in database.get_additional_folders():
                folders.append({
                    "path": p,
                    "accessible": path_accessible(p),
                    "is_primary": False
                })

            return {"success": True, "folders": folders}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def add_network_folder(path):
        """Validates and registers an additional network or local image folder."""
        try:
            if not path:
                return {"success": False, "cancelled": True}
            if not path_accessible(path):
                return {"success": False, "error": "Folder path does not exist or is not accessible"}

            folders = database.get_additional_folders()
            if path not in folders:
                folders.append(path)
                database.save_additional_folders(folders)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def remove_network_folder(path):
        """Removes a registered additional folder from the database."""
        try:
            folders = database.get_additional_folders()
            if path in folders:
                folders.remove(path)
                database.save_additional_folders(folders)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_auto_index_mode():
        return database.get_info_value("auto_index_mode", "prompt")

    @staticmethod
    def set_auto_index_mode(mode):
        valid = mode if mode in ("prompt", "background", "manual") else "prompt"
        database.set_info_value("auto_index_mode", valid)
        return valid

    def _get_baseline_stats(self):
        return database.get_info_value("folder_baseline_stats", {}) or {}

    def _save_baseline_stats(self, stats):
        database.set_info_value("folder_baseline_stats", stats)

    def check_folder_changes(self):
        """
        Fast disk check to detect if unindexed spot billing photos exist on disk.
        Supports both top-level and nested subfolders across local and network shares in < 0.8s.
        """
        if self._indexing_state["running"]:
            return {"success": True, "indexing_running": True, "has_changes": False}

        try:
            additional_folders = database.get_additional_folders()
            folders = [config.IMAGE_FOLDER] + (additional_folders or [])
            unique_folders = []
            for f in folders:
                if f and path_accessible(f, timeout=0.8) and os.path.normpath(f) not in [os.path.normpath(u) for u in unique_folders]:
                    unique_folders.append(f)

            conn = database.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id, dir_path FROM directories")
            all_dirs = cursor.fetchall()
            known_dirs = {os.path.normpath(row[1]).lower(): row[0] for row in all_dirs}

            cursor.execute("SELECT dir_id, COUNT(*) FROM images GROUP BY dir_id")
            db_counts = dict(cursor.fetchall())

            baseline = self._get_baseline_stats()
            dir_mtimes = baseline.get("dir_mtimes", {})
            is_first_mtime_init = len(dir_mtimes) == 0

            changed_folders = []
            total_diff = 0
            now = time.time()

            # 1. Check for brand new folders or subfolders created on disk that are not yet in the DB
            for root_folder in unique_folders:
                try:
                    norm_root = os.path.normpath(root_folder).lower()
                    if norm_root not in known_dirs:
                        new_photos = sum(1 for e in os.scandir(root_folder) if len(e.name) >= 25 and e.name[:8].isdigit() and not e.name.startswith('.'))
                        if new_photos > 0:
                            changed_folders.append(root_folder)
                            total_diff += new_photos

                    for entry in os.scandir(root_folder):
                        if entry.is_dir():
                            name = entry.name
                            if name.startswith('.') or name in ('$RECYCLE.BIN', 'System Volume Information', 'Recovery', '.git', 'node_modules', 'temp', 'Temp'):
                                continue
                            norm_entry = os.path.normpath(entry.path).lower()
                            if norm_entry not in known_dirs:
                                new_photos = sum(1 for e in os.scandir(entry.path) if len(e.name) >= 25 and e.name[:8].isdigit() and not e.name.startswith('.'))
                                if new_photos > 0:
                                    changed_folders.append(entry.path)
                                    total_diff += new_photos
                except Exception:
                    pass

            # 2. Check all known directories in DB (both local and network)
            for dir_id, dir_path in all_dirs:
                dir_norm = os.path.normpath(dir_path).lower()
                try:
                    if not os.path.exists(dir_path):
                        continue
                    mtime = os.path.getmtime(dir_path)
                    prev_mtime = dir_mtimes.get(dir_norm)
                    needs_check = False
                    if prev_mtime is not None:
                        if mtime != prev_mtime:
                            needs_check = True
                    else:
                        # Scan directory if not yet recorded in baseline
                        needs_check = True

                    if needs_check:
                        disk_cnt = sum(1 for e in os.scandir(dir_path) if len(e.name) >= 25 and e.name[:8].isdigit())
                        db_cnt = db_counts.get(dir_id, 0)
                        diff = disk_cnt - db_cnt
                        if diff != 0:
                            changed_folders.append(dir_path)
                            total_diff += diff
                            # Do NOT update dir_mtimes while diff != 0 so notification persists until indexed
                        else:
                            dir_mtimes[dir_norm] = mtime
                    else:
                        dir_mtimes[dir_norm] = mtime
                except Exception:
                    pass

            baseline["dir_mtimes"] = dir_mtimes
            self._save_baseline_stats(baseline)

            indexed_count = database.get_total_image_count()
            has_changes = len(changed_folders) > 0 or (total_diff != 0)

            # Clean folder names for display (e.g. "ImageBackup\042022")
            changed_display_names = []
            for cf in changed_folders:
                parts = os.path.normpath(cf).split(os.sep)
                if len(parts) >= 2:
                    changed_display_names.append(f"{parts[-2]}\\{parts[-1]}")
                else:
                    changed_display_names.append(parts[-1])

            res = {
                "success": True,
                "has_changes": has_changes,
                "current_files": indexed_count + total_diff,
                "disk_files": indexed_count + total_diff,
                "indexed_count": indexed_count,
                "indexed_images": indexed_count,
                "diff": total_diff,
                "changed_folders": changed_folders,
                "changed_folder_names": changed_display_names,
                "mode": self.get_auto_index_mode()
            }
            self._cached_folder_check_result = res
            return res
        except Exception as e:
            return {"success": False, "error": str(e), "has_changes": False}

    def start_indexing(self, target_folders=None, full_reindex=False):
        """
        Bulk or incremental scan of registered image folders.
        - target_folders: optional list of specific folders to scan (e.g. only changed folder)
        - full_reindex: if True, wipes database and re-indexes all folders from scratch.
                        if False (default for auto-sync), uses INSERT OR IGNORE and updates only new photos.
        """
        if self._indexing_state["running"]:
            return {"success": False, "error": "Indexing already running"}

        self._indexing_state["running"] = True
        self._indexing_state["scanned"] = 0
        self._indexing_state["total"] = 0
        self._indexing_state["files_seen"] = 0
        self._indexing_state["new_added"] = 0
        self._indexing_state["elapsed"] = 0
        self._indexing_state["speed"] = 0
        self._indexing_state["eta_seconds"] = None
        self._indexing_state["current_folder"] = ""
        self._indexing_state["error"] = None
        self._indexing_state["full_reindex"] = bool(full_reindex)

        def _index():
            start = time.time()
            total_inserted = 0
            scanned_files_count = 0
            try:
                database.init_db()

                additional_folders = database.get_additional_folders()
                all_registered = [config.IMAGE_FOLDER] + (additional_folders or [])
                unique_folders = []
                for f in all_registered:
                    if f and path_accessible(f) and os.path.normpath(f) not in [os.path.normpath(u) for u in unique_folders]:
                        unique_folders.append(f)

                # Filter target folders if specified (accepts both root folders and nested subfolders)
                if target_folders:
                    scan_folders = []
                    for t in target_folders:
                        if t and path_accessible(t):
                            t_norm = os.path.normpath(t).lower()
                            if any(t_norm == os.path.normpath(u).lower() or t_norm.startswith(os.path.normpath(u).lower() + os.sep) for u in unique_folders):
                                scan_folders.append(t)
                    if not scan_folders:
                        scan_folders = unique_folders
                else:
                    scan_folders = unique_folders

                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=OFF;")

                dir_cache = {}
                next_dir_id = 1

                if full_reindex:
                    cursor.execute("DELETE FROM images")
                    cursor.execute("DELETE FROM directories")
                    conn.commit()
                else:
                    # Incremental sync: retain existing images and load directory cache
                    cursor.execute("SELECT dir_path, id FROM directories")
                    dir_cache = {row[0]: row[1] for row in cursor.fetchall()}
                    cursor.execute("SELECT MAX(id) FROM directories")
                    max_id_row = cursor.fetchone()
                    if max_id_row and max_id_row[0]:
                        next_dir_id = max_id_row[0] + 1

                cursor.execute("SELECT COUNT(*) FROM images")
                count_before = cursor.fetchone()[0]

                batch_data = []
                BATCH_SIZE = 1000
                last_ui_update = 0.0

                from collections import deque

                for folder in scan_folders:
                    folder_base = os.path.basename(folder) or folder
                    self._indexing_state["current_folder"] = folder_base

                    # Streaming queue-based directory traversal (avoids buffering 100k+ file arrays over SMB)
                    dir_queue = deque([folder])

                    while dir_queue:
                        current_dir = dir_queue.popleft()
                        try:
                            rel = os.path.relpath(current_dir, folder)
                            cur_display = folder_base if rel == '.' else f"{folder_base}\\{os.path.basename(current_dir)}"
                            self._indexing_state["current_folder"] = cur_display

                            # Register directory in DB cache
                            if current_dir not in dir_cache:
                                cursor.execute("INSERT OR IGNORE INTO directories (dir_path) VALUES (?)", (current_dir,))
                                cursor.execute("SELECT id FROM directories WHERE dir_path = ?", (current_dir,))
                                row = cursor.fetchone()
                                if row:
                                    dir_cache[current_dir] = row[0]
                                else:
                                    dir_cache[current_dir] = next_dir_id
                                    next_dir_id += 1
                            dir_id = dir_cache[current_dir]

                            # Pre-load known filenames for this directory if incremental
                            existing_in_dir = None
                            if not full_reindex:
                                cursor.execute("SELECT filename FROM images WHERE dir_id = ?", (dir_id,))
                                existing_in_dir = set(row[0] for row in cursor.fetchall())

                            with os.scandir(current_dir) as it:
                                for entry in it:
                                    try:
                                        name = entry.name
                                        # Instantly skip hidden and trash files (e.g. .trashed-*, .git, etc.)
                                        if name.startswith('.'):
                                            continue

                                        if entry.is_dir(follow_symlinks=False):
                                            if name not in ('$RECYCLE.BIN', 'System Volume Information', 'Recovery', '.git', 'node_modules', 'temp', 'Temp'):
                                                dir_queue.append(entry.path)
                                            continue

                                        scanned_files_count += 1

                                        # Fast skip if already indexed
                                        if existing_in_dir is not None and name in existing_in_dir:
                                            now = time.time()
                                            if now - last_ui_update >= 0.3:
                                                last_ui_update = now
                                                elapsed = max(1, int(now - start))
                                                self._indexing_state["files_seen"] = scanned_files_count
                                                self._indexing_state["elapsed"] = elapsed
                                                self._indexing_state["speed"] = int(scanned_files_count / elapsed)
                                                self._indexing_state["current_folder"] = cur_display
                                            continue

                                        # Validate spot bill format
                                        if len(name) < 25 or not name[:8].isdigit():
                                            continue

                                        date_orig = name[:8]
                                        try:
                                            dt = datetime.strptime(date_orig, "%d%m%Y")
                                            date_iso = dt.strftime("%Y-%m-%d")
                                        except ValueError:
                                            continue

                                        mru = name[8:16]
                                        cid = name[16:25]

                                        batch_data.append((cid, date_orig, date_iso, mru, name, dir_id))

                                        if len(batch_data) >= BATCH_SIZE:
                                            cursor.executemany(
                                                "INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)",
                                                batch_data
                                            )
                                            conn.commit()
                                            total_inserted += len(batch_data)
                                            batch_data = []

                                            now = time.time()
                                            last_ui_update = now
                                            elapsed = max(1, int(now - start))
                                            speed = int(scanned_files_count / elapsed)
                                            self._indexing_state["scanned"] = total_inserted
                                            self._indexing_state["total"] = total_inserted
                                            self._indexing_state["new_added"] = total_inserted
                                            self._indexing_state["files_seen"] = scanned_files_count
                                            self._indexing_state["elapsed"] = elapsed
                                            self._indexing_state["speed"] = speed
                                            self._indexing_state["current_folder"] = cur_display
                                        else:
                                            now = time.time()
                                            if now - last_ui_update >= 0.3:
                                                last_ui_update = now
                                                elapsed = max(1, int(now - start))
                                                self._indexing_state["files_seen"] = scanned_files_count
                                                self._indexing_state["elapsed"] = elapsed
                                                self._indexing_state["speed"] = int(scanned_files_count / elapsed)
                                                self._indexing_state["new_added"] = total_inserted
                                                self._indexing_state["current_folder"] = cur_display
                                    except Exception:
                                        continue
                        except Exception:
                            continue

                if batch_data:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)",
                        batch_data
                    )
                    conn.commit()
                    total_inserted += len(batch_data)

                cursor.execute("ANALYZE;")
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                cursor.execute("PRAGMA synchronous=NORMAL;")

                cursor.execute("SELECT COUNT(*) FROM images")
                final_total = cursor.fetchone()[0]
                new_added = max(0, final_total - count_before)
                database.set_info_value("cached_total_images", final_total)

                # Update baseline stats for the scanned folders so change detector is in sync
                baseline = self._get_baseline_stats()
                dir_mtimes = baseline.get("dir_mtimes", {})
                for folder in scan_folders:
                    folder_norm = os.path.normpath(folder).lower()
                    try:
                        dir_mtimes[folder_norm] = os.path.getmtime(folder) if os.path.exists(folder) else 0
                    except Exception:
                        pass
                baseline["dir_mtimes"] = dir_mtimes
                self._save_baseline_stats(baseline)

                elapsed = max(1, int(time.time() - start))
                speed = int(scanned_files_count / elapsed) if scanned_files_count else 0
                self._indexing_state["scanned"] = final_total if full_reindex else new_added
                self._indexing_state["total"] = final_total
                self._indexing_state["new_added"] = new_added
                self._indexing_state["files_seen"] = scanned_files_count
                self._indexing_state["elapsed"] = elapsed
                self._indexing_state["speed"] = speed
            except Exception as e:
                print(f"[Error in Indexing Worker]: {e}", flush=True)
                self._indexing_state["error"] = str(e)
            finally:
                self._indexing_state["running"] = False

        threading.Thread(target=_index, daemon=True).start()
        return {"success": True}
