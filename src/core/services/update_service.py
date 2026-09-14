import os
import time
import requests
import tempfile
import threading
try:
    from core import config, utils
except ImportError:
    import config, utils


class UpdateService:
    """
    Manages auto-update checking against remote JSON manifest, background
    installer downloading with progress tracking, and installer execution.
    """

    def __init__(self):
        self._update_state = {
            "status": "idle",
            "downloaded": 0,
            "total": 0,
            "percent": 0,
            "error": None,
            "installer_path": None
        }

    def get_progress(self):
        return dict(self._update_state)

    @staticmethod
    def check_for_updates():
        """Queries the update URL to see if a newer version is available."""
        try:
            r = requests.get(config.UPDATE_URL, timeout=4)
            if r.status_code == 200:
                data = r.json()
                latest_v = data.get("version")
                has_update = float(latest_v) > float(config.CURRENT_VERSION)
                return {
                    "success": True,
                    "has_update": has_update,
                    "current_version": config.CURRENT_VERSION,
                    "latest_version": latest_v,
                    "release_notes": data.get("release_notes", ""),
                    "installer_url": data.get("installer_url") or data.get("download_url", "")
                }
            return {"success": False, "error": "Failed to connect to update server."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_self_update(self, installer_url=""):
        """Downloads installer asynchronously and launches installer trigger."""
        if self._update_state.get("status") == "downloading":
            return {"success": True, "message": "Download already in progress."}

        self._update_state = {
            "status": "downloading",
            "downloaded": 0,
            "total": 0,
            "percent": 0,
            "error": None,
            "installer_path": None
        }

        def _worker():
            try:
                target_url = str(installer_url).strip() if installer_url else ""
                if not target_url:
                    r = requests.get(config.UPDATE_URL, timeout=5)
                    if r.status_code == 200:
                        d = r.json()
                        target_url = d.get("installer_url") or d.get("download_url") or ""
                if not target_url:
                    raise ValueError("No valid installer URL found.")

                filename = os.path.basename(target_url.split("?")[0]) or f"SpotImageViewer_Setup_v{config.CURRENT_VERSION}.exe"
                temp_dir = tempfile.gettempdir()
                dest_path = os.path.join(temp_dir, filename)

                def _prog(dl, tot):
                    self._update_state["downloaded"] = dl
                    self._update_state["total"] = tot
                    self._update_state["percent"] = int((dl / tot) * 100) if tot else 0

                utils.download_file_with_progress(target_url, dest_path, _prog)

                self._update_state["status"] = "ready"
                self._update_state["percent"] = 100
                self._update_state["installer_path"] = dest_path

                current_pid = os.getpid()
                utils.launch_windows_installer(dest_path, current_pid)
            except Exception as e:
                self._update_state["status"] = "error"
                self._update_state["error"] = str(e)

        threading.Thread(target=_worker, daemon=True).start()
        return {"success": True}

    @staticmethod
    def exit_for_update(window=None):
        """Terminates application so staged installer script can run."""
        def _delayed_exit():
            time.sleep(1.0)
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
            os._exit(0)

        threading.Thread(target=_delayed_exit, daemon=True).start()
        return {"success": True}
