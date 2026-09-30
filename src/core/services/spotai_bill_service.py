"""
SpotAI Bill Downloader & Batch Printing Service.
Handles SpotAI officer authentication (OTP dispatch/verification),
consumer billing history lookups, single & batch bill PDF downloading,
batch PDF merging, and direct Windows printing.
"""

import os
import re
import csv
import json
import base64
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

try:
    from core import config, utils
except ImportError:
    import config, utils

SPOTAI_HOST = "https://spotai.wbsedcl.in"
SECRET_KEY = "@FrTu^^&!#$%^/41"


def hk_encrypt(password_str: str) -> str:
    """SpotAI custom XOR + Latin1 + Base64 encryption."""
    key_len = len(SECRET_KEY)
    xor_chars = []
    for r in range(len(password_str)):
        c_code = ord(password_str[r])
        k_code = ord(SECRET_KEY[r % key_len])
        xor_chars.append(chr(c_code ^ k_code))
    xor_str = "".join(xor_chars)
    return base64.b64encode(xor_str.encode("latin1")).decode("utf-8")


class SpotAIBillService:
    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util import Retry

        self._lock = threading.Lock()
        self._bulk_thread = None
        self._cancel_requested = False

        # High-throughput persistent HTTP session with Keep-Alive connection pooling
        self._http = requests.Session()
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=retries)
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)
        
        # State tracking for batch download
        self._bulk_state = {
            "running": False,
            "processed": 0,
            "total": 0,
            "success_count": 0,
            "failed_count": 0,
            "current_cid": "",
            "results": [],
            "error": "",
            "cancelled": False,
            "start_time": 0,
            "completed_time": 0,
            "output_dir": "",
            "merged_pdf_path": "",
        }

        # Session storage path
        self._session_file = os.path.join(config.BASE_DIR, "spotai_session.json")
        self._session = self._load_saved_session()

    # =========================================================================
    # Session & Authentication Management
    # =========================================================================
    def _load_saved_session(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self._session_file):
                with open(self._session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("token"):
                        return data
        except Exception:
            pass
        return {}

    def _save_session_to_disk(self):
        try:
            with open(self._session_file, "w", encoding="utf-8") as f:
                json.dump(self._session, f, indent=2)
        except Exception:
            pass

    def get_session(self) -> Dict[str, Any]:
        with self._lock:
            if not self._session.get("token"):
                return {"authenticated": False}
            return {
                "authenticated": True,
                "username": self._session.get("username", ""),
                "token": self._session.get("token", ""),
                "off_code": self._session.get("off_code", ""),
                "off_name": self._session.get("off_name", ""),
                "name": self._session.get("name", ""),
                "designation": self._session.get("designation", ""),
            }

    def logout(self) -> Dict[str, Any]:
        with self._lock:
            self._session = {}
            if os.path.exists(self._session_file):
                try:
                    os.remove(self._session_file)
                except Exception:
                    pass
        return {"success": True}

    def request_otp(self, username: str, password: str) -> Dict[str, Any]:
        """Dispatches OTP to officer's registered mobile number."""
        import requests
        u = str(username).strip()
        p = str(password).strip()
        if not u or not p:
            return {"success": False, "error": "Username and password required"}

        enc_pw = hk_encrypt(p)
        payload = [{"username": u, "password": enc_pw}]
        url = f"{SPOTAI_HOST}/spotaiportal/spot_ai_portal_login"

        headers = {
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        }

        try:
            resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                res_json = res_json[0]

            code = str(res_json.get("code", ""))
            raw_msg = str(res_json.get("message") or res_json.get("error") or "")

            # If user was previously logged in on another machine/session, SpotAI logs them out
            # and requires a second submission. Automatically retry once.
            if "logged out" in raw_msg.lower() or "logout" in raw_msg.lower():
                time.sleep(0.5)
                retry_resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=15)
                retry_resp.raise_for_status()
                retry_json = retry_resp.json()
                if isinstance(retry_json, list) and len(retry_json) > 0:
                    retry_json = retry_json[0]
                retry_code = str(retry_json.get("code", ""))
                if retry_code == "200":
                    return {
                        "success": True,
                        "message": retry_json.get("message", "OTP dispatched"),
                        "auto_relogged": True
                    }
                else:
                    res_json = retry_json
                    code = retry_code

            if code == "200":
                return {"success": True, "message": res_json.get("message", "OTP dispatched")}
            else:
                return {
                    "success": False,
                    "error": res_json.get("message") or res_json.get("error") or f"Server returned code {code}"
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to connect to portal: {str(e)}"}

    def verify_otp(self, username: str, otp: str) -> Dict[str, Any]:
        """Verifies OTP and stores JWT token & officer profile."""
        import requests
        u = str(username).strip()
        o = str(otp).strip()
        if not u or not o:
            return {"success": False, "error": "Username and OTP required"}

        payload = [{"username": u, "otp": o}]
        url = f"{SPOTAI_HOST}/spotaiportal/spot_ai_portal_login"

        headers = {
            "Content-Type": "text/plain",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        }

        try:
            resp = requests.post(url, data=json.dumps(payload), headers=headers, timeout=15)
            resp.raise_for_status()
            res_json = resp.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                res_json = res_json[0]

            code = str(res_json.get("code", ""))
            msg = res_json.get("message")

            token = ""
            off_code = ""
            off_name = ""
            name = ""
            designation = ""

            if code == "200" and isinstance(msg, dict):
                token = msg.get("JWT_token") or msg.get("token", "")
                off_code = msg.get("off_code", "")
                off_name = msg.get("off_name", "")
                name = msg.get("name", "")
                designation = msg.get("designation", "")
            elif code == "200" and res_json.get("JWT_token"):
                token = res_json.get("JWT_token")
                off_code = res_json.get("off_code", "")
                off_name = res_json.get("off_name", "")
                name = res_json.get("name", "")
                designation = res_json.get("designation", "")

            if not token:
                return {
                    "success": False,
                    "error": str(msg) if msg else "Invalid OTP or session token not returned"
                }

            with self._lock:
                self._session = {
                    "username": u,
                    "token": token,
                    "off_code": off_code,
                    "off_name": off_name,
                    "name": name,
                    "designation": designation,
                    "login_time": datetime.now().isoformat()
                }
                self._save_session_to_disk()

            return {
                "success": True,
                "session": {
                    "username": u,
                    "off_code": off_code,
                    "off_name": off_name,
                    "name": name,
                    "designation": designation
                }
            }
        except Exception as e:
            return {"success": False, "error": f"OTP verification failed: {str(e)}"}

    # =========================================================================
    # Consumer ID Extraction Utility
    # =========================================================================
    @staticmethod
    def extract_consumer_ids(input_data: Any) -> List[str]:
        raw_ids = []
        if isinstance(input_data, list):
            for item in input_data:
                cleaned = str(item).strip()
                matches = re.findall(r"\b\d{9}\b", cleaned)
                raw_ids.extend(matches)
        elif isinstance(input_data, str):
            clean_str = input_data.strip()
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
                matches = re.findall(r"\b\d{9}\b", clean_str)
                raw_ids.extend(matches)

        seen = set()
        unique_ids = []
        for cid in raw_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)
        return unique_ids

    # =========================================================================
    # Master Column Definitions & Portal Fetching
    # =========================================================================
    COLUMN_DEFINITIONS = {
        "consumer_id": {"label": "Consumer ID", "field": "consumer_id"},
        "name": {"label": "Consumer Name", "field": "name"},
        "address": {"label": "Address", "field": "address"},
        "mobile": {"label": "Mobile No", "field": "mobile"},
        "meter_no": {"label": "Meter No", "field": "meter_no"},
        "class_desc": {"label": "Class / Category", "field": "class_desc"},
        "tariff": {"label": "Tariff / Phase", "field": "tariff"},
        "conn_status": {"label": "Connection Status", "field": "conn_status"},
        "conn_load": {"label": "Connected Load", "field": "conn_load"},
        "bill_month": {"label": "Bill Month", "field": "bill_month"},
        "invoice_no": {"label": "Invoice No", "field": "invoice_no"},
        "due_date": {"label": "Due Date", "field": "due_date"},
        "bill_amount": {"label": "Bill Amount (Rs)", "field": "bill_amount"},
        "osd_principal": {"label": "Total Principal OSD (Rs)", "field": "osd_principal"},
        "lpsc": {"label": "Current Live LPSC (Rs)", "field": "lpsc"},
        "total_dues": {"label": "Total Dues (OSD + LPSC) (Rs)", "field": "total_dues"},
        "last_pay_date": {"label": "Last Payment Date", "field": "last_pay_date"},
        "last_pay_amt": {"label": "Last Payment Amount (Rs)", "field": "last_pay_amt"},
        "last_pay_mode": {"label": "Last Payment Mode", "field": "last_pay_mode"},
        "status": {"label": "Download Status", "field": "status"},
        "file_path": {"label": "PDF File Path", "field": "file_path"},
        "error": {"label": "Error Details", "field": "error"},
    }

    DEFAULT_COLUMNS = [
        "consumer_id",
        "name",
        "bill_month",
        "invoice_no",
        "due_date",
        "bill_amount",
        "osd_principal",
        "lpsc",
        "total_dues",
        "status",
        "file_path",
        "error"
    ]

    def get_available_columns(self) -> List[Dict[str, str]]:
        """Returns the list of fixed columns available for Excel export customization."""
        return [{"id": k, "label": v["label"]} for k, v in self.COLUMN_DEFINITIONS.items()]

    def _fetch_portal_endpoint(self, cid: str, parameter: str, flag: str, printdoc: str = "") -> Dict[str, Any]:
        """Generic requester for /spotaiportal/con_dtls using reused Keep-Alive connection."""
        sess = self.get_session()
        if not sess.get("authenticated"):
            return {"success": False, "error": "Not authenticated"}

        payload = [{
            "username": sess["username"],
            "token": sess["token"],
            "off_code": sess["off_code"],
            "con_id": str(cid).strip(),
            "parameter": parameter,
            "flag": flag
        }]
        if printdoc:
            payload[0]["printdoc"] = str(printdoc).strip()

        url = f"{SPOTAI_HOST}/spotaiportal/con_dtls"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive"
        }

        try:
            resp = self._http.post(url, json=payload, headers=headers, timeout=20)
            resp.raise_for_status()
            res_json = resp.json()
            if isinstance(res_json, list) and len(res_json) > 0:
                res_json = res_json[0]

            code = str(res_json.get("code", ""))
            if code == "200":
                return {"success": True, "data": res_json.get("message")}
            return {"success": False, "error": res_json.get("message") or f"Server code {code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fetch_billing_history(self, consumer_id: str) -> Dict[str, Any]:
        """Fetches list of all bills/invoices for a consumer (parameter='BILLING', flag='B')."""
        res = self._fetch_portal_endpoint(consumer_id, "BILLING", "B")
        if res.get("success"):
            bills = res.get("data", [])
            if isinstance(bills, list):
                return {"success": True, "bills": bills}
            elif isinstance(bills, dict):
                return {"success": True, "bills": [bills]}
            return {"success": False, "error": "No billing records found"}
        return res

    def _fetch_all_consumer_data(self, cid: str, custom_columns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Concurrently queries BILLING, MASTER, OSD, and (if needed) PAYMENT for a single consumer.
        Returns a dictionary containing all extracted consumer, ledger, and billing info.
        """
        data_out = {
            "consumer_id": cid,
            "name": "-",
            "address": "-",
            "mobile": "-",
            "meter_no": "-",
            "class_desc": "-",
            "tariff": "-",
            "conn_status": "-",
            "conn_load": "-",
            "osd_principal": "0.00",
            "lpsc": "0.00",
            "total_dues": "0.00",
            "last_pay_date": "-",
            "last_pay_amt": "0.00",
            "last_pay_mode": "-",
            "bills": [],
            "billing_error": ""
        }

        # Check if payment history is required by selected columns
        need_payment = True
        if custom_columns is not None and len(custom_columns) > 0:
            need_payment = any(c in custom_columns for c in ["last_pay_date", "last_pay_amt", "last_pay_mode"])

        def _worker(param, flag):
            return param, self._fetch_portal_endpoint(cid, param, flag)

        tasks = [("BILLING", "B"), ("MASTER", "C"), ("OSD", "O")]
        if need_payment:
            tasks.append(("PAYMENT", "P"))

        results_map = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = [pool.submit(_worker, param, flag) for param, flag in tasks]
            for f in as_completed(futures):
                try:
                    param, res = f.result()
                    results_map[param] = res
                except Exception:
                    pass

        # 1. BILLING
        billing_res = results_map.get("BILLING", {})
        if billing_res.get("success"):
            b_list = billing_res.get("data", [])
            if isinstance(b_list, list):
                data_out["bills"] = b_list
            elif isinstance(b_list, dict):
                data_out["bills"] = [b_list]
        else:
            data_out["billing_error"] = billing_res.get("error", "Failed to retrieve billing")

        # 2. MASTER
        master_res = results_map.get("MASTER", {})
        master_dict = {}
        if master_res.get("success"):
            m_data = master_res.get("data")
            if isinstance(m_data, list) and len(m_data) > 0 and isinstance(m_data[0], dict):
                master_dict = m_data[0]
            elif isinstance(m_data, dict):
                master_dict = m_data

            data_out["name"] = str(master_dict.get("ZNAME") or "-").strip()
            data_out["address"] = str(master_dict.get("ZADDRESS") or "-").strip()
            data_out["mobile"] = str(master_dict.get("ZMOB_NO") or "-").strip()
            data_out["meter_no"] = str(master_dict.get("ZMET1") or "-").strip()
            data_out["class_desc"] = str(master_dict.get("ZCLASS_DESC") or "-").strip()
            data_out["tariff"] = str(master_dict.get("ZTARIFF") or "-").strip()
            data_out["conn_status"] = str(master_dict.get("ZCONN_STAT") or "-").strip()
            data_out["conn_load"] = str(master_dict.get("ZCONN_LOAD") or "-").strip()

        # 3. OSD & LPSC
        def _parse_float(val):
            try:
                return float(str(val).replace(",", "").strip())
            except (ValueError, TypeError):
                return 0.0

        osd_res = results_map.get("OSD", {})
        osd_principal = 0.0
        live_lpsc = 0.0

        if osd_res.get("success"):
            o_data = osd_res.get("data")
            osd_dict = o_data[0] if (isinstance(o_data, list) and len(o_data) > 0 and isinstance(o_data[0], dict)) else (o_data if isinstance(o_data, dict) else {})
            
            # T6: Gross Principal OSD
            t6 = osd_dict.get("T6")
            if isinstance(t6, list) and len(t6) > 0 and t6[0].get("AMT"):
                osd_principal = _parse_float(t6[0]["AMT"])
            elif master_dict.get("ZTOT_OSD"):
                osd_principal = _parse_float(master_dict.get("ZTOT_OSD"))
            else:
                t4 = osd_dict.get("T4")
                if isinstance(t4, list) and len(t4) > 0 and t4[0].get("AMT"):
                    osd_principal = _parse_float(t4[0]["AMT"])

            # L4: Dynamic Live LPSC
            l4 = osd_dict.get("L4")
            if isinstance(l4, list) and len(l4) > 0 and l4[0].get("AMT"):
                live_lpsc = _parse_float(l4[0]["AMT"])
        else:
            if master_dict.get("ZTOT_OSD"):
                osd_principal = _parse_float(master_dict.get("ZTOT_OSD"))

        total_dues = round(osd_principal + live_lpsc, 2)
        data_out["osd_principal"] = f"{osd_principal:.2f}"
        data_out["lpsc"] = f"{live_lpsc:.2f}"
        data_out["total_dues"] = f"{total_dues:.2f}"

        # 4. PAYMENT
        pay_res = results_map.get("PAYMENT", {})
        if pay_res.get("success"):
            p_data = pay_res.get("data")
            p_list = p_data if isinstance(p_data, list) else (p_data.get("payments", []) if isinstance(p_data, dict) else [])
            if isinstance(p_list, list) and len(p_list) > 0 and isinstance(p_list[0], dict):
                first_pay = p_list[0]
                data_out["last_pay_date"] = str(first_pay.get("PAY_DATE") or "-").strip()
                data_out["last_pay_amt"] = f"{_parse_float(first_pay.get('PAY_AMOUNT')):.2f}"
                data_out["last_pay_mode"] = str(first_pay.get("MODE_OF_PAYMENT") or "-").strip()

        return data_out

    def download_bill_pdf(self, consumer_id: str, invoice_no: str, save_path: str) -> Dict[str, Any]:
        """Fetches bill PDF base64 (flag='P', printdoc=invoice_no) and saves to file."""
        cid = str(consumer_id).strip()
        inv = str(invoice_no).strip()

        res = self._fetch_portal_endpoint(cid, "BILLING", "P", printdoc=inv)
        if not res.get("success"):
            return {"success": False, "error": res.get("error", "Download failed")}

        msg = res.get("data")
        if isinstance(msg, list) and len(msg) > 0 and msg[0].get("base64"):
            try:
                b64_data = msg[0]["base64"]
                pdf_bytes = base64.b64decode(b64_data)
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(pdf_bytes)
                return {"success": True, "file_path": save_path, "size_bytes": len(pdf_bytes)}
            except Exception as e:
                return {"success": False, "error": f"Failed to save PDF: {str(e)}"}
        else:
            err_msg = msg if isinstance(msg, str) else "Bill PDF document not available"
            return {"success": False, "error": err_msg}

    # =========================================================================
    # Batch Bill Downloader
    # =========================================================================
    def start_batch_download(
        self,
        consumer_ids_input: Any,
        bill_option: str = "latest",
        target_month: str = "",
        output_dir: str = "",
        max_workers: int = 8,
        custom_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Starts concurrent batch download of consumer bills with complete dues and master data.
        bill_option:
          - "latest": only download the newest bill per consumer
          - "month": download bill matching target_month (e.g. "08.2026")
          - "all": download all available bills
        """
        cids = self.extract_consumer_ids(consumer_ids_input)
        if not cids:
            return {"success": False, "error": "No valid 9-digit consumer IDs provided"}

        sess = self.get_session()
        if not sess.get("authenticated"):
            return {"success": False, "error": "Authentication required. Please login first."}

        with self._lock:
            if self._bulk_state["running"]:
                return {"success": False, "error": "A batch bill download is already in progress"}

            # Setup destination directory
            if not output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(config.BASE_DIR, "Downloaded_Bills", f"Batch_{timestamp}")
            os.makedirs(output_dir, exist_ok=True)

            self._cancel_requested = False
            self._bulk_state = {
                "running": True,
                "processed": 0,
                "total": len(cids),
                "success_count": 0,
                "failed_count": 0,
                "current_cid": "",
                "results": [],
                "error": "",
                "cancelled": False,
                "start_time": time.time(),
                "completed_time": 0,
                "output_dir": output_dir,
                "merged_pdf_path": "",
                "custom_columns": custom_columns or []
            }

        def _worker_thread():
            self._run_batch(cids, bill_option, target_month, output_dir, max_workers, custom_columns)

        self._bulk_thread = threading.Thread(target=_worker_thread, daemon=True)
        self._bulk_thread.start()

        return {
            "success": True,
            "total": len(cids),
            "output_dir": output_dir
        }

    def _run_batch(
        self,
        cids: List[str],
        bill_option: str,
        target_month: str,
        output_dir: str,
        max_workers: int,
        custom_columns: Optional[List[str]] = None
    ):
        clean_target_m = target_month.strip().replace("/", ".")

        def _process_single(cid: str) -> List[Dict[str, Any]]:
            if self._cancel_requested:
                return [{"consumer_id": cid, "status": "Cancelled", "error": "User cancelled"}]

            with self._lock:
                self._bulk_state["current_cid"] = cid

            # Step 1: Concurrently fetch all consumer data (BILLING, MASTER, OSD, PAYMENT)
            cdata = self._fetch_all_consumer_data(cid, custom_columns)
            all_bills = cdata.get("bills", [])

            base_info = {
                "consumer_id": cid,
                "name": cdata.get("name", "-"),
                "address": cdata.get("address", "-"),
                "mobile": cdata.get("mobile", "-"),
                "meter_no": cdata.get("meter_no", "-"),
                "class_desc": cdata.get("class_desc", "-"),
                "tariff": cdata.get("tariff", "-"),
                "conn_status": cdata.get("conn_status", "-"),
                "conn_load": cdata.get("conn_load", "-"),
                "osd_principal": cdata.get("osd_principal", "0.00"),
                "lpsc": cdata.get("lpsc", "0.00"),
                "total_dues": cdata.get("total_dues", "0.00"),
                "last_pay_date": cdata.get("last_pay_date", "-"),
                "last_pay_amt": cdata.get("last_pay_amt", "0.00"),
                "last_pay_mode": cdata.get("last_pay_mode", "-"),
            }

            if not all_bills:
                rec = dict(base_info)
                rec.update({
                    "status": "No Bills",
                    "error": cdata.get("billing_error") or "No bill records found for this consumer",
                    "bill_month": "-",
                    "invoice_no": "-",
                    "due_date": "-",
                    "bill_amount": "0.00",
                    "file_path": ""
                })
                with self._lock:
                    self._bulk_state["results"].append(rec)
                    self._bulk_state["failed_count"] += 1
                return [rec]

            # Step 2: Select which bill(s) to download
            selected_bills = []
            if bill_option == "latest":
                selected_bills = [all_bills[0]]
            elif bill_option == "month" and clean_target_m:
                selected_bills = [b for b in all_bills if str(b.get("BIL_MM_YY", "")).strip() == clean_target_m]
                if not selected_bills:
                    rec = dict(base_info)
                    rec.update({
                        "status": "Not Found",
                        "error": f"No bill matching month {clean_target_m}",
                        "bill_month": clean_target_m,
                        "invoice_no": "-",
                        "due_date": "-",
                        "bill_amount": "0.00",
                        "file_path": ""
                    })
                    with self._lock:
                        self._bulk_state["results"].append(rec)
                        self._bulk_state["failed_count"] += 1
                    return [rec]
            else:
                # "all" or fallback
                selected_bills = all_bills

            # Step 3: Download each selected bill
            results = []
            for b in selected_bills:
                if self._cancel_requested:
                    break

                inv = str(b.get("INV_NO", "")).strip()
                month = str(b.get("BIL_MM_YY", "")).strip()
                due_dt = str(b.get("DUE_DATE", "")).strip()
                raw_amt = b.get("AMT_BFR_D_DT") or b.get("AMT_AFTR_DUE_DT") or "0.00"
                try:
                    amt_str = f"{float(str(raw_amt).replace(',', '').strip()):.2f}"
                except Exception:
                    amt_str = str(raw_amt)

                rec = dict(base_info)
                rec.update({
                    "bill_month": month or "-",
                    "invoice_no": inv or "-",
                    "due_date": due_dt or "-",
                    "bill_amount": amt_str,
                })

                if not inv:
                    rec.update({
                        "status": "Failed",
                        "error": "Missing invoice number",
                        "file_path": ""
                    })
                    with self._lock:
                        self._bulk_state["results"].append(rec)
                        self._bulk_state["failed_count"] += 1
                    results.append(rec)
                    continue

                safe_month = month.replace(".", "_") if month else "unknown"
                filename = f"{cid}_{safe_month}_{inv}.pdf"
                save_path = os.path.join(output_dir, filename)

                dl_res = self.download_bill_pdf(cid, inv, save_path)
                if dl_res.get("success"):
                    rec.update({
                        "status": "Success",
                        "error": "",
                        "file_path": save_path
                    })
                    with self._lock:
                        self._bulk_state["results"].append(rec)
                        self._bulk_state["success_count"] += 1
                else:
                    rec.update({
                        "status": "Failed",
                        "error": dl_res.get("error", "PDF download failed"),
                        "file_path": ""
                    })
                    with self._lock:
                        self._bulk_state["results"].append(rec)
                        self._bulk_state["failed_count"] += 1

                results.append(rec)

            return results

        # Execute concurrent worker pool across consumers (up to 16 workers)
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 16))) as executor:
            future_to_cid = {executor.submit(_process_single, cid): cid for cid in cids}

            for future in as_completed(future_to_cid):
                if self._cancel_requested:
                    break

                with self._lock:
                    self._bulk_state["processed"] += 1

                try:
                    future.result()
                except Exception as e:
                    cid = future_to_cid.get(future, "Unknown")
                    rec = {
                        "consumer_id": cid,
                        "name": "-",
                        "address": "-",
                        "mobile": "-",
                        "meter_no": "-",
                        "class_desc": "-",
                        "tariff": "-",
                        "conn_status": "-",
                        "conn_load": "-",
                        "osd_principal": "0.00",
                        "lpsc": "0.00",
                        "total_dues": "0.00",
                        "last_pay_date": "-",
                        "last_pay_amt": "0.00",
                        "last_pay_mode": "-",
                        "bill_month": "-",
                        "invoice_no": "-",
                        "due_date": "-",
                        "bill_amount": "0.00",
                        "status": "Failed",
                        "error": str(e),
                        "file_path": ""
                    }
                    with self._lock:
                        self._bulk_state["results"].append(rec)
                        self._bulk_state["failed_count"] += 1

        # Post-processing: Save summary Excel & CSV
        with self._lock:
            self._bulk_state["running"] = False
            self._bulk_state["completed_time"] = time.time()
            self._bulk_state["current_cid"] = ""
            if self._cancel_requested:
                self._bulk_state["cancelled"] = True

            results_copy = list(self._bulk_state["results"])

        # Write Summary Files with custom or default layout
        self._export_batch_summary(results_copy, output_dir, custom_columns)

    def export_custom_excel(
        self,
        results: Optional[List[Dict[str, Any]]] = None,
        custom_columns: Optional[List[str]] = None,
        save_path: str = ""
    ) -> Dict[str, Any]:
        """
        Exports consumer records to an Excel file with columns arranged as requested by the user.
        """
        if results is None:
            with self._lock:
                results = list(self._bulk_state["results"])

        if not results:
            return {"success": False, "error": "No records available to export"}

        cols_to_use = custom_columns if (custom_columns and len(custom_columns) > 0) else self.DEFAULT_COLUMNS
        valid_cols = [c for c in cols_to_use if c in self.COLUMN_DEFINITIONS]
        if not valid_cols:
            valid_cols = self.DEFAULT_COLUMNS

        headers = ["Sl No"] + [self.COLUMN_DEFINITIONS[c]["label"] for c in valid_cols]

        rows = []
        for idx, r in enumerate(results, 1):
            row = [idx]
            for col_key in valid_cols:
                field_name = self.COLUMN_DEFINITIONS[col_key]["field"]
                val = r.get(field_name, "")
                if val is None or val == "":
                    val = "-"
                row.append(val)
            rows.append(row)

        if not save_path:
            with self._lock:
                out_dir = self._bulk_state.get("output_dir") or os.path.join(config.BASE_DIR, "Downloaded_Bills")
            os.makedirs(out_dir, exist_ok=True)
            save_path = os.path.join(out_dir, f"Custom_Consumer_Bills_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

        try:
            openpyxl = utils.get_openpyxl()
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Consumer Bills & Dues"

            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            data_font = Font(name="Calibri", size=10)
            center_align = Alignment(horizontal="center", vertical="center")
            right_align = Alignment(horizontal="right", vertical="center")
            left_align = Alignment(horizontal="left", vertical="center")
            thin_border = Border(
                left=Side(style='thin', color='E2E8F0'),
                right=Side(style='thin', color='E2E8F0'),
                top=Side(style='thin', color='E2E8F0'),
                bottom=Side(style='thin', color='E2E8F0')
            )

            # Write header
            ws.append(headers)
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align

            # Write rows
            for row_idx, row_data in enumerate(rows, start=2):
                for col_idx, val in enumerate(row_data, start=1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.font = data_font
                    cell.border = thin_border

                    # Contextual alignment
                    col_key = valid_cols[col_idx - 2] if col_idx > 1 else "sl_no"
                    if col_key in ["bill_amount", "osd_principal", "lpsc", "total_dues", "last_pay_amt"]:
                        cell.alignment = right_align
                    elif col_key in ["sl_no", "consumer_id", "bill_month", "due_date", "last_pay_date", "status", "meter_no", "mobile", "tariff", "conn_status"]:
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align

            # Auto fit column widths
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    val_str = str(cell.value or "")
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 45)

            wb.save(save_path)
            return {"success": True, "file_path": save_path, "count": len(results)}
        except Exception as e:
            return {"success": False, "error": f"Failed to save Excel file: {str(e)}"}

    def _export_batch_summary(
        self,
        results: List[Dict[str, Any]],
        output_dir: str,
        custom_columns: Optional[List[str]] = None
    ):
        """Creates an Excel and CSV summary in the output directory respecting custom column ordering."""
        excel_path = os.path.join(output_dir, "Batch_Download_Summary.xlsx")
        csv_path = os.path.join(output_dir, "Batch_Download_Summary.csv")

        # 1. Export Excel using custom or default columns
        self.export_custom_excel(results=results, custom_columns=custom_columns, save_path=excel_path)

        # 2. Export CSV
        cols_to_use = custom_columns if (custom_columns and len(custom_columns) > 0) else self.DEFAULT_COLUMNS
        valid_cols = [c for c in cols_to_use if c in self.COLUMN_DEFINITIONS]
        if not valid_cols:
            valid_cols = self.DEFAULT_COLUMNS

        headers = ["Sl No"] + [self.COLUMN_DEFINITIONS[c]["label"] for c in valid_cols]
        rows = []
        for idx, r in enumerate(results, 1):
            row = [idx]
            for col_key in valid_cols:
                field_name = self.COLUMN_DEFINITIONS[col_key]["field"]
                val = r.get(field_name, "")
                row.append(val if (val is not None and val != "") else "-")

        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
        except Exception:
            pass

    def get_bulk_status(self) -> Dict[str, Any]:
        with self._lock:
            state = dict(self._bulk_state)
            state["results"] = list(self._bulk_state["results"])
            return state

    def cancel_bulk(self) -> Dict[str, Any]:
        with self._lock:
            self._cancel_requested = True
            if self._bulk_state["running"]:
                self._bulk_state["cancelled"] = True
        return {"success": True}

    # =========================================================================
    # PDF Merging & Batch Printing
    # =========================================================================
    def merge_downloaded_bills(self, pdf_paths: Optional[List[str]] = None, output_merged_path: str = "") -> Dict[str, Any]:
        """
        Merges multiple bill PDFs into a single unified multi-page PDF document
        ready for 1-click batch viewing or printing.
        """
        import pypdf

        if not pdf_paths:
            with self._lock:
                pdf_paths = [r["file_path"] for r in self._bulk_state["results"] if r.get("status") == "Success" and r.get("file_path") and os.path.exists(r["file_path"])]

        valid_paths = [p for p in pdf_paths if p and os.path.exists(p)]
        if not valid_paths:
            return {"success": False, "error": "No valid downloaded bill PDFs available to merge"}

        if not output_merged_path:
            with self._lock:
                out_dir = self._bulk_state.get("output_dir") or os.path.join(config.BASE_DIR, "Downloaded_Bills")
            os.makedirs(out_dir, exist_ok=True)
            output_merged_path = os.path.join(out_dir, "All_Downloaded_Bills_Merged.pdf")

        try:
            if hasattr(pypdf, "PdfWriter"):
                writer = pypdf.PdfWriter()
                for path in valid_paths:
                    writer.append(path)
                with open(output_merged_path, "wb") as f_out:
                    writer.write(f_out)
                writer.close()
            else:
                merger = pypdf.PdfMerger()
                for path in valid_paths:
                    merger.append(path)
                merger.write(output_merged_path)
                merger.close()

            with self._lock:
                self._bulk_state["merged_pdf_path"] = output_merged_path

            return {
                "success": True,
                "merged_path": output_merged_path,
                "bill_count": len(valid_paths)
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to merge bill PDFs: {str(e)}"}

    def print_all_bills(self, pdf_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Prepares merged PDF and sends it directly to Windows Print / default PDF Viewer.
        """
        merge_res = self.merge_downloaded_bills(pdf_paths)
        if not merge_res.get("success"):
            return merge_res

        merged_path = merge_res["merged_path"]
        try:
            # Trigger Windows default print verb or open in viewer
            os.startfile(merged_path, "print")
            return {
                "success": True,
                "printed": True,
                "file_path": merged_path,
                "message": f"Sent {merge_res['bill_count']} bills to default Windows printer"
            }
        except Exception:
            # If default print handler fails, open file so user can print with Ctrl+P
            try:
                os.startfile(merged_path)
                return {
                    "success": True,
                    "printed": False,
                    "opened": True,
                    "file_path": merged_path,
                    "message": f"Opened merged PDF ({merge_res['bill_count']} bills). Press Ctrl+P to print all."
                }
            except Exception as ex:
                return {"success": False, "error": f"Failed to launch printer: {str(ex)}"}
