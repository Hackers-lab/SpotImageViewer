import os
import csv
from collections import OrderedDict

try:
    from core import database, utils
except ImportError:
    import database, utils

from .base import _io_pool, _image_pool


class ViewerBridge:
    """Image search, retrieval, image operations, consumer notes, and search history bridge."""

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

            by_date = OrderedDict()
            for date_orig, mru, dir_path, filename in rows:
                if date_orig not in by_date:
                    by_date[date_orig] = []
                by_date[date_orig].append((mru, dir_path, filename))

            grouped = {}
            flat_images = []
            for date_orig, candidates in by_date.items():
                chosen = candidates[0]
                if len(candidates) > 1 and not (len(chosen[1]) >= 2 and chosen[1][1] == ':'):
                    for cand in candidates:
                        if len(cand[1]) >= 2 and cand[1][1] == ':':
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
