import os
import re
import csv
import datetime
import openpyxl


def detect_file_format(file_path):
    """
    Detects the real format of an uploaded file regardless of extension:
    Returns: 'xlsx', 'utf16_tsv', 'ole_xls', 'text_csv'
    """
    if not os.path.exists(file_path):
        return 'unknown'
    with open(file_path, 'rb') as f:
        header = f.read(32)
    if header.startswith(b'PK\x03\x04'):
        return 'xlsx'
    if header.startswith(b'\xff\xfe') or b'\x00' in header[:16]:
        return 'utf16_tsv'
    if header.startswith(b'\xd0\xcf\x11\xe0'):
        return 'ole_xls'
    return 'text_csv'


def normalize_date_str(val):
    """Normalizes any date object or string into standard 'dd.mm.yyyy' string."""
    if val is None:
        return ""
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%d.%m.%Y")
    s = str(val).strip()
    # If in yyyy-mm-dd format
    m_iso = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', s)
    if m_iso:
        y, m, d = m_iso.groups()
        return f"{int(d):02d}.{int(m):02d}.{int(y):04d}"
    # If in dd.mm.yyyy or dd-mm-yyyy or dd/mm/yyyy
    m_dmy = re.match(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})', s)
    if m_dmy:
        d, m, y = m_dmy.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{int(d):02d}.{int(m):02d}.{int(y):04d}"
    return s


def parse_date_obj(date_str):
    """Parses 'dd.mm.yyyy' string into datetime.date object for accurate comparison."""
    if not date_str:
        return None
    s = normalize_date_str(date_str)
    try:
        parts = s.split('.')
        if len(parts) == 3:
            return datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
    except:
        pass
    return None


def format_amount_str(amt):
    """Formats amount as standard number string without unnecessary decimals (e.g. 100 or 1360)."""
    if amt is None or amt == '':
        return '0'
    try:
        f = float(str(amt).replace(',', '').strip())
        if f.is_integer():
            return str(int(f))
        return f"{f:.2f}"
    except:
        return str(amt).strip()


def parse_sap_utf16_tsv(file_path):
    """
    Parses SAP Unicode UTF-16LE tab-separated reports (like DC.XLS, RC.XLS, DR.xls, ONLINE DR.XLS).
    Skips report header metadata and locates table headers.
    """
    with open(file_path, 'r', encoding='utf-16', errors='ignore') as f:
        lines = f.readlines()

    header_idx = -1
    col_names = []
    for i, line in enumerate(lines[:30]):
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        # Check if this line contains standard column names
        lowers = [p.lower() for p in parts]
        if any('consumer' in p or 'con_id' in p for p in lowers) or ('payment type' in lowers and 'amount' in lowers):
            header_idx = i
            col_names = parts
            break

    if header_idx == -1:
        # Fallback: line containing tabs with multiple non-empty tokens
        for i, line in enumerate(lines[:20]):
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if len(parts) >= 4:
                header_idx = i
                col_names = parts
                break

    rows = []
    if header_idx != -1:
        for line in lines[header_idx + 1:]:
            parts = [p.strip() for p in line.split('\t')]
            # filter leading/trailing empty tab splits
            cleaned = [p for p in parts if p != '']
            if len(cleaned) >= 3:
                rows.append(cleaned)

    return col_names, rows


def _read_file_rows(file_path, sheet_name=None):
    """
    Reads rows from any file (.xlsx, SAP UTF-16 TSV, CSV, or .xls) without requiring pandas.
    Returns list of lists/tuples.
    """
    fmt = detect_file_format(file_path)
    if fmt == 'xlsx':
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
            return list(ws.iter_rows(values_only=True))
        finally:
            wb.close()
    elif fmt == 'utf16_tsv':
        col_names, raw_rows = parse_sap_utf16_tsv(file_path)
        return [col_names] + raw_rows
    elif fmt == 'ole_xls':
        try:
            import xlrd
            wb = xlrd.open_workbook(file_path)
            sheet = wb.sheet_by_name(sheet_name) if sheet_name and sheet_name in wb.sheet_names() else wb.sheet_by_index(0)
            return [sheet.row_values(r) for r in range(sheet.nrows)]
        except Exception:
            pass

    # Fallback to standard CSV / text with encoding detection
    for enc in ('utf-8', 'cp1252', 'latin1'):
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                sample = f.read(2048)
                f.seek(0)
                delimiter = '\t' if '\t' in sample else ','
                reader = csv.reader(f, delimiter=delimiter)
                return list(reader)
        except Exception:
            continue
    return []


def find_column_by_synonyms(headers, synonyms, default_idx=-1):
    """Matches a header against a list of synonym substrings."""
    for i, h in enumerate(headers):
        if h is None:
            continue
        hl = str(h).strip().lower()
        if any(s in hl for s in synonyms):
            return i
    return default_idx


def parse_dcrc_event_file(file_path):
    """
    Parses an individual DCRC file (DC, RC, DR, ONLINE DR) and returns a normalized list of dicts:
    [
       {
          "consumer_id": "300873317",
          "payment_type": "DC",
          "amount": 40.0,
          "amount_str": "40",
          "payment_date": "08.01.2026",
          "payment_date_obj": datetime.date(2026, 1, 8),
          "source_file": "DC.XLS",
          "coll_agency": "BILLDESK"
       }, ...
    ]
    """
    fname = os.path.basename(file_path)
    fmt = detect_file_format(file_path)
    records = []

    cid_synonyms = ['consumer', 'con_id', 'con id', 'account', 'acct', 'cid', 'ca no', 'ca_no']
    type_synonyms = ['payment type', 'pay type', 'type', 'activity', 'action']
    amt_synonyms = ['amount', 'amt', 'fee', 'charges']
    date_synonyms = ['payment date', 'pay date', 'entry date', 'entered on', 'date', 'dt']
    coll_synonyms = ['coll', 'agency', 'channel', 'mode']

    if fmt == 'utf16_tsv':
        col_names, raw_rows = parse_sap_utf16_tsv(file_path)

        cid_idx = find_column_by_synonyms(col_names, cid_synonyms, 0)
        type_idx = find_column_by_synonyms(col_names, type_synonyms, 1)
        amt_idx = find_column_by_synonyms(col_names, amt_synonyms, 2)
        date_idx = find_column_by_synonyms(col_names, date_synonyms, 3)
        coll_idx = find_column_by_synonyms(col_names, coll_synonyms, -1)

        for row in raw_rows:
            try:
                cid = row[cid_idx] if (cid_idx != -1 and cid_idx < len(row)) else row[0]
                cid_clean = str(cid).strip()
                if not cid_clean.isdigit() and len(cid_clean) < 8:
                    continue

                if type_idx != -1 and type_idx < len(row):
                    ptype = row[type_idx]
                elif len(row) > 3 and str(row[3]).strip() in ('DC', 'RC', 'DR'):
                    ptype = row[3]
                else:
                    ptype = row[1] if len(row) > 1 else ''

                if amt_idx != -1 and amt_idx < len(row):
                    amt = row[amt_idx]
                else:
                    amt = row[2] if len(row) > 2 else '0'

                if date_idx != -1 and date_idx < len(row):
                    pdate = row[date_idx]
                else:
                    pdate = row[3] if len(row) > 3 else ''

                coll_agency = row[coll_idx].strip() if (coll_idx != -1 and coll_idx < len(row)) else ''

                ptype_clean = str(ptype).strip().upper()
                if not ptype_clean:
                    for code in ('DC', 'RC', 'DR'):
                        if code in fname.upper():
                            ptype_clean = code
                            break

                date_norm = normalize_date_str(pdate)
                amt_formatted = format_amount_str(amt)

                records.append({
                    "consumer_id": cid_clean,
                    "payment_type": ptype_clean,
                    "amount": float(amt_formatted) if amt_formatted else 0.0,
                    "amount_str": amt_formatted,
                    "payment_date": date_norm,
                    "payment_date_obj": parse_date_obj(date_norm),
                    "source_file": fname,
                    "coll_agency": coll_agency
                })
            except Exception:
                continue

    else:
        # Read using openpyxl or csv without pandas
        try:
            rows = _read_file_rows(file_path)
            if not rows:
                return []

            # Find header row
            header_row_idx = 0
            for r in range(min(15, len(rows))):
                row_vals = [str(x).lower() for x in rows[r] if x is not None]
                if any('consumer' in x for x in row_vals) and any('amount' in x for x in row_vals):
                    header_row_idx = r
                    break

            header = [str(x).strip().lower() if x is not None else '' for x in rows[header_row_idx]]
            cid_idx = next((i for i, c in enumerate(header) if 'consumer' in c or 'con_id' in c), 0)
            type_idx = next((i for i, c in enumerate(header) if 'type' in c), 1)
            amt_idx = next((i for i, c in enumerate(header) if 'amount' in c), 2)
            date_idx = next((i for i, c in enumerate(header) if 'date' in c), 3)

            for row in rows[header_row_idx + 1:]:
                if len(row) <= max(cid_idx, type_idx, amt_idx, date_idx):
                    continue
                cid_val = row[cid_idx]
                if cid_val is None:
                    continue
                cid = str(cid_val).strip()
                if not cid or not cid.isdigit():
                    continue

                ptype = str(row[type_idx]).strip().upper() if type_idx < len(row) and row[type_idx] is not None else ''
                amt = row[amt_idx] if amt_idx < len(row) else 0
                pdate = row[date_idx] if date_idx < len(row) else ''

                date_norm = normalize_date_str(pdate)
                amt_formatted = format_amount_str(amt)

                records.append({
                    "consumer_id": cid,
                    "payment_type": ptype,
                    "amount": float(amt_formatted) if amt_formatted else 0.0,
                    "amount_str": amt_formatted,
                    "payment_date": date_norm,
                    "payment_date_obj": parse_date_obj(date_norm),
                    "source_file": fname,
                    "coll_agency": ""
                })
        except Exception as e:
            print(f"Error parsing excel/csv DCRC file {fname}: {e}")

    return records


def parse_cash_payment_file(file_path):
    """
    Parses a Cash Payment file (cash1.XLSX, CASH2.XLSX, etc.).
    Returns a dictionary of payment documents keyed by:
    1. Primary Key: f"{consumer_id}-{amount_str}-{date_str}" -> doc_no
    2. Fallback Key: f"{consumer_id}-{amount_str}" -> list of doc_nos
    """
    primary_lookup = {}
    fallback_lookup = {}

    rows = _read_file_rows(file_path)
    if not rows:
        return primary_lookup, fallback_lookup

    # Find headers
    headers = [str(c).strip().lower() if c is not None else '' for c in rows[0]]
    cid_idx = -1
    date_idx = -1
    amt_idx = -1
    doc_idx = -1

    for i, h in enumerate(headers):
        if 'time' in h or 'revers' in h:
            continue
        if 'account' in h or 'consumer' in h or 'acct' in h:
            cid_idx = i
        elif 'entered on' in h or 'entry date' in h or 'payment date' in h:
            date_idx = i
        elif 'date' in h and date_idx == -1:
            date_idx = i
        elif 'amount' in h:
            amt_idx = i
        elif 'document number' in h or 'doc. no' in h or 'doc no' in h:
            doc_idx = i
        elif ('doc' in h or 'document' in h) and doc_idx == -1:
            doc_idx = i

    # Fallback to column index 0, 1, 5, 6 (typical SAP cash desk layout)
    if cid_idx == -1: cid_idx = 0
    if date_idx == -1: date_idx = 1
    if amt_idx == -1: amt_idx = 5
    if doc_idx == -1: doc_idx = 6

    for row in rows[1:]:
        if len(row) <= max(cid_idx, date_idx, amt_idx, doc_idx):
            continue
        cid_val = row[cid_idx]
        if cid_val is None:
            continue
        cid = str(cid_val).strip()
        # Ignore non-digit opening/summary balance lines
        if not cid.isdigit():
            continue

        doc_val = row[doc_idx]
        doc_no = str(doc_val).strip() if doc_val is not None else ''
        if not doc_no or doc_no == 'None':
            continue

        amt_str = format_amount_str(row[amt_idx])
        date_str = normalize_date_str(row[date_idx])

        primary_key = f"{cid}-{amt_str}-{date_str}"
        primary_lookup[primary_key] = doc_no

        fallback_key = f"{cid}-{amt_str}"
        if fallback_key not in fallback_lookup:
            fallback_lookup[fallback_key] = []
        fallback_lookup[fallback_key].append(doc_no)

    return primary_lookup, fallback_lookup


def parse_consumer_master_file(file_path):
    """
    Parses a Consumer Master file (e.g. Consumer Data.xlsx or CSV).
    Columns expected:
    - Consumer ID (CON_ID)
    - Zone / MRU
    - Phase (CONN_PHASE: 1 or 3)
    Returns:
    {
       "301290315": {"mru": "K4S08MMR", "phase": 1}, ...
    }
    """
    rows = _read_file_rows(file_path, sheet_name='Consumer Data')
    if not rows:
        return {}

    headers = [str(c).strip().lower() if c is not None else '' for c in rows[0]]
    cid_idx = -1
    mru_idx = -1
    phase_idx = -1

    for i, h in enumerate(headers):
        if 'consumer' in h or 'con_id' in h or 'account' in h or 'cid' in h:
            cid_idx = i
        elif 'mru' in h or 'zone' in h:
            mru_idx = i
        elif 'phase' in h:
            phase_idx = i

    if cid_idx == -1: cid_idx = 0
    if mru_idx == -1: mru_idx = 1
    if phase_idx == -1: phase_idx = 2

    consumer_map = {}
    for r in rows[1:]:
        if len(r) <= cid_idx or r[cid_idx] is None:
            continue
        cid_str = str(r[cid_idx]).strip()
        if not cid_str or not cid_str.isdigit():
            continue

        mru_str = str(r[mru_idx]).strip().upper() if (mru_idx < len(r) and r[mru_idx] is not None) else ''

        phase_val = 1
        if phase_idx < len(r) and r[phase_idx] is not None:
            p_str = str(r[phase_idx]).strip()
            if '3' in p_str:
                phase_val = 3
            elif '1' in p_str:
                phase_val = 1

        consumer_map[cid_str] = {
            "mru": mru_str,
            "phase": phase_val
        }

    return consumer_map


def parse_zones_file(file_path):
    """
    Parses Zones.xlsx / Zones file.
    Expected Layout:
    Row 1: 'zone', '27.11.2025', '02.01.2026', '11.02.2026', '19.02.2026' ...
    Subsequent rows: 'K4S02MMR', 'ABDUL MATIN', 'ABDUL MATIN', ...

    Returns:
    {
       "date_cutoffs": [datetime.date(2025, 11, 27), datetime.date(2026, 1, 2), ...],
       "date_strings": ["27.11.2025", "02.01.2026", ...],
       "zones": {
           "K4S08MMR": [
               {"start_date": datetime.date(2025, 11, 27), "agency": "ABDUL MATIN"},
               {"start_date": datetime.date(2026, 1, 2), "agency": "ABDUL MATIN"},
               {"start_date": datetime.date(2026, 2, 11), "agency": "SA"},
               {"start_date": datetime.date(2026, 2, 19), "agency": "SA"}
           ]
       }
    }
    """
    rows = _read_file_rows(file_path)
    if not rows:
        return {"date_cutoffs": [], "date_strings": [], "zones": {}}

    header_row = rows[0]
    zone_idx = 0
    date_columns = []  # list of (col_idx, date_obj, date_str)

    for i, h in enumerate(header_row):
        if h is None: continue
        h_str = str(h).strip()
        if 'zone' in h_str.lower() or 'mru' in h_str.lower():
            zone_idx = i
            continue
        d_obj = parse_date_obj(h_str)
        if d_obj:
            date_columns.append((i, d_obj, normalize_date_str(h_str)))

    # Sort date columns chronologically
    date_columns.sort(key=lambda x: x[1])

    zone_map = {}
    for r in rows[1:]:
        if len(r) <= zone_idx or r[zone_idx] is None:
            continue
        z_name = str(r[zone_idx]).strip().upper()
        if not z_name:
            continue

        periods = []
        for col_idx, d_obj, d_str in date_columns:
            if col_idx < len(r) and r[col_idx] is not None:
                agency = str(r[col_idx]).strip().upper()
                if agency:
                    periods.append({"start_date": d_obj, "date_str": d_str, "agency": agency})

        zone_map[z_name] = periods

    return {
        "date_cutoffs": [x[1] for x in date_columns],
        "date_strings": [x[2] for x in date_columns],
        "zones": zone_map
    }
