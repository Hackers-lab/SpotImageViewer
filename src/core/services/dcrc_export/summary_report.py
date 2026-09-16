import os
import openpyxl
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from .styles import (
    BANNER_FILL, BANNER_FONT, HEADER_FILL, HEADER_FONT,
    SUBHEADER_FILL, SUBHEADER_FONT, DATA_FONT,
    TOTAL_FILL, TOTAL_FONT, BORDER_THIN, _get_date_range_str,
    _style_banner_row
)


def export_summary_report(processed_result, output_dir):
    """
    Exports the PO Summary Report matching the layout of the REPORT sheet in LIST SOFTWARE V2.xlsm.
    Prefixed with 01_ for sorting. Formatted with light headers and horizontal centering.
    """
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "01_PO_Summary_Report.xlsx")
    date_range_str = _get_date_range_str(processed_result)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "REPORT"

    total_cols = 18

    # Row 1: Banner
    banner_text = f"PO SUMMARY BILLING REPORT   |   DATE RANGE: {date_range_str}"
    ws.append([banner_text])
    _style_banner_row(ws, 1, total_cols, banner_text, fill=BANNER_FILL, font=BANNER_FONT, height=24)

    # Row 2: Group Headers
    ws.append([""] * total_cols)
    ws.row_dimensions[2].height = 22
    ws.cell(2, 1, "Agency")
    ws.cell(2, 2, "1 PHASE (1PH)")
    ws.cell(2, 8, "3 PHASE (3PH)")
    ws.cell(2, 14, "TOTAL PAYABLE")

    ws.merge_cells("B2:G2")
    ws.merge_cells("H2:M2")
    ws.merge_cells("N2:R2")

    for c in range(1, total_cols + 1):
        cell = ws.cell(2, c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER_THIN

    # Row 3: Sub-headers
    sub_headers = [
        "Agency",
        "DC", "Rate", "RC", "Rate", "DR", "Rate",
        "DC", "Rate", "RC", "Rate", "DR", "Rate",
        "Total Amount", "Total DC", "Total RC", "Total DR", "Total Records"
    ]
    ws.append(sub_headers)
    ws.row_dimensions[3].height = 22

    for c in range(1, total_cols + 1):
        cell = ws.cell(3, c)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN

    # Data Rows (Row 4+)
    summary_rows = processed_result.get("summary", [])
    for item in summary_rows:
        row_vals = [
            item["agency"],
            item["c_1ph_dc"], item["r_1ph_dc"],
            item["c_1ph_rc"], item["r_1ph_rc"],
            item["c_1ph_dr"], item["r_1ph_dr"],
            item["c_3ph_dc"], item["r_3ph_dc"],
            item["c_3ph_rc"], item["r_3ph_rc"],
            item["c_3ph_dr"], item["r_3ph_dr"],
            item["total_amount"],
            item["total_dc"], item["total_rc"], item["total_dr"], item["total_count"]
        ]
        ws.append(row_vals)
        cur_row = ws.max_row
        ws.row_dimensions[cur_row].height = 19
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_row, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if c == 14:
                    cell.number_format = '#,##0.00'

    # Grand Total Row
    totals = processed_result.get("totals", {})
    total_row = [
        "TOTAL",
        totals.get("1ph_dc", 0), "",
        totals.get("1ph_rc", 0), "",
        totals.get("1ph_dr", 0), "",
        totals.get("3ph_dc", 0), "",
        totals.get("3ph_rc", 0), "",
        totals.get("3ph_dr", 0), "",
        totals.get("total_amount", 0.0),
        totals.get("1ph_dc", 0) + totals.get("3ph_dc", 0),
        totals.get("1ph_rc", 0) + totals.get("3ph_rc", 0),
        totals.get("1ph_dr", 0) + totals.get("3ph_dr", 0),
        totals.get("total_records", 0)
    ]
    ws.append(total_row)
    cur_row = ws.max_row
    ws.row_dimensions[cur_row].height = 22
    for c in range(1, total_cols + 1):
        cell = ws.cell(cur_row, c)
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER_THIN
        if c == 1:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            if c == 14:
                cell.number_format = '#,##0.00'

    # Phase summary block below
    ws.cell(cur_row + 2, 2, "PHASE SUMMARY").font = TOTAL_FONT
    ws.cell(cur_row + 3, 2, "1PH Total:").font = TOTAL_FONT
    ws.cell(cur_row + 3, 3, totals.get("1ph_total", 0)).font = TOTAL_FONT
    ws.cell(cur_row + 4, 2, "3PH Total:").font = TOTAL_FONT
    ws.cell(cur_row + 4, 3, totals.get("3ph_total", 0)).font = TOTAL_FONT
    ws.cell(cur_row + 5, 2, "Overall Total Records:").font = TOTAL_FONT
    ws.cell(cur_row + 5, 3, totals.get("total_records", 0)).font = TOTAL_FONT
    ws.cell(cur_row + 6, 2, "Overall P.O. Amount (Rs):").font = TOTAL_FONT
    tot_amt_cell = ws.cell(cur_row + 6, 3, totals.get("total_amount", 0.0))
    tot_amt_cell.font = TOTAL_FONT
    tot_amt_cell.number_format = '#,##0.00'

    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_margins.left = 0.3
    ws.page_margins.right = 0.3
    ws.page_margins.top = 0.35
    ws.page_margins.bottom = 0.4
    ws.print_options.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = '1:3'
    ws.oddFooter.right.text = "Page &P of &N"
    ws.evenFooter.right.text = "Page &P of &N"
    ws.oddFooter.left.text = ""
    ws.evenFooter.left.text = ""
    ws.print_options.gridLines = True

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        if col[0].column == 1:
            ws.column_dimensions[col_letter].width = 20
        elif col[0].column == 14:
            ws.column_dimensions[col_letter].width = 14
        else:
            ws.column_dimensions[col_letter].width = 9

    # Sheet 2: PO Quantity Details (Consolidated DC & RC)
    _create_po_quantity_details_sheet(wb, processed_result, date_range_str)

    wb.save(file_path)
    return file_path


def _create_po_quantity_details_sheet(wb, processed_result, date_range_str):
    """
    Creates the 'PO QUANTITY DETAILS' sheet where quantities reflect Purchase Order line items:
    - 1PH DC = 1PH DC + 1PH DR
    - 1PH RC = 1PH RC + 1PH DR
    - 3PH DC = 3PH DC + 3PH DR
    - 3PH RC = 3PH RC + 3PH DR
    Total Amount matches the primary REPORT sheet exactly.
    """
    ws = wb.create_sheet(title="PO QUANTITY DETAILS")
    total_cols = 15

    # Row 1: Banner
    banner_text = f"PO QUANTITY BILLING DETAILS (CONSOLIDATED DC & RC)   |   DATE RANGE: {date_range_str}"
    ws.append([banner_text])
    _style_banner_row(ws, 1, total_cols, banner_text, fill=BANNER_FILL, font=BANNER_FONT, height=24)

    # Row 2: Group Headers
    ws.append([""] * total_cols)
    ws.row_dimensions[2].height = 22
    ws.cell(2, 1, "Agency")
    ws.cell(2, 2, "1 PHASE (1PH)")
    ws.cell(2, 7, "3 PHASE (3PH)")
    ws.cell(2, 12, "TOTAL PAYABLE")

    ws.merge_cells("B2:F2")
    ws.merge_cells("G2:K2")
    ws.merge_cells("L2:O2")

    for c in range(1, total_cols + 1):
        cell = ws.cell(2, c)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER_THIN

    # Row 3: Sub-headers
    sub_headers = [
        "Agency",
        "DC (DC+DR)", "Rate", "RC (RC+DR)", "Rate", "1PH Amount",
        "DC (DC+DR)", "Rate", "RC (RC+DR)", "Rate", "3PH Amount",
        "Total Amount", "Total DC", "Total RC", "Total PO Qty"
    ]
    ws.append(sub_headers)
    ws.row_dimensions[3].height = 22

    for c in range(1, total_cols + 1):
        cell = ws.cell(3, c)
        cell.font = SUBHEADER_FONT
        cell.fill = SUBHEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN

    # Data Rows (Row 4+)
    summary_rows = processed_result.get("summary", [])
    tot_po_1ph_dc = 0
    tot_po_1ph_rc = 0
    tot_po_1ph_amt = 0.0
    tot_po_3ph_dc = 0
    tot_po_3ph_rc = 0
    tot_po_3ph_amt = 0.0

    for item in summary_rows:
        po_1_dc = item["c_1ph_dc"] + item["c_1ph_dr"]
        r_1_dc = item["r_1ph_dc"]
        po_1_rc = item["c_1ph_rc"] + item["c_1ph_dr"]
        r_1_rc = item["r_1ph_rc"]
        amt_1ph = (po_1_dc * r_1_dc) + (po_1_rc * r_1_rc)

        po_3_dc = item["c_3ph_dc"] + item["c_3ph_dr"]
        r_3_dc = item["r_3ph_dc"]
        po_3_rc = item["c_3ph_rc"] + item["c_3ph_dr"]
        r_3_rc = item["r_3ph_rc"]
        amt_3ph = (po_3_dc * r_3_dc) + (po_3_rc * r_3_rc)

        agency_tot_dc = po_1_dc + po_3_dc
        agency_tot_rc = po_1_rc + po_3_rc
        agency_tot_po = agency_tot_dc + agency_tot_rc
        agency_tot_amt = amt_1ph + amt_3ph

        row_vals = [
            item["agency"],
            po_1_dc, r_1_dc,
            po_1_rc, r_1_rc,
            amt_1ph,
            po_3_dc, r_3_dc,
            po_3_rc, r_3_rc,
            amt_3ph,
            agency_tot_amt,
            agency_tot_dc, agency_tot_rc, agency_tot_po
        ]
        ws.append(row_vals)
        cur_row = ws.max_row
        ws.row_dimensions[cur_row].height = 19
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_row, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if c in (6, 11, 12):
                    cell.number_format = '#,##0.00'

        tot_po_1ph_dc += po_1_dc
        tot_po_1ph_rc += po_1_rc
        tot_po_1ph_amt += amt_1ph
        tot_po_3ph_dc += po_3_dc
        tot_po_3ph_rc += po_3_rc
        tot_po_3ph_amt += amt_3ph

    # Grand Total Row
    tot_overall_dc = tot_po_1ph_dc + tot_po_3ph_dc
    tot_overall_rc = tot_po_1ph_rc + tot_po_3ph_rc
    tot_overall_po = tot_overall_dc + tot_overall_rc
    tot_overall_amt = tot_po_1ph_amt + tot_po_3ph_amt

    total_row = [
        "TOTAL",
        tot_po_1ph_dc, "",
        tot_po_1ph_rc, "",
        tot_po_1ph_amt,
        tot_po_3ph_dc, "",
        tot_po_3ph_rc, "",
        tot_po_3ph_amt,
        tot_overall_amt,
        tot_overall_dc, tot_overall_rc, tot_overall_po
    ]
    ws.append(total_row)
    cur_row = ws.max_row
    ws.row_dimensions[cur_row].height = 22
    for c in range(1, total_cols + 1):
        cell = ws.cell(cur_row, c)
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER_THIN
        if c == 1:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            if c in (6, 11, 12):
                cell.number_format = '#,##0.00'

    # Summary block below
    ws.cell(cur_row + 2, 2, "PO QUANTITY SUMMARY (CONSOLIDATED)").font = TOTAL_FONT
    ws.cell(cur_row + 3, 2, "1PH DC Quantity (DC+DR):").font = TOTAL_FONT
    ws.cell(cur_row + 3, 3, tot_po_1ph_dc).font = TOTAL_FONT
    ws.cell(cur_row + 4, 2, "1PH RC Quantity (RC+DR):").font = TOTAL_FONT
    ws.cell(cur_row + 4, 3, tot_po_1ph_rc).font = TOTAL_FONT
    ws.cell(cur_row + 5, 2, "1PH Total PO Quantity:").font = TOTAL_FONT
    ws.cell(cur_row + 5, 3, tot_po_1ph_dc + tot_po_1ph_rc).font = TOTAL_FONT
    ws.cell(cur_row + 6, 2, "1PH Total PO Amount (Rs):").font = TOTAL_FONT
    amt_1_cell = ws.cell(cur_row + 6, 3, tot_po_1ph_amt)
    amt_1_cell.font = TOTAL_FONT
    amt_1_cell.number_format = '#,##0.00'

    ws.cell(cur_row + 8, 2, "3PH DC Quantity (DC+DR):").font = TOTAL_FONT
    ws.cell(cur_row + 8, 3, tot_po_3ph_dc).font = TOTAL_FONT
    ws.cell(cur_row + 9, 2, "3PH RC Quantity (RC+DR):").font = TOTAL_FONT
    ws.cell(cur_row + 9, 3, tot_po_3ph_rc).font = TOTAL_FONT
    ws.cell(cur_row + 10, 2, "3PH Total PO Quantity:").font = TOTAL_FONT
    ws.cell(cur_row + 10, 3, tot_po_3ph_dc + tot_po_3ph_rc).font = TOTAL_FONT
    ws.cell(cur_row + 11, 2, "3PH Total PO Amount (Rs):").font = TOTAL_FONT
    amt_3_cell = ws.cell(cur_row + 11, 3, tot_po_3ph_amt)
    amt_3_cell.font = TOTAL_FONT
    amt_3_cell.number_format = '#,##0.00'

    ws.cell(cur_row + 13, 2, "Total PO DC Quantity:").font = TOTAL_FONT
    ws.cell(cur_row + 13, 3, tot_overall_dc).font = TOTAL_FONT
    ws.cell(cur_row + 14, 2, "Total PO RC Quantity:").font = TOTAL_FONT
    ws.cell(cur_row + 14, 3, tot_overall_rc).font = TOTAL_FONT
    ws.cell(cur_row + 15, 2, "Overall Total PO Quantity:").font = TOTAL_FONT
    ws.cell(cur_row + 15, 3, tot_overall_po).font = TOTAL_FONT
    ws.cell(cur_row + 16, 2, "Overall P.O. Amount (Rs):").font = TOTAL_FONT
    tot_amt_cell = ws.cell(cur_row + 16, 3, tot_overall_amt)
    tot_amt_cell.font = TOTAL_FONT
    tot_amt_cell.number_format = '#,##0.00'

    # Page setup
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_margins.left = 0.3
    ws.page_margins.right = 0.3
    ws.page_margins.top = 0.35
    ws.page_margins.bottom = 0.4
    ws.print_options.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = '1:3'
    ws.oddFooter.right.text = "Page &P of &N"
    ws.evenFooter.right.text = "Page &P of &N"
    ws.print_options.gridLines = True

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        col_idx = col[0].column
        if col_idx == 1:
            ws.column_dimensions[col_letter].width = 20
        elif col_idx in (6, 11, 12):
            ws.column_dimensions[col_letter].width = 14
        elif col_idx in (3, 5, 8, 10):
            ws.column_dimensions[col_letter].width = 8
        else:
            ws.column_dimensions[col_letter].width = 11

