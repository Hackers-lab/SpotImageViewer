import json
import os
import config

# Use the global BASE_DIR from config.py
CONFIG_FILE = os.path.join(config.BASE_DIR, "tariff_settings.json")
MIGRATION_MARKER_FILE = os.path.join(config.BASE_DIR, "tariff_migration_version.txt")

# Bump this string only when you want to force a one-time tariff reset in a new release.
TARIFF_MIGRATION_VERSION = "18.3"

# Verified 2025-26 Source of Truth for automatic pre-filling
DEFAULT_TARIFF = {
    "Domestic (Rural) - Rate A(DM-R)": {
        "fixed_charge": 30.0,
        "min_charge": 75.0, 
        "load_factor": 0.5,
        "slabs": [
            {"limit": 34, "rate": 5.00}, {"limit": 26, "rate": 6.24},
            {"limit": 40, "rate": 6.89}, {"limit": 100, "rate": 7.44},
            {"limit": 100, "rate": 7.61}, {"limit": None, "rate": 9.22}
        ],
        "ed_slabs": [{"limit": 300, "rate": 0.0}, {"limit": None, "rate": 0.10}]
    },
    "Domestic (Urban) - Rate A(DM-U)": {
        "fixed_charge": 30.0,
        "min_charge": 75.0,
        "load_factor": 0.5,
        "slabs": [
            {"limit": 34, "rate": 5.04}, {"limit": 26, "rate": 6.33},
            {"limit": 40, "rate": 7.12}, {"limit": 100, "rate": 7.52},
            {"limit": 100, "rate": 7.69}, {"limit": None, "rate": 9.22}
        ],
        "ed_slabs": [{"limit": 300, "rate": 0.0}, {"limit": None, "rate": 0.10}]
    },
    "Commercial - Rate A(CM)": {
        "fixed_charge": 60.0,
        "min_charge": 105.0, 
        "load_factor": 0.75,
        "slabs": [
            {"limit": 60, "rate": 5.77}, {"limit": 40, "rate": 7.52},
            {"limit": 50, "rate": 8.20}, {"limit": 150, "rate": 8.51},
            {"limit": None, "rate": 9.02}
        ],
        "ed_slabs": [
            {"limit": 150, "rate": 0.0},
            {"limit": 500, "rate": 0.10},
            {"limit": 1000, "rate": 0.125},
            {"limit": None, "rate": 0.15}
        ]
    },
    "Commercial - Rate A(CM-II)": {
        "fixed_charge": 34.0,
        "min_charge": 105.0,
        "load_factor": 0.75,
        "slabs": [{"limit": None, "rate": 6.09}],
        "ed_slabs": [
            {"limit": 150, "rate": 0.0},
            {"limit": 500, "rate": 0.10},
            {"limit": 1000, "rate": 0.125},
            {"limit": None, "rate": 0.15}
        ]
    },
    "Agriculture Normal - Rate C(A)": {
        "fixed_charge": 60.0,
        "min_charge": 60.0, 
        "load_factor": 0.75,
        "slabs": [{"limit": None, "rate": 4.66}], 
        "ed_slabs": [{"limit": None, "rate": 0.0}]
    },
    "Agriculture TOD - Rate C(T)": {
        "fixed_charge": 40.0,
        "min_charge": 40.0,
        "load_factor": 0.75,
        "tod_slabs": {"Normal": 3.50, "Peak": 7.71, "Off_Peak": 2.65}, 
        "ed_slabs": [{"limit": None, "rate": 0.0}]
    },
    "Industry (Rural) - Rate B(I-R)": {
        "fixed_charge": 75.0,
        "min_charge": 200.0, 
        "load_factor": 0.75,
        "slabs": [
            {"limit": 500, "rate": 5.07}, 
            {"limit": None, "rate": 7.65}
        ],
        "ed_slabs": [
            {"limit": 500, "rate": 0.0},
            {"limit": 2000, "rate": 0.025},
            {"limit": 3500, "rate": 0.075},
            {"limit": None, "rate": 0.125}
        ]
    }
}


def _merge_missing_defaults(existing_data, default_data):
    """Merge missing top-level tariff categories and keys from defaults."""
    updated = False

    for category, default_config in default_data.items():
        if category not in existing_data:
            existing_data[category] = default_config
            updated = True
            continue

        if isinstance(existing_data[category], dict):
            for key, value in default_config.items():
                if key not in existing_data[category]:
                    existing_data[category][key] = value
                    updated = True

    return existing_data, updated


def _read_migration_marker():
    if not os.path.exists(MIGRATION_MARKER_FILE):
        return ""
    try:
        with open(MIGRATION_MARKER_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _write_migration_marker(version):
    try:
        with open(MIGRATION_MARKER_FILE, "w", encoding="utf-8") as f:
            f.write(version)
    except Exception:
        pass


def _needs_one_time_reset():
    return _read_migration_marker() != TARIFF_MIGRATION_VERSION

def load_tariff():
    """Returns tariff data; creates file with defaults if missing."""
    if _needs_one_time_reset() or not os.path.exists(CONFIG_FILE):
        save_tariff(DEFAULT_TARIFF)
        _write_migration_marker(TARIFF_MIGRATION_VERSION)
        return DEFAULT_TARIFF
    
    with open(CONFIG_FILE, "r") as f:
        tariff_data = json.load(f)

    merged_data, changed = _merge_missing_defaults(tariff_data, DEFAULT_TARIFF)
    if changed:
        save_tariff(merged_data)
        _write_migration_marker(TARIFF_MIGRATION_VERSION)

    return merged_data

def save_tariff(tariff_data):
    """Saves updated dictionary back to JSON."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(tariff_data, f, indent=4)