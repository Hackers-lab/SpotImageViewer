import os
import time
import json
import threading
from datetime import datetime
try:
    from core import config, database
except ImportError:
    import config, database


def path_accessible(p, timeout=1.0):
    """
    Resilient path check with strict timeout.
    Uses a daemon thread so it NEVER hangs on unreachable network shares.
    """
    if not p:
        return False
    # Fast-path for local drive letters (e.g. C:\, D:\, F:\)
    if len(p) >= 2 and p[1] == ':':
        try:
            drive = p[:2] + '\\'
            if not os.path.exists(drive):
                return False
            return os.path.exists(p)
        except Exception:
            return False

    res = [False]
    ev = threading.Event()

    def _worker():
        try:
            res[0] = os.path.exists(p)
        except Exception:
            res[0] = False
        finally:
            ev.set()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    ev.wait(timeout=timeout)
    return res[0]


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

    def check_folder_changes(self, async_check=True):
        """
        Fast disk check to detect if file counts or directory state changed.
        If async_check=True, returns immediately with the latest cached state and
        performs disk traversal in a background daemon thread so the UI never hangs.
        """
        if self._indexing_state["running"]:
            return {"success": True, "indexing_running": True, "has_changes": False}

        if async_check:
            if not self._folder_check_running:
                threading.Thread(target=self._run_folder_check, daemon=True).start()
            return self._cached_folder_check_result
        return self._run_folder_check()

    def _run_folder_check(self):
        if self._folder_check_running:
            return self._cached_folder_check_result

        self._folder_check_running = True
        try:
            additional_folders = database.get_additional_folders()
            folders = [config.IMAGE_FOLDER] + (additional_folders or [])
            unique_folders = []
            for f in folders:
                if f and path_accessible(f, timeout=1.0) and os.path.normpath(f) not in [os.path.normpath(u) for u in unique_folders]:
                    unique_folders.append(f)

            baseline = self._get_baseline_stats()
            total_disk_files = 0
            changed_folders = []
            total_diff = 0
            is_initial_baseline = len(baseline) == 0

            for folder in unique_folders:
                folder_norm = os.path.normpath(folder).lower()
                current_count = 0
                is_local = len(folder) >= 2 and folder[1] == ':'
                try:
                    if is_local:
                        for root, dirs, files in os.walk(folder):
                            current_count += len(files)
                    else:
                        # For remote network UNC paths, check folder mtime
                        # to prevent multi-minute SMB traversal hangs
                        mtime = os.path.getmtime(folder) if os.path.exists(folder) else 0
                        prev_mtime = baseline.get(folder_norm, {}).get("last_mtime", 0)
                        prev_count = baseline.get(folder_norm, {}).get("file_count", 0)
                        if prev_count > 0 and mtime == prev_mtime:
                            current_count = prev_count
                        else:
                            for root, dirs, files in os.walk(folder):
                                current_count += len(files)
                except Exception:
                    continue

                total_disk_files += current_count

                if folder_norm not in baseline:
                    baseline[folder_norm] = {
                        "path": folder,
                        "file_count": current_count,
                        "last_mtime": os.path.getmtime(folder) if os.path.exists(folder) else 0
                    }
                else:
                    prev_count = baseline[folder_norm].get("file_count", 0)
                    folder_diff = current_count - prev_count
                    if folder_diff != 0:
                        changed_folders.append(folder)
                        total_diff += folder_diff

            if is_initial_baseline:
                self._save_baseline_stats(baseline)
                total_diff = 0
                changed_folders = []

            indexed_count = database.get_total_image_count()
            has_changes = len(changed_folders) > 0 or (total_diff != 0)

            res = {
                "success": True,
                "has_changes": has_changes,
                "current_files": total_disk_files,
                "disk_files": total_disk_files,
                "indexed_count": indexed_count,
                "indexed_images": indexed_count,
                "diff": total_diff,
                "changed_folders": changed_folders,
                "changed_folder_names": [os.path.basename(f) or f for f in changed_folders],
                "mode": self.get_auto_index_mode()
            }
            self._cached_folder_check_result = res
            return res
        except Exception as e:
            return {"success": False, "error": str(e), "has_changes": False}
        finally:
            self._folder_check_running = False

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

                # Filter target folders if specified
                if target_folders:
                    targets_norm = [os.path.normpath(t).lower() for t in target_folders if t]
                    scan_folders = [f for f in unique_folders if os.path.normpath(f).lower() in targets_norm]
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
                BATCH_SIZE = 5000

                for folder in scan_folders:
                    self._indexing_state["current_folder"] = os.path.basename(folder) or folder
                    for root_dir, dirs, files in os.walk(folder):
                        if not files:
                            continue

                        if root_dir not in dir_cache:
                            cursor.execute("INSERT OR IGNORE INTO directories (dir_path) VALUES (?)", (root_dir,))
                            cursor.execute("SELECT id FROM directories WHERE dir_path = ?", (root_dir,))
                            row = cursor.fetchone()
                            if row:
                                dir_cache[root_dir] = row[0]
                            else:
                                dir_cache[root_dir] = next_dir_id
                                next_dir_id += 1
                        dir_id = dir_cache[root_dir]

                        for filename in files:
                            scanned_files_count += 1
                            try:
                                if len(filename) < 25:
                                    continue
                                if not filename[:8].isdigit():
                                    continue

                                date_orig = filename[:8]
                                try:
                                    dt = datetime.strptime(date_orig, "%d%m%Y")
                                    date_iso = dt.strftime("%Y-%m-%d")
                                except ValueError:
                                    continue

                                mru = filename[8:16]
                                cid = filename[16:25]

                                batch_data.append((cid, date_orig, date_iso, mru, filename, dir_id))

                                if len(batch_data) >= BATCH_SIZE:
                                    cursor.executemany(
                                        "INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)",
                                        batch_data
                                    )
                                    conn.commit()
                                    total_inserted += len(batch_data)
                                    batch_data = []
                                    elapsed = max(1, int(time.time() - start))
                                    speed = int(scanned_files_count / elapsed)
                                    self._indexing_state["scanned"] = total_inserted
                                    self._indexing_state["total"] = total_inserted
                                    self._indexing_state["files_seen"] = scanned_files_count
                                    self._indexing_state["elapsed"] = elapsed
                                    self._indexing_state["speed"] = speed
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
                for folder in scan_folders:
                    folder_norm = os.path.normpath(folder).lower()
                    try:
                        f_count = sum(len(f_files) for _, _, f_files in os.walk(folder))
                        baseline[folder_norm] = {
                            "path": folder,
                            "file_count": f_count,
                            "last_mtime": os.path.getmtime(folder) if os.path.exists(folder) else 0
                        }
                    except Exception:
                        pass
                self._save_baseline_stats(baseline)

                elapsed = max(1, int(time.time() - start))
                speed = int(scanned_files_count / elapsed) if scanned_files_count else 0
                self._indexing_state["scanned"] = final_total
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
