import json
import os

CONFIG_FILE = "tariff_settings.json"

def load_tariff():
    """Reads the JSON file and returns it as a Python dictionary."""
    if not os.path.exists(CONFIG_FILE):
        print("Error: tariff_settings.json not found in the directory.")
        return {}
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_tariff(tariff_data):
    """Saves updated rates back to the JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(tariff_data, f, indent=4)