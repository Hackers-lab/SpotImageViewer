import os
import csv
import json
from datetime import datetime
try:
    from core import config, utils
except ImportError:
    import config, utils


class AuditService:
    """
    Handles Low-Consumption Verification Studio data:
    session persistence, Excel queue parsing, and CSV audit reports.
    """

    @staticmethod
    def get_session_file():
        return os.path.join(config.BASE_DIR, "verification_session.json")

    @classmethod
    def get_session(cls):
        """Retrieve saved low consumption audit session if it exists."""
        session_file = cls.get_session_file()
        try:
            if os.path.exists(session_file):
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {"success": True, "data": data, "count": len(data)}
            return {"success": True, "data": [], "count": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @classmethod
    def save_session(cls, data):
        """Save verification session state to JSON file."""
        session_file = cls.get_session_file()
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def parse_file(cls, file_path):
        """Parse Excel file containing consumer audit list."""
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": "File not found."}

            openpyxl = utils.get_openpyxl()
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return {"success": False, "error": "Excel sheet is empty."}

            items = []
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

            cls.save_session(items)
            return {"success": True, "data": items, "count": len(items)}
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    @staticmethod
    def export_report(items):
        """Export audit queue records to CSV file."""
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

            return {"success": True, "file_path": dest_file, "count": len(items)}
        except Exception as ex:
            return {"success": False, "error": str(ex)}
