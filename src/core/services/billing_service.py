import math
try:
    from core import tariff_manager
except ImportError:
    import tariff_manager


class BillingService:
    """
    Core mathematical engine for energy billing, tariff calculations,
    and Section 135/126 electricity theft assessments.
    """

    @staticmethod
    def calculate_bill(p):
        """Calculates electricity bill based on WBSEDCL tariff schedules."""
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
                if days <= 0:
                    days = 1
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
                    if u <= 0:
                        break
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

            # MVCA (in ₹ per unit)
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

                    if u > 0:
                        slab = min(u, s1)
                        subsidy_amount += slab * 0.90
                        u -= slab
                    if u > 0:
                        slab = min(u, s2)
                        subsidy_amount += slab * 0.90
                        u -= slab
                    if u > 0:
                        slab = min(u, s3)
                        subsidy_amount += slab * 0.74
                        u -= slab
                    if u > 0:
                        subsidy_amount += u * 0.79
                    if phase == "1-Phase":
                        subsidy_amount += (10.0 * months_multiplier)

            ed_percent = 0.0
            for slab in cat_data.get("ed_slabs", []):
                if slab["limit"] is None or monthly_units <= slab["limit"]:
                    ed_percent = slab["rate"]
                    break

            ed_charge = (energy_charge + mvca_charge) * ed_percent
            gross_total = base_amount + meter_rent + mvca_charge + ed_charge

            # Rebates
            timely_rebate = 0.0
            epay_rebate = 0.0
            special_rebate = 0.0

            if p.get("rebate_timely", True):
                timely_rebate = energy_charge * 0.01

            if p.get("rebate_epay", True):
                epay_rebate = energy_charge * 0.01

            if p.get("rebate_special", False) and not is_tod:
                special_rebate = energy_charge * 0.05

            total_rebates = timely_rebate + epay_rebate + special_rebate + subsidy_amount
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

    @staticmethod
    def calculate_theft(p):
        """Calculates electricity theft assessment under Section 126/135."""
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
                if "slabs" in cat_data:
                    highest_rate = max(slab["rate"] for slab in cat_data["slabs"])
                elif "tod_slabs" in cat_data:
                    highest_rate = max(cat_data["tod_slabs"].values())
                normal_monthly_charge = units_per_month * highest_rate
            else:
                charge = 0.0
                u = units_per_month
                if "slabs" in cat_data:
                    for slab in cat_data["slabs"]:
                        if u <= 0:
                            break
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
            rounded_assessment = math.ceil(net_assessment)

            return {
                "success": True,
                "result": {
                    "assessed_units": total_units,
                    "months": round(months, 2),
                    "rounded_months": rounded_months,
                    "units_per_month": round(units_per_month, 2),
                    "penal_energy_charge": round(penal_energy_charge, 2),
                    "penal_fixed_charge": round(penal_fc, 2),
                    "ed_percentage": round(ed_percent * 100, 2),
                    "ed_amount": round(total_ed, 2),
                    "electricity_duty": round(total_ed, 2),
                    "gross_bill": round(gross_bill, 2),
                    "gross_assessment": round(gross_bill, 2),
                    "total_adjustments": round(total_adjustments, 2),
                    "net_assessment": round(net_assessment, 2),
                    "rounded_assessment": rounded_assessment,
                    "breakdown": {
                        "days": days,
                        "hours": hours,
                        "load_kva": round(load_kva, 3),
                        "pf": pf,
                        "lf": lf,
                        "units": total_units,
                        "months": round(months, 2),
                        "rounded_months": rounded_months,
                        "units_per_month": round(units_per_month, 2),
                        "normal_monthly_energy": round(normal_monthly_charge, 2),
                        "normal_total_energy": round(normal_total_charge, 2),
                        "penal_energy": round(penal_energy_charge, 2),
                        "fixed_rate": cat_data.get("fixed_charge", 0.0),
                        "rounded_load": round(rounded_load, 3),
                        "normal_fc": round(normal_fc, 2),
                        "penal_fc": round(penal_fc, 2),
                        "ed_percent": round(ed_percent * 100, 2),
                        "ed_amount": round(total_ed, 2),
                        "gross": round(gross_bill, 2)
                    }
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def calculate_theft_dual(cls, p):
        """Calculates both provisional and final assessments with comparison/relief analysis."""
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

            final_days = int(p.get("final_days", prov_days))
            final_hours = float(p.get("final_hours", prov_hours))

            adj_e = float(p.get("adj_energy", 0.0))
            adj_f = float(p.get("adj_fixed", 0.0))
            adj_ed = float(p.get("adj_ed", 0.0))
            total_adjustments = adj_e + adj_f + adj_ed

            pf = 0.85
            lf = cat_data.get("load_factor", 0.5 if "domestic" in cat.lower() else 0.75)

            def compute_assessment(days, hours):
                months = days / (365 / 12)
                units = round(load_kva * pf * lf * days * hours)
                upm = units / months if months > 0 else 0

                if cons_type == "Non-Consumer":
                    highest_rate = 0.0
                    if "slabs" in cat_data:
                        highest_rate = max(slab["rate"] for slab in cat_data["slabs"])
                    elif "tod_slabs" in cat_data:
                        highest_rate = max(cat_data["tod_slabs"].values())
                    normal_monthly_charge = upm * highest_rate
                else:
                    charge = 0.0
                    u = upm
                    if "slabs" in cat_data:
                        for slab in cat_data["slabs"]:
                            if u <= 0:
                                break
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
                penal_energy = normal_total_charge * 2

                rounded_load = max(1.0, load_kva)
                rounded_months = math.ceil(months)
                normal_fc = rounded_load * cat_data["fixed_charge"] * rounded_months
                penal_fc = normal_fc * 2

                ed_percent = 0.0
                for slab in cat_data.get("ed_slabs", []):
                    if slab["limit"] is None or upm <= slab["limit"]:
                        ed_percent = slab["rate"]
                        break
                ed = (penal_energy + penal_fc) * ed_percent
                gross = penal_energy + penal_fc + ed

                return {
                    "units": units,
                    "months": round(months, 2),
                    "rounded_months": rounded_months,
                    "upm": round(upm, 2),
                    "energy": round(penal_energy, 2),
                    "fixed": round(penal_fc, 2),
                    "ed_percent": ed_percent,
                    "ed": round(ed, 2),
                    "gross": round(gross, 2),
                    "load_kva": round(load_kva, 3),
                    "rounded_load": round(rounded_load, 3),
                    "pf": pf,
                    "lf": lf,
                    "units_per_month": round(upm, 2),
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

    @classmethod
    def calculate_theft_reverse_load(cls, p):
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
                res = cls.calculate_theft(calc_payload)
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
            verify_res = cls.calculate_theft(verify_payload)
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
