"""
Handles the setup and initialization of the SQLite database.
"""
import sqlite3

# --- EXACT OFFICIAL DATABASE ENGINE ---
def setup_database():
    """
    Connects to the database, creates tables if they don't exist,
    and populates them with initial data if they are empty.
    """
    # Connect to the database file in the parent directory
    conn = sqlite3.connect('erp_master.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS materials (item_code TEXT, item_name TEXT PRIMARY KEY, rate REAL, unit TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS labor (labor_code TEXT PRIMARY KEY, task_name TEXT, rate REAL, unit TEXT)''')

    cursor.execute("SELECT COUNT(*) FROM materials")
    if cursor.fetchone()[0] == 0:
        materials = [
            ("110030141", "P C C POLE:8 Mtrs.Long", 5363.44, "NOS"), ("110030241", "P C C POLE:9 Mtrs.Long", 10198.28, "NOS"),
            ("301018141", "Dist. Transformer 25KVA", 103528.11, "NOS"), ("301018241", "Dist. Transformer 63KVA", 107589.53, "NOS"),
            ("102010611", "M.S Channel 75X40 mm", 110043.09, "MT"), ("101011311", "M.S Angle 65X65X6mm", 108667.24, "MT"),
            ("103011511", "M.S Flat 65X6 mm", 117493.74, "MT"), ("505030641", "Suspension Clamp Suitable for 35sq.mm. Messenger Conductor", 367.62, "NOS"),
            ("505034141", "Dead end clamp LT ABC", 389.66, "NOS"), 
            ("505030841", "Eye hook for anchor clamp", 110.64, "NOS"),
            ("504027141", "IPC for connecting ABC to ABC TEE joint", 149.17, "NOS"),
            ("508040441", "Shakle Insulator", 23.34, "NOS"), 
            ("508030541", "11 KV Polymer Disc Insulator 45KN", 183.15, "NOS"), ("508011141", "11 KV Polymer Pin Insulator 45KN", 243.79, "NOS"),
            ("504010132", "Hardware fittings 11KV", 327.83, "SET"), ("504070441", "LT Spacer 3 PHASE 4 WIRE", 77.62, "NOS"),
            ("502010921", "ACSR Conductor 50SQMM", 62290.12, "KM"), ("501030521", "LT AB CABLE 1.1KV 3CX50+1CX16+1CX35sqmm", 315558.99, "KM"), 
            ("504110541", "G.I. Earth Spike 6*3.25ft", 367.98, "NOS"), ("504130432", "H.T. Stay Set Complete", 795.83, "SET"),
            ("504130332", "LT Stay set", 462.17, "SET"), ("508040841", "H.T. Guy Insulator 11KV", 52.24, "NOS"),
            ("508040741", "LT Guy Insulator", 21.11, "NOS"), ("503050711", "G.I. Stay Wire 7/3..15MM 10 SWG(HT)", 142310.93, "MT"),
            ("503050611", "GI STAY WIRE 7/12 SWG", 145404.60, "MT"), ("503010711", "G.I. 8 SWG Wire (4mm)", 137360.98, "MT"),
            ("503010811", "G.I. 6 SWG Wire (5mm)", 136865.98, "MT"), ("910010241", "Caution Board-11KVA", 160.18, "NOS"),
            ("195021741", "UH-LT BKT 4 WAY", 500.00, "NOS"), ("597011541", "UH-CLAMP FOR 8 MTR PCC POLE", 150.00, "NOS"),
            ("597011741", "UH-Diron Clump", 40.00, "NOS"), ("304010532", "T.P.G.O. Isolator (200Amps) 11KV", 10384.98, "SET"),
            ("309010841", "Lightning Arrestor 12 KV", 524.23, "NOS"), ("912011441", "G.I. Turn Buckle", 238.70, "NOS"),
            ("407010641", "LT Distribution KIOSK FOR 25 KVA DTR", 8878.41, "NOS"), ("501017821", "PVC Cable 4 Core 25SQMM", 229429.95, "KM"),
            ("504060941", "LT Distribution Box along with steel Strap & Buckle for 3ph connection in ABC system", 1489.9, "NOS"),
            ("501017421", "CABLE (PVC 1.1 KV GRADE) 4Core X10 sq mm", 125852.36, "KM"), ("501017721", "CABLE (PVC 1.1 KV GRADE) 4CX16 sq mm", 119154.63, "KM"),
            ("501017821", "CABLE (PVC 1.1 KV GRADE) 4CX25 sq mm", 229429.95, "KM")
        ]
        labor = [
            ("LAB-01", "Erection of . 8mtr  PCC Pole ( LT)", 1501.00, "NOS"), ("LAB-02", "Erection of . 8mtr  PCC Pole (HT)", 1680.00, "NOS"),
            ("LAB-03", "Erection of . 9mtr  PCC Pole (HT)", 2620.00, "NOS"), ("LAB-04", "Erection of . 9mtr  PCC Pole (HT) Without Painted", 2620.00, "NOS"),
            ("LAB-05", "Erection of S/S D.P. Structure  (8 mtr without Painted)", 9875.00, "NOS"), ("LAB-06", "Sub-Stationn Str with 9 Mtr PCC pole DP", 13169.00, "NOS"),
            ("LAB-07", "Sub-Stationn Str with 9 Mtr PCC pole DP Without Painted", 13169.00, "NOS"),
            ("LAB-08", "Erection of 8 mtr D.P structure (HT)", 5654.00, "NOS"), ("LAB-09", "Erection of 9 MTR Long PCC pole D/P for HTOH line", 9438.00, "NOS"), 
            ("LAB-10", "Erection of 25 KVA Transformer", 1925.00, "NOS"),
            ("LAB-11", "Stringing & Sagging with 50 sq.mm A.C.S.R. 3 Wire", 8289.00, "KM"), ("LAB-12", "Strining& saging with ACSR 50sqmm 4wire", 9715.00, "KM"),
            ("LAB-13", "Stringing & Sagging of LT AB Cable", 46000.00, "KM"), ("LAB-14", "H.T. Stay Set Complete Labor", 641.00, "SET"),
            ("LAB-15", "LT Stay set complete", 555.00, "SET"), ("LAB-16", "Earthing Complete", 313.00, "NOS"),
            ("LAB-17", "Fabrication & Fixing  of Cattle Guard Bracket (SP)", 237.00, "NOS"), ("LAB-18", "Fabrication & Fixing  of Cattle Guard Bracket (DP)", 369.00, "NOS"),
            ("LAB-19", "Extension of 8 mtr PCC Pole (Without Painted)HT", 1506.00, "NOS"), ("LAB-20", "Fixing Cross lacing", 15.00, "NOS"), 
            ("LAB-21", "Lead Wire above above 60 Mtrs (2 Wire)", 506.00, "NOS"), ("LAB-22", "Fixing of Caution Board", 24.00, "NOS"), 
            ("LAB-23", "Fixing of LT Bracket(Without Painted)", 596.00, "NOS"), ("LAB-24", "Pole GIS survey", 31.00, "NOS"),
            ("LAB-25", "Fixing of 11 KV Pin Insulator", 63.00, "NOS"), ("LAB-26", "Fixing of 11 KV Disc Insulator", 65.00, "NOS"), 
            ("LAB-27", "Fixing of LT Shackle Insulator (with N/B)", 52.00, "NOS"), ("LAB-28", "Fixing of LT spacer", 56.00, "NOS"),
            ("LAB-29", "Fixing of  11 KV TGPO Isolator on S/Stn Structure", 1193.00, "SET"), ("LAB-30", "Fixing of neutral earthing of DTR WITH G", 3816.00, "NOS"),
            ("LAB-31", "Fixing of 11 KV Lightning Arrestor", 339.00, "SET"), ("LAB-32", "FIXING OF LT Distribution KIOSK FOR 25 KVA DTR", 2155.00, "NOS"),
            ("LAB-33", "Erection of Anchoring/Suspension Clamp", 154.00, "NOS"), ("LAB-34", "Survey for H.T.O.H Line", 2761.00, "KM"), ("LAB-35", "Survey for L.T.O.H Line", 1714.00, "KM"),
            ("LAB-36", "Fixing of Solid Tee-off Bracket on S.P", 1495.00, "NOS"), ("LAB-37", "Fixing of Solid Tee-off Bracket on D.P", 1483.00, "NOS"),
            ("LAB-38", "DTR Code Painting", 65.00, "NOS"), 
            ("LAB-39", "Fixing of 3ph Service Connection with cable", 570.00, "NOS"), 
            ("LAB-40", "Fixing of 1ph Service Connection with cable", 270.00, "NOS"),
            ("LAB-41", "Fixing of 3ph Service Connection", 6117.00, "NOS"), 
            ("LAB-42", "Fixing of 1ph Service Connection", 1578.00, "NOS"),
            ("LAB-43", "Erection of distribution box", 507.00, "NOS"), ("LAB-44", "Laying & Dressing of 1.1 KV PVC/XLPE 2x10,4x10/16, 3.5/4x25 Sqmm Cable", 15000.00, "KM")
        ]
        cursor.executemany('INSERT INTO materials VALUES (?,?,?,?)', materials)
        cursor.executemany('INSERT INTO labor VALUES (?,?,?,?)', labor)
    
    conn.commit()
    conn.close()
