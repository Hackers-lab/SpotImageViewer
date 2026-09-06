import os
import json
import threading
import openpyxl
import csv
import tkinter as tk
from tkinter import messagebox, filedialog, Listbox, ttk, END, LEFT, RIGHT, TOP, BOTTOM, BOTH, X, Y, HORIZONTAL
import ttkbootstrap as tb
from PIL import Image, ImageTk

import config
from database import get_db_connection

class LowConsumptionVerifier(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Low Consumption Verification Mode")
        self.geometry("1300x850")
        self.state("zoomed")
        
        # Data & Session Paths
        self.data = [] 
        self.current_index = -1
        self.current_cid = None
        self.date_to_widget = {} 
        self.session_file = os.path.join(config.BASE_DIR, "verification_session.json")
        
        # Layout
        self.create_widgets()
        
        # Startup Logic
        self.after(200, self.startup_check)

    def create_widgets(self):
        toolbar = tb.Frame(self, bootstyle="secondary", padding=5)
        toolbar.pack(fill=X, side=TOP)
        tb.Button(toolbar, text="Load Excel", command=self.load_excel, bootstyle="info").pack(side=LEFT, padx=5)
        tb.Button(toolbar, text="Paste from Clipboard", command=self.load_paste, bootstyle="info").pack(side=LEFT, padx=5)
        tb.Button(toolbar, text="Export CSV", command=self.export_report, bootstyle="success").pack(side=LEFT, padx=5)
        tb.Label(toolbar, text=" |  Shortcuts: Alt+S (Save), Alt+N (Skip)", bootstyle="inverse-secondary").pack(side=LEFT, padx=15)

        split = tb.Panedwindow(self, orient=HORIZONTAL)
        split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        left_frame = tb.Frame(split, width=400)
        split.add(left_frame)
        
        filter_f = tb.Frame(left_frame, padding=5)
        filter_f.pack(fill=X)
        tb.Label(filter_f, text="Search:").pack(side=LEFT)
        self.var_filter = tk.StringVar()
        self.var_filter.trace("w", self.filter_tree)
        tb.Entry(filter_f, textvariable=self.var_filter).pack(side=LEFT, fill=X, expand=True, padx=5)

        cols = ("status", "cid", "meter", "unit", "spacer")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("status", text="St")
        self.tree.heading("cid", text="Consumer ID")
        self.tree.heading("meter", text="Meter No")
        self.tree.heading("unit", text="Unit")
        self.tree.heading("spacer", text="") 
        
        self.tree.column("status", width=40, anchor="center")
        self.tree.column("cid", width=110, anchor="w")
        self.tree.column("meter", width=110, anchor="w")
        self.tree.column("unit", width=80, anchor="center") 
        self.tree.column("spacer", width=20, anchor="center") 
        
        self.tree.pack(fill=BOTH, expand=True)
        
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        vsb.place(relx=1.0, rely=0, relheight=1.0, anchor="ne")
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        right_frame = tb.Frame(split)
        split.add(right_frame)

        action_frame = tb.Labelframe(right_frame, text="Verification Decision", padding=10, bootstyle="primary")
        action_frame.pack(side=BOTTOM, fill=X, padx=10, pady=10)

        input_f = tb.Frame(action_frame)
        input_f.pack(fill=X, pady=5)
        
        self.var_status = tk.StringVar(value="OK")
        tb.Radiobutton(input_f, text="OK (Verified)", variable=self.var_status, value="OK", bootstyle="success-toolbutton").pack(side=LEFT, padx=5)
        tb.Radiobutton(input_f, text="Suspicious / Not OK", variable=self.var_status, value="CHECK", bootstyle="danger-toolbutton").pack(side=LEFT, padx=5)
        
        tb.Label(input_f, text="Remarks:", font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=(20, 5))
        self.entry_remarks = tb.Entry(input_f)
        self.entry_remarks.pack(side=LEFT, fill=X, expand=True, padx=5)

        btn_f = tb.Frame(action_frame)
        btn_f.pack(fill=X, pady=(5, 0))
        tb.Button(btn_f, text="Save & Next (Alt+S)", command=self.save_and_next, bootstyle="success", width=20).pack(side=RIGHT, padx=5)
        tb.Button(btn_f, text="Skip (Alt+N)", command=self.skip_item, bootstyle="warning", width=10).pack(side=RIGHT, padx=5)

        info_card = tb.Frame(right_frame, padding=10, bootstyle="light")
        info_card.pack(side=TOP, fill=X)
        
        self.lbl_cid_big = tb.Label(info_card, text="Select Consumer", font=("Segoe UI", 18, "bold"), bootstyle="primary")
        self.lbl_cid_big.pack(side=LEFT)
        
        self.lbl_meter_big = tb.Label(info_card, text="", font=("Segoe UI", 12))
        self.lbl_meter_big.pack(side=LEFT, padx=20)
        
        self.lbl_unit_big = tb.Label(info_card, text="", font=("Segoe UI", 18, "bold"), bootstyle="danger")
        self.lbl_unit_big.pack(side=RIGHT, padx=10)
        tb.Label(info_card, text="Billed Unit:", font=("Segoe UI", 10)).pack(side=RIGHT)

        content_split = tb.Panedwindow(right_frame, orient=HORIZONTAL)
        content_split.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
        
        date_frame = tb.Labelframe(content_split, text="Select Date", width=180, padding=5)
        content_split.add(date_frame)
        
        self.lb_dates = Listbox(date_frame, font=("Segoe UI", 11), relief="flat", bg="#f8f9fa", selectbackground="#0d6efd")
        self.lb_dates.pack(fill=BOTH, expand=True)
        self.lb_dates.bind("<<ListboxSelect>>", self.on_date_click)

        self.grid_container = tb.Labelframe(content_split, text="Image Gallery (Latest First)", padding=5)
        content_split.add(self.grid_container)
        
        self.canvas = tk.Canvas(self.grid_container, bg="white", highlightthickness=0)
        self.scrollbar = tb.Scrollbar(self.grid_container, orient="vertical", command=self.canvas.yview)
        
        self.scroll_frame = tk.Frame(self.canvas, bg="white")

        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas_window_id = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

        def _on_canvas_configure(event):
            self.canvas.itemconfig(self.canvas_window_id, width=event.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.bind("<Alt-s>", lambda e: self.save_and_next())
        self.bind("<Alt-n>", lambda e: self.skip_item())


    def startup_check(self):
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r") as f:
                    self.data = json.load(f)
                
                if self.data:
                    if messagebox.askyesno("Session Found", f"Restore previous session with {len(self.data)} records?"):
                        self.filter_tree()
                        self.lift()
                        self.focus_force()
                        first_pending = next((item['id'] for item in self.data if item['status'] == "PENDING"), None)
                        if first_pending is not None:
                            self.tree.selection_set(first_pending)
                            self.tree.see(first_pending)
                    else:
                        self.data = []
                        self.save_session()
                        self.filter_tree()
            except Exception as e:
                print(f"Session load error: {e}")
                self.data = []
                self.save_session()
                self.filter_tree()
        


    def save_session(self):
        try:
            with open(self.session_file, "w") as f:
                json.dump(self.data, f)
        except: pass

    def load_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if not path:
            return
        
        try:
            wb = openpyxl.load_workbook(path)
            sheet = wb.active
            
            new_data = []
            for idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if not any(row): continue
                cid = str(row[0]).strip() if row[0] else ""
                if not cid or cid.lower() == "nan": continue
                meter = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                unit = str(row[2]).strip() if len(row) > 2 and row[2] else "0"
                new_data.append({"id": idx, "cid": cid, "meter": meter, "unit": unit, "status": "PENDING", "remarks": ""})
            
            self.data = new_data
            self.save_session()
            self.filter_tree()
            messagebox.showinfo("Loaded", f"{len(self.data)} records from Excel.")
            self.lift()
            self.focus_force()

        except Exception as e:
            messagebox.showerror("Excel Error", f"Failed to read Excel file.\n{e}")

    def load_paste(self):
        pwin = tb.Toplevel(self)
        pwin.title("Paste Data")
        pwin.geometry("400x350")

        tb.Label(pwin, text="Paste data from clipboard (ID | Meter | Unit)").pack(pady=10)
        
        txt = tk.Text(pwin, height=10, width=50)
        txt.pack(pady=5, padx=10, fill="both", expand=True)
        
        def go():
            raw = txt.get("1.0", END)
            rows = [line.split() for line in raw.split('\n') if line.strip()]
            
            new_data = []
            for idx, row in enumerate(rows):
                if not row: continue
                cid = str(row[0]).strip() if row[0] else ""
                if not cid or cid.lower() == "nan": continue
                meter = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                unit = str(row[2]).strip() if len(row) > 2 and row[2] else "0"
                new_data.append({"id": idx, "cid": cid, "meter": meter, "unit": unit, "status": "PENDING", "remarks": ""})

            self.data = new_data
            self.save_session()
            self.filter_tree()
            messagebox.showinfo("Loaded", f"{len(self.data)} records from clipboard.", parent=self)
            pwin.destroy()

        tb.Button(pwin, text="Import Data", command=go, bootstyle="success").pack(pady=10)
        pwin.transient(self)
        pwin.grab_set()
        pwin.focus_set()

    def filter_tree(self, *args):
        query = self.var_filter.get().lower()
        self.tree.delete(*self.tree.get_children())
        for item in self.data:
            if query in item['cid'].lower() or query in item['meter'].lower():
                icon = "⏳"
                if item['status'] == "OK": icon = "✅"
                elif item['status'] == "CHECK": icon = "❌"
                self.tree.insert("", "end", iid=item['id'], values=(icon, item['cid'], item['meter'], item['unit'], ""))

    def _on_mousewheel(self, event):
        try: self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except: pass

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        idx = int(sel[0])
        self.current_index = idx
        
        item = next((x for x in self.data if x['id'] == idx), None)
        if not item: return
        
        self.current_cid = item['cid']
        
        self.lbl_cid_big.config(text=f"ID: {item['cid']}")
        self.lbl_meter_big.config(text=f"Meter: {item['meter']}")
        self.lbl_unit_big.config(text=str(item['unit']))
        
        self.var_status.set(item['status'] if item['status'] != "PENDING" else "OK")
        self.entry_remarks.delete(0, END)
        self.entry_remarks.insert(0, item['remarks'])
        self.entry_remarks.focus_set()
        
        self.load_consumer_data(item['cid'])

    def load_consumer_data(self, cid):
        self.lb_dates.delete(0, END)
        for w in self.scroll_frame.winfo_children(): w.destroy()
        self.date_to_widget = {}
        
        def worker():
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT d.dir_path, i.filename
                FROM images i
                JOIN directories d ON i.dir_id = d.id
                WHERE i.consumer_id = ?
                ORDER BY i.date_iso DESC
                LIMIT 24
            """, (cid,))
            rows = cur.fetchall()
            conn.close()

            processed_rows = []
            for dir_path, filename in rows:
                full_path = os.path.join(dir_path, filename)
                date_orig = filename[:8]
                processed_rows.append((date_orig, full_path))

            self.after(0, lambda: self.populate_ui(processed_rows))
            
        threading.Thread(target=worker, daemon=True).start()

    def populate_ui(self, rows):
        if not rows:
            lbl = tk.Label(self.scroll_frame, text="NO IMAGES FOUND", font=("Segoe UI", 20, "bold"), fg="#adb5bd", bg="white")
            lbl.pack(pady=50, padx=20)
            return

        COLUMNS = 4
        self.photo_refs = [] 
        
        for i, (date, path) in enumerate(rows):
            pretty = f"{date[:2]}-{date[2:4]}-{date[4:]}"
            self.lb_dates.insert(END, pretty)
            
            if not os.path.exists(path): continue
            
            try:
                f = tk.Frame(self.scroll_frame, bg="white", bd=2, relief="flat")
                f.grid(row=i//COLUMNS, column=i%COLUMNS, padx=8, pady=8)
                self.date_to_widget[pretty] = f
                
                im = Image.open(path)
                im.thumbnail((180, 180)) 
                ph = ImageTk.PhotoImage(im)
                self.photo_refs.append(ph)
                
                lbl_img = tk.Label(f, image=ph, bg="white")
                lbl_img.pack(padx=2, pady=2)
                
                lbl_txt = tk.Label(f, text=pretty, bg="white", font=("Arial", 9, "bold"))
                lbl_txt.pack()
            except: pass

    def on_date_click(self, event):
        sel = self.lb_dates.curselection()
        if not sel: return
        
        date_str = self.lb_dates.get(sel[0])
        target_widget = self.date_to_widget.get(date_str)
        
        if target_widget:
            for w in self.date_to_widget.values(): w.config(bg="white")
            target_widget.config(bg="#0d6efd")
            
            y = target_widget.winfo_y()
            height = self.scroll_frame.winfo_height()
            if height > 0:
                self.canvas.yview_moveto(y / height)

    def save_and_next(self):
        if self.current_index == -1: return
        
        item = next((x for x in self.data if x['id'] == self.current_index), None)
        if item:
            item['status'] = self.var_status.get()
            item['remarks'] = self.entry_remarks.get().strip()
            
            icon = "✅" if item['status'] == "OK" else "❌"
            self.tree.item(self.current_index, values=(icon, item['cid'], item['meter'], item['unit'], ""))
            
            self.save_session() 
            self.skip_item() 

    def skip_item(self):
        next_id = -1
        found = False
        children = self.tree.get_children()
        for child in children:
            if found:
                next_id = child
                break
            if int(child) == self.current_index:
                found = True
        
        if next_id != -1:
            self.tree.selection_set(next_id)
            self.tree.see(next_id)
        else:
            messagebox.showinfo("Done", "End of list.")

    def export_report(self):
        if not self.data:
            messagebox.showwarning("No Data", "There is no data to export.")
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
            
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
                writer.writeheader()
                writer.writerows(self.data)
            messagebox.showinfo("Saved", "Report Exported Successfully.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV.\n{e}")