import os
import sys
import json
import time
import base64
import io
import threading
import queue
import requests
from PIL import Image, ImageTk
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import logging

# Define appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Setup App Data logging
LOG_DIR = os.path.expanduser("~/.gemini/antigravity/logs")
os.makedirs(LOG_DIR, exist_ok=True)
IMAGE_CACHE_DIR = os.path.join(LOG_DIR, "image_cache")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
DEFAULT_BASE_URL = "https://spotai.wbsedcl.in"
DEFAULT_USER = "90018747"
DEFAULT_OFF_CODE = "6612107"

class SessionExpiredException(Exception):
    pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def hk_encrypt(password_str):
    secret_key = "@FrTu^^&!#$%^/41"
    key_len = len(secret_key)
    xor_chars = []
    for r in range(len(password_str)):
        c_code = ord(password_str[r])
        k_code = ord(secret_key[r % key_len])
        xor_chars.append(chr(c_code ^ k_code))
    xor_str = "".join(xor_chars)
    # latin1 preserves the exact 0-255 byte values as characters
    return base64.b64encode(xor_str.encode('latin1')).decode('utf-8')

class TomcatAPIClient:
    def __init__(self, base_url=DEFAULT_BASE_URL):
        self.base_url = base_url.strip().rstrip('/')

    def _post(self, path, payload, content_type="application/json", timeout=10):
        url = f"{self.base_url}{path}"
        headers = HEADERS.copy()
        headers["Content-Type"] = content_type
        try:
            if content_type == "text/plain":
                data = json.dumps(payload)
                response = requests.post(url, data=data, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            res_json = response.json()
            # Intercept session expiration codes
            if isinstance(res_json, dict) and res_json.get("code") in ("100", "600"):
                raise SessionExpiredException(res_json.get("message", "Session expired (Code 100/600)"))
            elif isinstance(res_json, list) and len(res_json) > 0 and isinstance(res_json[0], dict):
                if res_json[0].get("code") in ("100", "600"):
                    raise SessionExpiredException(res_json[0].get("message", "Session expired (Code 100/600)"))
            return res_json
        except requests.exceptions.HTTPError as he:
            if he.response is not None and he.response.status_code in (401, 403):
                raise SessionExpiredException("Authentication failed or session expired (401/403)")
            try:
                err_data = response.json()
                if isinstance(err_data, dict) and err_data.get("code") in ("100", "600"):
                    raise SessionExpiredException(err_data.get("message", "Session expired"))
                return err_data
            except Exception:
                raise Exception(f"HTTP Error {response.status_code}: {response.text}")
        except SessionExpiredException:
            raise
        except Exception as e:
            raise Exception(f"Network error: {str(e)}")

    def submit_for_otp(self, username, password):
        path = "/spotaiportal/spot_ai_portal_login"
        encrypted_password = hk_encrypt(password)
        payload = [{
            "username": username,
            "password": encrypted_password
        }]
        res = self._post(path, payload, content_type="text/plain")
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def submit_final_otp(self, username, otp):
        path = "/spotaiportal/spot_ai_portal_login"
        payload = [{
            "username": username,
            "otp": otp
        }]
        res = self._post(path, payload, content_type="text/plain")
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def verify_token(self, username, token):
        path = "/spotaiportal/spot_ai_portal_token_check"
        payload = [{"username": username, "token": token}]
        res = self._post(path, payload)
        if isinstance(res, dict):
            return res
        elif isinstance(res, list) and len(res) > 0:
            return res[0]
        raise Exception("Invalid response format from server")

    def fetch_smrd(self, username, token, off_code):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "parameter": "smrd"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return [item["smrd"] for item in res.get("message", []) if item.get("smrd")]
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch SMRD: {msg}")

    def fetch_mru(self, username, token, off_code, acc_month, acc_year):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "ccc_code": off_code,
            "parameter": "mru"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return [item["mru"] for item in res.get("message", []) if item.get("mru")]
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch MRU: {msg}")

    def fetch_queue(self, username, token, off_code, acc_month, acc_year, zone, ai_flag):
        path = "/spotaiportal/snapshot"
        
        # Mapping AI Flag to corresponding parameter as per JS bundle
        param_map = {
            "Accepted by Reader": "imagecheckingAIH",
            "Not Accepted by Reader": "imagecheckingAIM",
            "No Reading from AI Engine": "imagecheckingAIN",
            "Not under AI Scope": "imagecheckingAIU"
        }
        parameter = param_map.get(ai_flag, "imagecheckingAIH")

        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "zone": zone,
            "parameter": parameter
        }]
        
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return res.get("message", [])
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch batch queue: {msg}")

    def fetch_image_base64(self, username, token, off_code, photo_url):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "parameter": "getimagebase64",
            "connection_string": [{"URL": photo_url}]
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            msg_list = res.get("message", [])
            if msg_list and isinstance(msg_list, list):
                return msg_list[0].get("imagebase64")
        return None

    def fetch_conid_all(self, username, token, off_code, con_id):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "con_id": str(con_id),
            "parameter": "conid_all"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict) and res.get("code") == "200":
            return res.get("message", [])
        else:
            msg = res.get("message") if isinstance(res, dict) else str(res)
            raise Exception(f"Failed to fetch billing history: {msg}")

    def submit_audit_record(self, username, token, off_code, acc_month, acc_year, ccc_code, ccc_name, con_id, smrdn, verification_stat, meter_note=" ", sapdata="MIS"):
        path = "/spotaiportal/snapshot"
        payload = [{
            "username": username,
            "token": token,
            "off_code": off_code,
            "acc_month": acc_month,
            "acc_year": acc_year,
            "ccc_code": ccc_code,
            "ccc_name": ccc_name,
            "con_id": str(con_id),
            "smrdn": smrdn if smrdn else " ",
            "verification_stat": verification_stat,
            "meter_note": meter_note if meter_note else " ",
            "sapdata": sapdata,
            "parameter": "imagecheckinginsert"
        }]
        res = self._post(path, payload)
        if isinstance(res, dict):
            code = res.get("code")
            msg = res.get("message", "")
            if code == "200" or "SUCCESS" in str(msg).upper():
                return True, msg
            else:
                return False, f"Code {code}: {msg}"
        elif isinstance(res, list) and len(res) > 0:
            msg = str(res[0])
            if "SUCCESS" in msg.upper():
                return True, msg
            return False, msg
        return False, str(res)


class ImagePrefetcher:
    def __init__(self, api_client):
        self.api_client = api_client
        self.image_cache = {}      # con_id -> PIL.Image or "error"
        self.cache_loading = set() # set of con_ids currently fetching
        self.queue_records = []
        self.current_index = 0
        
        self.username = ""
        self.token = ""
        self.off_code = ""
        self.default_zone = ""
        
        self.lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.work_event = threading.Event()
        
        self.ui_update_callback = None
        
        # Start background thread
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def update_config(self, username, token, off_code):
        with self.lock:
            self.username = username
            self.token = token
            self.off_code = off_code

    def set_queue(self, records, default_smrd="", default_zone=""):
        # default_smrd is kept for backward signature compatibility, unused
        with self.lock:
            self.queue_records = records
            self.current_index = 0
            self.default_zone = default_zone
        
        with self.cache_lock:
            self.image_cache.clear()
            self.cache_loading.clear()
            
        self.work_event.set()

    def set_active_index(self, index):
        with self.lock:
            self.current_index = index
        self.work_event.set()

    def get_image(self, con_id):
        with self.cache_lock:
            return self.image_cache.get(con_id)

    def trigger_prefetch(self):
        self.work_event.set()

    def stop(self):
        self.stop_event.set()
        self.work_event.set()

    def _worker_loop(self):
        while not self.stop_event.is_set():
            # Wait for signal or timeout
            self.work_event.wait(timeout=0.1)
            if self.stop_event.is_set():
                break

            # Safely fetch state parameters
            with self.lock:
                records = list(self.queue_records)
                active_idx = self.current_index
                username = self.username
                token = self.token
                off_code = self.off_code
                default_zone = self.default_zone

            if not records or active_idx < 0 or active_idx >= len(records):
                self.work_event.clear()
                continue

            # Prioritize targets
            # 0: Active consumer image
            # 1 to 15: Look-ahead images
            targets = []
            targets.append((active_idx, records[active_idx]))
            
            for offset in range(1, 16):
                idx = active_idx + offset
                if idx < len(records):
                    targets.append((idx, records[idx]))

            # Fetch each target in priority order
            for idx, record in targets:
                if self.stop_event.is_set():
                    break

                # Quick check: did active index change since loop start?
                with self.lock:
                    new_active_idx = self.current_index
                if new_active_idx != active_idx:
                    break  # Pivot immediately to new active image

                con_id = record.get("con_id")
                if not con_id:
                    continue

                # Check if already cached
                with self.cache_lock:
                    if con_id in self.image_cache or con_id in self.cache_loading:
                        continue
                    self.cache_loading.add(con_id)

                try:
                    conn_str = record.get("connection_string", [])
                    if conn_str and isinstance(conn_str, list) and "URL" in conn_str[0]:
                        photo_url = conn_str[0]["URL"]
                    else:
                        smrd_val = record.get("smrd", record.get("smrdn", ""))
                        photo_url = self._build_fallback_url(con_id, smrd_val, default_zone)

                    # Check local disk cache
                    import hashlib
                    url_hash = hashlib.md5(photo_url.encode('utf-8')).hexdigest()
                    local_path = os.path.join(IMAGE_CACHE_DIR, f"{url_hash}.jpg")

                    pil_img = None
                    if os.path.exists(local_path):
                        try:
                            with open(local_path, "rb") as f_img:
                                img_bytes = f_img.read()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            pil_img.verify()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        except Exception:
                            try:
                                os.remove(local_path)
                            except Exception:
                                pass
                            pil_img = None

                    if pil_img is None:
                        # Fetch from server
                        img_b64 = self.api_client.fetch_image_base64(username, token, off_code, photo_url)
                        if img_b64:
                            img_bytes = base64.b64decode(img_b64)
                            try:
                                with open(local_path, "wb") as f_img:
                                    f_img.write(img_bytes)
                            except Exception as fe:
                                print(f"Failed to write image to disk cache: {fe}")
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        else:
                            raise Exception("Empty image payload")

                    if pil_img:
                        # Downscale immediately to prevent rendering bottlenecks and save RAM
                        pil_img = self._downscale_image(pil_img, max_size=1024)
                        
                        with self.cache_lock:
                            self.image_cache[con_id] = pil_img
                            if con_id in self.cache_loading:
                                self.cache_loading.remove(con_id)
                        
                        # Notify GUI if this was the active image
                        with self.lock:
                            current_active_con_id = records[self.current_index].get("con_id") if self.current_index < len(records) else None
                        if current_active_con_id == con_id and self.ui_update_callback:
                            self.ui_update_callback(con_id)
                except Exception as e:
                    # If token expired, bubble it up to main UI rather than storing general error
                    if isinstance(e, SessionExpiredException):
                        with self.cache_lock:
                            self.image_cache[con_id] = "error"
                            if con_id in self.cache_loading:
                                self.cache_loading.remove(con_id)
                        if self.ui_update_callback:
                            self.ui_update_callback(con_id)
                        break
                    
                    print(f"Prefetch failed for {con_id}: {e}")
                    with self.cache_lock:
                        self.image_cache[con_id] = "error"
                        if con_id in self.cache_loading:
                            self.cache_loading.remove(con_id)
                    
                    with self.lock:
                        current_active_con_id = records[self.current_index].get("con_id") if self.current_index < len(records) else None
                    if current_active_con_id == con_id and self.ui_update_callback:
                        self.ui_update_callback(con_id)

            # Cleanup older cache items to protect RAM footprint
            with self.lock:
                keep_indices = range(max(0, active_idx - 5), min(len(records), active_idx + 16))
                keep_con_ids = {records[i].get("con_id") for i in keep_indices if records[i].get("con_id")}
            
            with self.cache_lock:
                keys_to_remove = [k for k in self.image_cache if k not in keep_con_ids]
                for k in keys_to_remove:
                    del self.image_cache[k]

            self.work_event.clear()

    def _downscale_image(self, pil_img, max_size=1024):
        try:
            w, h = pil_img.size
            if w > max_size or h > max_size:
                scale = max_size / max(w, h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                return pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        except Exception:
            pass
        return pil_img

    def _build_fallback_url(self, con_id, smrd_val, mru_val):
        smrd_clean = "".join(c for c in str(smrd_val) if c.isdigit())
        if len(smrd_clean) == 8 and smrd_clean.startswith("20"):  # YYYYMMDD
            year = smrd_clean[0:4]
            month = smrd_clean[4:6]
            day = smrd_clean[6:8]
            smrd_formatted = f"{day}{month}{year}"
        else:
            smrd_formatted = smrd_clean
            
        mru_formatted = mru_val
        if mru_val.endswith("PR"):
            mru_formatted = mru_val[:-2] + "MR"
            
        return f"http://10.19.2.6/{smrd_formatted}{mru_formatted}{con_id}.jpeg"


class ActiveQueueFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select_callback, on_toggle_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.on_select_callback = on_select_callback
        self.on_toggle_callback = on_toggle_callback
        self.row_frames = {} # con_id -> tk.Frame
        self.checkbox_vars = {} # con_id -> StringVar
        self.badge_labels = {} # con_id -> tk.Label
        self.selected_con_id = None

    def populate_queue(self, records):
        # Destroy all children first
        for child in self.winfo_children():
            child.destroy()
        self.row_frames.clear()
        self.checkbox_vars.clear()
        self.badge_labels.clear()
        self.selected_con_id = None

        if not records:
            lbl = tk.Label(self, text="Queue Empty. Fetch or load records.", font=("Arial", 10, "italic"), fg="gray", bg="#1a1a24")
            lbl.pack(pady=30)
            return

        for idx, rec in enumerate(records):
            con_id = str(rec.get("con_id"))
            meter_no = rec.get("meter_no", "N/A")
            
            # Row Outer Container (Standard tk Frame for 100x rendering speed)
            row_frm = tk.Frame(self, bg="#1a1a24", bd=0, highlightthickness=0)
            row_frm.pack(fill="x", pady=2, padx=4)
            self.row_frames[con_id] = row_frm

            # Checkbox
            var = tk.StringVar(value="C")
            self.checkbox_vars[con_id] = var
            chk = tk.Checkbutton(
                row_frm, 
                text="", 
                variable=var, 
                onvalue="C", 
                offvalue="IL", 
                command=lambda cid=con_id: self.on_toggle_callback(cid),
                bg="#1a1a24",
                activebackground="#1a1a24",
                selectcolor="#111827",
                fg="white",
                bd=0,
                highlightthickness=0
            )
            chk.pack(side="left", padx=(8, 4))
            
            # ID and Meter Details Frame
            lbl_frm = tk.Frame(row_frm, bg="#1a1a24")
            lbl_frm.pack(side="left", fill="both", expand=True, padx=4)
            
            id_lbl = tk.Label(lbl_frm, text=f"ID: {con_id}", font=("Arial", 10, "bold"), fg="#ffffff", bg="#1a1a24", anchor="w")
            id_lbl.pack(anchor="w", fill="x", pady=(2, 0))
            
            meter_lbl = tk.Label(lbl_frm, text=f"Meter: {meter_no}", font=("Arial", 9), fg="#9ca3af", bg="#1a1a24", anchor="w")
            meter_lbl.pack(anchor="w", fill="x", pady=(0, 2))

            # Status Badge Label
            badge = tk.Label(
                row_frm, 
                text="Approved", 
                bg="#064e3b", 
                fg="#10b981", 
                font=("Arial", 9, "bold"),
                width=10,
                height=1,
                bd=0
            )
            badge.pack(side="right", padx=(4, 8))
            self.badge_labels[con_id] = badge

            # Bind mouse clicks to select row
            for widget in (row_frm, lbl_frm, id_lbl, meter_lbl):
                widget.bind("<Button-1>", lambda e, cid=con_id: self.on_select_callback(cid))
        
    def _set_row_bg(self, con_id_str, bg_color):
        if con_id_str in self.row_frames:
            frm = self.row_frames[con_id_str]
            frm.configure(bg=bg_color)
            for child in frm.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=bg_color)
                    for gchild in child.winfo_children():
                        if isinstance(gchild, (tk.Label, tk.Checkbutton)):
                            gchild.configure(bg=bg_color)
                elif isinstance(child, (tk.Label, tk.Checkbutton)):
                    if child != self.badge_labels.get(con_id_str):
                        child.configure(bg=bg_color)

    def highlight_row(self, con_id):
        con_id_str = str(con_id)
        # Reset old highlight
        if self.selected_con_id and self.selected_con_id in self.row_frames:
            try:
                self._set_row_bg(self.selected_con_id, "#1a1a24")
            except Exception:
                pass
        
        self.selected_con_id = con_id_str
        # Set new highlight
        if con_id_str in self.row_frames:
            try:
                self._set_row_bg(con_id_str, "#2b313e")
                # Automatically scroll view to keep highlighted row visible if possible
                self.row_frames[con_id_str].focus()
            except Exception:
                pass

    def update_status_badge(self, con_id, status):
        con_id_str = str(con_id)
        # Update checkbox var
        if con_id_str in self.checkbox_vars:
            if status == "C":
                self.checkbox_vars[con_id_str].set("C")
            else:
                self.checkbox_vars[con_id_str].set(status) # offvalue

        # Update badge colors and text
        if con_id_str in self.badge_labels:
            lbl = self.badge_labels[con_id_str]
            if status == "C":
                lbl.configure(
                    text="Approved", 
                    bg="#064e3b", 
                    fg="#10b981"
                )
            elif status == "IL":
                lbl.configure(
                    text="Illegible", 
                    bg="#78350f", 
                    fg="#fbbf24"
                )
            elif status == "MM":
                lbl.configure(
                    text="Diff Meter", 
                    bg="#7f1d1d", 
                    fg="#f87171"
                )
            elif status == "LM":
                lbl.configure(
                    text="Diff Loc", 
                    bg="#581c87", 
                    fg="#c084fc"
                )
            elif status == "NMI":
                lbl.configure(
                    text="Non Meter", 
                    bg="#374151", 
                    fg="#9ca3af"
                )
            elif status == "I":
                lbl.configure(
                    text="Mismatch", 
                    bg="#1e3a8a", 
                    fg="#60a5fa"
                )


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_login_success):
        super().__init__(parent, fg_color="#121316")
        self.parent = parent
        self.on_login_success = on_login_success
        self.api_client = parent.api_client if hasattr(parent, 'api_client') else parent.master.api_client

        self.username = ""
        self.password = ""
        self.countdown_val = 60
        self.countdown_active = False

        # Card container (centered)
        self.card = ctk.CTkFrame(self, fg_color="#1f2022", corner_radius=16, border_width=1, border_color="gray30", width=420, height=480)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.grid_propagate(False)
        self.card.grid_columnconfigure(0, weight=1)
        
        self.logo_lbl = ctk.CTkLabel(self.card, text="⚡", font=ctk.CTkFont(size=44))
        self.logo_lbl.grid(row=0, column=0, pady=(24, 0))

        self.title_lbl = ctk.CTkLabel(self.card, text="WBSedcl Meter Verification", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_lbl.grid(row=1, column=0, pady=(5, 2))

        self.subtitle_lbl = ctk.CTkLabel(self.card, text="Spot Reading Portal Auditor", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray60")
        self.subtitle_lbl.grid(row=2, column=0, pady=(0, 20))

        # Credentials View Frame
        self.cred_frm = ctk.CTkFrame(self.card, fg_color="transparent")
        self.cred_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.cred_frm.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.cred_frm, text="ERP ID (Username)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.user_ent = ctk.CTkEntry(self.cred_frm, placeholder_text="Enter 8-digit ERP ID", height=36)
        self.user_ent.pack(fill="x", pady=(0, 10))
        self.user_ent.bind("<Return>", lambda e: self.action_send_otp())

        ctk.CTkLabel(self.cred_frm, text="Password", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.pass_ent = ctk.CTkEntry(self.cred_frm, placeholder_text="Enter Portal Password", show="*", height=36)
        self.pass_ent.pack(fill="x", pady=(0, 20))
        self.pass_ent.bind("<Return>", lambda e: self.action_send_otp())

        self.send_otp_btn = ctk.CTkButton(self.cred_frm, text="Send OTP", height=38, font=ctk.CTkFont(size=13, weight="bold"), command=self.action_send_otp)
        self.send_otp_btn.pack(fill="x")

        # OTP Verification Frame (Initially Hidden)
        self.otp_frm = ctk.CTkFrame(self.card, fg_color="transparent")
        self.otp_frm.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.otp_frm, text="OTP Code", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.otp_ent = ctk.CTkEntry(self.otp_frm, placeholder_text="Enter OTP code", height=36, justify="center", font=ctk.CTkFont(size=16, weight="bold"))
        self.otp_ent.pack(fill="x", pady=(0, 15))
        self.otp_ent.bind("<Return>", lambda e: self.action_verify_otp())

        self.verify_otp_btn = ctk.CTkButton(self.otp_frm, text="Verify OTP", height=38, font=ctk.CTkFont(size=13, weight="bold"), command=self.action_verify_otp)
        self.verify_otp_btn.pack(fill="x", pady=(0, 10))

        timer_row = ctk.CTkFrame(self.otp_frm, fg_color="transparent")
        timer_row.pack(fill="x", pady=(5, 0))
        
        self.timer_lbl = ctk.CTkLabel(timer_row, text="Resend OTP in 60s", font=ctk.CTkFont(size=11), text_color="gray60")
        self.timer_lbl.pack(side="left")

        self.resend_btn = ctk.CTkButton(timer_row, text="Resend OTP", width=80, height=22, font=ctk.CTkFont(size=11), state="disabled", fg_color="transparent", text_color="gray50", command=self.action_resend_otp)
        self.resend_btn.pack(side="right")

        self.back_btn = ctk.CTkButton(self.otp_frm, text="← Back to Login", width=120, height=24, fg_color="transparent", text_color="gray60", command=self.action_back_to_login)
        self.back_btn.pack(pady=(15, 0))

        # Status Message
        self.status_lbl = ctk.CTkLabel(self.card, text="", font=ctk.CTkFont(size=12), wraplength=340)
        self.status_lbl.grid(row=4, column=0, pady=(15, 10), padx=30, sticky="ew")

    def set_status(self, text, is_error=True):
        color = "#ef4444" if is_error else "#10b981"
        self.status_lbl.configure(text=text, text_color=color)

    def action_send_otp(self):
        username = self.user_ent.get().strip()
        password = self.pass_ent.get().strip()

        if not username or not password:
            self.set_status("ERP ID and Password are required.")
            return

        if not username.isdigit() or len(username) != 8:
            self.set_status("ERP ID must be an 8-digit number.")
            return

        self.send_otp_btn.configure(state="disabled", text="Sending OTP...")
        self.set_status("Requesting OTP...", is_error=False)

        def task():
            try:
                res = self.api_client.submit_for_otp(username, password)
                code = res.get("code")
                msg = res.get("message", "OTP sent successfully")
                if code == "200":
                    self.username = username
                    self.password = password
                    self.after(0, self.show_otp_view)
                else:
                    self.after(0, lambda: self.send_otp_btn.configure(state="normal", text="Send OTP"))
                    self.after(0, lambda: self.set_status(f"Error {code}: {msg}"))
            except Exception as e:
                self.after(0, lambda: self.send_otp_btn.configure(state="normal", text="Send OTP"))
                self.after(0, lambda: self.set_status(f"Error: {str(e)}"))

        threading.Thread(target=task, daemon=True).start()

    def show_otp_view(self):
        self.cred_frm.grid_forget()
        self.otp_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.set_status("OTP sent successfully.", is_error=False)
        self.start_timer()

    def action_back_to_login(self):
        self.stop_timer()
        self.otp_frm.grid_forget()
        self.cred_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.set_status("")
        self.send_otp_btn.configure(state="normal", text="Send OTP")

    def start_timer(self):
        self.countdown_val = 60
        self.countdown_active = True
        self.resend_btn.configure(state="disabled", text_color="gray50")
        self.timer_lbl.configure(text=f"Resend OTP in {self.countdown_val}s", text_color="gray60")
        self.update_timer()

    def stop_timer(self):
        self.countdown_active = False

    def update_timer(self):
        if not self.countdown_active:
            return
        if self.countdown_val > 0:
            self.countdown_val -= 1
            self.timer_lbl.configure(text=f"Resend OTP in {self.countdown_val}s")
            self.after(1000, self.update_timer)
        else:
            self.timer_lbl.configure(text="Didn't receive OTP?", text_color="gray80")
            self.resend_btn.configure(state="normal", text_color="#3b82f6")

    def action_resend_otp(self):
        self.resend_btn.configure(state="disabled")
        self.set_status("Resending OTP...", is_error=False)
        def task():
            try:
                res = self.api_client.submit_for_otp(self.username, self.password)
                code = res.get("code")
                msg = res.get("message", "OTP resent successfully")
                if code == "200":
                    self.after(0, lambda: self.set_status("OTP resent successfully.", is_error=False))
                    self.after(0, self.start_timer)
                else:
                    self.after(0, lambda: self.set_status(f"Error resending: {msg}"))
                    self.after(0, lambda: self.resend_btn.configure(state="normal"))
            except Exception as e:
                self.after(0, lambda: self.set_status(f"Error resending: {str(e)}"))
                self.after(0, lambda: self.resend_btn.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def action_verify_otp(self):
        otp = self.otp_ent.get().strip()
        if not otp:
            self.set_status("OTP code is required.")
            return

        self.verify_otp_btn.configure(state="disabled", text="Verifying...")
        self.set_status("Verifying OTP...", is_error=False)

        def task():
            try:
                res = self.api_client.submit_final_otp(self.username, otp)
                code = res.get("code")
                if code == "200":
                    msg_body = res.get("message", {})
                    jwt_token = msg_body.get("JWT_token")
                    off_code = msg_body.get("off_code")
                    off_name = msg_body.get("off_name")
                    name = msg_body.get("name", "N/A")
                    desg = msg_body.get("designation", "N/A")

                    self.after(0, lambda: self.on_login_success(
                        self.username, jwt_token, off_code, off_name, name, desg
                    ))
                else:
                    msg = res.get("message", "Incorrect OTP code.")
                    self.after(0, lambda: self.verify_otp_btn.configure(state="normal", text="Verify OTP"))
                    self.after(0, lambda: self.set_status(f"Error {code}: {msg}"))
            except Exception as e:
                self.after(0, lambda: self.verify_otp_btn.configure(state="normal", text="Verify OTP"))
                self.after(0, lambda: self.set_status(f"Error: {str(e)}"))

        threading.Thread(target=task, daemon=True).start()


class MeterAuditApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WBSedcl Meter Image Verification Audit Tool")
        self.geometry("1280x780")
        self.minimum_size = (1100, 700)
        
        # State Management
        self.api_client = TomcatAPIClient(DEFAULT_BASE_URL)
        self.prefetcher = ImagePrefetcher(self.api_client)
        self.prefetcher.ui_update_callback = self.on_image_prefetch_done

        # Session properties
        self.session_username = ""
        self.session_token = ""
        self.session_off_code = ""
        self.session_off_name = ""
        self.session_name = ""
        self.session_designation = ""

        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {} # con_id -> {"verification_stat": status, "meter_note": note}
        self.is_committing = False
        self.audited_ids = set()
        self.telemetry_labels = {}
        self.keep_alive_active = False
        self.keep_alive_thread = None

        # Zones persistent cache
        self.zones_cache_file = os.path.join(LOG_DIR, "zones_cache.json")
        self.zones_cache = self.load_zones_cache()

        # Clear local progress file on startup/app restart to prevent stale carry-over
        try:
            startup_progress_path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(startup_progress_path):
                os.remove(startup_progress_path)
        except Exception as e:
            logging.error(f"Failed to clear local progress on startup: {e}")

        # Load cascade choices on startup asynchronously
        self.smrd_choices = []
        self.mru_choices = []

        # Unified container frame to prevent pack/grid manager conflicts on root
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Show Login Frame
        self.show_login_screen()

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

    def show_login_screen(self):
        self.login_frame = LoginFrame(self.main_container, self.on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def on_login_success(self, username, token, off_code, off_name, name, designation):
        self.session_username = username
        self.session_token = token
        self.session_off_code = off_code
        self.session_off_name = off_name
        self.session_name = name
        self.session_designation = designation

        self.login_frame.pack_forget()
        self.login_frame.destroy()

        # Update Prefetcher configuration
        self.prefetcher.update_config(username, token, off_code)

        # Setup layout and bind hotkeys
        self._setup_layout()
        self._bind_hotkeys()

        # Start keep-alive timer
        self.start_keep_alive_timer()

        # Fetch MRUs automatically
        self.fetch_cascade_mru()

    def logout(self):
        self.stop_keep_alive_timer()
        self.session_username = ""
        self.session_token = ""
        self.session_off_code = ""
        self.session_off_name = ""
        self.session_name = ""
        self.session_designation = ""

        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {}
        self.audited_ids = set()

        # Clear prefetch queue
        self.prefetcher.set_queue([], "", "")
        self.prefetcher.update_config("", "", "")

        # Destroy everything inside the main container to wipe out all grid layouts and configurations
        self.main_container.pack_forget()
        self.main_container.destroy()

        # Re-create a fresh container frame for packing the login frame
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.show_login_screen()

    def handle_api_error(self, e):
        if isinstance(e, SessionExpiredException):
            def show_warning_logout():
                messagebox.showwarning("Session Expired", "Your backend Tomcat session has expired or is invalid (Code 100/600).\nRedirecting to login...")
                self.logout()
            self.after(0, show_warning_logout)
            return True
        return False

    def start_keep_alive_timer(self):
        self.stop_keep_alive_timer()
        self.keep_alive_active = True
        self.keep_alive_thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self.keep_alive_thread.start()
        self.log_to_console("Session keep-alive ping worker started.")

    def stop_keep_alive_timer(self):
        self.keep_alive_active = False

    def _keep_alive_loop(self):
        while self.keep_alive_active:
            # Sleep 300 seconds (5 minutes) in small steps to react quickly to shutdown
            for _ in range(300):
                if not self.keep_alive_active:
                    return
                time.sleep(1)
            
            if not self.session_username or not self.session_token:
                continue
                
            try:
                logging.info("Sending session keep-alive ping to Tomcat server...")
                self.api_client.verify_token(self.session_username, self.session_token)
                self.after(0, lambda: self.update_status_bar("Keep-alive ping sent to Tomcat server successfully.", "gray60"))
            except Exception as e:
                logging.warning(f"Session keep-alive ping failed: {e}")
                self.after(0, lambda msg=str(e): self.update_status_bar(f"Keep-alive ping failed: {msg}", "#ef4444"))

    def save_local_progress(self):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            saved_decisions = {}
            for cid in self.audited_ids:
                if cid in self.audit_decisions:
                    saved_decisions[cid] = self.audit_decisions[cid]
            
            payload = {
                "mru": self.mru_combo.get(),
                "month": self.month_combo.get(),
                "year": self.year_combo.get(),
                "decisions": saved_decisions
            }
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save local progress: {e}")

    def load_local_progress(self):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    payload = json.load(f)
                
                if isinstance(payload, dict) and "decisions" in payload:
                    file_mru = payload.get("mru")
                    file_month = payload.get("month")
                    file_year = payload.get("year")
                    
                    cur_mru = self.mru_combo.get()
                    cur_month = self.month_combo.get()
                    cur_year = self.year_combo.get()
                    
                    # Verify metadata match
                    if file_mru == cur_mru and file_month == cur_month and file_year == cur_year:
                        saved = payload["decisions"]
                        count = 0
                        for con_id, decision in saved.items():
                            con_id_str = str(con_id)
                            if con_id_str in self.audit_decisions:
                                self.audit_decisions[con_id_str] = decision
                                self.audited_ids.add(con_id_str)
                                self.queue_frame.update_status_badge(con_id_str, decision.get("verification_stat", "C"))
                                count += 1
                        if count > 0:
                            self.log_to_console(f"Restored {count} decisions from local progress.")
                            self.update_stats_dashboard()
                    else:
                        # Clear file if it's for a different zone or parameters
                        self.log_to_console("Local progress is for a different zone/period. Clearing progress file.")
                        try:
                            os.remove(path)
                        except Exception:
                            pass
        except Exception as e:
            logging.error(f"Failed to load local progress: {e}")

    def remove_from_local_progress(self, con_id):
        try:
            con_id_str = str(con_id)
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    payload = json.load(f)
                if isinstance(payload, dict) and "decisions" in payload:
                    if con_id_str in payload["decisions"]:
                        del payload["decisions"][con_id_str]
                        with open(path, "w") as f:
                            json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to remove {con_id} from local progress: {e}")

    def _setup_layout(self):
        # Configure Grid Rows and Columns on main_container
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=0) # Bottom status bar row
        self.main_container.grid_columnconfigure(0, weight=0, minsize=450) # Left panel width
        self.main_container.grid_columnconfigure(1, weight=1)              # Right panel takes remaining

        # ----------------------------------------------------
        # LEFT PANEL: Interactive Workspace
        # ----------------------------------------------------
        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="#1a1a24", corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        # Left Panel Subgrid layout
        self.left_panel.grid_rowconfigure(2, weight=1) # Queue table takes extra space
        self.left_panel.grid_columnconfigure(0, weight=1)

        # 1. User Profile Status Card
        self.profile_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.profile_frm.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        
        profile_title = ctk.CTkLabel(self.profile_frm, text="User Session Profile", font=ctk.CTkFont(size=13, weight="bold"))
        profile_title.pack(anchor="w", padx=10, pady=(8, 2))

        prof_row = ctk.CTkFrame(self.profile_frm, fg_color="transparent")
        prof_row.pack(fill="x", padx=10, pady=(2, 8))

        profile_details = f"Name: {self.session_name} ({self.session_username})\nDesg: {self.session_designation}\nOffice: {self.session_off_name} ({self.session_off_code})"
        self.profile_info_lbl = ctk.CTkLabel(prof_row, text=profile_details, font=ctk.CTkFont(size=11), justify="left", anchor="w")
        self.profile_info_lbl.pack(side="left", padx=5)

        self.logout_btn = ctk.CTkButton(prof_row, text="Logout", height=24, width=60, fg_color="#ef4444", hover_color="#dc2626", font=ctk.CTkFont(size=11, weight="bold"), command=self.logout)
        self.logout_btn.pack(side="right", padx=5, anchor="e")

        # 2. Selector Cascade Card (Unified Top Filters & Action Row)
        self.selector_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.selector_frm.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        self.selector_frm.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Row 0: Labels
        ctk.CTkLabel(self.selector_frm, text="Month", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=0, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="Year", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=1, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="AI Flag Filter", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=2, padx=6, pady=(6, 0), sticky="w")
        
        mru_lbl_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        mru_lbl_frm.grid(row=0, column=3, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(mru_lbl_frm, text="MRU (Zone)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(side="left")
        self.mru_spinner_lbl = ctk.CTkLabel(mru_lbl_frm, text="", font=ctk.CTkFont(size=10, slant="italic"), text_color="#10b981")
        self.mru_spinner_lbl.pack(side="left", padx=4)

        # Row 1: Option Menus
        self.month_combo = ctk.CTkOptionMenu(self.selector_frm, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.month_combo.set("04")
        self.month_combo.grid(row=1, column=0, padx=4, pady=(2, 6), sticky="ew")

        self.year_combo = ctk.CTkOptionMenu(self.selector_frm, values=["2025", "2026", "2027", "2028"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.year_combo.set("2026")
        self.year_combo.grid(row=1, column=1, padx=4, pady=(2, 6), sticky="ew")

        ai_options = [
            "Accepted by Reader",
            "Not Accepted by Reader",
            "No Reading from AI Engine",
            "Not under AI Scope"
        ]
        self.aiflag_combo = ctk.CTkOptionMenu(self.selector_frm, values=ai_options, height=26, font=ctk.CTkFont(size=11))
        self.aiflag_combo.set("Accepted by Reader")
        self.aiflag_combo.grid(row=1, column=2, padx=4, pady=(2, 6), sticky="ew")

        self.mru_combo = ctk.CTkOptionMenu(self.selector_frm, values=["None"], height=26, font=ctk.CTkFont(size=11))
        self.mru_combo.set("None")
        self.mru_combo.grid(row=1, column=3, padx=4, pady=(2, 6), sticky="ew")

        # Row 2: Slider & Actions
        slider_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        slider_frm.grid(row=2, column=0, columnspan=2, padx=4, pady=(2, 8), sticky="ew")
        
        self.pacing_lbl = ctk.CTkLabel(slider_frm, text="Pacing: 0.4s", font=ctk.CTkFont(size=10))
        self.pacing_lbl.pack(side="left", padx=(2, 4))
        
        self.pacing_slider = ctk.CTkSlider(slider_frm, from_=0.1, to=2.0, number_of_steps=19, height=14, command=self.on_pacing_change)
        self.pacing_slider.set(0.4)
        self.pacing_slider.pack(side="left", fill="x", expand=True)

        self.fetch_queue_btn = ctk.CTkButton(
            self.selector_frm, 
            text="Fetch Queue", 
            height=26, 
            fg_color="#2563eb", 
            hover_color="#1d4ed8", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            command=self.fetch_server_queue
        )
        self.fetch_queue_btn.grid(row=2, column=2, padx=4, pady=(2, 8), sticky="ew")

        self.commit_btn = ctk.CTkButton(
            self.selector_frm, 
            text="Commit Batch", 
            height=26, 
            fg_color="#10b981", 
            hover_color="#059669", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            command=self.start_batch_commit
        )
        self.commit_btn.grid(row=2, column=3, padx=4, pady=(2, 8), sticky="ew")

        # 3. Active Queue Table Container
        self.table_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.table_frm.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        self.table_frm.grid_rowconfigure(1, weight=1)
        self.table_frm.grid_columnconfigure(0, weight=1)

        # Table Header
        tbl_hdr = ctk.CTkFrame(self.table_frm, fg_color="transparent")
        tbl_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        
        self.queue_title = ctk.CTkLabel(tbl_hdr, text="Audit Queue list (0 records)", font=ctk.CTkFont(size=13, weight="bold"))
        self.queue_title.pack(side="left", pady=2)

        # Active Queue Scrollable List Frame
        self.queue_frame = ActiveQueueFrame(
            self.table_frm, 
            on_select_callback=self.select_consumer_by_id,
            on_toggle_callback=self.on_row_checkbox_toggled,
            fg_color="#1a1a24"
        )
        self.queue_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # 4. Audit Progress & Statistics Dashboard (Replaces bottom logs/commit card)
        self.stats_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.stats_frm.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
        
        self.stats_progress_lbl = ctk.CTkLabel(self.stats_frm, text="Progress: 0 / 0 (0%)", font=ctk.CTkFont(size=12, weight="bold"))
        self.stats_progress_lbl.pack(anchor="w", padx=12, pady=(8, 2))
        
        self.progress_bar = ctk.CTkProgressBar(self.stats_frm)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 8))
        
        grid_frm = ctk.CTkFrame(self.stats_frm, fg_color="transparent")
        grid_frm.pack(fill="x", padx=12, pady=(2, 8))
        grid_frm.columnconfigure((0, 1, 2), weight=1)
        
        # Correct Stat Panel
        c_frm = ctk.CTkFrame(grid_frm, fg_color="#182721", height=55, corner_radius=6)
        c_frm.grid(row=0, column=0, padx=4, sticky="nsew")
        c_frm.grid_propagate(False)
        c_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(c_frm, text="Correct (C)", font=ctk.CTkFont(size=10), text_color="#a7f3d0").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_correct = ctk.CTkLabel(c_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10b981")
        self.lbl_stat_correct.grid(row=1, column=0)
        
        # Illegible Stat Panel
        il_frm = ctk.CTkFrame(grid_frm, fg_color="#2d2217", height=55, corner_radius=6)
        il_frm.grid(row=0, column=1, padx=4, sticky="nsew")
        il_frm.grid_propagate(False)
        il_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(il_frm, text="Illegible (IL)", font=ctk.CTkFont(size=10), text_color="#fde68a").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_illegible = ctk.CTkLabel(il_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#fbbf24")
        self.lbl_stat_illegible.grid(row=1, column=0)
        
        # Other Defects Stat Panel
        o_frm = ctk.CTkFrame(grid_frm, fg_color="#1e2433", height=55, corner_radius=6)
        o_frm.grid(row=0, column=2, padx=4, sticky="nsew")
        o_frm.grid_propagate(False)
        o_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(o_frm, text="Other Defects", font=ctk.CTkFont(size=10), text_color="#dbeafe").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_other = ctk.CTkLabel(o_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#60a5fa")
        self.lbl_stat_other.grid(row=1, column=0)

        # ----------------------------------------------------
        # RIGHT PANEL: Rapid-Fire Audit Viewer
        # ----------------------------------------------------
        self.right_panel = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        
        self.right_panel.grid_rowconfigure(0, weight=1) # Image container takes maximum space
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Main vertical container in right panel
        self.viewer_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.viewer_container.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        
        self.viewer_container.grid_rowconfigure(0, weight=1) # Image container
        self.viewer_container.grid_rowconfigure(1, weight=0) # Telemetry & Hotkeys
        self.viewer_container.grid_columnconfigure(0, weight=1)

        # 1. Image Container Frame
        self.image_outer_frm = ctk.CTkFrame(self.viewer_container, fg_color="#1f2937", border_width=1, border_color="gray30", corner_radius=10)
        self.image_outer_frm.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self.image_outer_frm.bind("<Configure>", self.on_image_container_resize)

        self.img_lbl = ctk.CTkLabel(self.image_outer_frm, text="Fetch and select a consumer to display meter image.", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray60")
        self.img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Semi-transparent HUD overlay on image container
        self.image_hud = ctk.CTkFrame(self.image_outer_frm, fg_color="#111827", corner_radius=6)
        self.hud_meter_lbl = ctk.CTkLabel(self.image_hud, text="Meter: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        self.hud_meter_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_pres_lbl = ctk.CTkLabel(self.image_hud, text="Present Reading: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10b981")
        self.hud_pres_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_mrnote_lbl = ctk.CTkLabel(self.image_hud, text="MR Note: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f59e0b")
        self.hud_mrnote_lbl.pack(side="left", expand=True, padx=12, pady=6)

        # 2. Telemetry and Hotkeys Split Row
        self.telemetry_hotkey_frm = ctk.CTkFrame(self.viewer_container, fg_color="transparent")
        self.telemetry_hotkey_frm.grid(row=1, column=0, sticky="ew")
        self.telemetry_hotkey_frm.grid_columnconfigure(0, weight=3)
        self.telemetry_hotkey_frm.grid_columnconfigure(1, weight=2)

        # 2a. Telemetry Card
        self.tel_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.tel_frm.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        tel_title = ctk.CTkLabel(self.tel_frm, text="Meter & Consumer Telemetry", font=ctk.CTkFont(size=13, weight="bold"))
        tel_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 4))

        # Metadata grid fields
        self.telemetry_labels = {}
        fields = [
            ("Consumer ID:", "N/A"), ("Meter No:", "N/A"),
            ("CCC Name:", "N/A"), ("CCC Code:", "N/A"),
            ("Prev Reading:", "N/A"), ("Pres Reading:", "N/A"),
            ("Consumption:", "N/A"), ("Upload Date:", "N/A"),
            ("MR Note:", "N/A"), ("AI Flag:", "N/A")
        ]
        
        for idx, (label_txt, val_txt) in enumerate(fields):
            r = (idx // 2) + 1
            c_label = (idx % 2) * 2
            c_val = c_label + 1
            
            lbl = ctk.CTkLabel(self.tel_frm, text=label_txt, font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70")
            lbl.grid(row=r, column=c_label, sticky="e", padx=(12, 4), pady=2)
            
            val = ctk.CTkLabel(self.tel_frm, text=val_txt, font=ctk.CTkFont(size=11), anchor="w")
            val.grid(row=r, column=c_val, sticky="w", padx=(4, 12), pady=2)
            self.telemetry_labels[label_txt] = val

        self.btn_view_details = ctk.CTkButton(
            self.tel_frm, 
            text="🔍 View Consumer Details", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            height=24, 
            fg_color="gray30", 
            hover_color="gray40", 
            command=self.open_consumer_details_popup
        )
        self.btn_view_details.grid(row=6, column=0, columnspan=4, pady=(6, 8), padx=12, sticky="ew")

        # 2b. Hotkey Quick-Action Bar
        self.hotkey_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.hotkey_frm.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        hk_title = ctk.CTkLabel(self.hotkey_frm, text="Rapid-Fire Audit Decisions", font=ctk.CTkFont(size=13, weight="bold"))
        hk_title.pack(anchor="w", padx=12, pady=(8, 4))

        hk_btn_frm = ctk.CTkFrame(self.hotkey_frm, fg_color="transparent")
        hk_btn_frm.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        
        self.btn_correct = ctk.CTkButton(
            hk_btn_frm, 
            text="✅ Meter Image Correct (C)", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color="#064e3b", 
            hover_color="#065f46", 
            height=32, 
            command=lambda: self.set_status("C")
        )
        self.btn_correct.pack(fill="x", pady=2)

        self.btn_illegible = ctk.CTkButton(
            hk_btn_frm, 
            text="⚠️ Illegible Image (IL)", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color="#78350f", 
            hover_color="#92400e", 
            height=32, 
            command=lambda: self.set_status("IL")
        )
        self.btn_illegible.pack(fill="x", pady=2)

        other_obs = [
            "Select Other Observations...",
            "Different Meter No (MM)",
            "Location Difference (LM)",
            "Non Meter Image (NMI)",
            "Mismatch Reading (I)"
        ]
        self.combo_other_obs = ctk.CTkOptionMenu(
            hk_btn_frm, 
            values=other_obs, 
            height=30, 
            font=ctk.CTkFont(size=11),
            command=self.on_other_obs_selected
        )
        self.combo_other_obs.set("Select Other Observations...")
        self.combo_other_obs.pack(fill="x", pady=4)

        # Bottom Status Bar Frame
        self.status_bar = ctk.CTkFrame(self.main_container, fg_color="#0f1115", height=24, corner_radius=0)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        self.status_lbl = ctk.CTkLabel(self.status_bar, text="Status: Idle", font=ctk.CTkFont(size=11), text_color="gray70")
        self.status_lbl.pack(side="left", padx=12, pady=2)

    def log_to_console(self, msg):
        logging.info(msg)
        print(msg)
        clean_msg = str(msg).replace("──►", "->").replace("🚀", "").replace("⚡", "").strip()
        if len(clean_msg) > 90:
            clean_msg = clean_msg[:87] + "..."
        self.update_status_bar(clean_msg)

    def update_status_bar(self, text, color="gray70"):
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            self.status_lbl.configure(text=f"Status: {text}", text_color=color)

    def on_pacing_change(self, val):
        self.pacing_lbl.configure(text=f"Pacing Interval: {float(val):.1f}s")

    def is_input_focused(self):
        focused = self.focus_get()
        if not focused:
            return False
        # If the focused widget is a text entry, ignore hotkeys
        cls_name = focused.winfo_class()
        # customtkinter entry has a child entry or is CTkEntry
        if "Entry" in cls_name or "Text" in cls_name:
            return True
        return False

    def _bind_hotkeys(self):
        # Keyboard triggers for the 6 choices
        self.bind("<F1>", lambda e: not self.is_input_focused() and self.set_status("C"))
        self.bind("c", lambda e: not self.is_input_focused() and self.set_status("C"))
        self.bind("C", lambda e: not self.is_input_focused() and self.set_status("C"))

        self.bind("<F2>", lambda e: not self.is_input_focused() and self.set_status("IL"))
        self.bind("i", lambda e: not self.is_input_focused() and self.set_status("IL"))
        self.bind("I", lambda e: not self.is_input_focused() and self.set_status("IL"))

        self.bind("<F3>", lambda e: not self.is_input_focused() and self.set_status("MM"))
        self.bind("<F4>", lambda e: not self.is_input_focused() and self.set_status("LM"))
        self.bind("<F5>", lambda e: not self.is_input_focused() and self.set_status("NMI"))
        self.bind("<F6>", lambda e: not self.is_input_focused() and self.set_status("I"))

        self.bind("<Down>", lambda e: not self.is_input_focused() and self.next_consumer())
        self.bind("<Up>", lambda e: not self.is_input_focused() and self.prev_consumer())

    # ----------------------------------------------------
    # EVENT HANDLERS & FLOW CONTROL
    # ----------------------------------------------------
    
    def on_cascade_change(self, val):
        self.fetch_cascade_mru()

    def fetch_cascade_mru(self):
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        month = self.month_combo.get()
        year = self.year_combo.get()

        cache_key = f"{off_code}_{month}_{year}"
        if cache_key in self.zones_cache:
            mrus = self.zones_cache[cache_key]
            self.log_to_console(f"Using cached zones/MRUs for {month}/{year}")
            self._update_mru_dropdown(mrus)
            return

        # Update indicators to "Loading..."
        self.mru_combo.configure(values=["Loading..."])
        self.mru_combo.set("Loading...")
        self.mru_spinner_lbl.configure(text="⏳ Fetching...")

        def fetch_task():
            try:
                mrus = self.api_client.fetch_mru(username, token, off_code, month, year)
                if mrus:
                    self.zones_cache[cache_key] = mrus
                    self.save_zones_cache()
                    self.after(0, lambda: self._update_mru_dropdown(mrus))
                else:
                    self.after(0, lambda: self._update_mru_dropdown([]))
            except Exception as e:
                print(f"Failed to fetch MRUs: {e}")
                self.after(0, lambda: self._update_mru_dropdown([]))

        threading.Thread(target=fetch_task, daemon=True).start()

    def _update_mru_dropdown(self, mrus):
        self.mru_spinner_lbl.configure(text="")
        self.mru_choices = mrus
        if mrus:
            self.mru_combo.configure(values=mrus)
            cur = self.mru_combo.get()
            if cur not in mrus:
                self.mru_combo.set(mrus[0])
        else:
            self.mru_combo.configure(values=["None"])
            self.mru_combo.set("None")

    def fetch_server_queue(self):
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        month = self.month_combo.get()
        year = self.year_combo.get()
        mru = self.mru_combo.get()
        ai_flag = self.aiflag_combo.get()

        if mru == "None" or not mru:
            messagebox.showwarning("Validation Error", "Please select a valid MRU (Zone) code first.")
            return

        self.fetch_queue_btn.configure(state="disabled", text="Fetching...")
        
        def fetch_task():
            try:
                records = self.api_client.fetch_queue(username, token, off_code, month, year, mru, ai_flag)
                self.after(0, lambda: self.load_records_into_memory(records, source="Server"))
            except Exception as e:
                self.after(0, lambda e_str=str(e): messagebox.showerror("Queue Fetch Error", f"Could not retrieve queue:\n{e_str}"))
                self.after(0, lambda: self.fetch_queue_btn.configure(state="normal", text="Fetch Server Queue"))

        threading.Thread(target=fetch_task, daemon=True).start()

    def load_queue_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Queue JSON File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            records = []
            if isinstance(data, list):
                # If it's a simple list of consumer IDs, map them into a list of dicts
                for item in data:
                    if isinstance(item, dict):
                        records.append(item)
                    else:
                        # Consumer ID string
                        records.append({
                            "con_id": str(item),
                            "meter_no": "Unknown",
                            "smrd": self.month_combo.get(),
                            "ccc_code": self.session_off_code,
                            "ccc_name": "KUSHIDA CCC" # Default fallback
                        })
            else:
                raise Exception("JSON root must be a list of records or consumer IDs.")

            self.load_records_into_memory(records, source=f"File ({os.path.basename(file_path)})")
        except Exception as e:
            messagebox.showerror("File Error", f"Could not parse selected file:\n{str(e)}")

    def load_records_into_memory(self, records, source=""):
        self.queue_records = records
        if records:
            logging.info(f"Sample record payload keys & data: {json.dumps(records[0])}")
        self.current_index = -1
        self.audit_decisions.clear()
        self.audited_ids = set()

        # Initialize default decision state for all records to Approved "C"
        for rec in records:
            con_id = rec.get("con_id")
            if con_id:
                self.audit_decisions[str(con_id)] = {
                    "verification_stat": "C",
                    "meter_note": " "
                }

        self.queue_title.configure(text=f"Audit Queue list ({len(records)} records)")
        self.log_to_console(f"Loaded {len(records)} records in-memory from {source}.")

        # Populate GUI Table list
        self.queue_frame.populate_queue(records)

        # Restore local progress
        self.load_local_progress()

        # Enable Commit and Fetch buttons
        self.fetch_queue_btn.configure(state="normal", text="Fetch Queue")
        self.progress_bar.set(0)
        self.update_stats_dashboard()

        # Select first consumer
        if records:
            first_con_id = records[0].get("con_id")
            self.select_consumer_by_id(first_con_id)
            
            # Setup prefetcher
            self.prefetcher.set_queue(
                records,
                default_smrd="",
                default_zone=self.mru_combo.get()
            )
        else:
            self._clear_viewer()

    def select_consumer_by_id(self, con_id):
        idx = next((i for i, r in enumerate(self.queue_records) if r.get("con_id") == con_id), -1)
        if idx == -1:
            return

        self.current_index = idx
        self.queue_frame.highlight_row(con_id)
        self.prefetcher.set_active_index(idx)
        
        # Display image (instantly if cached, else load)
        self.update_active_image()
        # Update telemetry panel
        self.update_active_telemetry()

    def update_active_image(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            self._clear_viewer()
            return

        record = self.queue_records[self.current_index]
        con_id = record.get("con_id")
        
        # Clear old image and show loading placeholder instantly
        self.img_lbl.configure(image="", text="⏳ Loading image...")
        self.img_lbl.image = None
        
        # Retrieve from cache
        cached_img = self.prefetcher.get_image(con_id)
        
        if cached_img == "error":
            self.img_lbl.configure(image=None, text="Error fetching meter image from server.")
        elif cached_img is None:
            # Not in cache yet, start fetching inline
            self.img_lbl.configure(image=None, text="Prefetching image... Please wait.")
            # Trigger prefetch check immediately
            self.prefetcher.trigger_prefetch()
            
            # Fetch explicitly if background didn't finish
            def fetch_inline_task():
                try:
                    conn_str = record.get("connection_string", [])
                    if conn_str and isinstance(conn_str, list) and "URL" in conn_str[0]:
                        photo_url = conn_str[0]["URL"]
                    else:
                        photo_url = self.prefetcher._build_fallback_url(
                            con_id, 
                            record.get("smrd", record.get("smrdn", "")), 
                            self.mru_combo.get()
                        )
                    
                    # Check local disk cache
                    import hashlib
                    url_hash = hashlib.md5(photo_url.encode('utf-8')).hexdigest()
                    local_path = os.path.join(IMAGE_CACHE_DIR, f"{url_hash}.jpg")

                    pil_img = None
                    if os.path.exists(local_path):
                        try:
                            with open(local_path, "rb") as f_img:
                                img_bytes = f_img.read()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            pil_img.verify()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        except Exception:
                            try:
                                os.remove(local_path)
                            except Exception:
                                pass
                            pil_img = None

                    if pil_img is None:
                        username = self.session_username
                        token = self.session_token
                        off_code = self.session_off_code

                        img_b64 = self.api_client.fetch_image_base64(username, token, off_code, photo_url)
                        if img_b64:
                            img_bytes = base64.b64decode(img_b64)
                            try:
                                with open(local_path, "wb") as f_img:
                                    f_img.write(img_bytes)
                            except Exception as fe:
                                print(f"Failed to write image to disk cache: {fe}")
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        else:
                            raise Exception("Null image")

                    if pil_img:
                        # Downscale to save memory
                        pil_img = self.prefetcher._downscale_image(pil_img, max_size=1024)
                        with self.prefetcher.cache_lock:
                            self.prefetcher.image_cache[con_id] = pil_img
                        
                        # Verify we are still on the same index
                        with self.prefetcher.lock:
                            active_con = self.queue_records[self.current_index].get("con_id") if self.queue_records else None
                        
                        if active_con == con_id:
                            self.after(0, self.update_active_image)
                except Exception as e:
                    if self.handle_api_error(e):
                        return
                    with self.prefetcher.cache_lock:
                        self.prefetcher.image_cache[con_id] = "error"
                    self.after(0, lambda: self.img_lbl.configure(image=None, text=f"Failed to fetch image: {str(e)}"))

            threading.Thread(target=fetch_inline_task, daemon=True).start()
        else:
            # Display cached image
            self._render_image(cached_img)

    def on_image_prefetch_done(self, con_id):
        # Callback from background prefetcher when active image finished loading
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            active_con_id = self.queue_records[self.current_index].get("con_id")
            if active_con_id == con_id:
                self.after(0, self.update_active_image)

    def _render_image(self, pil_img):
        # Resize image maintaining aspect ratio
        container_w = self.image_outer_frm.winfo_width()
        container_h = self.image_outer_frm.winfo_height()
        
        # Fallback to defaults if container not rendered yet
        if container_w <= 10 or container_h <= 10:
            container_w = 600
            container_h = 450

        # Leave small margin
        target_w = container_w - 20
        target_h = container_h - 20

        w, h = pil_img.size
        scale = min(target_w / w, target_h / h)
        new_w = max(int(w * scale), 10)
        new_h = max(int(h * scale), 10)

        # CustomTkinter CTkImage Widget
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img

    def on_image_container_resize(self, event):
        # Trigger re-render of image on container resize
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            con_id = self.queue_records[self.current_index].get("con_id")
            cached_img = self.prefetcher.get_image(con_id)
            if cached_img and cached_img != "error":
                self._render_image(cached_img)

    def update_active_telemetry(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            return

        rec = self.queue_records[self.current_index]
        con_id = str(rec.get("con_id", "N/A"))
        
        # Populate key values
        self.telemetry_labels["Consumer ID:"].configure(text=con_id)
        self.telemetry_labels["Meter No:"].configure(text=str(rec.get("meter_no", "N/A")))
        self.telemetry_labels["CCC Name:"].configure(text=str(rec.get("ccc_name", "N/A")))
        self.telemetry_labels["CCC Code:"].configure(text=str(rec.get("ccc_code", "N/A")))
        self.telemetry_labels["Prev Reading:"].configure(text=str(rec.get("previous_reading", "N/A")))
        self.telemetry_labels["Pres Reading:"].configure(text=str(rec.get("present_reading", "N/A")))
        
        # Calculate consumption
        try:
            prev = float(rec.get("previous_reading", 0))
            pres = float(rec.get("present_reading", 0))
            diff = pres - prev
            self.telemetry_labels["Consumption:"].configure(text=f"{diff:.2f}")
        except Exception:
            self.telemetry_labels["Consumption:"].configure(text="N/A")
            
        # Extract MR Note robustly
        raw_note = ""
        for key in ["mr_note", "mrnote", "mr_remark", "mrremark", "remarks", "remark", "note", "reader_note", "readernote", "mr_note_desc", "mrnote_desc"]:
            val = rec.get(key)
            if val is not None:
                raw_note = str(val).strip()
                if raw_note:
                    break
        mr_note = raw_note if raw_note else "N/A"

        self.telemetry_labels["Upload Date:"].configure(text=str(rec.get("upload_date", "N/A")))
        self.telemetry_labels["MR Note:"].configure(text=mr_note)
        self.telemetry_labels["AI Flag:"].configure(text=str(rec.get("aiflag", rec.get("ai_flag", "N/A"))))

        # Update HUD labels
        self.hud_meter_lbl.configure(text=f"Meter: {rec.get('meter_no', 'N/A')}")
        self.hud_pres_lbl.configure(text=f"Present Rdg: {rec.get('present_reading', 'N/A')}")
        self.hud_mrnote_lbl.configure(text=f"MR Note: {mr_note}")
        
        # Overlay HUD on image
        self.image_hud.place(relx=0.5, rely=0.9, relwidth=0.92, relheight=0.12, anchor="center")
        self.image_hud.lift()

    def _clear_viewer(self):
        self.img_lbl.configure(image=None, text="Fetch and select a consumer to display meter image.")
        for lbl in self.telemetry_labels.values():
            lbl.configure(text="N/A")
        self.image_hud.place_forget()

    def on_row_checkbox_toggled(self, con_id):
        chk_var = self.queue_frame.checkbox_vars.get(str(con_id))
        if chk_var:
            val = chk_var.get()
            self.set_status_for_con(con_id, val)

    def set_status(self, status):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            return
        con_id = self.queue_records[self.current_index].get("con_id")
        self.set_status_for_con(con_id, status)
        self.after(50, self.next_consumer)

    def set_status_for_con(self, con_id, status):
        con_id_str = str(con_id)
        if con_id_str not in self.audit_decisions:
            self.audit_decisions[con_id_str] = {"verification_stat": "C", "meter_note": " "}
        
        self.audit_decisions[con_id_str]["verification_stat"] = status
        self.queue_frame.update_status_badge(con_id_str, status)
        self.log_to_console(f"Consumer ID {con_id_str} flagged locally ──► {status}")
        
        self.audited_ids.add(con_id_str)
        self.update_stats_dashboard()
        self.save_local_progress()

    def on_other_obs_selected(self, val):
        if val == "Select Other Observations...":
            return
        
        mapping = {
            "Different Meter No (MM)": "MM",
            "Location Difference (LM)": "LM",
            "Non Meter Image (NMI)": "NMI",
            "Mismatch Reading (I)": "I"
        }
        code = mapping.get(val)
        if code:
            self.set_status(code)
        
        self.combo_other_obs.set("Select Other Observations...")

    def update_stats_dashboard(self):
        total = len(self.queue_records)
        audited = len(self.audited_ids)
        
        correct = total
        illegible = 0
        other = 0
        
        for rec in self.queue_records:
            cid = str(rec.get("con_id"))
            dec = self.audit_decisions.get(cid, {"verification_stat": "C"})
            stat = dec.get("verification_stat", "C")
            if stat == "IL":
                illegible += 1
                correct -= 1
            elif stat in ("MM", "LM", "NMI", "I"):
                other += 1
                correct -= 1
                
        pct = int((audited / total) * 100) if total > 0 else 0
        self.stats_progress_lbl.configure(text=f"Progress: {audited} / {total} ({pct}%)")
        self.progress_bar.set(audited / total if total > 0 else 0)
        
        self.lbl_stat_correct.configure(text=str(correct))
        self.lbl_stat_illegible.configure(text=str(illegible))
        self.lbl_stat_other.configure(text=str(other))

    def open_consumer_details_popup(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            messagebox.showerror("Error", "No consumer selected.")
            return
            
        record = self.queue_records[self.current_index]
        con_id = record.get("con_id")
        if not con_id:
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"Consumer Details - {con_id}")
        popup.geometry("750x500")
        popup.after(200, lambda: popup.focus_force())
        
        title_lbl = ctk.CTkLabel(popup, text=f"Billing & Telemetry History for ID: {con_id}", font=ctk.CTkFont(size=14, weight="bold"))
        title_lbl.pack(pady=10)

        content_frm = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        content_frm.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        loading_lbl = ctk.CTkLabel(content_frm, text="Fetching billing history snapshot from server...", font=ctk.CTkFont(size=12, slant="italic"))
        loading_lbl.pack(pady=40)

        def fetch_details_thread():
            try:
                username = self.session_username
                token = self.session_token
                off_code = self.session_off_code
                
                details = self.api_client.fetch_conid_all(username, token, off_code, con_id)
                
                def render_ui():
                    loading_lbl.destroy()
                    if not details:
                        no_data_lbl = ctk.CTkLabel(content_frm, text="No historical snapshot data found on Tomcat backend.", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray60")
                        no_data_lbl.pack(pady=40)
                        return
                    
                    for idx, bill in enumerate(details):
                        # Card outer container
                        bill_frm = ctk.CTkFrame(content_frm, fg_color="#1f2937" if idx % 2 == 0 else "#111827", corner_radius=8, border_width=1, border_color="gray30")
                        bill_frm.pack(fill="x", pady=6, padx=6)
                        
                        # Title Header Row: Month / Year / Date
                        header_frm = ctk.CTkFrame(bill_frm, fg_color="#374151", corner_radius=4, height=28)
                        header_frm.pack(fill="x", padx=8, pady=(8, 4))
                        
                        acc_m = str(bill.get("acc_month", bill.get("month", "N/A")))
                        acc_y = str(bill.get("acc_year", bill.get("year", "N/A")))
                        smrd_val = str(bill.get("smrd", bill.get("smrdn", bill.get("upload_date", "N/A"))))
                        
                        header_lbl = ctk.CTkLabel(
                            header_frm, 
                            text=f"📅 Billing Period: {acc_m}/{acc_y}   |   SMRD: {smrd_val}", 
                            font=ctk.CTkFont(size=11, weight="bold"), 
                            text_color="#38bdf8"
                        )
                        header_lbl.pack(side="left", padx=10, pady=2)
                        
                        # Grid for reading & metadata details
                        grid_frm = ctk.CTkFrame(bill_frm, fg_color="transparent")
                        grid_frm.pack(fill="x", padx=8, pady=4)
                        grid_frm.columnconfigure((0, 1), weight=1)
                        
                        # Left Column: Readings
                        left_frm = ctk.CTkFrame(grid_frm, fg_color="transparent")
                        left_frm.grid(row=0, column=0, sticky="nsew", padx=4)
                        
                        prev_rdg = bill.get("previous_reading", bill.get("prev_rdg", "N/A"))
                        pres_rdg = bill.get("present_reading", bill.get("pres_rdg", "N/A"))
                        
                        cons = "N/A"
                        try:
                            cons_val = float(pres_rdg) - float(prev_rdg)
                            cons = f"{cons_val:.2f}"
                        except Exception:
                            cons = str(bill.get("consumption", "N/A"))
                            
                        ctk.CTkLabel(left_frm, text=f"• Present Rdg:  {pres_rdg}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10b981", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(left_frm, text=f"• Prev Rdg:       {prev_rdg}", font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(left_frm, text=f"• Consumption:   {cons}", font=ctk.CTkFont(size=11), text_color="#60a5fa", anchor="w").pack(fill="x", pady=1)
                        
                        # Right Column: Meter & AI Status
                        right_frm = ctk.CTkFrame(grid_frm, fg_color="transparent")
                        right_frm.grid(row=0, column=1, sticky="nsew", padx=4)
                        
                        met_no = bill.get("meter_no", bill.get("meterno", "N/A"))
                        ai_flg = bill.get("aiflag", bill.get("ai_flag", "N/A"))
                        v_stat = bill.get("verification_stat", bill.get("status", "N/A"))
                        
                        ctk.CTkLabel(right_frm, text=f"• Meter No:  {met_no}", font=ctk.CTkFont(size=11), text_color="gray80", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(right_frm, text=f"• AI Flag:     {ai_flg}", font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(right_frm, text=f"• Audit Stat: {v_stat}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fbbf24", anchor="w").pack(fill="x", pady=1)
                        
                        # Extract MR Note robustly
                        raw_note = ""
                        for key in ["mr_note", "mrnote", "mr_remark", "mrremark", "remarks", "remark", "note", "reader_note", "readernote", "mr_note_desc", "mrnote_desc"]:
                            val = bill.get(key)
                            if val is not None:
                                raw_note = str(val).strip()
                                if raw_note:
                                    break
                        mr_note = raw_note if raw_note else "N/A"
                        
                        # MR Note Highlight Box
                        note_frm = ctk.CTkFrame(bill_frm, fg_color="#223e2b" if mr_note != "N/A" else "#27272a", corner_radius=4)
                        note_frm.pack(fill="x", padx=8, pady=(4, 8))
                        
                        note_lbl = ctk.CTkLabel(
                            note_frm, 
                            text=f"📝 MR Note: {mr_note}", 
                            font=ctk.CTkFont(size=11, weight="bold" if mr_note != "N/A" else "normal"), 
                            text_color="#a7f3d0" if mr_note != "N/A" else "gray60",
                            anchor="w",
                            justify="left",
                            wraplength=680
                        )
                        note_lbl.pack(fill="x", padx=10, pady=4)
                popup.after(0, render_ui)
            except Exception as e:
                def render_err():
                    loading_lbl.destroy()
                    err_lbl = ctk.CTkLabel(content_frm, text=f"Failed to fetch: {str(e)}", text_color="#ef4444", font=ctk.CTkFont(size=12, weight="bold"))
                    err_lbl.pack(pady=40)
                popup.after(0, render_err)

        threading.Thread(target=fetch_details_thread, daemon=True).start()

    def next_consumer(self):
        if not self.queue_records:
            return
        
        # Default active one to Correct (C) if not modified, then advance
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            con_id = self.queue_records[self.current_index].get("con_id")
            # If down arrow key was pressed, it leaves record as "C" (or whatever it currently is)
            # so no action needed.
            
            # Advance index
            next_idx = self.current_index + 1
            if next_idx < len(self.queue_records):
                next_con_id = self.queue_records[next_idx].get("con_id")
                self.select_consumer_by_id(next_con_id)
            else:
                self.log_to_console("End of queue reached.")

    def prev_consumer(self):
        if not self.queue_records:
            return
        
        if self.current_index > 0:
            prev_idx = self.current_index - 1
            prev_con_id = self.queue_records[prev_idx].get("con_id")
            self.select_consumer_by_id(prev_con_id)

    # ----------------------------------------------------
    # UNIFIED BATCH EXECUTION COMMIT LOOP
    # ----------------------------------------------------
    
    def start_batch_commit(self):
        if not self.queue_records:
            messagebox.showwarning("Commit Blocked", "No records loaded in queue to commit.")
            return
        
        if self.is_committing:
            messagebox.showwarning("Commit Blocked", "Batch submission is already running.")
            return

        confirm = messagebox.askyesno(
            "Confirm Batch Commit", 
            f"Are you sure you want to commit verification decisions for all {len(self.queue_records)} records to the backend Tomcat server?"
        )
        if not confirm:
            return

        self.is_committing = True
        self.commit_btn.configure(state="disabled", text="Committing...")
        self.fetch_queue_btn.configure(state="disabled")

        # Run submission loop in background thread
        threading.Thread(target=self._batch_commit_task, daemon=True).start()

    def _batch_commit_task(self):
        records = list(self.queue_records)
        decisions = dict(self.audit_decisions)
        
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        acc_month = self.month_combo.get()
        acc_year = self.year_combo.get()
        pacing = float(self.pacing_slider.get())

        total = len(records)
        success_count = 0
        failure_count = 0

        self.log_to_console(f"\n--- Batch Upload Initiated ({total} records) ---")

        for idx, rec in enumerate(records, start=1):
            con_id = rec.get("con_id")
            
            # Extract decision
            decision = decisions.get(str(con_id), {"verification_stat": "C", "meter_note": " "})
            status = decision.get("verification_stat", "C")
            note = decision.get("meter_note", " ")

            ccc_code = rec.get("ccc_code", off_code)
            ccc_name = rec.get("ccc_name", "KUSHIDA CCC")
            
            # Extract SMRD directly from record
            smrdn = rec.get("smrd", rec.get("smrdn", " "))
            if not smrdn or str(smrdn).strip().lower() == "none":
                smrdn = " "

            # Log current action
            self.log_to_console(f"[{idx}/{total}] Uploading Consumer ID {con_id} (Status: {status})...")

            # Try request
            try:
                success, server_msg = self.api_client.submit_audit_record(
                    username=username,
                    token=token,
                    off_code=off_code,
                    acc_month=acc_month,
                    acc_year=acc_year,
                    ccc_code=ccc_code,
                    ccc_name=ccc_name,
                    con_id=con_id,
                    smrdn=smrdn,
                    verification_stat=status,
                    meter_note=note
                )
                if success:
                    success_count += 1
                    self.log_to_console(f"   ──► Success: {server_msg}")
                    self.remove_from_local_progress(con_id)
                else:
                    failure_count += 1
                    self.log_to_console(f"   ──► Failed: {server_msg}")
            except Exception as e:
                if self.handle_api_error(e):
                    # Session expired and redirect triggered, breakout!
                    return
                failure_count += 1
                self.log_to_console(f"   ──► Network Fault: {str(e)}")

            # Update progress bar
            progress_val = idx / total
            self.after(0, lambda val=progress_val: self.progress_bar.set(val))

            # Sleep pacing
            time.sleep(pacing)

        # Complete audit summary
        self.log_to_console(f"--- Batch Upload Completed. Success: {success_count} | Failed: {failure_count} ---")
        
        # Reset UI controls on main thread
        def reset_ui():
            self.is_committing = False
            self.commit_btn.configure(state="normal", text="Commit Batch")
            self.fetch_queue_btn.configure(state="normal")
            messagebox.showinfo(
                "Batch Execution Done", 
                f"Batch upload finished.\n\nSuccess: {success_count}\nFailures: {failure_count}"
            )

        self.after(0, reset_ui)


if __name__ == "__main__":
    app = MeterAuditApp()
    
    # Clean shutdown of background prefetcher threads
    def on_closing():
        app.prefetcher.stop()
        app.stop_keep_alive_timer()
        app.destroy()
        sys.exit(0)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
