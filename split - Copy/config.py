import os

BASE_DIR = r"C:\spotbillfiles\backup"
IMAGE_FOLDER = os.path.join(BASE_DIR, "image")
DB_FILE = os.path.join(BASE_DIR, "images_v7.db") 
JSON_FILE = os.path.join(BASE_DIR, "meter_mapping.json")
SEARCHED_LISTS_FILE = os.path.join(BASE_DIR, "searched_lists.json")
ADDITIONAL_FOLDERS_FILE = os.path.join(BASE_DIR, "additional_folders.json")
NOTES_PKL = os.path.join(BASE_DIR, "notes.pkl")
NOTE_TXT = os.path.join(BASE_DIR, "note.txt")

if not os.path.exists(BASE_DIR):
    try:
        os.makedirs(BASE_DIR)
    except: pass