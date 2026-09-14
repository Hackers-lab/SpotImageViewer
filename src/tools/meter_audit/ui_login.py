import time
import threading
import tkinter as tk
import customtkinter as ctk

class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_login_success):
        super().__init__(parent, fg_color="#121316")
        self.parent = parent
        self.on_login_success = on_login_success
        self.api_client = parent.api_client if hasattr(parent, 'api_client') else parent.master.api_client

        self.username = ""
        self.password = ""
        self.countdown_val = 60
        self.countdown_active = False

        # Card container (centered)
        self.card = ctk.CTkFrame(self, fg_color="#1f2022", corner_radius=16, border_width=1, border_color="gray30", width=420, height=480)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.grid_propagate(False)
        self.card.grid_columnconfigure(0, weight=1)
        
        self.logo_lbl = ctk.CTkLabel(self.card, text="⚡", font=ctk.CTkFont(size=44))
        self.logo_lbl.grid(row=0, column=0, pady=(24, 0))

        self.title_lbl = ctk.CTkLabel(self.card, text="WBSedcl Meter Verification", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_lbl.grid(row=1, column=0, pady=(5, 2))

        self.subtitle_lbl = ctk.CTkLabel(self.card, text="Spot Reading Portal Auditor", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray60")
        self.subtitle_lbl.grid(row=2, column=0, pady=(0, 20))

        # Credentials View Frame
        self.cred_frm = ctk.CTkFrame(self.card, fg_color="transparent")
        self.cred_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.cred_frm.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.cred_frm, text="ERP ID (Username)", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.user_ent = ctk.CTkEntry(self.cred_frm, placeholder_text="Enter 8-digit ERP ID", height=36)
        self.user_ent.pack(fill="x", pady=(0, 10))
        self.user_ent.bind("<Return>", lambda e: self.action_send_otp())

        ctk.CTkLabel(self.cred_frm, text="Password", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.pass_ent = ctk.CTkEntry(self.cred_frm, placeholder_text="Enter Portal Password", show="*", height=36)
        self.pass_ent.pack(fill="x", pady=(0, 20))
        self.pass_ent.bind("<Return>", lambda e: self.action_send_otp())

        self.send_otp_btn = ctk.CTkButton(self.cred_frm, text="Send OTP", height=38, font=ctk.CTkFont(size=13, weight="bold"), command=self.action_send_otp)
        self.send_otp_btn.pack(fill="x")

        # OTP Verification Frame (Initially Hidden)
        self.otp_frm = ctk.CTkFrame(self.card, fg_color="transparent")
        self.otp_frm.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.otp_frm, text="OTP Code", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray70").pack(anchor="w", pady=(5, 2))
        self.otp_ent = ctk.CTkEntry(self.otp_frm, placeholder_text="Enter OTP code", height=36, justify="center", font=ctk.CTkFont(size=16, weight="bold"))
        self.otp_ent.pack(fill="x", pady=(0, 15))
        self.otp_ent.bind("<Return>", lambda e: self.action_verify_otp())

        self.verify_otp_btn = ctk.CTkButton(self.otp_frm, text="Verify OTP", height=38, font=ctk.CTkFont(size=13, weight="bold"), command=self.action_verify_otp)
        self.verify_otp_btn.pack(fill="x", pady=(0, 10))

        timer_row = ctk.CTkFrame(self.otp_frm, fg_color="transparent")
        timer_row.pack(fill="x", pady=(5, 0))
        
        self.timer_lbl = ctk.CTkLabel(timer_row, text="Resend OTP in 60s", font=ctk.CTkFont(size=11), text_color="gray60")
        self.timer_lbl.pack(side="left")

        self.resend_btn = ctk.CTkButton(timer_row, text="Resend OTP", width=80, height=22, font=ctk.CTkFont(size=11), state="disabled", fg_color="transparent", text_color="gray50", command=self.action_resend_otp)
        self.resend_btn.pack(side="right")

        self.back_btn = ctk.CTkButton(self.otp_frm, text="← Back to Login", width=120, height=24, fg_color="transparent", text_color="gray60", command=self.action_back_to_login)
        self.back_btn.pack(pady=(15, 0))

        # Status Message
        self.status_lbl = ctk.CTkLabel(self.card, text="", font=ctk.CTkFont(size=12), wraplength=340)
        self.status_lbl.grid(row=4, column=0, pady=(15, 10), padx=30, sticky="ew")

    def set_status(self, text, is_error=True):
        color = "#ef4444" if is_error else "#10b981"
        self.status_lbl.configure(text=text, text_color=color)

    def action_send_otp(self):
        username = self.user_ent.get().strip()
        password = self.pass_ent.get().strip()

        if not username or not password:
            self.set_status("ERP ID and Password are required.")
            return

        if not username.isdigit() or len(username) != 8:
            self.set_status("ERP ID must be an 8-digit number.")
            return

        self.send_otp_btn.configure(state="disabled", text="Sending OTP...")
        self.set_status("Requesting OTP...", is_error=False)

        def task():
            try:
                res = self.api_client.submit_for_otp(username, password)
                code = res.get("code")
                msg = res.get("message", "OTP sent successfully")
                if code == "200":
                    self.username = username
                    self.password = password
                    self.after(0, self.show_otp_view)
                else:
                    self.after(0, lambda: self.send_otp_btn.configure(state="normal", text="Send OTP"))
                    self.after(0, lambda: self.set_status(f"Error {code}: {msg}"))
            except Exception as e:
                self.after(0, lambda: self.send_otp_btn.configure(state="normal", text="Send OTP"))
                self.after(0, lambda: self.set_status(f"Error: {str(e)}"))

        threading.Thread(target=task, daemon=True).start()

    def show_otp_view(self):
        self.cred_frm.grid_forget()
        self.otp_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.set_status("OTP sent successfully.", is_error=False)
        self.start_timer()

    def action_back_to_login(self):
        self.stop_timer()
        self.otp_frm.grid_forget()
        self.cred_frm.grid(row=3, column=0, sticky="nsew", padx=35)
        self.set_status("")
        self.send_otp_btn.configure(state="normal", text="Send OTP")

    def start_timer(self):
        self.countdown_val = 60
        self.countdown_active = True
        self.resend_btn.configure(state="disabled", text_color="gray50")
        self.timer_lbl.configure(text=f"Resend OTP in {self.countdown_val}s", text_color="gray60")
        self.update_timer()

    def stop_timer(self):
        self.countdown_active = False

    def update_timer(self):
        if not self.countdown_active:
            return
        if self.countdown_val > 0:
            self.countdown_val -= 1
            self.timer_lbl.configure(text=f"Resend OTP in {self.countdown_val}s")
            self.after(1000, self.update_timer)
        else:
            self.timer_lbl.configure(text="Didn't receive OTP?", text_color="gray80")
            self.resend_btn.configure(state="normal", text_color="#3b82f6")

    def action_resend_otp(self):
        self.resend_btn.configure(state="disabled")
        self.set_status("Resending OTP...", is_error=False)
        def task():
            try:
                res = self.api_client.submit_for_otp(self.username, self.password)
                code = res.get("code")
                msg = res.get("message", "OTP resent successfully")
                if code == "200":
                    self.after(0, lambda: self.set_status("OTP resent successfully.", is_error=False))
                    self.after(0, self.start_timer)
                else:
                    self.after(0, lambda: self.set_status(f"Error resending: {msg}"))
                    self.after(0, lambda: self.resend_btn.configure(state="normal"))
            except Exception as e:
                self.after(0, lambda: self.set_status(f"Error resending: {str(e)}"))
                self.after(0, lambda: self.resend_btn.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    def action_verify_otp(self):
        otp = self.otp_ent.get().strip()
        if not otp:
            self.set_status("OTP code is required.")
            return

        self.verify_otp_btn.configure(state="disabled", text="Verifying...")
        self.set_status("Verifying OTP...", is_error=False)

        def task():
            try:
                res = self.api_client.submit_final_otp(self.username, otp)
                code = res.get("code")
                if code == "200":
                    msg_body = res.get("message", {})
                    jwt_token = msg_body.get("JWT_token")
                    off_code = msg_body.get("off_code")
                    off_name = msg_body.get("off_name")
                    name = msg_body.get("name", "N/A")
                    desg = msg_body.get("designation", "N/A")

                    self.after(0, lambda: self.on_login_success(
                        self.username, jwt_token, off_code, off_name, name, desg
                    ))
                else:
                    msg = res.get("message", "Incorrect OTP code.")
                    self.after(0, lambda: self.verify_otp_btn.configure(state="normal", text="Verify OTP"))
                    self.after(0, lambda: self.set_status(f"Error {code}: {msg}"))
            except Exception as e:
                self.after(0, lambda: self.verify_otp_btn.configure(state="normal", text="Verify OTP"))
                self.after(0, lambda: self.set_status(f"Error: {str(e)}"))

        threading.Thread(target=task, daemon=True).start()


