import os
import base64
import logging
import customtkinter as ctk

# Define appearance and theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Setup App Data logging
LOG_DIR = os.path.expanduser("~/.gemini/antigravity/logs")
os.makedirs(LOG_DIR, exist_ok=True)
IMAGE_CACHE_DIR = os.path.join(LOG_DIR, "image_cache")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
DEFAULT_BASE_URL = "https://spotai.wbsedcl.in"
DEFAULT_USER = "90018747"
DEFAULT_OFF_CODE = "6612107"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def hk_encrypt(password_str):
    secret_key = "@FrTu^^&!#$%^/41"
    key_len = len(secret_key)
    xor_chars = []
    for r in range(len(password_str)):
        c_code = ord(password_str[r])
        k_code = ord(secret_key[r % key_len])
        xor_chars.append(chr(c_code ^ k_code))
    xor_str = "".join(xor_chars)
    return base64.b64encode(xor_str.encode('latin1')).decode('utf-8')
