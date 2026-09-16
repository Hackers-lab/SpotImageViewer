import os

from .base import _io_pool


class FuzzyBridge:
    """Fuzzy matching engine and consumer master data management bridge."""

    def get_fuzzy_status(self):
        return self._fuzzy_service.get_status()

    def generate_fuzzy_template(self, save_path=""):
        if not save_path:
            save_path = self.pick_save_file(
                title="Save Fuzzy Lookup Template",
                default_filename="fuzzy_lookup_input_template.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        return self._fuzzy_service.generate_fuzzy_template(save_path)

    def lookup_fuzzy_rows(self, rows, threshold=0.85, top_n=5):
        return _io_pool.submit(lambda: self._fuzzy_service.lookup_fuzzy_rows(rows, threshold, top_n)).result()

    def run_fuzzy_lookup(self, input_path="", output_path="", threshold=0.85, top_n=5, include_live_osd=False):
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
                import time
                ts = time.strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(input_dir, f"fuzzy_lookup_results_{ts}.xlsx")

        return self._fuzzy_service.start_batch_lookup(input_path, output_path, threshold, top_n, include_live_osd)

    def generate_consumer_template(self, save_path=""):
        if not save_path:
            save_path = self.pick_save_file(
                title="Save Consumer Data Template",
                default_filename="consumer_data_template.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        return self._consumer_service.generate_template(save_path)

    def import_consumer_data(self, file_path=""):
        if not file_path:
            file_path = self.pick_file(
                title="Select Consumer Data Excel",
                file_types=[("Excel Files (*.xlsx;*.xls)", "*.xlsx;*.xls")]
            )
        if not file_path:
            return {"success": False, "cancelled": True}

        def _do_import():
            res = self._consumer_service.import_from_excel(file_path)
            if res.get("success"):
                self._fuzzy_service.invalidate_cache()
            return res

        return _io_pool.submit(_do_import).result()

    def export_consumer_data_file(self, dest_path=""):
        if not dest_path:
            dest_path = self.pick_save_file(
                title="Export Consumer Master Records",
                default_filename="consumer_master_export.xlsx",
                file_types=[("Excel Files (*.xlsx)", "*.xlsx")]
            )
        if not dest_path:
            return {"success": False, "cancelled": True}

        def _do_export():
            res = self._consumer_service.export_to_excel(dest_path)
            if res.get("success"):
                self.open_file_external(dest_path)
            return res

        return _io_pool.submit(_do_export).result()
