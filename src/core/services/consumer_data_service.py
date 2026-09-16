import os
import re
from datetime import datetime
try:
    from core import utils, database
except ImportError:
    import utils, database


class ConsumerDataService:
    """
    Handles consumer master data import, export to Excel, and blank template generation.
    """

    @staticmethod
    def generate_template(save_path):
        """Creates an empty Excel template for consumer master data imports."""
        try:
            if not save_path:
                return {"success": False, "cancelled": True}

            openpyxl = utils.get_openpyxl()
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

    @staticmethod
    def import_from_excel(file_path):
        """Reads consumer records from an Excel workbook and updates SQLite meter_mapping with streaming."""
        wb = None
        try:
            if not file_path or not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            openpyxl = utils.get_openpyxl()
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
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

            row_iter = sheet.iter_rows(values_only=True)
            first_row = next(row_iter, None)
            if first_row is None:
                return {"success": False, "error": "Excel sheet is empty."}

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

            chunk = {}
            total_imported = 0

            # If first row was not header, process it as data
            if not has_headers:
                cid = get_val(first_row, "consumer_id", 0)
                meter_no = get_val(first_row, "meter_no", 1)
                if cid and meter_no:
                    mobile = re.sub(r"\D", "", get_val(first_row, "mobile_number", 4))
                    if len(mobile) == 12 and mobile.startswith("91"):
                        mobile = mobile[2:]
                    chunk[cid] = {
                        "meter_no": meter_no,
                        "name": get_val(first_row, "name", 2),
                        "address": get_val(first_row, "address", 3),
                        "mobile_number": mobile,
                        "contractual_load": get_val(first_row, "contractual_load", 5),
                        "class": get_val(first_row, "class", 6),
                    }

            for row in row_iter:
                if not row:
                    continue
                cid = get_val(row, "consumer_id", 0)
                meter_no = get_val(row, "meter_no", 1)
                if not cid or not meter_no:
                    continue

                mobile = re.sub(r"\D", "", get_val(row, "mobile_number", 4))
                if len(mobile) == 12 and mobile.startswith("91"):
                    mobile = mobile[2:]

                chunk[cid] = {
                    "meter_no": meter_no,
                    "name": get_val(row, "name", 2),
                    "address": get_val(row, "address", 3),
                    "mobile_number": mobile,
                    "contractual_load": get_val(row, "contractual_load", 5),
                    "class": get_val(row, "class", 6),
                }

                if len(chunk) >= 5000:
                    utils.update_meter_mapping(chunk)
                    total_imported += len(chunk)
                    chunk.clear()

            if chunk:
                utils.update_meter_mapping(chunk)
                total_imported += len(chunk)
                chunk.clear()

            if total_imported == 0:
                return {"success": False, "error": "No valid consumer records found in file."}

            database.set_info_value("consumer_data_updated_at", datetime.now().strftime("%d-%m-%Y %H:%M"))
            return {"success": True, "count": total_imported, "file_path": file_path}
        except Exception as ex:
            return {"success": False, "error": str(ex)}
        finally:
            if wb:
                try:
                    wb.close()
                except Exception:
                    pass

    @staticmethod
    def export_to_excel(dest_path):
        """Exports all consumer master mapping records from SQLite into an Excel workbook using write_only streaming."""
        cursor = None
        wb = None
        try:
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

            openpyxl = utils.get_openpyxl()
            wb = openpyxl.Workbook(write_only=True)
            sheet = wb.create_sheet(title="ConsumerMaster")
            headers = [
                "CONSUMER ID", "METER NO", "NAME", "ADDRESS",
                "MOBILE NUMBER", "CONTRACTUAL LOAD", "CLASS"
            ]
            sheet.append(headers)

            total_exported = 0
            while True:
                chunk = cursor.fetchmany(5000)
                if not chunk:
                    break
                for r in chunk:
                    sheet.append([
                        str(r[0] or ""), str(r[1] or ""), str(r[2] or ""),
                        str(r[3] or ""), str(r[4] or ""), str(r[5] or ""),
                        str(r[6] or "")
                    ])
                    total_exported += 1

            wb.save(dest_path)
            return {"success": True, "count": total_exported, "path": dest_path}
        except Exception as ex:
            return {"success": False, "error": str(ex)}
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if wb:
                try:
                    wb.close()
                except Exception:
                    pass
