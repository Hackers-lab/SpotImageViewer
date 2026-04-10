"""
Image Check Status Viewer
=========================
Shows upload data organised as Month → Portion tree (left pane) and
a tabular status summary (right pane) drawn from wbsedcl.db.

Supports consolidation across multiple user DBs (local + network users).

Tables used
-----------
uploaddata  - meter-reading records; smrd = ddmmyyyy (scheduled meter-read date)
sapdata     - SAP-processed records; remarks = C/P/I/IL/NMI

DB path pattern
---------------
  C:/Users/<username>/AppData/Local/Application4SM/app/wbsedcl.db
"""

import os
import json
import sqlite3
import threading
import getpass

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

_APP_DIR       = os.path.dirname(os.path.abspath(__file__))
_SETTINGS_FILE = os.path.join(_APP_DIR, "image_check_users.json")
_DB_SUBPATH    = os.path.join("AppData", "Local", "Application4SM", "app", "wbsedcl.db")

_MON_NAMES = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}

REMARK_COLS   = ["C", "P", "I", "IL", "NMI"]
STATUS_COLORS = {
    "done":    ("#27ae60", "#d4edda"),
    "partial": ("#e67e22", "#fff3cd"),
    "none":    ("#e74c3c", "#fde8e8"),
    "no_sap":  ("#7f8c8d", "#f0f3f4"),
}


def _load_settings():
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"extra_usernames": []}


def _save_settings(settings):
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"[ImageCheckStatus] Failed to save settings: {e}")


def _local_username():
    try:
        return os.getlogin()
    except Exception:
        return getpass.getuser()


def _db_path_for_user(username):
    return os.path.join("C:\\Users", username, _DB_SUBPATH)


def _get_all_db_sources():
    settings   = _load_settings()
    local_user = _local_username()
    extras     = [u for u in settings.get("extra_usernames", []) if u != local_user]
    sources    = [(local_user, _db_path_for_user(local_user), True)]
    for uname in extras:
        sources.append((uname, _db_path_for_user(uname), False))
    return sources


def _smrd_to_month_key(smrd):
    if smrd and len(smrd) == 8:
        mm, yyyy = smrd[2:4], smrd[4:8]
        return yyyy + mm, f"{_MON_NAMES.get(mm, mm)}-{yyyy}"
    return None, None


def _month_totals(portions):
    totals = {"upload": 0, "sap_total": 0, **{r: 0 for r in REMARK_COLS}}
    for pd in portions.values():
        for k in totals:
            totals[k] += pd.get(k, 0)
    return totals


def _build_db_data(sources):
    data         = {}
    loaded_users = []
    failed_users = []

    for username, db_path, _is_local in sources:
        if not os.path.isfile(db_path):
            failed_users.append((username, "File not found"))
            continue
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            c    = conn.cursor()

            c.execute("""
                SELECT smrd, portion, COUNT(*) AS cnt
                FROM   uploaddata
                WHERE  smrd IS NOT NULL AND portion IS NOT NULL
                GROUP  BY smrd, portion
            """)
            for smrd, portion, cnt in c.fetchall():
                mk, mlabel = _smrd_to_month_key(smrd)
                if mk is None:
                    continue
                if mk not in data:
                    data[mk] = {"label": mlabel, "portions": {}}
                p = data[mk]["portions"]
                if portion not in p:
                    p[portion] = {"upload": 0, "sap_total": 0, **{r: 0 for r in REMARK_COLS}}
                p[portion]["upload"] += cnt

            c.execute("""
                SELECT smrd, portion, remarks, COUNT(*) AS cnt
                FROM   sapdata
                WHERE  smrd IS NOT NULL AND portion IS NOT NULL
                GROUP  BY smrd, portion, remarks
            """)
            for smrd, portion, remarks, cnt in c.fetchall():
                mk, mlabel = _smrd_to_month_key(smrd)
                if mk is None:
                    continue
                if mk not in data:
                    data[mk] = {"label": mlabel, "portions": {}}
                p = data[mk]["portions"]
                if portion not in p:
                    p[portion] = {"upload": 0, "sap_total": 0, **{r: 0 for r in REMARK_COLS}}
                rkey = (remarks or "").strip().upper()
                if rkey in REMARK_COLS:
                    p[portion][rkey] += cnt
                p[portion]["sap_total"] += cnt

            conn.close()
            loaded_users.append(username)
        except Exception as e:
            failed_users.append((username, str(e)))

    return data, loaded_users, failed_users


class _UserManagerDialog(tb.Toplevel):
    def __init__(self, parent, on_close=None):
        super().__init__(parent)
        self.title("Manage Network Users")
        self.geometry("520x420")
        self.resizable(False, False)
        self._on_close = on_close
        self._build_ui()
        self._refresh_list()
        self.grab_set()

    def _build_ui(self):
        hdr = tb.Frame(self, padding=(10, 8), bootstyle="primary")
        hdr.pack(fill=X)
        tb.Label(hdr, text="  Network Users", font=("Segoe UI", 12, "bold"),
                 foreground="white", bootstyle="inverse-primary").pack(side=LEFT)

        info = tb.Frame(self, padding=(10, 6))
        info.pack(fill=X)
        local = _local_username()
        tb.Label(info, text=f"Local user (always included):  {local}",
                 font=("Segoe UI", 9), bootstyle="secondary").pack(anchor="w")
        tb.Label(info,
                 text=r"DB path:  C:\Users\<username>\AppData\Local\Application4SM\app\wbsedcl.db",
                 font=("Segoe UI", 8), bootstyle="secondary", wraplength=480).pack(anchor="w")

        list_frm = tb.Frame(self, padding=(10, 0))
        list_frm.pack(fill=BOTH, expand=YES)
        cols = ("username", "db_path", "status")
        self._tv = ttk.Treeview(list_frm, columns=cols, show="headings",
                                selectmode="browse", height=8)
        self._tv.heading("username", text="Username")
        self._tv.heading("db_path",  text="DB Path")
        self._tv.heading("status",   text="Status")
        self._tv.column("username", width=110, anchor="w")
        self._tv.column("db_path",  width=280, anchor="w")
        self._tv.column("status",   width=80,  anchor="center")
        self._tv.tag_configure("ok",      foreground="#27ae60")
        self._tv.tag_configure("missing", foreground="#e74c3c")
        sb = tb.Scrollbar(list_frm, orient=VERTICAL, command=self._tv.yview, bootstyle="round")
        self._tv.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self._tv.pack(fill=BOTH, expand=YES)

        add_frm = tb.Frame(self, padding=(10, 4))
        add_frm.pack(fill=X)
        tb.Label(add_frm, text="Add username:", font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 6))
        self._entry = tb.Entry(add_frm, width=22, font=("Segoe UI", 10))
        self._entry.pack(side=LEFT)
        self._entry.bind("<Return>", lambda _: self._add_user())
        tb.Button(add_frm, text="Add", bootstyle="success-outline",
                  width=8, command=self._add_user).pack(side=LEFT, padx=(6, 0))
        tb.Button(add_frm, text="Remove Selected", bootstyle="danger-outline",
                  command=self._remove_user).pack(side=RIGHT)

        btn_frm = tb.Frame(self, padding=(10, 6))
        btn_frm.pack(fill=X)
        tb.Button(btn_frm, text="Close", bootstyle="primary",
                  width=10, command=self._close).pack(side=RIGHT)

    def _refresh_list(self):
        self._tv.delete(*self._tv.get_children())
        settings = _load_settings()
        for uname in settings.get("extra_usernames", []):
            path   = _db_path_for_user(uname)
            exists = os.path.isfile(path)
            self._tv.insert("", "end",
                            values=(uname, path, "Found" if exists else "Missing"),
                            tags=("ok" if exists else "missing",))

    def _add_user(self):
        uname = self._entry.get().strip()
        if not uname:
            return
        if uname == _local_username():
            messagebox.showinfo("Skipped",
                                f"'{uname}' is the local user and is always included.",
                                parent=self)
            return
        settings = _load_settings()
        extras   = settings.setdefault("extra_usernames", [])
        if uname in extras:
            messagebox.showinfo("Duplicate", f"'{uname}' is already in the list.", parent=self)
            return
        extras.append(uname)
        _save_settings(settings)
        self._entry.delete(0, "end")
        self._refresh_list()

    def _remove_user(self):
        sel = self._tv.selection()
        if not sel:
            return
        uname = self._tv.item(sel[0], "values")[0]
        settings = _load_settings()
        extras   = settings.get("extra_usernames", [])
        if uname in extras:
            extras.remove(uname)
            _save_settings(settings)
        self._refresh_list()

    def _close(self):
        self.destroy()
        if self._on_close:
            self._on_close()


class ImageCheckStatus(tb.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Image Check Status")
        self.geometry("1200x700")
        self.minsize(900, 500)
        self._data         = {}
        self._loaded_users = []
        self._failed_users = []
        self._build_ui()
        self._load_async()

    def _build_ui(self):
        hdr = tb.Frame(self, padding=(12, 8), bootstyle="primary")
        hdr.pack(fill=X)
        tb.Label(hdr, text="  Image Check Status",
                 font=("Segoe UI", 14, "bold"),
                 foreground="white", bootstyle="inverse-primary").pack(side=LEFT)
        tb.Button(hdr, text="Users", bootstyle="outline-light",
                  width=9, command=self._open_user_manager).pack(side=RIGHT, padx=6)
        self._lbl_status = tb.Label(hdr, text="Loading...",
                                    font=("Segoe UI", 9), foreground="#d0e8ff",
                                    bootstyle="inverse-primary")
        self._lbl_status.pack(side=RIGHT, padx=8)

        self._sources_bar = tb.Frame(self, padding=(10, 3), bootstyle="secondary")
        self._sources_bar.pack(fill=X)
        self._summary_bar = tb.Frame(self, padding=(10, 4), bootstyle="light")
        self._summary_bar.pack(fill=X)

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               sashwidth=6, sashrelief=tk.RAISED, bg="#cbd5e0")
        paned.pack(fill=BOTH, expand=YES)

        left = tb.Frame(paned, padding=0)
        paned.add(left, minsize=220, width=290)
        tb.Label(left, text="Month  /  Portion",
                 font=("Segoe UI", 10, "bold"),
                 bootstyle="primary", anchor="w").pack(fill=X, padx=8, pady=(6, 2))

        tree_frm = tb.Frame(left)
        tree_frm.pack(fill=BOTH, expand=YES, padx=4, pady=(0, 4))
        style = ttk.Style()
        style.configure("ImageCheck.Treeview",         rowheight=24, font=("Segoe UI", 9))
        style.configure("ImageCheck.Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self._tree = ttk.Treeview(tree_frm, style="ImageCheck.Treeview",
                                  columns=("cnt",), show="tree headings",
                                  selectmode="browse")
        self._tree.heading("#0",  text="Month / Portion")
        self._tree.heading("cnt", text="Uploaded")
        self._tree.column("#0",   stretch=True, minwidth=150)
        self._tree.column("cnt",  width=72, anchor="center")
        vsb = tb.Scrollbar(tree_frm, orient=VERTICAL,   command=self._tree.yview, bootstyle="round")
        hsb = tb.Scrollbar(tree_frm, orient=HORIZONTAL, command=self._tree.xview, bootstyle="round")
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=RIGHT,  fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        self._tree.pack(fill=BOTH, expand=YES)
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        right = tb.Frame(paned, padding=0)
        paned.add(right, minsize=600)
        rhdr = tb.Frame(right, padding=(8, 4))
        rhdr.pack(fill=X)
        self._lbl_right_title = tb.Label(rhdr,
                                         text="Select a month or portion from the tree",
                                         font=("Segoe UI", 11, "bold"),
                                         bootstyle="secondary")
        self._lbl_right_title.pack(side=LEFT)
        tb.Button(rhdr, text="Refresh", bootstyle="outline-primary",
                  width=10, command=self._load_async).pack(side=RIGHT, padx=4)

        leg = tb.Frame(right, padding=(8, 2))
        leg.pack(fill=X)
        self._make_legend(leg)

        tbl_frm = tb.Frame(right, padding=(4, 0, 4, 4))
        tbl_frm.pack(fill=BOTH, expand=YES)
        tbl_cols = ("portion", "upload", "sap_total",
                    "C", "P", "I", "IL", "NMI", "pct", "status")
        self._table = ttk.Treeview(tbl_frm, columns=tbl_cols,
                                   show="headings", selectmode="browse")
        col_cfg = [
            ("portion",   "Portion",   140, "w"),
            ("upload",    "Uploaded",   72, "center"),
            ("sap_total", "SAP Total",  72, "center"),
            ("C",         "Checked",    66, "center"),
            ("P",         "Pending",    62, "center"),
            ("I",         "Illegal",    60, "center"),
            ("IL",        "Ill.Load",   62, "center"),
            ("NMI",       "No Meter",   72, "center"),
            ("pct",       "Checked %",  80, "center"),
            ("status",    "Status",     90, "center"),
        ]
        for cid, heading, w, anchor in col_cfg:
            self._table.heading(cid, text=heading, anchor=anchor)
            self._table.column(cid, width=w, anchor=anchor, stretch=(cid == "portion"))
        self._table.tag_configure("done",    background="#d4edda", foreground="#155724")
        self._table.tag_configure("partial", background="#fff3cd", foreground="#856404")
        self._table.tag_configure("none",    background="#fde8e8", foreground="#721c24")
        self._table.tag_configure("no_sap",  background="#f0f3f4", foreground="#495057")
        self._table.tag_configure("total",   background="#dbe9ff", foreground="#0a3680",
                                  font=("Segoe UI", 9, "bold"))
        tsb  = tb.Scrollbar(tbl_frm, orient=VERTICAL,   command=self._table.yview, bootstyle="round")
        thsb = tb.Scrollbar(tbl_frm, orient=HORIZONTAL, command=self._table.xview, bootstyle="round")
        self._table.configure(yscrollcommand=tsb.set, xscrollcommand=thsb.set)
        tsb.pack(side=RIGHT,  fill=Y)
        thsb.pack(side=BOTTOM, fill=X)
        self._table.pack(fill=BOTH, expand=YES)

    @staticmethod
    def _make_legend(parent):
        items = [
            ("#27ae60", "All Checked"),
            ("#e67e22", "Partial"),
            ("#e74c3c", "None Checked"),
            ("#7f8c8d", "No SAP Data"),
        ]
        tb.Label(parent, text="Status: ", font=("Segoe UI", 8, "bold")).pack(side=LEFT)
        for color, label in items:
            dot = tk.Canvas(parent, width=13, height=13, highlightthickness=0, bg="#f8f9fa")
            dot.pack(side=LEFT, padx=(4, 1), pady=2)
            dot.create_oval(2, 2, 11, 11, fill=color, outline=color)
            tb.Label(parent, text=label, font=("Segoe UI", 8)).pack(side=LEFT, padx=(0, 8))

    def _open_user_manager(self):
        _UserManagerDialog(self, on_close=self._load_async)

    def _load_async(self):
        self._lbl_status.config(text="Loading...")
        self._tree.delete(*self._tree.get_children())
        self._table.delete(*self._table.get_children())
        for w in self._sources_bar.winfo_children():
            w.destroy()
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _load_worker(self):
        sources = _get_all_db_sources()
        data, loaded, failed = _build_db_data(sources)
        self.after(0, lambda: self._apply_data(data, loaded, failed))

    def _apply_data(self, data, loaded_users, failed_users):
        self._data         = data
        self._loaded_users = loaded_users
        self._failed_users = failed_users
        self._populate_tree()
        self._update_summary_bar()
        self._update_sources_bar()
        n_ok  = len(loaded_users)
        n_err = len(failed_users)
        msg   = f"Loaded {len(data)} month(s)  |  {n_ok} user DB(s)"
        if n_err:
            msg += f"  |  {n_err} unavailable"
        self._lbl_status.config(text=msg)

    def _update_sources_bar(self):
        for w in self._sources_bar.winfo_children():
            w.destroy()
        tb.Label(self._sources_bar, text="Data sources: ",
                 font=("Segoe UI", 8, "bold"), foreground="white",
                 bootstyle="inverse-secondary").pack(side=LEFT)
        for uname in self._loaded_users:
            tb.Label(self._sources_bar, text=f"  {uname}",
                     font=("Segoe UI", 8), foreground="#90ee90",
                     bootstyle="inverse-secondary").pack(side=LEFT, padx=(0, 6))
        for uname, reason in self._failed_users:
            lbl = tb.Label(self._sources_bar, text=f"  {uname} (unavailable)",
                           font=("Segoe UI", 8), foreground="#ffaaaa",
                           bootstyle="inverse-secondary", cursor="hand2")
            lbl.pack(side=LEFT, padx=(0, 6))
            lbl.bind("<Button-1>", lambda _e, u=uname, r=reason:
                     messagebox.showinfo("DB Not Found",
                                         f"User: {u}\nPath: {_db_path_for_user(u)}\n\nReason: {r}",
                                         parent=self))

    def _populate_tree(self):
        self._tree.delete(*self._tree.get_children())
        for mk in sorted(self._data.keys()):
            minfo  = self._data[mk]
            totals = _month_totals(minfo["portions"])
            mtag   = self._status_tag(totals)
            m_iid  = self._tree.insert("", "end", iid=f"M_{mk}",
                                       text=f"  {minfo['label']}",
                                       values=(totals["upload"],),
                                       tags=(mtag,), open=False)
            for portion in sorted(minfo["portions"].keys()):
                pd   = minfo["portions"][portion]
                ptag = self._status_tag(pd)
                self._tree.insert(m_iid, "end", iid=f"P_{mk}_{portion}",
                                  text=f"    {portion}",
                                  values=(pd["upload"],), tags=(ptag,))
        for tag, (fg, bg) in STATUS_COLORS.items():
            self._tree.tag_configure(tag, foreground=fg, background=bg)

    @staticmethod
    def _status_tag(pd):
        sap = pd.get("sap_total", 0)
        if sap == 0:
            return "no_sap"
        checked = pd.get("C", 0)
        if checked == 0:
            return "none"
        if checked >= sap:
            return "done"
        return "partial"

    @staticmethod
    def _pct(checked, total):
        if total == 0:
            return "-"
        return f"{checked / total * 100:.1f}%"

    @staticmethod
    def _status_label(tag):
        return {"done": "Complete", "partial": "Partial",
                "none": "None", "no_sap": "No Data"}.get(tag, "")

    def _on_tree_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        self._table.delete(*self._table.get_children())
        if iid.startswith("M_"):
            self._show_month(iid[2:])
        elif iid.startswith("P_"):
            mk, portion = iid[2:].split("_", 1)
            self._show_portion(mk, portion)

    def _show_month(self, mk):
        minfo = self._data.get(mk)
        if not minfo:
            return
        self._lbl_right_title.config(
            text=f"Month: {minfo['label']}  -  All Portions",
            bootstyle="primary")
        portions = minfo["portions"]
        totals   = _month_totals(portions)
        for portion in sorted(portions.keys()):
            pd  = portions[portion]
            tag = self._status_tag(pd)
            self._table.insert("", "end", values=(
                portion, pd["upload"], pd["sap_total"],
                pd.get("C",  0) or "", pd.get("P",  0) or "",
                pd.get("I",  0) or "", pd.get("IL", 0) or "",
                pd.get("NMI",0) or "",
                self._pct(pd.get("C", 0), pd.get("sap_total", 0)),
                self._status_label(tag),
            ), tags=(tag,))
        t_tag = self._status_tag(totals)
        self._table.insert("", "end", values=(
            f"TOTAL  ({len(portions)} portions)",
            totals["upload"], totals["sap_total"],
            totals.get("C",0), totals.get("P",0),
            totals.get("I",0), totals.get("IL",0), totals.get("NMI",0),
            self._pct(totals.get("C",0), totals.get("sap_total",0)),
            self._status_label(t_tag),
        ), tags=("total",))

    def _show_portion(self, mk, portion):
        minfo = self._data.get(mk)
        if not minfo:
            return
        pd  = minfo["portions"].get(portion, {})
        tag = self._status_tag(pd)
        self._lbl_right_title.config(
            text=f"Month: {minfo['label']}  |  Portion: {portion}",
            bootstyle="primary")
        self._table.insert("", "end", values=(
            portion,
            pd.get("upload",    0), pd.get("sap_total", 0),
            pd.get("C",  0), pd.get("P",  0),
            pd.get("I",  0), pd.get("IL", 0), pd.get("NMI", 0),
            self._pct(pd.get("C", 0), pd.get("sap_total", 0)),
            self._status_label(tag),
        ), tags=(tag,))

    def _update_summary_bar(self):
        for w in self._summary_bar.winfo_children():
            w.destroy()
        grand = {"upload": 0, "sap_total": 0, **{r: 0 for r in REMARK_COLS}}
        for minfo in self._data.values():
            mt = _month_totals(minfo["portions"])
            for k in grand:
                grand[k] += mt.get(k, 0)
        cards = [
            ("Total Uploaded",      grand["upload"],             "primary"),
            ("Total SAP",           grand["sap_total"],          "secondary"),
            ("Checked (C)",         grand["C"],                  "success"),
            ("Pending (P)",         grand["P"],                  "warning"),
            ("Illegal (I/IL)",      grand["I"] + grand["IL"],    "danger"),
            ("No Meter (NMI)",      grand["NMI"],                "info"),
        ]
        for label, val, bs in cards:
            card = tb.Frame(self._summary_bar, padding=(10, 4), bootstyle="light")
            card.pack(side=LEFT, padx=4, pady=2)
            tb.Label(card, text=str(val), font=("Segoe UI", 13, "bold"), bootstyle=bs).pack()
            tb.Label(card, text=label,    font=("Segoe UI", 8), bootstyle="secondary").pack()
