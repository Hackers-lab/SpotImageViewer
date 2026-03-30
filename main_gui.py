from bill_calculator import BillCalculatorApp
from theft_calculator import TheftCalculatorApp
from tariff_editor import TariffEditor

import os
import shutil
import threading
import time
import csv
import json
import subprocess
import sys
import webbrowser
from datetime import datetime
import openpyxl
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import messagebox, filedialog, Menu, Toplevel, Listbox, ttk
from tkinter import CENTER, NE, NW, SW, SE, TOP, BOTTOM, LEFT, RIGHT, BOTH, X, Y, END
import ttkbootstrap as tb

import config
import database
import utils
from low_consumption import LowConsumptionVerifier
import documentation

# --- Global State Variables ---
img_tk = None
img = None
img_original = None
zoom_scale = 1.0
additional_folders = utils.load_additional_folders()
indexing_active = False
current_search_data = {}  
preview_references = [] 
preview_canvas_widgets = []

LIGHT_THEME = "cosmo"
DARK_THEME = "darkly"


def is_dark_mode_active():
    try:
        return root.style.theme_use() == DARK_THEME
    except Exception:
        return False


def refresh_non_ttk_widget_colors():
    """Update all plain-tk widget colours to match the current ttkbootstrap theme."""
    dark = is_dark_mode_active()

    if dark:
        listbox_bg   = "#2c3136"
        listbox_fg   = "#f8f9fa"
        select_bg    = "#4c6ef5"
        canvas_bg    = "#212529"
        scroller_bg  = "#2c3136"
        preview_bg   = "#2c3136"
        notes_bg     = "#3a3024"
        notes_fg     = "#f8f9fa"
        folders_bg   = "#1e3044"
        menu_bg      = "#2c3136"
        menu_fg      = "#f8f9fa"
        menu_act_bg  = "#4c6ef5"
    else:
        listbox_bg   = "#f8f9fa"
        listbox_fg   = "#212529"
        select_bg    = "#0d6efd"
        canvas_bg    = "#e9ecef"
        scroller_bg  = "#ffffff"
        preview_bg   = "#f0f0f0"
        notes_bg     = "#fff3cd"
        notes_fg     = "#212529"
        folders_bg   = "#e3f2fd"
        menu_bg      = "#f8f9fa"
        menu_fg      = "#212529"
        menu_act_bg  = "#0d6efd"

    select_fg   = "#ffffff"
    menu_act_fg = "#ffffff"

    # --- Listboxes ---
    for name, bg in [('listbox_dates', listbox_bg), ('folder_listbox', folders_bg)]:
        w = globals().get(name)
        if w:
            w.config(bg=bg, fg=listbox_fg, selectbackground=select_bg, selectforeground=select_fg)

    # --- Canvases ---
    w = globals().get('canvas')
    if w:
        w.config(bg=canvas_bg)

    w = globals().get('preview_canvas_scroller')
    if w:
        w.config(bg=scroller_bg)

    for cw in preview_canvas_widgets:
        try:
            if cw.winfo_exists():
                cw.config(bg=preview_bg)
        except Exception:
            continue

    # --- Text widget (notes) ---
    w = globals().get('txt_remarks')
    if w:
        w.config(bg=notes_bg, fg=notes_fg, insertbackground=notes_fg)

    # --- Frames that carry a fixed bootstyle ---
    frame_style = "dark" if dark else "light"
    for name in ('welcome_frame', 'top_f'):
        w = globals().get(name)
        if w:
            try:
                w.config(bootstyle=frame_style)
            except Exception:
                pass

    # --- Menu bar ---
    for name in ('mb', 'fm', 'bm', 'nm', 'vm', 'tm', 'hm'):
        w = globals().get(name)
        if w:
            try:
                w.config(bg=menu_bg, fg=menu_fg,
                         activebackground=menu_act_bg, activeforeground=menu_act_fg)
            except Exception:
                pass

    # --- Status-bar toggle buttons ---
    for btn_name, pane_name in [('btn_notes', 'notes_pane'), ('btn_folders', 'folder_pane')]:
        btn = globals().get(btn_name)
        pane = globals().get(pane_name)
        if btn and pane:
            btn.config(bootstyle=_toggle_btn_style(pane.winfo_ismapped()))


def update_theme_toggle_button_text():
    if 'btn_theme_toggle' not in globals():
        return

    if is_dark_mode_active():
        btn_theme_toggle.config(text="Light Mode", bootstyle="light-outline")
    else:
        btn_theme_toggle.config(text="Dark Mode", bootstyle="dark-outline")


def toggle_theme():
    next_theme = DARK_THEME if not is_dark_mode_active() else LIGHT_THEME
    root.style.theme_use(next_theme)
    refresh_non_ttk_widget_colors()
    update_theme_toggle_button_text()


def _toggle_btn_style(active):
    """Return the right bootstyle for status-bar toggle buttons."""
    if is_dark_mode_active():
        return "light" if active else "light-outline"
    return "dark" if active else "dark-outline"


def launch_tool(script_name, tool_title):
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        if not os.path.exists(script_path):
            messagebox.showerror("Tool Not Found", f"{tool_title} file was not found:\n{script_path}")
            return

        subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path))
    except Exception as e:
        messagebox.showerror("Launch Error", f"Could not open {tool_title}.\n\n{e}")

def add_network_folder():
    try:
        folder = filedialog.askdirectory(title="Select Network Folder")
        if folder and folder not in additional_folders:
            additional_folders.append(folder)
            utils.save_additional_folders(additional_folders)
            update_folder_list_ui() 
            run_single_check()
            if messagebox.askyesno("Index Now?", "Folder added. Scan it for images now?"):
                start_indexing_process()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def remove_network_folder():
    try:
        selection = folder_listbox.curselection()
        if selection:
            idx = selection[0]
            if idx == 0:
                messagebox.showwarning("Warning", "Cannot remove the default Image folder.")
                return
            
            folder_idx = idx - 1
            if 0 <= folder_idx < len(additional_folders):
                del additional_folders[folder_idx]
                utils.save_additional_folders(additional_folders)
                update_folder_list_ui()
                run_single_check() 
                messagebox.showinfo("Info", "Folder removed. Images remain until 'Reload Images' is clicked.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def index_images_thread(progress_callback, finish_callback):
    global indexing_active
    indexing_active = True
    
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=OFF;")

        folders = [config.IMAGE_FOLDER] + additional_folders
        batch_data = []
        BATCH_SIZE = 5000 
        total_inserted = 0

        cursor.execute("DELETE FROM images")
        cursor.execute("DELETE FROM directories") # Also clear directories
        conn.commit()
        
        start_time = time.time()

        for folder in folders:
            if not os.path.exists(folder):
                continue
            
            for root_dir, dirs, files in os.walk(folder):
                # Get the directory ID for the current root_dir
                cursor.execute("INSERT OR IGNORE INTO directories (dir_path) VALUES (?)", (root_dir,))
                cursor.execute("SELECT id FROM directories WHERE dir_path = ?", (root_dir,))
                dir_id = cursor.fetchone()[0]

                for filename in files:
                    try:
                        if len(filename) < 20: continue
                        if not filename[:8].isdigit(): continue
                        
                        date_orig = filename[:8]
                        try:
                            dt = datetime.strptime(date_orig, "%d%m%Y")
                            date_iso = dt.strftime("%Y-%m-%d")
                        except:
                            continue 

                        mru = filename[8:16]
                        cid = filename[16:25]

                        batch_data.append((cid, date_orig, date_iso, mru, filename, dir_id))

                        if len(batch_data) >= BATCH_SIZE:
                            cursor.executemany("INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)", batch_data)
                            conn.commit()
                            total_inserted += len(batch_data)
                            batch_data = []
                            elapsed = int(time.time() - start_time)
                            progress_callback(total_inserted, elapsed)
                            
                    except Exception:
                        continue

        if batch_data:
            cursor.executemany("INSERT OR IGNORE INTO images (consumer_id, date_original, date_iso, mru, filename, dir_id) VALUES (?,?,?,?,?,?)", batch_data)
            conn.commit()
            total_inserted += len(batch_data)
        
        cursor.execute("ANALYZE;") 
        
        # Optimize and compress database
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        cursor.execute("VACUUM;")
        
        conn.close()

    except Exception as e:
        print(f"Indexing error: {e}")
    finally:
        indexing_active = False
        finish_callback(total_inserted)

def add_new_note_option():
    def save_opt():
        new_opt = entry_opt.get().strip()
        if new_opt:
            utils.add_note_option(new_opt)
            # Refresh the note options in the UI
            global note_options
            note_options = utils.load_note_options()
            combo_notes['values'] = note_options
            note_var.set(new_opt)
            pop.destroy()

    pop = Toplevel()
    pop.title("Add Note Option")
    pop.geometry("300x150")
    
    tb.Label(pop, text="Enter New Option:").pack(pady=10)
    entry_opt = tb.Entry(pop)
    entry_opt.pack(pady=5, padx=10, fill=X)
    entry_opt.focus()
    entry_opt.bind("<Return>", lambda e: save_opt())
    tb.Button(pop, text="Add", command=save_opt, bootstyle="success").pack(pady=10)

def export_notes_csv():
    try:
        notes = utils.load_all_notes()
        if not notes:
            messagebox.showinfo("Info", "No notes to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV", "*.csv")],
            title="Export Notes"
        )
        if not path:
            return

        prog = Toplevel()
        prog.title("Exporting Notes")
        prog.geometry("350x100")
        tb.Label(prog, text="Exporting notes, please wait...").pack(padx=20, pady=10)
        prog.update()

        def worker(export_path, data):
            try:
                with open(export_path, "w", newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Consumer ID", "Note", "Remarks"])
                    for cid, d in data.items():
                        writer.writerow([cid, d.get('note',''), d.get('remarks','')])
                root.after(0, lambda: messagebox.showinfo("Success", f"Exported to {export_path}"))
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("Error", f"Export failed: {e}"))
            finally:
                try:
                    root.after(0, prog.destroy)
                except: pass

        threading.Thread(target=worker, args=(path, notes), daemon=True).start()

    except Exception as e:
        messagebox.showerror("Error", f"Export failed: {e}")

def perform_backup():
    def on_date_select():
        date_str = date_entry.get().strip()
        try:
            dt = datetime.strptime(date_str, "%d-%m-%Y")
            iso_limit = dt.strftime("%Y-%m-%d")
            top.withdraw() 
            backup_dir = filedialog.askdirectory(title="Select Backup Destination")
            top.destroy()
            
            if not backup_dir: return
            run_backup_thread(iso_limit, backup_dir)
        except ValueError:
            messagebox.showerror("Error", "Format: DD-MM-YYYY", parent=top)

    top = Toplevel()
    top.title("Backup Images")
    top.geometry("300x150")
    
    tb.Label(top, text="Backup images UP TO date (DD-MM-YYYY):").pack(padx=10, pady=10)
    date_entry = tb.Entry(top)
    date_entry.pack(padx=10)
    tb.Button(top, text="Start Backup", command=on_date_select).pack(pady=10)

def run_backup_thread(iso_date_limit, target_folder):
    prog_win = Toplevel()
    prog_win.title("Backing Up")
    prog_win.geometry("400x150")
    lbl = tb.Label(prog_win, text="Querying database...")
    lbl.pack(padx=20, pady=10)
    pb = ttk.Progressbar(prog_win, length=300, mode="determinate")
    pb.pack(padx=20, pady=10)
    
    def worker():
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.dir_path, i.filename 
                FROM images i
                JOIN directories d ON i.dir_id = d.id
                WHERE i.date_iso <= ?
            """, (iso_date_limit,))
            rows = cursor.fetchall()
            conn.close()
            
            total = len(rows)
            if total == 0:
                root.after(0, lambda: messagebox.showinfo("Info", "No images found up to that date."))
                root.after(0, prog_win.destroy)
                return

            root.after(0, lambda: lbl.config(text=f"Moving {total} images..."))
            root.after(0, lambda: pb.config(maximum=total))
            
            count = 0
            moved = 0
            
            for dir_path, filename in rows:
                if dir_path == config.IMAGE_FOLDER:
                    try:
                        full_path = os.path.join(dir_path, filename)
                        if os.path.exists(full_path):
                            dst = os.path.join(target_folder, filename)
                            shutil.move(full_path, dst)
                            moved += 1
                    except: pass
                count += 1
                if count % 100 == 0:
                    root.after(0, lambda c=count: pb.config(value=c))
            
            root.after(0, prog_win.destroy)
            root.after(0, lambda: messagebox.showinfo("Backup Complete", f"Moved {moved} images."))
            root.after(0, lambda: ask_add_backup(target_folder))
        except Exception as e:
             root.after(0, lambda: messagebox.showerror("Backup Error", str(e)))
             try: root.after(0, prog_win.destroy)
             except: pass

    threading.Thread(target=worker, daemon=True).start()

def ask_add_backup(target_folder):
    if messagebox.askyesno("Update Index", "Do you want to add this backup folder to the network list and re-index?"):
        if target_folder not in additional_folders:
            additional_folders.append(target_folder)
            utils.save_additional_folders(additional_folders)
            update_folder_list_ui()
        start_indexing_process()

def start_indexing_process():
    if indexing_active: return
    btn_reload.config(state="disabled")
    status_label.config(text="Indexing...", bootstyle="warning")
    progress_bar.pack(side=RIGHT, padx=10)
    progress_bar.start(10)
    
    def on_prog(c, t):
        root.after(0, lambda: status_label.config(text=f"Indexed: {c} ({t}s)"))
    
    def on_done(total):
        root.after(0, lambda: finish_indexing(total))
        
    threading.Thread(target=index_images_thread, args=(on_prog, on_done), daemon=True).start()

def finish_indexing(total):
    progress_bar.stop()
    progress_bar.pack_forget()
    status_label.config(text=f"Total Images: {total}", bootstyle="success")
    btn_reload.config(state="normal")
    messagebox.showinfo("Done", f"Indexing Complete.\nTotal Images: {total}")

def search_consumer():
    cid = entry_consumer_id.get().strip()
    if not cid.isdigit() or len(cid) != 9:
        messagebox.showwarning("Error", "Invalid Consumer ID (9 digits required)")
        return
    
    welcome_frame.pack_forget()
    listbox_dates.delete(0, tk.END)
    raise_preview_pane()
    hide_buttons() 
    
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT i.date_original, i.mru, d.dir_path, i.filename 
            FROM images i 
            JOIN directories d ON i.dir_id = d.id 
            WHERE i.consumer_id = ? 
            ORDER BY i.date_iso DESC
        """, (cid,))
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            label_consumer_details.config(text=f"Consumer ID: {cid}\nNo images found.", bootstyle="danger")
            label_latest_date.config(text="")
            clear_previews()
            return

        mru = rows[0][1]
        
        global current_search_data
        current_search_data = {}
        dates_ordered = []
        
        for date, _, dir_path, filename in rows:
            path = os.path.join(dir_path, filename)
            if date not in current_search_data:
                current_search_data[date] = []
                dates_ordered.append(date)
            current_search_data[date].append(path)
            
        count = len(rows)
        meter = utils.get_meter_number(cid)
        meter_txt = f"\nMeter: {meter}" if meter else ""
        label_consumer_details.config(text=f"ID: {cid}\nMRU: {mru}{meter_txt}", bootstyle="primary")
        label_total_images.config(text=f"Images Found: {count}")
        
        latest = dates_ordered[0]
        pretty_latest = f"{latest[:2]}-{latest[2:4]}-{latest[4:]}"
        label_latest_date.config(text=f"Latest Image: {pretty_latest}", bootstyle="success")

        for d in dates_ordered:
            pretty = f"{d[:2]}-{d[2:4]}-{d[4:]}"
            listbox_dates.insert(tk.END, pretty)
            
        show_dynamic_previews(dates_ordered)
        load_consumer_note(cid)
        utils.save_search_history("consumer_ids", cid)

    except Exception as e:
        messagebox.showerror("DB Error", f"Search failed: {e}")

def clear_previews():
    global preview_canvas_widgets
    for widget in scrollable_frame.winfo_children():
        widget.destroy()
    global preview_references
    preview_references = []
    preview_canvas_widgets = []

def show_dynamic_previews(dates):
    preview_bg = "#2c3136" if is_dark_mode_active() else "#f0f0f0"
    clear_previews()
    for i, date in enumerate(dates):
        path = current_search_data[date][0]
        if os.path.exists(path):
            try:
                im = Image.open(path)
                im.thumbnail((180, 180)) 
                ph = ImageTk.PhotoImage(im)
                preview_references.append(ph)
                
                cols = 4 
                pf = tb.Labelframe(scrollable_frame, text=f"{date[:2]}-{date[2:4]}-{date[4:]}", padding=5, bootstyle="info")
                pf.grid(row=i//cols, column=i%cols, padx=10, pady=10, sticky="nsew")
                
                pc = tk.Canvas(pf, width=180, height=180, bg=preview_bg, highlightthickness=0)
                pc.pack()
                pc.create_image(90, 90, image=ph)
                preview_canvas_widgets.append(pc)
                
                def mk_click(p): return lambda e: load_image_to_canvas(p)
                pc.bind("<Button-1>", mk_click(path))
                pf.bind("<Button-1>", mk_click(path)) 
            except: pass

def on_date_select(event):
    idx = listbox_dates.curselection()
    if not idx: return
    txt = listbox_dates.get(idx[0]) 
    raw = txt.replace("-", "") 
    
    if raw in current_search_data:
        paths = current_search_data[raw]
        best_path = paths[0]
        for p in paths:
            if config.IMAGE_FOLDER in p:
                best_path = p
                break
        load_image_to_canvas(best_path)

def load_image_to_canvas(path):
    raise_canvas_pane()
    global img_original, zoom_scale, img, img_tk
    if not os.path.exists(path):
        messagebox.showerror("Error", "Image file not accessible (Offline?)")
        return
    try:
        img_original = Image.open(path)
        zoom_scale = 1.0
        render_image()
        show_buttons() 
    except Exception as e:
        messagebox.showerror("Error", str(e))

def raise_preview_pane():
    preview_container.tkraise()
    btn_show_previews.pack_forget()

def raise_canvas_pane():
    canvas_container.tkraise()
    btn_show_previews.pack(side=TOP, anchor=NE, padx=5, pady=2) 

def render_image():
    global img, img_tk
    if not img_original: return
    
    cw = canvas.winfo_width()
    ch = canvas.winfo_height()
    if cw < 50: cw = 800
    if ch < 50: ch = 600
    
    w, h = img_original.size
    
    if zoom_scale == 1.0:
        ratio = min(cw/w, ch/h)
        nw, nh = int(w*ratio), int(h*ratio)
    else:
        nw, nh = int(w*zoom_scale), int(h*zoom_scale)
        
    img = img_original.resize((nw, nh), Image.Resampling.LANCZOS)
    img_tk = ImageTk.PhotoImage(img)
    canvas.delete("all")
    canvas.create_image(cw//2, ch//2, anchor=CENTER, image=img_tk)

def zoom(factor):
    global zoom_scale
    zoom_scale *= factor
    render_image()

def print_image():
    if not img_original: return
    try:
        tmp = "temp_print.png"
        img_original.save(tmp)
        os.startfile(tmp, "print")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def save_image():
    if not img_original: return
    
    original_filename = os.path.basename(img_original.filename)
    
    path = filedialog.asksaveasfilename(
        initialfile=original_filename,
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")]
    )
    if not path: return

    try:
        img_copy = img_original.copy()
    except:
        img_copy = img_original

    prog = Toplevel()
    prog.title("Saving Image")
    prog.geometry("320x90")
    tb.Label(prog, text="Saving image, please wait...").pack(padx=20, pady=10)
    prog.update()

    def worker(im, out_path):
        try:
            im.save(out_path)
            root.after(0, lambda: messagebox.showinfo("Saved", "Image Saved."))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Save failed: {e}"))
        finally:
            try:
                root.after(0, prog.destroy)
            except:
                pass

    threading.Thread(target=worker, args=(img_copy, path), daemon=True).start()

def save_all_images():
    cid = entry_consumer_id.get().strip()
    if not cid or not current_search_data: return 
    
    dest = filedialog.askdirectory(title="Select Destination Folder")
    if not dest: return
    
    target_dir = os.path.join(dest, cid)
    os.makedirs(target_dir, exist_ok=True)
    
    prog = Toplevel()
    prog.title("Saving Images")
    prog.geometry("360x110")
    lbl = tb.Label(prog, text="Saving images, please wait...")
    lbl.pack(padx=20, pady=10)
    pbar = ttk.Progressbar(prog, length=300, mode="indeterminate")
    pbar.pack(padx=10, pady=5)
    pbar.start(10)
    prog.update()
    
    def worker(data, out_dir):
        count = 0
        try:
            for date, paths in data.items():
                for p in paths:
                    if os.path.exists(p):
                        original_filename = os.path.basename(p)
                        try:
                            shutil.copy2(p, os.path.join(out_dir, original_filename))
                            count += 1
                        except Exception as copy_e:
                            print(f"Could not copy {p}: {copy_e}")
            root.after(0, lambda: messagebox.showinfo("Success", f"Saved {count} images to {out_dir}"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Error", f"Save all failed: {e}"))
        finally:
            try:
                root.after(0, pbar.stop)
                root.after(0, prog.destroy)
            except:
                pass

    threading.Thread(target=worker, args=(current_search_data, target_dir), daemon=True).start()

def toggle_notes():
    if notes_pane.winfo_ismapped():
        notes_pane.pack_forget()
        btn_notes.config(bootstyle=_toggle_btn_style(False))
    else:
        notes_pane.pack(side=RIGHT, fill=Y, padx=5, pady=5)
        btn_notes.config(bootstyle=_toggle_btn_style(True))
        folder_pane.pack_forget()
        btn_folders.config(bootstyle=_toggle_btn_style(False))

def toggle_folders():
    if folder_pane.winfo_ismapped():
        folder_pane.pack_forget()
        btn_folders.config(bootstyle=_toggle_btn_style(False))
    else:
        folder_pane.pack(side=RIGHT, fill=Y, padx=5, pady=5)
        btn_folders.config(bootstyle=_toggle_btn_style(True))
        notes_pane.pack_forget()
        btn_notes.config(bootstyle=_toggle_btn_style(False))

def load_consumer_note(cid):
    try:
        all_n = utils.load_all_notes()
        data = all_n.get(cid, {})
        n_txt = data.get('note', '')
        r_txt = data.get('remarks', '')
        
        if n_txt:
            label_prev_note.config(text=f"Note: {n_txt}\n{r_txt}")
            note_var.set(n_txt)
            txt_remarks.delete("1.0", tk.END)
            txt_remarks.insert("1.0", r_txt)
            if not notes_pane.winfo_ismapped(): toggle_notes()
        else:
            label_prev_note.config(text="No prior notes.")
            note_var.set(note_options[0] if note_options else "")
            txt_remarks.delete("1.0", tk.END)
    except: pass

def save_current_note():
    cid = entry_consumer_id.get().strip()
    if not cid: return
    note = note_var.get()
    remarks = txt_remarks.get("1.0", tk.END).strip()
    utils.save_note(cid, note, remarks)
    messagebox.showinfo("Saved", "Note updated.")
    load_consumer_note(cid)

def delete_current_note():
    cid = entry_consumer_id.get().strip()
    if not cid: return
    if messagebox.askyesno("Confirm", "Are you sure you want to delete the note for this consumer?"):
        utils.delete_note(cid)
        load_consumer_note(cid)
        messagebox.showinfo("Deleted", "Note removed.")

def update_folder_list_ui():
    folder_listbox.delete(0, tk.END)
    folder_listbox.insert(tk.END, config.IMAGE_FOLDER)
    for f in additional_folders:
        folder_listbox.insert(tk.END, f)
    run_single_check()

def run_single_check():
    threading.Thread(target=_check_paths_thread, daemon=True).start()

def _check_paths_thread():
    folders_to_check = [config.IMAGE_FOLDER] + additional_folders
    results = []
    for f in folders_to_check:
        results.append((f, os.path.exists(f)))
    if 'root' in globals():
        root.after(0, lambda: apply_network_colors(results))

def apply_network_colors(results):
    try:
        dark = is_dark_mode_active()
        for idx, (path, is_online) in enumerate(results):
            if is_online:
                color = "#00e676" if dark else "green"
            else:
                color = "#ff5252" if dark else "red"
            folder_listbox.itemconfig(idx, foreground=color)
    except: pass



def update_meter_search_state():
    if database.has_meter_data():
        entry_meter_number.config(state="normal")
        meter_button.config(text="Search Meter", command=search_meter, bootstyle="primary")
    else:
        entry_meter_number.config(state="disabled")
        meter_button.config(text="Update Meter List", command=update_meter_list_threaded, bootstyle="success")



def show_history(event, key, widget):
    try:
        items = utils.load_search_history(key)[::-1] # Reverse for recent first
        if not items: return
        
        if hasattr(widget, 'history_popup') and widget.history_popup.winfo_exists():
            return

        top = Toplevel()
        widget.history_popup = top
        top.overrideredirect(True)
        top.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty()+widget.winfo_height()}")
        _dark = is_dark_mode_active()
        _lb_bg  = "#2c3136" if _dark else "#ffffff"
        _lb_fg  = "#f8f9fa" if _dark else "#212529"
        _lb_sel = "#4c6ef5" if _dark else "#0d6efd"
        if _dark:
            top.config(bg=_lb_bg)
        lb = Listbox(top, height=10, font=("Arial", 11),
                     bg=_lb_bg, fg=_lb_fg,
                     selectbackground=_lb_sel, selectforeground="#ffffff")
        lb.pack(fill=BOTH, expand=True)
        for i in items: lb.insert(tk.END, i)
        
        def pick(e):
            if lb.curselection():
                val = lb.get(lb.curselection())
                widget.delete(0, tk.END)
                widget.insert(0, val)
                top.destroy()
                if key == "consumer_ids": search_consumer()
                else: search_meter()
                
        lb.bind("<Button-1>", pick)
        lb.bind("<FocusOut>", lambda e: top.destroy())
        lb.focus_set()
    except: pass

def search_meter():
    m = entry_meter_number.get().strip()
    if not m: return

    cid = utils.get_consumer_by_meter(m)
    if cid:
        entry_consumer_id.delete(0, tk.END)
        entry_consumer_id.insert(0, cid)
        search_consumer()
        utils.save_search_history("meter_numbers", m)
    else:
        messagebox.showinfo("Not Found", "Meter Number not found.")

def update_meter_list_threaded():
    utils.console_log("FUNCTION STARTED: update_meter_list_threaded")
    utils.console_log("Step 1: Opening Message Box...")
    messagebox.showinfo("Excel File Format", "Please ensure the Excel file contains:\n- Consumer ID in Column 1\n- Meter Number in Column 2")
    utils.console_log("Step 1: Message Box Closed by User.")
    
    def open_file_picker():
        utils.console_log("Step 2: Opening File Dialog (askopenfilename)...")
        try:
            path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
            utils.console_log(f"Step 2: Dialog Result -> {path}")
        except Exception as e:
            utils.console_log(f"!!! ERROR in File Dialog: {e}")
            return
        
        if not path: 
            utils.console_log("Action Cancelled by user.")
            return
        
        utils.console_log("Step 3: Preparing UI for update...")
        meter_button.config(state="disabled", text="Updating...")
        progress_bar.pack(side=RIGHT, padx=10)
        progress_bar.start(10)
        
        threading.Thread(target=worker, args=(path,), daemon=True).start()

    def worker(file_path):
        utils.console_log(f"WORKER: Reading file {file_path} with openpyxl")
        try:
            d = {}
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active
            
            for row in sheet.iter_rows():
                if len(row) >= 2 and row[0].value and row[1].value:
                    cid = str(row[0].value).strip()
                    meter = str(row[1].value).strip()
                    if cid and meter:
                        d[cid] = meter
            
            utils.console_log(f"WORKER: Processed {len(d)} rows.")
            
            utils.update_meter_mapping(d)
            utils.console_log("WORKER: Database updated.")
            
            root.after(0, lambda: messagebox.showinfo("Success", "Meter list updated."))
        except Exception as e:
            utils.console_log(f"!!! WORKER ERROR: {e}")
            root.after(0, lambda e=e: messagebox.showerror("Error", f"Failed to read Excel.\n{str(e)}\n\nEnsure 'openpyxl' is installed."))
        finally:
            utils.console_log("WORKER: Cleaning up UI.")
            root.after(0, reset_ui)

    def reset_ui():
        update_meter_search_state()
        progress_bar.stop()
        progress_bar.pack_forget()

    utils.console_log("WAITING: Scheduling File Picker in 200ms to prevent freeze...")
    root.after(200, open_file_picker)

def show_about():
    about_win = Toplevel(root)
    about_win.title("About Spot Image Viewer")
    about_win.geometry("450x350")
    about_win.transient(root)
    about_win.grab_set()

    header_font = ("Segoe UI", 14, "bold")
    title_font = ("Segoe UI", 11, "bold")
    link_font = ("Segoe UI", 10, "underline")

    main_frame = tb.Frame(about_win, padding=20)
    main_frame.pack(fill=BOTH, expand=True)

    tb.Label(main_frame, text=f"Spot Image Viewer V{config.CURRENT_VERSION}", font=header_font, bootstyle="primary").pack(pady=(0, 15))
    
    tb.Label(main_frame, text="Developer:", font=title_font).pack(anchor=NW)
    tb.Label(main_frame, text="Pramod Verma", font=("Segoe UI", 10)).pack(anchor=NW, padx=(10, 0), pady=(0, 10))

    tb.Label(main_frame, text="Contact & Support:", font=title_font).pack(anchor=NW, pady=(10, 0))
    
    # Email
    email_label = tb.Label(main_frame, text="je.kushidaccc@gmail.com", font=link_font, cursor="hand2", bootstyle="info")
    email_label.pack(anchor=NW, padx=(10, 0))
    email_label.bind("<Button-1>", lambda e: webbrowser.open("mailto:je.kushidaccc@gmail.com"))

    # WhatsApp
    whatsapp_label = tb.Label(main_frame, text="WhatsApp Community", font=link_font, cursor="hand2", bootstyle="info")
    whatsapp_label.pack(anchor=NW, padx=(10, 0), pady=(5, 0))
    whatsapp_label.bind("<Button-1>", lambda e: webbrowser.open("https://chat.whatsapp.com/LZKLg40n8FxCLdnAIO9HGE"))
    
    tb.Button(main_frame, text="Close", command=about_win.destroy, bootstyle="secondary").pack(side=BOTTOM, pady=(20, 0))

def open_help():
    documentation.show_documentation(root)

def prompt_update(version, notes, link):
    title = f"New Version Available: v{version}"
    message = f"A new version of the application is available.\n\nRelease Notes:\n{notes}\n\nDo you want to download it now?"
    if messagebox.askyesno(title, message):
        webbrowser.open(link)

def on_update_found(version, notes, link):
    root.after(0, lambda: prompt_update(version, notes, link))

def on_update_check_finished_auto(status, data):
    if status == "update_found":
        on_update_found(
            data.get("version"),
            data.get("release_notes"),
            data.get("download_url")
        )

def on_update_check_finished_manual(status, data):
    if status == "update_found":
        version = data.get("version")
        notes = data.get("release_notes")
        link = data.get("download_url")
        root.after(0, lambda: prompt_update(version, notes, link))
    elif status == "no_update":
        latest_version = data.get("version") if data else config.CURRENT_VERSION
        release_notes = data.get("release_notes", "No feature notes available.") if data else "No feature notes available."
        message = (
            "You are already using the latest version.\n\n"
            f"Current Version: v{config.CURRENT_VERSION}\n"
            f"Latest Version: v{latest_version}\n\n"
            "Latest Version Features:\n"
            f"{release_notes}"
        )
        root.after(0, lambda: messagebox.showinfo("No Updates", message))
    elif status == "error":
        error_msg = data.get('error', 'An unknown error occurred.')
        root.after(0, lambda: messagebox.showerror("Update Error", f"Failed to check for updates:\n{error_msg}"))

def manual_update_check():
    utils.check_for_updates_background(
        config.CURRENT_VERSION, 
        config.UPDATE_URL, 
        on_update_check_finished_manual
    )

def on_startup_check():
    try:
        utils.check_for_updates_background(config.CURRENT_VERSION, config.UPDATE_URL, on_update_check_finished_auto)
        update_folder_list_ui()
        update_meter_search_state()
        cnt = database.get_total_image_count()
        status_label.config(text=f"Total Indexed Images: {cnt}")
        
        if cnt == 0:
            if messagebox.askyesno("Startup", "Database is empty. Index images now?"):
                start_indexing_process()
    except Exception as e:
        messagebox.showerror("Startup Error", str(e))

# ==============================================================================
# GUI SETUP 
# ==============================================================================
root = tb.Window(themename="cosmo") 
root.title(f"Spot Image Viewer V{config.CURRENT_VERSION}")
root.geometry("1300x850")
root.state("zoomed")

def on_close():
    root.destroy()
    os._exit(0) 

root.protocol("WM_DELETE_WINDOW", on_close)

mb = Menu(root)
root.config(menu=mb)

fm = Menu(mb, tearoff=0)
mb.add_cascade(label="File", menu=fm)
fm.add_command(label="Reload Images", command=start_indexing_process)
fm.add_command(label="Update Meter List", command=update_meter_list_threaded)
fm.add_separator()
fm.add_command(label="Exit", command=root.quit)

bm = Menu(mb, tearoff=0)
mb.add_cascade(label="Backup", menu=bm)
bm.add_command(label="Backup Images", command=perform_backup)

nm = Menu(mb, tearoff=0)
mb.add_cascade(label="Notes", menu=nm)
nm.add_command(label="Export Notes", command=export_notes_csv)

vm = Menu(mb, tearoff=0)
mb.add_cascade(label="Verification", menu=vm)
vm.add_command(label="Low Consumption Check", command=lambda: LowConsumptionVerifier(root))

# Remove the old launch_tool references and use the classes instead
tm = Menu(mb, tearoff=0)
mb.add_cascade(label="Tools", menu=tm)
tm.add_command(label="Bill Calculator", command=lambda: BillCalculatorApp(root))
tm.add_command(label="Theft Bill Calculator", command=lambda: TheftCalculatorApp(root))
tm.add_command(label="Tariff Editor", command=lambda: TariffEditor(root))

hm = Menu(mb, tearoff=0)
mb.add_cascade(label="Help", menu=hm)
hm.add_command(label="Documentation", command=open_help)
hm.add_command(label="Check for Updates", command=manual_update_check)
hm.add_command(label="About", command=show_about)

top_f = tb.Frame(root, padding=15, bootstyle="light") 
top_f.pack(fill=X)

search_card = tb.Labelframe(top_f, text="Search Controls", padding=10, bootstyle="default")
search_card.pack(fill=X, expand=True)

tb.Label(search_card, text="Consumer ID:", font=("Segoe UI", 11, "bold")).pack(side=LEFT, padx=5)
entry_consumer_id = tb.Entry(search_card, width=15, font=("Segoe UI", 11))
entry_consumer_id.pack(side=LEFT, padx=5)
entry_consumer_id.bind("<Return>", lambda e: search_consumer())
entry_consumer_id.bind("<space>", lambda e: show_history(e, "consumer_ids", entry_consumer_id))

tb.Button(search_card, text="Search", bootstyle="primary", command=search_consumer).pack(side=LEFT, padx=5)

tb.Label(search_card, text="Meter No:", font=("Segoe UI", 11, "bold")).pack(side=LEFT, padx=15)
entry_meter_number = tb.Entry(search_card, width=15, font=("Segoe UI", 11))
entry_meter_number.pack(side=LEFT, padx=5)
entry_meter_number.bind("<Return>", lambda e: search_meter())
entry_meter_number.bind("<space>", lambda e: show_history(e, "meter_numbers", entry_meter_number))

meter_button = tb.Button(search_card, text="Search Meter") # Text/command set dynamically
meter_button.pack(side=LEFT, padx=5)

btn_theme_toggle = tb.Button(search_card, text="Dark Mode", command=toggle_theme, bootstyle="dark-outline")
btn_theme_toggle.pack(side=LEFT, padx=5)

btn_reload = tb.Button(search_card, text="Reload Images", bootstyle="warning", command=start_indexing_process)
btn_reload.pack(side=RIGHT, padx=5)

stat_f = tb.Frame(root, padding=5, bootstyle="secondary")
stat_f.pack(side=BOTTOM, fill=X)
status_label = tb.Label(stat_f, text="Ready", font=("Segoe UI", 10), bootstyle="inverse-secondary")
status_label.pack(side=LEFT, padx=5)
progress_bar = ttk.Progressbar(stat_f, mode="indeterminate", length=200)

toggle_f = tb.Frame(stat_f, bootstyle="secondary")
toggle_f.pack(side=RIGHT)
btn_folders = tb.Button(toggle_f, text="Networks", command=toggle_folders, bootstyle="dark-outline")
btn_folders.pack(side=RIGHT, padx=5)
btn_notes = tb.Button(toggle_f, text="Notes", command=toggle_notes, bootstyle="dark-outline")
btn_notes.pack(side=RIGHT, padx=5)

container = tb.Frame(root, padding=10)
container.pack(fill=BOTH, expand=True)

left_p = tb.Labelframe(container, text="Details", width=250, padding=10, bootstyle="default")
left_p.pack(side=LEFT, fill=Y, padx=5)

label_consumer_details = tb.Label(left_p, text="Welcome", font=("Segoe UI", 12, "bold"), wraplength=220, bootstyle="primary")
label_consumer_details.pack(pady=10)
label_latest_date = tb.Label(left_p, text="", font=("Segoe UI", 10, "bold"), bootstyle="success")
label_latest_date.pack(pady=5)
label_total_images = tb.Label(left_p, text="", font=("Segoe UI", 10))
label_total_images.pack(pady=5)

tb.Label(left_p, text="Available Dates:", font=("Segoe UI", 10, "bold")).pack(fill=X, pady=(15,0))
listbox_dates = Listbox(left_p, font=("Segoe UI", 11), relief="flat")
listbox_dates.pack(fill=BOTH, expand=True, pady=5)
listbox_dates.bind("<<ListboxSelect>>", on_date_select)

right_outer_frame = tb.Frame(container)
right_outer_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=5)

right_inner_frame = tb.Frame(right_outer_frame)
right_inner_frame.pack(fill=BOTH, expand=True)

right_inner_frame.grid_rowconfigure(0, weight=1)
right_inner_frame.grid_columnconfigure(0, weight=1)

welcome_frame = tb.Frame(right_inner_frame, bootstyle="light")
welcome_frame.grid(row=0, column=0, sticky="nsew")
welcome_msg = tb.Label(welcome_frame, text="Welcome to Spot Image Viewer", font=("Segoe UI", 24, "bold"), bootstyle="secondary")
welcome_msg.place(relx=0.5, rely=0.4, anchor=CENTER)
welcome_sub = tb.Label(welcome_frame, text="Enter a Consumer ID or Meter Number to begin search.", font=("Segoe UI", 14), bootstyle="secondary")
welcome_sub.place(relx=0.5, rely=0.5, anchor=CENTER)

preview_container = tb.Frame(right_inner_frame)
preview_container.grid(row=0, column=0, sticky="nsew")

preview_canvas_scroller = tk.Canvas(preview_container, highlightthickness=0)
preview_scrollbar = tb.Scrollbar(preview_container, orient="vertical", command=preview_canvas_scroller.yview)
scrollable_frame = tb.Frame(preview_canvas_scroller)

scrollable_frame.bind("<Configure>", lambda e: preview_canvas_scroller.configure(scrollregion=preview_canvas_scroller.bbox("all")))
preview_canvas_scroller.create_window((0, 0), window=scrollable_frame, anchor="nw")
preview_canvas_scroller.configure(yscrollcommand=preview_scrollbar.set)

preview_canvas_scroller.pack(side="left", fill="both", expand=True)
preview_scrollbar.pack(side="right", fill="y")

def _on_preview_mousewheel(event):
    preview_canvas_scroller.yview_scroll(int(-1 * (event.delta / 120)), "units")

def _bind_preview_mousewheel(event):
    preview_canvas_scroller.bind_all("<MouseWheel>", _on_preview_mousewheel)

def _unbind_preview_mousewheel(event):
    preview_canvas_scroller.unbind_all("<MouseWheel>")

preview_canvas_scroller.bind('<Enter>', _bind_preview_mousewheel)
preview_canvas_scroller.bind('<Leave>', _unbind_preview_mousewheel)

canvas_container = tb.Frame(right_inner_frame)
canvas_container.grid(row=0, column=0, sticky="nsew")

btn_show_previews = tb.Button(right_outer_frame, text="Show Previews", command=raise_preview_pane, bootstyle="info-outline")

canvas = tk.Canvas(canvas_container, highlightthickness=0)
canvas.pack(fill=BOTH, expand=True)

btns_f = tb.Frame(canvas_container)
btns_f.pack(pady=5)
btn_zoomin = tb.Button(btns_f, text="+", width=4, command=lambda: zoom(1.2), bootstyle="secondary")
btn_zoomout = tb.Button(btns_f, text="-", width=4, command=lambda: zoom(0.8), bootstyle="secondary")
btn_prnt = tb.Button(btns_f, text="Print", command=print_image, bootstyle="info")
btn_sv = tb.Button(btns_f, text="Save", command=save_image, bootstyle="success")
btn_svall = tb.Button(btns_f, text="Save All", command=save_all_images, bootstyle="success")

def show_buttons():
    btn_zoomout.pack(side=LEFT, padx=3)
    btn_zoomin.pack(side=LEFT, padx=3)
    btn_prnt.pack(side=LEFT, padx=3)
    btn_sv.pack(side=LEFT, padx=3)
    btn_svall.pack(side=LEFT, padx=3)

def hide_buttons():
    for w in btns_f.winfo_children(): w.pack_forget()

welcome_frame.tkraise()
hide_buttons()

notes_pane = tb.Labelframe(container, text="Notes", width=280, padding=10, bootstyle="warning")
label_prev_note = tb.Label(notes_pane, text="No notes", wraplength=250, justify=LEFT, bootstyle="secondary")
label_prev_note.pack(fill=X, pady=5)

note_opts_f = tb.Frame(notes_pane)
note_opts_f.pack(fill=X, pady=5)
note_options = utils.load_note_options()
note_var = tk.StringVar(value=note_options[0] if note_options else "")
combo_notes = ttk.Combobox(note_opts_f, textvariable=note_var, values=note_options)
combo_notes.pack(side=LEFT, fill=X, expand=True)
tb.Button(note_opts_f, text="+", width=3, command=add_new_note_option, bootstyle="success-outline").pack(side=LEFT, padx=(5,0))

txt_remarks = tk.Text(notes_pane, height=6, width=25, relief="flat")
txt_remarks.pack(fill=X, pady=5)
tb.Button(notes_pane, text="Save Note", command=save_current_note, bootstyle="success").pack(fill=X, pady=2)
tb.Button(notes_pane, text="Delete Note", command=delete_current_note, bootstyle="danger-outline").pack(fill=X, pady=2)

folder_pane = tb.Labelframe(container, text="Networks", width=280, padding=10, bootstyle="info")
folder_listbox = Listbox(folder_pane, height=15, relief="flat")
folder_listbox.pack(fill=BOTH, expand=True, pady=5)
tb.Button(folder_pane, text="Add Folder", command=add_network_folder, bootstyle="success-outline").pack(fill=X, pady=2)
tb.Button(folder_pane, text="Remove Folder", command=remove_network_folder, bootstyle="danger-outline").pack(fill=X, pady=2)

def run_app():
    success, msg = database.init_db()
    if not success:
        print(f"Database init failed: {msg}")

    refresh_non_ttk_widget_colors()
    update_theme_toggle_button_text()
    
    root.after(500, on_startup_check)
    root.mainloop()
