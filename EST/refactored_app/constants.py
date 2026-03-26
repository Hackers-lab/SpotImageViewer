"""
This file stores constant values and shared configuration dictionaries
for the ERP Estimate Generator application.
"""

# Data for the Rule Builder in RulesetManagerDialog
PROPERTY_DATA = {
    "SmartPole": {
        'pole_type': ['LT', 'HT', 'DTR'],
        'height': [8, 9],
        'dtr_size': ["None", "16 KVA", "25KVA", "63KVA", "100KVA", "160KVA"],
        'is_existing': [True, False],
        'has_extension': [True, False],
        'earth_count': 'int',
        'stay_count': 'int'
    },
    "SmartSpan": {
        'conductor': ["ACSR", "AB Cable", "PVC Cable", "Service Drop"],
        'is_service_drop': [True, False],
        'has_cg': [True, False],
        'phase': ["1 Phase", "3 Phase"],
        'aug_type': ["New", "Replace 2W->4W", "Add-on 2W"],
        'length': 'int',
        'wire_count': 'int'
    },
    "SmartHome": {}
}

# Variables available for use in rule formulas
FORMULA_VARS = {
    "SmartPole": ['height', 'earth_count', 'stay_count'],
    "SmartSpan": ['length', 'wire_count'],
    "SmartHome": []
}

# Definitions for the drawing tools in the main toolbar
TOOLS = {
    "SELECT": "🖱 Select / Edit",
    "ADD_LT": "🔵 LT Pole",
    "ADD_HT": "🔴 HT Pole",
    "ADD_DTR": "🟩 DP/DTR",
    "ADD_EXISTING": "⚪ Ex Pole",
    "ADD_HOME": "🏠 Home",
    "ADD_SPAN": "📏 Span"
}
