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

# Patch numpy attributes if newer numpy is present so openpyxl doesn't crash on import
try:
    import numpy as _np
    if not hasattr(_np, 'short'):
        _np.short = _np.int16
    if not hasattr(_np, 'ushort'):
        _np.ushort = _np.uint16
    if not hasattr(_np, 'int_'):
        _np.int_ = _np.int64
    if not hasattr(_np, 'uint_'):
        _np.uint_ = _np.uint64
except Exception:
    pass

import openpyxl

try:
    from core import config, database, utils, tariff_manager, live_osd_service
except ImportError:
    import config, database, utils, tariff_manager, live_osd_service

class AppAPI:
    """
    Python-to-JavaScript RPC bridge exposed to PyWebView window.
    All methods return JSON-serializable dictionaries or primitives.
    """

    _indexing_state = {"running": False, "scanned": 0, "total": 0, "elapsed": 0}
    _update_state = {"status": "idle", "downloaded": 0, "total": 0, "percent": 0, "error": None, "installer_path": None}

    def __init__(self, window=None):
        self.window = window

    def set_window(self, window):
        self.window = window

    # --- System & Settings ---
    def get_app_info(self):
        # Check if cache is missing FIRST and launch background recounts.
        # The get_total_image_count() / get_consumer_count() calls below will
        # return 0 instantly when no cache exists (no blocking query).
        # The background threads will do the heavy COUNT(*) and push the real
        # values to the UI via evaluate_js.
        needs_image_recount = database.get_info_value("cached_total_images", None) is None
        needs_consumer_recount = database.get_info_value("cached_consumer_count", None) is None

        if needs_image_recount:
            def _bg_recount_images():
                try:
                    import time
                    time.sleep(1.0) # Allow initial UI rendering and RPCs to finish first
                    c = database.get_total_image_count(force_recount=True)
                    if self.window:
                        self.window.evaluate_js(f"if (typeof updateAppCounts === 'function') {{ updateAppCounts({c}, null); }}")
                except Exception:
                    pass
            threading.Thread(target=_bg_recount_images, daemon=True).start()

        if needs_consumer_recount:
            def _bg_recount_consumers():
                try:
                    import time
                    time.sleep(1.5) # Stagger so they do not compete for disk I/O
                    c = database.get_consumer_count(force_recount=True)
                    if self.window:
                        self.window.evaluate_js(f"if (typeof updateAppCounts === 'function') {{ updateAppCounts(null, {c}); }}")
                except Exception:
                    pass
            threading.Thread(target=_bg_recount_consumers, daemon=True).start()

        # These return cached value instantly, or 0 if no cache yet
        total_images = database.get_total_image_count()
        consumer_count = database.get_consumer_count()

        folders = []
        primary_path = config.IMAGE_FOLDER
        folders.append({
            "path": primary_path,
            "accessible": os.path.exists(primary_path),
            "is_primary": True
        })
        for p in database.get_additional_folders():
            folders.append({
                "path": p,
                "accessible": os.path.exists(p),
                "is_primary": False
            })

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
            # Support both normalized (dir_id -> directories) schema and legacy (full_path) schema
            try:
                cur.execute("""
                    SELECT i.date_original, i.mru, d.dir_path, i.filename 
                    FROM images i 
                    JOIN directories d ON i.dir_id = d.id 
                    WHERE i.consumer_id = ? 
                    ORDER BY i.date_iso DESC
                """, (cid,))
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                # Legacy table fallback if directories table doesn't exist or column differs
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
                    "rounded_assessment": math.ceil(net_assessment)
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
                    "ed_percent": ed_percent, "ed": total_ed, "gross": gross_bill,
                    "months": round(months, 4),
                    "rounded_months": rounded_months,
                    "units_per_month": round(units_per_month, 2),
                    "pf": pf,
                    "lf": lf,
                    "load_kva": round(load_kva, 3),
                    "rounded_load": rounded_load,
                    "normal_monthly_energy": round(normal_monthly_charge, 2),
                    "normal_total_energy": round(normal_total_charge, 2),
                    "fixed_charge_rate": cat_data.get("fixed_charge", 0.0),
                    "normal_fc": round(normal_fc, 2),
                    "days": days,
                    "hours": hours
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
                    "rounded_assessment": math.ceil(net),
                    "breakdown": {
                        "days": b["days"],
                        "hours": b["hours"],
                        "load_kva": b["load_kva"],
                        "pf": b["pf"],
                        "lf": b["lf"],
                        "units": b["units"],
                        "months": b["months"],
                        "rounded_months": b["rounded_months"],
                        "units_per_month": b["units_per_month"],
                        "normal_monthly_energy": b["normal_monthly_energy"],
                        "normal_total_energy": b["normal_total_energy"],
                        "penal_energy": b["energy"],
                        "fixed_rate": b["fixed_charge_rate"],
                        "rounded_load": b["rounded_load"],
                        "normal_fc": b["normal_fc"],
                        "penal_fc": b["fixed"],
                        "ed_percent": round(b["ed_percent"] * 100, 2),
                        "ed_amount": b["ed"],
                        "gross": b["gross"]
                    }
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

    def calculate_theft_reverse_load(self, p):
        """Calculate expected connected load given a target assessed amount, days, hours, and tariff."""
        try:
            target_amount = float(p.get("target_amount", 0.0))
            if target_amount <= 0:
                return {"success": False, "error": "Target assessment amount must be greater than 0"}

            hours = min(24.0, max(0.1, float(p.get("hours", 24.0))))
            days = max(1, int(p.get("days", 365)))
            category = p.get("category", "")
            consumer_type = p.get("consumer_type", "Consumer")

            adj_e = float(p.get("adj_energy", 0.0))
            adj_f = float(p.get("adj_fixed", 0.0))
            adj_ed = float(p.get("adj_ed", 0.0))
            target_gross = target_amount + (adj_e + adj_f + adj_ed)

            def test_load(load_kva):
                calc_payload = {
                    "category": category,
                    "consumer_type": consumer_type,
                    "load": load_kva,
                    "load_unit": "kVA",
                    "days": days,
                    "hours": hours,
                    "adj_energy": 0,
                    "adj_fixed": 0,
                    "adj_ed": 0
                }
                res = self.calculate_theft(calc_payload)
                if res.get("success"):
                    return res["result"]["gross_bill"]
                return 0.0

            # Binary search for matching load in kVA
            low, high = 0.01, 2000.0
            for _ in range(60):
                mid = (low + high) / 2.0
                g = test_load(mid)
                if g < target_gross:
                    low = mid
                else:
                    high = mid

            load_kva = round(mid, 3)
            load_kw = round(load_kva * 0.85, 3)

            # Verification forward calculation
            verify_payload = {
                "category": category,
                "consumer_type": consumer_type,
                "load": load_kva,
                "load_unit": "kVA",
                "days": days,
                "hours": hours,
                "adj_energy": adj_e,
                "adj_fixed": adj_f,
                "adj_ed": adj_ed
            }
            verify_res = self.calculate_theft(verify_payload)
            ver = verify_res.get("result", {}) if verify_res.get("success") else {}

            return {
                "success": True,
                "load_kva": load_kva,
                "load_kw": load_kw,
                "target_amount": target_amount,
                "resulting_gross": ver.get("gross_bill", 0),
                "resulting_net": ver.get("net_assessment", 0),
                "assessed_units": ver.get("assessed_units", 0),
                "hours": hours,
                "days": days
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
                    "installer_url": data.get("installer_url") or data.get("download_url", "")
                }
            return {"success": False, "error": "Failed to connect to update server."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_self_update(self, installer_url=""):
        """Download installer in background and stage Windows installer execution."""
        if AppAPI._update_state.get("status") == "downloading":
            return {"success": True, "message": "Download already in progress."}

        AppAPI._update_state = {
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

                import tempfile
                filename = os.path.basename(target_url.split("?")[0]) or "SpotImageViewer_Setup.exe"
                temp_dir = tempfile.gettempdir()
                dest_path = os.path.join(temp_dir, filename)

                def _prog(dl, tot):
                    AppAPI._update_state["downloaded"] = dl
                    AppAPI._update_state["total"] = tot
                    AppAPI._update_state["percent"] = int((dl / tot) * 100) if tot else 0

                utils.download_file_with_progress(target_url, dest_path, _prog)

                AppAPI._update_state["status"] = "ready"
                AppAPI._update_state["percent"] = 100
                AppAPI._update_state["installer_path"] = dest_path

                # Launch installer helper script which waits for current PID to exit
                current_pid = os.getpid()
                utils.launch_windows_installer(dest_path, current_pid)
            except Exception as e:
                AppAPI._update_state["status"] = "error"
                AppAPI._update_state["error"] = str(e)

        threading.Thread(target=_worker, daemon=True).start()
        return {"success": True}

    def get_update_progress(self):
        """Return live download progress status for self update."""
        return dict(AppAPI._update_state)

    def exit_for_update(self):
        """Close window and terminate application so the staged installer can run."""
        def _delayed_exit():
            time.sleep(1.0)
            if self.window:
                try:
                    self.window.destroy()
                except Exception:
                    pass
            os._exit(0)
        threading.Thread(target=_delayed_exit, daemon=True).start()
        return {"success": True}

    # --- Search History ---
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

    def add_network_folder(self, path=""):
        try:
            if not path:
                path = self.pick_folder(title="Select Folder to Add")
            if not path:
                return {"success": False, "cancelled": True}

            if not os.path.exists(path):
                return {"success": False, "error": "Folder path does not exist or is not accessible"}
            folders = database.get_additional_folders()
            if path not in folders:
                folders.append(path)
                database.save_additional_folders(folders)
            return {"success": True, "path": path}
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

    # --- System & Image Indexing ---
    def start_indexing(self):
        if self._indexing_state["running"]:
            return {"success": False, "error": "Indexing already running"}
        
        self._indexing_state["running"] = True
        self._indexing_state["scanned"] = 0
        self._indexing_state["total"] = 0
        self._indexing_state["files_seen"] = 0
        self._indexing_state["elapsed"] = 0
        self._indexing_state["speed"] = 0
        self._indexing_state["eta_seconds"] = None
        self._indexing_state["current_folder"] = ""
        self._indexing_state["error"] = None
        
        def _index():
            start = time.time()
            total_inserted = 0
            scanned_files_count = 0
            try:
                # 0. Ensure schema is fully up-to-date
                database.init_db()

                # 1. Dynamically fetch registered folders
                additional_folders = database.get_additional_folders()
                folders = [config.IMAGE_FOLDER] + (additional_folders or [])
                unique_folders = []
                for f in folders:
                    if f and os.path.exists(f) and os.path.normpath(f) not in [os.path.normpath(u) for u in unique_folders]:
                        unique_folders.append(f)

                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=OFF;")

                cursor.execute("DELETE FROM images")
                cursor.execute("DELETE FROM directories")
                conn.commit()

                # In-memory directory lookup cache to eliminate repeated SELECT queries
                dir_cache = {}
                next_dir_id = 1

                # Check if existing directories table has autoincrement id
                cursor.execute("SELECT MAX(id) FROM directories")
                max_id_row = cursor.fetchone()
                if max_id_row and max_id_row[0]:
                    next_dir_id = max_id_row[0] + 1

                batch_data = []
                BATCH_SIZE = 5000

                for folder in unique_folders:
                    self._indexing_state["current_folder"] = os.path.basename(folder) or folder
                    for root_dir, dirs, files in os.walk(folder):
                        if not files:
                            continue

                        # Resolve directory ID via in-memory cache
                        if root_dir not in dir_cache:
                            cursor.execute("INSERT OR IGNORE INTO directories (dir_path) VALUES (?)", (root_dir,))
                            cursor.execute("SELECT id FROM directories WHERE dir_path = ?", (root_dir,))
                            row = cursor.fetchone()
                            if row:
                                dir_cache[root_dir] = row[0]
                            else:
                                dir_cache[root_dir] = next_dir_id
                                next_dir_id += 1
                        dir_id = dir_cache[root_dir]

                        for filename in files:
                            scanned_files_count += 1
                            try:
                                if len(filename) < 25:
                                    continue
                                if not filename[:8].isdigit():
                                    continue

                                date_orig = filename[:8]
                                try:
                                    dt = datetime.strptime(date_orig, "%d%m%Y")
                                    date_iso = dt.strftime("%Y-%m-%d")
                                except ValueError:
                                    continue

                                mru = filename[8:16]
                                cid = filename[16:25]

                                batch_data.append((cid, date_orig, date_iso, mru, filename, dir_id))

                                if len(batch_data) >= BATCH_SIZE:
                                    cursor.executemany(
                                        "INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)",
                                        batch_data
                                    )
                                    conn.commit()
                                    total_inserted += len(batch_data)
                                    batch_data = []
                                    elapsed = max(1, int(time.time() - start))
                                    speed = int(total_inserted / elapsed)
                                    self._indexing_state["scanned"] = total_inserted
                                    self._indexing_state["total"] = total_inserted
                                    self._indexing_state["files_seen"] = scanned_files_count
                                    self._indexing_state["elapsed"] = elapsed
                                    self._indexing_state["speed"] = speed
                            except Exception:
                                continue

                if batch_data:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)",
                        batch_data
                    )
                    conn.commit()
                    total_inserted += len(batch_data)

                cursor.execute("ANALYZE;")
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
                database.set_info_value("cached_total_images", total_inserted)

                elapsed = max(1, int(time.time() - start))
                speed = int(total_inserted / elapsed) if total_inserted else 0
                self._indexing_state["scanned"] = total_inserted
                self._indexing_state["total"] = total_inserted
                self._indexing_state["files_seen"] = scanned_files_count
                self._indexing_state["elapsed"] = elapsed
                self._indexing_state["speed"] = speed
            except Exception as e:
                print(f"[Error in Indexing Worker]: {e}", flush=True)
                self._indexing_state["error"] = str(e)
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

            # Search in project workspace directory first, then fallback paths
            current_dir = os.path.dirname(os.path.abspath(__file__))  # src/bridge
            src_dir = os.path.dirname(current_dir)                    # src
            project_root = os.path.dirname(src_dir)                   # repo root
            
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

    # --- Fuzzy Lookup Shared Helpers & Prepped DB Cache ---
    _cached_prepped_fuzzy_db = None
    _cached_fuzzy_lock = threading.Lock()

    @staticmethod
    def _normalize_fuzzy_text(value):
        text = str(value or "").upper()
        text = re.sub(r"[^A-Z0-9 ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _strip_fuzzy_prefixes(value):
        text = AppAPI._normalize_fuzzy_text(value)
        pattern = r"^(?:C\s*O|S\s*O|D\s*O|W\s*O|CARE\s*OF|SON\s*OF|DAUGHTER\s*OF|WIFE\s*OF|LATE|LT|SRI|SMT|MD|MR|MRS|DR)\s+"
        while True:
            subbed = re.sub(pattern, "", text)
            if subbed == text:
                break
            text = subbed.strip()
        return text

    @staticmethod
    def _extract_co_and_name(text, is_address=False):
        if not text:
            return "", ""

        ADDR_KEYWORDS = {
            "VILL", "VILLAGE", "PO", "P O", "PS", "P S", "DIST", "DISTRICT",
            "PIN", "PINCODE", "ROAD", "STREET", "LANE", "SARANI", "PARA",
            "WARD", "HOLDING", "HOUSE", "NEAR", "BEHIND", "OPP", "OPPOSITE",
            "GP", "PANCHAYAT", "MUNICIPALITY", "BLOCK", "SECTOR", "PLOT", "FLAT", "APARTMENT"
        }

        if is_address:
            parts = [p.strip() for p in re.split(r"[,;]+", str(text)) if p.strip()]
            if parts:
                first_seg = AppAPI._normalize_fuzzy_text(parts[0])
                pattern = r"\b(?:S\s*O|D\s*O|W\s*O|C\s*O|CARE\s*OF|SON\s*OF|DAUGHTER\s*OF|WIFE\s*OF)\b"
                m = re.search(pattern, first_seg)
                if m:
                    co_part = AppAPI._strip_fuzzy_prefixes(first_seg[m.end():])
                    remaining_addr = ", ".join(parts[1:]).strip() if len(parts) > 1 else ""
                    return AppAPI._strip_fuzzy_prefixes(remaining_addr), co_part

                first_words = first_seg.split()
                has_addr_kw = any(w in ADDR_KEYWORDS for w in first_words)
                has_digit = any(w.isdigit() for w in first_words)
                if 2 <= len(first_words) <= 4 and not has_addr_kw and not has_digit:
                    co_part = AppAPI._strip_fuzzy_prefixes(first_seg)
                    remaining_addr = ", ".join(parts[1:]).strip() if len(parts) > 1 else ""
                    return AppAPI._strip_fuzzy_prefixes(remaining_addr), co_part

        cleaned = AppAPI._normalize_fuzzy_text(text)
        pattern = r"\b(?:S\s*O|D\s*O|W\s*O|C\s*O|CARE\s*OF|SON\s*OF|DAUGHTER\s*OF|WIFE\s*OF)\b"
        m = re.search(pattern, cleaned)
        if m:
            main_part = AppAPI._strip_fuzzy_prefixes(cleaned[:m.start()])
            co_part = AppAPI._strip_fuzzy_prefixes(cleaned[m.end():])
            return main_part, co_part

        return AppAPI._strip_fuzzy_prefixes(cleaned), ""

    @staticmethod
    def _normalize_mobile_10(value):
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        return digits if len(digits) == 10 else ""

    @staticmethod
    def _tokenize_for_lookup(text):
        return [t for t in AppAPI._normalize_fuzzy_text(text).split(" ") if len(t) >= 2]

    @staticmethod
    def _token_level_sim(s1, s2):
        t1 = [w for w in s1.split() if len(w) >= 2]
        t2 = [w for w in s2.split() if len(w) >= 2]
        if not t1 or not t2:
            return 0.0
        matches1 = sum(1 for w1 in t1 if any(SequenceMatcher(None, w1, w2).ratio() >= 0.80 for w2 in t2))
        matches2 = sum(1 for w2 in t2 if any(SequenceMatcher(None, w2, w1).ratio() >= 0.80 for w1 in t1))
        return ((matches1 / len(t1)) + (matches2 / len(t2))) / 2.0

    @staticmethod
    def _match_single_field(a, b):
        a_clean = AppAPI._strip_fuzzy_prefixes(a)
        b_clean = AppAPI._strip_fuzzy_prefixes(b)
        if not a_clean or not b_clean:
            return 0.0
        if a_clean == b_clean:
            return 100.0

        if rapidfuzz_fuzz is not None:
            ratio = float(rapidfuzz_fuzz.ratio(a_clean, b_clean))
            token_sort = float(rapidfuzz_fuzz.token_sort_ratio(a_clean, b_clean))
            token_set = float(rapidfuzz_fuzz.token_set_ratio(a_clean, b_clean))
            partial = float(rapidfuzz_fuzz.partial_ratio(a_clean, b_clean))
            score = (0.25 * ratio) + (0.35 * token_set) + (0.25 * token_sort) + (0.15 * partial)
        else:
            seq = SequenceMatcher(None, a_clean, b_clean).ratio() * 100.0
            tok = AppAPI._token_level_sim(a_clean, b_clean) * 100.0
            sub = 0.0
            if a_clean in b_clean and len(a_clean.split()) >= 2:
                sub = 90.0
            elif b_clean in a_clean and len(b_clean.split()) >= 2:
                sub = 90.0
            score = max(seq, tok, sub)
        return min(100.0, score)

    def _get_prepped_fuzzy_db(self):
        with AppAPI._cached_fuzzy_lock:
            if AppAPI._cached_prepped_fuzzy_db is not None:
                return AppAPI._cached_prepped_fuzzy_db

            db_profiles = utils.get_all_consumer_profiles()
            if not db_profiles:
                return None

            prepped_db = []
            mobile_index = defaultdict(set)
            prefix_index = defaultdict(set)
            token_index = defaultdict(set)

            for idx, row in enumerate(db_profiles):
                db_name = str(row.get("name", "") or "").strip()
                db_address = str(row.get("address", "") or "").strip()
                db_name_main, db_name_co = self._extract_co_and_name(db_name, is_address=False)
                db_addr_main, db_addr_co = self._extract_co_and_name(db_address, is_address=True)

                db_combined_raw = f"{db_name} {db_address}".strip()
                combined_norm = self._normalize_fuzzy_text(db_combined_raw)
                combined_tokens = set(self._tokenize_for_lookup(combined_norm))
                mobile_norm = self._normalize_mobile_10(row.get("mobile_number", ""))

                prepped_db.append({
                    "consumer_id": str(row.get("consumer_id", "") or ""),
                    "name": db_name,
                    "address": db_address,
                    "name_main": db_name_main,
                    "name_co": db_name_co,
                    "addr_main": db_addr_main,
                    "addr_co": db_addr_co,
                    "mobile_number": str(row.get("mobile_number", "") or ""),
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

            cache_data = (prepped_db, mobile_index, prefix_index, token_index)
            AppAPI._cached_prepped_fuzzy_db = cache_data
            return cache_data

    def _score_single_fuzzy_query(self, input_name, input_co, input_address, input_mobile, threshold=0.85, top_n=5):
        prepped = self._get_prepped_fuzzy_db()
        if not prepped:
            return []

        prepped_db, mobile_index, prefix_index, token_index = prepped

        input_name = str(input_name or "").strip()
        input_co = str(input_co or "").strip()
        input_address = str(input_address or "").strip()
        input_mobile = str(input_mobile or "").strip()

        if not (input_name or input_co or input_address or input_mobile):
            return []

        input_combined = self._normalize_fuzzy_text(f"{input_name} {input_co} {input_address}")
        input_mobile_norm = self._normalize_mobile_10(input_mobile)
        input_tokens = [t for t in self._tokenize_for_lookup(input_combined) if len(t) >= 3]

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
            mobile_score = 100.0 if (input_mobile_norm and db_row["mobile_norm"] == input_mobile_norm) else 0.0

            # Token overlap pre-check if mobile does not match
            if input_tokens and db_row["tokens"] and mobile_score != 100.0:
                overlap = len(set(input_tokens).intersection(db_row["tokens"]))
                if overlap == 0:
                    continue

            # 1. Evaluate Name match
            name_targets = [t for t in [db_row["name"], db_row["name_main"], db_row["addr_co"]] if t]
            name_score = max((self._match_single_field(input_name, t) for t in name_targets), default=0.0) if input_name else 0.0

            # 2. Evaluate C/O match
            co_targets = [t for t in [db_row["name_co"], db_row["addr_co"], db_row["name"]] if t]
            co_score = max((self._match_single_field(input_co, t) for t in co_targets), default=0.0) if input_co else 0.0

            # Cross-check: If input_name matches DB C/O or vice-versa
            if input_name and db_row["name_co"]:
                name_score = max(name_score, self._match_single_field(input_name, db_row["name_co"]))
            if input_co and db_row["name_main"]:
                co_score = max(co_score, self._match_single_field(input_co, db_row["name_main"]))

            # 3. Calculate Identity Score
            if input_name and input_co:
                if name_score >= 60.0 and co_score >= 60.0:
                    identity_score = (name_score * 0.60) + (co_score * 0.40)
                elif name_score >= 75.0:
                    identity_score = (name_score * 0.85) + (co_score * 0.15)
                elif co_score >= 80.0:
                    identity_score = (co_score * 0.70) + (name_score * 0.30)
                else:
                    identity_score = max(name_score, co_score * 0.70)
            elif input_name:
                identity_score = name_score
            elif input_co:
                identity_score = co_score
            else:
                identity_score = 0.0

            # 4. Evaluate Address match
            addr_targets = [t for t in [db_row["address"], db_row["addr_main"]] if t]
            address_score = max((self._match_single_field(input_address, t) for t in addr_targets), default=0.0) if input_address else 0.0

            # 5. Composite Scoring & Identity Gating
            if mobile_score == 100.0:
                final_score = 100.0 if identity_score >= 50.0 else max(95.0, identity_score)
            else:
                # GATE: If neither name nor C/O matches with >= 50%, candidate is disqualified!
                if (input_name or input_co) and identity_score < 50.0:
                    final_score = identity_score * 0.40
                else:
                    if input_address:
                        final_score = (identity_score * 0.60) + (address_score * 0.40)
                    else:
                        final_score = identity_score

            final_score = round(min(100.0, max(0.0, final_score)), 2)

            if final_score >= (threshold * 100.0) or mobile_score == 100.0:
                # Determine Relation: SELF vs RELATIVE
                # If input_co matched the DB owner's name strongly (>= 75%) and input_name didn't match as strongly, it's a RELATIVE
                if input_co and co_score >= 75.0 and name_score < co_score - 10.0:
                    relation = "RELATIVE"
                elif name_score >= 60.0:
                    relation = "SELF"
                elif input_co and co_score >= 70.0:
                    relation = "RELATIVE"
                else:
                    relation = "SELF" if name_score >= co_score else "RELATIVE"

                if mobile_score == 100.0 and final_score >= (threshold * 100.0):
                    match_type = "Both"
                elif mobile_score == 100.0:
                    match_type = "Mobile Exact"
                else:
                    match_type = "Fuzzy Identity"

                candidates.append({
                    "consumer_id": db_row["consumer_id"],
                    "name": db_row["name"],
                    "address": db_row["address"],
                    "mobile_number": db_row["mobile_number"],
                    "identity_score": round(identity_score, 2),
                    "name_score": round(name_score, 2),
                    "co_score": round(co_score, 2),
                    "address_score": round(address_score, 2),
                    "mobile_score": round(mobile_score, 2),
                    "final_score": final_score,
                    "match_type": match_type,
                    "relation": relation
                })

        candidates.sort(key=lambda x: (x["final_score"], x["identity_score"], x["mobile_score"]), reverse=True)
        return candidates[:top_n]

    def lookup_fuzzy_rows(self, rows, threshold=0.85, top_n=5):
        """
        Interactive synchronous API for 1 or more rows typed or pasted in UI.
        Returns immediate ranked candidates for inline rendering.
        """
        try:
            try:
                threshold = float(threshold)
            except Exception:
                threshold = 0.85
            threshold = max(0.0, min(1.0, threshold))

            try:
                top_n = int(top_n)
            except Exception:
                top_n = 5
            top_n = max(1, min(50, top_n))

            if not isinstance(rows, list) or not rows:
                return {"success": False, "error": "No input rows provided."}

            prepped = self._get_prepped_fuzzy_db()
            if not prepped:
                return {"success": False, "error": "Consumer database is empty. Please import consumer data first."}

            output_results = []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                in_name = str(item.get("name", "") or "").strip()
                in_co = str(item.get("co", "") or "").strip()
                in_address = str(item.get("address", "") or "").strip()
                in_mobile = str(item.get("mobile", "") or item.get("mobile_number", "") or "").strip()

                candidates = self._score_single_fuzzy_query(
                    input_name=in_name,
                    input_co=in_co,
                    input_address=in_address,
                    input_mobile=in_mobile,
                    threshold=threshold,
                    top_n=top_n
                )

                output_results.append({
                    "input": {
                        "name": in_name,
                        "co": in_co,
                        "address": in_address,
                        "mobile": in_mobile
                    },
                    "candidates": candidates
                })

            return {"success": True, "total_rows": len(output_results), "results": output_results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_fuzzy_lookup(self, input_path="", output_path="", threshold=0.85, top_n=5, include_live_osd=False):
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

            do_live_osd = bool(include_live_osd)

            self._fuzzy_state["running"] = True
            self._fuzzy_state["processed"] = 0
            self._fuzzy_state["total"] = 0
            self._fuzzy_state["elapsed"] = 0
            self._fuzzy_state["status"] = "Preparing consumer database..."
            self._fuzzy_state["output_path"] = output_path
            self._fuzzy_state["error"] = ""

            def _worker():
                start_time = time.time()
                try:
                    prepped = self._get_prepped_fuzzy_db()
                    if not prepped:
                        self._fuzzy_state["error"] = "No consumer data found. Please update consumer database first."
                        return

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
                        "care of": "co",
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
                        "Relation",
                        "Identity Match %",
                        "Name Match %",
                        "C/O Match %",
                        "Address Match %",
                        "Mobile Exact Match %",
                        "Final Score %",
                        "Match Type",
                        "Rank",
                    ]
                    if do_live_osd:
                        out_headers.extend([
                            "Live Connection Status",
                            "Live OSD (Rs)",
                            "Live LPSC (Rs)",
                            "Total Payable Dues (Rs)",
                            "Service Conn Date",
                            "Office Name",
                        ])
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

                        candidates = self._score_single_fuzzy_query(
                            input_name=input_name,
                            input_co=input_co,
                            input_address=input_address,
                            input_mobile=input_mobile,
                            threshold=threshold,
                            top_n=top_n
                        )

                        if not candidates:
                            empty_row = [
                                input_name, input_co, input_address, input_mobile,
                                "", "", "", "",
                                "-", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
                                "No Match", ""
                            ]
                            if do_live_osd:
                                empty_row.extend(["-", "0.00", "0.00", "0.00", "-", "-"])
                            out_sh.append(empty_row)
                            continue

                        rank = 1
                        for c in candidates:
                            c_cid = str(c["consumer_id"]).strip()
                            row_data = [
                                input_name, input_co, input_address, input_mobile,
                                c["consumer_id"], c["name"], c["address"], c["mobile_number"],
                                c.get("relation", "SELF"),
                                f"{c['identity_score']:.2f}", f"{c['name_score']:.2f}", f"{c['co_score']:.2f}",
                                f"{c['address_score']:.2f}", f"{c['mobile_score']:.2f}", f"{c['final_score']:.2f}",
                                c["match_type"], rank
                            ]

                            if do_live_osd:
                                osd_info = {"status": "-", "osd": 0.0, "lpsc": 0.0, "total": 0.0, "date": "-", "office": "-"}
                                if len(c_cid) == 9 and c_cid.isdigit():
                                    try:
                                        self._fuzzy_state["status"] = f"Fetching live OSD for CID {c_cid}..."
                                        live_res = live_osd_service.get_live_osd_data(c_cid)
                                        if live_res and live_res.get("success") and live_res.get("data"):
                                            ld = live_res["data"]
                                            osd_info = {
                                                "status": ld.get("connectionStatus", "-"),
                                                "osd": float(ld.get("osd", 0.0)),
                                                "lpsc": float(ld.get("lpsc", 0.0)),
                                                "total": float(ld.get("totalDues", 0.0)),
                                                "date": ld.get("connDate", "-"),
                                                "office": ld.get("office", "-"),
                                            }
                                    except Exception:
                                        pass

                                row_data.extend([
                                    osd_info["status"],
                                    f"{osd_info['osd']:.2f}",
                                    f"{osd_info['lpsc']:.2f}",
                                    f"{osd_info['total']:.2f}",
                                    osd_info["date"],
                                    osd_info["office"],
                                ])

                            out_sh.append(row_data)
                            rank += 1

                    widths = [24, 24, 36, 16, 18, 26, 36, 16, 14, 16, 14, 14, 16, 18, 14, 16, 10]
                    if do_live_osd:
                        widths.extend([22, 16, 16, 22, 18, 26])
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
            database.set_info_value("consumer_data_updated_at", datetime.now().strftime("%d-%m-%Y %H:%M"))
            AppAPI._cached_prepped_fuzzy_db = None
            return {"success": True, "count": len(d), "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_file_external(self, file_path=""):
        """Open any file or directory in default system application or explorer."""
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
        """Open web URL in user's default browser."""
        try:
            if not url:
                url = "https://github.com/Hackers-lab/SpotImageViewer"
            import webbrowser
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_database_folder(self):
        """Open database directory in Windows explorer."""
        return self.open_file_external(config.BASE_DIR)

    def export_consumer_data_file(self, dest_path=""):
        """Export current SQLite meter_mapping records into an Excel file and open it."""
        try:
            if not dest_path:
                dest_path = self.pick_save_file(
                    title="Export Consumer Master Records",
                    default_filename="consumer_master_export.xlsx",
                    file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
                )
            if not dest_path:
                return {"success": False, "cancelled": True}

            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT consumer_id, meter_no, name, address, mobile_number, contractual_load, class
                FROM meter_mapping
                ORDER BY consumer_id ASC
                """
            )
            rows = cursor.fetchall()
            conn.close()

            wb = openpyxl.Workbook()
            sheet = wb.active
            sheet.title = "ConsumerMaster"
            headers = [
                "CONSUMER ID", "METER NO", "NAME", "ADDRESS",
                "MOBILE NUMBER", "CONTRACTUAL LOAD", "CLASS"
            ]
            sheet.append(headers)

            for r in rows:
                sheet.append([
                    str(r[0] or ""), str(r[1] or ""), str(r[2] or ""),
                    str(r[3] or ""), str(r[4] or ""), str(r[5] or ""),
                    str(r[6] or "")
                ])

            sheet.freeze_panes = "A2"
            widths = [18, 16, 28, 36, 18, 18, 14]
            for idx, width in enumerate(widths, start=1):
                col = openpyxl.utils.get_column_letter(idx)
                sheet.column_dimensions[col].width = width

            wb.save(dest_path)
            # Open the exported excel file automatically
            self.open_file_external(dest_path)
            return {"success": True, "count": len(rows), "path": dest_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Low Consumption Audit Studio ---
    def get_low_consumption_session(self):
        """Retrieve saved low consumption audit session if exists."""
        session_file = os.path.join(config.BASE_DIR, "verification_session.json")
        try:
            if os.path.exists(session_file):
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"success": True, "data": data, "count": len(data)}
            return {"success": True, "data": [], "count": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    def save_low_consumption_session(self, data):
        """Save verification session state."""
        session_file = os.path.join(config.BASE_DIR, "verification_session.json")
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def parse_low_consumption_file(self, file_path=""):
        """Parse Excel file for low consumption audit."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File not found."}
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return {"success": False, "error": "Excel sheet is empty."}

            items = []
            # Check if row 0 looks like header
            start_idx = 0
            first_row_str = " ".join([str(c or "").lower() for c in rows[0]])
            if any(k in first_row_str for k in ["consumer", "cid", "meter", "unit", "cons"]):
                start_idx = 1

            for idx, r in enumerate(rows[start_idx:]):
                if not any(r):
                    continue
                cid = str(r[0] or "").strip()
                if not cid or cid.lower() in ("none", "nan"):
                    continue
                meter = str(r[1] or "").strip() if len(r) > 1 else ""
                unit = str(r[2] or "").strip() if len(r) > 2 else "0"
                items.append({
                    "id": idx,
                    "cid": cid,
                    "meter": meter,
                    "unit": unit,
                    "status": "PENDING",
                    "remarks": ""
                })

            if not items:
                return {"success": False, "error": "No valid consumer rows found in file."}

            self.save_low_consumption_session(items)
            return {"success": True, "data": items, "count": len(items)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_low_consumption_report(self, items):
        """Export audit report to CSV and open destination folder."""
        try:
            if not items:
                return {"success": False, "error": "No audit records to export."}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_file = os.path.join(config.BASE_DIR, f"Low_Consumption_Audit_{timestamp}.csv")
            fieldnames = ["id", "cid", "meter", "unit", "status", "remarks"]
            with open(dest_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(items)

            self.open_file_external(dest_file)
            return {"success": True, "file_path": dest_file, "count": len(items)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_system_clipboard(self):
        """Retrieve plain text from system clipboard using tkinter fallback."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            try:
                text = root.clipboard_get()
            except Exception:
                text = ""
            finally:
                root.destroy()
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e), "text": ""}

    # --- Live WBSEDCL OSD & Connection Status ---
    def get_live_osd(self, consumer_id, force_refresh=False):
        """
        Fetches live Outstanding Dues (OSD), LPSC surcharge, total payable dues,
        and connection status directly from WBSEDCL portal.
        """
        try:
            cid = str(consumer_id).strip()
            if not re.match(r"^\d{9}$", cid):
                return {"success": False, "error": f"Invalid Consumer ID '{cid}'. Must be a 9-digit number."}

            res = live_osd_service.get_live_osd_data(cid, include_pdf_base64=True, force_refresh=bool(force_refresh))
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_live_osd_pdf(self, consumer_id):
        """
        Fetches live OSD PDF and opens it in Windows default PDF viewer.
        """
        try:
            cid = str(consumer_id).strip()
            if not re.match(r"^\d{9}$", cid):
                return {"success": False, "error": "Invalid Consumer ID. Must be 9 digits."}

            pdf_bytes = live_osd_service.fetch_live_osd_pdf(cid)
            temp_dir = os.path.join(config.BASE_DIR, "temp_osd")
            os.makedirs(temp_dir, exist_ok=True)
            pdf_path = os.path.join(temp_dir, f"WBSEDCL_OSD_{cid}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            self.open_file_external(pdf_path)
            return {"success": True, "file_path": pdf_path}
        except Exception as e:
            return {"success": False, "error": str(e)}



