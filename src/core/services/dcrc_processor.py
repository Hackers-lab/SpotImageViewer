import os
import datetime
from core.services import dcrc_parser
from core import database


DEFAULT_STANDARD_RATES = {
    "1PH": {"DC": 65.0, "RC": 65.0, "DR": 130.0},
    "3PH": {"DC": 88.0, "RC": 88.0, "DR": 176.0}
}

# Known custom agency rates from historical PO contracts
DEFAULT_CUSTOM_AGENCY_RATES = {
    "LAIBAH": {
        "1PH": {"DC": 66.0, "RC": 66.0, "DR": 131.0},
        "3PH": {"DC": 89.0, "RC": 89.0, "DR": 177.0}
    }
}


def resolve_agency_for_zone_and_date(zone_name, payment_date_obj, zone_dict):
    """
    Finds the active agency for zone_name on payment_date_obj.
    zone_dict is { "K4S08MMR": [ {"start_date": date, "agency": "ABDUL MATIN"}, ... ] }
    Periods are assumed sorted by start_date.
    """
    if not zone_name or not payment_date_obj:
        return ""
    z_clean = str(zone_name).strip().upper()
    periods = zone_dict.get(z_clean)
    if not periods:
        return ""

    # Find latest period where start_date <= payment_date_obj
    assigned_agency = ""
    for p in periods:
        if payment_date_obj >= p["start_date"]:
            assigned_agency = p["agency"]
        else:
            break

    # If payment date is earlier than first period start date, default to the first period's agency
    if not assigned_agency and periods:
        assigned_agency = periods[0]["agency"]

    return assigned_agency


def process_dcrc_run(dcrc_file_paths, cash_file_paths, zone_file_path, consumer_master_file_path=None, custom_rates=None):
    """
    Executes the complete processing run:
    1. Parses Zone map from zone_file_path
    2. Parses Cash payments from cash_file_paths
    3. Parses Consumer master (from file if provided, else from local DB)
    4. Parses DCRC events from dcrc_file_paths
    5. Matches Doc Numbers, Zones, Phases, and Agencies
    6. Computes agency-wise 1PH/3PH matrix and PO bill totals
    7. Collects discrepancy/exception records
    """
    # 1. Parse Zone Map
    zone_info = dcrc_parser.parse_zones_file(zone_file_path) if zone_file_path and os.path.exists(zone_file_path) else {"zones": {}, "date_strings": []}
    zone_dict = zone_info.get("zones", {})

    # 2. Parse Cash Payments
    cash_primary = {}
    cash_fallback = {}
    for c_path in (cash_file_paths or []):
        if os.path.exists(c_path):
            p_map, f_map = dcrc_parser.parse_cash_payment_file(c_path)
            cash_primary.update(p_map)
            for k, docs in f_map.items():
                if k not in cash_fallback:
                    cash_fallback[k] = []
                cash_fallback[k].extend(docs)

    # 3. Parse Consumer Master (Authority for Zone/MRU and Phase)
    consumer_master = {}
    if consumer_master_file_path and os.path.exists(consumer_master_file_path):
        consumer_master = dcrc_parser.parse_consumer_master_file(consumer_master_file_path)
    else:
        # Fallback to local DB
        consumer_master = database.get_consumer_master_map()

    # 4. Parse DCRC Events
    all_dcrc_records = []
    for d_path in (dcrc_file_paths or []):
        if os.path.exists(d_path):
            recs = dcrc_parser.parse_dcrc_event_file(d_path)
            all_dcrc_records.extend(recs)

    # 5. Enrich each transaction
    rates_config = custom_rates or DEFAULT_CUSTOM_AGENCY_RATES
    enriched_records = []
    discrepancies = []

    for idx, rec in enumerate(all_dcrc_records):
        cid = rec["consumer_id"]
        ptype = rec["payment_type"]
        amt_str = rec["amount_str"]
        pdate = rec["payment_date"]
        pdate_obj = rec["payment_date_obj"]
        source_file = rec["source_file"]
        coll_agency = rec.get("coll_agency", "")

        # Composite key for doc matching
        key = f"{cid}-{amt_str}-{pdate}"
        doc_no = cash_primary.get(key, "")
        if not doc_no:
            # Check fallback
            fb_list = cash_fallback.get(f"{cid}-{amt_str}", [])
            if len(fb_list) == 1:
                doc_no = fb_list[0]

        # Online tagging
        is_online = ("ONLINE" in source_file.upper() or bool(coll_agency))
        if not doc_no and is_online:
            doc_no = coll_agency or "ONLINE"

        # Consumer master lookup (MRU and Phase)
        c_info = consumer_master.get(cid, {"mru": "", "phase": 1})
        zone = c_info.get("mru", "")
        phase = c_info.get("phase", 1)

        # Agency lookup
        agency = resolve_agency_for_zone_and_date(zone, pdate_obj, zone_dict) if zone else ""

        item = {
            "sl": idx + 1,
            "consumer_id": cid,
            "payment_type": ptype,
            "amount": rec["amount"],
            "amount_str": amt_str,
            "payment_date": pdate,
            "key": key,
            "doc_number": doc_no,
            "zone": zone,
            "agency": agency,
            "phase": phase,
            "is_online": is_online,
            "source_file": source_file
        }
        enriched_records.append(item)

        # Check for discrepancies
        issue = None
        if not doc_no and not is_online:
            issue = "Missing Document Number (Cash desk match not found)"
        elif not zone:
            issue = "Missing Zone (Consumer ID not in master or MRU empty)"
        elif not agency:
            issue = f"Unassigned Agency for Zone '{zone}' on {pdate}"

        if issue:
            discrepancies.append({
                "consumer_id": cid,
                "payment_type": ptype,
                "amount": amt_str,
                "payment_date": pdate,
                "zone": zone,
                "agency": agency,
                "issue": issue
            })

    # Sort records into standard billing parts:
    # 1PH DR -> 1PH DC -> 1PH RC -> 3PH DR -> 3PH DC -> 3PH RC
    type_priority = {"DR": 1, "DC": 2, "RC": 3}

    def record_sort_key(r):
        ph = 1 if r.get("phase") == 1 else 2
        pt = str(r.get("payment_type") or "").strip().upper()
        pt_prio = type_priority.get(pt, 9)
        pdate = r.get("payment_date_obj") or datetime.date.min
        cid = str(r.get("consumer_id") or "")
        return (ph, pt_prio, pdate, cid)

    enriched_records.sort(key=record_sort_key)
    for idx, r in enumerate(enriched_records, start=1):
        r["sl"] = idx

    # 6. Aggregate Agency Summary Matrix
    agency_groups = {}
    for r in enriched_records:
        ag = r["agency"] or "UNASSIGNED"
        ph = r["phase"]
        pt = r["payment_type"]

        if ag not in agency_groups:
            agency_groups[ag] = {
                "agency": ag,
                "1ph_dc": 0, "1ph_rc": 0, "1ph_dr": 0,
                "3ph_dc": 0, "3ph_rc": 0, "3ph_dr": 0,
            }

        if ph == 1:
            if pt == "DC": agency_groups[ag]["1ph_dc"] += 1
            elif pt == "RC": agency_groups[ag]["1ph_rc"] += 1
            elif pt == "DR": agency_groups[ag]["1ph_dr"] += 1
        elif ph == 3:
            if pt == "DC": agency_groups[ag]["3ph_dc"] += 1
            elif pt == "RC": agency_groups[ag]["3ph_rc"] += 1
            elif pt == "DR": agency_groups[ag]["3ph_dr"] += 1

    summary_rows = []
    grand_totals = {
        "1ph_dc": 0, "1ph_rc": 0, "1ph_dr": 0, "1ph_total": 0,
        "3ph_dc": 0, "3ph_rc": 0, "3ph_dr": 0, "3ph_total": 0,
        "total_records": 0,
        "total_amount": 0.0
    }

    # Sort agencies alphabetically (with UNASSIGNED last if present)
    sorted_agencies = sorted([a for a in agency_groups if a != "UNASSIGNED"])
    if "UNASSIGNED" in agency_groups:
        sorted_agencies.append("UNASSIGNED")

    for ag in sorted_agencies:
        g = agency_groups[ag]
        # Determine applicable rates
        ag_rates = rates_config.get(ag, DEFAULT_STANDARD_RATES)
        r_1ph_dc = ag_rates.get("1PH", {}).get("DC", 65.0)
        r_1ph_rc = ag_rates.get("1PH", {}).get("RC", 65.0)
        r_1ph_dr = ag_rates.get("1PH", {}).get("DR", 130.0)

        r_3ph_dc = ag_rates.get("3PH", {}).get("DC", 88.0)
        r_3ph_rc = ag_rates.get("3PH", {}).get("RC", 88.0)
        r_3ph_dr = ag_rates.get("3PH", {}).get("DR", 176.0)

        c_1_dc = g["1ph_dc"]
        c_1_rc = g["1ph_rc"]
        c_1_dr = g["1ph_dr"]

        c_3_dc = g["3ph_dc"]
        c_3_rc = g["3ph_rc"]
        c_3_dr = g["3ph_dr"]

        sub_1ph_dc = c_1_dc * r_1ph_dc
        sub_1ph_rc = c_1_rc * r_1ph_rc
        sub_1ph_dr = c_1_dr * r_1ph_dr

        sub_3ph_dc = c_3_dc * r_3ph_dc
        sub_3ph_rc = c_3_rc * r_3ph_rc
        sub_3ph_dr = c_3_dr * r_3ph_dr

        agency_total_amount = (sub_1ph_dc + sub_1ph_rc + sub_1ph_dr +
                               sub_3ph_dc + sub_3ph_rc + sub_3ph_dr)
        agency_total_count = (c_1_dc + c_1_rc + c_1_dr + c_3_dc + c_3_rc + c_3_dr)

        row_data = {
            "agency": ag,
            # 1 Phase
            "c_1ph_dc": c_1_dc, "r_1ph_dc": r_1ph_dc,
            "c_1ph_rc": c_1_rc, "r_1ph_rc": r_1ph_rc,
            "c_1ph_dr": c_1_dr, "r_1ph_dr": r_1ph_dr,
            # 3 Phase
            "c_3ph_dc": c_3_dc, "r_3ph_dc": r_3ph_dc,
            "c_3ph_rc": c_3_rc, "r_3ph_rc": r_3ph_rc,
            "c_3ph_dr": c_3_dr, "r_3ph_dr": r_3ph_dr,
            # Subtotals
            "total_count": agency_total_count,
            "total_amount": agency_total_amount,
            "total_dc": c_1_dc + c_3_dc,
            "total_rc": c_1_rc + c_3_rc,
            "total_dr": c_1_dr + c_3_dr,
        }
        summary_rows.append(row_data)

        # Add to Grand Totals
        grand_totals["1ph_dc"] += c_1_dc
        grand_totals["1ph_rc"] += c_1_rc
        grand_totals["1ph_dr"] += c_1_dr
        grand_totals["3ph_dc"] += c_3_dc
        grand_totals["3ph_rc"] += c_3_rc
        grand_totals["3ph_dr"] += c_3_dr
        grand_totals["total_amount"] += agency_total_amount

    grand_totals["1ph_total"] = grand_totals["1ph_dc"] + grand_totals["1ph_rc"] + grand_totals["1ph_dr"]
    grand_totals["3ph_total"] = grand_totals["3ph_dc"] + grand_totals["3ph_rc"] + grand_totals["3ph_dr"]
    grand_totals["total_records"] = grand_totals["1ph_total"] + grand_totals["3ph_total"]

    valid_dates = [r["payment_date_obj"] for r in all_dcrc_records if r.get("payment_date_obj")]
    if valid_dates:
        min_date = min(valid_dates).strftime("%d.%m.%Y")
        max_date = max(valid_dates).strftime("%d.%m.%Y")
        date_range_str = f"{min_date} to {max_date}"
    else:
        date_range_str = ""

    return {
        "success": True,
        "summary": summary_rows,
        "totals": grand_totals,
        "discrepancies": discrepancies,
        "records": enriched_records,
        "total_records_processed": len(enriched_records),
        "total_discrepancies": len(discrepancies),
        "zone_cutoffs": zone_info.get("date_strings", []),
        "date_range": date_range_str
    }
