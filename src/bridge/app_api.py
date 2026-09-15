import os
import sys
import json
import re
import csv
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor

try:
    from core import config, database, utils, tariff_manager, live_osd_service
    from core.services.billing_service import BillingService
    from core.services.image_service import ImageService
    from core.services.fuzzy_service import FuzzyService
    from core.services.consumer_data_service import ConsumerDataService
    from core.services.audit_service import AuditService
    from core.services.folder_service import FolderIndexerService, path_accessible
    from core.services.update_service import UpdateService
    from core.services.osd_service import OSDService
except ImportError:
    import config, database, utils, tariff_manager, live_osd_service
    from services.billing_service import BillingService
    from services.image_service import ImageService
    from services.fuzzy_service import FuzzyService
    from services.consumer_data_service import ConsumerDataService
    from services.audit_service import AuditService
    from services.folder_service import FolderIndexerService, path_accessible
    from services.update_service import UpdateService
    from services.osd_service import OSDService

# Shared thread pool for offloading heavy I/O from the PyWebView bridge thread.
_io_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="siv-io")


def _wait_db(timeout=5.0):
    """Wait for init_db to finish (prevents deadlock with schema migration locks)."""
    database.init_db_ready.wait(timeout=timeout)


class AppAPI:
    """
    Python-to-JavaScript RPC bridge exposed to the PyWebView window.
    Acts as a clean Facade dispatching requests to core domain services.
    All methods return JSON-serializable dictionaries or primitives.
    """

    def __init__(self, window=None):
        self._window = window
        self._billing_service = BillingService()
        self._image_service = ImageService()
        self._fuzzy_service = FuzzyService()
        self._consumer_service = ConsumerDataService()
        self._audit_service = AuditService()
        self._folder_service = FolderIndexerService()
        self._update_service = UpdateService()
        self._osd_service = OSDService()

    def set_window(self, window):
        self._window = window

    # =========================================================================
    # System & Settings
    # =========================================================================
    def get_app_info(self):
        _wait_db()
        needs_image_recount = database.get_info_value("cached_total_images", None) is None
        needs_consumer_recount = database.get_info_value("cached_consumer_count", None) is None

        if needs_image_recount:
            def _bg_recount_images():
                try:
                    import time
                    time.sleep(1.0)
                    c = database.get_total_image_count(force_recount=True)
                    if self._window:
                        self._window.evaluate_js(f"if (typeof updateAppCounts === 'function') {{ updateAppCounts({c}, null); }}")
                except Exception:
                    pass
            threading.Thread(target=_bg_recount_images, daemon=True).start()

        if needs_consumer_recount:
            def _bg_recount_consumers():
                try:
                    import time
                    time.sleep(1.5)
                    c = database.get_consumer_count(force_recount=True)
                    if self._window:
                        self._window.evaluate_js(f"if (typeof updateAppCounts === 'function') {{ updateAppCounts(null, {c}); }}")
                except Exception:
                    pass
            threading.Thread(target=_bg_recount_consumers, daemon=True).start()

        total_images = database.get_total_image_count()
        consumer_count = database.get_consumer_count()

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

        return {
            "version": config.CURRENT_VERSION,
            "total_images": total_images,
            "folders": folders,
            "has_meter_data": consumer_count > 0,
            "consumer_count": consumer_count,
            "consumer_updated_at": database.get_info_value("consumer_data_updated_at", ""),
            "theme": database.get_info_value("app_theme", "dark")
        }

    def get_theme(self):
        theme = database.get_info_value("app_theme", "dark")
        return {"success": True, "theme": theme}

    def set_theme(self, theme):
        theme_val = "light" if str(theme).lower() == "light" else "dark"
        database.set_info_value("app_theme", theme_val)
        return {"success": True, "theme": theme_val}

    def get_system_clipboard(self):
        """Retrieve plain text from system clipboard using Win32 API."""
        try:
            import ctypes
            from ctypes import wintypes
            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            kernel32.GlobalLock.restype = ctypes.c_wchar_p
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

            if not user32.OpenClipboard(None):
                return {"success": True, "text": ""}
            try:
                h = user32.GetClipboardData(CF_UNICODETEXT)
                if not h:
                    return {"success": True, "text": ""}
                text = kernel32.GlobalLock(h) or ""
                kernel32.GlobalUnlock(h)
                return {"success": True, "text": str(text)}
            finally:
                user32.CloseClipboard()
        except Exception as e:
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                try:
                    text = root.clipboard_get()
                except Exception:
                    text = ""
                finally:
                    root.destroy()
                return {"success": True, "text": text}
            except Exception:
                return {"success": False, "error": str(e), "text": ""}

    # =========================================================================
    # Search & Consumer Details
    # =========================================================================
    def search_consumer(self, query, filter_type="auto"):
        query = str(query or "").strip()
        if not query:
            return {"success": False, "error": "Search query cannot be empty."}

        def _do_search():
            detected_type = filter_type
            if filter_type == "auto":
                if query.isdigit() and len(query) == 9:
                    detected_type = "cid"
                elif query.isdigit() and len(query) == 10:
                    detected_type = "mobile"
                elif any(c.isalpha() for c in query) and not any(c.isdigit() for c in query) and len(query) >= 2:
                    detected_type = "name"
                else:
                    detected_type = "meter"

            results = []
            if detected_type == "cid":
                profile = database.get_consumer_profile(query)
                if profile:
                    results.append(profile)
                else:
                    results.append({
                        "consumer_id": query,
                        "meter_no": "",
                        "name": "",
                        "address": "",
                        "mobile_number": "",
                        "contractual_load": "",
                        "class": ""
                    })
            elif detected_type == "meter":
                cid = database.get_consumer_by_meter(query)
                if cid:
                    prof = database.get_consumer_profile(cid)
                    if prof:
                        results.append(prof)
                else:
                    try:
                        conn = database.get_db_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class 
                            FROM meter_mapping 
                            WHERE meter_no LIKE ? LIMIT 50
                        """, (f"{query}%",))
                        prefix_rows = cur.fetchall()
                        if prefix_rows:
                            for r in prefix_rows:
                                results.append({
                                    "consumer_id": r[0], "meter_no": r[1], "name": r[2], "address": r[3],
                                    "mobile_number": r[4], "contractual_load": r[5], "class": r[6]
                                })
                        else:
                            cur.execute("""
                                SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class 
                                FROM meter_mapping 
                                WHERE meter_no LIKE ? LIMIT 50
                            """, (f"%{query}%",))
                            for r in cur.fetchall():
                                results.append({
                                    "consumer_id": r[0], "meter_no": r[1], "name": r[2], "address": r[3],
                                    "mobile_number": r[4], "contractual_load": r[5], "class": r[6]
                                })
                    except Exception:
                        pass
            elif detected_type == "name":
                results = database.search_consumers_by_name(query, limit=50)
            elif detected_type == "mobile":
                results = database.search_consumers_by_mobile(query, limit=50)

            return {
                "success": True,
                "detected_type": detected_type,
                "count": len(results),
                "results": results
            }
        return _io_pool.submit(_do_search).result()

    def _fetch_consumer_images(self, consumer_id):
        cid = str(consumer_id).strip()
        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT i.date_original, i.mru, d.dir_path, i.filename 
                    FROM images i 
                    JOIN directories d ON i.dir_id = d.id 
                    WHERE i.consumer_id = ? 
                    ORDER BY i.date_iso DESC, CASE WHEN d.dir_path LIKE '_:%' THEN 0 ELSE 1 END, i.rowid ASC
                """, (cid,))
                rows = cur.fetchall()
            except Exception:
                cur.execute("PRAGMA table_info(images)")
                cols = [c[1] for c in cur.fetchall()]
                if 'full_path' in cols:
                    cur.execute("SELECT date_original, mru, full_path FROM images WHERE consumer_id = ? ORDER BY date_original DESC", (cid,))
                    raw_rows = cur.fetchall()
                    rows = [(r[0], r[1], os.path.dirname(r[2]), os.path.basename(r[2])) for r in raw_rows]
                elif 'filename' in cols and 'dir_id' not in cols:
                    cur.execute("SELECT date_original, mru, '', filename FROM images WHERE consumer_id = ?", (cid,))
                    rows = cur.fetchall()
                else:
                    rows = []

            if not rows:
                return {"success": False, "error": f"No images found for Consumer ID {cid}."}

            grouped = {}
            flat_images = []
            for date_orig, mru, dir_path, filename in rows:
                full_path = os.path.join(dir_path, filename)
                pretty_date = f"{date_orig[:2]}-{date_orig[2:4]}-{date_orig[4:]}" if len(date_orig) == 8 else date_orig

                item = {
                    "date_original": date_orig,
                    "date_formatted": pretty_date,
                    "mru": mru,
                    "filename": filename,
                    "full_path": full_path,
                    "exists": True
                }
                if pretty_date not in grouped:
                    grouped[pretty_date] = []
                grouped[pretty_date].append(item)
                flat_images.append(item)

            profile = database.get_consumer_profile(cid)

            return {
                "success": True,
                "consumer_id": cid,
                "profile": profile,
                "mru": rows[0][1] if rows else "",
                "total_images": len(rows),
                "dates": list(grouped.keys()),
                "grouped": grouped,
                "images": flat_images
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_consumer_images(self, consumer_id):
        return _io_pool.submit(lambda: self._fetch_consumer_images(consumer_id)).result()

    # =========================================================================
    # Image Operations
    # =========================================================================
    def get_image_data(self, file_path, max_dim=1400):
        return _io_pool.submit(lambda: self._image_service.get_image_data(file_path, max_dim)).result()

    def save_image_to(self, file_path, dest_path=""):
        if not dest_path:
            dest_path = self.pick_save_file(
                title="Save Image As",
                default_filename=os.path.basename(file_path),
                file_types=[("JPEG Images (*.jpg;*.jpeg)", "*.jpg;*.jpeg"), ("All Files (*.*)", "*.*")]
            )
        if not dest_path:
            return {"success": False, "cancelled": True}
        return self._image_service.save_image_to(file_path, dest_path)

    def save_all_images(self, consumer_id, dest_dir=""):
        if not dest_dir:
            dest_dir = self.pick_folder(title=f"Select Destination Folder for Consumer {consumer_id} Photos")
        if not dest_dir:
            return {"success": False, "cancelled": True}

        def _do_copy():
            images_data = self._fetch_consumer_images(consumer_id)
            if not images_data.get("success"):
                return images_data
            return self._image_service.save_all_images(consumer_id, dest_dir, images_data.get("images", []))

        return _io_pool.submit(_do_copy).result()

    def print_image(self, file_path):
        return self._image_service.print_image(file_path)

    def open_image_external(self, file_path):
        return self._image_service.open_image_external(file_path)

    # =========================================================================
    # Calculators
    # =========================================================================
    def calculate_bill(self, p):
        return self._billing_service.calculate_bill(p)

    def calculate_theft(self, p):
        return self._billing_service.calculate_theft(p)

    def calculate_theft_dual(self, p):
        return self._billing_service.calculate_theft_dual(p)

    def calculate_theft_reverse_load(self, p):
        return self._billing_service.calculate_theft_reverse_load(p)

    def get_tariffs(self):
        try:
            return {"success": True, "tariffs": tariff_manager.load_tariff()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_tariff_data(self, tariffs):
        try:
            tariff_manager.save_tariff(tariffs)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset_tariff_data(self, category=None):
        try:
            tariffs = tariff_manager.reset_tariff(category)
            return {"success": True, "tariffs": tariffs}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Auto-Update
    # =========================================================================
    def check_for_updates(self):
        return _io_pool.submit(self._update_service.check_for_updates).result()

    def start_self_update(self, installer_url=""):
        return self._update_service.start_self_update(installer_url)

    def get_update_progress(self):
        return self._update_service.get_progress()

    def exit_for_update(self):
        return self._update_service.exit_for_update(self._window)

    # =========================================================================
    # Search History & Consumer Notes
    # =========================================================================
    def get_search_history(self, key="consumer_ids"):
        try:
            return {"success": True, "history": utils.load_search_history(key)}
        except Exception as e:
            return {"success": False, "error": str(e), "history": []}

    def save_search_history(self, key="consumer_ids", val=""):
        try:
            if val:
                utils.save_search_history(key, str(val).strip())
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_consumer_note(self, consumer_id):
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT note, remarks FROM notes WHERE consumer_id = ?", (consumer_id,))
            row = cursor.fetchone()
            if row:
                return {"success": True, "note": row[0], "remarks": row[1]}
            return {"success": True, "note": None, "remarks": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_consumer_note(self, consumer_id, note_type, remarks):
        try:
            database.save_note(consumer_id, note_type, remarks)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_consumer_note(self, consumer_id):
        try:
            database.delete_note(consumer_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_note_options(self):
        try:
            return {"success": True, "options": database.get_note_options()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_note_option(self, option_text):
        try:
            database.add_note_option(option_text)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_notes_csv(self, dest_path=""):
        try:
            if not dest_path:
                dest_path = self.pick_save_file(
                    title="Export Notes to CSV",
                    default_filename="consumer_notes_export.csv",
                    file_types=[("CSV Files (*.csv)", "*.csv"), ("All Files (*.*)", "*.*")]
                )
            if not dest_path:
                return {"success": False, "cancelled": True}

            notes = database.get_all_notes()
            with open(dest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Consumer ID", "Note", "Remarks"])
                for cid, data in notes.items():
                    writer.writerow([cid, data["note"], data["remarks"]])
            return {"success": True, "path": dest_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Folder Management & Indexing
    # =========================================================================
    def get_folder_status(self):
        return self._folder_service.get_folder_status()

    def add_network_folder(self, path=""):
        if not path:
            path = self.pick_folder(title="Select Folder to Add")
        if not path:
            return {"success": False, "cancelled": True}
        return self._folder_service.add_network_folder(path)

    def remove_network_folder(self, path):
        return self._folder_service.remove_network_folder(path)

    def start_indexing(self, target_folders=None, full_reindex=False, **kwargs):
        if isinstance(target_folders, dict):
            full_reindex = target_folders.get("full_reindex", target_folders.get("full", False))
            target_folders = target_folders.get("target_folders", None)
        return self._folder_service.start_indexing(target_folders=target_folders, full_reindex=full_reindex)

    def get_indexing_status(self):
        return self._folder_service.get_indexing_status()

    def check_folder_changes(self):
        return self._folder_service.check_folder_changes()

    def get_auto_index_settings(self):
        return {"success": True, "mode": self._folder_service.get_auto_index_mode()}

    def set_auto_index_settings(self, mode):
        saved = self._folder_service.set_auto_index_mode(mode)
        return {"success": True, "mode": saved}

    # =========================================================================
    # Native File & Folder Dialogs
    # =========================================================================
    def _ensure_window_enabled(self):
        """Ensures the PyWebView main window is enabled and brought to foreground."""
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst and hasattr(inst, 'Handle'):
                    import ctypes
                    hwnd = inst.Handle.ToInt64()
                    ctypes.windll.user32.EnableWindow(hwnd, True)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def pick_file(self, title="Select File", file_types=None):
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import OpenFileDialog, DialogResult
                    from System import Func, Object

                    def _show_ofd():
                        try:
                            ofd = OpenFileDialog()
                            ofd.Title = title
                            ofd.RestoreDirectory = True
                            if file_types:
                                if isinstance(file_types, (list, tuple)):
                                    ofd.Filter = "|".join(file_types)
                                else:
                                    ofd.Filter = str(file_types)
                            else:
                                ofd.Filter = "All Files (*.*)|*.*"
                            res = ofd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return ofd.FileName
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_ofd))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_file WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                file_filter = ()
                if file_types:
                    file_filter = tuple(file_types) if isinstance(file_types, (list, tuple)) else (str(file_types),)
                res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=file_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0]
                return ""
        except Exception as e:
            print(f"[pick_file webview error]: {e}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            tk_types = [("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            if file_types and isinstance(file_types, list):
                tk_types = []
                for ft in file_types:
                    if isinstance(ft, (list, tuple)) and len(ft) >= 2:
                        tk_types.append((ft[0], ft[1]))
                    elif isinstance(ft, str):
                        tk_types.append(("Files", ft))
            chosen = filedialog.askopenfilename(title=title, filetypes=tk_types or [("All Files", "*.*")])
            root.destroy()
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_file]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_save_file(self, title="Save File", default_filename="export.xlsx", file_types=None):
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import SaveFileDialog, DialogResult
                    from System import Func, Object

                    def _show_sfd():
                        try:
                            sfd = SaveFileDialog()
                            sfd.Title = title
                            sfd.FileName = default_filename
                            sfd.RestoreDirectory = True
                            if file_types:
                                if isinstance(file_types, (list, tuple)):
                                    sfd.Filter = "|".join(file_types)
                                else:
                                    sfd.Filter = str(file_types)
                            else:
                                sfd.Filter = "All Files (*.*)|*.*"
                            res = sfd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return sfd.FileName
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_sfd))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_save_file WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                file_filter = ()
                if file_types:
                    file_filter = tuple(file_types) if isinstance(file_types, (list, tuple)) else (str(file_types),)
                res = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename, file_types=file_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0] if isinstance(res, (list, tuple)) else str(res)
                return ""
        except Exception as e:
            print(f"[pick_save_file webview error]: {e}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.asksaveasfilename(
                title=title,
                initialfile=default_filename,
                filetypes=file_types or [("All Files", "*.*")]
            )
            root.destroy()
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_save_file]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_folder(self, title="Select Folder to Add", initial_dir=""):
        try:
            if self._window and hasattr(self._window, 'gui'):
                uid = getattr(self._window, 'uid', None)
                from webview.platforms.winforms import BrowserView
                inst = BrowserView.instances.get(uid)
                if inst:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System')
                    from System.Windows.Forms import FolderBrowserDialog, DialogResult
                    from System import Func, Object

                    def _show_fbd():
                        try:
                            fbd = FolderBrowserDialog()
                            fbd.Description = title
                            fbd.ShowNewFolderButton = True
                            if initial_dir and os.path.exists(initial_dir):
                                fbd.SelectedPath = initial_dir
                            res = fbd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return fbd.SelectedPath
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_fbd))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_folder WinForms Invoke error]: {e}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.askdirectory(title=title)
            root.destroy()
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_folder]: {e}")
            self._ensure_window_enabled()
            return ""

    # =========================================================================
    # External File/URL & Tool Launchers
    # =========================================================================
    def launch_image_check_gui(self):
        """Spawns the standalone Image Check GUI tool."""
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                exe_name = "imagecheckgui.exe"
                exe_path = os.path.join(base_dir, exe_name)
                if os.path.exists(exe_path):
                    subprocess.Popen([exe_path], cwd=base_dir)
                    return {"success": True, "message": "Image Check GUI launched (bundled executable)."}

            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(current_dir)
            project_root = os.path.dirname(src_dir)

            candidates = [
                os.path.join(src_dir, "tools", "imagecheckgui.py"),
                os.path.join(project_root, "src", "tools", "imagecheckgui.py"),
                os.path.join(project_root, "tools", "imagecheckgui.py"),
                os.path.join(project_root, "imagecheckgui.py"),
                os.path.join(config.BASE_DIR, "tools", "imagecheckgui.py"),
                os.path.join(config.BASE_DIR, "src", "tools", "imagecheckgui.py"),
                os.path.join(config.BASE_DIR, "imagecheckgui.py"),
                os.path.join(project_root, "dist", f"SpotImageViewerV{config.CURRENT_VERSION}", "imagecheckgui.exe"),
            ]
            script_path = next((c for c in candidates if os.path.exists(c)), None)
            if not script_path:
                return {"success": False, "error": "imagecheckgui.py was not found in tools directory."}

            if script_path.endswith(".exe"):
                subprocess.Popen([script_path], cwd=os.path.dirname(script_path))
            else:
                subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path))
            return {"success": True, "message": f"Image Check GUI launched from {os.path.basename(script_path)}."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_file_external(self, file_path=""):
        try:
            if not file_path:
                return {"success": False, "error": "No file path provided."}
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File does not exist: {file_path}"}

            if os.name == 'nt':
                os.startfile(file_path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, file_path])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_url_external(self, url=""):
        try:
            if not url:
                url = "https://github.com/Hackers-lab/SpotImageViewer"
            import webbrowser
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_database_folder(self):
        return self.open_file_external(config.BASE_DIR)

    # =========================================================================
    # Fuzzy Lookup Engine
    # =========================================================================
    def get_fuzzy_status(self):
        return self._fuzzy_service.get_status()

    def generate_fuzzy_template(self, save_path=""):
        if not save_path:
            save_path = self.pick_save_file(
                title="Save Fuzzy Lookup Template",
                default_filename="fuzzy_lookup_input_template.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        return self._fuzzy_service.generate_fuzzy_template(save_path)

    def lookup_fuzzy_rows(self, rows, threshold=0.85, top_n=5):
        return _io_pool.submit(lambda: self._fuzzy_service.lookup_fuzzy_rows(rows, threshold, top_n)).result()

    def run_fuzzy_lookup(self, input_path="", output_path="", threshold=0.85, top_n=5, include_live_osd=False):
        if not input_path:
            input_path = self.pick_file(
                title="Select Fuzzy Lookup Input Excel",
                file_types=[("Excel Files (*.xlsx;*.xls)", "*.xlsx;*.xls")]
            )
        if not input_path:
            return {"success": False, "cancelled": True}

        if not output_path:
            input_dir = os.path.dirname(os.path.abspath(input_path))
            output_path = os.path.join(input_dir, "fuzzy_lookup_results.xlsx")
            if os.path.exists(output_path):
                import time
                ts = time.strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(input_dir, f"fuzzy_lookup_results_{ts}.xlsx")

        return self._fuzzy_service.start_batch_lookup(input_path, output_path, threshold, top_n, include_live_osd)

    # =========================================================================
    # Consumer Master Data Management
    # =========================================================================
    def generate_consumer_template(self, save_path=""):
        if not save_path:
            save_path = self.pick_save_file(
                title="Save Consumer Data Template",
                default_filename="consumer_data_template.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        return self._consumer_service.generate_template(save_path)

    def import_consumer_data(self, file_path=""):
        if not file_path:
            file_path = self.pick_file(
                title="Select Consumer Data Excel",
                file_types=[("Excel Files (*.xlsx;*.xls)", "*.xlsx;*.xls")]
            )
        if not file_path:
            return {"success": False, "cancelled": True}

        def _do_import():
            res = self._consumer_service.import_from_excel(file_path)
            if res.get("success"):
                self._fuzzy_service.invalidate_cache()
            return res

        return _io_pool.submit(_do_import).result()

    def export_consumer_data_file(self, dest_path=""):
        if not dest_path:
            dest_path = self.pick_save_file(
                title="Export Consumer Master Records",
                default_filename="consumer_master_export.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        if not dest_path:
            return {"success": False, "cancelled": True}

        def _do_export():
            res = self._consumer_service.export_to_excel(dest_path)
            if res.get("success"):
                self.open_file_external(dest_path)
            return res

        return _io_pool.submit(_do_export).result()

    # =========================================================================
    # Low Consumption Audit Studio
    # =========================================================================
    def get_low_consumption_session(self):
        return self._audit_service.get_session()

    def save_low_consumption_session(self, data):
        return self._audit_service.save_session(data)

    def parse_low_consumption_file(self, file_path=""):
        return _io_pool.submit(lambda: self._audit_service.parse_file(file_path)).result()

    def export_low_consumption_report(self, items):
        def _do_export():
            res = self._audit_service.export_report(items)
            if res.get("success") and res.get("file_path"):
                self.open_file_external(res["file_path"])
            return res

        return _io_pool.submit(_do_export).result()

    # =========================================================================
    # Live WBSEDCL OSD & Connection Status
    # =========================================================================
    def get_live_osd(self, consumer_id, force_refresh=False):
        cid = str(consumer_id).strip()
        if not re.match(r"^\d{9}$", cid):
            return {"success": False, "error": f"Invalid Consumer ID '{cid}'. Must be a 9-digit number."}

        import time as _time
        now = _time.time()
        from core import live_osd_service as _los
        with _los._OSD_LOCK:
            if not force_refresh and cid in _los._OSD_CACHE:
                cached_time, cached_result, cached_pdf = _los._OSD_CACHE[cid]
                if (now - cached_time) < _los._CACHE_TTL:
                    import base64 as _b64
                    res = dict(cached_result)
                    if cached_pdf:
                        res["pdfBase64"] = _b64.b64encode(cached_pdf).decode("utf-8")
                    res["cached"] = True
                    return {"success": True, "data": res}

        def _bg_fetch():
            try:
                result = live_osd_service.get_live_osd_data(cid, include_pdf_base64=True, force_refresh=bool(force_refresh))
                if self._window:
                    js_data = json.dumps(result)
                    self._window.evaluate_js(f"if (typeof onLiveOsdResult === 'function') {{ onLiveOsdResult({js_data}); }}")
            except Exception as e:
                if self._window:
                    err = json.dumps({"success": False, "error": str(e)})
                    self._window.evaluate_js(f"if (typeof onLiveOsdResult === 'function') {{ onLiveOsdResult({err}); }}")

        threading.Thread(target=_bg_fetch, daemon=True).start()
        return {"success": True, "pending": True}

    def open_live_osd_pdf(self, consumer_id):
        cid = str(consumer_id).strip()
        if not re.match(r"^\d{9}$", cid):
            return {"success": False, "error": "Invalid Consumer ID. Must be 9 digits."}

        def _fetch():
            try:
                pdf_bytes = live_osd_service.fetch_live_osd_pdf(cid)
                temp_dir = os.path.join(config.BASE_DIR, "temp_osd")
                os.makedirs(temp_dir, exist_ok=True)
                pdf_path = os.path.join(temp_dir, f"WBSEDCL_OSD_{cid}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                self.open_file_external(pdf_path)
                return {"success": True, "file_path": pdf_path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return _io_pool.submit(_fetch).result()

    def check_single_osd(self, consumer_id, force_refresh=False):
        """Synchronously or thread-pool fetches single consumer live OSD data."""
        cid = str(consumer_id).strip()
        return _io_pool.submit(self._osd_service.get_single_osd, cid, bool(force_refresh)).result()

    def start_bulk_osd(self, consumer_ids_input, auto_download_pdf=False, max_workers=3):
        """Starts a background bulk verification run for multiple consumer IDs."""
        return self._osd_service.start_bulk_osd(consumer_ids_input, bool(auto_download_pdf), int(max_workers))

    def get_bulk_osd_status(self):
        """Polls current status and results of the bulk verification job."""
        return self._osd_service.get_bulk_status()

    def cancel_bulk_osd(self):
        """Signals cancellation to the bulk verification job."""
        return self._osd_service.cancel_bulk()

    def export_bulk_osd_excel(self, results, save_path=None):
        """Prompts for save path if not given and exports results to formatted Excel."""
        if not save_path:
            from datetime import datetime
            default_name = f"Consumer_Dues_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            save_path = self.pick_save_file(
                title="Save Dues Excel Report",
                default_filename=default_name,
                file_types=["Excel Files (*.xlsx)", "All Files (*.*)"]
            )
            if not save_path:
                return {"success": False, "cancelled": True}
        return _io_pool.submit(self._osd_service.export_excel, results, save_path).result()

    def export_bulk_osd_csv(self, results, save_path=None):
        """Prompts for save path if not given and exports results to CSV."""
        if not save_path:
            from datetime import datetime
            default_name = f"Consumer_Dues_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            save_path = self.pick_save_file(
                title="Save Dues CSV Report",
                default_filename=default_name,
                file_types=["CSV Files (*.csv)", "All Files (*.*)"]
            )
            if not save_path:
                return {"success": False, "cancelled": True}
        return _io_pool.submit(self._osd_service.export_csv, results, save_path).result()

    def select_osd_batch_file(self):
        """Opens file dialog for user to select an Excel or CSV file containing consumer IDs."""
        path = self.pick_file(
            title="Select Excel or CSV File with Consumer IDs",
            file_types=["Excel / CSV / Text Files (*.xlsx;*.xls;*.csv;*.txt)", "All Files (*.*)"]
        )
        if not path:
            return {"success": False, "cancelled": True}
        ids = self._osd_service.extract_consumer_ids(path)
        return {"success": True, "path": path, "consumer_ids": ids, "count": len(ids)}

    def generate_bulk_osd_template(self):
        """Prompts user where to save a blank bulk consumer input template."""
        save_path = self.pick_save_file(
            title="Save Bulk Input Template",
            default_filename="Bulk_Consumer_ID_Template.xlsx",
            file_types=["Excel Files (*.xlsx)", "All Files (*.*)"]
        )
        if not save_path:
            return {"success": False, "cancelled": True}
        return self._osd_service.generate_template(save_path)
