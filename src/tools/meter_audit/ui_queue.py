import tkinter as tk
import customtkinter as ctk

class ActiveQueueFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select_callback, on_toggle_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.on_select_callback = on_select_callback
        self.on_toggle_callback = on_toggle_callback
        self.row_frames = {} # con_id -> tk.Frame
        self.checkbox_vars = {} # con_id -> StringVar
        self.badge_labels = {} # con_id -> tk.Label
        self.selected_con_id = None

    def populate_queue(self, records, audited_ids=None, audit_decisions=None, allow_without_lookup=True):
        if audited_ids is None:
            audited_ids = set()
        if audit_decisions is None:
            audit_decisions = {}

        # Destroy all children first
        for child in self.winfo_children():
            child.destroy()
        self.row_frames.clear()
        self.checkbox_vars.clear()
        self.badge_labels.clear()
        self.selected_con_id = None

        if not records:
            lbl = tk.Label(self, text="Queue Empty. Fetch or load records.", font=("Arial", 10, "italic"), fg="gray", bg="#1a1a24")
            lbl.pack(pady=30)
            return

        for idx, rec in enumerate(records):
            con_id = str(rec.get("con_id"))
            meter_no = rec.get("meter_no", "N/A")
            
            # Row Outer Container (Standard tk Frame for 100x rendering speed)
            row_frm = tk.Frame(self, bg="#1a1a24", bd=0, highlightthickness=0)
            row_frm.pack(fill="x", pady=2, padx=4)
            self.row_frames[con_id] = row_frm

            # Resolve status
            if con_id in audited_ids:
                status = audit_decisions.get(con_id, {}).get("verification_stat", "C")
            else:
                status = "C" if allow_without_lookup else "Pending"

            # Checkbox
            var = tk.StringVar()
            if status == "C":
                var.set("C")
            elif status == "Pending":
                var.set("")
            else:
                var.set(status)

            self.checkbox_vars[con_id] = var
            chk = tk.Checkbutton(
                row_frm, 
                text="", 
                variable=var, 
                onvalue="C", 
                offvalue="IL", 
                command=lambda cid=con_id: self.on_toggle_callback(cid),
                bg="#1a1a24",
                activebackground="#1a1a24",
                selectcolor="#111827",
                fg="white",
                bd=0,
                highlightthickness=0
            )
            chk.pack(side="left", padx=(8, 4))
            
            # ID and Meter Details Frame
            lbl_frm = tk.Frame(row_frm, bg="#1a1a24")
            lbl_frm.pack(side="left", fill="both", expand=True, padx=4)
            
            id_lbl = tk.Label(lbl_frm, text=f"ID: {con_id}", font=("Arial", 10, "bold"), fg="#ffffff", bg="#1a1a24", anchor="w")
            id_lbl.pack(anchor="w", fill="x", pady=(2, 0))
            
            meter_lbl = tk.Label(lbl_frm, text=f"Meter: {meter_no}", font=("Arial", 9), fg="#9ca3af", bg="#1a1a24", anchor="w")
            meter_lbl.pack(anchor="w", fill="x", pady=(0, 2))

            # Status Badge Label
            if status == "C":
                b_text = "Approved"
                b_bg = "#064e3b"
                b_fg = "#10b981"
            elif status == "Pending":
                b_text = "Pending"
                b_bg = "#374151"
                b_fg = "#9ca3af"
            elif status == "IL":
                b_text = "Illegible"
                b_bg = "#78350f"
                b_fg = "#fbbf24"
            elif status == "MM":
                b_text = "Diff Meter"
                b_bg = "#7f1d1d"
                b_fg = "#f87171"
            elif status == "LM":
                b_text = "Diff Loc"
                b_bg = "#581c87"
                b_fg = "#c084fc"
            elif status == "NMI":
                b_text = "Non Meter"
                b_bg = "#374151"
                b_fg = "#9ca3af"
            elif status == "I":
                b_text = "Mismatch"
                b_bg = "#1e3a8a"
                b_fg = "#60a5fa"
            else:
                b_text = "Approved"
                b_bg = "#064e3b"
                b_fg = "#10b981"

            badge = tk.Label(
                row_frm, 
                text=b_text, 
                bg=b_bg, 
                fg=b_fg, 
                font=("Arial", 9, "bold"),
                width=10,
                height=1,
                bd=0
            )
            badge.pack(side="right", padx=(4, 8))
            self.badge_labels[con_id] = badge

            # Bind mouse clicks to select row
            for widget in (row_frm, lbl_frm, id_lbl, meter_lbl):
                widget.bind("<Button-1>", lambda e, cid=con_id: self.on_select_callback(cid))
        
    def _set_row_bg(self, con_id_str, bg_color):
        if con_id_str in self.row_frames:
            frm = self.row_frames[con_id_str]
            frm.configure(bg=bg_color)
            for child in frm.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=bg_color)
                    for gchild in child.winfo_children():
                        if isinstance(gchild, (tk.Label, tk.Checkbutton)):
                            gchild.configure(bg=bg_color)
                elif isinstance(child, (tk.Label, tk.Checkbutton)):
                    if child != self.badge_labels.get(con_id_str):
                        child.configure(bg=bg_color)

    def highlight_row(self, con_id):
        con_id_str = str(con_id)
        # Reset old highlight
        if self.selected_con_id and self.selected_con_id in self.row_frames:
            try:
                self._set_row_bg(self.selected_con_id, "#1a1a24")
            except Exception:
                pass
        
        self.selected_con_id = con_id_str
        # Set new highlight
        if con_id_str in self.row_frames:
            try:
                self._set_row_bg(con_id_str, "#2b313e")
                # Automatically scroll view to keep highlighted row visible if possible
                self.row_frames[con_id_str].focus()
            except Exception:
                pass

    def update_status_badge(self, con_id, status):
        con_id_str = str(con_id)
        # Update checkbox var
        if con_id_str in self.checkbox_vars:
            if status == "C":
                self.checkbox_vars[con_id_str].set("C")
            elif status == "Pending":
                self.checkbox_vars[con_id_str].set("")
            else:
                self.checkbox_vars[con_id_str].set(status) # offvalue

        # Update badge colors and text
        if con_id_str in self.badge_labels:
            lbl = self.badge_labels[con_id_str]
            if status == "C":
                lbl.configure(
                    text="Approved", 
                    bg="#064e3b", 
                    fg="#10b981"
                )
            elif status == "Pending":
                lbl.configure(
                    text="Pending", 
                    bg="#374151", 
                    fg="#9ca3af"
                )
            elif status == "IL":
                lbl.configure(
                    text="Illegible", 
                    bg="#78350f", 
                    fg="#fbbf24"
                )
            elif status == "MM":
                lbl.configure(
                    text="Diff Meter", 
                    bg="#7f1d1d", 
                    fg="#f87171"
                )
            elif status == "LM":
                lbl.configure(
                    text="Diff Loc", 
                    bg="#581c87", 
                    fg="#c084fc"
                )
            elif status == "NMI":
                lbl.configure(
                    text="Non Meter", 
                    bg="#374151", 
                    fg="#9ca3af"
                )
            elif status == "I":
                lbl.configure(
                    text="Mismatch", 
                    bg="#1e3a8a", 
                    fg="#60a5fa"
                )

