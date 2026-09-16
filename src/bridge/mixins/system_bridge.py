import os
import sys
import json
import threading
import subprocess

try:
    from core import config, database
except ImportError:
    import config, database

from .base import _wait_db, _get_tk_root, _io_pool


class SystemBridge:
    """System information, settings, theme, update, and external tool launcher bridge."""

    def log_perf_client(self, stage, elapsed_ms=None, details=""):
        try:
            from core import perf_log
            perf_log.log_perf(stage, elapsed_ms, details)
        except Exception:
            pass
        return True

    def show_window(self):
        if self._window:
            self._window.show()
            try:
                from core import perf_log
                perf_log.log_perf("WINDOW_SHOWN", details="App window revealed on screen fully rendered")
            except Exception:
                pass
        return True

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

    def check_for_updates(self):
        return _io_pool.submit(self._update_service.check_for_updates).result()

    def start_self_update(self, installer_url=""):
        return self._update_service.start_self_update(installer_url)

    def get_update_progress(self):
        return self._update_service.get_progress()

    def exit_for_update(self):
        return self._update_service.exit_for_update(self._window)

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
            bridge_dir = os.path.dirname(current_dir)
            src_dir = os.path.dirname(bridge_dir)
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
