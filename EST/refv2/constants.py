"""
constants.py
============
Shared configuration, lookup tables, and constant definitions for the
ERP Estimate Generator v5.0.

Consumers of this module
------------------------
app.py          — TOOLS, PROJECT_TYPES, SUPERVISION_RATES
ui_dialogs.py   — PROPERTY_DATA, FORMULA_VARS, PROJECT_TYPES,
                  SUPERVISION_RATES, HEIGHT_OPTIONS, CONDUCTOR_SIZES,
                  SERVICE_CABLE_SIZES, SIM_DEFAULTS
rule_engine.py  — (no direct import; context keys documented here)
canvas_objects.py — HEIGHT_OPTIONS, CONDUCTOR_SIZES (optional reference)
"""

# ─────────────────────────────────────────────────────────────────────────────
#  DRAWING TOOLS  (toolbar button order matters)
# ─────────────────────────────────────────────────────────────────────────────
TOOLS = {
    "SELECT":        "🖱 Select",
    "ADD_LT":        "🔵 LT Pole",
    "ADD_HT":        "🔴 HT Pole",
    "ADD_STRUCTURE": "🟩 Structure",
    "ADD_EXISTING":  "⚪ Ex. Pole",
    "ADD_CONSUMER":  "🏠 Consumer",
    "ADD_SPAN":      "📏 Span",
}

# ─────────────────────────────────────────────────────────────────────────────
#  PROJECT TYPES & SUPERVISION RATES
# ─────────────────────────────────────────────────────────────────────────────

# Display labels shown in the Project Setup Wizard dropdown
PROJECT_TYPES = [
    "NSC",
    "FDS / TURNKEY",
    "MAINTENANCE",
    "SHIFTING",
    "AUGMENTATION",
]

# Supervision charge rate keyed by project type string
# NSC = 10%, all others = 15%
SUPERVISION_RATES = {
    "NSC":              0.10,
    "FDS / TURNKEY":    0.15,
    "MAINTENANCE":      0.15,
    "SHIFTING":         0.15,
    "AUGMENTATION":     0.15,
}

# ─────────────────────────────────────────────────────────────────────────────
#  POLE / STRUCTURE HEIGHT OPTIONS  (keyed by pole_type2)
# ─────────────────────────────────────────────────────────────────────────────
HEIGHT_OPTIONS = {
    "PCC":    ["8MTR", "9MTR"],
    "STP":    ["9MTR", "9.5MTR", "11MTR"],
    "H-BEAM": ["13MTR"],
}

# Default heights per pole voltage type when pole_type2 == PCC
DEFAULT_HEIGHT = {
    "LT": "8MTR",
    "HT": "9MTR",
}

# ─────────────────────────────────────────────────────────────────────────────
#  CONDUCTOR SIZE OPTIONS
# ─────────────────────────────────────────────────────────────────────────────
CONDUCTOR_SIZES = {
    # ACSR — same for LT and HT
    ("ACSR", "LT"):      ["30SQMM", "50SQMM"],
    ("ACSR", "HT"):      ["30SQMM", "50SQMM"],

    # LT Aerial Bunched Cable
    ("AB Cable", "LT"):  [
        "3CX50+1CX35",
        "3CX50+1CX16+1CX35",
        "3CX70+1CX16+1CX50",
    ],

    # HT Aerial Bunched Cable (11 kV)
    ("AB Cable", "HT"):  [
        "3CX50+1CX150",
        "3CX95+1CX70",
    ],

    # PVC underground / overhead cable — same range for LT and HT
    ("PVC Cable", "LT"): [
        "10 SQMM", "16 SQMM", "25 SQMM",
        "50 SQMM", "95 SQMM", "120 SQMM",
    ],
    ("PVC Cable", "HT"): [
        "10 SQMM", "16 SQMM", "25 SQMM",
        "50 SQMM", "95 SQMM", "120 SQMM",
    ],
}

# Service drop cable sizes per phase
SERVICE_CABLE_SIZES = {
    "1 Phase": ["10 SQMM", "16 SQMM"],
    "3 Phase": ["10 SQMM", "16 SQMM", "25 SQMM", "50 SQMM"],
}

# ─────────────────────────────────────────────────────────────────────────────
#  STRUCTURE EARTH COUNT DEFAULTS  (keyed by structure_type)
# ─────────────────────────────────────────────────────────────────────────────
STRUCTURE_EARTH_DEFAULTS = {
    "DP":  2,
    "TP":  3,
    "4P":  4,
    "DTR": 5,
}

# ─────────────────────────────────────────────────────────────────────────────
#  RULE BUILDER — PROPERTY_DATA
#  Defines what properties each canvas object exposes in the rule builder UI.
#  Value is either a list of allowed values (→ ComboBox) or 'int' (→ SpinBox).
# ─────────────────────────────────────────────────────────────────────────────
PROPERTY_DATA = {
    "SmartPole": {
        "pole_type":        ["LT", "HT"],
        "pole_type2":       ["PCC", "STP", "H-BEAM"],
        "height":           [8, 9],           # numeric metres for rule conditions
        "is_existing":      [True, False],
        "has_extension":    [True, False],
        "extension_height": "int",
        "earth_count":      "int",
        "stay_count":       "int",
        "has_cg":           [True, False],
    },
    "SmartStructure": {
        "structure_type":   ["DP", "TP", "4P", "DTR"],
        "pole_type2":       ["PCC", "STP", "H-BEAM"],
        "height":           [8, 9],
        "has_extension":    [True, False],
        "extension_height": "int",
        "earth_count":      "int",
        "stay_count":       "int",
        "dtr_size":         [
            "None", "10KVA", "16KVA", "25KVA",
            "63KVA", "100KVA", "160KVA"
        ],
    },
    "SmartSpan": {
        "conductor":        ["ACSR", "AB Cable", "PVC Cable", "Service Drop"],
        "conductor_size":   "text",           # free-text; too many combinations
        "is_service_drop":  [True, False],
        "is_existing_span": [True, False],
        "is_lt_span":       [True, False],
        "has_cg":           [True, False],
        "phase":            ["1 Phase", "3 Phase"],
        "aug_type":         ["New", "Replace 2W->4W", "Add-on 2W"],
        "consider_cable":   [True, False],
        "length":           "int",
        "wire_count":       "int",
    },
    "SmartConsumer": {
        "phase":            ["1 Phase", "3 Phase"],
        "cable_size":       [
            "10 SQMM", "16 SQMM", "25 SQMM", "50 SQMM"
        ],
        "agency_supply":    [True, False],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  RULE BUILDER — FORMULA_VARS
#  Numeric variables available inside qty formula strings.
# ─────────────────────────────────────────────────────────────────────────────
FORMULA_VARS = {
    "SmartPole": [
        "height",           # int metres  e.g. 8 or 9
        "extension_height", # float metres e.g. 3.0
        "earth_count",
        "stay_count",
    ],
    "SmartStructure": [
        "height",
        "extension_height",
        "earth_count",
        "stay_count",
    ],
    "SmartSpan": [
        "length",           # metres
        "wire_count",       # int
    ],
    "SmartConsumer": [],
}

# ─────────────────────────────────────────────────────────────────────────────
#  RULE BUILDER SIMULATOR — DEFAULT VALUES
#  Used by RulesetManagerDialog simulator panel to pre-populate widgets.
#  Format: prop_name → (widget_type, options_or_range, default)
#    widget_type: "combo" | "spin" | "dspin"
#    options_or_range: list of strings for combo; (min,max) tuple for spin
# ─────────────────────────────────────────────────────────────────────────────
SIM_DEFAULTS = {
    "SmartPole": {
        "pole_type":        ("combo", ["LT", "HT"],                     "LT"),
        "pole_type2":       ("combo", ["PCC", "STP", "H-BEAM"],         "PCC"),
        "is_existing":      ("combo", ["False", "True"],                 "False"),
        "height":           ("spin",  (8, 13),                           8),
        "has_extension":    ("combo", ["False", "True"],                 "False"),
        "extension_height": ("spin",  (1, 10),                           3),
        "earth_count":      ("spin",  (0, 10),                           1),
        "stay_count":       ("spin",  (0, 10),                           0),
        "has_cg":           ("combo", ["False", "True"],                 "False"),
        "ht_spans_count":   ("spin",  (0, 10),                           0),
        "use_uh":           ("combo", ["False", "True"],                 "False"),
        "project_type":     ("combo", PROJECT_TYPES,                     "NSC"),
    },
    "SmartStructure": {
        "structure_type":   ("combo", ["DP", "TP", "4P", "DTR"],        "DP"),
        "pole_type2":       ("combo", ["PCC", "STP", "H-BEAM"],         "PCC"),
        "height":           ("spin",  (8, 13),                           9),
        "has_extension":    ("combo", ["False", "True"],                 "False"),
        "extension_height": ("spin",  (1, 10),                           3),
        "earth_count":      ("spin",  (0, 20),                           2),
        "stay_count":       ("spin",  (0, 20),                           4),
        "dtr_size":         ("combo",
                             ["None","10KVA","16KVA","25KVA",
                              "63KVA","100KVA","160KVA"],                "None"),
        "use_uh":           ("combo", ["False", "True"],                 "False"),
        "project_type":     ("combo", PROJECT_TYPES,                     "NSC"),
    },
    "SmartSpan": {
        "conductor":        ("combo",
                             ["AB Cable", "ACSR", "PVC Cable",
                              "Service Drop"],                           "AB Cable"),
        "conductor_size":   ("combo",
                             ["50SQMM", "30SQMM",
                              "3CX50+1CX35", "3CX50+1CX16+1CX35",
                              "3CX70+1CX16+1CX50",
                              "3CX50+1CX150", "3CX95+1CX70",
                              "10 SQMM", "16 SQMM", "25 SQMM",
                              "50 SQMM", "95 SQMM", "120 SQMM"],        "50SQMM"),
        "is_existing_span": ("combo", ["False", "True"],                 "False"),
        "is_service_drop":  ("combo", ["False", "True"],                 "False"),
        "is_lt_span":       ("combo", ["True", "False"],                 "True"),
        "length":           ("spin",  (1, 1000),                         40),
        "wire_count":       ("combo", ["2", "3", "4"],                   "3"),
        "phase":            ("combo", ["1 Phase", "3 Phase"],            "3 Phase"),
        "has_cg":           ("combo", ["False", "True"],                 "False"),
        "aug_type":         ("combo",
                             ["New", "Replace 2W->4W", "Add-on 2W"],    "New"),
        "consider_cable":   ("combo", ["False", "True"],                 "False"),
        "use_uh":           ("combo", ["False", "True"],                 "False"),
        "project_type":     ("combo", PROJECT_TYPES,                     "NSC"),
    },
    "SmartConsumer": {
        "phase":            ("combo", ["1 Phase", "3 Phase"],            "3 Phase"),
        "cable_size":       ("combo",
                             ["10 SQMM", "16 SQMM",
                              "25 SQMM", "50 SQMM"],                    "10 SQMM"),
        "agency_supply":    ("combo", ["False", "True"],                 "False"),
        "project_type":     ("combo", PROJECT_TYPES,                     "NSC"),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  RULE BUILDER TREE DEFINITION
#  Hierarchy shown in the left panel of RulesetManagerDialog.
#  Format per entry: (display_label, obj_type, filter_dict, children)
# ─────────────────────────────────────────────────────────────────────────────
TREE_DEF = [
    ("SmartPole", "SmartPole", {}, [
        ("LT Pole",       "SmartPole", {"pole_type": "LT"}, [
            ("PCC 8m",  "SmartPole", {"pole_type": "LT", "height": 8,  "pole_type2": "PCC"}, []),
            ("PCC 9m",  "SmartPole", {"pole_type": "LT", "height": 9,  "pole_type2": "PCC"}, []),
            ("STP",     "SmartPole", {"pole_type": "LT", "pole_type2": "STP"},               []),
        ]),
        ("HT Pole",       "SmartPole", {"pole_type": "HT"}, [
            ("PCC 8m",  "SmartPole", {"pole_type": "HT", "height": 8,  "pole_type2": "PCC"}, []),
            ("PCC 9m",  "SmartPole", {"pole_type": "HT", "height": 9,  "pole_type2": "PCC"}, []),
            ("STP",     "SmartPole", {"pole_type": "HT", "pole_type2": "STP"},               []),
            ("H-BEAM",  "SmartPole", {"pole_type": "HT", "pole_type2": "H-BEAM"},            []),
        ]),
        ("Existing Pole", "SmartPole", {"is_existing": True}, []),
    ]),
    ("SmartStructure", "SmartStructure", {}, [
        ("DP Structure",  "SmartStructure", {"structure_type": "DP"},  []),
        ("TP Structure",  "SmartStructure", {"structure_type": "TP"},  []),
        ("4P Structure",  "SmartStructure", {"structure_type": "4P"},  []),
        ("DTR / Sub-Stn", "SmartStructure", {"structure_type": "DTR"}, [
            ("10 KVA",  "SmartStructure", {"structure_type": "DTR", "dtr_size": "10KVA"},  []),
            ("16 KVA",  "SmartStructure", {"structure_type": "DTR", "dtr_size": "16KVA"},  []),
            ("25 KVA",  "SmartStructure", {"structure_type": "DTR", "dtr_size": "25KVA"},  []),
            ("63 KVA",  "SmartStructure", {"structure_type": "DTR", "dtr_size": "63KVA"},  []),
            ("100 KVA", "SmartStructure", {"structure_type": "DTR", "dtr_size": "100KVA"}, []),
            ("160 KVA", "SmartStructure", {"structure_type": "DTR", "dtr_size": "160KVA"}, []),
        ]),
    ]),
    ("SmartSpan", "SmartSpan", {}, [
        ("AB Cable LT",   "SmartSpan", {"conductor": "AB Cable",  "is_lt_span": True},  [
            ("New",           "SmartSpan", {"conductor": "AB Cable", "aug_type": "New"},              []),
            ("Replace 2W→4W", "SmartSpan", {"conductor": "AB Cable", "aug_type": "Replace 2W->4W"},   []),
            ("Add-on 2W",     "SmartSpan", {"conductor": "AB Cable", "aug_type": "Add-on 2W"},        []),
        ]),
        ("AB Cable HT",   "SmartSpan", {"conductor": "AB Cable",  "is_lt_span": False}, []),
        ("ACSR",          "SmartSpan", {"conductor": "ACSR"},  [
            ("3 Wire", "SmartSpan", {"conductor": "ACSR", "wire_count": "3"}, []),
            ("4 Wire", "SmartSpan", {"conductor": "ACSR", "wire_count": "4"}, []),
        ]),
        ("PVC Cable",     "SmartSpan", {"conductor": "PVC Cable"}, [
            ("10 SQMM",  "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "10 SQMM"},  []),
            ("16 SQMM",  "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "16 SQMM"},  []),
            ("25 SQMM",  "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "25 SQMM"},  []),
            ("50 SQMM",  "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "50 SQMM"},  []),
            ("95 SQMM",  "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "95 SQMM"},  []),
            ("120 SQMM", "SmartSpan", {"conductor": "PVC Cable", "conductor_size": "120 SQMM"}, []),
        ]),
        ("Service Drop",  "SmartSpan", {"is_service_drop": True},  [
            ("1 Phase", "SmartSpan", {"is_service_drop": True, "phase": "1 Phase"}, []),
            ("3 Phase", "SmartSpan", {"is_service_drop": True, "phase": "3 Phase"}, []),
        ]),
    ]),
    ("SmartConsumer", "SmartConsumer", {}, [
        ("1 Phase", "SmartConsumer", {"phase": "1 Phase"}, []),
        ("3 Phase", "SmartConsumer", {"phase": "3 Phase"}, []),
    ]),
]

# ─────────────────────────────────────────────────────────────────────────────
#  RULE BUILDER — FILTER CHIPS
#  Context-aware checkbox filters shown above the card list per object type.
#  Format: (display_label, context_key, match_value)
# ─────────────────────────────────────────────────────────────────────────────
FILTER_CHIPS = {
    "SmartPole": [
        ("New Pole",      "is_existing",    False),
        ("Existing",      "is_existing",    True),
        ("Has Extension", "has_extension",  True),
        ("Has CG",        "has_cg",         True),
        ("With Earth",    "earth_count_gt", 0),
        ("With Stay",     "stay_count_gt",  0),
    ],
    "SmartStructure": [
        ("With DTR",      "dtr_size_ne",    "None"),
        ("Has Extension", "has_extension",  True),
        ("With Earth",    "earth_count_gt", 0),
        ("With Stay",     "stay_count_gt",  0),
    ],
    "SmartSpan": [
        ("New Span",      "is_existing_span", False),
        ("Existing Span", "is_existing_span", True),
        ("Service Drop",  "is_service_drop",  True),
        ("Has CG",        "has_cg",           True),
        ("New Work",      "aug_type",          "New"),
    ],
    "SmartConsumer": [
        ("Agency Supply", "agency_supply", True),
        ("WBSEDCL",       "agency_supply", False),
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
#  IRON BREAKUP — UNIT WEIGHTS  (kg per metre)
# ─────────────────────────────────────────────────────────────────────────────
IRON_UNIT_WEIGHTS = {
    "MS Channel 75x40":  7.14,
    "MS Angle 65x65x6":  6.50,
    "MS Angle 50x50x6":  5.00,
    "MS Flat 65x6":      3.50,
}
