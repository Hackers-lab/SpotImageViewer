import os
import sys
import json
import math
import base64
from io import BytesIO
from datetime import datetime, date
import calendar
from PIL import Image, ImageOps
import requests
import shutil
import csv
import threading
import time

from core import config, database, utils, tariff_manager

class AppAPI:
    """
    Python-to-JavaScript RPC bridge exposed to PyWebView window.
    All methods return JSON-serializable dictionaries or primitives.
    """

    _indexing_state = {"running": False, "scanned": 0, "total": 0, "elapsed": 0}

    def __init__(self, window=None):
        self.window = window

    def set_window(self, window):
        self.window = window

    # --- System & Settings ---
    def get_app_info(self):
        total_images = database.get_total_image_count()
        folders = [config.IMAGE_FOLDER] + database.get_additional_folders()
        return {
            "version": config.CURRENT_VERSION,
            "total_images": total_images,
            "folders": folders,
            "has_meter_data": database.has_meter_data()
        }

    # --- Search & Consumer Details ---
    def search_consumer(self, query, filter_type="auto"):
        query = str(query or "").strip()
        if not query:
            return {"success": False, "error": "Search query cannot be empty."}

        detected_type = filter_type
        if filter_type == "auto":
            if query.isdigit() and len(query) == 9:
                detected_type = "cid"
            elif query.isdigit() and len(query) == 10:
                detected_type = "mobile"
            elif any(c.isalpha() for c in query) and len(query) > 3 and not any(c.isdigit() for c in query):
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
                    """, (f"%{query}%",))
                    for r in cur.fetchall():
                        results.append({
                            "consumer_id": r[0], "meter_no": r[1], "name": r[2], "address": r[3],
                            "mobile_number": r[4], "contractual_load": r[5], "class": r[6]
                        })
                    conn.close()
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

    # --- Fetch Consumer Images ---
    def get_consumer_images(self, consumer_id):
        cid = str(consumer_id).strip()
        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT i.date_original, i.mru, d.dir_path, i.filename 
                FROM images i 
                JOIN directories d ON i.dir_id = d.id 
                WHERE i.consumer_id = ? 
                ORDER BY i.date_iso DESC
            """, (cid,))
            rows = cur.fetchall()
            conn.close()

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

    # --- Fetch Single Image Base64 ---
    def get_image_data(self, file_path, max_dim=1400):
        try:
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

    # --- Calculation Engines ---
    def calculate_bill(self, p):
        try:
            tariffs = tariff_manager.load_tariff()
            cat = p.get("category", "")
            if not cat or cat not in tariffs:
                return {"success": False, "error": f"Invalid tariff class {cat}"}
            cat_data = tariffs[cat]
            cat_lower = cat.lower()
            is_tod = "tod" in cat_lower

            cycle = p.get("cycle", "Quarterly")
            if cycle == "Quarterly":
                months_multiplier = 3.0
            elif cycle == "Monthly":
                months_multiplier = 1.0
            else:
                days = int(p.get("days", 30))
                if days <= 0: days = 1
                months_multiplier = days / 30.0

            phase = p.get("phase", "1-Phase")
            mvca_rate = float(p.get("mvca", 0.0))
            load_unit = p.get("load_unit", "kVA")
            raw_load = float(p.get("load", 1.0))
            load_kva = (raw_load / 0.85) if load_unit == "kW" else raw_load
            if "commercial" in cat_lower and 0 < load_kva < 1.0:
                load_kva = 1.0

            energy_charge = 0.0
            total_units = 0

            if is_tod:
                n = int(p.get("tod_n", 0))
                pk = int(p.get("tod_p", 0))
                o = int(p.get("tod_o", 0))
                total_units = n + pk + o
                if "tod_slabs" in cat_data:
                    energy_charge += n * cat_data["tod_slabs"].get("Normal", 0)
                    energy_charge += pk * cat_data["tod_slabs"].get("Peak", 0)
                    energy_charge += o * cat_data["tod_slabs"].get("Off_Peak", 0)
            else:
                total_units = int(p.get("units", 0))
                if "commercial" in cat_lower:
                    energy_charge -= (min(total_units, 100 * months_multiplier) * 0.02)
                u = total_units
                for slab in cat_data.get("slabs", []):
                    if u <= 0: break
                    limit, rate = slab["limit"], slab["rate"]
                    if limit is None:
                        energy_charge += u * rate
                        u = 0
                    else:
                        slab_units = min(u, limit * months_multiplier)
                        energy_charge += slab_units * rate
                        u -= slab_units

            base_fc = load_kva * cat_data["fixed_charge"] * months_multiplier
            
            is_monsoon = p.get("is_monsoon", False)
            if is_monsoon and "agriculture" in cat_lower and not is_tod:
                base_fc /= 2.0
                
            if "domestic" in cat_lower:
                base_fc = max(base_fc, 30.0 * months_multiplier)

            min_floor = load_kva * cat_data.get("min_charge", 0.0) * months_multiplier
            is_minimum = (energy_charge + base_fc) < min_floor and min_floor > 100.0

            if is_minimum:
                base_amount = min_floor
            else:
                base_amount = energy_charge + base_fc

            # Meter rent
            meter_rent = 0.0
            if p.get("meter_rent_applicable", True) and phase != "Own Meter":
                if is_tod:
                    base_rent = 25.0
                elif "domestic" in cat_lower and phase == "1-Phase":
                    base_rent = 10.0
                elif "commercial" in cat_lower and phase == "1-Phase":
                    base_rent = 15.0
                elif phase == "3-Phase":
                    if "commercial" in cat_lower:
                        base_rent = 30.0
                    else:
                        base_rent = 50.0
                else:
                    base_rent = 50.0
                meter_rent = base_rent * months_multiplier

            # MVCA
            mvca_charge = (total_units * mvca_rate) / 100.0

            # Electricity Duty (ED)
            monthly_units = total_units / months_multiplier if months_multiplier > 0 else 0
            
            # Govt Subsidy / Relief
            subsidy_amount = 0.0
            if "domestic" in cat_lower:
                max_subsidized_units = 300.0 * months_multiplier
                if total_units <= max_subsidized_units:
                    u = total_units
                    s1, s2, s3 = 34 * months_multiplier, 26 * months_multiplier, 40 * months_multiplier
                    
                    if u > 0: slab = min(u, s1); subsidy_amount += slab * 0.90; u -= slab
                    if u > 0: slab = min(u, s2); subsidy_amount += slab * 0.90; u -= slab
                    if u > 0: slab = min(u, s3); subsidy_amount += slab * 0.74; u -= slab
                    if u > 0: subsidy_amount += u * 0.79
                    if phase == "1-Phase": subsidy_amount += (10.0 * months_multiplier)
            
            rebateable_amount = base_amount + mvca_charge
            timely_rebate = rebateable_amount * 0.01

            ed_base = base_amount - timely_rebate if "domestic" in cat_lower or "commercial" in cat_lower else base_amount
            ed_percent = 0.0
            for slab in cat_data.get("ed_slabs", []):
                scaled_limit = slab["limit"] * months_multiplier if slab["limit"] else None
                if scaled_limit is None or total_units <= scaled_limit:
                    ed_percent = slab["rate"]
                    break
                        
            ed_charge = ed_base * ed_percent
            gross_total = base_amount + mvca_charge + meter_rent + ed_charge - subsidy_amount
            
            special_rebate = total_units * 0.10 if ("domestic" in cat_lower or "commercial" in cat_lower) and months_multiplier > 2.0 else 0.0
            net_after_timely = gross_total - special_rebate - timely_rebate
            epay_rebate = net_after_timely * 0.01 if net_after_timely > 0 else 0.0
            total_rebates = special_rebate + timely_rebate + epay_rebate
            
            net_bill = gross_total - total_rebates

            return {
                "success": True,
                "result": {
                    "total_units": total_units,
                    "months_multiplier": round(months_multiplier, 4),
                    "energy_charge": round(energy_charge, 2),
                    "fixed_charge": round(base_fc, 2),
                    "is_minimum_override": is_minimum,
                    "minimum_floor": round(min_floor, 2),
                    "meter_rent": round(meter_rent, 2),
                    "mvca_charge": round(mvca_charge, 2),
                    "ed_charge": round(ed_charge, 2),
                    "ed_percentage": round(ed_percent * 100, 2),
                    "gross_total": round(gross_total, 2),
                    "gov_relief": round(subsidy_amount, 2),
                    "special_rebate": round(special_rebate, 2),
                    "timely_rebate": round(timely_rebate, 2),
                    "epay_rebate": round(epay_rebate, 2),
                    "net_bill": round(net_bill, 2),
                    "rounded_bill": round(net_bill)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def calculate_theft(self, p):
        try:
            tariffs = tariff_manager.load_tariff()
            cat = p.get("category", "")
            if not cat or cat not in tariffs:
                return {"success": False, "error": f"Invalid tariff category {cat}"}
            cat_data = tariffs[cat]
            cons_type = p.get("consumer_type", "Consumer")
            raw_load = float(p.get("load", 1.0))
            load_kva = (raw_load / 0.85) if p.get("load_unit", "kVA") == "kW" else raw_load

            days = int(p.get("days", 365))
            hours = float(p.get("hours", 8.0))

            pf = 0.85
            lf = cat_data.get("load_factor", 0.5 if "domestic" in cat.lower() else 0.75)
            months = days / (365 / 12)
            total_units = round(load_kva * pf * lf * days * hours)
            units_per_month = total_units / months if months > 0 else 0

            # Normal charge calculation
            if cons_type == "Non-Consumer":
                highest_rate = 0.0
                if "slabs" in cat_data: highest_rate = max(slab["rate"] for slab in cat_data["slabs"])
                elif "tod_slabs" in cat_data: highest_rate = max(cat_data["tod_slabs"].values())
                normal_monthly_charge = units_per_month * highest_rate
            else:
                charge = 0.0
                u = units_per_month
                if "slabs" in cat_data:
                    for slab in cat_data["slabs"]:
                        if u <= 0: break
                        limit, rate = slab["limit"], slab["rate"]
                        if limit is None:
                            charge += u * rate
                            u = 0
                        else:
                            slab_units = min(u, limit)
                            charge += slab_units * rate
                            u -= slab_units
                elif "tod_slabs" in cat_data:
                    charge = u * cat_data["tod_slabs"].get("Normal", 0.0)
                normal_monthly_charge = charge

            normal_total_charge = normal_monthly_charge * months
            penal_energy_charge = normal_total_charge * 2

            rounded_load = max(1.0, load_kva)
            rounded_months = math.ceil(months)
            normal_fc = rounded_load * cat_data["fixed_charge"] * rounded_months
            penal_fc = normal_fc * 2

            # ED
            ed_percent = 0.0
            for slab in cat_data.get("ed_slabs", []):
                if slab["limit"] is None or units_per_month <= slab["limit"]:
                    ed_percent = slab["rate"]
                    break
            total_ed = (penal_energy_charge + penal_fc) * ed_percent
            gross_bill = penal_energy_charge + penal_fc + total_ed

            # Adjustments
            adj_e = float(p.get("adj_energy", 0.0))
            adj_f = float(p.get("adj_fixed", 0.0))
            adj_ed = float(p.get("adj_ed", 0.0))
            total_adjustments = adj_e + adj_f + adj_ed

            net_assessment = gross_bill - total_adjustments

            return {
                "success": True,
                "result": {
                    "assessed_units": total_units,
                    "months": round(months, 2),
                    "penal_energy_charge": round(penal_energy_charge, 2),
                    "penal_fixed_charge": round(penal_fc, 2),
                    "electricity_duty": round(total_ed, 2),
                    "ed_rate": round(ed_percent * 100, 2),
                    "gross_bill": round(gross_bill, 2),
                    "total_adjustments": round(total_adjustments, 2),
                    "net_assessment": round(net_assessment, 2),
                    "rounded_assessment": round(net_assessment)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def calculate_theft_dual(self, p):
        try:
            tariffs = tariff_manager.load_tariff()
            cat = p.get("category", "")
            if not cat or cat not in tariffs:
                return {"success": False, "error": f"Invalid tariff category {cat}"}
            cat_data = tariffs[cat]
            cons_type = p.get("consumer_type", "Consumer")
            raw_load = float(p.get("load", 1.0))
            load_kva = (raw_load / 0.85) if p.get("load_unit", "kVA") == "kW" else raw_load

            prov_days = int(p.get("prov_days", 365))
            prov_hours = float(p.get("prov_hours", 24.0))
            final_days = int(p.get("final_days", 365))
            final_hours = float(p.get("final_hours", 19.0))
            
            adj_e = float(p.get("adj_energy", 0.0))
            adj_f = float(p.get("adj_fixed", 0.0))
            adj_ed = float(p.get("adj_ed", 0.0))
            total_adjustments = adj_e + adj_f + adj_ed

            def compute_assessment(days, hours):
                pf = 0.85
                lf = cat_data.get("load_factor", 0.5 if "domestic" in cat.lower() else 0.75)
                months = days / (365 / 12)  
                total_units = round(load_kva * pf * lf * days * hours)
                units_per_month = total_units / months if months > 0 else 0
                
                if cons_type == "Non-Consumer":
                    highest_rate = 0.0
                    if "slabs" in cat_data: highest_rate = max(slab["rate"] for slab in cat_data["slabs"])
                    elif "tod_slabs" in cat_data: highest_rate = max(cat_data["tod_slabs"].values())
                    normal_monthly_charge = units_per_month * highest_rate
                else:
                    charge = 0.0; u = units_per_month
                    if "slabs" in cat_data:
                        for slab in cat_data["slabs"]:
                            if u <= 0: break
                            limit, rate = slab["limit"], slab["rate"]
                            if limit is None:
                                charge += u * rate; u = 0
                            else:
                                slab_units = min(u, limit)
                                charge += slab_units * rate; u -= slab_units
                    elif "tod_slabs" in cat_data:
                        charge = u * cat_data["tod_slabs"].get("Normal", 0.0)
                    normal_monthly_charge = charge
                    
                normal_total_charge = normal_monthly_charge * months
                penal_energy_charge = normal_total_charge * 2

                rounded_load = max(1.0, load_kva)
                rounded_months = math.ceil(months)
                normal_fc = rounded_load * cat_data["fixed_charge"] * rounded_months

                penal_fc = normal_fc * 2 
                
                ed_percent = 0.0
                for slab in cat_data.get("ed_slabs", []):
                    if slab["limit"] is None or units_per_month <= slab["limit"]:
                        ed_percent = slab["rate"]
                        break
                        
                total_ed = (penal_energy_charge + penal_fc) * ed_percent
                gross_bill = penal_energy_charge + penal_fc + total_ed
                
                return {
                    "units": total_units, "energy": penal_energy_charge, "fixed": penal_fc,
                    "ed_percent": ed_percent, "ed": total_ed, "gross": gross_bill
                }

            prov = compute_assessment(prov_days, prov_hours)
            final = compute_assessment(final_days, final_hours)
            
            prov_net = prov['gross'] - total_adjustments
            final_net = final['gross'] - total_adjustments
            
            diff_rs = prov_net - final_net
            diff_pct = (diff_rs / prov_net * 100) if prov_net > 0 else 0
            
            return {
                "success": True,
                "prov": prov,
                "final": final,
                "adjustments": total_adjustments,
                "prov_net": prov_net,
                "final_net": final_net,
                "diff_rs": diff_rs,
                "diff_pct": diff_pct
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Tariff Data ---
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

    # --- Auto Update ---
    def check_for_updates(self):
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
                    "installer_url": data.get("installer_url", "")
                }
            return {"success": False, "error": "Failed to connect to update server."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Consumer Notes ---
    def get_consumer_note(self, consumer_id):
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT note, remarks FROM notes WHERE consumer_id = ?", (consumer_id,))
            row = cursor.fetchone()
            conn.close()
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
            options = database.get_note_options()
            return {"success": True, "options": options}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_note_option(self, option_text):
        try:
            database.add_note_option(option_text)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Image Operations ---
    def save_image_to(self, file_path, dest_path):
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(file_path, dest_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_all_images(self, consumer_id, dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
            images_data = self.get_consumer_images(consumer_id)
            if not images_data.get("success"):
                return images_data
                
            count = 0
            for img in images_data.get("images", []):
                src = img["full_path"]
                if os.path.exists(src):
                    dst = os.path.join(dest_dir, f"{consumer_id}_{img['filename']}")
                    shutil.copy2(src, dst)
                    count += 1
            return {"success": True, "count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def print_image(self, file_path):
        try:
            if os.name == 'nt':
                os.startfile(file_path, "print")
                return {"success": True}
            return {"success": False, "error": "Printing only supported on Windows"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_image_external(self, file_path):
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            else:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, file_path])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Folder Management ---
    def get_folder_status(self):
        try:
            folders = []
            
            # Primary
            primary_path = config.IMAGE_FOLDER
            folders.append({
                "path": primary_path,
                "accessible": os.path.exists(primary_path),
                "is_primary": True
            })
            
            # Additional
            for p in database.get_additional_folders():
                folders.append({
                    "path": p,
                    "accessible": os.path.exists(p),
                    "is_primary": False
                })
                
            return {"success": True, "folders": folders}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_network_folder(self, path):
        try:
            if not os.path.exists(path):
                return {"success": False, "error": "Folder path does not exist or is not accessible"}
            folders = database.get_additional_folders()
            if path not in folders:
                folders.append(path)
                database.save_additional_folders(folders)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_network_folder(self, path):
        try:
            folders = database.get_additional_folders()
            if path in folders:
                folders.remove(path)
                database.save_additional_folders(folders)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- System ---
    def start_indexing(self):
        if self._indexing_state["running"]:
            return {"success": False, "error": "Indexing already running"}
        
        self._indexing_state["running"] = True
        self._indexing_state["scanned"] = 0
        self._indexing_state["total"] = 0
        self._indexing_state["elapsed"] = 0
        
        def _index():
            start = time.time()
            try:
                if hasattr(utils, "index_images_generator"):
                    for status in utils.index_images_generator():
                        self._indexing_state["scanned"] = status.get("scanned", 0)
                        self._indexing_state["total"] = status.get("total", 0)
                        self._indexing_state["elapsed"] = int(time.time() - start)
                else:
                    time.sleep(2)
            finally:
                self._indexing_state["running"] = False
                
        threading.Thread(target=_index, daemon=True).start()
        return {"success": True}

    def get_indexing_status(self):
        return {"success": True, **self._indexing_state}

    def export_notes_csv(self, dest_path):
        try:
            notes = database.get_all_notes()
            with open(dest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Consumer ID", "Note", "Remarks"])
                for cid, data in notes.items():
                    writer.writerow([cid, data["note"], data["remarks"]])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
