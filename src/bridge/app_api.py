import os
import sys
import json
import re
import csv
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
_tk_lock = threading.Lock()
_tk_root = None

def _get_tk_root():
    global _tk_root
    with _tk_lock:
        if _tk_root is None:
            import tkinter as tk
            _tk_root = tk.Tk()
            _tk_root.withdraw()
        return _tk_root

try:
    from core import config, database, utils, tariff_manager
except ImportError:
    import config, database, utils, tariff_manager

# Shared thread pool for offloading heavy I/O from the PyWebView bridge thread.
_io_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="siv-io")
# Dedicated thread pool for image decoding and resizing to prevent UI thread starvation
_image_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="siv-img")


def _wait_db(timeout=5.0):
    """Wait for init_db to finish (prevents deadlock with schema migration locks)."""
    database.init_db_ready.wait(timeout=timeout)


class AppAPI:
    """
    Python-to-JavaScript RPC bridge exposed to the PyWebView window.
    Acts as a clean Facade dispatching requests to core domain services.
    All methods return JSON-serializable dictionaries or primitives.
    Heavy domain services are loaded lazily on first access to ensure
    near-instantaneous application window startup (<600ms).
    """

    def __init__(self, window=None):
        self._window = window
        self._billing_service_inst = None
        self._image_service_inst = None
        self._fuzzy_service_inst = None
        self._consumer_service_inst = None
        self._audit_service_inst = None
        self._folder_service_inst = None
        self._update_service_inst = None
        self._osd_service_inst = None
        self._last_dcrc_result = None

    def set_window(self, window):
        self._window = window

    @property
    def _billing_service(self):
        if self._billing_service_inst is None:
            try:
                from core.services.billing_service import BillingService
            except ImportError:
                from services.billing_service import BillingService
            self._billing_service_inst = BillingService()
        return self._billing_service_inst

    @property
    def _image_service(self):
        if self._image_service_inst is None:
            try:
                from core.services.image_service import ImageService
            except ImportError:
                from services.image_service import ImageService
            self._image_service_inst = ImageService()
        return self._image_service_inst

    @property
    def _fuzzy_service(self):
        if self._fuzzy_service_inst is None:
            try:
                from core.services.fuzzy_service import FuzzyService
            except ImportError:
                from services.fuzzy_service import FuzzyService
            self._fuzzy_service_inst = FuzzyService()
        return self._fuzzy_service_inst

    @property
    def _consumer_service(self):
        if self._consumer_service_inst is None:
            try:
                from core.services.consumer_data_service import ConsumerDataService
            except ImportError:
                from services.consumer_data_service import ConsumerDataService
            self._consumer_service_inst = ConsumerDataService()
        return self._consumer_service_inst

    @property
    def _audit_service(self):
        if self._audit_service_inst is None:
            try:
                from core.services.audit_service import AuditService
            except ImportError:
                from services.audit_service import AuditService
            self._audit_service_inst = AuditService()
        return self._audit_service_inst

    @property
    def _folder_service(self):
        if self._folder_service_inst is None:
            try:
                from core.services.folder_service import FolderIndexerService
            except ImportError:
                from services.folder_service import FolderIndexerService
            self._folder_service_inst = FolderIndexerService()
        return self._folder_service_inst

    @property
    def _update_service(self):
        if self._update_service_inst is None:
            try:
                from core.services.update_service import UpdateService
            except ImportError:
                from services.update_service import UpdateService
            self._update_service_inst = UpdateService()
        return self._update_service_inst

    @property
    def _osd_service(self):
        if self._osd_service_inst is None:
            try:
                from core.services.osd_service import OSDService
            except ImportError:
                from services.osd_service import OSDService
            self._osd_service_inst = OSDService()
        return self._osd_service_inst

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
        # Fast local check for primary folder
        folders.append({
            "path": primary_path,
            "accessible": os.path.exists(primary_path) if primary_path else False,
            "is_primary": True
        })
        for p in database.get_additional_folders():
            folders.append({
                "path": p,
                "accessible": True,  # Optimistic initial status; validated asynchronously below
                "is_primary": False
            })

        # Check all folder accessibility asynchronously so network shares or disconnected drives NEVER block startup
        def _bg_check_folders():
            try:
                from core.services.folder_service import path_accessible
                updated_folders = []
                for f in folders:
                    updated_folders.append({
                        "path": f["path"],
                        "accessible": path_accessible(f["path"], timeout=0.8),
                        "is_primary": f["is_primary"]
                    })
                if self._window:
                    import json
                    payload = json.dumps(updated_folders).replace('\\', '\\\\')
                    self._window.evaluate_js(f"if (typeof renderFolders === 'function') {{ renderFolders({payload}); }}")
            except Exception:
                pass
        threading.Thread(target=_bg_check_folders, daemon=True).start()

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
                root = _get_tk_root()
                try:
                    text = root.clipboard_get()
                except Exception:
                    text = ""
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

            # Deduplicate by date: when multiple images of the same date exist from different folders,
            # select only ONE best image per date (preferring existing files and local storage)
            from collections import OrderedDict
            by_date = OrderedDict()
            for date_orig, mru, dir_path, filename in rows:
                if date_orig not in by_date:
                    by_date[date_orig] = []
                by_date[date_orig].append((mru, dir_path, filename))

            grouped = {}
            flat_images = []
            for date_orig, candidates in by_date.items():
                chosen = candidates[0]
                # If multiple candidates exist for the same date, prefer one whose file exists on disk
                if len(candidates) > 1:
                    for cand in candidates:
                        mru, dir_path, filename = cand
                        fp = os.path.join(dir_path, filename)
                        if os.path.exists(fp):
                            chosen = cand
                            break

                mru, dir_path, filename = chosen
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
                grouped[pretty_date] = [item]
                flat_images.append(item)

            profile = database.get_consumer_profile(cid)

            return {
                "success": True,
                "consumer_id": cid,
                "profile": profile,
                "mru": flat_images[0]["mru"] if flat_images else "",
                "total_images": len(flat_images),
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
        return _image_pool.submit(lambda: self._image_service.get_image_data(file_path, max_dim)).result()

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

    @staticmethod
    def _format_file_filters(file_types):
        """
        Normalizes arbitrary file_types specifications into valid formats for:
        1. WinForms OpenFileDialog/SaveFileDialog: 'Desc1 (*.ext)|*.ext|All Files (*.*)|*.*'
        2. pywebview Window.create_file_dialog: ('Desc1 (*.ext)', 'All Files (*.*)')
        3. tkinter.filedialog: [('Desc1', '*.ext'), ('All Files', '*.*')]
        """
        pairs = []
        if not file_types:
            pairs = [("All Files", "*.*")]
        elif isinstance(file_types, str):
            if "|" in file_types:
                parts = [p.strip() for p in file_types.split("|") if p.strip()]
                for i in range(0, len(parts) - 1, 2):
                    pairs.append((parts[i], parts[i + 1]))
            else:
                pairs.append((file_types, file_types))
        elif isinstance(file_types, (list, tuple)):
            for item in file_types:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    pairs.append((str(item[0]), str(item[1])))
                elif isinstance(item, str):
                    m = re.match(r'^(.*?)\s*\((.*?)\)$', item.strip())
                    if m:
                        pairs.append((m.group(1).strip(), m.group(2).strip()))
                    else:
                        pairs.append((item.strip(), item.strip()))

        normalized_pairs = []
        has_all = False
        for desc, patt in pairs:
            clean_desc = re.sub(r'\s*\(.*?\)\s*$', '', desc).strip()
            clean_patt = patt.strip('() ').strip()
            if clean_patt == '*.*' or clean_desc.lower() == 'all files':
                has_all = True
                normalized_pairs.append(('All Files', '*.*'))
            else:
                normalized_pairs.append((clean_desc or 'Supported Files', clean_patt))

        if not has_all:
            normalized_pairs.append(('All Files', '*.*'))

        # 1. WinForms filter string: "Description (pattern)|pattern|All Files (*.*)|*.*"
        wf_parts = []
        for desc, patt in normalized_pairs:
            if patt == '*.*':
                wf_parts.append('All Files (*.*)')
                wf_parts.append('*.*')
            else:
                wf_parts.append(f'{desc} ({patt})')
                wf_parts.append(patt)
        winforms_str = '|'.join(wf_parts)

        # 2. PyWebView filter tuple: ('Safe Description (*.ext)', ...)
        pwv_list = []
        for desc, patt in normalized_pairs:
            safe_desc = re.sub(r'[^\w ]', ' ', desc)
            safe_desc = ' '.join(safe_desc.split()) or 'Files'
            clean_pw_patt = patt.replace(' ', '')
            pwv_str = f'{safe_desc} ({clean_pw_patt})'
            pwv_list.append(pwv_str)

        # 3. Tkinter filetypes list: [('Description', '*.ext1 *.ext2'), ...]
        tk_list = []
        for desc, patt in normalized_pairs:
            tk_patt = patt.replace(';', ' ')
            tk_list.append((desc, tk_patt))

        return winforms_str, tuple(pwv_list), tk_list

    def pick_file(self, title="Select File", file_types=None):
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
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
                            ofd.Filter = wf_filter
                            ofd.FilterIndex = 1
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
                res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0]
                return ""
        except Exception as e:
            print(f"[pick_file webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.askopenfilename(title=title, filetypes=tk_filter)
            self._ensure_window_enabled()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_file]: {e}")
            self._ensure_window_enabled()
            return ""

    def pick_save_file(self, title="Save File", default_filename="export.xlsx", file_types=None):
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
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
                            sfd.Filter = wf_filter
                            sfd.FilterIndex = 1
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
                res = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0] if isinstance(res, (list, tuple)) else str(res)
                return ""
        except Exception as e:
            print(f"[pick_save_file webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.asksaveasfilename(
                title=title,
                initialfile=default_filename,
                filetypes=tk_filter
            )
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
                from webview.platforms.winforms import BrowserView, OpenFolderDialog
                inst = BrowserView.instances.get(uid)
                if inst:
                    from System import Func, Object

                    def _show_native_folder():
                        try:
                            # Uses native Windows Vista/7/10/11 IFileDialog with FOS_PICKFOLDERS
                            # providing full Windows Explorer navigation with Search box,
                            # expandable Network locations, and address bar.
                            res = OpenFolderDialog.show(inst, initial_dir or None, False, title)
                            if res and len(res) > 0:
                                return res[0]
                            return ""
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_native_folder))
                    return str(chosen) if chosen else ""
        except Exception as e:
            print(f"[pick_folder WinForms OpenFolderDialog error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=initial_dir or "")
                self._ensure_window_enabled()
                if res and len(res) > 0:
                    return res[0]
                return ""
        except Exception as e:
            print(f"[pick_folder webview error]: {e}")

        try:
            from tkinter import filedialog
            root = _get_tk_root()
            root.attributes('-topmost', True)
            chosen = filedialog.askdirectory(title=title)
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

        try:
            from core import live_osd_service as _los
        except ImportError:
            import live_osd_service as _los

        # If already cached and not force refreshing, return immediately
        if not force_refresh:
            cached_res = _los.get_live_osd_data(cid, include_pdf_base64=False, force_refresh=False)
            if cached_res.get("success") and cached_res.get("data", {}).get("cached"):
                return cached_res

        def _bg_fetch():
            try:
                result = _los.get_live_osd_data(cid, include_pdf_base64=True, force_refresh=bool(force_refresh))
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
                try:
                    from core import live_osd_service as _los
                except ImportError:
                    import live_osd_service as _los

                pdf_bytes = _los.fetch_live_osd_pdf(cid)

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

    # =========================================================================
    # DCRC & Agency PO Generator Bridge Methods
    # =========================================================================
    def pick_files_multiple(self, title="Select Files", file_types=None):
        """Allows selecting multiple files via WinForms, webview, or tkinter fallback."""
        wf_filter, pwv_filter, tk_filter = self._format_file_filters(file_types)
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

                    def _show_ofd_multi():
                        try:
                            ofd = OpenFileDialog()
                            ofd.Title = title
                            ofd.Multiselect = True
                            ofd.RestoreDirectory = True
                            ofd.Filter = wf_filter
                            ofd.FilterIndex = 1
                            res = ofd.ShowDialog(inst)
                            if res == DialogResult.OK:
                                return list(ofd.FileNames)
                            return []
                        finally:
                            self._ensure_window_enabled()

                    chosen = inst.Invoke(Func[Object](_show_ofd_multi))
                    return list(chosen) if chosen else []
        except Exception as e:
            print(f"[pick_files_multiple WinForms Invoke error]: {e}")

        try:
            if self._window and hasattr(self._window, "create_file_dialog"):
                import webview
                res = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True, file_types=pwv_filter)
                self._ensure_window_enabled()
                if res:
                    return list(res)
                return []
        except Exception as e:
            print(f"[pick_files_multiple webview error]: {e}")

        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.askopenfilenames(title=title, filetypes=tk_filter)
            root.destroy()
            self._ensure_window_enabled()
            return list(chosen) if chosen else []
        except Exception as e:
            print(f"[Error in pick_files_multiple]: {e}")
            self._ensure_window_enabled()
            return []

    def pick_dcrc_events_files(self):
        """Selects one or more DCRC SAP export files (DC.XLS, RC.XLS, DR.xls, ONLINE DR.XLS)."""
        files = self.pick_files_multiple(
            title="Select DCRC Files (DC, RC, DR, ONLINE DR)",
            file_types=["SAP / Excel Files (*.xls;*.xlsx;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "files": files, "count": len(files)}

    def pick_cash_payment_files(self):
        """Selects one or more SAP Cash Payment Register files (cash1.XLSX, CASH2.XLSX)."""
        files = self.pick_files_multiple(
            title="Select Payment / Cash Files (cash1, CASH2)",
            file_types=["Excel / SAP Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "files": files, "count": len(files)}

    def pick_zone_mapping_file(self):
        """Selects the Zone-Agency Mapping file (Zones.xlsx)."""
        f = self.pick_file(
            title="Select Zone-Agency Mapping File (Zones.xlsx)",
            file_types=["Excel / CSV Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "file": f}

    def pick_consumer_master_file(self):
        """Selects the Consumer Master Data file (Consumer Data.xlsx)."""
        f = self.pick_file(
            title="Select Consumer Master File (Consumer Data.xlsx)",
            file_types=["Excel / CSV Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "file": f}

    def pick_dcrc_output_folder(self):
        """Selects the folder where Agency Workbooks & Reports will be saved."""
        folder = self.pick_folder(title="Select Output Folder for Agency Workbooks")
        return {"success": True, "folder": folder}

    def get_dcrc_defaults(self):
        """Returns paths to default templates and configured standard rates."""
        try:
            from core.services import dcrc_processor
        except ImportError:
            from services import dcrc_processor

        template_dir = r"C:\spotbillfiles\dcrc_templates"
        zone_tpl = os.path.join(template_dir, "Zones_Template.xlsx")
        cm_tpl = os.path.join(template_dir, "Consumer_Master_Template.xlsx")
        default_out = r"C:\spotbillfiles\DCRC_PO_Output"

        return {
            "success": True,
            "template_dir": template_dir,
            "zone_template": zone_tpl if os.path.exists(zone_tpl) else "",
            "consumer_template": cm_tpl if os.path.exists(cm_tpl) else "",
            "default_output": default_out,
            "standard_rates": dcrc_processor.DEFAULT_STANDARD_RATES,
            "custom_rates": dcrc_processor.DEFAULT_CUSTOM_AGENCY_RATES
        }

    def process_dcrc_data(self, dcrc_files, cash_files, zone_file, consumer_file=None, custom_rates=None):
        """
        Processes the DCRC run asynchronously in the I/O pool.
        Stores the result in self._last_dcrc_result for instant export.
        """
        def _run():
            try:
                try:
                    from core.services import dcrc_processor
                except ImportError:
                    from services import dcrc_processor

                # If consumer_file is empty or not provided, check if default template exists
                cm_path = consumer_file
                if not cm_path or not os.path.exists(cm_path):
                    default_cm = r"C:\spotbillfiles\dcrc_templates\Consumer_Master_Template.xlsx"
                    if os.path.exists(default_cm):
                        cm_path = default_cm

                res = dcrc_processor.process_dcrc_run(
                    dcrc_file_paths=dcrc_files,
                    cash_file_paths=cash_files,
                    zone_file_path=zone_file,
                    consumer_master_file_path=cm_path,
                    custom_rates=custom_rates
                )
                self._last_dcrc_result = res
                # Return lightweight summary to frontend (omit full records array for fast serialization)
                return {
                    "success": True,
                    "summary": res.get("summary", []),
                    "totals": res.get("totals", {}),
                    "discrepancies": res.get("discrepancies", [])[:100],
                    "total_records_processed": res.get("total_records_processed", 0),
                    "total_discrepancies": res.get("total_discrepancies", 0),
                    "zone_cutoffs": res.get("zone_cutoffs", []),
                    "sample_records": res.get("records", [])[:30]
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"success": False, "error": str(e)}

        return _io_pool.submit(_run).result()

    def export_dcrc_files(self, output_folder=None):
        """
        Exports individual <Agency>.xlsx workbooks, PO Summary Report, and MAIN LIST.
        """
        if not self._last_dcrc_result:
            return {"success": False, "error": "No processed DCRC data available. Please process files first."}

        try:
            from core.services import dcrc_exporter
        except ImportError:
            from services import dcrc_exporter

        out_dir = output_folder or r"C:\spotbillfiles\DCRC_PO_Output"
        try:
            ag_files = dcrc_exporter.export_agency_workbooks(self._last_dcrc_result, out_dir)
            rep_file = dcrc_exporter.export_summary_report(self._last_dcrc_result, out_dir)
            main_file = dcrc_exporter.export_master_list(self._last_dcrc_result, out_dir)

            return {
                "success": True,
                "output_dir": out_dir,
                "agency_files_count": len(ag_files),
                "summary_report": rep_file,
                "main_list": main_file
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_folder_in_explorer(self, folder_path):
        """Opens the specified folder in Windows Explorer."""
        try:
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return {"success": True}
            return {"success": False, "error": "Folder does not exist"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_sample_template_path(self, sample_type):
        filename_map = {
            "dcrc": "Sample_DCRC_List.xlsx",
            "payment": "Sample_Payment_Cash.xlsx",
            "zone": "Sample_Zone_Map.xlsx",
            "consumer_master": "Sample_Consumer_Master.xlsx"
        }
        fname = filename_map.get(sample_type)
        if not fname:
            return None, None

        # Priority 1: C:\spotbillfiles\dcrc_templates
        p1 = os.path.join(r"C:\spotbillfiles\dcrc_templates", fname)
        if os.path.exists(p1):
            return p1, fname

        # Priority 2: src/resources/templates
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p2 = os.path.join(base_dir, "resources", "templates", fname)
        if os.path.exists(p2):
            return p2, fname

        return None, fname

    def download_dcrc_sample(self, sample_type):
        """Allows user to save a sample template to a location of their choice."""
        src_path, fname = self._get_sample_template_path(sample_type)
        if not src_path:
            return {"success": False, "error": f"Sample template '{fname}' not found."}

        dest = self.pick_save_file(
            title=f"Save {fname}",
            default_filename=fname,
            file_types=[("Excel Files", "*.xlsx")]
        )
        if not dest:
            return {"success": False, "cancelled": True}

        try:
            shutil.copyfile(src_path, dest)
            return {"success": True, "saved_path": dest, "filename": fname}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_dcrc_sample(self, sample_type):
        """Directly opens the requested sample template in default spreadsheet application."""
        src_path, fname = self._get_sample_template_path(sample_type)
        if not src_path:
            return {"success": False, "error": f"Sample template '{fname}' not found."}
        try:
            os.startfile(src_path)
            return {"success": True, "path": src_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_dcrc_templates_folder(self):
        """Opens the folder containing sample templates in Windows Explorer."""
        p = r"C:\spotbillfiles\dcrc_templates"
        if not os.path.exists(p):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            p = os.path.join(base_dir, "resources", "templates")
        try:
            os.makedirs(p, exist_ok=True)
            os.startfile(p)
            return {"success": True, "folder": p}
        except Exception as e:
            return {"success": False, "error": str(e)}


