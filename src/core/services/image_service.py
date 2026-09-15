import os
import sys
import base64
import shutil
import subprocess
from io import BytesIO
from PIL import Image, ImageOps


class ImageService:
    """
    Handles image decoding, EXIF orientation correction, thumbnail resizing,
    base64 encoding for webview rendering, file saving, and native printing.
    """

    @staticmethod
    def get_image_data(file_path, max_dim=1400):
        """Loads and encodes an image into JPEG base64 with EXIF orientation correction."""
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
                        cur.execute(
                            "SELECT d.dir_path FROM images i JOIN directories d ON i.dir_id = d.id WHERE i.filename = ?",
                            (fname,)
                        )
                        for row in cur.fetchall():
                            candidate = os.path.join(row[0], fname)
                            if os.path.exists(candidate):
                                fallback_path = candidate
                                break
                    except Exception:
                        pass

                if fallback_path:
                    file_path = fallback_path
                else:
                    return {"success": False, "error": f"Image file is offline or inaccessible: {file_path}"}

            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)
                orig_w, orig_h = img.size
                if max_dim and (orig_w > max_dim or orig_h > max_dim):
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                buffer = BytesIO()
                img.convert('RGB').save(buffer, format="JPEG", quality=88)
                b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

                return {
                    "success": True,
                    "mime": "image/jpeg",
                    "width": orig_w,
                    "height": orig_h,
                    "data": f"data:image/jpeg;base64,{b64_str}"
                }
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
