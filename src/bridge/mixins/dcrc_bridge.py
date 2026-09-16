import os
import shutil

from .base import _io_pool


class DCRCBridge:
    """DCRC billing, Agency PO generation, file processing, and template management bridge."""

    def pick_dcrc_events_files(self):
        """Selects one or more DCRC SAP export files (DC.XLS, RC.XLS, DR.xls, ONLINE DR.XLS)."""
        files = self.pick_files_multiple(
            title="Select DCRC Files (DC, RC, DR, ONLINE DR)",
            file_types=["SAP / Excel Files (*.xls;*.xlsx;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "files": files, "count": len(files)}

    def pick_cash_payment_files(self):
        """Selects one or more SAP Cash Payment Register files (cash1.XLSX, CASH2.XLSX)."""
        files = self.pick_files_multiple(
            title="Select Payment / Cash Files (cash1, CASH2)",
            file_types=["Excel / SAP Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "files": files, "count": len(files)}

    def pick_zone_mapping_file(self):
        """Selects the Zone-Agency Mapping file (Zones.xlsx)."""
        f = self.pick_file(
            title="Select Zone-Agency Mapping File (Zones.xlsx)",
            file_types=["Excel / CSV Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "file": f}

    def pick_consumer_master_file(self):
        """Selects the Consumer Master Data file (Consumer Data.xlsx)."""
        f = self.pick_file(
            title="Select Consumer Master File (Consumer Data.xlsx)",
            file_types=["Excel / CSV Files (*.xlsx;*.xls;*.csv)", "All Files (*.*)"]
        )
        return {"success": True, "file": f}

    def pick_dcrc_output_folder(self):
        """Selects the folder where Agency Workbooks & Reports will be saved."""
        folder = self.pick_folder(title="Select Output Folder for Agency Workbooks")
        return {"success": True, "folder": folder}

    def get_dcrc_defaults(self):
        """Returns paths to default templates and configured standard rates."""
        try:
            from core.services import dcrc_processor
        except ImportError:
            from services import dcrc_processor

        template_dir = r"C:\spotbillfiles\dcrc_templates"
        zone_tpl = os.path.join(template_dir, "Zones_Template.xlsx")
        cm_tpl = os.path.join(template_dir, "Consumer_Master_Template.xlsx")
        default_out = r"C:\spotbillfiles\DCRC_PO_Output"

        return {
            "success": True,
            "template_dir": template_dir,
            "zone_template": zone_tpl if os.path.exists(zone_tpl) else "",
            "consumer_template": cm_tpl if os.path.exists(cm_tpl) else "",
            "default_output": default_out,
            "standard_rates": dcrc_processor.DEFAULT_STANDARD_RATES,
            "custom_rates": dcrc_processor.DEFAULT_CUSTOM_AGENCY_RATES
        }

    def process_dcrc_data(self, dcrc_files, cash_files, zone_file, consumer_file=None, custom_rates=None):
        """
        Processes the DCRC run asynchronously in the I/O pool.
        Stores the result in self._last_dcrc_result for instant export.
        """
        def _run():
            try:
                try:
                    from core.services import dcrc_processor
                except ImportError:
                    from services import dcrc_processor

                # If consumer_file is empty or not provided, check if default template exists
                cm_path = consumer_file
                if not cm_path or not os.path.exists(cm_path):
                    default_cm = r"C:\spotbillfiles\dcrc_templates\Consumer_Master_Template.xlsx"
                    if os.path.exists(default_cm):
                        cm_path = default_cm

                res = dcrc_processor.process_dcrc_run(
                    dcrc_file_paths=dcrc_files,
                    cash_file_paths=cash_files,
                    zone_file_path=zone_file,
                    consumer_master_file_path=cm_path,
                    custom_rates=custom_rates
                )
                self._last_dcrc_result = res
                # Return lightweight summary to frontend (omit full records array for fast serialization)
                return {
                    "success": True,
                    "summary": res.get("summary", []),
                    "totals": res.get("totals", {}),
                    "discrepancies": res.get("discrepancies", [])[:100],
                    "total_records_processed": res.get("total_records_processed", 0),
                    "total_discrepancies": res.get("total_discrepancies", 0),
                    "zone_cutoffs": res.get("zone_cutoffs", []),
                    "sample_records": res.get("records", [])[:30]
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"success": False, "error": str(e)}

        return _io_pool.submit(_run).result()

    def export_dcrc_files(self, output_folder=None):
        """
        Exports individual <Agency>.xlsx workbooks, PO Summary Report, and MAIN LIST.
        """
        if not self._last_dcrc_result:
            return {"success": False, "error": "No processed DCRC data available. Please process files first."}

        try:
            from core.services import dcrc_exporter
        except ImportError:
            from services import dcrc_exporter

        out_dir = output_folder or r"C:\spotbillfiles\DCRC_PO_Output"
        try:
            ag_files = dcrc_exporter.export_agency_workbooks(self._last_dcrc_result, out_dir)
            rep_file = dcrc_exporter.export_summary_report(self._last_dcrc_result, out_dir)
            main_file = dcrc_exporter.export_master_list(self._last_dcrc_result, out_dir)

            return {
                "success": True,
                "output_dir": out_dir,
                "agency_files_count": len(ag_files),
                "summary_report": rep_file,
                "main_list": main_file
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_folder_in_explorer(self, folder_path):
        """Opens the specified folder in Windows Explorer."""
        try:
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return {"success": True}
            return {"success": False, "error": "Folder does not exist"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_sample_template_path(self, sample_type):
        filename_map = {
            "dcrc": "Sample_DCRC_List.xlsx",
            "payment": "Sample_Payment_Cash.xlsx",
            "zone": "Sample_Zone_Map.xlsx",
            "consumer_master": "Sample_Consumer_Master.xlsx"
        }
        fname = filename_map.get(sample_type)
        if not fname:
            return None, None

        # Priority 1: C:\spotbillfiles\dcrc_templates
        p1 = os.path.join(r"C:\spotbillfiles\dcrc_templates", fname)
        if os.path.exists(p1):
            return p1, fname

        # Priority 2: src/resources/templates
        bridge_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.dirname(bridge_dir)
        p2 = os.path.join(base_dir, "resources", "templates", fname)
        if os.path.exists(p2):
            return p2, fname

        return None, fname

    def download_dcrc_sample(self, sample_type):
        """Allows user to save a sample template to a location of their choice."""
        src_path, fname = self._get_sample_template_path(sample_type)
        if not src_path:
            return {"success": False, "error": f"Sample template '{fname}' not found."}

        dest = self.pick_save_file(
            title=f"Save {fname}",
            default_filename=fname,
            file_types=[("Excel Files", "*.xlsx")]
        )
        if not dest:
            return {"success": False, "cancelled": True}

        try:
            shutil.copyfile(src_path, dest)
            return {"success": True, "saved_path": dest, "filename": fname}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_dcrc_sample(self, sample_type):
        """Directly opens the requested sample template in default spreadsheet application."""
        src_path, fname = self._get_sample_template_path(sample_type)
        if not src_path:
            return {"success": False, "error": f"Sample template '{fname}' not found."}
        try:
            os.startfile(src_path)
            return {"success": True, "path": src_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_dcrc_templates_folder(self):
        """Opens the folder containing sample templates in Windows Explorer."""
        p = r"C:\spotbillfiles\dcrc_templates"
        if not os.path.exists(p):
            bridge_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            base_dir = os.path.dirname(bridge_dir)
            p = os.path.join(base_dir, "resources", "templates")
        try:
            os.makedirs(p, exist_ok=True)
            os.startfile(p)
            return {"success": True, "folder": p}
        except Exception as e:
            return {"success": False, "error": str(e)}
