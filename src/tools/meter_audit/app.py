import os
import sys
import json
import time
import base64
import io
import threading
import logging
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox, filedialog

from .constants import DEFAULT_BASE_URL, IMAGE_CACHE_DIR, LOG_DIR
from .client import TomcatAPIClient, SessionExpiredException
from .prefetcher import ImagePrefetcher
from .session_manager import SessionManager
from .commit_worker import BatchCommitWorker
from .ui_dialogs import prompt_password, show_consumer_details_popup
from .ui_queue import ActiveQueueFrame
from .ui_login import LoginFrame


class MeterAuditApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WBSedcl Meter Image Verification Audit Tool")
        self.geometry("1280x780")
        self.minimum_size = (1100, 700)

        # Core Services
        self.api_client = TomcatAPIClient(DEFAULT_BASE_URL)
        self.session_mgr = SessionManager(self.api_client)
        self.prefetcher = ImagePrefetcher(self.api_client)
        self.prefetcher.ui_update_callback = self.on_image_prefetch_done
        self.commit_worker = BatchCommitWorker(self.api_client)

        # State Management
        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {}  # con_id -> {"verification_stat": status, "meter_note": note}
        self.audited_ids = set()
        self.allow_submission_without_lookup = False
        self.telemetry_labels = {}
        self.mru_choices = []

        # Clear local progress file on startup/app restart to prevent stale carry-over
        try:
            startup_progress_path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(startup_progress_path):
                os.remove(startup_progress_path)
        except Exception as e:
            logging.error(f"Failed to clear local progress on startup: {e}")

        # Unified container frame to prevent pack/grid manager conflicts on root
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Show Login Frame
        self.show_login_screen()

    # Session properties proxies for backwards compatibility
    @property
    def session_username(self):
        return self.session_mgr.username

    @property
    def session_token(self):
        return self.session_mgr.token

    @property
    def session_off_code(self):
        return self.session_mgr.off_code

    @property
    def session_off_name(self):
        return self.session_mgr.off_name

    @property
    def session_name(self):
        return self.session_mgr.name

    @property
    def session_designation(self):
        return self.session_mgr.designation

    def show_login_screen(self):
        self.login_frame = LoginFrame(self.main_container, self.on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def on_login_success(self, username, token, off_code, off_name, name, designation):
        self.session_mgr.set_session(username, token, off_code, off_name, name, designation)

        self.login_frame.pack_forget()
        self.login_frame.destroy()

        self.prefetcher.update_config(username, token, off_code)
        self._setup_layout()
        self._bind_hotkeys()

        self.session_mgr.start_keep_alive(
            on_success_callback=lambda: self.after(0, lambda: self.update_status_bar("Keep-alive ping sent to Tomcat server successfully.", "gray60")),
            on_error_callback=lambda msg: self.after(0, lambda: self.update_status_bar(f"Keep-alive ping failed: {msg}", "#ef4444"))
        )

        self.fetch_cascade_mru()

    def logout(self):
        self.session_mgr.clear_session()
        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {}
        self.audited_ids = set()

        self.prefetcher.set_queue([], "", "")
        self.prefetcher.update_config("", "", "")

        self.main_container.pack_forget()
        self.main_container.destroy()

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        self.show_login_screen()

    def handle_api_error(self, e):
        if isinstance(e, SessionExpiredException):
            def show_warning_logout():
                messagebox.showwarning("Session Expired", "Your backend Tomcat session has expired or is invalid (Code 100/600).\nRedirecting to login...")
                self.logout()
            self.after(0, show_warning_logout)
            return True
        return False

    def save_local_progress(self):
        self.session_mgr.save_local_progress(
            mru=self.mru_combo.get(),
            month=self.month_combo.get(),
            year=self.year_combo.get(),
            audited_ids=self.audited_ids,
            audit_decisions=self.audit_decisions
        )

    def load_local_progress(self):
        decisions = self.session_mgr.load_local_progress(
            current_mru=self.mru_combo.get(),
            current_month=self.month_combo.get(),
            current_year=self.year_combo.get()
        )
        if decisions:
            count = 0
            for con_id, decision in decisions.items():
                con_id_str = str(con_id)
                if con_id_str in self.audit_decisions:
                    self.audit_decisions[con_id_str] = decision
                    self.audited_ids.add(con_id_str)
                    self.queue_frame.update_status_badge(con_id_str, decision.get("verification_stat", "C"))
                    count += 1
            if count > 0:
                self.log_to_console(f"Restored {count} decisions from local progress.")
                self.update_stats_dashboard()

    def _setup_layout(self):
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=0)
        self.main_container.grid_columnconfigure(0, weight=0, minsize=450)
        self.main_container.grid_columnconfigure(1, weight=1)

        # LEFT PANEL
        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="#1a1a24", corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_rowconfigure(2, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)

        # Profile Card
        self.profile_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.profile_frm.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkLabel(self.profile_frm, text="User Session Profile", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=10, pady=(8, 2))

        prof_row = ctk.CTkFrame(self.profile_frm, fg_color="transparent")
        prof_row.pack(fill="x", padx=10, pady=(2, 8))
        profile_details = f"Name: {self.session_name} ({self.session_username})\nDesg: {self.session_designation}\nOffice: {self.session_off_name} ({self.session_off_code})"
        self.profile_info_lbl = ctk.CTkLabel(prof_row, text=profile_details, font=ctk.CTkFont(size=11), justify="left", anchor="w")
        self.profile_info_lbl.pack(side="left", padx=5)
        self.logout_btn = ctk.CTkButton(prof_row, text="Logout", height=24, width=60, fg_color="#ef4444", hover_color="#dc2626", font=ctk.CTkFont(size=11, weight="bold"), command=self.logout)
        self.logout_btn.pack(side="right", padx=5, anchor="e")

        # Cascade Card
        self.selector_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.selector_frm.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        self.selector_frm.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(self.selector_frm, text="Month", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=0, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="Year", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=1, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="AI Flag Filter", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=2, padx=6, pady=(6, 0), sticky="w")
        mru_lbl_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        mru_lbl_frm.grid(row=0, column=3, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(mru_lbl_frm, text="MRU (Zone)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(side="left")
        self.mru_spinner_lbl = ctk.CTkLabel(mru_lbl_frm, text="", font=ctk.CTkFont(size=10, slant="italic"), text_color="#10b981")
        self.mru_spinner_lbl.pack(side="left", padx=4)

        self.month_combo = ctk.CTkOptionMenu(self.selector_frm, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.month_combo.set("04")
        self.month_combo.grid(row=1, column=0, padx=4, pady=(2, 6), sticky="ew")

        self.year_combo = ctk.CTkOptionMenu(self.selector_frm, values=["2025", "2026", "2027", "2028"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.year_combo.set("2026")
        self.year_combo.grid(row=1, column=1, padx=4, pady=(2, 6), sticky="ew")

        ai_options = ["Accepted by Reader", "Not Accepted by Reader", "No Reading from AI Engine", "Not under AI Scope"]
        self.aiflag_combo = ctk.CTkOptionMenu(self.selector_frm, values=ai_options, height=26, font=ctk.CTkFont(size=11))
        self.aiflag_combo.set("Accepted by Reader")
        self.aiflag_combo.grid(row=1, column=2, padx=4, pady=(2, 6), sticky="ew")

        self.mru_combo = ctk.CTkOptionMenu(self.selector_frm, values=["None"], height=26, font=ctk.CTkFont(size=11))
        self.mru_combo.set("None")
        self.mru_combo.grid(row=1, column=3, padx=4, pady=(2, 6), sticky="ew")

        slider_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        slider_frm.grid(row=2, column=0, columnspan=2, padx=4, pady=(2, 8), sticky="ew")
        self.pacing_lbl = ctk.CTkLabel(slider_frm, text="Pacing: 0.4s", font=ctk.CTkFont(size=10))
        self.pacing_lbl.pack(side="left", padx=(2, 4))
        self.pacing_slider = ctk.CTkSlider(slider_frm, from_=0.1, to=15.0, number_of_steps=149, height=14, command=self.on_pacing_change)
        self.pacing_slider.set(0.4)
        self.pacing_slider.pack(side="left", fill="x", expand=True)

        self.fetch_queue_btn = ctk.CTkButton(self.selector_frm, text="Fetch Queue", height=26, fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=11, weight="bold"), command=self.fetch_server_queue)
        self.fetch_queue_btn.grid(row=2, column=2, padx=4, pady=(2, 8), sticky="ew")

        self.commit_btn = ctk.CTkButton(self.selector_frm, text="Update", height=26, fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(size=11, weight="bold"), command=self.start_batch_commit)
        self.commit_btn.grid(row=2, column=3, padx=4, pady=(2, 8), sticky="ew")

        settings_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        settings_frm.grid(row=3, column=0, columnspan=4, padx=6, pady=(0, 6), sticky="ew")
        self.submission_toggle = ctk.CTkSwitch(settings_frm, text="Allow Submission Without Lookup", font=ctk.CTkFont(size=11), command=self.toggle_submission_setting)
        self.submission_toggle.deselect()
        self.submission_toggle.pack(side="left", padx=4)

        # Table Container
        self.table_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.table_frm.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        self.table_frm.grid_rowconfigure(1, weight=1)
        self.table_frm.grid_columnconfigure(0, weight=1)

        tbl_hdr = ctk.CTkFrame(self.table_frm, fg_color="transparent")
        tbl_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        self.queue_title = ctk.CTkLabel(tbl_hdr, text="Audit Queue list (0 records)", font=ctk.CTkFont(size=13, weight="bold"))
        self.queue_title.pack(side="left", pady=2)

        self.queue_frame = ActiveQueueFrame(self.table_frm, on_select_callback=self.select_consumer_by_id, on_toggle_callback=self.on_row_checkbox_toggled, fg_color="#1a1a24")
        self.queue_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Stats Dashboard
        self.stats_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.stats_frm.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
        self.stats_progress_lbl = ctk.CTkLabel(self.stats_frm, text="Progress: 0 / 0 (0%)", font=ctk.CTkFont(size=12, weight="bold"))
        self.stats_progress_lbl.pack(anchor="w", padx=12, pady=(8, 2))
        self.progress_bar = ctk.CTkProgressBar(self.stats_frm)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 8))

        grid_frm = ctk.CTkFrame(self.stats_frm, fg_color="transparent")
        grid_frm.pack(fill="x", padx=12, pady=(2, 8))
        grid_frm.columnconfigure((0, 1, 2), weight=1)

        c_frm = ctk.CTkFrame(grid_frm, fg_color="#182721", height=55, corner_radius=6)
        c_frm.grid(row=0, column=0, padx=4, sticky="nsew")
        c_frm.grid_propagate(False)
        c_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(c_frm, text="Correct (C)", font=ctk.CTkFont(size=10), text_color="#a7f3d0").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_correct = ctk.CTkLabel(c_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10b981")
        self.lbl_stat_correct.grid(row=1, column=0)

        il_frm = ctk.CTkFrame(grid_frm, fg_color="#2d2217", height=55, corner_radius=6)
        il_frm.grid(row=0, column=1, padx=4, sticky="nsew")
        il_frm.grid_propagate(False)
        il_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(il_frm, text="Illegible (IL)", font=ctk.CTkFont(size=10), text_color="#fde68a").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_illegible = ctk.CTkLabel(il_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#fbbf24")
        self.lbl_stat_illegible.grid(row=1, column=0)

        o_frm = ctk.CTkFrame(grid_frm, fg_color="#1e2433", height=55, corner_radius=6)
        o_frm.grid(row=0, column=2, padx=4, sticky="nsew")
        o_frm.grid_propagate(False)
        o_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(o_frm, text="Other Defects", font=ctk.CTkFont(size=10), text_color="#dbeafe").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_other = ctk.CTkLabel(o_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#60a5fa")
        self.lbl_stat_other.grid(row=1, column=0)

        # RIGHT PANEL: Rapid-Fire Audit Viewer
        self.right_panel = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.viewer_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.viewer_container.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.viewer_container.grid_rowconfigure(0, weight=1)
        self.viewer_container.grid_rowconfigure(1, weight=0)
        self.viewer_container.grid_columnconfigure(0, weight=1)

        self.image_outer_frm = ctk.CTkFrame(self.viewer_container, fg_color="#1f2937", border_width=1, border_color="gray30", corner_radius=10)
        self.image_outer_frm.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self.image_outer_frm.bind("<Configure>", self.on_image_container_resize)

        self.img_lbl = ctk.CTkLabel(self.image_outer_frm, text="Fetch and select a consumer to display meter image.", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray60")
        self.img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self.image_hud = ctk.CTkFrame(self.image_outer_frm, fg_color="#111827", corner_radius=6)
        self.hud_meter_lbl = ctk.CTkLabel(self.image_hud, text="Meter: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        self.hud_meter_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_pres_lbl = ctk.CTkLabel(self.image_hud, text="Present Reading: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10b981")
        self.hud_pres_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_mrnote_lbl = ctk.CTkLabel(self.image_hud, text="MR Note: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f59e0b")
        self.hud_mrnote_lbl.pack(side="left", expand=True, padx=12, pady=6)

        self.telemetry_hotkey_frm = ctk.CTkFrame(self.viewer_container, fg_color="transparent")
        self.telemetry_hotkey_frm.grid(row=1, column=0, sticky="ew")
        self.telemetry_hotkey_frm.grid_columnconfigure(0, weight=3)
        self.telemetry_hotkey_frm.grid_columnconfigure(1, weight=2)

        self.tel_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.tel_frm.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(self.tel_frm, text="Meter & Consumer Telemetry", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 4))

        fields = [
            ("Consumer ID:", "N/A"), ("Meter No:", "N/A"),
            ("CCC Name:", "N/A"), ("CCC Code:", "N/A"),
            ("Prev Reading:", "N/A"), ("Pres Reading:", "N/A"),
            ("Consumption:", "N/A"), ("Upload Date:", "N/A"),
            ("MR Note:", "N/A"), ("AI Flag:", "N/A")
        ]
        self.telemetry_labels = {}
        for idx, (label_txt, val_txt) in enumerate(fields):
            r = (idx // 2) + 1
            c_label = (idx % 2) * 2
            c_val = c_label + 1
            ctk.CTkLabel(self.tel_frm, text=label_txt, font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=r, column=c_label, sticky="e", padx=(12, 4), pady=2)
            val = ctk.CTkLabel(self.tel_frm, text=val_txt, font=ctk.CTkFont(size=11), anchor="w")
            val.grid(row=r, column=c_val, sticky="w", padx=(4, 12), pady=2)
            self.telemetry_labels[label_txt] = val

        self.btn_view_details = ctk.CTkButton(self.tel_frm, text="🔍 View Consumer Details", font=ctk.CTkFont(size=11, weight="bold"), height=24, fg_color="gray30", hover_color="gray40", command=self.open_consumer_details_popup)
        self.btn_view_details.grid(row=6, column=0, columnspan=4, pady=(6, 8), padx=12, sticky="ew")

        self.hotkey_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.hotkey_frm.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(self.hotkey_frm, text="Rapid-Fire Audit Decisions", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=12, pady=(8, 4))

        hk_btn_frm = ctk.CTkFrame(self.hotkey_frm, fg_color="transparent")
        hk_btn_frm.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.btn_correct = ctk.CTkButton(hk_btn_frm, text="✅ Meter Image Correct (C)", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#064e3b", hover_color="#065f46", height=32, command=lambda: self.set_status("C"))
        self.btn_correct.pack(fill="x", pady=2)

        self.btn_illegible = ctk.CTkButton(hk_btn_frm, text="⚠️ Illegible Image (IL)", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#78350f", hover_color="#92400e", height=32, command=lambda: self.set_status("IL"))
        self.btn_illegible.pack(fill="x", pady=2)

        other_obs = ["Select Other Observations...", "Different Meter No (MM)", "Location Difference (LM)", "Non Meter Image (NMI)", "Mismatch Reading (I)"]
        self.combo_other_obs = ctk.CTkOptionMenu(hk_btn_frm, values=other_obs, height=30, font=ctk.CTkFont(size=11), command=self.on_other_obs_selected)
        self.combo_other_obs.set("Select Other Observations...")
        self.combo_other_obs.pack(fill="x", pady=4)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self.main_container, fg_color="#0f1115", height=24, corner_radius=0)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_lbl = ctk.CTkLabel(self.status_bar, text="Status: Idle", font=ctk.CTkFont(size=11), text_color="gray70")
        self.status_lbl.pack(side="left", padx=12, pady=2)

    def log_to_console(self, msg):
        logging.info(msg)
        print(msg)
        clean_msg = str(msg).replace("──►", "->").replace("🚀", "").replace("⚡", "").strip()
        if len(clean_msg) > 90:
            clean_msg = clean_msg[:87] + "..."
        self.update_status_bar(clean_msg)

    def update_status_bar(self, text, color="gray70"):
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            self.status_lbl.configure(text=f"Status: {text}", text_color=color)

    def on_pacing_change(self, val):
        self.pacing_lbl.configure(text=f"Pacing Interval: {float(val):.1f}s")

    def is_input_focused(self):
        focused = self.focus_get()
        if not focused:
            return False
        cls_name = focused.winfo_class()
        return "Entry" in cls_name or "Text" in cls_name

    def _bind_hotkeys(self):
        self.bind("<F1>", lambda e: not self.is_input_focused() and self.set_status("C"))
        self.bind("c", lambda e: not self.is_input_focused() and self.set_status("C"))
        self.bind("C", lambda e: not self.is_input_focused() and self.set_status("C"))
        self.bind("<F2>", lambda e: not self.is_input_focused() and self.set_status("IL"))
        self.bind("i", lambda e: not self.is_input_focused() and self.set_status("IL"))
        self.bind("I", lambda e: not self.is_input_focused() and self.set_status("IL"))
        self.bind("<F3>", lambda e: not self.is_input_focused() and self.set_status("MM"))
        self.bind("<F4>", lambda e: not self.is_input_focused() and self.set_status("LM"))
        self.bind("<F5>", lambda e: not self.is_input_focused() and self.set_status("NMI"))
        self.bind("<F6>", lambda e: not self.is_input_focused() and self.set_status("I"))
        self.bind("<Down>", lambda e: not self.is_input_focused() and self.next_consumer())
        self.bind("<Up>", lambda e: not self.is_input_focused() and self.prev_consumer())

    def on_cascade_change(self, val):
        self.fetch_cascade_mru()

    def fetch_cascade_mru(self):
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        month = self.month_combo.get()
        year = self.year_combo.get()

        cache_key = f"{off_code}_{month}_{year}"
        if cache_key in self.session_mgr.zones_cache:
            mrus = self.session_mgr.zones_cache[cache_key]
            self.log_to_console(f"Using cached zones/MRUs for {month}/{year}")
            self._update_mru_dropdown(mrus)
            return

        self.mru_combo.configure(values=["Loading..."])
        self.mru_combo.set("Loading...")
        self.mru_spinner_lbl.configure(text="⏳ Fetching...")

        def fetch_task():
            try:
                mrus = self.api_client.fetch_mru(username, token, off_code, month, year)
                if mrus:
                    self.session_mgr.zones_cache[cache_key] = mrus
                    self.session_mgr.save_zones_cache()
                    self.after(0, lambda: self._update_mru_dropdown(mrus))
                else:
                    self.after(0, lambda: self._update_mru_dropdown([]))
            except Exception as e:
                logging.error(f"Failed to fetch MRUs: {e}")
                self.after(0, lambda: self._update_mru_dropdown([]))

        threading.Thread(target=fetch_task, daemon=True).start()

    def _update_mru_dropdown(self, mrus):
        self.mru_spinner_lbl.configure(text="")
        self.mru_choices = mrus
        if mrus:
            self.mru_combo.configure(values=mrus)
            cur = self.mru_combo.get()
            if cur not in mrus:
                self.mru_combo.set(mrus[0])
        else:
            self.mru_combo.configure(values=["None"])
            self.mru_combo.set("None")

    def fetch_server_queue(self):
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        month = self.month_combo.get()
        year = self.year_combo.get()
        mru = self.mru_combo.get()
        ai_flag = self.aiflag_combo.get()

        if mru == "None" or not mru:
            messagebox.showwarning("Validation Error", "Please select a valid MRU (Zone) code first.")
            return

        self.fetch_queue_btn.configure(state="disabled", text="Fetching...")

        def fetch_task():
            try:
                records = self.api_client.fetch_queue(username, token, off_code, month, year, mru, ai_flag)
                self.after(0, lambda: self.load_records_into_memory(records, source="Server"))
            except Exception as e:
                self.after(0, lambda e_str=str(e): messagebox.showerror("Queue Fetch Error", f"Could not retrieve queue:\n{e_str}"))
                self.after(0, lambda: self.fetch_queue_btn.configure(state="normal", text="Fetch Queue"))

        threading.Thread(target=fetch_task, daemon=True).start()

    def load_queue_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Queue JSON File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            records = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        records.append(item)
                    else:
                        records.append({
                            "con_id": str(item),
                            "meter_no": "Unknown",
                            "smrd": self.month_combo.get(),
                            "ccc_code": self.session_off_code,
                            "ccc_name": "KUSHIDA CCC"
                        })
            else:
                raise Exception("JSON root must be a list of records or consumer IDs.")

            self.load_records_into_memory(records, source=f"File ({os.path.basename(file_path)})")
        except Exception as e:
            messagebox.showerror("File Error", f"Could not parse selected file:\n{str(e)}")

    def load_records_into_memory(self, records, source=""):
        self.queue_records = records
        self.current_index = -1
        self.audit_decisions.clear()
        self.audited_ids = set()

        for rec in records:
            con_id = rec.get("con_id")
            if con_id:
                self.audit_decisions[str(con_id)] = {"verification_stat": "C", "meter_note": " "}

        self.queue_title.configure(text=f"Audit Queue list ({len(records)} records)")
        self.log_to_console(f"Loaded {len(records)} records in-memory from {source}.")

        self.queue_frame.populate_queue(
            records,
            audited_ids=self.audited_ids,
            audit_decisions=self.audit_decisions,
            allow_without_lookup=self.allow_submission_without_lookup
        )

        self.load_local_progress()
        self.fetch_queue_btn.configure(state="normal", text="Fetch Queue")
        self.progress_bar.set(0)
        self.update_stats_dashboard()

        if records:
            first_con_id = records[0].get("con_id")
            self.select_consumer_by_id(first_con_id)
            self.prefetcher.set_queue(records, default_smrd="", default_zone=self.mru_combo.get())
        else:
            self._clear_viewer()

    def select_consumer_by_id(self, con_id):
        idx = next((i for i, r in enumerate(self.queue_records) if r.get("con_id") == con_id), -1)
        if idx == -1:
            return

        self.current_index = idx
        self.queue_frame.highlight_row(con_id)
        self.prefetcher.set_active_index(idx)
        self.update_active_image()
        self.update_active_telemetry()

    def update_active_image(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            self._clear_viewer()
            return

        record = self.queue_records[self.current_index]
        con_id = record.get("con_id")

        self.img_lbl.configure(image="", text="⏳ Loading image...")
        self.img_lbl.image = None

        cached_img = self.prefetcher.get_image(con_id)
        if cached_img == "error":
            self.img_lbl.configure(image=None, text="Error fetching meter image from server.")
        elif cached_img is None:
            self.img_lbl.configure(image=None, text="Prefetching image... Please wait.")
            self.prefetcher.trigger_prefetch()

            def fetch_inline_task():
                try:
                    conn_str = record.get("connection_string", [])
                    if conn_str and isinstance(conn_str, list) and "URL" in conn_str[0]:
                        photo_url = conn_str[0]["URL"]
                    else:
                        photo_url = self.prefetcher._build_fallback_url(
                            con_id, record.get("smrd", record.get("smrdn", "")), self.mru_combo.get()
                        )

                    import hashlib
                    url_hash = hashlib.md5(photo_url.encode('utf-8')).hexdigest()
                    local_path = os.path.join(IMAGE_CACHE_DIR, f"{url_hash}.jpg")

                    pil_img = None
                    if os.path.exists(local_path):
                        try:
                            with open(local_path, "rb") as f_img:
                                img_bytes = f_img.read()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            pil_img.verify()
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        except Exception:
                            try:
                                os.remove(local_path)
                            except Exception:
                                pass
                            pil_img = None

                    if pil_img is None:
                        img_b64 = self.api_client.fetch_image_base64(self.session_username, self.session_token, self.session_off_code, photo_url)
                        if img_b64:
                            img_bytes = base64.b64decode(img_b64)
                            try:
                                with open(local_path, "wb") as f_img:
                                    f_img.write(img_bytes)
                            except Exception as fe:
                                logging.warning(f"Failed to write image to disk cache: {fe}")
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        else:
                            raise Exception("Null image")

                    if pil_img:
                        pil_img = self.prefetcher._downscale_image(pil_img, max_size=1024)
                        with self.prefetcher.cache_lock:
                            self.prefetcher.image_cache[con_id] = pil_img

                        with self.prefetcher.lock:
                            active_con = self.queue_records[self.current_index].get("con_id") if self.queue_records else None

                        if active_con == con_id:
                            self.after(0, self.update_active_image)
                except Exception as e:
                    if self.handle_api_error(e):
                        return
                    with self.prefetcher.cache_lock:
                        self.prefetcher.image_cache[con_id] = "error"
                    self.after(0, lambda: self.img_lbl.configure(image=None, text=f"Failed to fetch image: {str(e)}"))

            threading.Thread(target=fetch_inline_task, daemon=True).start()
        else:
            self._render_image(cached_img)

    def on_image_prefetch_done(self, con_id):
        if 0 <= self.current_index < len(self.queue_records):
            active_con_id = self.queue_records[self.current_index].get("con_id")
            if active_con_id == con_id:
                self.after(0, self.update_active_image)

    def _render_image(self, pil_img):
        container_w = self.image_outer_frm.winfo_width()
        container_h = self.image_outer_frm.winfo_height()
        if container_w <= 10 or container_h <= 10:
            container_w = 600
            container_h = 450

        target_w = container_w - 20
        target_h = container_h - 20
        w, h = pil_img.size
        scale = min(target_w / w, target_h / h)
        new_w = max(int(w * scale), 10)
        new_h = max(int(h * scale), 10)

        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img

    def on_image_container_resize(self, event):
        if 0 <= self.current_index < len(self.queue_records):
            con_id = self.queue_records[self.current_index].get("con_id")
            cached_img = self.prefetcher.get_image(con_id)
            if cached_img and cached_img != "error":
                self._render_image(cached_img)

    def update_active_telemetry(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            return

        rec = self.queue_records[self.current_index]
        con_id = str(rec.get("con_id", "N/A"))

        self.telemetry_labels["Consumer ID:"].configure(text=con_id)
        self.telemetry_labels["Meter No:"].configure(text=str(rec.get("meter_no", "N/A")))
        self.telemetry_labels["CCC Name:"].configure(text=str(rec.get("ccc_name", "N/A")))
        self.telemetry_labels["CCC Code:"].configure(text=str(rec.get("ccc_code", "N/A")))
        self.telemetry_labels["Prev Reading:"].configure(text=str(rec.get("previous_reading", "N/A")))
        self.telemetry_labels["Pres Reading:"].configure(text=str(rec.get("present_reading", "N/A")))

        try:
            prev = float(rec.get("previous_reading", 0))
            pres = float(rec.get("present_reading", 0))
            diff = pres - prev
            self.telemetry_labels["Consumption:"].configure(text=f"{diff:.2f}")
        except Exception:
            self.telemetry_labels["Consumption:"].configure(text="N/A")

        raw_note = ""
        for key in ["mr_note", "mrnote", "mr_remark", "mrremark", "remarks", "remark", "note", "reader_note", "readernote", "mr_note_desc", "mrnote_desc"]:
            val = rec.get(key)
            if val is not None:
                raw_note = str(val).strip()
                if raw_note:
                    break
        mr_note = raw_note if raw_note else "N/A"

        self.telemetry_labels["Upload Date:"].configure(text=str(rec.get("upload_date", "N/A")))
        self.telemetry_labels["MR Note:"].configure(text=mr_note)
        self.telemetry_labels["AI Flag:"].configure(text=str(rec.get("aiflag", rec.get("ai_flag", "N/A"))))

        self.hud_meter_lbl.configure(text=f"Meter: {rec.get('meter_no', 'N/A')}")
        self.hud_pres_lbl.configure(text=f"Present Rdg: {rec.get('present_reading', 'N/A')}")
        self.hud_mrnote_lbl.configure(text=f"MR Note: {mr_note}")
        self.image_hud.place(relx=0.5, rely=0.9, relwidth=0.92, relheight=0.12, anchor="center")
        self.image_hud.lift()

    def _clear_viewer(self):
        self.img_lbl.configure(image=None, text="Fetch and select a consumer to display meter image.")
        for lbl in self.telemetry_labels.values():
            lbl.configure(text="N/A")
        self.image_hud.place_forget()

    def on_row_checkbox_toggled(self, con_id):
        chk_var = self.queue_frame.checkbox_vars.get(str(con_id))
        if chk_var:
            val = chk_var.get()
            self.set_status_for_con(con_id, val)

    def set_status(self, status):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            return
        con_id = self.queue_records[self.current_index].get("con_id")
        self.set_status_for_con(con_id, status)
        self.after(50, self.next_consumer)

    def set_status_for_con(self, con_id, status):
        con_id_str = str(con_id)
        if con_id_str not in self.audit_decisions:
            self.audit_decisions[con_id_str] = {"verification_stat": "C", "meter_note": " "}

        self.audit_decisions[con_id_str]["verification_stat"] = status
        self.queue_frame.update_status_badge(con_id_str, status)
        self.log_to_console(f"Consumer ID {con_id_str} flagged locally ──► {status}")

        self.audited_ids.add(con_id_str)
        self.update_stats_dashboard()
        self.save_local_progress()

    def on_other_obs_selected(self, val):
        if val == "Select Other Observations...":
            return
        mapping = {
            "Different Meter No (MM)": "MM",
            "Location Difference (LM)": "LM",
            "Non Meter Image (NMI)": "NMI",
            "Mismatch Reading (I)": "I"
        }
        code = mapping.get(val)
        if code:
            self.set_status(code)
        self.combo_other_obs.set("Select Other Observations...")

    def update_stats_dashboard(self):
        total = len(self.queue_records)
        audited = len(self.audited_ids)
        correct = 0
        illegible = 0
        other = 0

        for rec in self.queue_records:
            cid = str(rec.get("con_id"))
            if self.allow_submission_without_lookup or cid in self.audited_ids:
                dec = self.audit_decisions.get(cid, {"verification_stat": "C"})
                stat = dec.get("verification_stat", "C")
                if stat == "IL":
                    illegible += 1
                elif stat in ("MM", "LM", "NMI", "I"):
                    other += 1
                else:
                    correct += 1

        pct = int((audited / total) * 100) if total > 0 else 0
        self.stats_progress_lbl.configure(text=f"Progress: {audited} / {total} ({pct}%)")
        self.progress_bar.set(audited / total if total > 0 else 0)
        self.lbl_stat_correct.configure(text=str(correct))
        self.lbl_stat_illegible.configure(text=str(illegible))
        self.lbl_stat_other.configure(text=str(other))
        self.update_button_state()

    def open_consumer_details_popup(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            messagebox.showerror("Error", "No consumer selected.")
            return
        con_id = self.queue_records[self.current_index].get("con_id")
        if con_id:
            show_consumer_details_popup(self, self.api_client, self.session_username, self.session_token, self.session_off_code, con_id)

    def next_consumer(self):
        if not self.queue_records:
            return
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            next_idx = self.current_index + 1
            if next_idx < len(self.queue_records):
                next_con_id = self.queue_records[next_idx].get("con_id")
                self.select_consumer_by_id(next_con_id)
            else:
                self.log_to_console("End of queue reached.")

    def prev_consumer(self):
        if not self.queue_records:
            return
        if self.current_index > 0:
            prev_idx = self.current_index - 1
            prev_con_id = self.queue_records[prev_idx].get("con_id")
            self.select_consumer_by_id(prev_con_id)

    def start_batch_commit(self):
        if not self.queue_records:
            messagebox.showwarning("Commit Blocked", "No records loaded in queue to commit.")
            return

        if self.commit_worker.is_committing:
            if not self.commit_worker.cancel_requested:
                self.commit_worker.cancel()
                self.commit_btn.configure(state="disabled", text="Stopping...")
                self.log_to_console("🛑 Cancellation requested. Safely aborting remaining upload tasks...")
            return

        confirm = messagebox.askyesno("Confirm Batch Update", f"Are you sure you want to update verification decisions for all {len(self.queue_records)} records to the backend Tomcat server?")
        if not confirm:
            return

        self.commit_btn.configure(text="Cancel Update", fg_color="#ef4444", hover_color="#dc2626")
        self.fetch_queue_btn.configure(state="disabled")
        self.set_selectors_state("disabled")

        self.commit_worker.start(
            records=self.queue_records,
            decisions=self.audit_decisions,
            audited_ids=self.audited_ids,
            allow_submission_without_lookup=self.allow_submission_without_lookup,
            session_username=self.session_username,
            session_token=self.session_token,
            session_off_code=self.session_off_code,
            acc_month=self.month_combo.get(),
            acc_year=self.year_combo.get(),
            pacing=float(self.pacing_slider.get()),
            on_log=self.log_to_console,
            on_progress=lambda p: self.after(0, lambda: self.progress_bar.set(p)),
            on_success_record=lambda cid: self.session_mgr.remove_from_local_progress(cid),
            on_session_expired=self.handle_api_error,
            on_complete=self._on_commit_complete
        )

    def _on_commit_complete(self, success_count, failure_count, total, was_empty=False, cancelled=False):
        def _reset_ui():
            self.commit_btn.configure(state="normal", text="Update", fg_color="#10b981", hover_color="#059669")
            self.fetch_queue_btn.configure(state="normal")
            self.set_selectors_state("normal")
            if was_empty:
                messagebox.showwarning("No Audited Records", "No manually audited records were found. Please mark/audit records first, or enable 'Allow Submission Without Lookup' in the settings.")
            elif cancelled:
                processed = success_count + failure_count
                messagebox.showwarning("Upload Cancelled", f"Batch upload was aborted by user.\n\nSuccessfully updated: {success_count}\nRemaining: {total - processed}")
            else:
                messagebox.showinfo("Batch Execution Done", f"Batch upload finished.\n\nSuccess: {success_count}\nFailures: {failure_count}")
        self.after(0, _reset_ui)

    def toggle_submission_setting(self):
        current_switch_state = self.submission_toggle.get()
        if current_switch_state == 1:
            self.submission_toggle.deselect()
        else:
            self.submission_toggle.select()

        def on_verified(result):
            if result is True:
                if current_switch_state == 1:
                    self.submission_toggle.select()
                    self.allow_submission_without_lookup = True
                    self.log_to_console("Security Settings: Enabled submission without lookup.")
                else:
                    self.submission_toggle.deselect()
                    self.allow_submission_without_lookup = False
                    self.log_to_console("Security Settings: Disabled submission without lookup.")
                self.refresh_unaudited_rows()
                self.update_stats_dashboard()

        prompt_password(self, on_verified)

    def set_selectors_state(self, state):
        self.month_combo.configure(state=state)
        self.year_combo.configure(state=state)
        self.aiflag_combo.configure(state=state)
        self.mru_combo.configure(state=state)

    def refresh_unaudited_rows(self):
        for rec in self.queue_records:
            con_id_str = str(rec.get("con_id"))
            if con_id_str not in self.audited_ids:
                if self.allow_submission_without_lookup:
                    if con_id_str in self.queue_frame.checkbox_vars:
                        self.queue_frame.checkbox_vars[con_id_str].set("C")
                    if con_id_str in self.queue_frame.badge_labels:
                        self.queue_frame.badge_labels[con_id_str].configure(text="Approved", bg="#064e3b", fg="#10b981")
                else:
                    if con_id_str in self.queue_frame.checkbox_vars:
                        self.queue_frame.checkbox_vars[con_id_str].set("")
                    if con_id_str in self.queue_frame.badge_labels:
                        self.queue_frame.badge_labels[con_id_str].configure(text="Pending", bg="#374151", fg="#9ca3af")

    def update_button_state(self):
        if self.commit_worker.is_committing:
            return
        if self.allow_submission_without_lookup or len(self.audited_ids) > 0:
            self.commit_btn.configure(state="normal")
        else:
            self.commit_btn.configure(state="disabled")
