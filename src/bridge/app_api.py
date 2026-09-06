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
import re
import subprocess
from collections import defaultdict
from difflib import SequenceMatcher
try:
    from rapidfuzz import fuzz as rapidfuzz_fuzz
except ImportError:
    rapidfuzz_fuzz = None
import openpyxl

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

            phase_input = str(p.get("phase", "1-Phase")).strip()
            if phase_input in ("1", "1-Phase", "Single Phase"):
                phase = "1-Phase"
            elif phase_input in ("3", "3-Phase", "Three Phase"):
                phase = "3-Phase"
            elif phase_input.lower() in ("own", "own meter"):
                phase = "Own Meter"
            else:
                phase = phase_input

            mvca_rate = float(p.get("mvca", 0.0))
            load_unit = p.get("load_unit", "kVA")
            raw_load = float(p.get("load", 1.0))
            load_kva = (raw_load / 0.85) if load_unit == "kW" else raw_load
            if "commercial" in cat_lower and 0 < load_kva < 1.0:
                load_kva = 1.0

            energy_charge = 0.0
            total_units = 0

            if is_tod:
                tod_dict = p.get("tod_units") or {}
                n = int(tod_dict.get("normal", p.get("tod_n", 0)))
                pk = int(tod_dict.get("peak", p.get("tod_p", 0)))
                o = int(tod_dict.get("off_peak", p.get("tod_o", 0)))
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

            # MVCA (in ₹ per unit, directly multiplied as in desktop bill calculator)
            mvca_charge = total_units * mvca_rate

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
                    "min_charge_override": is_minimum,
                    "minimum_floor": round(min_floor, 2),
                    "minimum_charge": round(min_floor, 2),
                    "meter_rent": round(meter_rent, 2),
                    "mvca_charge": round(mvca_charge, 2),
                    "ed_charge": round(ed_charge, 2),
                    "ed_percentage": round(ed_percent * 100, 2),
                    "gross_total": round(gross_total, 2),
                    "gross_bill": round(gross_total, 2),
                    "gov_relief": round(subsidy_amount, 2),
                    "special_rebate": round(special_rebate, 2),
                    "rebate_special": round(special_rebate, 2),
                    "timely_rebate": round(timely_rebate, 2),
                    "rebate_timely": round(timely_rebate, 2),
                    "epay_rebate": round(epay_rebate, 2),
                    "rebate_epay": round(epay_rebate, 2),
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

            prov_days = int(p.get("days_prov", p.get("prov_days", 365)))
            final_days = int(p.get("days_final", p.get("final_days", 365)))
            
            shared_hours = p.get("hours")
            prov_hours = float(p.get("prov_hours", shared_hours if shared_hours is not None else 24.0))
            final_hours = float(p.get("final_hours", shared_hours if shared_hours is not None else 19.0))
            
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

            def format_block(b, net):
                return {
                    "units": b["units"],
                    "assessed_units": b["units"],
                    "energy": b["energy"],
                    "penal_energy_charge": b["energy"],
                    "fixed": b["fixed"],
                    "penal_fixed_charge": b["fixed"],
                    "ed_percent": b["ed_percent"],
                    "ed": b["ed"],
                    "electricity_duty": b["ed"],
                    "gross": b["gross"],
                    "gross_assessment": b["gross"],
                    "total_adjustments": total_adjustments,
                    "net": net,
                    "net_assessment": net,
                    "rounded_assessment": round(net)
                }

            prov_block = format_block(prov, prov_net)
            final_block = format_block(final, final_net)
            relief_info = {
                "diff_rs": diff_rs,
                "diff_pct": diff_pct
            }

            return {
                "success": True,
                "prov": prov_block,
                "provisional": prov_block,
                "final": final_block,
                "adjustments": total_adjustments,
                "prov_net": prov_net,
                "final_net": final_net,
                "relief": relief_info,
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
    def save_image_to(self, file_path, dest_path=""):
        try:
            if not dest_path:
                default_name = os.path.basename(file_path)
                dest_path = self.pick_save_file(
                    title="Save Image As",
                    default_filename=default_name,
                    file_types=[("JPEG Images (*.jpg;*.jpeg)", "*.jpg;*.jpeg"), ("All Files (*.*)", "*.*")]
                )
            if not dest_path:
                return {"success": False, "cancelled": True}

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(file_path, dest_path)
            return {"success": True, "path": dest_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_all_images(self, consumer_id, dest_dir=""):
        try:
            if not dest_dir:
                dest_dir = self.pick_folder(title=f"Select Destination Folder for Consumer {consumer_id} Photos")
            if not dest_dir:
                return {"success": False, "cancelled": True}

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
            return {"success": True, "count": count, "path": dest_dir}
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

    # --- Native File & Folder Dialogs ---
    def pick_file(self, title="Select File", file_types=None):
        """Open native file dialog to select a file."""
        try:
            if self.window and hasattr(self.window, "create_file_dialog"):
                import webview
                file_filter = ()
                if file_types:
                    file_filter = tuple(file_types) if isinstance(file_types, (list, tuple)) else (str(file_types),)
                res = self.window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=file_filter)
                if res and len(res) > 0:
                    return res[0]
                return ""
            
            # Tkinter fallback
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            tk_types = [("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
            if file_types and isinstance(file_types, list):
                tk_types = []
                for ft in file_types:
                    if isinstance(ft, (list, tuple)) and len(ft) >= 2:
                        tk_types.append((ft[0], ft[1]))
                    elif isinstance(ft, str):
                        tk_types.append(("Files", ft))
            chosen = filedialog.askopenfilename(title=title, filetypes=tk_types or [("All Files", "*.*")])
            root.destroy()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_file]: {e}")
            return ""

    def pick_save_file(self, title="Save File", default_filename="export.xlsx", file_types=None):
        """Open native file dialog to pick a save path."""
        try:
            if self.window and hasattr(self.window, "create_file_dialog"):
                import webview
                file_filter = ()
                if file_types:
                    file_filter = tuple(file_types) if isinstance(file_types, (list, tuple)) else (str(file_types),)
                res = self.window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename, file_types=file_filter)
                if res and len(res) > 0:
                    return res[0] if isinstance(res, (list, tuple)) else str(res)
                return ""

            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.asksaveasfilename(
                title=title,
                initialfile=default_filename,
                filetypes=file_types or [("All Files", "*.*")]
            )
            root.destroy()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_save_file]: {e}")
            return ""

    def pick_folder(self, title="Select Folder"):
        """Open native folder dialog."""
        try:
            if self.window and hasattr(self.window, "create_file_dialog"):
                import webview
                res = self.window.create_file_dialog(webview.FileDialog.FOLDER)
                if res and len(res) > 0:
                    return res[0]
                return ""

            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            chosen = filedialog.askdirectory(title=title)
            root.destroy()
            return chosen or ""
        except Exception as e:
            print(f"[Error in pick_folder]: {e}")
            return ""

    # --- Tool Launcher: Image Check GUI ---
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

            tools_dir = os.path.join(config.BASE_DIR, "tools")
            src_tools_dir = os.path.join(config.BASE_DIR, "src", "tools")
            candidates = [
                os.path.join(src_tools_dir, "imagecheckgui.py"),
                os.path.join(tools_dir, "imagecheckgui.py"),
                os.path.join(config.BASE_DIR, "imagecheckgui.py"),
            ]
            script_path = next((c for c in candidates if os.path.exists(c)), None)
            if not script_path:
                return {"success": False, "error": "imagecheckgui.py was not found in tools directory."}

            subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path))
            return {"success": True, "message": f"Image Check GUI launched from {os.path.basename(script_path)}."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Fuzzy Lookup Tool Engine ---
    _fuzzy_state = {
        "running": False,
        "processed": 0,
        "total": 0,
        "elapsed": 0,
        "status": "idle",
        "output_path": "",
        "error": ""
    }

    def get_fuzzy_status(self):
        return {"success": True, **self._fuzzy_state}

    def generate_fuzzy_template(self, save_path=""):
        try:
            if not save_path:
                save_path = self.pick_save_file(
                    title="Save Fuzzy Lookup Template",
                    default_filename="fuzzy_lookup_input_template.xlsx",
                    file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
                )
            if not save_path:
                return {"success": False, "cancelled": True}

            wb = openpyxl.Workbook()
            sheet = wb.active
            sheet.title = "FuzzyLookupInput"
            sheet.append(["NAME", "C/O", "ADDRESS", "MOBILE NUMBER"])
            sheet.append(["", "", "", ""])
            sheet.freeze_panes = "A2"

            widths = [28, 28, 42, 18]
            for idx, width in enumerate(widths, start=1):
                col = openpyxl.utils.get_column_letter(idx)
                sheet.column_dimensions[col].width = width

            wb.save(save_path)
            return {"success": True, "path": save_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_fuzzy_lookup(self, input_path="", output_path="", threshold=0.85, top_n=5):
        if self._fuzzy_state["running"]:
            return {"success": False, "error": "Fuzzy lookup is already currently running."}

        try:
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
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    output_path = os.path.join(input_dir, f"fuzzy_lookup_results_{ts}.xlsx")

            try:
                threshold = float(threshold)
            except Exception:
                threshold = 0.85
            threshold = max(0.0, min(1.0, threshold))

            try:
                top_n = int(top_n)
            except Exception:
                top_n = 5
            top_n = max(1, min(200, top_n))

            self._fuzzy_state["running"] = True
            self._fuzzy_state["processed"] = 0
            self._fuzzy_state["total"] = 0
            self._fuzzy_state["elapsed"] = 0
            self._fuzzy_state["status"] = "Preparing consumer database..."
            self._fuzzy_state["output_path"] = output_path
            self._fuzzy_state["error"] = ""

            def _normalize_fuzzy_text(value):
                text = str(value or "").upper()
                text = re.sub(r"[^A-Z0-9 ]+", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return text

            def _normalize_mobile_10(value):
                digits = re.sub(r"\D", "", str(value or ""))
                if len(digits) == 12 and digits.startswith("91"):
                    digits = digits[2:]
                return digits if len(digits) == 10 else ""

            def _tokenize_for_lookup(text):
                return [t for t in _normalize_fuzzy_text(text).split(" ") if len(t) >= 2]

            def _fast_text_similarity(a, b):
                if not a or not b:
                    return 0.0
                tokens_a = set(_tokenize_for_lookup(a))
                tokens_b = set(_tokenize_for_lookup(b))

                def token_sim(x, y):
                    if rapidfuzz_fuzz is not None:
                        return float(rapidfuzz_fuzz.ratio(x, y)) / 100.0
                    return SequenceMatcher(None, x, y).ratio()

                if tokens_a:
                    covered = 0
                    for ta in tokens_a:
                        best = 0.0
                        for tb in tokens_b:
                            s = token_sim(ta, tb)
                            if s > best:
                                best = s
                        if best >= 0.80:
                            covered += 1
                    coverage_input = covered / len(tokens_a)
                else:
                    coverage_input = 0.0

                if rapidfuzz_fuzz is not None:
                    ratio_score = float(rapidfuzz_fuzz.ratio(a, b))
                    sort_score = float(rapidfuzz_fuzz.token_sort_ratio(a, b))
                    partial_score = float(rapidfuzz_fuzz.partial_ratio(a, b))
                    set_score = float(rapidfuzz_fuzz.token_set_ratio(a, b))
                    blended = (0.20 * ratio_score) + (0.20 * sort_score) + (0.25 * partial_score) + (0.35 * set_score)
                    adjusted = blended * (0.55 + (0.90 * coverage_input))
                    return min(100.0, adjusted)
                return SequenceMatcher(None, a, b).ratio() * 100.0

            def _worker():
                start_time = time.time()
                try:
                    db_profiles = utils.get_all_consumer_profiles()
                    if not db_profiles:
                        self._fuzzy_state["error"] = "No consumer data found. Please update consumer database first."
                        return

                    prepped_db = []
                    mobile_index = defaultdict(set)
                    prefix_index = defaultdict(set)
                    token_index = defaultdict(set)

                    for idx, row in enumerate(db_profiles):
                        db_name = str(row.get("name", ""))
                        db_address = str(row.get("address", ""))
                        db_combined_raw = f"{db_name} {db_address}".strip()
                        combined_norm = _normalize_fuzzy_text(db_combined_raw)
                        combined_tokens = set(_tokenize_for_lookup(combined_norm))
                        mobile_norm = _normalize_mobile_10(row.get("mobile_number", ""))

                        prepped_db.append({
                            "consumer_id": str(row.get("consumer_id", "")),
                            "name": db_name,
                            "address": db_address,
                            "mobile_number": str(row.get("mobile_number", "")),
                            "mobile_norm": mobile_norm,
                            "combined_norm": combined_norm,
                            "tokens": combined_tokens,
                        })

                        if mobile_norm:
                            mobile_index[mobile_norm].add(idx)

                        for tok in combined_tokens:
                            if len(tok) >= 3:
                                prefix_index[tok[:3]].add(idx)
                            if len(tok) >= 4:
                                token_index[tok].add(idx)

                    wb_in = openpyxl.load_workbook(input_path)
                    sh_in = wb_in.active
                    rows = list(sh_in.iter_rows(values_only=True))
                    if not rows:
                        raise ValueError("Input Excel sheet is empty.")

                    header_map = {
                        "name": "name",
                        "co": "co",
                        "c/o": "co",
                        "careof": "co",
                        "address": "address",
                        "mobile": "mobile",
                        "mobilenumber": "mobile",
                        "mobile number": "mobile",
                    }

                    first_row = rows[0]
                    idx_map = {}
                    for i, v in enumerate(first_row):
                        if v is None:
                            continue
                        key = str(v).strip().lower().replace("_", " ")
                        key = " ".join(key.split())
                        compact = key.replace(" ", "")
                        mapped = header_map.get(key) or header_map.get(compact)
                        if mapped:
                            idx_map[mapped] = i

                    has_headers = "name" in idx_map and "address" in idx_map
                    data_rows = rows[1:] if has_headers else rows
                    self._fuzzy_state["total"] = len(data_rows)
                    self._fuzzy_state["status"] = "Performing fuzzy matching..."

                    def _get_input_value(row_vals, field, fallback_idx):
                        idx = idx_map.get(field, fallback_idx)
                        if idx is None or idx >= len(row_vals):
                            return ""
                        val = row_vals[idx]
                        return "" if val is None else str(val).strip()

                    out_wb = openpyxl.Workbook()
                    out_sh = out_wb.active
                    out_sh.title = "FuzzyLookupResults"
                    out_headers = [
                        "Input Name",
                        "Input C/O",
                        "Input Address",
                        "Input Mobile",
                        "Matched Consumer ID",
                        "Matched Name",
                        "Matched Address",
                        "Matched Mobile",
                        "Combined Text Match %",
                        "Mobile Exact Match %",
                        "Final Score %",
                        "Match Type",
                        "Rank",
                    ]
                    out_sh.append(out_headers)

                    for in_row in data_rows:
                        self._fuzzy_state["processed"] += 1
                        self._fuzzy_state["elapsed"] = int(time.time() - start_time)

                        if not in_row:
                            continue

                        input_name = _get_input_value(in_row, "name", 0)
                        input_co = _get_input_value(in_row, "co", 1)
                        input_address = _get_input_value(in_row, "address", 2)
                        input_mobile = _get_input_value(in_row, "mobile", 3)

                        if not (input_name or input_co or input_address or input_mobile):
                            continue

                        input_combined = _normalize_fuzzy_text(f"{input_name} {input_co} {input_address}")
                        input_mobile_norm = _normalize_mobile_10(input_mobile)
                        input_tokens = [t for t in _tokenize_for_lookup(input_combined) if len(t) >= 3]

                        candidate_ids = set()
                        if input_mobile_norm:
                            candidate_ids.update(mobile_index.get(input_mobile_norm, set()))

                        for tok in input_tokens[:6]:
                            candidate_ids.update(prefix_index.get(tok[:3], set()))

                        longest_tokens = sorted({t for t in input_tokens if len(t) >= 4}, key=len, reverse=True)[:4]
                        for tok in longest_tokens:
                            candidate_ids.update(token_index.get(tok, set()))

                        if not candidate_ids and input_tokens:
                            for tok in input_tokens:
                                candidate_ids.update(prefix_index.get(tok[:3], set()))

                        if not candidate_ids:
                            candidate_ids = set(range(len(prepped_db)))

                        candidates = []
                        for cand_idx in candidate_ids:
                            db_row = prepped_db[cand_idx]
                            text_score = 0.0
                            if input_combined and db_row["combined_norm"]:
                                if input_tokens and db_row["tokens"]:
                                    overlap = len(set(input_tokens).intersection(db_row["tokens"]))
                                    if overlap == 0 and (not input_mobile_norm or db_row["mobile_norm"] != input_mobile_norm):
                                        continue
                                text_score = _fast_text_similarity(input_combined, db_row["combined_norm"])

                            mobile_score = 100.0 if (input_mobile_norm and db_row["mobile_norm"] == input_mobile_norm) else 0.0
                            final_score = max(text_score, mobile_score)

                            if text_score >= (threshold * 100.0) or mobile_score == 100.0:
                                candidates.append({
                                    "db": db_row,
                                    "text_score": text_score,
                                    "mobile_score": mobile_score,
                                    "final_score": final_score,
                                })

                        candidates.sort(key=lambda x: (x["final_score"], x["text_score"], x["mobile_score"]), reverse=True)
                        candidates = candidates[:top_n]

                        if not candidates:
                            out_sh.append([
                                input_name, input_co, input_address, input_mobile,
                                "", "", "", "",
                                "0.00", "0.00", "0.00", "No Match", ""
                            ])
                            continue

                        rank = 1
                        for c in candidates:
                            db_row = c["db"]
                            if c["mobile_score"] == 100.0 and c["text_score"] >= (threshold * 100.0):
                                match_type = "Both"
                            elif c["mobile_score"] == 100.0:
                                match_type = "Mobile Exact"
                            else:
                                match_type = "Fuzzy Text"

                            out_sh.append([
                                input_name, input_co, input_address, input_mobile,
                                db_row["consumer_id"], db_row["name"], db_row["address"], db_row["mobile_number"],
                                f"{c['text_score']:.2f}", f"{c['mobile_score']:.2f}", f"{c['final_score']:.2f}",
                                match_type, rank
                            ])
                            rank += 1

                    widths = [24, 24, 36, 16, 18, 26, 36, 16, 20, 18, 14, 14, 10]
                    for idx, width in enumerate(widths, start=1):
                        col = openpyxl.utils.get_column_letter(idx)
                        out_sh.column_dimensions[col].width = width
                    out_sh.freeze_panes = "A2"

                    out_wb.save(output_path)
                    self._fuzzy_state["status"] = "Complete"
                except Exception as ex:
                    self._fuzzy_state["error"] = str(ex)
                    self._fuzzy_state["status"] = "Error"
                finally:
                    self._fuzzy_state["running"] = False

            threading.Thread(target=_worker, daemon=True).start()
            return {"success": True, "output_path": output_path}
        except Exception as e:
            self._fuzzy_state["running"] = False
            return {"success": False, "error": str(e)}

    # --- Consumer Database Import & Template ---
    def generate_consumer_template(self, save_path=""):
        try:
            if not save_path:
                save_path = self.pick_save_file(
                    title="Save Consumer Data Template",
                    default_filename="consumer_data_template.xlsx",
                    file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
                )
            if not save_path:
                return {"success": False, "cancelled": True}

            wb = openpyxl.Workbook()
            sheet = wb.active
            sheet.title = "ConsumerData"
            headers = [
                "CONSUMER ID",
                "METER NO",
                "NAME",
                "ADDRESS",
                "MOBILE NUMBER",
                "CONTRACTUAL LOAD",
                "CLASS",
            ]
            sheet.append(headers)
            sheet.append(["", "", "", "", "", "", ""])
            sheet.freeze_panes = "A2"

            widths = [18, 16, 28, 36, 18, 18, 14]
            for idx, width in enumerate(widths, start=1):
                col = openpyxl.utils.get_column_letter(idx)
                sheet.column_dimensions[col].width = width

            wb.save(save_path)
            return {"success": True, "path": save_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_consumer_data(self, file_path=""):
        try:
            if not file_path:
                file_path = self.pick_file(
                    title="Select Consumer Data Excel",
                    file_types=[("Excel Files (*.xlsx;*.xls)", "*.xlsx;*.xls")]
                )
            if not file_path:
                return {"success": False, "cancelled": True}

            d = {}
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active

            header_map = {
                "consumer id": "consumer_id",
                "consumerid": "consumer_id",
                "meter no": "meter_no",
                "meterno": "meter_no",
                "name": "name",
                "address": "address",
                "mobile number": "mobile_number",
                "mobilenumber": "mobile_number",
                "mobile": "mobile_number",
                "contractual load": "contractual_load",
                "contractualload": "contractual_load",
                "class": "class",
            }

            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return {"success": False, "error": "Excel sheet is empty."}

            first_row = rows[0]
            index_map = {}
            for idx, val in enumerate(first_row):
                if val is None:
                    continue
                key = str(val).strip().lower().replace("_", " ")
                key = " ".join(key.split())
                key_compact = key.replace(" ", "")
                mapped = header_map.get(key) or header_map.get(key_compact)
                if mapped:
                    index_map[mapped] = idx

            has_headers = "consumer_id" in index_map and "meter_no" in index_map
            data_rows = rows[1:] if has_headers else rows

            def get_val(row_vals, field, fallback_idx):
                idx = index_map.get(field, fallback_idx)
                if idx is None or idx >= len(row_vals):
                    return ""
                val = row_vals[idx]
                if val is None:
                    return ""
                if isinstance(val, float) and val.is_integer():
                    return str(int(val)).strip()
                return str(val).strip()

            for row in data_rows:
                if not row:
                    continue
                cid = get_val(row, "consumer_id", 0)
                meter_no = get_val(row, "meter_no", 1)
                if not cid or not meter_no:
                    continue

                mobile = re.sub(r"\D", "", get_val(row, "mobile_number", 4))
                if len(mobile) == 12 and mobile.startswith("91"):
                    mobile = mobile[2:]

                d[cid] = {
                    "meter_no": meter_no,
                    "name": get_val(row, "name", 2),
                    "address": get_val(row, "address", 3),
                    "mobile_number": mobile,
                    "contractual_load": get_val(row, "contractual_load", 5),
                    "class": get_val(row, "class", 6),
                }

            if not d:
                return {"success": False, "error": "No valid consumer records found in file."}

            utils.update_meter_mapping(d)
            return {"success": True, "count": len(d)}
        except Exception as e:
            return {"success": False, "error": str(e)}

