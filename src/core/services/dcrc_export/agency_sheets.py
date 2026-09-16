import openpyxl
from openpyxl.styles import Alignment
from openpyxl.worksheet.pagebreak import Break

from .styles import (
    BANNER_FILL, BANNER_FONT, BANNER_SUB_FILL, BANNER_SUB_FONT,
    HEADER_FILL, HEADER_FONT, PART_FILL, PART_FONT,
    DATA_FONT, SUBTOTAL_FILL, SUBTOTAL_FONT, TOTAL_FILL, TOTAL_FONT,
    BORDER_THIN, BORDER_DOUBLE_BOTTOM, PARTS_CONFIG_AGENCY,
    _setup_portrait_page, _get_date_range_str, _apply_value_based_widths,
    _style_banner_row, _get_agency_metrics
)


def _create_agency_breakup_sheet(wb, agency_name, processed_result, ag_records):
    """
    Creates the standalone Breakup Summary Report sheet for an agency.
    (Dual Action word removed, Signatures block removed as requested).
    Formatted to print on exactly 1 Portrait page with light headers and horizontal centering.
    """
    ws = wb.create_sheet(title="BREAKUP REPORT")
    date_range_str = _get_date_range_str(processed_result)
    m = _get_agency_metrics(agency_name, processed_result, ag_records)
    total_cols = 5

    # Row 1: Title Banner
    ws.append(["PURCHASE ORDER BILLING BREAKUP REPORT"])
    _style_banner_row(ws, 1, total_cols, "PURCHASE ORDER BILLING BREAKUP REPORT", fill=BANNER_FILL, font=BANNER_FONT, height=26)

    # Row 2: Subtitle Banner
    ws.append([f"AGENCY: {agency_name}   |   DATE RANGE: {date_range_str}"])
    _style_banner_row(ws, 1, total_cols, f"AGENCY: {agency_name}   |   DATE RANGE: {date_range_str}", fill=BANNER_SUB_FILL, font=BANNER_SUB_FONT, height=22)

    # Row 3: Spacer
    ws.append([""] * total_cols)
    ws.row_dimensions[3].height = 8

    # Row 4: Headers
    headers = ["SL", "Particulars / Work Item Description", "Records / Qty", "Rate (Rs.)", "Total Amount (Rs.)"]
    ws.append(headers)
    ws.row_dimensions[4].height = 24
    for c in range(1, total_cols + 1):
        cell = ws.cell(4, c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN

    # Section 1: Single Phase (Dual Action removed)
    sec1_row = ws.max_row + 1
    ws.append(["SINGLE PHASE (1PH) WORK ITEMS"])
    ws.merge_cells(start_row=sec1_row, start_column=1, end_row=sec1_row, end_column=total_cols)
    ws.row_dimensions[sec1_row].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(sec1_row, c)
        cell.fill = PART_FILL
        cell.border = BORDER_THIN
    top_cell = ws.cell(sec1_row, 1)
    top_cell.font = PART_FONT
    top_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    items_1ph = [
        (1, "1 Phase - DR (Disconnection & Reconnection)", m["c_1_dr"], m["r_1_dr"], m["amt_1_dr"]),
        (2, "1 Phase - DC (Disconnection)", m["c_1_dc"], m["r_1_dc"], m["amt_1_dc"]),
        (3, "1 Phase - RC (Reconnection)", m["c_1_rc"], m["r_1_rc"], m["amt_1_rc"])
    ]
    for sl, desc, cnt, rate, amt in items_1ph:
        ws.append([sl, desc, cnt, rate, amt])
        cur_r = ws.max_row
        ws.row_dimensions[cur_r].height = 20
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_r, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c == 2:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == 3:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c in (4, 5):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00'

    sub1_row = ws.max_row + 1
    ws.append(["", "SUBTOTAL SINGLE PHASE (1PH)", m["sub_1_count"], "", m["sub_1_amt"]])
    ws.row_dimensions[sub1_row].height = 21
    for c in range(1, total_cols + 1):
        cell = ws.cell(sub1_row, c)
        cell.font = SUBTOTAL_FONT
        cell.fill = SUBTOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 3:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Section 2: Three Phase (Dual Action removed)
    sec3_row = ws.max_row + 1
    ws.append(["THREE PHASE (3PH) WORK ITEMS"])
    ws.merge_cells(start_row=sec3_row, start_column=1, end_row=sec3_row, end_column=total_cols)
    ws.row_dimensions[sec3_row].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(sec3_row, c)
        cell.fill = PART_FILL
        cell.border = BORDER_THIN
    top_cell = ws.cell(sec3_row, 1)
    top_cell.font = PART_FONT
    top_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    items_3ph = [
        (4, "3 Phase - DR (Disconnection & Reconnection)", m["c_3_dr"], m["r_3_dr"], m["amt_3_dr"]),
        (5, "3 Phase - DC (Disconnection)", m["c_3_dc"], m["r_3_dc"], m["amt_3_dc"]),
        (6, "3 Phase - RC (Reconnection)", m["c_3_rc"], m["r_3_rc"], m["amt_3_rc"])
    ]
    for sl, desc, cnt, rate, amt in items_3ph:
        ws.append([sl, desc, cnt, rate, amt])
        cur_r = ws.max_row
        ws.row_dimensions[cur_r].height = 20
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_r, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c == 2:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == 3:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c in (4, 5):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00'

    sub3_row = ws.max_row + 1
    ws.append(["", "SUBTOTAL THREE PHASE (3PH)", m["sub_3_count"], "", m["sub_3_amt"]])
    ws.row_dimensions[sub3_row].height = 21
    for c in range(1, total_cols + 1):
        cell = ws.cell(sub3_row, c)
        cell.font = SUBTOTAL_FONT
        cell.fill = SUBTOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 3:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Grand Total
    gt_row = ws.max_row + 1
    ws.append(["", "GRAND TOTAL PAYABLE", m["grand_count"], "", m["grand_amt"]])
    ws.row_dimensions[gt_row].height = 24
    for c in range(1, total_cols + 1):
        cell = ws.cell(gt_row, c)
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 3:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Highlights Box
    sp_row = ws.max_row + 1
    ws.append([""] * total_cols)
    ws.row_dimensions[sp_row].height = 14

    box_start = ws.max_row + 1
    ws.append(["SUMMARY HIGHLIGHTS", "", "", "", ""])
    ws.merge_cells(start_row=box_start, start_column=1, end_row=box_start, end_column=total_cols)
    ws.cell(box_start, 1).font = TOTAL_FONT
    ws.cell(box_start, 1).alignment = Alignment(horizontal="left")

    ws.append(["1-Phase Total Records:", m["sub_1_count"], "", "1-Phase Payable Amount (Rs):", m["sub_1_amt"]])
    ws.append(["3-Phase Total Records:", m["sub_3_count"], "", "3-Phase Payable Amount (Rs):", m["sub_3_amt"]])
    ws.append(["Overall Total Records:", m["grand_count"], "", "Overall P.O. Payable Amount (Rs):", m["grand_amt"]])

    for r_idx in range(box_start + 1, box_start + 4):
        ws.row_dimensions[r_idx].height = 18
        ws.cell(r_idx, 1).font = DATA_FONT
        ws.cell(r_idx, 2).font = TOTAL_FONT
        ws.cell(r_idx, 2).alignment = Alignment(horizontal="left")
        ws.cell(r_idx, 4).font = DATA_FONT
        c5 = ws.cell(r_idx, 5)
        c5.font = TOTAL_FONT
        c5.alignment = Alignment(horizontal="right")
        c5.number_format = '#,##0.00'

    # Signatures block removed as requested: "THIS PAGE DONT NEED SIGN"

    breakup_widths = {'A': 6, 'B': 44, 'C': 15, 'D': 14, 'E': 18}
    for col_l, w in breakup_widths.items():
        ws.column_dimensions[col_l].width = w

    _setup_portrait_page(ws, title_rows='', fit_to_height=1)
    return ws


def _create_agency_print_all_sheet(wb, agency_name, processed_result, ag_records):
    """
    Creates the comprehensive 'PRINT_ALL' sheet where user can print directly at once:
    - Page 1 contains the complete Breakup Report (without signatures, dual action word removed)
    - Followed by explicit page break so 1PH and 3PH are printed on separate pages!
    - Consumer list has NO total amount in subtotal rows; total counts are merged and centered!
    - Spacings added after parts.
    - Configured for Portrait A4, horizontal centering, repeating table headers, and page numbers.
    """
    ws = wb.create_sheet(title="PRINT_ALL")
    date_range_str = _get_date_range_str(processed_result)
    m = _get_agency_metrics(agency_name, processed_result, ag_records)
    total_cols = 8  # Matched to consumer columns: SL, CID, Type, Amt, Date, Doc, Zone, Phase

    # 1. Title Banner
    ws.append(["PURCHASE ORDER BILLING BREAKUP & DETAILS REPORT"])
    _style_banner_row(ws, 1, total_cols, "PURCHASE ORDER BILLING BREAKUP & DETAILS REPORT", fill=BANNER_FILL, font=BANNER_FONT, height=24)

    # 2. Subtitle Banner
    ws.append([f"AGENCY: {agency_name}   |   DATE RANGE: {date_range_str}"])
    _style_banner_row(ws, 1, total_cols, f"AGENCY: {agency_name}   |   DATE RANGE: {date_range_str}", fill=BANNER_SUB_FILL, font=BANNER_SUB_FONT, height=22)

    # 3. Spacer
    ws.append([""] * total_cols)
    ws.row_dimensions[3].height = 6

    # 4. Breakup Table Header (Spans A to H)
    hdr_row = ws.max_row + 1
    ws.append(["SL", "Particulars / Work Item Description", "", "", "Records / Qty", "Rate (Rs.)", "Total Amount (Rs.)", ""])
    ws.merge_cells(start_row=hdr_row, start_column=2, end_row=hdr_row, end_column=4)
    ws.merge_cells(start_row=hdr_row, start_column=7, end_row=hdr_row, end_column=8)
    ws.row_dimensions[hdr_row].height = 22
    for c in range(1, total_cols + 1):
        cell = ws.cell(hdr_row, c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER_THIN

    # Breakup: Single Phase Section Header (Dual Action removed)
    bsec1_r = ws.max_row + 1
    ws.append(["SINGLE PHASE (1PH) WORK ITEMS"] + [""] * (total_cols - 1))
    ws.merge_cells(start_row=bsec1_r, start_column=1, end_row=bsec1_r, end_column=total_cols)
    ws.row_dimensions[bsec1_r].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(bsec1_r, c)
        cell.fill = PART_FILL
        cell.border = BORDER_THIN
    ws.cell(bsec1_r, 1).font = PART_FONT
    ws.cell(bsec1_r, 1).alignment = Alignment(horizontal="left", vertical="center", indent=1)

    items_1ph = [
        (1, "1 Phase - DR (Disconnection & Reconnection)", m["c_1_dr"], m["r_1_dr"], m["amt_1_dr"]),
        (2, "1 Phase - DC (Disconnection)", m["c_1_dc"], m["r_1_dc"], m["amt_1_dc"]),
        (3, "1 Phase - RC (Reconnection)", m["c_1_rc"], m["r_1_rc"], m["amt_1_rc"])
    ]
    for sl, desc, cnt, rate, amt in items_1ph:
        ws.append([sl, desc, "", "", cnt, rate, amt, ""])
        cur_r = ws.max_row
        ws.merge_cells(start_row=cur_r, start_column=2, end_row=cur_r, end_column=4)
        ws.merge_cells(start_row=cur_r, start_column=7, end_row=cur_r, end_column=8)
        ws.row_dimensions[cur_r].height = 19
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_r, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c == 2:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == 5:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c in (6, 7):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00'

    # Breakup: Subtotal 1PH
    bsub1_r = ws.max_row + 1
    ws.append(["", "SUBTOTAL SINGLE PHASE (1PH)", "", "", m["sub_1_count"], "", m["sub_1_amt"], ""])
    ws.merge_cells(start_row=bsub1_r, start_column=2, end_row=bsub1_r, end_column=4)
    ws.merge_cells(start_row=bsub1_r, start_column=7, end_row=bsub1_r, end_column=8)
    ws.row_dimensions[bsub1_r].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(bsub1_r, c)
        cell.font = SUBTOTAL_FONT
        cell.fill = SUBTOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 7:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Breakup: Three Phase Section Header (Dual Action removed)
    bsec3_r = ws.max_row + 1
    ws.append(["THREE PHASE (3PH) WORK ITEMS"] + [""] * (total_cols - 1))
    ws.merge_cells(start_row=bsec3_r, start_column=1, end_row=bsec3_r, end_column=total_cols)
    ws.row_dimensions[bsec3_r].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(bsec3_r, c)
        cell.fill = PART_FILL
        cell.border = BORDER_THIN
    ws.cell(bsec3_r, 1).font = PART_FONT
    ws.cell(bsec3_r, 1).alignment = Alignment(horizontal="left", vertical="center", indent=1)

    items_3ph = [
        (4, "3 Phase - DR (Disconnection & Reconnection)", m["c_3_dr"], m["r_3_dr"], m["amt_3_dr"]),
        (5, "3 Phase - DC (Disconnection)", m["c_3_dc"], m["r_3_dc"], m["amt_3_dc"]),
        (6, "3 Phase - RC (Reconnection)", m["c_3_rc"], m["r_3_rc"], m["amt_3_rc"])
    ]
    for sl, desc, cnt, rate, amt in items_3ph:
        ws.append([sl, desc, "", "", cnt, rate, amt, ""])
        cur_r = ws.max_row
        ws.merge_cells(start_row=cur_r, start_column=2, end_row=cur_r, end_column=4)
        ws.merge_cells(start_row=cur_r, start_column=7, end_row=cur_r, end_column=8)
        ws.row_dimensions[cur_r].height = 19
        for c in range(1, total_cols + 1):
            cell = ws.cell(cur_r, c)
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if c == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c == 2:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            elif c == 5:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif c in (6, 7):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00'

    # Breakup: Subtotal 3PH
    bsub3_r = ws.max_row + 1
    ws.append(["", "SUBTOTAL THREE PHASE (3PH)", "", "", m["sub_3_count"], "", m["sub_3_amt"], ""])
    ws.merge_cells(start_row=bsub3_r, start_column=2, end_row=bsub3_r, end_column=4)
    ws.merge_cells(start_row=bsub3_r, start_column=7, end_row=bsub3_r, end_column=8)
    ws.row_dimensions[bsub3_r].height = 20
    for c in range(1, total_cols + 1):
        cell = ws.cell(bsub3_r, c)
        cell.font = SUBTOTAL_FONT
        cell.fill = SUBTOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 7:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Breakup: Grand Total Row
    bgt_r = ws.max_row + 1
    ws.append(["", "GRAND TOTAL PAYABLE", "", "", m["grand_count"], "", m["grand_amt"], ""])
    ws.merge_cells(start_row=bgt_r, start_column=2, end_row=bgt_r, end_column=4)
    ws.merge_cells(start_row=bgt_r, start_column=7, end_row=bgt_r, end_column=8)
    ws.row_dimensions[bgt_r].height = 22
    for c in range(1, total_cols + 1):
        cell = ws.cell(bgt_r, c)
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
        if c == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif c == 5:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif c == 7:
            cell.alignment = Alignment(horizontal="right", vertical="center")
            cell.number_format = '#,##0.00'

    # Breakup: Summary Highlights
    sp_row = ws.max_row + 1
    ws.append([""] * total_cols)
    ws.row_dimensions[sp_row].height = 14

    box_start = ws.max_row + 1
    ws.append(["SUMMARY HIGHLIGHTS", "", "", "", "", "", "", ""])
    ws.merge_cells(start_row=box_start, start_column=1, end_row=box_start, end_column=total_cols)
    ws.cell(box_start, 1).font = TOTAL_FONT
    ws.cell(box_start, 1).alignment = Alignment(horizontal="left")

    ws.append(["1-Phase Total Records:", m["sub_1_count"], "", "", "1-Phase Payable Amount (Rs):", "", m["sub_1_amt"], ""])
    ws.merge_cells(start_row=box_start + 1, start_column=5, end_row=box_start + 1, end_column=6)
    ws.merge_cells(start_row=box_start + 1, start_column=7, end_row=box_start + 1, end_column=8)

    ws.append(["3-Phase Total Records:", m["sub_3_count"], "", "", "3-Phase Payable Amount (Rs):", "", m["sub_3_amt"], ""])
    ws.merge_cells(start_row=box_start + 2, start_column=5, end_row=box_start + 2, end_column=6)
    ws.merge_cells(start_row=box_start + 2, start_column=7, end_row=box_start + 2, end_column=8)

    ws.append(["Overall Total Records:", m["grand_count"], "", "", "Overall P.O. Payable Amount (Rs):", "", m["grand_amt"], ""])
    ws.merge_cells(start_row=box_start + 3, start_column=5, end_row=box_start + 3, end_column=6)
    ws.merge_cells(start_row=box_start + 3, start_column=7, end_row=box_start + 3, end_column=8)

    for r_idx in range(box_start + 1, box_start + 4):
        ws.row_dimensions[r_idx].height = 18
        ws.cell(r_idx, 1).font = DATA_FONT
        ws.cell(r_idx, 2).font = TOTAL_FONT
        ws.cell(r_idx, 2).alignment = Alignment(horizontal="left")
        ws.cell(r_idx, 5).font = DATA_FONT
        c7 = ws.cell(r_idx, 7)
        c7.font = TOTAL_FONT
        c7.alignment = Alignment(horizontal="right")
        c7.number_format = '#,##0.00'

    # Signatures block removed as requested: "REMOVE PREPARED BY CHECKED BY AND AUTHOROZED SIGNS.. THIS PAGE DONT NEED SIGN"

    # PAGE BREAK: Page 1 prints Breakup Report only!
    breakup_last_row = ws.max_row
    ws.row_breaks.append(Break(id=breakup_last_row))

    det_headers = ['SL', 'Consumer ID', 'Payment Type', 'Amount', 'Payment Date', 'DOC NUMBER', 'ZONE', 'Phase']
    consumer_header_rows = []

    # ==========================================
    # SECTION 2: SINGLE PHASE (1PH) DETAILS (PAGE 2)
    # ==========================================
    phase1_records = [r for r in ag_records if r.get("phase") == 1]
    if phase1_records:
        ws.append([""] * total_cols)
        ws.row_dimensions[ws.max_row].height = 8

        # 1PH Main Section Title
        p1_title_row = ws.max_row + 1
        ws.append([f"1 PHASE (1PH) DETAILED CONSUMER LIST   |   AGENCY: {agency_name}"] + [""] * (total_cols - 1))
        ws.merge_cells(start_row=p1_title_row, start_column=1, end_row=p1_title_row, end_column=total_cols)
        ws.row_dimensions[p1_title_row].height = 24
        for c in range(1, total_cols + 1):
            cell = ws.cell(p1_title_row, c)
            cell.fill = BANNER_FILL
            cell.border = BORDER_THIN
        ws.cell(p1_title_row, 1).font = BANNER_FONT
        ws.cell(p1_title_row, 1).alignment = Alignment(horizontal="center", vertical="center")

        # 1PH Table Column Headers
        p1_hdr_row = ws.max_row + 1
        consumer_header_rows.append(p1_hdr_row)
        ws.append(det_headers)
        ws.row_dimensions[p1_hdr_row].height = 24
        for c in range(1, total_cols + 1):
            cell = ws.cell(p1_hdr_row, c)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORDER_THIN

        cur_part_idx = 1
        phase1_total_count = 0

        for ptype, part_label in PARTS_CONFIG_AGENCY:
            part_records = [
                r for r in phase1_records
                if str(r.get("payment_type") or "").strip().upper() == ptype
            ]
            if not part_records:
                continue

            phase1_total_count += len(part_records)

            # Part Header Banner (Dual Action removed, NO amount)
            pb_row = ws.max_row + 1
            part_title = f"PART {cur_part_idx}: 1 PHASE - {part_label}   |   COUNT: {len(part_records)}"
            ws.append([part_title] + [""] * (total_cols - 1))
            ws.merge_cells(start_row=pb_row, start_column=1, end_row=pb_row, end_column=total_cols)
            ws.row_dimensions[pb_row].height = 21
            for c in range(1, total_cols + 1):
                cell = ws.cell(pb_row, c)
                cell.fill = PART_FILL
                cell.border = BORDER_THIN
            ws.cell(pb_row, 1).font = PART_FONT
            ws.cell(pb_row, 1).alignment = Alignment(horizontal="left", vertical="center", indent=1)

            # Data rows (SL countable 1..N)
            for sl, r in enumerate(part_records, start=1):
                try:
                    amt_val = float(r["amount"])
                except (ValueError, TypeError):
                    amt_val = r["amount"]

                row_vals = [
                    sl, r["consumer_id"], r["payment_type"], amt_val,
                    r["payment_date"], r["doc_number"], r["zone"], r["phase"]
                ]
                ws.append(row_vals)
                cur_r = ws.max_row
                ws.row_dimensions[cur_r].height = 19
                for c in range(1, total_cols + 1):
                    cell = ws.cell(cur_r, c)
                    cell.font = DATA_FONT
                    cell.border = BORDER_THIN
                    if c == 4 and isinstance(amt_val, (int, float)):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.number_format = '#,##0.00'
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")

            # Part Details Subtotal Row: NO TOTAL AMOUNT, MERGED AND CENTERED TOTAL COUNT
            sub_row = ws.max_row + 1
            ws.append([f"TOTAL 1PH {ptype} RECORDS: {len(part_records)}"] + [""] * (total_cols - 1))
            ws.merge_cells(start_row=sub_row, start_column=1, end_row=sub_row, end_column=total_cols)
            ws.row_dimensions[sub_row].height = 20
            for c in range(1, total_cols + 1):
                cell = ws.cell(sub_row, c)
                cell.fill = SUBTOTAL_FILL
                cell.border = BORDER_DOUBLE_BOTTOM
            mid_c = ws.cell(sub_row, 1)
            mid_c.font = SUBTOTAL_FONT
            mid_c.alignment = Alignment(horizontal="center", vertical="center")

            # Spacing after parts
            ws.append([""] * total_cols)
            ws.row_dimensions[ws.max_row].height = 10

            cur_part_idx += 1

        # Total 1-Phase Row (Merged and Centered count, NO amount)
        p1_tot_r = ws.max_row + 1
        ws.append([f"TOTAL SINGLE PHASE (1PH) RECORDS: {phase1_total_count}"] + [""] * (total_cols - 1))
        ws.merge_cells(start_row=p1_tot_r, start_column=1, end_row=p1_tot_r, end_column=total_cols)
        ws.row_dimensions[p1_tot_r].height = 22
        for c in range(1, total_cols + 1):
            cell = ws.cell(p1_tot_r, c)
            cell.fill = TOTAL_FILL
            cell.border = BORDER_DOUBLE_BOTTOM
        ws.cell(p1_tot_r, 1).font = TOTAL_FONT
        ws.cell(p1_tot_r, 1).alignment = Alignment(horizontal="center", vertical="center")

    # ==========================================
    # PAGE BREAK: 1PH AND 3PH ON DIFFERENT PAGES!
    # ==========================================
    phase3_records = [r for r in ag_records if r.get("phase") == 3]
    if phase3_records:
        p1_last_row = ws.max_row
        ws.row_breaks.append(Break(id=p1_last_row))

        # ==========================================
        # SECTION 3: THREE PHASE (3PH) DETAILS
        # ==========================================
        ws.append([""] * total_cols)
        ws.row_dimensions[ws.max_row].height = 8

        # 3PH Main Section Title
        p3_title_row = ws.max_row + 1
        ws.append([f"3 PHASE (3PH) DETAILED CONSUMER LIST   |   AGENCY: {agency_name}"] + [""] * (total_cols - 1))
        ws.merge_cells(start_row=p3_title_row, start_column=1, end_row=p3_title_row, end_column=total_cols)
        ws.row_dimensions[p3_title_row].height = 24
        for c in range(1, total_cols + 1):
            cell = ws.cell(p3_title_row, c)
            cell.fill = BANNER_FILL
            cell.border = BORDER_THIN
        ws.cell(p3_title_row, 1).font = BANNER_FONT
        ws.cell(p3_title_row, 1).alignment = Alignment(horizontal="center", vertical="center")

        # 3PH Table Column Headers
        p3_hdr_row = ws.max_row + 1
        ws.append(det_headers)
        ws.row_dimensions[p3_hdr_row].height = 24
        for c in range(1, total_cols + 1):
            cell = ws.cell(p3_hdr_row, c)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORDER_THIN

        cur_part_idx = 1
        phase3_total_count = 0

        for ptype, part_label in PARTS_CONFIG_AGENCY:
            part_records = [
                r for r in phase3_records
                if str(r.get("payment_type") or "").strip().upper() == ptype
            ]
            if not part_records:
                continue

            phase3_total_count += len(part_records)

            # Part Header Banner (Dual Action removed, NO amount)
            pb_row = ws.max_row + 1
            part_title = f"PART {cur_part_idx}: 3 PHASE - {part_label}   |   COUNT: {len(part_records)}"
            ws.append([part_title] + [""] * (total_cols - 1))
            ws.merge_cells(start_row=pb_row, start_column=1, end_row=pb_row, end_column=total_cols)
            ws.row_dimensions[pb_row].height = 21
            for c in range(1, total_cols + 1):
                cell = ws.cell(pb_row, c)
                cell.fill = PART_FILL
                cell.border = BORDER_THIN
            ws.cell(pb_row, 1).font = PART_FONT
            ws.cell(pb_row, 1).alignment = Alignment(horizontal="left", vertical="center", indent=1)

            # Data rows (SL countable 1..N)
            for sl, r in enumerate(part_records, start=1):
                try:
                    amt_val = float(r["amount"])
                except (ValueError, TypeError):
                    amt_val = r["amount"]

                row_vals = [
                    sl, r["consumer_id"], r["payment_type"], amt_val,
                    r["payment_date"], r["doc_number"], r["zone"], r["phase"]
                ]
                ws.append(row_vals)
                cur_r = ws.max_row
                ws.row_dimensions[cur_r].height = 19
                for c in range(1, total_cols + 1):
                    cell = ws.cell(cur_r, c)
                    cell.font = DATA_FONT
                    cell.border = BORDER_THIN
                    if c == 4 and isinstance(amt_val, (int, float)):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.number_format = '#,##0.00'
                    else:
                        cell.alignment = Alignment(horizontal="center", vertical="center")

            # Part Details Subtotal Row: NO TOTAL AMOUNT, MERGED AND CENTERED TOTAL COUNT
            sub_row = ws.max_row + 1
            ws.append([f"TOTAL 3PH {ptype} RECORDS: {len(part_records)}"] + [""] * (total_cols - 1))
            ws.merge_cells(start_row=sub_row, start_column=1, end_row=sub_row, end_column=total_cols)
            ws.row_dimensions[sub_row].height = 20
            for c in range(1, total_cols + 1):
                cell = ws.cell(sub_row, c)
                cell.fill = SUBTOTAL_FILL
                cell.border = BORDER_DOUBLE_BOTTOM
            mid_c = ws.cell(sub_row, 1)
            mid_c.font = SUBTOTAL_FONT
            mid_c.alignment = Alignment(horizontal="center", vertical="center")

            # Spacing after parts
            ws.append([""] * total_cols)
            ws.row_dimensions[ws.max_row].height = 10

            cur_part_idx += 1

        # Total 3-Phase Row (Merged and Centered count, NO amount)
        p3_tot_r = ws.max_row + 1
        ws.append([f"TOTAL THREE PHASE (3PH) RECORDS: {phase3_total_count}"] + [""] * (total_cols - 1))
        ws.merge_cells(start_row=p3_tot_r, start_column=1, end_row=p3_tot_r, end_column=total_cols)
        ws.row_dimensions[p3_tot_r].height = 22
        for c in range(1, total_cols + 1):
            cell = ws.cell(p3_tot_r, c)
            cell.fill = TOTAL_FILL
            cell.border = BORDER_DOUBLE_BOTTOM
        ws.cell(p3_tot_r, 1).font = TOTAL_FONT
        ws.cell(p3_tot_r, 1).alignment = Alignment(horizontal="center", vertical="center")

    # OVERALL GRAND TOTAL COUNT ROW (Merged & Centered, NO amount)
    gtot_r = ws.max_row + 1
    ws.append([f"OVERALL TOTAL RECORDS: {m['grand_count']}"] + [""] * (total_cols - 1))
    ws.merge_cells(start_row=gtot_r, start_column=1, end_row=gtot_r, end_column=total_cols)
    ws.row_dimensions[gtot_r].height = 24
    for c in range(1, total_cols + 1):
        cell = ws.cell(gtot_r, c)
        cell.fill = TOTAL_FILL
        cell.border = BORDER_DOUBLE_BOTTOM
    ws.cell(gtot_r, 1).font = TOTAL_FONT
    ws.cell(gtot_r, 1).alignment = Alignment(horizontal="center", vertical="center")

    # Repeat consumer table headers across subsequent pages
    repeat_hdr = consumer_header_rows[0] if consumer_header_rows else ""
    title_rows_str = f"{repeat_hdr}:{repeat_hdr}" if repeat_hdr else ""

    _setup_portrait_page(ws, title_rows=title_rows_str, fit_to_height=0)
    _apply_value_based_widths(ws, det_headers, data_start_row=3)
    return ws


def _create_raw_data_sheet(wb, headers, records, is_master=False):
    """
    Creates a pure, completely unformatted data sheet:
    Just column headers on Row 1 and pure raw records below.
    Zero formatting, zero colors, zero custom fonts.
    """
    ws = wb.create_sheet(title="RAW_DATA")
    ws.append(headers)
    for sl, r in enumerate(records, start=1):
        if is_master:
            ws.append([
                sl, r["consumer_id"], r["payment_type"], r["amount"],
                r["payment_date"], r["doc_number"], r["zone"],
                r["agency"], r["phase"]
            ])
        else:
            ws.append([
                sl, r["consumer_id"], r["payment_type"], r["amount"],
                r["payment_date"], r["doc_number"], r["zone"],
                r["phase"]
            ])
    return ws
