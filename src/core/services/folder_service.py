import os
import time
import threading
from datetime import datetime
try:
    from core import config, database
except ImportError:
    import config, database


def path_accessible(p, timeout=1.5):
    """
    Resilient path check with strict timeout.
    Uses a daemon thread so it NEVER hangs on executor.shutdown(wait=True)
    when Windows SMB/NetBIOS name resolution is stalled on unreachable network shares.
    """
    if not p:
        return False
    # Fast-path for local drive letters (e.g. C:\, D:\)
    if len(p) >= 2 and p[1] == ':' and os.path.exists(p[:3]):
        try:
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
            "elapsed": 0,
            "speed": 0,
            "eta_seconds": None,
            "current_folder": "",
            "error": None
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

    def start_indexing(self):
        """Launches background bulk scan of all registered image folders."""
        if self._indexing_state["running"]:
            return {"success": False, "error": "Indexing already running"}

        self._indexing_state["running"] = True
        self._indexing_state["scanned"] = 0
        self._indexing_state["total"] = 0
        self._indexing_state["files_seen"] = 0
        self._indexing_state["elapsed"] = 0
        self._indexing_state["speed"] = 0
        self._indexing_state["eta_seconds"] = None
        self._indexing_state["current_folder"] = ""
        self._indexing_state["error"] = None

        def _index():
            start = time.time()
            total_inserted = 0
            scanned_files_count = 0
            try:
                database.init_db()

                additional_folders = database.get_additional_folders()
                folders = [config.IMAGE_FOLDER] + (additional_folders or [])
                unique_folders = []
                for f in folders:
                    if f and os.path.exists(f) and os.path.normpath(f) not in [os.path.normpath(u) for u in unique_folders]:
                        unique_folders.append(f)

                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=OFF;")

                cursor.execute("DELETE FROM images")
                cursor.execute("DELETE FROM directories")
                conn.commit()

                dir_cache = {}
                next_dir_id = 1

                cursor.execute("SELECT MAX(id) FROM directories")
                max_id_row = cursor.fetchone()
                if max_id_row and max_id_row[0]:
                    next_dir_id = max_id_row[0] + 1

                batch_data = []
                BATCH_SIZE = 5000

                for folder in unique_folders:
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
                                    speed = int(total_inserted / elapsed)
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
                database.set_info_value("cached_total_images", total_inserted)

                elapsed = max(1, int(time.time() - start))
                speed = int(total_inserted / elapsed) if total_inserted else 0
                self._indexing_state["scanned"] = total_inserted
                self._indexing_state["total"] = total_inserted
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
