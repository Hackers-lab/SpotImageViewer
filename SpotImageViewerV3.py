import os
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import messagebox, filedialog, Menu, Toplevel, Listbox, ttk
from PIL import Image, ImageTk
from datetime import datetime, timedelta
import subprocess
import json
import pandas as pd
import pickle
import threading
import hashlib
import shutil
import time

# Constants
IMAGE_FOLDER = r"C:\spotbillfiles\backup\image"
TXT_FILE = r"C:\spotbillfiles\backup\images.txt"
JSON_FILE = r"C:\spotbillfiles\backup\meter_mapping.json"
SEARCHED_LISTS_FILE = r"C:\spotbillfiles\backup\searched_lists.json"
PICKLE_FILE = r"C:\spotbillfiles\backup\image_index.pkl"
ADDITIONAL_FOLDERS_FILE = r"C:\spotbillfiles\backup\additional_folders.json"

# Global Variables
image_index = {}
meter_mapping = {}
img_tk = None
img = None
img_original = None
zoom_scale = 1.0
additional_folders = []
last_online_folders = set()


def generate_images_txt():
    """
    Generate images.txt for all online folders (default + additional).
    Each folder gets its own TXT file with a unique name.
    """
    # Always include the default folder first
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    txt_files = []

    for folder in folders:
        # Create a unique filename for each folder's txt file
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        txt_file = os.path.join(os.path.dirname(TXT_FILE), f"images_{folder_hash}.txt")
        txt_files.append(txt_file)
        try:
            command = f'dir "{folder}" /b > "{txt_file}"'
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to load images from {folder}: {e}")

    # Merge all txt files into the main TXT_FILE (default folder first, then others)
    with open(TXT_FILE, "w") as outfile:
        for folder, txt_file in zip(folders, txt_files):
            with open(txt_file, "r") as infile:
                for line in infile:
                    outfile.write(f"{os.path.abspath(folder)}|{line.strip()}\n")

    messagebox.showinfo("Success", "Images loaded successfully from all online folders!")
    reload_image_index(save_pickle=True)

def save_image_index_pickle(index):
    with open(PICKLE_FILE, "wb") as f:
        pickle.dump(index, f)

def load_image_index_pickle():
    if os.path.exists(PICKLE_FILE):
        with open(PICKLE_FILE, "rb") as f:
            return pickle.load(f)
    return None

def load_image_index():
    """
    Load image index from TXT_FILE, supporting multiple folders.
    Only images from online folders are included.
    """
    global image_index
    image_index = {}
    try:
        with open(TXT_FILE, "r") as file:
            for line in file:
                line = line.strip()
                if "|" in line:
                    folder_path, filename = line.split("|", 1)
                else:
                    # For backward compatibility, assume default folder
                    folder_path, filename = IMAGE_FOLDER, line

                # Only process if folder is online
                if not check_folder_status(folder_path):
                    continue

                if len(filename) < 23:
                    continue
                date = filename[:8]
                mru = filename[8:16]
                consumer_id = filename[16:25]
                full_path = os.path.join(folder_path, filename)
                # Priority: default folder images overwrite others
                if consumer_id not in image_index:
                    image_index[consumer_id] = {"MRU": mru, "images": {}}
                if date not in image_index[consumer_id]["images"]:
                    image_index[consumer_id]["images"][date] = []
                # Only add if not already present (avoid duplicates)
                if full_path not in image_index[consumer_id]["images"][date]:
                    image_index[consumer_id]["images"][date].append(full_path)
    except FileNotFoundError:
        messagebox.showinfo("Welcome", "Greetings!!\nAt first we will load existing images!!\nPress OK to continue...")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while loading the image index: {e}")
    return image_index

def reload_image_index(save_pickle=False):
    load_all_folder_indexes()
    #update_image_count()

def reload_image_index_no_ui(save_pickle=False):
    load_all_folder_indexes()
    # Do NOT call update_image_count() here

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
        "Version: 4.1.0\n"
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
    """Run reload_image_index in a background thread and update UI when done."""
    def worker():
        t0 = time.time()
        reload_image_index_no_ui()
        t1 = time.time()
        print(f"[Startup] reload_image_index (background): {t1-t0:.2f} seconds")
        # Schedule UI update on main thread
        root.after(0, update_image_count)
    threading.Thread(target=worker, daemon=True).start()

def update_image_count():
    """
    Update the total image count label using the same logic as debug_show_index_counts,
    so the displayed count always matches the merged/app total.
    """
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
                # Prefer default folder image if present
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
    """
    Save the currently displayed image in a folder named after the consumer ID,
    with the filename as the date, inside the user's Downloads directory.
    """
    if img_original:
        consumer_id = entry_consumer_id.get().strip()
        selected_date_index = listbox_dates.curselection()
        if not consumer_id or not selected_date_index:
            messagebox.showwarning("Warning", "Please select a consumer and a date.")
            return
        selected_date = listbox_dates.get(selected_date_index)
        # Format date for filename
        date_str = selected_date.replace("-", "")
        # Downloads path
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
    """
    Save all images for the current consumer ID in the Downloads/consumer_id folder,
    with filenames as their dates.
    """
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
        # Prefer default folder image if present
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
        # Get the index under the mouse pointer for single click
        index = listbox.nearest(event.y)
        if index < 0 or index >= listbox.size():
            return
        selected_item = listbox.get(index)
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, selected_item)
        dropdown.destroy()
        # Trigger search and show image
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
        # Prefer default folder image if present
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
            # Prefer default folder image if present
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
            root.after(0, reload_image_index)  # Ensure UI update on main thread
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
    # Refresh status colors in the listbox
    for idx, folder in enumerate(additional_folders):
        status = check_folder_status(folder)
        color = "green" if status else "red"
        folder_listbox.itemconfig(idx, foreground=color)
    # Check if online folders have changed
    current_online = set([IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)])
    if current_online != last_online_folders:
        last_online_folders = current_online
        reload_image_index()  # This will also update image count
    # Schedule next check
    folder_status_pane.after(3000, refresh_folder_status)

def generate_folder_index(folder):
    """
    Generate a pickle index for a single folder.
    """
    folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
    index_file = os.path.join(os.path.dirname(TXT_FILE), f"index_{folder_hash}.pkl")
    index = {}
    try:
        for filename in os.listdir(folder):
            if len(filename) < 23:
                continue
            date = filename[:8]
            mru = filename[8:16]
            consumer_id = filename[16:25]
            full_path = os.path.join(folder, filename)
            if consumer_id not in index:
                index[consumer_id] = {"MRU": mru, "images": {}}
            if date not in index[consumer_id]["images"]:
                index[consumer_id]["images"][date] = []
            index[consumer_id]["images"][date].append(full_path)
        with open(index_file, "wb") as f:
            pickle.dump(index, f)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to index images in {folder}: {e}")

def show_indexing_progress():
    progress_window = Toplevel()
    progress_window.title("Indexing Images")
    label = tb.Label(progress_window, text="Indexing images, please wait...", font=("Arial", 14))
    label.pack(padx=30, pady=30)
    progress_window.update()
    # Let the window be visible for at least a short time
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
        total = sum([len(os.listdir(folder)) for folder in folders if os.path.exists(folder)])
        if total == 0:
            root.after(0, lambda: messagebox.showinfo("Info", "No images found in any folder."))
            root.after(0, hide_progress_bar)
            return
        processed = 0
        for folder in folders:
            folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
            index_file = os.path.join(os.path.dirname(TXT_FILE), f"index_{folder_hash}.pkl")
            index = {}
            try:
                files = os.listdir(folder)
                for filename in files:
                    if len(filename) < 23:
                        continue
                    date = filename[:8]
                    mru = filename[8:16]
                    consumer_id = filename[16:25]
                    full_path = os.path.join(folder, filename)
                    if consumer_id not in index:
                        index[consumer_id] = {"MRU": mru, "images": {}}
                    if date not in index[consumer_id]["images"]:
                        index[consumer_id]["images"][date] = []
                    index[consumer_id]["images"][date].append(full_path)
                    processed += 1
                    if processed % 100 == 0 or processed == total:
                        percent = (processed / total) * 100
                        root.after(0, lambda p=percent: update_progress_bar(p))
                with open(index_file, "wb") as f:
                    pickle.dump(index, f)
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

def load_all_folder_indexes():
    """
    Load and merge indexes from all online folders, giving priority to default folder.
    """
    global image_index
    image_index = {}
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    folder_indexes = []
    for folder in folders:
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        index_file = os.path.join(os.path.dirname(TXT_FILE), f"index_{folder_hash}.pkl")
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                folder_indexes.append(pickle.load(f))
    # Merge: default folder first, then others (others only add if not present)
    for idx, folder_index in enumerate(folder_indexes):
        for consumer_id, consumer_data in folder_index.items():
            if consumer_id not in image_index:
                image_index[consumer_id] = {"MRU": consumer_data["MRU"], "images": {}}
            for date, images in consumer_data["images"].items():
                if date not in image_index[consumer_id]["images"]:
                    image_index[consumer_id]["images"][date] = []
                # For default folder, insert at front; for others, append if not present
                for img_path in images:
                    if img_path not in image_index[consumer_id]["images"][date]:
                        if idx == 0:  # default folder
                            image_index[consumer_id]["images"][date].insert(0, img_path)
                        else:
                            image_index[consumer_id]["images"][date].append(img_path)

def debug_show_index_counts():
    """
    Show a popup with the image count for each folder index and the merged total.
    """
    folders = [IMAGE_FOLDER] + [f for f in additional_folders if check_folder_status(f)]
    msg_lines = []
    total_per_folder = []
    for folder in folders:
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        index_file = os.path.join(os.path.dirname(TXT_FILE), f"index_{folder_hash}.pkl")
        count = 0
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                folder_index = pickle.load(f)
                for consumer_data in folder_index.values():
                    for images in consumer_data["images"].values():
                        count += len(images)
        msg_lines.append(f"{os.path.basename(folder)}: {count} images")
        total_per_folder.append(count)
    # Now show merged total from image_index
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

btn_search_meter = tb.Button(frame_top, text="Update List", command=update_meter_list, bootstyle="info")
btn_search_meter.pack(side=LEFT, padx=5)

btn_refresh = tb.Button(frame_top, text="Refresh", command=refresh_search, bootstyle="warning")
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
    style="success.Horizontal.TProgressbar"  # You can use "info", "warning", etc.
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
file_menu.add_command(label="Reload Images", command=generate_all_folder_indexes_with_progress)  # Use per-folder index!
file_menu.add_command(label="Image Counts", command=debug_show_index_counts)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)


# Theme selector menu (Settings)
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
    font=("Arial", 11, "bold")  # Increased font size and bold
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

# New: Far right pane for folder management
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

# Enable selection with mouse click for folder_listbox
def on_folder_select(event):
    # This function can be expanded if you want to show folder details on selection
    pass

folder_listbox.bind("<<ListboxSelect>>", on_folder_select)

# Optionally, allow pressing Delete key to remove selected folder
def on_folder_delete(event):
    remove_folder()

folder_listbox.bind("<Delete>", on_folder_delete)

# Load and show folders at startup

load_additional_folders()

update_folder_list()
refresh_folder_status()
background_reload_image_index()

if os.path.exists(JSON_FILE):
    entry_meter_number.config(state=tk.NORMAL)
    btn_search_meter.config(text="Search Meter", command=search_meter)

entry_consumer_id.bind("<space>", lambda e: show_searched_lists(e, entry_consumer_id, "consumer_ids"))
entry_meter_number.bind("<space>", lambda e: show_searched_lists(e, entry_meter_number, "meter_numbers"))

def check_and_generate_indexes_on_startup():
    folders = [IMAGE_FOLDER] + additional_folders
    index_exists = False
    for folder in folders:
        folder_hash = hashlib.md5(folder.encode()).hexdigest()[:8]
        index_file = os.path.join(os.path.dirname(TXT_FILE), f"index_{folder_hash}.pkl")
        if os.path.exists(index_file):
            index_exists = True
            break
    if not index_exists:
        messagebox.showinfo("Welcome", "Greetings!!\nNo image index found. The app will now index all images. This may take a while.")
        generate_all_folder_indexes_with_progress()

check_and_generate_indexes_on_startup()



root.mainloop()

