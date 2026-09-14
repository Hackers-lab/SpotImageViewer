import os
import io
import time
import queue
import threading
import requests
from PIL import Image
from .constants import IMAGE_CACHE_DIR, HEADERS

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

