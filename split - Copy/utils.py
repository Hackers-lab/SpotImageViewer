import json
import os
import pickle
import config

def load_additional_folders():
    if os.path.exists(config.ADDITIONAL_FOLDERS_FILE):
        try:
            with open(config.ADDITIONAL_FOLDERS_FILE, "r") as f:
                return json.load(f)
        except: return []
    return []

def save_additional_folders(folders):
    try:
        with open(config.ADDITIONAL_FOLDERS_FILE, "w") as f:
            json.dump(folders, f, indent=4)
    except: pass

def load_note_options():
    # Restored original V12 fallback options
    options = ["Address Correction", "Meter Defective", "Reading Issue", "Other"]
    if os.path.exists(config.NOTE_TXT):
        try:
            with open(config.NOTE_TXT, "r") as f:
                file_opts = [line.strip() for line in f if line.strip()]
                if file_opts: options = file_opts
        except: pass
    return options

def load_all_notes():
    # Restored Pickle loader
    if os.path.exists(config.NOTES_PKL):
        try:
            with open(config.NOTES_PKL, "rb") as f:
                return pickle.load(f)
        except: return {}
    return {}

def save_all_notes(notes):
    # Restored Pickle saver
    try:
        with open(config.NOTES_PKL, "wb") as f:
            pickle.dump(notes, f)
    except Exception as e:
        pass

def get_meter_number(consumer_id):
    if os.path.exists(config.JSON_FILE):
        try:
            with open(config.JSON_FILE, "r") as f:
                data = json.load(f)
            return data.get(consumer_id, {}).get("meter_no")
        except: return None
    return None

def console_log(message):
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")