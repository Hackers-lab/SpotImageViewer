import os
import json
import time
import threading
import logging

from .constants import LOG_DIR
from .client import SessionExpiredException


class SessionManager:
    """Manages login session state, persistent zone cache, keep-alive heartbeat, and local progress."""

    def __init__(self, api_client):
        self.api_client = api_client
        self.username = ""
        self.token = ""
        self.off_code = ""
        self.off_name = ""
        self.name = ""
        self.designation = ""

        self.keep_alive_active = False
        self.keep_alive_thread = None

        self.zones_cache_file = os.path.join(LOG_DIR, "zones_cache.json")
        self.zones_cache = self.load_zones_cache()

    def set_session(self, username, token, off_code, off_name, name, designation):
        self.username = username
        self.token = token
        self.off_code = off_code
        self.off_name = off_name
        self.name = name
        self.designation = designation

    def clear_session(self):
        self.stop_keep_alive()
        self.username = ""
        self.token = ""
        self.off_code = ""
        self.off_name = ""
        self.name = ""
        self.designation = ""

    def load_zones_cache(self):
        try:
            if os.path.exists(self.zones_cache_file):
                with open(self.zones_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load zones cache: {e}")
        return {}

    def save_zones_cache(self):
        try:
            os.makedirs(os.path.dirname(self.zones_cache_file), exist_ok=True)
            with open(self.zones_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.zones_cache, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save zones cache: {e}")

    def start_keep_alive(self, on_success_callback=None, on_error_callback=None):
        self.stop_keep_alive()
        self.keep_alive_active = True

        def _loop():
            while self.keep_alive_active:
                for _ in range(300):
                    if not self.keep_alive_active:
                        return
                    time.sleep(1)

                if not self.username or not self.token:
                    continue

                try:
                    logging.info("Sending session keep-alive ping to Tomcat server...")
                    self.api_client.verify_token(self.username, self.token)
                    if on_success_callback:
                        on_success_callback()
                except Exception as e:
                    logging.warning(f"Session keep-alive ping failed: {e}")
                    if on_error_callback:
                        on_error_callback(str(e))

        self.keep_alive_thread = threading.Thread(target=_loop, daemon=True)
        self.keep_alive_thread.start()

    def stop_keep_alive(self):
        self.keep_alive_active = False

    def save_local_progress(self, mru, month, year, audited_ids, audit_decisions):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            saved_decisions = {}
            for cid in audited_ids:
                if cid in audit_decisions:
                    saved_decisions[cid] = audit_decisions[cid]

            payload = {
                "mru": mru,
                "month": month,
                "year": year,
                "decisions": saved_decisions
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save local progress: {e}")

    def load_local_progress(self, current_mru, current_month, current_year):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                if isinstance(payload, dict) and "decisions" in payload:
                    if (payload.get("mru") == current_mru and
                        payload.get("month") == current_month and
                        payload.get("year") == current_year):
                        return payload["decisions"]
                    else:
                        try:
                            os.remove(path)
                        except Exception:
                            pass
        except Exception as e:
            logging.error(f"Failed to load local progress: {e}")
        return None

    def remove_from_local_progress(self, con_id):
        try:
            con_id_str = str(con_id)
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict) and "decisions" in payload:
                    if con_id_str in payload["decisions"]:
                        del payload["decisions"][con_id_str]
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to remove {con_id} from local progress: {e}")
