import os
import threading
from .base import _io_pool


class SpotAIBridge:
    """SpotAI officer authentication, multi-consumer bill downloading, and batch printing bridge."""

    def spotai_get_session(self):
        """Returns current authentication state and officer details."""
        return self._spotai_bill_service.get_session()

    def spotai_logout(self):
        """Logs out from SpotAI and clears cached session."""
        return self._spotai_bill_service.logout()

    def spotai_request_otp(self, username, password):
        """Dispatches OTP to officer's registered mobile number."""
        return _io_pool.submit(self._spotai_bill_service.request_otp, username, password).result()

    def spotai_verify_otp(self, username, otp):
        """Verifies OTP and activates officer session."""
        return _io_pool.submit(self._spotai_bill_service.verify_otp, username, otp).result()

    def spotai_pick_download_folder(self):
        """Opens native Windows folder picker for bill output directory."""
        folder = self.pick_folder(title="Select Destination Folder for Downloaded Bills")
        return {"success": bool(folder), "folder": folder or ""}

    def spotai_pick_consumer_file(self):
        """Opens file dialog for user to select an Excel/CSV list of Consumer IDs."""
        file_path = self.pick_file(
            title="Select Consumer ID List",
            file_types=["Spreadsheet / Text (*.xlsx;*.xls;*.csv;*.txt)", "Excel Files (*.xlsx;*.xls)", "CSV Files (*.csv)", "All Files (*.*)"]
        )
        if not file_path:
            return {"success": False, "cancelled": True}

        ids = self._spotai_bill_service.extract_consumer_ids(file_path)
        return {
            "success": True,
            "path": file_path,
            "count": len(ids),
            "consumer_ids": ids
        }

    def spotai_get_available_columns(self):
        """Returns the list of fixed columns available for Excel export customization."""
        return self._spotai_bill_service.get_available_columns()

    def spotai_export_custom_excel(self, custom_columns=None, save_path=""):
        """Exports batch results to Excel with user-defined column order."""
        if not save_path:
            save_path = self.pick_save_file(
                title="Save Custom Consumer Excel Report",
                default_filename="Consumer_Bills_Report.xlsx",
                file_types=["Excel Files (*.xlsx)", "All Files (*.*)"]
            )
            if not save_path:
                return {"success": False, "cancelled": True}

        return _io_pool.submit(self._spotai_bill_service.export_custom_excel, None, custom_columns, save_path).result()

    def spotai_start_batch_download(self, consumer_ids_input, bill_option="latest", target_month="", output_dir="", max_workers=8, custom_columns=None):
        """Starts background batch download of bills."""
        return self._spotai_bill_service.start_batch_download(
            consumer_ids_input=consumer_ids_input,
            bill_option=bill_option,
            target_month=target_month,
            output_dir=output_dir,
            max_workers=max_workers,
            custom_columns=custom_columns
        )

    def spotai_get_batch_status(self):
        """Polls current status and progress of the batch download job."""
        return self._spotai_bill_service.get_bulk_status()

    def spotai_cancel_batch(self):
        """Signals cancellation to the running batch download job."""
        return self._spotai_bill_service.cancel_bulk()

    def spotai_open_download_folder(self, output_dir=""):
        """Opens output directory in Windows File Explorer."""
        if not output_dir:
            status = self._spotai_bill_service.get_bulk_status()
            output_dir = status.get("output_dir", "")
        if output_dir and os.path.exists(output_dir):
            self.open_file_external(output_dir)
            return {"success": True}
        return {"success": False, "error": "Output directory not found"}

    def spotai_open_file(self, file_path):
        """Opens specific PDF or summary file externally."""
        if file_path and os.path.exists(file_path):
            self.open_file_external(file_path)
            return {"success": True}
        return {"success": False, "error": "File does not exist"}

    def spotai_merge_bills(self, pdf_paths=None, output_path=""):
        """Merges all downloaded bill PDFs into a single unified document."""
        return _io_pool.submit(self._spotai_bill_service.merge_downloaded_bills, pdf_paths, output_path).result()

    def spotai_print_all_bills(self, pdf_paths=None):
        """
        Merges downloaded bills and invokes Windows print action
        or opens print-ready unified PDF.
        """
        return _io_pool.submit(self._spotai_bill_service.print_all_bills, pdf_paths).result()

    def spotai_check_access(self):
        """Checks if current machine has active license for SpotAI Bill Downloader."""
        return self._license_service.check_access()

    def spotai_activate_module(self, activation_key):
        """Validates and applies activation key for this machine."""
        return self._license_service.activate(activation_key)

    def spotai_admin_generate_key(self, request_code, admin_pin=""):
        """Admin generator: generates activation key for a given request code (protected by admin PIN)."""
        # Secret admin PIN to protect key generation in the UI (default: 9835901878)
        clean_pin = str(admin_pin).strip()
        if clean_pin != "9835901878":
            return {"success": False, "error": "Invalid Admin PIN"}
        key = self._license_service.generate_key_for_request(request_code)
        return {"success": True, "activation_key": key}

    def spotai_reset_license(self):
        """Removes local license to return to activation locked state (for testing/admin)."""
        return self._license_service.reset_license()


