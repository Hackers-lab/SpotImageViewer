import os
import sys
import base64
import shutil
import hashlib
import threading
import subprocess
from io import BytesIO
from collections import OrderedDict
from PIL import Image, ImageOps

try:
    from core import config
    _BASE_DIR = config.BASE_DIR
except ImportError:
    _BASE_DIR = r"C:\spotbillfiles\backup"

THUMB_CACHE_DIR = os.path.join(_BASE_DIR, "thumb_cache")

# Fast in-memory cache for the most recently accessed thumbnails/images (max 50)
_RAM_CACHE = OrderedDict()
_RAM_CACHE_LOCK = threading.Lock()
_MAX_RAM_CACHE = 50


class ImageService:
    """
    Handles image decoding, EXIF orientation correction, thumbnail resizing,
    disk and RAM caching, base64 encoding for webview rendering, file saving, and native printing.
    """

    @staticmethod
    def get_image_data(file_path, max_dim=1400):
        """Loads and encodes an image into JPEG base64 with EXIF orientation correction and caching."""
        try:
            if not file_path or not os.path.exists(file_path):
                # Fallback: check if the same filename is available in another indexed directory
                fallback_path = None
                if file_path:
                    fname = os.path.basename(file_path)
                    try:
                        from core import database
                        conn = database.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                "SELECT d.dir_path FROM images i JOIN directories d ON i.dir_id = d.id WHERE i.filename = ?",
                                (fname,)
                            )
                            for row in cur.fetchall():
                                candidate = os.path.join(row[0], fname)
                                if os.path.exists(candidate):
                                    fallback_path = candidate
                                    break
                        finally:
                            cur.close()
                    except Exception:
                        pass

                if fallback_path:
                    file_path = fallback_path
                else:
                    return {"success": False, "error": f"Image file is offline or inaccessible: {file_path}"}

            mtime = int(os.path.getmtime(file_path))
            cache_key = (file_path, max_dim, mtime)

            # 1. Check in-memory RAM cache (instant 0ms return)
            with _RAM_CACHE_LOCK:
                if cache_key in _RAM_CACHE:
                    cached_res = _RAM_CACHE[cache_key]
                    _RAM_CACHE.move_to_end(cache_key)
                    return cached_res

            # 2. Check disk thumbnail cache
            hash_id = hashlib.md5(f"{file_path}_{max_dim}_{mtime}".encode('utf-8')).hexdigest()
            disk_thumb_path = os.path.join(THUMB_CACHE_DIR, f"{hash_id}.jpg")

            if os.path.exists(disk_thumb_path) and os.path.getsize(disk_thumb_path) > 0:
                try:
                    with open(disk_thumb_path, "rb") as tf:
                        thumb_bytes = tf.read()
                    b64_str = base64.b64encode(thumb_bytes).decode('ascii')
                    result = {
                        "success": True,
                        "mime": "image/jpeg",
                        "width": 0,
                        "height": 0,
                        "data": f"data:image/jpeg;base64,{b64_str}"
                    }
                    with _RAM_CACHE_LOCK:
                        _RAM_CACHE[cache_key] = result
                        if len(_RAM_CACHE) > _MAX_RAM_CACHE:
                            _RAM_CACHE.popitem(last=False)
                    return result
                except Exception:
                    pass

            # 2.5 Fast-path for standard JPEGs under 1.5MB requested at main viewer size (>= 1400px)
            # Avoids heavy Pillow decoding, bicubic resampling, and JPEG re-encoding
            file_ext = os.path.splitext(file_path)[1].lower()
            file_size = os.path.getsize(file_path)
            if max_dim and max_dim >= 1400 and file_ext in ('.jpg', '.jpeg') and file_size < 1_500_000:
                try:
                    with Image.open(file_path) as test_img:
                        exif = test_img.getexif()
                        orientation = exif.get(0x0112, 1) if exif else 1
                        orig_w, orig_h = test_img.size
                    if orientation in (1, None):
                        with open(file_path, "rb") as rf:
                            raw_bytes = rf.read()
                        b64_str = base64.b64encode(raw_bytes).decode('ascii')
                        result = {
                            "success": True,
                            "mime": "image/jpeg",
                            "width": orig_w,
                            "height": orig_h,
                            "data": f"data:image/jpeg;base64,{b64_str}"
                        }
                        with _RAM_CACHE_LOCK:
                            _RAM_CACHE[cache_key] = result
                            if len(_RAM_CACHE) > _MAX_RAM_CACHE:
                                _RAM_CACHE.popitem(last=False)
                        return result
                except Exception:
                    pass

            # 3. Decode with Pillow (draft mode for fast DCT decode & BICUBIC/BILINEAR for thumbs)
            with Image.open(file_path) as orig:
                if max_dim:
                    try:
                        orig.draft('RGB', (max_dim, max_dim))
                    except Exception:
                        pass

                img = ImageOps.exif_transpose(orig)
                buffer = None
                try:
                    orig_w, orig_h = img.size
                    if max_dim and (orig_w > max_dim or orig_h > max_dim):
                        resample = Image.Resampling.BILINEAR if max_dim <= 400 else Image.Resampling.BICUBIC
                        img.thumbnail((max_dim, max_dim), resample)

                    buffer = BytesIO()
                    # Quality 82 provides crisp quality while cutting file size by ~40% vs quality 88
                    img.convert('RGB').save(buffer, format="JPEG", quality=82, optimize=False)
                    data_bytes = buffer.getvalue()

                    # Save to disk cache in background/inline
                    try:
                        os.makedirs(THUMB_CACHE_DIR, exist_ok=True)
                        with open(disk_thumb_path, "wb") as f:
                            f.write(data_bytes)
                    except Exception:
                        pass

                    b64_str = base64.b64encode(data_bytes).decode('ascii')
                    result = {
                        "success": True,
                        "mime": "image/jpeg",
                        "width": orig_w,
                        "height": orig_h,
                        "data": f"data:image/jpeg;base64,{b64_str}"
                    }

                    with _RAM_CACHE_LOCK:
                        _RAM_CACHE[cache_key] = result
                        if len(_RAM_CACHE) > _MAX_RAM_CACHE:
                            _RAM_CACHE.popitem(last=False)

                    return result
                finally:
                    if img is not orig:
                        try:
                            img.close()
                        except Exception:
                            pass
                    if buffer:
                        buffer.close()

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_image_to(file_path, dest_path):
        """Copies an image to a destination path."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "Source file does not exist."}
            if not dest_path:
                return {"success": False, "error": "Destination path required."}

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(file_path, dest_path)
            return {"success": True, "path": dest_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_all_images(consumer_id, dest_dir, image_records):
        """Copies all spot billing images for a consumer into the chosen destination folder."""
        try:
            if not dest_dir:
                return {"success": False, "error": "Destination directory is required."}
            os.makedirs(dest_dir, exist_ok=True)

            count = 0
            for img in image_records:
                src = img.get("full_path") or img.get("path")
                if src and os.path.exists(src):
                    filename = img.get("filename", os.path.basename(src))
                    dst = os.path.join(dest_dir, f"{consumer_id}_{filename}")
                    shutil.copy2(src, dst)
                    count += 1
            return {"success": True, "count": count, "path": dest_dir}
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    @staticmethod
    def print_image(file_path):
        """Sends the image file to the OS default print spooler."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File does not exist."}

            if os.name == 'nt':
                os.startfile(file_path, "print")
                return {"success": True}
            return {"success": False, "error": "Printing only supported on Windows"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def open_image_external(file_path):
        """Opens image in OS default photo viewer."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File does not exist."}

            if os.name == 'nt':
                os.startfile(file_path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, file_path])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
