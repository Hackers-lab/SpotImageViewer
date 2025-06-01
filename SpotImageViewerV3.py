import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu, Toplevel, Listbox
from PIL import Image, ImageTk
from datetime import datetime
import subprocess
import json
import pandas as pd
import pickle

# Constants
IMAGE_FOLDER = r"C:\spotbillfiles\backup\image"
TXT_FILE = r"C:\spotbillfiles\backup\images.txt"
JSON_FILE = r"C:\spotbillfiles\backup\meter_mapping.json"
SEARCHED_LISTS_FILE = r"C:\spotbillfiles\backup\searched_lists.json"
PICKLE_FILE = r"C:\spotbillfiles\backup\image_index.pkl"

# Global Variables
image_index = {}  # Stores the image index
meter_mapping = {}  # Stores the meter mapping (con_id -> meter_no)
img_tk = None  # Stores the displayed image
img = None  # Stores the original image
img_original = None  # Stores the original image for zooming

# Zoom scale
zoom_scale = 1.0  # Track zoom level


# Function to generate images.txt using the batch command and update pickle
def generate_images_txt():
    try:
        command = f'dir "{IMAGE_FOLDER}" /b > "{TXT_FILE}"'
        subprocess.run(command, shell=True, check=True)
        messagebox.showinfo("Success", "Images loaded successfully!")
        reload_image_index(save_pickle=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to load images: {e}")


# Save image index to pickle
def save_image_index_pickle(index):
    with open(PICKLE_FILE, "wb") as f:
        pickle.dump(index, f)


# Load image index from pickle
def load_image_index_pickle():
    if os.path.exists(PICKLE_FILE):
        with open(PICKLE_FILE, "rb") as f:
            return pickle.load(f)
    return None


# Load image index from the text file
def load_image_index():
    global image_index
    image_index = {}
    try:
        with open(TXT_FILE, "r") as file:
            for line in file:
                filename = line.strip()
                if len(filename) < 23:  # Ensure the filename has the correct format
                    continue
                date = filename[:8]  # Extract date (DDMMYYYY)
                mru = filename[8:16]  # Extract MRU code
                consumer_id = filename[16:25]  # Extract Consumer ID

                if consumer_id not in image_index:
                    image_index[consumer_id] = {"MRU": mru, "images": {}}

                if date not in image_index[consumer_id]["images"]:
                    image_index[consumer_id]["images"][date] = []

                image_index[consumer_id]["images"][date].append(os.path.join(IMAGE_FOLDER, filename))
    except FileNotFoundError:
        messagebox.showinfo("Welcome", "Greetings!!\nAt first we will load existing images!!\nPress OK to continue...")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while loading the image index: {e}")
    return image_index


# Reload the image index and update the GUI, using pickle if available
def reload_image_index(save_pickle=False):
    global image_index
    if not save_pickle:
        index = load_image_index_pickle()
        if index is not None:
            image_index = index
            update_image_count()
            return
    image_index = load_image_index()
    if save_pickle:
        save_image_index_pickle(image_index)
    update_image_count()


# Format date to a readable format (DD-MMM-YYYY)
def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%d%m%Y").strftime("%d-%b-%Y")
    except ValueError:
        return date_str


# Search for a Consumer ID
def search_consumer():
    consumer_id = entry_consumer_id.get().strip()
    listbox_dates.delete(0, tk.END)
    label_consumer_details.config(text="")
    label_total_images.config(text="")
    #canvas.delete("all")
    #hide_buttons()  # Hide buttons when no image is displayed
    show_latest_previews(consumer_id)

    if not consumer_id.isdigit() or len(consumer_id) != 9:
        messagebox.showwarning("Invalid Input", "Consumer ID must be a 9-digit number.")
        return

    if consumer_id in image_index:
        consumer_data = image_index[consumer_id]
        mru_code = consumer_data["MRU"]
        images_data = consumer_data["images"]

        if not images_data:  # No images found for this Consumer ID
            label_consumer_details.config(text=f"Consumer ID: {consumer_id}\nMRU: {mru_code}")
            label_total_images.config(text="No images found for this Consumer ID!", foreground="red")
            return

        # Sort dates in descending order
        sorted_dates = sorted(images_data.keys(), key=lambda x: datetime.strptime(x, "%d%m%Y"), reverse=True)

        # Display meter number if available
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

    # Update searched consumer IDs
    searched_lists = load_searched_lists()
    if consumer_id not in searched_lists["consumer_ids"]:
        searched_lists["consumer_ids"].append(consumer_id)
        save_searched_lists(searched_lists)


# Search for a Meter Number (Case Insensitive)
def search_meter():
    meter_number = entry_meter_number.get().strip().lower()  # Convert to lowercase for case insensitivity
    if not meter_number:
        messagebox.showwarning("Invalid Input", "Please enter a meter number.")
        return

    # Look up the consumer ID from the JSON file
    consumer_id = get_consumer_id(meter_number)
    if not consumer_id:
        messagebox.showinfo("Not Found", f"No consumer ID found for meter number: {meter_number}")
        return

    # Set the consumer ID in the search box and trigger the search
    entry_consumer_id.delete(0, tk.END)
    entry_consumer_id.insert(0, consumer_id)
    search_consumer()

    # Update searched meter numbers
    searched_lists = load_searched_lists()
    if meter_number not in searched_lists["meter_numbers"]:
        searched_lists["meter_numbers"].append(meter_number)
        save_searched_lists(searched_lists)


# Get meter number from consumer ID
def get_meter_number(consumer_id):
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as file:
            meter_mapping = json.load(file)
            return meter_mapping.get(consumer_id, {}).get("meter_no")
    return None


# Get consumer ID from meter number (Case Insensitive)
def get_consumer_id(meter_number):
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as file:
            meter_mapping = json.load(file)
            for con_id, data in meter_mapping.items():
                if data.get("meter_no", "").lower() == meter_number.lower():  # Case insensitive comparison
                    return con_id
    return None


# Update the meter mapping list from an Excel file
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
        
        # Read the Excel file (assuming Column A is Consumer ID and Column B is Meter Number)
        df = pd.read_excel(file_path, header=None, usecols=[0, 1], dtype={0: str, 1: str})
        progress_window.destroy()

        progress_window = show_progress("Processing meter numbers...")
        # Convert both columns to strings and strip trailing spaces
        df[0] = df[0].astype(str).str.strip()  # Consumer ID
        df[1] = df[1].astype(str).str.strip()  # Meter Number
        progress_window.destroy()

        progress_window = show_progress("Creating meter mapping...")
        # Create a dictionary for meter mapping
        global meter_mapping
        meter_mapping = {
            row[0]: {"meter_no": row[1]}  # row[0] = Consumer ID, row[1] = Meter Number
            for _, row in df.iterrows()
        }
        progress_window.destroy()

        progress_window = show_progress("Saving meter mapping to JSON file...")
        # Save the mapping to a JSON file
        with open(JSON_FILE, "w") as file:
            json.dump(meter_mapping, file, indent=4)  # Use indent for pretty-printing
        progress_window.destroy()

        messagebox.showinfo("Success", "Meter list updated successfully!")
        entry_meter_number.config(state=tk.NORMAL)  # Enable the meter number input box
        btn_search_meter.config(text="Search Meter", command=search_meter)
    except Exception as e:
        progress_window.destroy()
        messagebox.showerror("Error", f"Failed to update meter list: {e}")


# Clear the search and reset the display
def refresh_search():
    entry_consumer_id.delete(0, tk.END)
    entry_meter_number.delete(0, tk.END)
    listbox_dates.delete(0, tk.END)
    label_consumer_details.config(text="")
    label_total_images.config(text="")
    canvas.delete("all")
    hide_buttons()  # Hide buttons when no image is displayed
    # Hide preview images
    for frame in preview_frames:
        frame.pack_forget()


# Show About information
def show_about():
    about_text = (
        "Consumer Image Viewer\n\n"
        "This application allows you to:\n"
        "1. Search for consumer images using Consumer ID or Meter Number.\n"
        "2. View images sorted by date in descending order.\n"
        "3. Zoom in and out of images for better visibility.\n"
        "4. Print images directly from the application.\n"
        "5. Update the meter list by importing an Excel file with Consumer IDs and Meter Numbers.\n"
        "6. Maintain a history of searched Consumer IDs and Meter Numbers for quick access.\n\n"
        "Developed By: Pramod Verma\n"
        "ERP ID: 90018747\n\n"
        "Version: 2.2.3"
    )
    messagebox.showinfo("About", about_text)


# Add this function to open the PDF file using os.startfile
def open_documentation():
    pdf_path = os.path.join(os.path.dirname(TXT_FILE), "help.pdf")  # Path to the PDF file
    if os.path.exists(pdf_path):
        try:
            # Open the PDF file using the default application on Windows
            os.startfile(pdf_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open the PDF file: {e}")
    else:
        messagebox.showerror("Error", "The help documentation file (help.pdf) was not found!")


# Update the total image count label
def update_image_count():
    total_images = sum(
        len(images)
        for consumer_data in image_index.values()
        for images in consumer_data["images"].values()
    )
    label_image_count.config(text=f"Total Images in Database: {total_images}")


# Function to display the selected image
def display_image(event):
    # Hide previews
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
                image_path = images_data[date][0]
                try:
                    img_original = Image.open(image_path)  # Store original
                    img = img_original.copy()
                    img.thumbnail((canvas.winfo_width(), canvas.winfo_height()), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(img)

                    canvas.delete("all")
                    canvas.image = img_tk  # Keep a reference to avoid garbage collection
                    canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)
                    show_buttons()  # Show buttons when an image is displayed
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load image: {e}")
                break


# Zoom In functionality
def zoom_in():
    global img_tk, img, zoom_scale, img_original
    if img_original:
        zoom_scale *= 1.2
        new_size = (int(img_original.width * zoom_scale), int(img_original.height * zoom_scale))
        img = img_original.resize(new_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)


# Zoom Out functionality
def zoom_out():
    global img_tk, img, zoom_scale, img_original
    if img_original:
        zoom_scale *= 0.8
        new_size = (int(img_original.width * zoom_scale), int(img_original.height * zoom_scale))
        img = img_original.resize(new_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        canvas.delete("all")
        canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)


# Print functionality
def print_image():
    if img:
        temp_file = "temp_image.png"
        img.save(temp_file)  # Save the image temporarily
        os.startfile(temp_file, "print")  # Open the image in the default viewer and print


# Save functionality
def save_image():
    if img:
        filetypes = [("PNG files", "*.png"), ("JPEG files", "*.jpg;*.jpeg"), ("All files", "*.*")]
        save_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=filetypes)
        if save_path:
            try:
                img.save(save_path)
                messagebox.showinfo("Success", f"Image saved to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")


# Show buttons when an image is displayed
def show_buttons():
    btn_zoom_out.pack(side=tk.LEFT, padx=5)
    btn_zoom_in.pack(side=tk.LEFT, padx=5)
    btn_print.pack(side=tk.LEFT, padx=5)
    btn_save.pack(side=tk.LEFT, padx=5)  # <-- Add this line


# Hide buttons when no image is displayed
def hide_buttons():
    btn_zoom_in.pack_forget()
    btn_zoom_out.pack_forget()
    btn_print.pack_forget()
    btn_save.pack_forget()  # <-- Add this line


# Load searched lists from file
def load_searched_lists():
    if os.path.exists(SEARCHED_LISTS_FILE):
        with open(SEARCHED_LISTS_FILE, "r") as file:
            return json.load(file)
    return {"consumer_ids": [], "meter_numbers": []}


# Save searched lists to file
def save_searched_lists(searched_lists):
    with open(SEARCHED_LISTS_FILE, "w") as file:
        json.dump(searched_lists, file, indent=4)


# Function to show searched lists in a dropdown
def show_searched_lists(event, entry_widget, list_type):
    searched_lists = load_searched_lists()
    lists = searched_lists[list_type][-8:]  # Show only the last 8 items

    if not lists:
        return

    # Create a dropdown list
    dropdown = Toplevel()
    dropdown.geometry(f"+{entry_widget.winfo_rootx()}+{entry_widget.winfo_rooty() + entry_widget.winfo_height()}")
    dropdown.overrideredirect(True)  # Remove window decorations

    listbox = Listbox(dropdown, font=("Arial", 12), width=entry_widget.winfo_width() // 9)
    listbox.pack()

    for item in lists:
        listbox.insert(tk.END, item)

    # Bind selection to the entry widget
    def select_item(event):
        selected_item = listbox.get(listbox.curselection())
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, selected_item)
        dropdown.destroy()

    listbox.bind("<Double-Button-1>", select_item)
    listbox.bind("<Return>", select_item)


# Function to show progress in a dialogue box
def show_progress(message):
    progress_window = Toplevel()
    progress_window.title("Progress")
    label = ttk.Label(progress_window, text=message, font=("Arial", 12))
    label.pack(padx=20, pady=20)
    progress_window.update()  # Update the window to show the message
    return progress_window

def show_latest_previews(consumer_id):
    # Hide main image and buttons
    canvas.delete("all")
    hide_buttons()
    # Remove any previous previews
    for frame in preview_frames:
        frame.pack_forget()
    # If not found, do nothing
    if consumer_id not in image_index:
        return
    images_data = image_index[consumer_id]["images"]
    all_images = []
    for date, paths in images_data.items():
        for path in paths:
            all_images.append((date, path))
    all_images.sort(key=lambda x: datetime.strptime(x[0], "%d%m%Y"), reverse=True)
    # Store the date for each preview so we can use it in the click handler
    preview_dates = []
    for i, (date, path) in enumerate(all_images[:5]):
        try:
            img = Image.open(path)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img)
            preview_canvases[i].delete("all")
            preview_canvases[i].create_image(110, 110, anchor=tk.CENTER, image=img_tk)
            preview_canvases[i].image = img_tk  # Keep reference
            preview_labels[i].config(text=format_date(date))
            preview_frames[i].pack(side=tk.LEFT, padx=10, pady=10, in_=frame_right)
            preview_dates.append(date)
            # Remove previous bindings to avoid stacking
            preview_canvases[i].unbind("<Button-1>")
            # Bind click event to open the image as if selected from date pane
            def make_onclick(idx):
                return lambda event: open_preview_image(consumer_id, preview_dates[idx])
            preview_canvases[i].bind("<Button-1>", make_onclick(i))
        except Exception as e:
            preview_labels[i].config(text="Error")
            preview_canvases[i].delete("all")
            preview_frames[i].pack(side=tk.LEFT, padx=10, pady=10, in_=frame_right)
            preview_canvases[i].unbind("<Button-1>")
    # Hide unused previews
    for j in range(len(all_images), 5):
        preview_frames[j].pack_forget()
        preview_canvases[j].unbind("<Button-1>")

def open_preview_image(consumer_id, date):
    # Hide previews
    for frame in preview_frames:
        frame.pack_forget()
    global img_tk, img, img_original, zoom_scale
    zoom_scale = 1.0
    if consumer_id in image_index:
        images_data = image_index[consumer_id]["images"]
        if date in images_data:
            image_path = images_data[date][0]
            try:
                img_original = Image.open(image_path)  # Store original
                img = img_original.copy()
                img.thumbnail((canvas.winfo_width(), canvas.winfo_height()), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                canvas.delete("all")
                canvas.image = img_tk  # Keep a reference to avoid garbage collection
                canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, anchor=tk.CENTER, image=img_tk)
                show_buttons()  # Show buttons when an image is displayed
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")

# Initialize the GUI
root = tk.Tk()
root.title("Spot Image Viewer")
root.geometry("1200x800")
root.state("zoomed")

# Configure styles
style = ttk.Style()
style.configure("TButton", font=("Arial", 10), padding=5)  # Reduced font size for buttons
style.configure("TLabel", font=("Arial", 12))
style.configure("TEntry", font=("Arial", 12))

# Top Frame (Search Bar)
frame_top = ttk.Frame(root)
frame_top.pack(fill=tk.X, padx=10, pady=10)

# Consumer ID Search
label_consumer_id = ttk.Label(frame_top, text="Enter Consumer ID:")
label_consumer_id.pack(side=tk.LEFT, padx=5)

entry_consumer_id = ttk.Entry(frame_top, width=20)
entry_consumer_id.pack(side=tk.LEFT, padx=5)
entry_consumer_id.bind("<Return>", lambda event: search_consumer())  # Bind Enter key

btn_search = ttk.Button(frame_top, text="Search", command=search_consumer)
btn_search.pack(side=tk.LEFT, padx=5)

# Meter Number Search
label_meter_number = ttk.Label(frame_top, text="Enter Meter Number:")
label_meter_number.pack(side=tk.LEFT, padx=5)

entry_meter_number = ttk.Entry(frame_top, width=20, state=tk.DISABLED)
entry_meter_number.pack(side=tk.LEFT, padx=5)
entry_meter_number.bind("<Return>", lambda event: search_meter())  # Bind Enter key

btn_search_meter = ttk.Button(frame_top, text="Update List", command=update_meter_list)
btn_search_meter.pack(side=tk.LEFT, padx=5)

# Refresh Button
btn_refresh = ttk.Button(frame_top, text="Refresh", command=refresh_search)
btn_refresh.pack(side=tk.LEFT, padx=5)

# Total Image Count Label
label_image_count = ttk.Label(frame_top, text="Total Images: 0", font=("Arial", 12), foreground="green")
label_image_count.pack(side=tk.LEFT, padx=5)

# Menu Bar
menu_bar = Menu(root)
root.config(menu=menu_bar)

# File Menu
file_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Update Consumer List", command=update_meter_list)
file_menu.add_command(label="Reload Images", command=generate_images_txt)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Help Menu
help_menu = Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="Documentation", command=open_documentation)  
help_menu.add_command(label="About", command=show_about)

# Main Frame (Split into Left and Right Panes)
main_frame = ttk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

# Left Pane (Dates List)
frame_left = ttk.Frame(main_frame, width=200)
frame_left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

label_consumer_details = ttk.Label(frame_left, text="", wraplength=180, foreground="green")
label_consumer_details.pack(pady=5)

label_total_images = ttk.Label(frame_left, text="", wraplength=180)
label_total_images.pack(pady=5)

label_dates = ttk.Label(frame_left, text="Available Dates:")
label_dates.pack()

listbox_dates = tk.Listbox(frame_left, font=("Arial", 12), height=20)
listbox_dates.pack(fill=tk.BOTH, expand=True)
listbox_dates.bind("<<ListboxSelect>>", display_image)

# Right Pane (Image Display)
frame_right = ttk.Frame(main_frame)
frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

canvas = tk.Canvas(frame_right, bg="white")
canvas.pack(fill=tk.BOTH, expand=True)

# Preview canvases and labels for 5 latest images
preview_frames = []
preview_canvases = []
preview_labels = []
for i in range(5):  # Change 3 to 5
    frame = ttk.Frame(frame_right)
    canvas_preview = tk.Canvas(frame, width=220, height=220, bg="white", highlightthickness=1, highlightbackground="gray")
    label = ttk.Label(frame, text="", font=("Arial", 10))
    canvas_preview.pack()
    label.pack()
    preview_frames.append(frame)
    preview_canvases.append(canvas_preview)
    preview_labels.append(label)

# Add buttons for zoom in, zoom out, print, and save
button_frame = ttk.Frame(frame_right)
button_frame.pack(pady=10)

btn_zoom_out = ttk.Button(button_frame, text="-", command=zoom_out)
btn_zoom_in = ttk.Button(button_frame, text="+", command=zoom_in)
btn_print = ttk.Button(button_frame, text="Print", command=print_image)
btn_save = ttk.Button(button_frame, text="Save", command=save_image)  # <-- Add this line

# Hide buttons initially
hide_buttons()

# Load the image index
reload_image_index()

# Check if images.txt exists, if not, generate it
if not os.path.exists(TXT_FILE):
    generate_images_txt()

# Check if meter_mapping.json exists and enable the meter number input box
if os.path.exists(JSON_FILE):
    entry_meter_number.config(state=tk.NORMAL)
    btn_search_meter.config(text="Search Meter", command=search_meter)

# Bind spacebar to show searched lists
entry_consumer_id.bind("<space>", lambda e: show_searched_lists(e, entry_consumer_id, "consumer_ids"))
entry_meter_number.bind("<space>", lambda e: show_searched_lists(e, entry_meter_number, "meter_numbers"))

# Start the application
root.mainloop()

