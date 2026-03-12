import os

BASE_DIR = r"C:\spotbillfiles\backup"
IMAGE_FOLDER = os.path.join(BASE_DIR, "image")
DB_FILE = os.path.join(BASE_DIR, "images_v7.db") 

if not os.path.exists(BASE_DIR):
    try:
        os.makedirs(BASE_DIR)
    except: pass
