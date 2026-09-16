import os
import re
import json
import threading

try:
    from core import config
except ImportError:
    import config

from .base import _io_pool


class OSDBridge:
    """Live WBSEDCL Outstanding Statement (OSD), PDF parsing, and bulk dues verification bridge."""

    def get_live_osd(self, consumer_id, force_refresh=False):
        cid = str(consumer_id).strip()
        if not re.match(r"^\d{9}$", cid):
            return {"success": False, "error": f"Invalid Consumer ID '{cid}'. Must be a 9-digit number."}

        try:
            from core import live_osd_service as _los
        except ImportError:
            import live_osd_service as _los

        # If already cached and not force refreshing, return immediately
        if not force_refresh:
            cached_res = _los.get_live_osd_data(cid, include_pdf_base64=False, force_refresh=False)
            if cached_res.get("success") and cached_res.get("data", {}).get("cached"):
                return cached_res

        def _bg_fetch():
            try:
                result = _los.get_live_osd_data(cid, include_pdf_base64=True, force_refresh=bool(force_refresh))
                if self._window:
                    js_data = json.dumps(result)
                    self._window.evaluate_js(f"if (typeof onLiveOsdResult === 'function') {{ onLiveOsdResult({js_data}); }}")
            except Exception as e:
                if self._window:
                    err = json.dumps({"success": False, "error": str(e)})
                    self._window.evaluate_js(f"if (typeof onLiveOsdResult === 'function') {{ onLiveOsdResult({err}); }}")

        threading.Thread(target=_bg_fetch, daemon=True).start()
        return {"success": True, "pending": True}

    def open_live_osd_pdf(self, consumer_id):
        cid = str(consumer_id).strip()
        if not re.match(r"^\d{9}$", cid):
            return {"success": False, "error": "Invalid Consumer ID. Must be 9 digits."}

        def _fetch():
            try:
                try:
                    from core import live_osd_service as _los
                except ImportError:
                    import live_osd_service as _los

                pdf_bytes = _los.fetch_live_osd_pdf(cid)

                temp_dir = os.path.join(config.BASE_DIR, "temp_osd")
                os.makedirs(temp_dir, exist_ok=True)
                pdf_path = os.path.join(temp_dir, f"WBSEDCL_OSD_{cid}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                self.open_file_external(pdf_path)
                return {"success": True, "file_path": pdf_path}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return _io_pool.submit(_fetch).result()

    def check_single_osd(self, consumer_id, force_refresh=False):
        """Synchronously or thread-pool fetches single consumer live OSD data."""
        cid = str(consumer_id).strip()
        return _io_pool.submit(self._osd_service.get_single_osd, cid, bool(force_refresh)).result()

    def start_bulk_osd(self, consumer_ids_input, auto_download_pdf=False, max_workers=3):
        """Starts a background bulk verification run for multiple consumer IDs."""
        return self._osd_service.start_bulk_osd(consumer_ids_input, bool(auto_download_pdf), int(max_workers))

    def get_bulk_osd_status(self):
        """Polls current status and results of the bulk verification job."""
        return self._osd_service.get_bulk_status()

    def cancel_bulk_osd(self):
        """Signals cancellation to the bulk verification job."""
        return self._osd_service.cancel_bulk()

    def export_bulk_osd_excel(self, results, save_path=None):
        """Prompts for save path if not given and exports results to formatted Excel."""
        if not save_path:
            from datetime import datetime
            default_name = f"Consumer_Dues_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            save_path = self.pick_save_file(
                title="Save Dues Excel Report",
                default_filename=default_name,
                file_types=["Excel Files (*.xlsx)", "All Files (*.*)"]
            )
            if not save_path:
                return {"success": False, "cancelled": True}
        return _io_pool.submit(self._osd_service.export_excel, results, save_path).result()

    def export_bulk_osd_csv(self, results, save_path=None):
        """Prompts for save path if not given and exports results to CSV."""
        if not save_path:
            from datetime import datetime
            default_name = f"Consumer_Dues_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            save_path = self.pick_save_file(
                title="Save Dues CSV Report",
                default_filename=default_name,
                file_types=["CSV Files (*.csv)", "All Files (*.*)"]
            )
            if not save_path:
                return {"success": False, "cancelled": True}
        return _io_pool.submit(self._osd_service.export_csv, results, save_path).result()

    def select_osd_batch_file(self):
        """Opens file dialog for user to select an Excel or CSV file containing consumer IDs."""
        path = self.pick_file(
            title="Select Excel or CSV File with Consumer IDs",
            file_types=["Excel / CSV / Text Files (*.xlsx;*.xls;*.csv;*.txt)", "All Files (*.*)"]
        )
        if not path:
            return {"success": False, "cancelled": True}
        ids = self._osd_service.extract_consumer_ids(path)
        return {"success": True, "path": path, "consumer_ids": ids, "count": len(ids)}

    def generate_bulk_osd_template(self):
        """Prompts user where to save a blank bulk consumer input template."""
        save_path = self.pick_save_file(
            title="Save Bulk Input Template",
            default_filename="Bulk_Consumer_ID_Template.xlsx",
            file_types=["Excel Files (*.xlsx)", "All Files (*.*)"]
        )
        if not save_path:
            return {"success": False, "cancelled": True}
        return self._osd_service.generate_template(save_path)
