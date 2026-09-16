"""
OSD (Outstanding Dues & No Dues Certificate) Domain Service
Handles single consumer OSD checks, concurrent bulk verification batches,
progress tracking, and report generation (Excel & CSV).
"""

import os
import re
import csv
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

try:
    from core import config, utils, live_osd_service
except ImportError:
    import config, utils, live_osd_service


class OSDService:
    def __init__(self):
        self._lock = threading.Lock()
        self._bulk_thread = None
        self._cancel_requested = False
        self._bulk_state = {
            "running": False,
            "processed": 0,
            "total": 0,
            "current_cid": "",
            "results": [],
            "error": "",
            "cancelled": False,
            "start_time": 0,
            "completed_time": 0
        }

    # =========================================================================
    # Consumer ID Extraction & Parsing
    # =========================================================================
    @staticmethod
    def extract_consumer_ids(input_data: Any) -> List[str]:
        """
        Extracts valid unique 9-digit consumer IDs from various input formats:
        raw string (pasted text with newlines/commas/spaces), list of strings,
        or file path (.txt, .csv, .xlsx, .xls).
        Preserves original order.
        """
        raw_ids = []

        if isinstance(input_data, list):
            for item in input_data:
                cleaned = str(item).strip()
                matches = re.findall(r"\b\d{9}\b", cleaned)
                raw_ids.extend(matches)

        elif isinstance(input_data, str):
            clean_str = input_data.strip()
            # If it looks like a local file path
            if os.path.exists(clean_str) and os.path.isfile(clean_str):
                ext = os.path.splitext(clean_str)[1].lower()
                if ext in [".xlsx", ".xls"]:
                    try:
                        openpyxl = utils.get_openpyxl()
                        wb = openpyxl.load_workbook(clean_str, read_only=True, data_only=True)
                        sheet = wb.active
                        for row in sheet.iter_rows(values_only=True):
                            for cell in row:
                                if cell is not None:
                                    matches = re.findall(r"\b\d{9}\b", str(cell).strip())
                                    raw_ids.extend(matches)
                        wb.close()
                    except Exception:
                        pass
                elif ext in [".csv", ".txt", ".tsv"]:
                    try:
                        with open(clean_str, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            matches = re.findall(r"\b\d{9}\b", content)
                            raw_ids.extend(matches)
                    except Exception:
                        pass
            else:
                # Raw text string pasted by user
                matches = re.findall(r"\b\d{9}\b", clean_str)
                raw_ids.extend(matches)

        # Deduplicate while strictly preserving insertion order
        seen = set()
        unique_ids = []
        for cid in raw_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)

        return unique_ids

    # =========================================================================
    # Single Consumer OSD
    # =========================================================================
    def get_single_osd(self, consumer_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches live OSD data for a single consumer."""
        clean_id = str(consumer_id).strip()
        if not re.match(r"^\d{9}$", clean_id):
            return {"success": False, "error": f"Invalid Consumer ID '{clean_id}'. Must be a 9-digit number."}

        return live_osd_service.get_live_osd_data(
            clean_id,
            include_pdf_base64=True,
            force_refresh=force_refresh
        )

    # =========================================================================
    # Bulk Verification Batch Engine
    # =========================================================================
    def start_bulk_osd(self, consumer_ids_input: Any, auto_download_pdf: bool = False, max_workers: int = 3) -> Dict[str, Any]:
        """
        Starts a background verification job for a list of consumer IDs.
        Uses a bounded thread pool (3 workers) to maintain high throughput
        while being safe with portal rate limits.
        """
        with self._lock:
            if self._bulk_state["running"]:
                return {"success": False, "error": "A bulk verification job is already running."}

            consumer_ids = self.extract_consumer_ids(consumer_ids_input)
            if not consumer_ids:
                return {"success": False, "error": "No valid 9-digit Consumer IDs found."}

            self._cancel_requested = False
            self._bulk_state = {
                "running": True,
                "processed": 0,
                "total": len(consumer_ids),
                "current_cid": consumer_ids[0],
                "results": [],
                "error": "",
                "cancelled": False,
                "start_time": time.time(),
                "completed_time": 0
            }

            self._bulk_thread = threading.Thread(
                target=self._run_bulk_worker,
                args=(consumer_ids, auto_download_pdf, max_workers),
                daemon=True
            )
            self._bulk_thread.start()

            return {
                "success": True,
                "total": len(consumer_ids),
                "message": f"Started bulk check for {len(consumer_ids)} consumers."
            }

    def _run_bulk_worker(self, consumer_ids: List[str], auto_download_pdf: bool, max_workers: int):
        """Worker thread executing bulk requests concurrently."""
        download_dir = None
        if auto_download_pdf:
            download_dir = os.path.join(config.BASE_DIR, "downloads_osd")
            os.makedirs(download_dir, exist_ok=True)

        def _fetch_one(cid: str) -> Dict[str, Any]:
            if self._cancel_requested:
                return {"consumerId": cid, "status": "Cancelled", "error": "User cancelled"}
            try:
                res = live_osd_service.get_live_osd_data(cid, include_pdf_base64=False, force_refresh=False)
                if res.get("success") and res.get("data"):
                    d = res["data"]
                    item = {
                        "consumerId": d.get("consumerId", cid),
                        "name": d.get("name", "N/A"),
                        "address": d.get("address", "N/A"),
                        "office": d.get("office", "N/A"),
                        "connectionStatus": d.get("connectionStatus", "N/A"),
                        "connDate": d.get("connDate", "N/A"),
                        "osd": float(d.get("osd", 0.0) or 0.0),
                        "lpsc": float(d.get("lpsc", 0.0) or 0.0),
                        "totalDues": float(d.get("totalDues", 0.0) or 0.0),
                        "isLive": bool(d.get("isLive", False)),
                        "isDeemed": bool(d.get("isDeemed", False)),
                        "isTempDisconnected": bool(d.get("isTempDisconnected", False)),
                        "isDisconnected": bool(d.get("isDisconnected", False)),
                        "status": "Success",
                        "error": ""
                    }
                    return item
                else:
                    return {
                        "consumerId": cid,
                        "name": "N/A",
                        "address": "N/A",
                        "office": "N/A",
                        "connectionStatus": "N/A",
                        "connDate": "N/A",
                        "osd": 0.0,
                        "lpsc": 0.0,
                        "totalDues": 0.0,
                        "status": "Failed",
                        "error": res.get("error", "Failed to retrieve verification records")
                    }
            except Exception as e:
                return {
                    "consumerId": cid,
                    "name": "N/A",
                    "address": "N/A",
                    "office": "N/A",
                    "connectionStatus": "N/A",
                    "connDate": "N/A",
                    "osd": 0.0,
                    "lpsc": 0.0,
                    "totalDues": 0.0,
                    "status": "Failed",
                    "error": str(e)
                }

        results_map = {}
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 5))) as executor:
            future_to_cid = {executor.submit(_fetch_one, cid): cid for cid in consumer_ids}
            for future in as_completed(future_to_cid):
                cid = future_to_cid[future]
                if self._cancel_requested:
                    break
                try:
                    res_item = future.result()
                except Exception as ex:
                    res_item = {
                        "consumerId": cid,
                        "name": "N/A",
                        "address": "N/A",
                        "office": "N/A",
                        "connectionStatus": "N/A",
                        "connDate": "N/A",
                        "docType": "ERROR",
                        "osd": 0.0,
                        "lpsc": 0.0,
                        "totalDues": 0.0,
                        "status": "Failed",
                        "error": str(ex)
                    }

                with self._lock:
                    results_map[cid] = res_item
                    self._bulk_state["processed"] += 1
                    self._bulk_state["current_cid"] = cid
                    self._bulk_state["results"].append(res_item)

        with self._lock:
            # Order once at completion according to original consumer_ids
            self._bulk_state["results"] = [
                results_map[c] for c in consumer_ids if c in results_map
            ]
            self._bulk_state["running"] = False
            self._bulk_state["completed_time"] = time.time()
            if self._cancel_requested:
                self._bulk_state["cancelled"] = True

    def get_bulk_status(self) -> Dict[str, Any]:
        """Returns live status snapshot of the bulk verification job."""
        with self._lock:
            state = dict(self._bulk_state)
            state["results"] = list(self._bulk_state["results"])
            return {"success": True, **state}

    def cancel_bulk(self) -> Dict[str, Any]:
        """Cancels an ongoing bulk verification run."""
        with self._lock:
            if not self._bulk_state["running"]:
                return {"success": True, "message": "No job currently running."}
            self._cancel_requested = True
            self._bulk_state["cancelled"] = True
            return {"success": True, "message": "Bulk check cancellation requested."}

    # =========================================================================
    # Report Export Engine (Excel & CSV)
    # =========================================================================
    def export_excel(self, results: List[Dict[str, Any]], save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Exports verification results to a beautifully formatted Excel (.xlsx) file
        matching corporate audit standards.
        """
        try:
            if not results:
                return {"success": False, "error": "No records to export."}

            if not save_path:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                save_path = os.path.join(default_dir, f"Consumer_Dues_Report_{ts}.xlsx")

            openpyxl = utils.get_openpyxl()
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Dues Verification Report"
            ws.views.sheetView[0].showGridLines = True

            # Styles
            title_font = Font(name="Segoe UI", size=14, bold=True, color="1E293B")
            sub_font = Font(name="Segoe UI", size=9, color="64748B")
            hdr_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
            hdr_fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")
            data_font = Font(name="Segoe UI", size=10, color="0F172A")
            bold_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
            green_font = Font(name="Segoe UI", size=10, bold=True, color="047857")
            red_font = Font(name="Segoe UI", size=10, bold=True, color="B91C1C")
            amber_font = Font(name="Segoe UI", size=10, bold=True, color="B45309")

            thin_border = Border(
                left=Side(style="thin", color="E2E8F0"),
                right=Side(style="thin", color="E2E8F0"),
                top=Side(style="thin", color="E2E8F0"),
                bottom=Side(style="thin", color="E2E8F0")
            )

            # Title Block
            ws["A1"] = "Consumer Outstanding Dues & Verification Report"
            ws["A1"].font = title_font
            ws["A2"] = f"Generated via Verification Studio • Date: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')} • Total Records: {len(results)}"
            ws["A2"].font = sub_font

            # Table Headers
            headers = [
                "#", "Consumer ID", "Consumer Name", "Service Location Address",
                "Office / Sub-Division", "Connection Status", "Date of Connection",
                "OSD (Rs)", "LPSC (Rs)", "Total Dues (Rs)", "Status"
            ]

            header_row = 4
            for col_idx, h_text in enumerate(headers, start=1):
                cell = ws.cell(row=header_row, column=col_idx, value=h_text)
                cell.font = hdr_font
                cell.fill = hdr_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[header_row].height = 26

            # Populate Rows
            total_osd = 0.0
            total_lpsc = 0.0
            total_payable = 0.0

            curr_row = header_row + 1
            for idx, r in enumerate(results, start=1):
                osd_val = float(r.get("osd", 0.0) or 0.0)
                lpsc_val = float(r.get("lpsc", 0.0) or 0.0)
                tot_val = float(r.get("totalDues", 0.0) or (osd_val + lpsc_val))
                conn_status = str(r.get("connectionStatus", "N/A")).strip().upper()

                total_osd += osd_val
                total_lpsc += lpsc_val
                total_payable += tot_val

                row_vals = [
                    idx,
                    str(r.get("consumerId", "")),
                    str(r.get("name", "N/A")),
                    str(r.get("address", "N/A")),
                    str(r.get("office", "N/A")),
                    conn_status,
                    str(r.get("connDate", "-")),
                    osd_val,
                    lpsc_val,
                    tot_val,
                    str(r.get("status", "Success"))
                ]

                fill_color = "F8FAFC" if idx % 2 == 0 else "FFFFFF"
                row_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

                for c_idx, val in enumerate(row_vals, start=1):
                    c = ws.cell(row=curr_row, column=c_idx, value=val)
                    c.font = data_font
                    c.fill = row_fill
                    c.border = thin_border

                    if c_idx == 1:
                        c.alignment = Alignment(horizontal="center")
                    elif c_idx == 2:
                        c.alignment = Alignment(horizontal="center")
                        c.font = bold_font
                    elif c_idx in [8, 9, 10]:
                        c.number_format = "#,##0.00"
                        c.alignment = Alignment(horizontal="right")
                        if c_idx == 10:
                            c.font = red_font if tot_val > 0 else green_font
                    elif c_idx == 6:
                        c.alignment = Alignment(horizontal="center")
                        upper_status = conn_status.upper()
                        if "DEEMED" in upper_status:
                            c.font = amber_font
                        elif "TEMP" in upper_status:
                            c.font = amber_font
                        elif "DISCONNECT" in upper_status or "DISCONN" in upper_status:
                            c.font = red_font
                        elif "LIVE" in upper_status or "CONNECTED" in upper_status:
                            c.font = green_font

                ws.row_dimensions[curr_row].height = 20
                curr_row += 1

            # Summary Totals Row
            summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
            for c_idx in range(1, len(headers) + 1):
                c = ws.cell(row=curr_row, column=c_idx)
                c.fill = summary_fill
                c.border = thin_border
                c.font = bold_font
                if c_idx == 5:
                    c.value = "TOTAL AMOUNT PAYABLE (RS):"
                    c.alignment = Alignment(horizontal="right")
                elif c_idx == 8:
                    c.value = total_osd
                    c.number_format = "#,##0.00"
                    c.alignment = Alignment(horizontal="right")
                elif c_idx == 9:
                    c.value = total_lpsc
                    c.number_format = "#,##0.00"
                    c.alignment = Alignment(horizontal="right")
                elif c_idx == 10:
                    c.value = total_payable
                    c.number_format = "#,##0.00"
                    c.alignment = Alignment(horizontal="right")
                    c.font = red_font if total_payable > 0 else green_font
            ws.row_dimensions[curr_row].height = 24

            # Auto Column Widths
            col_widths = {
                1: 6,   # #
                2: 16,  # Consumer ID
                3: 28,  # Name
                4: 38,  # Address
                5: 30,  # Office
                6: 20,  # Connection Status
                7: 18,  # Date
                8: 14,  # OSD
                9: 14,  # LPSC
                10: 16, # Total Dues
                11: 12  # Status
            }
            for col_idx, w in col_widths.items():
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                ws.column_dimensions[col_letter].width = w

            wb.save(save_path)
            return {"success": True, "path": save_path, "total_records": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_csv(self, results: List[Dict[str, Any]], save_path: Optional[str] = None) -> Dict[str, Any]:
        """Exports verification results to standard CSV file."""
        try:
            if not results:
                return {"success": False, "error": "No records to export."}

            if not save_path:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                save_path = os.path.join(default_dir, f"Consumer_Dues_Report_{ts}.csv")

            headers = [
                "Consumer ID", "Name", "Address", "Office",
                "OSD (Rs)", "LPSC (Rs)", "Total Dues (Rs)", "Connection Status",
                "Date of Connection", "Status"
            ]

            with open(save_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in results:
                    writer.writerow([
                        r.get("consumerId", ""),
                        r.get("name", "N/A"),
                        r.get("address", "N/A"),
                        r.get("office", "N/A"),
                        f"{float(r.get('osd', 0.0) or 0.0):.2f}",
                        f"{float(r.get('lpsc', 0.0) or 0.0):.2f}",
                        f"{float(r.get('totalDues', 0.0) or 0.0):.2f}",
                        r.get("connectionStatus", "N/A"),
                        r.get("connDate", "-"),
                        r.get("status", "Success")
                    ])

            return {"success": True, "path": save_path, "total_records": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_template(save_path: Optional[str] = None) -> Dict[str, Any]:
        """Generates an empty Excel template for bulk consumer ID input."""
        try:
            if not save_path:
                default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                save_path = os.path.join(default_dir, "Bulk_Consumer_ID_Template.xlsx")

            openpyxl = utils.get_openpyxl()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Consumer_IDs"

            ws.append(["CONSUMER_ID", "NOTES / REMARKS"])
            ws.append(["300055035", "Sample 9-digit Consumer ID"])
            ws.column_dimensions["A"].width = 22
            ws.column_dimensions["B"].width = 30

            wb.save(save_path)
            return {"success": True, "path": save_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
