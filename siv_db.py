import os
import sqlite3
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

# Constants
IMAGE_FOLDER = r"C:\spotbillfiles\backup\image"
JSON_FILE = r"C:\spotbillfiles\backup\meter_mapping.json"
SEARCHED_LISTS_FILE = r"C:\spotbillfiles\backup\searched_lists.json"
ADDITIONAL_FOLDERS_FILE = r"C:\spotbillfiles\backup\additional_folders.json"
DB_FILE = os.path.join(os.path.dirname(IMAGE_FOLDER), "spot_images.db")

# Global Variables
img_tk = None
img = None
img_original = None
zoom_scale = 1.0
additional_folders = []
last_online_folders = set()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consumer_id TEXT,
            meter_number TEXT,
            mru TEXT,
            date TEXT,
            image_path TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_consumer_id ON images (consumer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_meter_number ON images (meter_number)")
    conn.commit()
    conn.close()

def index_folder_to_db(folder):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for filename in os.listdir(folder):
        if len(filename) < 23:
            continue
        date = filename[:8]
        mru = filename[8:16]
        consumer_id = filename[16:25]
        full_path = os.path.join(folder, filename)
        meter_number = get_meter_number(consumer_id)
        c.execute("SELECT 1 FROM images WHERE consumer_id=? AND date=? AND image_path=?", (consumer_id, date, full_path))
        if not c.fetchone():
            c.execute(
                "INSERT INTO images (consumer_id, meter_number, mru, date, image_path) VALUES (?, ?, ?, ?, ?)",
                (consumer_id, meter_number, mru, date, full_path)
            )
    conn.commit()
    conn.close()

def generate_images_txt(folder, txt_file):
    with open(txt_file, "w", encoding="utf-8") as f:
        for filename in os.listdir(folder):
            if len(filename) >= 23:
                f.write(f"{folder}|{filename}\n")

def batch_insert_images_from_txt(txt_file):
    records = []
    with open(txt_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "|" not in line:
                continue
            folder, filename = line.split("|", 1)
            if len(filename) < 23:
                continue
            date = filename[:8]
            mru = filename[8:16]
            consumer_id = filename[16:25]
            full_path = os.path.join(folder, filename)
            meter_number = get_meter_number(consumer_id)
            records.append((consumer_id, meter_number, mru, date, full_path))
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM images")
    c.executemany(
        "INSERT INTO images (consumer_id, meter_number, mru, date, image_path) VALUES (?, ?, ?, ?, ?)",
        records
    )
    conn.commit()
    conn.close()


def index_all_folders_to_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM images")
    conn.commit()
    conn.close()
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    for folder in folders:
        index_folder_to_db(folder)
    messagebox.showinfo("Success", "Images indexed into database!")
    update_image_count()

def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%d%m%Y").strftime("%d-%b-%Y")
    except Exception:
        return date_str

def search_consumer():
    consumer_id = entry_consumer_id.get().strip()
    listbox_dates.delete(0, tk.END)
    label_consumer_details.config(text="")
    label_total_images.config(text="")
    show_latest_previews(consumer_id)

    if not consumer_id.isdigit() or len(consumer_id) != 9:
        messagebox.showwarning("Invalid Input", "Consumer ID must be a 9-digit number.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT mru, meter_number FROM images WHERE consumer_id=? LIMIT 1", (consumer_id,))
    row = c.fetchone()
    if not row:
        label_consumer_details.config(text="No images found for this Consumer ID!", foreground="red")
        label_total_images.config(text="")
        conn.close()
        return

    mru_code, meter_number = row
    meter_text = f"\nMeter Number: {meter_number}" if meter_number else ""
    label_consumer_details.config(text=f"Consumer ID: {consumer_id}\nMRU: {mru_code}{meter_text}")

    c.execute("SELECT DISTINCT date FROM images WHERE consumer_id=? ORDER BY date DESC", (consumer_id,))
    dates = [r[0] for r in c.fetchall()]
    label_total_images.config(text=f"Total Images Found: {len(dates)}")
    for date in dates:
        listbox_dates.insert(tk.END, format_date(date))
    conn.close()

    searched_lists = load_searched_lists()
    if consumer_id not in searched_lists["consumer_ids"]:
        searched_lists["consumer_ids"].append(consumer_id)
        save_searched_lists(searched_lists)

def search_meter():
    meter_number = entry_meter_number.get().strip().lower()
    if not meter_number:
        messagebox.showwarning("Invalid Input", "Please enter a meter number.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT consumer_id FROM images WHERE meter_number=? LIMIT 1", (meter_number,))
    row = c.fetchone()
    conn.close()
    if not row:
        messagebox.showinfo("Not Found", f"No consumer ID found for meter number: {meter_number}")
        return
    consumer_id = row[0]
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
        df[0] = df[0].astype(str).str.strip()
        df[1] = df[1].astype(str).str.strip()
        meter_mapping = {row[0]: {"meter_no": row[1]} for _, row in df.iterrows()}
        with open(JSON_FILE, "w") as file:
            json.dump(meter_mapping, file, indent=4)
        # Update meter numbers in DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for consumer_id, data in meter_mapping.items():
            meter_no = data["meter_no"]
            c.execute("UPDATE images SET meter_number=? WHERE consumer_id=?", (meter_no, consumer_id))
        conn.commit()
        conn.close()
        messagebox.showinfo("Success", "Meter list updated successfully!")
        entry_meter_number.config(state=tk.NORMAL)
        btn_search_meter.config(text="Search Meter", command=search_meter)
    except Exception as e:
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
        "Spot Image Viewer (DB Version)\n\n"
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
        "Version: 4.1.0\n"
    )
    messagebox.showinfo("About", about_text)

def open_documentation():
    pdf_path = os.path.join(os.path.dirname(IMAGE_FOLDER), "help.pdf")
    if os.path.exists(pdf_path):
        try:
            os.startfile(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open the PDF file: {e}")
    else:
        messagebox.showerror("Error", "The help documentation file (help.pdf) was not found!")

def update_image_count():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM images")
    count = c.fetchone()[0]
    conn.close()
    label_image_count.config(text=f"Total Images in Database: {count}")

def display_image(event):
    for frame in preview_frames:
        frame.pack_forget()
    global img_tk, img, img_original
    selected_date_index = listbox_dates.curselection()
    if not selected_date_index:
        return
    selected_date = listbox_dates.get(selected_date_index)
    consumer_id = entry_consumer_id.get().strip()
    date_str = selected_date.replace("-", "")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT image_path FROM images WHERE consumer_id=? AND date=? LIMIT 1", (consumer_id, date_str))
    row = c.fetchone()
    conn.close()
    if row:
        image_path = row[0]
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
    if not consumer_id:
        messagebox.showwarning("Warning", "Please search and select a valid Consumer ID first.")
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT date, image_path FROM images WHERE consumer_id=?", (consumer_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        messagebox.showwarning("Warning", "No images found for this Consumer ID.")
        return
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    consumer_dir = os.path.join(downloads_dir, consumer_id)
    os.makedirs(consumer_dir, exist_ok=True)
    saved = 0
    for date, image_path in rows:
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

def hide_buttons():
    btn_zoom_in.pack_forget()
    btn_zoom_out.pack_forget()
    btn_print.pack_forget()
    btn_save.pack_forget()
    btn_save_multiple.pack_forget()

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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT date, image_path FROM images WHERE consumer_id=? ORDER BY date DESC LIMIT 3", (consumer_id,))
    previews = c.fetchall()
    conn.close()
    preview_dates = []
    for i, (date, path) in enumerate(previews):
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
    for j in range(len(previews), 3):
        preview_frames[j].pack_forget()
        preview_canvases[j].unbind("<Button-1>")

def open_preview_image(consumer_id, date):
    for frame in preview_frames:
        frame.pack_forget()
    global img_tk, img, img_original, zoom_scale
    zoom_scale = 1.0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT image_path FROM images WHERE consumer_id=? AND date=? LIMIT 1", (consumer_id, date))
    row = c.fetchone()
    conn.close()
    if row:
        image_path = row[0]
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
            index_folder_to_db(folder)
            root.after(0, update_image_count)
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
    for folder in additional_folders:
        status = check_folder_status(folder)
        color = "green" if status else "red"
        folder_listbox.insert(tk.END, folder)
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
        update_image_count()
    folder_status_pane.after(3000, refresh_folder_status)

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

def check_and_index_on_startup():
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        messagebox.showinfo("Welcome", "Greetings!!\nNo image database found. The app will now index all images. This may take a while.")
        show_progress_bar()
        progress_time_label.config(text="Indexing images, please wait...")
        root.update()
        def do_indexing():
            index_all_folders_to_db()
            root.after(0, hide_progress_bar)
        threading.Thread(target=do_indexing, daemon=True).start()
    else:
        update_image_count()


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
label_image_count.pack()

progress_var = tb.DoubleVar()
progress_bar = ttk.Progressbar(
    label_image_count_frame,
    variable=progress_var,
    length=250,
    mode="indeterminate",
    style="success.Horizontal.TProgressbar"
)
progress_time_label = tb.Label(label_image_count_frame, text="", font=("Arial", 12, "italic"), bootstyle="secondary")

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

# Right pane (image display)
frame_right = tb.Frame(main_frame, padding=10, relief="ridge", borderwidth=2)
frame_right.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

canvas = tk.Canvas(frame_right, bg="#f8f9fa")
canvas.pack(fill=BOTH, expand=True)

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

btn_zoom_out = tb.Button(button_frame, text="-", command=zoom_out, bootstyle="secondary-outline")
btn_zoom_in = tb.Button(button_frame, text="+", command=zoom_in, bootstyle="secondary-outline")
btn_print = tb.Button(button_frame, text="Print", command=print_image, bootstyle="info-outline")
btn_save = tb.Button(button_frame, text="Save", command=save_image, bootstyle="success-outline")
btn_save_multiple = tb.Button(button_frame, text="Save All", command=save_multiple_images, bootstyle="success-outline")

hide_buttons()

# Far right pane for folder management
folder_status_pane = tb.Frame(main_frame, width=250, padding=10, relief="ridge", borderwidth=2)
folder_status_pane.pack(side=RIGHT, fill=Y, padx=10, pady=10)

folder_title = tb.Label(folder_status_pane, text="Network Folders", font=("Arial", 13, "bold"), bootstyle="info")
folder_title.pack(pady=(0, 10))

folder_listbox = tk.Listbox(folder_status_pane, font=("Arial", 12), height=20, width=32)
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

# Menu Bar
menu_bar = Menu(root)
root.config(menu=menu_bar)
file_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Update Consumer List", command=update_meter_list)
file_menu.add_command(label="Reload Images", command=index_all_folders_to_db)
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

init_db()  # <-- Ensure the DB and table exist before anything else

load_additional_folders()
update_folder_list()
refresh_folder_status()

if os.path.exists(JSON_FILE):
    entry_meter_number.config(state=tk.NORMAL)
    btn_search_meter.config(text="Search Meter", command=search_meter)

entry_consumer_id.bind("<space>", lambda e: show_searched_lists(e, entry_consumer_id, "consumer_ids"))
entry_meter_number.bind("<space>", lambda e: show_searched_lists(e, entry_meter_number, "meter_numbers"))

check_and_index_on_startup()
root.mainloop()