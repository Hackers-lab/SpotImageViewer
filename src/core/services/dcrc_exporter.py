"""
DCRC & Agency PO Excel Exporter Façade.
Orchestrates generation of individual Agency Workbooks, PO Summary Report, and Master List.
Modularized into sub-builders under dcrc_export/ for clean maintenance.
"""

from .dcrc_export import (
    export_agency_workbooks,
    export_summary_report,
    export_master_list,
    _create_agency_breakup_sheet,
    _create_agency_print_all_sheet,
    _create_raw_data_sheet,
    _setup_portrait_page,
    _get_date_range_str,
    _apply_value_based_widths,
    _style_banner_row,
    _get_agency_metrics,
)

__all__ = [
    "export_agency_workbooks",
    "export_summary_report",
    "export_master_list",
    "_create_agency_breakup_sheet",
    "_create_agency_print_all_sheet",
    "_create_raw_data_sheet",
    "_setup_portrait_page",
    "_get_date_range_str",
    "_apply_value_based_widths",
    "_style_banner_row",
    "_get_agency_metrics",
]
