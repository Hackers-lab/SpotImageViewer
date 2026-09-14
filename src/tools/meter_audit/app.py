import os
import sys
import json
import time
import base64
import io
import threading
import queue
import logging
import requests
from PIL import Image, ImageTk
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

from .constants import DEFAULT_BASE_URL, DEFAULT_USER, DEFAULT_OFF_CODE, IMAGE_CACHE_DIR, LOG_DIR
from .client import TomcatAPIClient, SessionExpiredException
from .prefetcher import ImagePrefetcher
from .ui_queue import ActiveQueueFrame
from .ui_login import LoginFrame

class MeterAuditApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WBSedcl Meter Image Verification Audit Tool")
        self.geometry("1280x780")
        self.minimum_size = (1100, 700)
        
        # State Management
        self.api_client = TomcatAPIClient(DEFAULT_BASE_URL)
        self.prefetcher = ImagePrefetcher(self.api_client)
        self.prefetcher.ui_update_callback = self.on_image_prefetch_done

        # Session properties
        self.session_username = ""
        self.session_token = ""
        self.session_off_code = ""
        self.session_off_name = ""
        self.session_name = ""
        self.session_designation = ""

        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {} # con_id -> {"verification_stat": status, "meter_note": note}
        self.is_committing = False
        self.audited_ids = set()
        self.allow_submission_without_lookup = False # Settings security flag
        self.cancel_requested = False
        self.telemetry_labels = {}
        self.keep_alive_active = False
        self.keep_alive_thread = None

        # Zones persistent cache
        self.zones_cache_file = os.path.join(LOG_DIR, "zones_cache.json")
        self.zones_cache = self.load_zones_cache()

        # Clear local progress file on startup/app restart to prevent stale carry-over
        try:
            startup_progress_path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(startup_progress_path):
                os.remove(startup_progress_path)
        except Exception as e:
            logging.error(f"Failed to clear local progress on startup: {e}")

        # Load cascade choices on startup asynchronously
        self.smrd_choices = []
        self.mru_choices = []

        # Unified container frame to prevent pack/grid manager conflicts on root
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Show Login Frame
        self.show_login_screen()

    def load_zones_cache(self):
        try:
            if os.path.exists(self.zones_cache_file):
                with open(self.zones_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load zones cache: {e}")
        return {}

    def save_zones_cache(self):
        try:
            os.makedirs(os.path.dirname(self.zones_cache_file), exist_ok=True)
            with open(self.zones_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.zones_cache, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save zones cache: {e}")

    def show_login_screen(self):
        self.login_frame = LoginFrame(self.main_container, self.on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def on_login_success(self, username, token, off_code, off_name, name, designation):
        self.session_username = username
        self.session_token = token
        self.session_off_code = off_code
        self.session_off_name = off_name
        self.session_name = name
        self.session_designation = designation

        self.login_frame.pack_forget()
        self.login_frame.destroy()

        # Update Prefetcher configuration
        self.prefetcher.update_config(username, token, off_code)

        # Setup layout and bind hotkeys
        self._setup_layout()
        self._bind_hotkeys()

        # Start keep-alive timer
        self.start_keep_alive_timer()

        # Fetch MRUs automatically
        self.fetch_cascade_mru()

    def logout(self):
        self.stop_keep_alive_timer()
        self.session_username = ""
        self.session_token = ""
        self.session_off_code = ""
        self.session_off_name = ""
        self.session_name = ""
        self.session_designation = ""

        self.queue_records = []
        self.current_index = -1
        self.audit_decisions = {}
        self.audited_ids = set()

        # Clear prefetch queue
        self.prefetcher.set_queue([], "", "")
        self.prefetcher.update_config("", "", "")

        # Destroy everything inside the main container to wipe out all grid layouts and configurations
        self.main_container.pack_forget()
        self.main_container.destroy()

        # Re-create a fresh container frame for packing the login frame
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

    def start_keep_alive_timer(self):
        self.stop_keep_alive_timer()
        self.keep_alive_active = True
        self.keep_alive_thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self.keep_alive_thread.start()
        self.log_to_console("Session keep-alive ping worker started.")

    def stop_keep_alive_timer(self):
        self.keep_alive_active = False

    def _keep_alive_loop(self):
        while self.keep_alive_active:
            # Sleep 300 seconds (5 minutes) in small steps to react quickly to shutdown
            for _ in range(300):
                if not self.keep_alive_active:
                    return
                time.sleep(1)
            
            if not self.session_username or not self.session_token:
                continue
                
            try:
                logging.info("Sending session keep-alive ping to Tomcat server...")
                self.api_client.verify_token(self.session_username, self.session_token)
                self.after(0, lambda: self.update_status_bar("Keep-alive ping sent to Tomcat server successfully.", "gray60"))
            except Exception as e:
                logging.warning(f"Session keep-alive ping failed: {e}")
                self.after(0, lambda msg=str(e): self.update_status_bar(f"Keep-alive ping failed: {msg}", "#ef4444"))

    def save_local_progress(self):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            saved_decisions = {}
            for cid in self.audited_ids:
                if cid in self.audit_decisions:
                    saved_decisions[cid] = self.audit_decisions[cid]
            
            payload = {
                "mru": self.mru_combo.get(),
                "month": self.month_combo.get(),
                "year": self.year_combo.get(),
                "decisions": saved_decisions
            }
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save local progress: {e}")

    def load_local_progress(self):
        try:
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    payload = json.load(f)
                
                if isinstance(payload, dict) and "decisions" in payload:
                    file_mru = payload.get("mru")
                    file_month = payload.get("month")
                    file_year = payload.get("year")
                    
                    cur_mru = self.mru_combo.get()
                    cur_month = self.month_combo.get()
                    cur_year = self.year_combo.get()
                    
                    # Verify metadata match
                    if file_mru == cur_mru and file_month == cur_month and file_year == cur_year:
                        saved = payload["decisions"]
                        count = 0
                        for con_id, decision in saved.items():
                            con_id_str = str(con_id)
                            if con_id_str in self.audit_decisions:
                                self.audit_decisions[con_id_str] = decision
                                self.audited_ids.add(con_id_str)
                                self.queue_frame.update_status_badge(con_id_str, decision.get("verification_stat", "C"))
                                count += 1
                        if count > 0:
                            self.log_to_console(f"Restored {count} decisions from local progress.")
                            self.update_stats_dashboard()
                    else:
                        # Clear file if it's for a different zone or parameters
                        self.log_to_console("Local progress is for a different zone/period. Clearing progress file.")
                        try:
                            os.remove(path)
                        except Exception:
                            pass
        except Exception as e:
            logging.error(f"Failed to load local progress: {e}")

    def remove_from_local_progress(self, con_id):
        try:
            con_id_str = str(con_id)
            path = os.path.join(LOG_DIR, "local_progress.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    payload = json.load(f)
                if isinstance(payload, dict) and "decisions" in payload:
                    if con_id_str in payload["decisions"]:
                        del payload["decisions"][con_id_str]
                        with open(path, "w") as f:
                            json.dump(payload, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to remove {con_id} from local progress: {e}")

    def _setup_layout(self):
        # Configure Grid Rows and Columns on main_container
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=0) # Bottom status bar row
        self.main_container.grid_columnconfigure(0, weight=0, minsize=450) # Left panel width
        self.main_container.grid_columnconfigure(1, weight=1)              # Right panel takes remaining

        # ----------------------------------------------------
        # LEFT PANEL: Interactive Workspace
        # ----------------------------------------------------
        self.left_panel = ctk.CTkFrame(self.main_container, fg_color="#1a1a24", corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        # Left Panel Subgrid layout
        self.left_panel.grid_rowconfigure(2, weight=1) # Queue table takes extra space
        self.left_panel.grid_columnconfigure(0, weight=1)

        # 1. User Profile Status Card
        self.profile_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.profile_frm.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        
        profile_title = ctk.CTkLabel(self.profile_frm, text="User Session Profile", font=ctk.CTkFont(size=13, weight="bold"))
        profile_title.pack(anchor="w", padx=10, pady=(8, 2))

        prof_row = ctk.CTkFrame(self.profile_frm, fg_color="transparent")
        prof_row.pack(fill="x", padx=10, pady=(2, 8))

        profile_details = f"Name: {self.session_name} ({self.session_username})\nDesg: {self.session_designation}\nOffice: {self.session_off_name} ({self.session_off_code})"
        self.profile_info_lbl = ctk.CTkLabel(prof_row, text=profile_details, font=ctk.CTkFont(size=11), justify="left", anchor="w")
        self.profile_info_lbl.pack(side="left", padx=5)

        self.logout_btn = ctk.CTkButton(prof_row, text="Logout", height=24, width=60, fg_color="#ef4444", hover_color="#dc2626", font=ctk.CTkFont(size=11, weight="bold"), command=self.logout)
        self.logout_btn.pack(side="right", padx=5, anchor="e")

        # 2. Selector Cascade Card (Unified Top Filters & Action Row)
        self.selector_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.selector_frm.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        self.selector_frm.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Row 0: Labels
        ctk.CTkLabel(self.selector_frm, text="Month", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=0, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="Year", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=1, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(self.selector_frm, text="AI Flag Filter", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").grid(row=0, column=2, padx=6, pady=(6, 0), sticky="w")
        
        mru_lbl_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        mru_lbl_frm.grid(row=0, column=3, padx=6, pady=(6, 0), sticky="w")
        ctk.CTkLabel(mru_lbl_frm, text="MRU (Zone)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(side="left")
        self.mru_spinner_lbl = ctk.CTkLabel(mru_lbl_frm, text="", font=ctk.CTkFont(size=10, slant="italic"), text_color="#10b981")
        self.mru_spinner_lbl.pack(side="left", padx=4)

        # Row 1: Option Menus
        self.month_combo = ctk.CTkOptionMenu(self.selector_frm, values=["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.month_combo.set("04")
        self.month_combo.grid(row=1, column=0, padx=4, pady=(2, 6), sticky="ew")

        self.year_combo = ctk.CTkOptionMenu(self.selector_frm, values=["2025", "2026", "2027", "2028"], height=26, font=ctk.CTkFont(size=11), command=self.on_cascade_change)
        self.year_combo.set("2026")
        self.year_combo.grid(row=1, column=1, padx=4, pady=(2, 6), sticky="ew")

        ai_options = [
            "Accepted by Reader",
            "Not Accepted by Reader",
            "No Reading from AI Engine",
            "Not under AI Scope"
        ]
        self.aiflag_combo = ctk.CTkOptionMenu(self.selector_frm, values=ai_options, height=26, font=ctk.CTkFont(size=11))
        self.aiflag_combo.set("Accepted by Reader")
        self.aiflag_combo.grid(row=1, column=2, padx=4, pady=(2, 6), sticky="ew")

        self.mru_combo = ctk.CTkOptionMenu(self.selector_frm, values=["None"], height=26, font=ctk.CTkFont(size=11))
        self.mru_combo.set("None")
        self.mru_combo.grid(row=1, column=3, padx=4, pady=(2, 6), sticky="ew")

        # Row 2: Slider & Actions
        slider_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        slider_frm.grid(row=2, column=0, columnspan=2, padx=4, pady=(2, 8), sticky="ew")
        
        self.pacing_lbl = ctk.CTkLabel(slider_frm, text="Pacing: 0.4s", font=ctk.CTkFont(size=10))
        self.pacing_lbl.pack(side="left", padx=(2, 4))
        
        self.pacing_slider = ctk.CTkSlider(slider_frm, from_=0.1, to=15.0, number_of_steps=149, height=14, command=self.on_pacing_change)
        self.pacing_slider.set(0.4)
        self.pacing_slider.pack(side="left", fill="x", expand=True)

        self.fetch_queue_btn = ctk.CTkButton(
            self.selector_frm, 
            text="Fetch Queue", 
            height=26, 
            fg_color="#2563eb", 
            hover_color="#1d4ed8", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            command=self.fetch_server_queue
        )
        self.fetch_queue_btn.grid(row=2, column=2, padx=4, pady=(2, 8), sticky="ew")

        self.commit_btn = ctk.CTkButton(
            self.selector_frm, 
            text="Update", 
            height=26, 
            fg_color="#10b981", 
            hover_color="#059669", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            command=self.start_batch_commit
        )
        self.commit_btn.grid(row=2, column=3, padx=4, pady=(2, 8), sticky="ew")

        # Row 3: Security & Submission Settings
        settings_frm = ctk.CTkFrame(self.selector_frm, fg_color="transparent")
        settings_frm.grid(row=3, column=0, columnspan=4, padx=6, pady=(0, 6), sticky="ew")
        
        self.submission_toggle = ctk.CTkSwitch(
            settings_frm,
            text="Allow Submission Without Lookup",
            font=ctk.CTkFont(size=11),
            command=self.toggle_submission_setting
        )
        self.submission_toggle.deselect()  # Unchecked by default
        self.submission_toggle.pack(side="left", padx=4)

        # 3. Active Queue Table Container
        self.table_frm = ctk.CTkFrame(self.left_panel, fg_color="#23232f", corner_radius=8)
        self.table_frm.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        self.table_frm.grid_rowconfigure(1, weight=1)
        self.table_frm.grid_columnconfigure(0, weight=1)

        # Table Header
        tbl_hdr = ctk.CTkFrame(self.table_frm, fg_color="transparent")
        tbl_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))
        
        self.queue_title = ctk.CTkLabel(tbl_hdr, text="Audit Queue list (0 records)", font=ctk.CTkFont(size=13, weight="bold"))
        self.queue_title.pack(side="left", pady=2)

        # Active Queue Scrollable List Frame
        self.queue_frame = ActiveQueueFrame(
            self.table_frm, 
            on_select_callback=self.select_consumer_by_id,
            on_toggle_callback=self.on_row_checkbox_toggled,
            fg_color="#1a1a24"
        )
        self.queue_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # 4. Audit Progress & Statistics Dashboard (Replaces bottom logs/commit card)
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
        
        # Correct Stat Panel
        c_frm = ctk.CTkFrame(grid_frm, fg_color="#182721", height=55, corner_radius=6)
        c_frm.grid(row=0, column=0, padx=4, sticky="nsew")
        c_frm.grid_propagate(False)
        c_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(c_frm, text="Correct (C)", font=ctk.CTkFont(size=10), text_color="#a7f3d0").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_correct = ctk.CTkLabel(c_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10b981")
        self.lbl_stat_correct.grid(row=1, column=0)
        
        # Illegible Stat Panel
        il_frm = ctk.CTkFrame(grid_frm, fg_color="#2d2217", height=55, corner_radius=6)
        il_frm.grid(row=0, column=1, padx=4, sticky="nsew")
        il_frm.grid_propagate(False)
        il_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(il_frm, text="Illegible (IL)", font=ctk.CTkFont(size=10), text_color="#fde68a").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_illegible = ctk.CTkLabel(il_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#fbbf24")
        self.lbl_stat_illegible.grid(row=1, column=0)
        
        # Other Defects Stat Panel
        o_frm = ctk.CTkFrame(grid_frm, fg_color="#1e2433", height=55, corner_radius=6)
        o_frm.grid(row=0, column=2, padx=4, sticky="nsew")
        o_frm.grid_propagate(False)
        o_frm.columnconfigure(0, weight=1)
        ctk.CTkLabel(o_frm, text="Other Defects", font=ctk.CTkFont(size=10), text_color="#dbeafe").grid(row=0, column=0, pady=(2, 0))
        self.lbl_stat_other = ctk.CTkLabel(o_frm, text="0", font=ctk.CTkFont(size=16, weight="bold"), text_color="#60a5fa")
        self.lbl_stat_other.grid(row=1, column=0)

        # ----------------------------------------------------
        # RIGHT PANEL: Rapid-Fire Audit Viewer
        # ----------------------------------------------------
        self.right_panel = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=0)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        
        self.right_panel.grid_rowconfigure(0, weight=1) # Image container takes maximum space
        self.right_panel.grid_columnconfigure(0, weight=1)

        # Main vertical container in right panel
        self.viewer_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.viewer_container.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        
        self.viewer_container.grid_rowconfigure(0, weight=1) # Image container
        self.viewer_container.grid_rowconfigure(1, weight=0) # Telemetry & Hotkeys
        self.viewer_container.grid_columnconfigure(0, weight=1)

        # 1. Image Container Frame
        self.image_outer_frm = ctk.CTkFrame(self.viewer_container, fg_color="#1f2937", border_width=1, border_color="gray30", corner_radius=10)
        self.image_outer_frm.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        self.image_outer_frm.bind("<Configure>", self.on_image_container_resize)

        self.img_lbl = ctk.CTkLabel(self.image_outer_frm, text="Fetch and select a consumer to display meter image.", font=ctk.CTkFont(size=14, slant="italic"), text_color="gray60")
        self.img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Semi-transparent HUD overlay on image container
        self.image_hud = ctk.CTkFrame(self.image_outer_frm, fg_color="#111827", corner_radius=6)
        self.hud_meter_lbl = ctk.CTkLabel(self.image_hud, text="Meter: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
        self.hud_meter_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_pres_lbl = ctk.CTkLabel(self.image_hud, text="Present Reading: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10b981")
        self.hud_pres_lbl.pack(side="left", expand=True, padx=12, pady=6)
        self.hud_mrnote_lbl = ctk.CTkLabel(self.image_hud, text="MR Note: N/A", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f59e0b")
        self.hud_mrnote_lbl.pack(side="left", expand=True, padx=12, pady=6)

        # 2. Telemetry and Hotkeys Split Row
        self.telemetry_hotkey_frm = ctk.CTkFrame(self.viewer_container, fg_color="transparent")
        self.telemetry_hotkey_frm.grid(row=1, column=0, sticky="ew")
        self.telemetry_hotkey_frm.grid_columnconfigure(0, weight=3)
        self.telemetry_hotkey_frm.grid_columnconfigure(1, weight=2)

        # 2a. Telemetry Card
        self.tel_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.tel_frm.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        
        tel_title = ctk.CTkLabel(self.tel_frm, text="Meter & Consumer Telemetry", font=ctk.CTkFont(size=13, weight="bold"))
        tel_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 4))

        # Metadata grid fields
        self.telemetry_labels = {}
        fields = [
            ("Consumer ID:", "N/A"), ("Meter No:", "N/A"),
            ("CCC Name:", "N/A"), ("CCC Code:", "N/A"),
            ("Prev Reading:", "N/A"), ("Pres Reading:", "N/A"),
            ("Consumption:", "N/A"), ("Upload Date:", "N/A"),
            ("MR Note:", "N/A"), ("AI Flag:", "N/A")
        ]
        
        for idx, (label_txt, val_txt) in enumerate(fields):
            r = (idx // 2) + 1
            c_label = (idx % 2) * 2
            c_val = c_label + 1
            
            lbl = ctk.CTkLabel(self.tel_frm, text=label_txt, font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70")
            lbl.grid(row=r, column=c_label, sticky="e", padx=(12, 4), pady=2)
            
            val = ctk.CTkLabel(self.tel_frm, text=val_txt, font=ctk.CTkFont(size=11), anchor="w")
            val.grid(row=r, column=c_val, sticky="w", padx=(4, 12), pady=2)
            self.telemetry_labels[label_txt] = val

        self.btn_view_details = ctk.CTkButton(
            self.tel_frm, 
            text="🔍 View Consumer Details", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            height=24, 
            fg_color="gray30", 
            hover_color="gray40", 
            command=self.open_consumer_details_popup
        )
        self.btn_view_details.grid(row=6, column=0, columnspan=4, pady=(6, 8), padx=12, sticky="ew")

        # 2b. Hotkey Quick-Action Bar
        self.hotkey_frm = ctk.CTkFrame(self.telemetry_hotkey_frm, fg_color="#1f2937", corner_radius=8)
        self.hotkey_frm.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        
        hk_title = ctk.CTkLabel(self.hotkey_frm, text="Rapid-Fire Audit Decisions", font=ctk.CTkFont(size=13, weight="bold"))
        hk_title.pack(anchor="w", padx=12, pady=(8, 4))

        hk_btn_frm = ctk.CTkFrame(self.hotkey_frm, fg_color="transparent")
        hk_btn_frm.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        
        self.btn_correct = ctk.CTkButton(
            hk_btn_frm, 
            text="✅ Meter Image Correct (C)", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color="#064e3b", 
            hover_color="#065f46", 
            height=32, 
            command=lambda: self.set_status("C")
        )
        self.btn_correct.pack(fill="x", pady=2)

        self.btn_illegible = ctk.CTkButton(
            hk_btn_frm, 
            text="⚠️ Illegible Image (IL)", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color="#78350f", 
            hover_color="#92400e", 
            height=32, 
            command=lambda: self.set_status("IL")
        )
        self.btn_illegible.pack(fill="x", pady=2)

        other_obs = [
            "Select Other Observations...",
            "Different Meter No (MM)",
            "Location Difference (LM)",
            "Non Meter Image (NMI)",
            "Mismatch Reading (I)"
        ]
        self.combo_other_obs = ctk.CTkOptionMenu(
            hk_btn_frm, 
            values=other_obs, 
            height=30, 
            font=ctk.CTkFont(size=11),
            command=self.on_other_obs_selected
        )
        self.combo_other_obs.set("Select Other Observations...")
        self.combo_other_obs.pack(fill="x", pady=4)

        # Bottom Status Bar Frame
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
        # If the focused widget is a text entry, ignore hotkeys
        cls_name = focused.winfo_class()
        # customtkinter entry has a child entry or is CTkEntry
        if "Entry" in cls_name or "Text" in cls_name:
            return True
        return False

    def _bind_hotkeys(self):
        # Keyboard triggers for the 6 choices
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

    # ----------------------------------------------------
    # EVENT HANDLERS & FLOW CONTROL
    # ----------------------------------------------------
    
    def on_cascade_change(self, val):
        self.fetch_cascade_mru()

    def fetch_cascade_mru(self):
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        month = self.month_combo.get()
        year = self.year_combo.get()

        cache_key = f"{off_code}_{month}_{year}"
        if cache_key in self.zones_cache:
            mrus = self.zones_cache[cache_key]
            self.log_to_console(f"Using cached zones/MRUs for {month}/{year}")
            self._update_mru_dropdown(mrus)
            return

        # Update indicators to "Loading..."
        self.mru_combo.configure(values=["Loading..."])
        self.mru_combo.set("Loading...")
        self.mru_spinner_lbl.configure(text="⏳ Fetching...")

        def fetch_task():
            try:
                mrus = self.api_client.fetch_mru(username, token, off_code, month, year)
                if mrus:
                    self.zones_cache[cache_key] = mrus
                    self.save_zones_cache()
                    self.after(0, lambda: self._update_mru_dropdown(mrus))
                else:
                    self.after(0, lambda: self._update_mru_dropdown([]))
            except Exception as e:
                print(f"Failed to fetch MRUs: {e}")
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
                self.after(0, lambda: self.fetch_queue_btn.configure(state="normal", text="Fetch Server Queue"))

        threading.Thread(target=fetch_task, daemon=True).start()

    def load_queue_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Queue JSON File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            
            records = []
            if isinstance(data, list):
                # If it's a simple list of consumer IDs, map them into a list of dicts
                for item in data:
                    if isinstance(item, dict):
                        records.append(item)
                    else:
                        # Consumer ID string
                        records.append({
                            "con_id": str(item),
                            "meter_no": "Unknown",
                            "smrd": self.month_combo.get(),
                            "ccc_code": self.session_off_code,
                            "ccc_name": "KUSHIDA CCC" # Default fallback
                        })
            else:
                raise Exception("JSON root must be a list of records or consumer IDs.")

            self.load_records_into_memory(records, source=f"File ({os.path.basename(file_path)})")
        except Exception as e:
            messagebox.showerror("File Error", f"Could not parse selected file:\n{str(e)}")

    def load_records_into_memory(self, records, source=""):
        self.queue_records = records
        if records:
            logging.info(f"Sample record payload keys & data: {json.dumps(records[0])}")
        self.current_index = -1
        self.audit_decisions.clear()
        self.audited_ids = set()

        # Initialize default decision state for all records to Approved "C"
        for rec in records:
            con_id = rec.get("con_id")
            if con_id:
                self.audit_decisions[str(con_id)] = {
                    "verification_stat": "C",
                    "meter_note": " "
                }

        self.queue_title.configure(text=f"Audit Queue list ({len(records)} records)")
        self.log_to_console(f"Loaded {len(records)} records in-memory from {source}.")

        # Populate GUI Table list
        self.queue_frame.populate_queue(
            records,
            audited_ids=self.audited_ids,
            audit_decisions=self.audit_decisions,
            allow_without_lookup=self.allow_submission_without_lookup
        )

        # Restore local progress
        self.load_local_progress()

        # Enable Commit and Fetch buttons
        self.fetch_queue_btn.configure(state="normal", text="Fetch Queue")
        self.progress_bar.set(0)
        self.update_stats_dashboard()

        # Select first consumer
        if records:
            first_con_id = records[0].get("con_id")
            self.select_consumer_by_id(first_con_id)
            
            # Setup prefetcher
            self.prefetcher.set_queue(
                records,
                default_smrd="",
                default_zone=self.mru_combo.get()
            )
        else:
            self._clear_viewer()

    def select_consumer_by_id(self, con_id):
        idx = next((i for i, r in enumerate(self.queue_records) if r.get("con_id") == con_id), -1)
        if idx == -1:
            return

        self.current_index = idx
        self.queue_frame.highlight_row(con_id)
        self.prefetcher.set_active_index(idx)
        
        # Display image (instantly if cached, else load)
        self.update_active_image()
        # Update telemetry panel
        self.update_active_telemetry()

    def update_active_image(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            self._clear_viewer()
            return

        record = self.queue_records[self.current_index]
        con_id = record.get("con_id")
        
        # Clear old image and show loading placeholder instantly
        self.img_lbl.configure(image="", text="⏳ Loading image...")
        self.img_lbl.image = None
        
        # Retrieve from cache
        cached_img = self.prefetcher.get_image(con_id)
        
        if cached_img == "error":
            self.img_lbl.configure(image=None, text="Error fetching meter image from server.")
        elif cached_img is None:
            # Not in cache yet, start fetching inline
            self.img_lbl.configure(image=None, text="Prefetching image... Please wait.")
            # Trigger prefetch check immediately
            self.prefetcher.trigger_prefetch()
            
            # Fetch explicitly if background didn't finish
            def fetch_inline_task():
                try:
                    conn_str = record.get("connection_string", [])
                    if conn_str and isinstance(conn_str, list) and "URL" in conn_str[0]:
                        photo_url = conn_str[0]["URL"]
                    else:
                        photo_url = self.prefetcher._build_fallback_url(
                            con_id, 
                            record.get("smrd", record.get("smrdn", "")), 
                            self.mru_combo.get()
                        )
                    
                    # Check local disk cache
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
                        username = self.session_username
                        token = self.session_token
                        off_code = self.session_off_code

                        img_b64 = self.api_client.fetch_image_base64(username, token, off_code, photo_url)
                        if img_b64:
                            img_bytes = base64.b64decode(img_b64)
                            try:
                                with open(local_path, "wb") as f_img:
                                    f_img.write(img_bytes)
                            except Exception as fe:
                                print(f"Failed to write image to disk cache: {fe}")
                            pil_img = Image.open(io.BytesIO(img_bytes))
                        else:
                            raise Exception("Null image")

                    if pil_img:
                        # Downscale to save memory
                        pil_img = self.prefetcher._downscale_image(pil_img, max_size=1024)
                        with self.prefetcher.cache_lock:
                            self.prefetcher.image_cache[con_id] = pil_img
                        
                        # Verify we are still on the same index
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
            # Display cached image
            self._render_image(cached_img)

    def on_image_prefetch_done(self, con_id):
        # Callback from background prefetcher when active image finished loading
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            active_con_id = self.queue_records[self.current_index].get("con_id")
            if active_con_id == con_id:
                self.after(0, self.update_active_image)

    def _render_image(self, pil_img):
        # Resize image maintaining aspect ratio
        container_w = self.image_outer_frm.winfo_width()
        container_h = self.image_outer_frm.winfo_height()
        
        # Fallback to defaults if container not rendered yet
        if container_w <= 10 or container_h <= 10:
            container_w = 600
            container_h = 450

        # Leave small margin
        target_w = container_w - 20
        target_h = container_h - 20

        w, h = pil_img.size
        scale = min(target_w / w, target_h / h)
        new_w = max(int(w * scale), 10)
        new_h = max(int(h * scale), 10)

        # CustomTkinter CTkImage Widget
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img

    def on_image_container_resize(self, event):
        # Trigger re-render of image on container resize
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            con_id = self.queue_records[self.current_index].get("con_id")
            cached_img = self.prefetcher.get_image(con_id)
            if cached_img and cached_img != "error":
                self._render_image(cached_img)

    def update_active_telemetry(self):
        if self.current_index < 0 or self.current_index >= len(self.queue_records):
            return

        rec = self.queue_records[self.current_index]
        con_id = str(rec.get("con_id", "N/A"))
        
        # Populate key values
        self.telemetry_labels["Consumer ID:"].configure(text=con_id)
        self.telemetry_labels["Meter No:"].configure(text=str(rec.get("meter_no", "N/A")))
        self.telemetry_labels["CCC Name:"].configure(text=str(rec.get("ccc_name", "N/A")))
        self.telemetry_labels["CCC Code:"].configure(text=str(rec.get("ccc_code", "N/A")))
        self.telemetry_labels["Prev Reading:"].configure(text=str(rec.get("previous_reading", "N/A")))
        self.telemetry_labels["Pres Reading:"].configure(text=str(rec.get("present_reading", "N/A")))
        
        # Calculate consumption
        try:
            prev = float(rec.get("previous_reading", 0))
            pres = float(rec.get("present_reading", 0))
            diff = pres - prev
            self.telemetry_labels["Consumption:"].configure(text=f"{diff:.2f}")
        except Exception:
            self.telemetry_labels["Consumption:"].configure(text="N/A")
            
        # Extract MR Note robustly
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

        # Update HUD labels
        self.hud_meter_lbl.configure(text=f"Meter: {rec.get('meter_no', 'N/A')}")
        self.hud_pres_lbl.configure(text=f"Present Rdg: {rec.get('present_reading', 'N/A')}")
        self.hud_mrnote_lbl.configure(text=f"MR Note: {mr_note}")
        
        # Overlay HUD on image
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
            if self.allow_submission_without_lookup:
                # Count un-audited records as Correct by default
                dec = self.audit_decisions.get(cid, {"verification_stat": "C"})
                stat = dec.get("verification_stat", "C")
                if stat == "IL":
                    illegible += 1
                elif stat in ("MM", "LM", "NMI", "I"):
                    other += 1
                else:
                    correct += 1
            else:
                # Only count audited records
                if cid in self.audited_ids:
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
            
        record = self.queue_records[self.current_index]
        con_id = record.get("con_id")
        if not con_id:
            return

        popup = ctk.CTkToplevel(self)
        popup.title(f"Consumer Details - {con_id}")
        popup.geometry("750x500")
        popup.after(200, lambda: popup.focus_force())
        
        title_lbl = ctk.CTkLabel(popup, text=f"Billing & Telemetry History for ID: {con_id}", font=ctk.CTkFont(size=14, weight="bold"))
        title_lbl.pack(pady=10)

        content_frm = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        content_frm.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        loading_lbl = ctk.CTkLabel(content_frm, text="Fetching billing history snapshot from server...", font=ctk.CTkFont(size=12, slant="italic"))
        loading_lbl.pack(pady=40)

        def fetch_details_thread():
            try:
                username = self.session_username
                token = self.session_token
                off_code = self.session_off_code
                
                details = self.api_client.fetch_conid_all(username, token, off_code, con_id)
                
                def render_ui():
                    loading_lbl.destroy()
                    if not details:
                        no_data_lbl = ctk.CTkLabel(content_frm, text="No historical snapshot data found on Tomcat backend.", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray60")
                        no_data_lbl.pack(pady=40)
                        return
                    
                    for idx, bill in enumerate(details):
                        # Card outer container
                        bill_frm = ctk.CTkFrame(content_frm, fg_color="#1f2937" if idx % 2 == 0 else "#111827", corner_radius=8, border_width=1, border_color="gray30")
                        bill_frm.pack(fill="x", pady=6, padx=6)
                        
                        # Title Header Row: Month / Year / Date
                        header_frm = ctk.CTkFrame(bill_frm, fg_color="#374151", corner_radius=4, height=28)
                        header_frm.pack(fill="x", padx=8, pady=(8, 4))
                        
                        acc_m = str(bill.get("acc_month", bill.get("month", "N/A")))
                        acc_y = str(bill.get("acc_year", bill.get("year", "N/A")))
                        smrd_val = str(bill.get("smrd", bill.get("smrdn", bill.get("upload_date", "N/A"))))
                        
                        header_lbl = ctk.CTkLabel(
                            header_frm, 
                            text=f"📅 Billing Period: {acc_m}/{acc_y}   |   SMRD: {smrd_val}", 
                            font=ctk.CTkFont(size=11, weight="bold"), 
                            text_color="#38bdf8"
                        )
                        header_lbl.pack(side="left", padx=10, pady=2)
                        
                        # Grid for reading & metadata details
                        grid_frm = ctk.CTkFrame(bill_frm, fg_color="transparent")
                        grid_frm.pack(fill="x", padx=8, pady=4)
                        grid_frm.columnconfigure((0, 1), weight=1)
                        
                        # Left Column: Readings
                        left_frm = ctk.CTkFrame(grid_frm, fg_color="transparent")
                        left_frm.grid(row=0, column=0, sticky="nsew", padx=4)
                        
                        prev_rdg = bill.get("previous_reading", bill.get("prev_rdg", "N/A"))
                        pres_rdg = bill.get("present_reading", bill.get("pres_rdg", "N/A"))
                        
                        cons = "N/A"
                        try:
                            cons_val = float(pres_rdg) - float(prev_rdg)
                            cons = f"{cons_val:.2f}"
                        except Exception:
                            cons = str(bill.get("consumption", "N/A"))
                            
                        ctk.CTkLabel(left_frm, text=f"• Present Rdg:  {pres_rdg}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10b981", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(left_frm, text=f"• Prev Rdg:       {prev_rdg}", font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(left_frm, text=f"• Consumption:   {cons}", font=ctk.CTkFont(size=11), text_color="#60a5fa", anchor="w").pack(fill="x", pady=1)
                        
                        # Right Column: Meter & AI Status
                        right_frm = ctk.CTkFrame(grid_frm, fg_color="transparent")
                        right_frm.grid(row=0, column=1, sticky="nsew", padx=4)
                        
                        met_no = bill.get("meter_no", bill.get("meterno", "N/A"))
                        ai_flg = bill.get("aiflag", bill.get("ai_flag", "N/A"))
                        v_stat = bill.get("verification_stat", bill.get("status", "N/A"))
                        
                        ctk.CTkLabel(right_frm, text=f"• Meter No:  {met_no}", font=ctk.CTkFont(size=11), text_color="gray80", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(right_frm, text=f"• AI Flag:     {ai_flg}", font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", pady=1)
                        ctk.CTkLabel(right_frm, text=f"• Audit Stat: {v_stat}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fbbf24", anchor="w").pack(fill="x", pady=1)
                        
                        # Extract MR Note robustly
                        raw_note = ""
                        for key in ["mr_note", "mrnote", "mr_remark", "mrremark", "remarks", "remark", "note", "reader_note", "readernote", "mr_note_desc", "mrnote_desc"]:
                            val = bill.get(key)
                            if val is not None:
                                raw_note = str(val).strip()
                                if raw_note:
                                    break
                        mr_note = raw_note if raw_note else "N/A"
                        
                        # MR Note Highlight Box
                        note_frm = ctk.CTkFrame(bill_frm, fg_color="#223e2b" if mr_note != "N/A" else "#27272a", corner_radius=4)
                        note_frm.pack(fill="x", padx=8, pady=(4, 8))
                        
                        note_lbl = ctk.CTkLabel(
                            note_frm, 
                            text=f"📝 MR Note: {mr_note}", 
                            font=ctk.CTkFont(size=11, weight="bold" if mr_note != "N/A" else "normal"), 
                            text_color="#a7f3d0" if mr_note != "N/A" else "gray60",
                            anchor="w",
                            justify="left",
                            wraplength=680
                        )
                        note_lbl.pack(fill="x", padx=10, pady=4)
                popup.after(0, render_ui)
            except Exception as e:
                def render_err():
                    loading_lbl.destroy()
                    err_lbl = ctk.CTkLabel(content_frm, text=f"Failed to fetch: {str(e)}", text_color="#ef4444", font=ctk.CTkFont(size=12, weight="bold"))
                    err_lbl.pack(pady=40)
                popup.after(0, render_err)

        threading.Thread(target=fetch_details_thread, daemon=True).start()

    def next_consumer(self):
        if not self.queue_records:
            return
        
        # Default active one to Correct (C) if not modified, then advance
        if self.current_index >= 0 and self.current_index < len(self.queue_records):
            con_id = self.queue_records[self.current_index].get("con_id")
            # If down arrow key was pressed, it leaves record as "C" (or whatever it currently is)
            # so no action needed.
            
            # Advance index
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

    # ----------------------------------------------------
    # UNIFIED BATCH EXECUTION COMMIT LOOP
    # ----------------------------------------------------
    
    def start_batch_commit(self):
        if not self.queue_records:
            messagebox.showwarning("Commit Blocked", "No records loaded in queue to commit.")
            return
        
        if self.is_committing:
            # If already running, this button click represents a Cancel request
            if not self.cancel_requested:
                self.cancel_requested = True
                self.commit_btn.configure(state="disabled", text="Stopping...")
                self.log_to_console("🛑 Cancellation requested. Safely aborting remaining upload tasks...")
            return

        confirm = messagebox.askyesno(
            "Confirm Batch Update", 
            f"Are you sure you want to update verification decisions for all {len(self.queue_records)} records to the backend Tomcat server?"
        )
        if not confirm:
            return

        self.is_committing = True
        self.cancel_requested = False
        
        # Turn the update button into a red cancel button
        self.commit_btn.configure(text="Cancel Update", fg_color="#ef4444", hover_color="#dc2626")
        self.fetch_queue_btn.configure(state="disabled")
        self.set_selectors_state("disabled")

        # Run submission loop in background thread
        threading.Thread(target=self._batch_commit_task, daemon=True).start()

    def _batch_commit_task(self):
        records = list(self.queue_records)
        if not self.allow_submission_without_lookup:
            records = [r for r in records if str(r.get("con_id")) in self.audited_ids]

        decisions = dict(self.audit_decisions)
        
        username = self.session_username
        token = self.session_token
        off_code = self.session_off_code
        acc_month = self.month_combo.get()
        acc_year = self.year_combo.get()
        pacing = float(self.pacing_slider.get())

        total = len(records)
        if total == 0:
            self.log_to_console("⚠️ Batch Commit Aborted: No audited/marked records to submit.")
            self.after(0, lambda: messagebox.showwarning(
                "No Audited Records", 
                "No manually audited records were found. Please mark/audit records first, or enable 'Allow Submission Without Lookup' in the settings."
            ))
            self.is_committing = False
            
            def restore_ui_early():
                self.commit_btn.configure(state="normal", text="Update", fg_color="#10b981", hover_color="#059669")
                self.fetch_queue_btn.configure(state="normal")
                self.set_selectors_state("normal")
            self.after(0, restore_ui_early)
            return

        success_count = 0
        failure_count = 0

        self.log_to_console(f"\n--- Batch Upload Initiated ({total} records) ---")

        for idx, rec in enumerate(records, start=1):
            if self.cancel_requested:
                self.log_to_console("🛑 Update process stopped by the user.")
                break
            con_id = rec.get("con_id")
            
            # Extract decision
            decision = decisions.get(str(con_id), {"verification_stat": "C"})
            status = decision.get("verification_stat", "C")
            
            # Format meter note dynamically: keep original if not "003"/empty, else send three spaces
            original_mrnote = rec.get("mrnote", "") or ""
            if original_mrnote in ("003", "") or str(original_mrnote).strip() == "":
                note_to_submit = "   "
            else:
                note_to_submit = str(original_mrnote)

            # Calculate sapdata from ai_flag dynamically
            ai_flag_val = rec.get("ai_flag", "") or ""
            ai_flag_str = str(ai_flag_val).strip()
            if "Accepted by Meter Reader" in ai_flag_str:
                sapdata_val = "HIT"
            elif "Not accepted by Meter Reader" in ai_flag_str:
                sapdata_val = "MIS"
            elif "No Reading from AI Engine" in ai_flag_str:
                sapdata_val = "NOA"
            elif "Not under AI scope" in ai_flag_str or "Not under AI Scope" in ai_flag_str:
                sapdata_val = "NUS"
            else:
                sapdata_val = "MIS"

            # Extract tariff class
            tariff_val = rec.get("tariff", " ")
            if not tariff_val or str(tariff_val).strip().lower() == "none":
                tariff_val = " "

            ccc_code = rec.get("ccc_code", off_code)
            ccc_name = rec.get("ccc_name", "KUSHIDA CCC")
            
            # Extract SMRD directly from record
            smrdn = rec.get("smrd", rec.get("smrdn", " "))
            if not smrdn or str(smrdn).strip().lower() == "none":
                smrdn = " "

            # Log current action
            self.log_to_console(f"[{idx}/{total}] Uploading Consumer ID {con_id} (Status: {status}, Sapdata: {sapdata_val}, Tariff: {tariff_val})...")

            # Try request
            try:
                success, server_msg = self.api_client.submit_audit_record(
                    username=username,
                    token=token,
                    off_code=off_code,
                    acc_month=acc_month,
                    acc_year=acc_year,
                    ccc_code=ccc_code,
                    ccc_name=ccc_name,
                    con_id=con_id,
                    smrdn=smrdn,
                    verification_stat=status,
                    meter_note=note_to_submit,
                    sapdata=sapdata_val,
                    tariff=tariff_val
                )
                if success:
                    success_count += 1
                    self.log_to_console(f"   ──► Success: {server_msg}")
                    self.remove_from_local_progress(con_id)
                else:
                    failure_count += 1
                    self.log_to_console(f"   ──► Failed: {server_msg}")
            except Exception as e:
                if self.handle_api_error(e):
                    # Session expired and redirect triggered, breakout!
                    return
                failure_count += 1
                self.log_to_console(f"   ──► Network Fault: {str(e)}")

            # Update progress bar
            progress_val = idx / total
            self.after(0, lambda val=progress_val: self.progress_bar.set(val))

            # Sleep pacing
            time.sleep(pacing)

        # Complete audit summary
        self.log_to_console(f"--- Batch Upload Completed. Success: {success_count} | Failed: {failure_count} ---")
        
        # Reset UI controls on main thread
        def reset_ui():
            self.is_committing = False
            self.commit_btn.configure(state="normal", text="Update", fg_color="#10b981", hover_color="#059669")
            self.fetch_queue_btn.configure(state="normal")
            self.set_selectors_state("normal")
            
            if self.cancel_requested:
                processed = success_count + failure_count
                messagebox.showwarning(
                    "Upload Cancelled", 
                    f"Batch upload was aborted by user.\n\nSuccessfully updated: {success_count}\nRemaining: {total - processed}"
                )
            else:
                messagebox.showinfo(
                    "Batch Execution Done", 
                    f"Batch upload finished.\n\nSuccess: {success_count}\nFailures: {failure_count}"
                )
            self.cancel_requested = False

        self.after(0, reset_ui)

    def prompt_password(self, callback):
        """Shows a premium password modal popup to confirm settings change."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Security Verification")
        dialog.geometry("340x180")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog on the screen relative to parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 170
        y = self.winfo_y() + (self.winfo_height() // 2) - 90
        dialog.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(
            dialog, 
            text="Enter Password to toggle this setting:", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl.pack(pady=(20, 10))
        
        pw_entry = ctk.CTkEntry(dialog, show="*", width=200)
        pw_entry.pack(pady=5)
        pw_entry.focus_force()
        
        btn_frm = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frm.pack(pady=(15, 10))
        
        def on_confirm(event=None):
            pw = pw_entry.get()
            if pw == "password":
                dialog.destroy()
                callback(True)
            else:
                messagebox.showerror("Access Denied", "Incorrect password!", parent=dialog)
                dialog.destroy()
                callback(False)
                
        def on_cancel():
            dialog.destroy()
            callback(None)
            
        pw_entry.bind("<Return>", on_confirm)
        
        btn_ok = ctk.CTkButton(
            btn_frm, 
            text="Verify", 
            width=80, 
            fg_color="#10b981", 
            hover_color="#059669", 
            command=on_confirm
        )
        btn_ok.pack(side="left", padx=5)
        
        btn_cancel = ctk.CTkButton(
            btn_frm, 
            text="Cancel", 
            width=80, 
            fg_color="gray30", 
            hover_color="gray40", 
            command=on_cancel
        )
        btn_cancel.pack(side="left", padx=5)

    def toggle_submission_setting(self):
        # We need to verify password to change the value
        # First, temporarily revert the switch value visual state until verified
        current_switch_state = self.submission_toggle.get()
        
        # Toggle back visually until password is authenticated
        if current_switch_state == 1:
            self.submission_toggle.deselect()
        else:
            self.submission_toggle.select()
            
        def on_verified(result):
            if result is True:
                # Password correct, apply new state
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
            elif result is False:
                # Password incorrect, keep old state (already reverted visually)
                pass
            else:
                # Canceled, keep old state (already reverted visually)
                pass
                
        self.prompt_password(on_verified)

    def set_selectors_state(self, state):
        """Disables or enables top selector dropdown menus to prevent corruption during upload."""
        self.month_combo.configure(state=state)
        self.year_combo.configure(state=state)
        self.aiflag_combo.configure(state=state)
        self.mru_combo.configure(state=state)

    def refresh_unaudited_rows(self):
        """Refreshes the badges and checkboxes of un-audited records when settings change."""
        for rec in self.queue_records:
            con_id_str = str(rec.get("con_id"))
            if con_id_str not in self.audited_ids:
                if self.allow_submission_without_lookup:
                    # Show as Approved
                    if con_id_str in self.queue_frame.checkbox_vars:
                        self.queue_frame.checkbox_vars[con_id_str].set("C")
                    if con_id_str in self.queue_frame.badge_labels:
                        self.queue_frame.badge_labels[con_id_str].configure(
                            text="Approved", 
                            bg="#064e3b", 
                            fg="#10b981"
                        )
                else:
                    # Show as Pending
                    if con_id_str in self.queue_frame.checkbox_vars:
                        self.queue_frame.checkbox_vars[con_id_str].set("")
                    if con_id_str in self.queue_frame.badge_labels:
                        self.queue_frame.badge_labels[con_id_str].configure(
                            text="Pending", 
                            bg="#374151", 
                            fg="#9ca3af"
                        )

    def update_button_state(self):
        """Updates the enable/disable state of the Update button based on settings and audited records."""
        if self.is_committing:
            return
            
        if self.allow_submission_without_lookup:
            self.commit_btn.configure(state="normal")
        else:
            if len(self.audited_ids) > 0:
                self.commit_btn.configure(state="normal")
            else:
                self.commit_btn.configure(state="disabled")


