import os
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import messagebox, filedialog, Menu, Toplevel, Listbox, ttk
from PIL import Image, ImageTk
from datetime import datetime
import json
import pandas as pd
import threading
import hashlib
import shutil
import time
import sqlite3
import csv

# Ensure backup directory exists before using any files in it
BACKUP_DIR = r"C:\spotbillfiles\backup"
os.makedirs(BACKUP_DIR, exist_ok=True)

# Constants
IMAGE_FOLDER = os.path.join(BACKUP_DIR, "image")
TXT_FILE = os.path.join(BACKUP_DIR, "images.txt")
JSON_FILE = os.path.join(BACKUP_DIR, "meter_mapping.json")
SEARCHED_LISTS_FILE = os.path.join(BACKUP_DIR, "searched_lists.json")
DATABASE_FILE = os.path.join(BACKUP_DIR, "image_database.db")
ADDITIONAL_FOLDERS_FILE = os.path.join(BACKUP_DIR, "additional_folders.json")

# Global Variables
image_index = {}
meter_mapping = {}
img_tk = None
img = None
img_original = None
zoom_scale = 1.0
additional_folders = []
last_online_folders = set()

def initialize_database():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS images (
        consumer_id TEXT,
        mru TEXT,
        date TEXT,
        image_path TEXT,
        folder_hash TEXT,
        PRIMARY KEY (consumer_id, date, image_path)
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS folder_indexes (
        folder_hash TEXT PRIMARY KEY,
        folder_path TEXT,
        last_indexed TEXT
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consumer_notes (
        consumer_id TEXT PRIMARY KEY,
        note_option TEXT,
        note_text TEXT
    )
    ''')
    conn.commit()
    conn.close()

def get_note_options():
    notes_file = os.path.join(BACKUP_DIR, "note.txt")
    if not os.path.exists(notes_file):
        return ["Inspection required", "regeneration required", "wrong meter reading"]
    with open(notes_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_note_color(note_text):
    if not note_text:
        return "secondary"
    note_lower = note_text.lower()
    if "inspection" in note_lower:
        return "danger"
    elif "regeneration" in note_lower:
        return "danger"
    elif "wrong" in note_lower:
        return "danger"
    return "secondary"

def get_consumer_note(consumer_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT note_option, note_text FROM consumer_notes WHERE consumer_id = ?", (consumer_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        note_option, note_text = row
        full_text = f"\nType: {note_option.title()}"
        if note_text:
            full_text += f"\n\nNote: {note_text.title()}"
        color = get_note_color(full_text)
        return full_text, color
    return "", "secondary"

def add_note_for_consumer():
    consumer_id = entry_consumer_id.get().strip()
    note_option = note_var.get()
    note_text = note_entry.get("1.0", tk.END).strip()
    if not consumer_id or not note_option or note_option == "Select Note...":
        messagebox.showwarning("Warning", "Please select a note option.")
        return
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO consumer_notes (consumer_id, note_option, note_text) VALUES (?, ?, ?)",
        (consumer_id, note_option, note_text)
    )
    conn.commit()
    conn.close()
    messagebox.showinfo("Success", f"Note added for Consumer ID: {consumer_id}")
    note_display, note_color = get_consumer_note(consumer_id)
    label_notes_content.config(
        text=note_display if note_display else "No note for this consumer.",
        bootstyle=note_color
    )

def export_notes_to_csv():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT consumer_id, note_option, note_text FROM consumer_notes")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        messagebox.showwarning("Warning", "No notes found to export.")
        return
    export_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="consumer_notes.csv"
    )
    if not export_path:
        return
    with open(export_path, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Consumer ID", "Note Option", "Note Text"])
        for row in rows:
            writer.writerow(row)
    messagebox.showinfo("Success", f"Notes exported to {export_path}")

def save_folder_index_sqlite(folder_path, index):
    folder_hash = hashlib.md5(folder_path.encode()).hexdigest()[:8]
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO folder_indexes (folder_hash, folder_path, last_indexed) VALUES (?, ?, ?)",
        (folder_hash, folder_path, datetime.now().isoformat())
    )
    cursor.execute("DELETE FROM images WHERE folder_hash = ?", (folder_hash,))
    for consumer_id, data in index.items():
        mru = data["MRU"]
        for date, paths in data["images"].items():
            for path in paths:
                cursor.execute(
                    "INSERT OR IGNORE INTO images (consumer_id, mru, date, image_path, folder_hash) VALUES (?, ?, ?, ?, ?)",
                    (consumer_id, mru, date, path, folder_hash)
                )
    conn.commit()
    conn.close()

def sync_folder_index_sqlite(folder_path):
    folder_hash = hashlib.md5(folder_path.encode()).hexdigest()[:8]
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    valid_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp')
    current_files = set()
    for folder_root, dirs, files in os.walk(folder_path):
        for filename in files:
            if not filename.lower().endswith(valid_exts):
                continue
            if len(filename) < 23:
                continue
            date = filename[:8]
            mru = filename[8:16]
            consumer_id = filename[16:25]
            full_path = os.path.join(folder_root, filename)
            current_files.add((consumer_id, mru, date, full_path, folder_hash))
    cursor.execute("SELECT consumer_id, mru, date, image_path, folder_hash FROM images WHERE folder_hash = ?", (folder_hash,))
    db_files = set(cursor.fetchall())
    to_add = current_files - db_files
    to_delete = db_files - current_files
    if to_add:
        cursor.executemany(
            "INSERT OR IGNORE INTO images (consumer_id, mru, date, image_path, folder_hash) VALUES (?, ?, ?, ?, ?)",
            list(to_add)
        )
    for record in to_delete:
        cursor.execute(
            "DELETE FROM images WHERE consumer_id=? AND mru=? AND date=? AND image_path=? AND folder_hash=?",
            record)
    cursor.execute(
        "INSERT OR REPLACE INTO folder_indexes (folder_hash, folder_path, last_indexed) VALUES (?, ?, ?)",
        (folder_hash, folder_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def load_all_folder_indexes_sqlite():
    global image_index
    image_index = {}
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    folder_hashes = [hashlib.md5(f.encode()).hexdigest()[:8] for f in folders]
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    default_hash = hashlib.md5(IMAGE_FOLDER.encode()).hexdigest()[:8]
    if default_hash in folder_hashes:
        cursor.execute("SELECT consumer_id, mru, date, image_path FROM images WHERE folder_hash = ?", (default_hash,))
        for consumer_id, mru, date, image_path in cursor.fetchall():
            if consumer_id not in image_index:
                image_index[consumer_id] = {"MRU": mru, "images": {}}
            if date not in image_index[consumer_id]["images"]:
                image_index[consumer_id]["images"][date] = []
            if image_path not in image_index[consumer_id]["images"][date]:
                image_index[consumer_id]["images"][date].append(image_path)
    for folder in additional_folders:
        if not check_folder_status(folder):
            continue
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        cursor.execute("SELECT consumer_id, mru, date, image_path FROM images WHERE folder_hash = ?", (folder_hash,))
        for consumer_id, mru, date, image_path in cursor.fetchall():
            if consumer_id not in image_index:
                image_index[consumer_id] = {"MRU": mru, "images": {}}
            if date not in image_index[consumer_id]["images"]:
                image_index[consumer_id]["images"][date] = []
            if image_path not in image_index[consumer_id]["images"][date]:
                image_index[consumer_id]["images"][date].append(image_path)
    conn.close()
    return image_index

def reload_image_index(save_pickle=False):
    load_all_folder_indexes_sqlite()
    update_image_count()

def reload_image_index_no_ui(save_pickle=False):
    load_all_folder_indexes_sqlite()

def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%d%m%Y").strftime("%d-%b-%Y")
    except ValueError:
        return date_str

def search_consumer():
    consumer_id = entry_consumer_id.get().strip()
    listbox_dates.delete(0, tk.END)
    label_consumer_details.config(text="")
    label_total_images.config(text="")
    show_latest_previews(consumer_id)
    note_display, note_color = get_consumer_note(consumer_id)
    label_notes_content.config(
        text=note_display if note_display else "No note for this consumer.",
        bootstyle=note_color
    )
    if not consumer_id.isdigit() or len(consumer_id) != 9:
        messagebox.showwarning("Invalid Input", "Consumer ID must be a 9-digit number.")
        return
    if consumer_id in image_index:
        consumer_data = image_index[consumer_id]
        mru_code = consumer_data["MRU"]
        images_data = consumer_data["images"]
        if not images_data:
            label_consumer_details.config(text=f"Consumer ID: {consumer_id}\nMRU: {mru_code}")
            label_total_images.config(text="No images found for this Consumer ID!", foreground="red")
            return
        sorted_dates = sorted(images_data.keys(), key=lambda x: datetime.strptime(x, "%d%m%Y"), reverse=True)
        meter_number = get_meter_number(consumer_id)
        meter_text = f"\nMeter Number: {meter_number}" if meter_number else ""
        label_consumer_details.config(text=f"Consumer ID: {consumer_id}\nMRU: {mru_code}{meter_text}")
        label_total_images.config(text=f"Total Images Found: {sum(len(images) for images in images_data.values())}")
        for date in sorted_dates:
            readable_date = format_date(date)
            listbox_dates.insert(tk.END, readable_date)
    else:
        label_consumer_details.config(text="No images found for this Consumer ID!", foreground="red")
        label_total_images.config(text="")
    searched_lists = load_searched_lists()
    if consumer_id not in searched_lists["consumer_ids"]:
        searched_lists["consumer_ids"].append(consumer_id)
        save_searched_lists(searched_lists)

def search_meter():
    meter_number = entry_meter_number.get().strip().lower()
    if not meter_number:
        messagebox.showwarning("Invalid Input", "Please enter a meter number.")
        return
    consumer_id = get_consumer_id(meter_number)
    if not consumer_id:
        messagebox.showinfo("Not Found", f"No consumer ID found for meter number: {meter_number}")
        return
    entry_consumer_id.delete(0, tk.END)
    entry_consumer_id.insert(0, consumer_id)
    search_consumer()
    searched_lists = load_searched_lists()
    if meter_number not in searched_lists["meter_numbers"]:
        searched_lists["meter_numbers"].append(meter_number)
        save_searched_lists(searched_lists)

def get_meter_number(consumer_id):
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as file:
            meter_mapping = json.load(file)
            return meter_mapping.get(consumer_id, {}).get("meter_no")
    return None

def get_consumer_id(meter_number):
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as file:
            meter_mapping = json.load(file)
            for con_id, data in meter_mapping.items():
                if data.get("meter_no", "").lower() == meter_number.lower():
                    return con_id
    return None

def update_meter_list():
    messagebox.showinfo(
        "Excel File Format",
        "Please ensure the Excel file contains:\n"
        "- Consumer ID in Column 1\n"
        "- Meter Number in Column 2"
    )
    file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
    if not file_path:
        return
    try:
        progress_window = show_progress("Reading Excel file...")
        df = pd.read_excel(file_path, header=None, usecols=[0, 1], dtype={0: str, 1: str})
        progress_window.destroy()
        progress_window = show_progress("Processing meter numbers...")
        df[0] = df[0].astype(str).str.strip()
        df[1] = df[1].astype(str).str.strip()
        progress_window.destroy()
        progress_window = show_progress("Creating meter mapping...")
        global meter_mapping
        meter_mapping = {
            row[0]: {"meter_no": row[1]}
            for _, row in df.iterrows()
        }
        progress_window.destroy()
        progress_window = show_progress("Saving meter mapping to JSON file...")
        with open(JSON_FILE, "w") as file:
            json.dump(meter_mapping, file, indent=4)
        progress_window.destroy()
        messagebox.showinfo("Success", "Meter list updated successfully!")
        entry_meter_number.config(state=tk.NORMAL)
        btn_search_meter.config(text="Search Meter", command=search_meter)
    except Exception as e:
        progress_window.destroy()
        messagebox.showerror("Error", f"Failed to update meter list: {e}")

def refresh_search():
    entry_consumer_id.delete(0, tk.END)
    entry_meter_number.delete(0, tk.END)
    listbox_dates.delete(0, tk.END)
    label_consumer_details.config(text="")
    label_total_images.config(text="")
    canvas.delete("all")
    hide_buttons()
    for frame in preview_frames:
        frame.pack_forget()

def show_about():
    about_text = (
        "Spot Image Viewer\n\n"
        "Features:\n"
        "• Search and preview consumer images by Consumer ID or Meter Number.\n"
        "• Instantly preview the 3 latest images for a consumer after search.\n"
        "• Click any preview to view it in full size.\n"
        "• View all available image dates and select any to display the image.\n"
        "• Zoom in/out, print, or save the displayed image.\n"
        "• Save all images for a consumer to your Downloads folder with one click.\n"
        "• Add or remove network folders; images from online folders are merged and counted live.\n"
        "• Update the meter list by importing an Excel file with Consumer IDs and Meter Numbers.\n"
        "• Theme selector for instant appearance change (Theme menu).\n"
        "• Maintain a history of searched Consumer IDs and Meter Numbers for quick access.\n\n"
        "Developed By: Pramod Verma\n"
        "ERP ID: 90018747\n"
        "Version: 5.2.0\n"
    )
    messagebox.showinfo("About", about_text)

def open_documentation():
    pdf_path = os.path.join(os.path.dirname(TXT_FILE), "help.pdf")
    if os.path.exists(pdf_path):
        try:
            os.startfile(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open the PDF file: {e}")
    else:
        messagebox.showerror("Error", "The help documentation file (help.pdf) was not found!")

def background_reload_image_index():
    def worker():
        t0 = time.time()
        reload_image_index_no_ui()
        t1 = time.time()
        print(f"[Startup] reload_image_index (background): {t1-t0:.2f} seconds")
        root.after(0, update_image_count)
    threading.Thread(target=worker, daemon=True).start()

def update_image_count():
    merged_total = 0
    for consumer_data in image_index.values():
        for images in consumer_data["images"].values():
            merged_total += len(images)
    label_image_count.config(text=f"Total Images in Database: {merged_total}")

def display_image(event):
    for frame in preview_frames:
        frame.pack_forget()
    global img_tk, img, img_original
    selected_date_index = listbox_dates.curselection()
    if not selected_date_index:
        return
    selected_date = listbox_dates.get(selected_date_index)
    consumer_id = entry_consumer_id.get().strip()
    if consumer_id in image_index:
        images_data = image_index[consumer_id]["images"]
        for date in images_data:
            if format_date(date) == selected_date:
                default_img = None
                for img_path in images_data[date]:
                    if img_path.startswith(os.path.abspath(IMAGE_FOLDER)):
                        default_img = img_path
                        break
                image_path = default_img if default_img else images_data[date][0]
                try:
                    img_original = Image.open(image_path)
                    img = img_original.copy()
                    img.thumbnail((canvas.winfo_width(), canvas.winfo_height()), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(img)
                    canvas.delete("all")
                    canvas.image = img_tk
                    canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)
                    show_buttons()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load image: {e}")
                break

def zoom_in():
    global img_tk, img, zoom_scale, img_original
    if img_original:
        zoom_scale *= 1.2
        new_size = (int(img_original.width * zoom_scale), int(img_original.height * zoom_scale))
        img = img_original.resize(new_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)

def zoom_out():
    global img_tk, img, zoom_scale, img_original
    if img_original:
        zoom_scale *= 0.8
        new_size = (int(img_original.width * zoom_scale), int(img_original.height * zoom_scale))
        img = img_original.resize(new_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)

def print_image():
    if img:
        temp_file = "temp_image.png"
        img.save(temp_file)
        os.startfile(temp_file, "print")

def save_image():
    if img_original:
        consumer_id = entry_consumer_id.get().strip()
        selected_date_index = listbox_dates.curselection()
        if not consumer_id or not selected_date_index:
            messagebox.showwarning("Warning", "Please select a consumer and a date.")
            return
        selected_date = listbox_dates.get(selected_date_index)
        date_str = selected_date.replace("-", "")
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        consumer_dir = os.path.join(downloads_dir, consumer_id)
        os.makedirs(consumer_dir, exist_ok=True)
        save_path = os.path.join(consumer_dir, f"{date_str}.png")
        try:
            img_original.save(save_path)
            messagebox.showinfo("Success", f"Image saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {e}")

def save_multiple_images():
    consumer_id = entry_consumer_id.get().strip()
    if not consumer_id or consumer_id not in image_index:
        messagebox.showwarning("Warning", "Please search and select a valid Consumer ID first.")
        return
    images_data = image_index[consumer_id]["images"]
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    consumer_dir = os.path.join(downloads_dir, consumer_id)
    os.makedirs(consumer_dir, exist_ok=True)
    saved = 0
    for date, paths in images_data.items():
        default_img = None
        for path in paths:
            if path.startswith(os.path.abspath(IMAGE_FOLDER)):
                default_img = path
                break
        image_path = default_img if default_img else paths[0]
        ext = os.path.splitext(image_path)[1].lower()
        save_path = os.path.join(consumer_dir, f"{date}{ext if ext else '.png'}")
        try:
            shutil.copy(image_path, save_path)
            saved += 1
        except Exception:
            continue
    if saved:
        messagebox.showinfo("Success", f"{saved} images saved to:\n{consumer_dir}")
    else:
        messagebox.showwarning("Warning", "No images were saved.")

def show_buttons():
    btn_zoom_out.pack(side=LEFT, padx=5)
    btn_zoom_in.pack(side=LEFT, padx=5)
    btn_print.pack(side=LEFT, padx=5)
    btn_save.pack(side=LEFT, padx=5)
    btn_save_multiple.pack(side=LEFT, padx=5)
    notes_pane.pack(side=RIGHT, fill=Y, padx=10, pady=10)


def hide_buttons():
    btn_zoom_in.pack_forget()
    btn_zoom_out.pack_forget()
    btn_print.pack_forget()
    btn_save.pack_forget()
    btn_save_multiple.pack_forget()
    notes_pane.pack_forget()
    
def load_searched_lists():
    if os.path.exists(SEARCHED_LISTS_FILE):
        with open(SEARCHED_LISTS_FILE, "r") as file:
            return json.load(file)
    return {"consumer_ids": [], "meter_numbers": []}

def save_searched_lists(searched_lists):
    with open(SEARCHED_LISTS_FILE, "w") as file:
        json.dump(searched_lists, file, indent=4)

def show_searched_lists(event, entry_widget, list_type):
    searched_lists = load_searched_lists()
    lists = searched_lists[list_type][-8:]
    if not lists:
        return
    dropdown = Toplevel()
    dropdown.geometry(f"+{entry_widget.winfo_rootx()}+{entry_widget.winfo_rooty() + entry_widget.winfo_height()}")
    dropdown.overrideredirect(True)
    listbox = Listbox(dropdown, font=("Arial", 12), width=entry_widget.winfo_width() // 9)
    listbox.pack()
    for item in lists:
        listbox.insert(tk.END, item)

    def select_item(event):
        index = listbox.nearest(event.y)
        if index < 0 or index >= listbox.size():
            return
        selected_item = listbox.get(index)
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, selected_item)
        dropdown.destroy()
        if list_type == "consumer_ids":
            search_consumer()
        elif list_type == "meter_numbers":
            search_meter()

    listbox.bind("<Button-1>", select_item)
    listbox.bind("<Return>", select_item)

def show_progress(message):
    progress_window = Toplevel()
    progress_window.title("Progress")
    label = tb.Label(progress_window, text=message, font=("Arial", 12))
    label.pack(padx=20, pady=20)
    progress_window.update()
    return progress_window

def show_latest_previews(consumer_id):
    canvas.delete("all")
    hide_buttons()
    for frame in preview_frames:
        frame.pack_forget()
    if consumer_id not in image_index:
        return
    images_data = image_index[consumer_id]["images"]
    all_images = []
    for date, paths in images_data.items():
        default_img = None
        for path in paths:
            if path.startswith(os.path.abspath(IMAGE_FOLDER)):
                default_img = path
                break
        all_images.append((date, default_img if default_img else paths[0]))
    all_images.sort(key=lambda x: datetime.strptime(x[0], "%d%m%Y"), reverse=True)
    preview_dates = []
    for i, (date, path) in enumerate(all_images[:3]):
        try:
            img = Image.open(path)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img)
            preview_canvases[i].delete("all")
            preview_canvases[i].create_image(110, 110, anchor=tk.CENTER, image=img_tk)
            preview_canvases[i].image = img_tk
            preview_labels[i].config(text=format_date(date))
            preview_frames[i].pack(side=LEFT, padx=10, pady=10, in_=frame_right)
            preview_dates.append(date)
            preview_canvases[i].unbind("<Button-1>")
            def make_onclick(idx):
                return lambda event: open_preview_image(consumer_id, preview_dates[idx])
            preview_canvases[i].bind("<Button-1>", make_onclick(i))
        except Exception as e:
            preview_labels[i].config(text="Error")
            preview_canvases[i].delete("all")
            preview_frames[i].pack(side=LEFT, padx=10, pady=10, in_=frame_right)
            preview_canvases[i].unbind("<Button-1>")
    for j in range(len(all_images), 3):
        preview_frames[j].pack_forget()
        preview_canvases[j].unbind("<Button-1>")

def open_preview_image(consumer_id, date):
    for frame in preview_frames:
        frame.pack_forget()
    global img_tk, img, img_original, zoom_scale
    zoom_scale = 1.0
    if consumer_id in image_index:
        images_data = image_index[consumer_id]["images"]
        if date in images_data:
            default_img = None
            for img_path in images_data[date]:
                if img_path.startswith(os.path.abspath(IMAGE_FOLDER)):
                    default_img = img_path
                    break
            image_path = default_img if default_img else images_data[date][0]
            try:
                img_original = Image.open(image_path)
                img = img_original.copy()
                img.thumbnail((canvas.winfo_width(), canvas.winfo_height()), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                canvas.delete("all")
                canvas.image = img_tk
                canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)
                show_buttons()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")

def load_additional_folders():
    global additional_folders
    if os.path.exists(ADDITIONAL_FOLDERS_FILE):
        with open(ADDITIONAL_FOLDERS_FILE, "r") as f:
            additional_folders = json.load(f)
    else:
        additional_folders = []

def save_additional_folders():
    with open(ADDITIONAL_FOLDERS_FILE, "w") as f:
        json.dump(additional_folders, f, indent=4)

def add_folder():
    folder = filedialog.askdirectory(title="Select Additional Image Folder")
    if folder and folder not in additional_folders:
        additional_folders.append(folder)
        save_additional_folders()
        update_folder_list()
        def do_indexing():
            generate_folder_index(folder)
            root.after(0, reload_image_index)
        threading.Thread(target=do_indexing, daemon=True).start()

def remove_folder():
    selected = folder_listbox.curselection()
    if selected:
        idx = selected[0]
        del additional_folders[idx]
        save_additional_folders()
        update_folder_list()

def check_folder_status(folder):
    return os.path.exists(folder)

def update_folder_list():
    folder_listbox.delete(0, tk.END)
    for idx, folder in enumerate(additional_folders, start=1):
        status = check_folder_status(folder)
        color = "green" if status else "red"
        folder_name = os.path.basename(folder)
        display_text = f"{idx}. {folder_name}\n [{folder}]"
        # display_text = f"{idx}. {os.path.basename(folder)}\n\n    {folder}"
        folder_listbox.insert(tk.END, display_text)
        folder_listbox.itemconfig(tk.END, foreground=color)

def refresh_folder_status():
    global last_online_folders
    for idx, folder in enumerate(additional_folders):
        status = check_folder_status(folder)
        color = "green" if status else "red"
        folder_listbox.itemconfig(idx, foreground=color)
    current_online = set([IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)])
    if current_online != last_online_folders:
        last_online_folders = current_online
        reload_image_index()
    folder_status_pane.after(3000, refresh_folder_status)

def generate_folder_index(folder):
    index = {}
    try:
        valid_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp')
        for folder_root, dirs, files in os.walk(folder):
            for filename in files:
                if not filename.lower().endswith(valid_exts):
                    continue
                if len(filename) < 23:
                    continue
                date = filename[:8]
                mru = filename[8:16]
                consumer_id = filename[16:25]
                full_path = os.path.join(folder_root, filename)
                if consumer_id not in index:
                    index[consumer_id] = {"MRU": mru, "images": {}}
                if date not in index[consumer_id]["images"]:
                    index[consumer_id]["images"][date] = []
                index[consumer_id]["images"][date].append(full_path)
        sync_folder_index_sqlite(folder)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to index images in {folder}: {e}")

def show_indexing_progress():
    progress_window = Toplevel()
    progress_window.title("Indexing Images")
    label = tb.Label(progress_window, text="Indexing images, please wait...", font=("Arial", 14))
    label.pack(padx=30, pady=30)
    progress_window.update()
    root.after(500, progress_window.destroy)

def generate_all_folder_indexes():
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    for folder in folders:
        generate_folder_index(folder)
    messagebox.showinfo("Success", "New images updated!")
    reload_image_index()

def generate_all_folder_indexes_with_progress():
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    show_progress_bar()
    progress_time_label.config(text="Loading images please wait...")
    root.update()
    def do_indexing():
        valid_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp')
        total = 0
        for folder in folders:
            for folder_root, dirs, files in os.walk(folder):
                total += sum(1 for filename in files if filename.lower().endswith(valid_exts) and len(filename) >= 23)
        if total == 0:
            root.after(0, lambda: messagebox.showinfo("Info", "No images found in any folder."))
            root.after(0, hide_progress_bar)
            return
        processed = 0
        for folder in folders:
            index = {}
            try:
                for rootdir, dirs, files in os.walk(folder):
                    for filename in files:
                        if not filename.lower().endswith(valid_exts):
                            continue
                        if len(filename) < 23:
                            continue
                        date = filename[:8]
                        mru = filename[8:16]
                        consumer_id = filename[16:25]
                        full_path = os.path.join(rootdir, filename)
                        if consumer_id not in index:
                            index[consumer_id] = {"MRU": mru, "images": {}}
                        if date not in index[consumer_id]["images"]:
                            index[consumer_id]["images"][date] = []
                        index[consumer_id]["images"][date].append(full_path)
                        processed += 1
                        if processed % 100 == 0 or processed == total:
                            percent = (processed / total) * 100
                            root.after(0, lambda p=percent: update_progress_bar(p))
                sync_folder_index_sqlite(folder)
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Error", f"Failed to index images in {folder}: {e}"))
        root.after(0, lambda: update_progress_bar(100))
        root.after(0, finish)
    def finish():
        hide_progress_bar()
        messagebox.showinfo("Success", "Images updated for all online folders!")
        reload_image_index()
        update_image_count()
    root.after(100, lambda: threading.Thread(target=do_indexing, daemon=True).start())

def debug_show_index_counts():
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    msg_lines = []
    total_per_folder = []
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    for folder in folders:
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        cursor.execute("SELECT COUNT(*) FROM images WHERE folder_hash = ?", (folder_hash,))
        count = cursor.fetchone()[0]
        msg_lines.append(f"{os.path.basename(folder)}: {count} images")
        total_per_folder.append(count)
    
    conn.close()
    
    merged_total = 0
    for consumer_data in image_index.values():
        for images in consumer_data["images"].values():
            merged_total += len(images)
    msg_lines.append(f"\nMerged (app) total: {merged_total} images")
    messagebox.showinfo("Image count info", "\n".join(msg_lines))

def update_progress_bar(percent):
    progress_var.set(percent)
    root.update_idletasks()

# --- GUI SECTION ---

root = tb.Window(themename="minty")
root.title("Spot Image Viewer")
root.geometry("1200x800")
root.state("zoomed")

frame_top = tb.Frame(root, padding=10)
frame_top.pack(fill=X, padx=10, pady=10)

label_consumer_id = tb.Label(frame_top, text="Enter Consumer ID:", font=("Arial", 12, "bold"))
label_consumer_id.pack(side=LEFT, padx=5)

entry_consumer_id = tb.Entry(frame_top, width=20, font=("Arial", 12))
entry_consumer_id.pack(side=LEFT, padx=5)
entry_consumer_id.bind("<Return>", lambda event: search_consumer())

btn_search = tb.Button(frame_top, text="Search", command=search_consumer, bootstyle="success")
btn_search.pack(side=LEFT, padx=5)

label_meter_number = tb.Label(frame_top, text="Enter Meter Number:", font=("Arial", 12, "bold"))
label_meter_number.pack(side=LEFT, padx=5)

entry_meter_number = tb.Entry(frame_top, width=20, font=("Arial", 12), state=tk.DISABLED)
entry_meter_number.pack(side=LEFT, padx=5)
entry_meter_number.bind("<Return>", lambda event: search_meter())

btn_search_meter = tb.Button(frame_top, text="Update List", command=update_meter_list, bootstyle="success")
btn_search_meter.pack(side=LEFT, padx=5)

btn_refresh = tb.Button(frame_top, text="Refresh", command=refresh_search, bootstyle="info")
btn_refresh.pack(side=LEFT, padx=5)

label_image_count_frame = tb.Frame(frame_top)
label_image_count_frame.pack(side=LEFT, padx=5)

label_image_count = tb.Label(label_image_count_frame, text="Total Images: 0", font=("Arial", 12, "bold"), bootstyle="success")
label_image_count.pack(side=LEFT)

progress_var = tb.DoubleVar()
progress_bar = ttk.Progressbar(
    label_image_count_frame,
    variable=progress_var,
    length=250,
    mode="indeterminate",
    style="success.Horizontal.TProgressbar"
)
progress_time_label = tb.Label(label_image_count_frame, text="", font=("Arial", 12, "italic"), bootstyle="secondary")

def show_progress_bar():
    label_image_count.pack_forget()
    progress_bar.pack()
    progress_time_label.pack()
    progress_bar.start(10)

def hide_progress_bar():
    progress_bar.stop()
    progress_bar.pack_forget()
    progress_time_label.pack_forget()
    label_image_count.pack()

# Menu Bar
menu_bar = Menu(root)
root.config(menu=menu_bar)
file_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Update Consumer List", command=update_meter_list)
file_menu.add_command(label="Reload Images", command=generate_all_folder_indexes_with_progress)
file_menu.add_command(label="Image Counts", command=debug_show_index_counts)
file_menu.add_separator()
file_menu.add_command(label="Export Notes to CSV", command=export_notes_to_csv)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

def change_theme(theme_name):
    root.style.theme_use(theme_name)

settings_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Theme", menu=settings_menu)

themes = [
    "cosmo", "flatly", "journal", "litera", "lumen", "minty", "pulse",
    "sandstone", "united", "yeti", "morph", "solar", "superhero", "cyborg", "darkly"
]
for theme in themes:
    settings_menu.add_command(
        label=theme.capitalize(),
        command=lambda t=theme: root.style.theme_use(t)
    )

help_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="Documentation", command=open_documentation)
help_menu.add_command(label="About", command=show_about)

main_frame = tb.Frame(root)
main_frame.pack(fill=BOTH, expand=True)

# Left pane (dates)
frame_left = tb.Frame(main_frame, width=200, padding=10, relief="ridge", borderwidth=2)
frame_left.pack(side=LEFT, fill=Y, padx=10, pady=10)

label_consumer_details = tb.Label(
    frame_left,
    text="",
    wraplength=400,
    bootstyle="success",
    font=("Arial", 11, "bold")
)
label_consumer_details.pack(pady=5)

label_total_images = tb.Label(frame_left, text="", wraplength=180)
label_total_images.pack(pady=5)

label_dates = tb.Label(frame_left, text="Available Dates:", font=("Arial", 12, "bold"))
label_dates.pack()

listbox_dates = tk.Listbox(frame_left, font=("Arial", 12), height=20)
listbox_dates.pack(fill=BOTH, expand=True)
listbox_dates.bind("<<ListboxSelect>>", display_image)

# Image display pane
frame_right = tb.Frame(main_frame, width=500, padding=10, relief="ridge", borderwidth=2)
frame_right.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

canvas = tk.Canvas(frame_right, bg="#f8f9fa", width=500, height=500)
canvas.pack(fill=BOTH, expand=True)

# Network folders pane (far right)
folder_status_pane = tb.Frame(main_frame, width=250, padding=10, relief="ridge", borderwidth=2)
folder_status_pane.pack(side=RIGHT, fill=Y, padx=10, pady=10)

folder_title = tb.Label(folder_status_pane, text="Network Folders", font=("Arial", 13, "bold"), bootstyle="info")
folder_title.pack(pady=(0, 10))

folder_listbox = tk.Listbox(folder_status_pane, font=("Arial", 9), height=25, width=32)
folder_listbox.pack(pady=5, fill=X)

btn_add_folder = tb.Button(folder_status_pane, text="Add", command=add_folder, bootstyle="success")
btn_add_folder.pack(side=LEFT, padx=5, pady=10, anchor="s")

btn_remove_folder = tb.Button(
    folder_status_pane,
    text="Remove",
    command=remove_folder,
    bootstyle="danger"
)
btn_remove_folder.pack(side=LEFT, padx=5, pady=10, anchor="s")

def on_folder_select(event):
    pass

folder_listbox.bind("<<ListboxSelect>>", on_folder_select)

def on_folder_delete(event):
    remove_folder()

folder_listbox.bind("<Delete>", on_folder_delete)

# Notes pane (middle)
notes_pane = tb.Frame(main_frame, width=200, padding=10, relief="ridge", borderwidth=2)
notes_pane.pack(side=RIGHT, fill=Y, padx=10, pady=10)

label_notes_title = tb.Label(notes_pane, text="Add/View Note", font=("Arial", 12, "bold"), bootstyle="info")
label_notes_title.pack(anchor="w", pady=(0, 10))

note_options = get_note_options()
note_var = tk.StringVar()
note_dropdown = ttk.Combobox(notes_pane, textvariable=note_var, values=note_options, state="readonly", width=28)
note_dropdown.set("Select Note...")
note_dropdown.pack(anchor="w", pady=(0, 5), fill=X)

note_text_frame = tb.Frame(notes_pane)
note_text_frame.pack(anchor="w", pady=(0, 5), fill=X)

note_text_var = tk.StringVar()
note_entry = tb.Text(note_text_frame, width=28, height=6, font=("Arial", 10))
note_entry.pack(fill=X)

note_buttons_frame = tb.Frame(notes_pane)
note_buttons_frame.pack(anchor="w", pady=(0, 10), fill=X)

btn_add_note = tb.Button(note_buttons_frame, text="Add Note", command=add_note_for_consumer, bootstyle="success")
btn_add_note.pack(side=LEFT, padx=(0, 5))

def delete_note_for_consumer():
    consumer_id = entry_consumer_id.get().strip()
    if not consumer_id:
        messagebox.showwarning("Warning", "Please select a Consumer ID first.")
        return
    
    # Confirm deletion
    if not messagebox.askyesno("Confirm", "Delete note for this consumer?"):
        return
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM consumer_notes WHERE consumer_id = ?", (consumer_id,))
    conn.commit()
    conn.close()
    
    messagebox.showinfo("Success", f"Note deleted for Consumer ID: {consumer_id}")
    # Clear the note display
    label_notes_content.config(text="No note for this consumer.", bootstyle="secondary")
    # Clear the input fields
    note_var.set("Select Note...")
    note_entry.delete("1.0", tk.END)

btn_delete_note = tb.Button(note_buttons_frame, text="Delete Note", command=delete_note_for_consumer, bootstyle="danger")
btn_delete_note.pack(side=LEFT)

label_prev_note_title = tb.Label(notes_pane, text="Previous Note:", font=("Arial", 11, "bold"), bootstyle="info")
label_prev_note_title.pack(anchor="w", pady=(10, 0))

label_notes_content = tb.Label(
    notes_pane, 
    text="", 
    font=("Arial", 12), 
    wraplength=270, 
    justify="left", 
    bootstyle="danger"
)
label_notes_content.pack(anchor="w", pady=(5, 0), fill=X)

preview_frames = []
preview_canvases = []
preview_labels = []
for i in range(3):
    frame = tb.Frame(frame_right, padding=5, relief="groove", borderwidth=2)
    canvas_preview = tk.Canvas(frame, width=220, height=220, bg="#f8f9fa", highlightthickness=2, highlightbackground="#0d6efd")
    label = tb.Label(frame, text="", font=("Arial", 10, "bold"), bootstyle="secondary")
    canvas_preview.pack()
    label.pack()
    preview_frames.append(frame)
    preview_canvases.append(canvas_preview)
    preview_labels.append(label)

button_frame = tb.Frame(frame_right, padding=5)
button_frame.pack(pady=10)

btn_zoom_out = tb.Button(button_frame, text="-", command=zoom_out, bootstyle="secondary")
btn_zoom_in = tb.Button(button_frame, text="+", command=zoom_in, bootstyle="secondary")
btn_print = tb.Button(button_frame, text="Print", command=print_image, bootstyle="info")
btn_save = tb.Button(button_frame, text="Save", command=save_image, bootstyle="success")
btn_save_multiple = tb.Button(button_frame, text="Save All", command=save_multiple_images, bootstyle="success")

hide_buttons()

# Initialize database and load data
initialize_database()
load_additional_folders()
update_folder_list()
refresh_folder_status()
root.after(100, background_reload_image_index)


if os.path.exists(JSON_FILE):
    entry_meter_number.config(state=tk.NORMAL)
    btn_search_meter.config(text="Search Meter", command=search_meter)

entry_consumer_id.bind("<space>", lambda e: show_searched_lists(e, entry_consumer_id, "consumer_ids"))
entry_meter_number.bind("<space>", lambda e: show_searched_lists(e, entry_meter_number, "meter_numbers"))

def check_and_generate_indexes_on_startup():
    folders = [IMAGE_FOLDER] + additional_folders
    index_exists = False
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images")
    count = cursor.fetchone()[0]
    conn.close()
    if count > 0:
        index_exists = True
    if not index_exists:
        messagebox.showinfo("Welcome", "Greetings!!\nNo image index found. The app will now index all images. This may take a while.")
        generate_all_folder_indexes_with_progress()

check_and_generate_indexes_on_startup()

root.mainloop()