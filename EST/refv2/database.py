"""
database.py
===========
Database setup for ERP Estimate Generator v5.0.

DATA SOURCES (all material rates are inclusive of GST):
--------------------------------------------------------
1. Material codes & rates — PRIMARY SOURCE:
   O/O No. CED/36 dated 20-07-2023, Chief Engineer (Distribution), WBSEDCL
   "Central Purchase Item for Estimation Purpose Only, FY 2023-2024"

2. Material codes & rates — SUPPLEMENTARY (items not in 2023-24 list):
   Material Cost Data FY 2021-22, WBSEDCL (COST_DATA_ALL_IN_ONE.pdf)

3. Labour rates:
   O/O No. CED/13 dt. 15.05.2018 — Erection Rate for New Construction Works
   O/O No. CED/15 dt. 15.05.2018 — Erection Rate for HT & LT AB Cables
   O/O No. CED/UG Cable Rate Contract — Underground Cable Rates
   As adopted in ESTIMATE_FORMAT_2023.xlsx (Durgapur Division)

ITEMS NEEDING FIELD VERIFICATION:
-----------------------------------
- STP 9.5M rate: CED/36 scan reads 116598.41 — likely OCR error for 16598.41.
  Update via DB Manager once verified.
- DTR 25KVA rate: CED/36 shows same code as 63KVA (both 0301018141/0301018241).
  Used separate codes from 2021-22 data for 25KVA.
- ABC cable rates had lakh-notation artifacts in scan — cleaned versions used.

ITEMS WITHOUT OFFICIAL WBSEDCL CODE:
--------------------------------------
- UH readymade materials use "LOCAL-UH0x" prefix.
  Replace with official codes when available.
"""

import sqlite3

DB_PATH = "erp_master.db"


# fmt: off
_SEED_MATERIALS = [

    # ══ POLE SECTION ══════════════════════════════════════════════════════════
    # CED/36 FY2023-24
    ("0110030141", "P C C POLE:8 Mtrs.Long",                          5363.44,   "NOS"),
    ("0110030241", "P C C POLE:9 Mtrs.Long",                         10198.28,   "NOS"),
    ("0110010341", "STEEL TUBULAR POLE 9 M LONG (WITH CAP)",          11550.45,   "NOS"),
    ("0110011541", "STEEL TUBULAR POLE 9.5M LONG (WITH CAP)",         16598.41,   "NOS"),  # NOTE: verify rate
    ("0110010741", "STEEL TUBULAR POLE 11 M LONG (WITH CAP)",         17887.87,   "NOS"),
    ("0110020711", "RAIL POLE (11-13 M LONG) 52 KG/MT",              93806.05,   "MT"),
    ("0110051111", "WIDE FLANGE BEAM 11M LONG WBP 160X160X30.44 KG/M", 67112.64, "MT"),
    ("0110051211", "WIDE FLANGE BEAM 13M LONG WBP 160X160X30.44 KG/M", 65952.78, "MT"),

    # ══ STEEL SECTION ═════════════════════════════════════════════════════════
    # CED/36 FY2023-24 / ESTIMATE_FORMAT_2023
    ("0102010911", "M.S Channel 100X50 mm",                          109813.95,   "MT"),
    ("0102010611", "M.S Channel 75X40 mm",                           110043.09,   "MT"),
    ("0101011311", "M.S Angle 65X65X6mm",                            108667.24,   "MT"),
    ("0101011011", "M.S Angle 50X50X6mm",                            109603.22,   "MT"),
    ("0103011211", "M.S Flat 50X6 mm",                               117623.30,   "MT"),
    ("0103011511", "M.S Flat 65X6 mm",                               117493.74,   "MT"),
    ("0103011611", "M.S Flat 65X8 mm",                               114149.39,   "MT"),
    ("0103011911", "M.S Flat 75X8 mm",                               114255.68,   "MT"),
    ("0103012311", "M.S Flat 75X12 mm",                              114336.31,   "MT"),

    # ══ STAY SETS ═════════════════════════════════════════════════════════════
    # CED/36 FY2023-24
    ("0504130432", "G.I. Stay Set HT (1830X20MM) WRKG LD-7900KG",       795.83,  "SET"),
    ("0504130332", "G.I. Stay Set LT (1680X16MM) WRKG LD-5100KG",       462.17,  "SET"),

    # ══ EARTHING ══════════════════════════════════════════════════════════════
    ("0504110541", "G.I. Earth Spike 1833X20MM",                         367.98,  "NOS"),
    ("0503010711", "G.I. Wire 4 MM (8 SWG)",                         137360.98,   "MT"),
    ("0503010811", "G.I. Wire 5 MM (6 SWG)",                         136865.98,   "MT"),

    # ══ STAY WIRE ═════════════════════════════════════════════════════════════
    ("0503050911", "G.I. Stay Wire 7/4 MM (8 SWG)",                  141692.18,   "MT"),
    ("0503050711", "G.I. Stay Wire 7/3.15MM (10 SWG)",               142310.93,   "MT"),
    ("0503050611", "G.I. Stay Wire 7/2.5MM (12 SWG)",                145404.64,   "MT"),

    # ══ INSULATORS (11KV) ═════════════════════════════════════════════════════
    ("0508011141", "11 KV Polymer Composite Pin Insulator 5KN 320MM CD", 243.79,  "NOS"),
    ("0508030541", "11 KV Polymer Composite Disc Insulator 45KN",        183.15,  "NOS"),
    ("0508020341", "11 KV Post Insulator",                               289.57,  "NOS"),
    ("0508040841", "Porcelain Guy Insulator HT",                          52.24,  "NOS"),
    ("0508040741", "Porcelain Guy Insulator LT",                          18.37,  "NOS"),

    # ══ HARDWARE FITTINGS ═════════════════════════════════════════════════════
    ("0504010132", "Composite Hardware Fittings for ACSR Weasel/Rabbit (30/50SQMM)", 327.83, "SET"),
    ("0504010232", "Composite Hardware Fittings for ACSR Dog (100SQMM)", 518.96,  "SET"),

    # ══ LIGHTNING ARRESTORS ════════════════════════════════════════════════════
    ("0309010541", "Lightning Arrestor 42KV 10KA Porcelain Gapless Type 33KV", 7628.27, "NOS"),
    ("0309010841", "Lightning Arrestor 12KV 5KA Porcelain Gapless Type 11KV",   524.23,  "NOS"),

    # ══ 11KV ISOLATORS ════════════════════════════════════════════════════════
    ("0304010632", "T.P.G.O. Isolator 11KV 400 AMP",                  19138.97,  "SET"),
    ("0304010532", "T.P.G.O. Isolator 11KV 200 AMP",                  10384.98,  "SET"),

    # ══ ACSR CONDUCTOR ════════════════════════════════════════════════════════
    # CED/36 FY2023-24
    ("0502010621", "ACSR Conductor 30SQMM (Weasel)",                  38139.33,   "KM"),
    ("0502010921", "ACSR Conductor 50SQMM (Rabbit)",                  62290.12,   "KM"),
    ("0502011221", "ACSR Conductor 100SQMM (Dog)",                   122653.45,   "KM"),

    # ══ LT ABC CABLE (1.1KV) ══════════════════════════════════════════════════
    # CED/36 FY2023-24 Sl.73-74 (scan artifacts cleaned)
    ("0501030321", "LT AB CABLE 1.1KV 3CX50+1CX35SQMM",             160930.91,   "KM"),  # from 2021-22
    ("0501030421", "LT AB CABLE 1.1KV 3CX50+1CX16+1CX35SQMM",       237394.49,   "KM"),
    ("0501030521", "LT AB CABLE 1.1KV 3CX70+1CX16+1CX50SQMM",       315558.99,   "KM"),

    # ══ HT ABC CABLE (11KV) ═══════════════════════════════════════════════════
    # CED/36 FY2023-24 Sl.75 (scan artifact cleaned: "/ 8,79,877.46" → 879877.46)
    ("0501031121", "HT AB CABLE 11KV 3CX95+1CX70SQMM",              879877.46,   "KM"),

    # ══ PVC CABLE (1.1KV) ═════════════════════════════════════════════════════
    # CED/36 FY2023-24 Sl.52-58
    ("0501017421", "CABLE (PVC 1.1KV GRADE) 4CORE X10SQMM",         125852.36,   "KM"),
    ("0501017721", "CABLE (PVC 1.1KV GRADE) 4CX16SQMM",             119154.63,   "KM"),
    ("0501017821", "CABLE (PVC 1.1KV GRADE) 4CX25SQMM",             229429.95,   "KM"),
    ("0501017921", "CABLE (PVC 1.1KV GRADE) 4CX50SQMM",             248238.29,   "KM"),
    ("0501018121", "CABLE (PVC 1.1KV GRADE) 4CX120SQMM",            481307.89,   "KM"),
    ("0501018221", "CABLE (PVC 1.1KV GRADE) 4CX185SQMM",            781231.73,   "KM"),
    ("0501018321", "CABLE (PVC 1.1KV GRADE) 4CX300SQMM",           1277593.58,   "KM"),

    # ══ DISTRIBUTION TRANSFORMERS ══════════════════════════════════════════════
    # CED/36 FY2023-24 Sl.79-87 & 2021-22 data
    ("0301010541", "DTR 10KVA 11/0.433KV",                           33410.20,   "NOS"),  # 2021-22
    ("0301011041", "DTR 16KVA 11/0.433KV",                           89547.19,   "NOS"),  # CED/36
    ("0301018141", "DTR 25KVA 11/0.433KV",                          103528.11,   "NOS"),  # 2021-22
    ("0301018241", "DTR 63KVA 11/0.433KV",                          107589.53,   "NOS"),  # CED/36
    ("0301018341", "DTR 100KVA 11/0.433KV",                         144370.09,   "NOS"),  # 2021-22
    ("0301018741", "DTR 160KVA 11/0.433KV",                         205888.02,   "NOS"),  # 2021-22
    ("0301019041", "DTR 315KVA 11/0.433KV Indoor Type",             987447.23,   "NOS"),  # Nag_Apt
    ("0301019141", "DTR 315KVA 11/0.433KV Outdoor Type",            985286.54,   "NOS"),  # Nag_Apt
    ("0301019341", "DTR 630KVA 11/0.415KV Outdoor Oil Cooled",     1843842.08,   "NOS"),  # Nag_Apt

    # ══ LT DISTRIBUTION KIOSKS ════════════════════════════════════════════════
    # ESTIMATE_FORMAT_2023
    ("0407010641", "LT Distribution KIOSK For 25KVA DTR",             8878.41,   "NOS"),
    ("0407010741", "LT Distribution KIOSK For 63KVA DTR",             9441.26,   "NOS"),
    ("0407010541", "LT Distribution KIOSK For 100KVA DTR",           10456.61,   "NOS"),

    # ══ MISCELLANEOUS ═════════════════════════════════════════════════════════
    ("0504070441", "LT Spacer 3 Phase 4 Wire",                           60.11,  "NOS"),
    ("0504070341", "LT Spacer 1 PHASE 2 WIRE",                           35.51,  "NOS"),
    ("0912011441", "G.I. Turn Buckle 18x5/8\"",                         182.36,  "NOS"),
    ("0910010241", "Caution Board 11KV",                                 143.95,  "NOS"),
    ("0504060941", "LT Distribution Box 3Ph with Steel Strap & Buckle ABC", 1632.58, "NOS"),
    ("0505030641", "Suspension Clamp with Bracket 35SQMM Messenger",    352.89,  "NOS"),
    ("0505034141", "Dead End Clamp LT ABC (3X70+1X16+1X50SQMM)",        307.84,  "NOS"),
    ("0505030841", "Eye Hook for Anchor/Suspension Clamp",               100.67,  "NOS"),
    ("0504027141", "IPC for ABC to ABC TEE Joint",                       149.17,  "NOS"),

    # ══ UH (READYMADE) MATERIALS — local codes, update when official available
    ("LOCAL-UH01", "UH-LT BKT 4 WAY",                                   500.00,  "NOS"),
    ("LOCAL-UH02", "UH-CLAMP FOR 8 MTR PCC POLE",                       150.00,  "NOS"),
    ("LOCAL-UH03", "UH-Diron Clump",                                      40.00,  "NOS"),
    ("LOCAL-UH04", "Porcelain Shackle Insulator 3x3.5\" (Shakle Insulator)", 19.41, "NOS"),
]

_SEED_LABOUR = [

    # ══ SURVEY ════════════════════════════════════════════════════════════════
    # CED/13 Sl.1-2
    ("LAB-01", "Survey for H.T.O.H Line",                             2761.00,  "KM"),
    ("LAB-02", "Survey for L.T.O.H Line",                             1714.00,  "KM"),

    # ══ SINGLE POLE ERECTION — LT (no fittings) ═══════════════════════════════
    # CED/13 Sl.3
    ("LAB-03", "Erection of 8MTR PCC Pole (LT) Without Painted",      1501.00, "NOS"),
    ("LAB-04", "Erection of 9MTR PCC Pole (LT) Without Painted",      2281.00, "NOS"),

    # ══ SINGLE POLE ERECTION — HT (with V-bracket, top adaptor) ═══════════════
    # CED/13 Sl.4
    ("LAB-05", "Erection of 8MTR PCC Pole (HT) Without Painted",      1766.00, "NOS"),
    ("LAB-06", "Erection of 9MTR PCC Pole (HT) Without Painted",      2620.00, "NOS"),
    ("LAB-07", "Erection of 9MTR STP Pole Single Pole HT",            2575.92, "NOS"),
    ("LAB-08", "Erection of 11MTR STP Pole Single Pole HT",           3127.30, "NOS"),

    # ══ DOUBLE POLE STRUCTURE (DP) ════════════════════════════════════════════
    # CED/13 Sl.5
    ("LAB-09", "Erection of DP Structure 8MTR PCC Pole HT",           6170.00, "NOS"),
    ("LAB-10", "Erection of DP Structure 9MTR PCC Pole HT",           9438.00, "NOS"),
    ("LAB-11", "Erection of DP Structure 9MTR STP Pole HT",           7285.84, "NOS"),
    ("LAB-12", "Erection of DP Structure 11MTR STP Pole HT",          7455.60, "NOS"),

    # ══ TRIPLE POLE STRUCTURE (TP) ════════════════════════════════════════════
    # CED/13 Sl.6 & ESTIMATE_FORMAT_2023
    ("LAB-13", "Erection of TP Structure 8MTR PCC Pole HT",          12044.00, "NOS"),
    ("LAB-14", "Erection of TP Structure 9MTR PCC Pole HT",          16274.00, "NOS"),
    ("LAB-15", "Erection of TP Structure 9MTR STP Pole HT",          19341.76, "NOS"),
    ("LAB-16", "Erection of TP Structure 11MTR STP Pole HT",         19595.90, "NOS"),

    # ══ FOUR POLE STRUCTURE (4P) ══════════════════════════════════════════════
    # CED/13 Sl.7 & ESTIMATE_FORMAT_2023
    ("LAB-17", "Erection of 4P Structure 8MTR PCC Pole HT",          15312.00, "NOS"),
    ("LAB-18", "Erection of 4P Structure 9MTR PCC Pole HT",          27829.68, "NOS"),

    # ══ SUB-STATION STRUCTURE (DTR DP) ════════════════════════════════════════
    # CED/13 Sl.9 & ESTIMATE_FORMAT_2023
    ("LAB-19", "Erection of S/S DP Structure 8MTR PCC Pole Without Painted",  9875.00, "NOS"),
    ("LAB-20", "Erection of S/S DP Structure 9MTR PCC Pole Without Painted", 13169.00, "NOS"),
    ("LAB-21", "Erection of S/S 4P Structure 8MTR PCC Pole",         19872.00, "NOS"),

    # ══ POLE EXTENSION ════════════════════════════════════════════════════════
    # CED/13 Sl.8
    ("LAB-22", "Extension of PCC Pole upto 3MTR Without Painted HT",  1506.00, "NOS"),
    ("LAB-23", "Extension of Rail Pole upto 3MTR",                    1862.95, "NOS"),
    ("LAB-73", "Extension of PCC Pole upto 3MTR Without Painted LT",  1506.00, "NOS"),

    # ══ TRANSFORMER ERECTION ══════════════════════════════════════════════════
    # CED/13 Sl.11 & ESTIMATE_FORMAT_2023
    ("LAB-24", "Erection of 10KVA and 16KVA DTR",                    1885.00, "NOS"),
    ("LAB-25", "Erection of 25KVA DTR",                               1925.00, "NOS"),
    ("LAB-26", "Erection of 63KVA DTR",                               2711.00, "NOS"),
    ("LAB-27", "Erection of 100KVA DTR",                              3214.00, "NOS"),
    ("LAB-28", "Erection of 160KVA DTR",                              3406.00, "NOS"),
    ("LAB-29", "Erection of 315KVA and above DTR",                    7248.00, "NOS"),

    # ══ ACSR STRINGING & SAGGING ══════════════════════════════════════════════
    # CED/13 Sl.10 — ACSR 50SQMM (Rabbit)
    ("LAB-30", "Stringing & Sagging ACSR 50SQMM 3 Wire",             8289.00,  "KM"),
    ("LAB-31", "Stringing & Sagging ACSR 50SQMM 4 Wire",             9715.00,  "KM"),
    ("LAB-32", "Stringing & Sagging ACSR 50SQMM 2 Wire",             6184.00,  "KM"),
    # ACSR 30SQMM (Weasel) — CED/13 Sl.10(c)
    ("LAB-33", "Stringing & Sagging ACSR 30SQMM 3 Wire",             7899.00,  "KM"),
    ("LAB-34", "Stringing & Sagging ACSR 30SQMM 4 Wire",             8821.00,  "KM"),
    ("LAB-35", "Stringing & Sagging ACSR 30SQMM 2 Wire",             5322.00,  "KM"),

    # ══ LT ABC CABLE ERECTION ═════════════════════════════════════════════════
    # CED/15 Sl.1 — per metre rate × 1000 = per KM rate
    ("LAB-36", "Stringing & Sagging LT AB Cable 3CX70+1CX16+1CX50",  50000.00, "KM"),
    ("LAB-37", "Stringing & Sagging LT AB Cable 3CX50+1CX16+1CX35",  46000.00, "KM"),
    ("LAB-38", "Stringing & Sagging LT AB Cable 3CX50+1CX35",        29000.00, "KM"),

    # ══ HT ABC CABLE ERECTION (11KV) ══════════════════════════════════════════
    # CED/15 Sl.13 — 3CX95+1CX70 @ Rs.48/m → Rs.48000/KM
    ("LAB-39", "Stringing & Sagging HT AB Cable 11KV 3CX95+1CX70",   48000.00, "KM"),

    # ══ STAY SETS ═════════════════════════════════════════════════════════════
    # CED/13 Sl.15
    ("LAB-40", "H.T. Stay Set Complete Labour",                         641.00, "SET"),
    ("LAB-41", "LT Stay Set Complete Labour",                           555.00, "SET"),

    # ══ EARTHING ══════════════════════════════════════════════════════════════
    # CED/13 Sl.16
    ("LAB-42", "Earthing Complete",                                     313.00, "NOS"),

    # ══ CATTLE GUARD ══════════════════════════════════════════════════════════
    # CED/13 Sl.12A
    ("LAB-43", "Fabrication & Fixing of CG Bracket Single Pole",        237.00, "NOS"),
    ("LAB-44", "Fabrication & Fixing of CG Bracket Double Pole",        369.00, "NOS"),

    # ══ INSULATORS ════════════════════════════════════════════════════════════
    # CED/13 Sl.13
    ("LAB-45", "Fixing of 11KV Pin Insulator",                           63.00, "NOS"),
    ("LAB-46", "Fixing of 11KV Disc Insulator with Strain Hardware",     65.00, "NOS"),
    ("LAB-47", "Fixing of LT Shackle Insulator with N/B",                52.00, "NOS"),
    ("LAB-48", "Fixing of LT Spacer",                                    56.00, "NOS"),
    ("LAB-72", "Fixing of LT Spacer 1ph Unit",                           37.00, "NOS"),

    # ══ SUB-STATION FITTINGS ══════════════════════════════════════════════════
    # CED/13 Sl.22, 25, 26, 29
    ("LAB-49", "Fixing of 11KV TPGO Isolator on S/Stn Structure",     1193.00, "SET"),
    ("LAB-50", "Fixing of 11KV Lightning Arrestor on Structure",         339.00, "SET"),
    ("LAB-51", "Fixing of LT Bracket Without Painted",                   596.00, "NOS"),
    ("LAB-52", "Fixing of Solid Tee-off Bracket on Single Pole",       1495.00, "NOS"),
    ("LAB-53", "Fixing of Solid Tee-off Bracket on Double Pole",       1483.00, "NOS"),

    # ══ KIOSK / DTR MISC ══════════════════════════════════════════════════════
    ("LAB-54", "Fixing of LT Distribution KIOSK Single Switch",        2155.00, "NOS"),
    ("LAB-55", "Fixing of Neutral Earthing of DTR with G",             3816.00, "NOS"),
    ("LAB-56", "DTR Code Painting",                                       65.00, "NOS"),

    # ══ MISCELLANEOUS LINE WORKS ══════════════════════════════════════════════
    # CED/13 Sl.12B, 12C, 14
    ("LAB-57", "Lead Wire above 60 Mtrs (2 Wire)",                      506.00, "NOS"),
    ("LAB-58", "Fixing Cross Lacing Wire",                                15.00, "NOS"),
    ("LAB-59", "Pole GIS Survey",                                         31.00, "NOS"),
    ("LAB-60", "Fixing of Caution Board",                                 24.00, "NOS"),

    # ══ ABC CLAMP ERECTION ════════════════════════════════════════════════════
    # CED/15 Sl.2-3, 7
    ("LAB-61", "Erection of Anchor/Dead End Clamp LT ABC",              154.00, "NOS"),
    ("LAB-62", "Erection of Suspension Clamp LT ABC",                   154.00, "NOS"),
    ("LAB-63", "Erection of Distribution Box LT ABC",                   507.00, "NOS"),
    ("LAB-71", "Fixing of IPC Connector LT ABC",                         75.00, "NOS"),

    # ══ PVC CABLE LAYING ══════════════════════════════════════════════════════
    # CED/UG Cable Rate Contract Sl.10(e-g) — per metre × 1000
    ("LAB-64", "Laying & Dressing 1.1KV PVC/XLPE 4x10/16/25 SQMM Cable", 15000.00, "KM"),
    ("LAB-65", "Laying & Dressing 1.1KV PVC/XLPE 4x35/50/70 SQMM Cable", 24000.00, "KM"),
    ("LAB-66", "Laying & Dressing 1.1KV PVC/XLPE 4x95/120 SQMM Cable",   31000.00, "KM"),

    # ══ CONSUMER SERVICE CONNECTIONS ══════════════════════════════════════════
    # CED/13 O&M Sl.27-28 & new construction rates
    ("LAB-67", "Fixing of 3Ph Service Connection (without cable)",     6117.00, "NOS"),
    ("LAB-68", "Fixing of 1Ph Service Connection (without cable)",     1578.00, "NOS"),
    ("LAB-69", "Fixing of 3Ph Service Connection with Cable",           570.00, "NOS"),
    ("LAB-70", "Fixing of 1Ph Service Connection with Cable",           270.00, "NOS"),
]
# fmt: on


# Rows to add to existing v4 databases (INSERT OR IGNORE)
_NEW_MATERIALS = [
    r for r in _SEED_MATERIALS
    if r[0].startswith(("0110010", "0110011", "0110020", "0110051",
                         "0101011011", "0103011611", "0103011911", "0103012311",
                         "0502010621", "0502011221",
                         "0501030321", "0501030421", "0501031121",
                         "0501017921", "0501018121", "0501018221", "0501018321",
                         "0301010541", "0301011041", "0301018341", "0301018741",
                         "0301019041", "0301019141", "0301019341",
                         "0407010741", "0407010541",
                         "0504070341",
                         "LOCAL-"))
]

_NEW_LABOUR = [
    r for r in _SEED_LABOUR
    if r[0] in {
        "LAB-04", "LAB-07", "LAB-08",
        "LAB-09", "LAB-10", "LAB-11", "LAB-12",
        "LAB-13", "LAB-14", "LAB-15", "LAB-16",
        "LAB-17", "LAB-18",
        "LAB-19", "LAB-20", "LAB-21",
        "LAB-23", "LAB-24", "LAB-26", "LAB-27", "LAB-28", "LAB-29",
        "LAB-32", "LAB-33", "LAB-34", "LAB-35",
        "LAB-36", "LAB-37", "LAB-38", "LAB-39",
        "LAB-61", "LAB-62", "LAB-63", "LAB-71", "LAB-72", "LAB-73",
        "LAB-64", "LAB-65", "LAB-66",
        "LAB-67", "LAB-68", "LAB-69", "LAB-70",
    }
]


def setup_database():
    """Called on every app launch."""
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            item_code  TEXT,
            item_name  TEXT PRIMARY KEY,
            rate       REAL,
            unit       TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS labor (
            labor_code TEXT PRIMARY KEY,
            task_name  TEXT,
            rate       REAL,
            unit       TEXT
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM materials")
    is_empty = cursor.fetchone()[0] == 0

    if is_empty:
        cursor.executemany("INSERT INTO materials VALUES (?,?,?,?)", _SEED_MATERIALS)
        cursor.executemany("INSERT INTO labor VALUES (?,?,?,?)", _SEED_LABOUR)
    else:
        cursor.executemany("INSERT OR IGNORE INTO materials VALUES (?,?,?,?)", _NEW_MATERIALS)
        cursor.executemany("INSERT OR IGNORE INTO labor VALUES (?,?,?,?)", _NEW_LABOUR)

    conn.commit()
    conn.close()


def get_material_rate(item_name: str) -> float:
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT rate FROM materials WHERE item_name=?", (item_name,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0


def get_labour_rate(task_name: str) -> float:
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT rate FROM labor WHERE task_name=?", (task_name,))
    row = cursor.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0
