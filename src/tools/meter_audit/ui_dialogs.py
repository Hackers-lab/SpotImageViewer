import threading
import customtkinter as ctk
from tkinter import messagebox


def prompt_password(parent, callback):
    """Shows a security password modal popup to confirm settings change."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("Security Verification")
    dialog.geometry("340x180")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - 170
    y = parent.winfo_y() + (parent.winfo_height() // 2) - 90
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


def show_consumer_details_popup(parent, api_client, session_username, session_token, session_off_code, con_id):
    """Fetches and displays billing and telemetry snapshot history for a consumer."""
    popup = ctk.CTkToplevel(parent)
    popup.title(f"Consumer Details - {con_id}")
    popup.geometry("750x500")
    popup.after(200, lambda: popup.focus_force())

    title_lbl = ctk.CTkLabel(
        popup,
        text=f"Billing & Telemetry History for ID: {con_id}",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    title_lbl.pack(pady=10)

    content_frm = ctk.CTkScrollableFrame(popup, fg_color="transparent")
    content_frm.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    loading_lbl = ctk.CTkLabel(
        content_frm,
        text="Fetching billing history snapshot from server...",
        font=ctk.CTkFont(size=12, slant="italic")
    )
    loading_lbl.pack(pady=40)

    def fetch_details_thread():
        try:
            details = api_client.fetch_conid_all(session_username, session_token, session_off_code, con_id)

            def render_ui():
                loading_lbl.destroy()
                if not details:
                    no_data_lbl = ctk.CTkLabel(
                        content_frm,
                        text="No historical snapshot data found on Tomcat backend.",
                        font=ctk.CTkFont(size=12, weight="bold"),
                        text_color="gray60"
                    )
                    no_data_lbl.pack(pady=40)
                    return

                for idx, bill in enumerate(details):
                    bill_frm = ctk.CTkFrame(
                        content_frm,
                        fg_color="#1f2937" if idx % 2 == 0 else "#111827",
                        corner_radius=8,
                        border_width=1,
                        border_color="gray30"
                    )
                    bill_frm.pack(fill="x", pady=6, padx=6)

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

                    grid_frm = ctk.CTkFrame(bill_frm, fg_color="transparent")
                    grid_frm.pack(fill="x", padx=8, pady=4)
                    grid_frm.columnconfigure((0, 1), weight=1)

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

                    right_frm = ctk.CTkFrame(grid_frm, fg_color="transparent")
                    right_frm.grid(row=0, column=1, sticky="nsew", padx=4)

                    met_no = bill.get("meter_no", bill.get("meterno", "N/A"))
                    ai_flg = bill.get("aiflag", bill.get("ai_flag", "N/A"))
                    v_stat = bill.get("verification_stat", bill.get("status", "N/A"))

                    ctk.CTkLabel(right_frm, text=f"• Meter No:  {met_no}", font=ctk.CTkFont(size=11), text_color="gray80", anchor="w").pack(fill="x", pady=1)
                    ctk.CTkLabel(right_frm, text=f"• AI Flag:     {ai_flg}", font=ctk.CTkFont(size=11), text_color="gray70", anchor="w").pack(fill="x", pady=1)
                    ctk.CTkLabel(right_frm, text=f"• Audit Stat: {v_stat}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fbbf24", anchor="w").pack(fill="x", pady=1)

                    raw_note = ""
                    for key in ["mr_note", "mrnote", "mr_remark", "mrremark", "remarks", "remark", "note", "reader_note", "readernote", "mr_note_desc", "mrnote_desc"]:
                        val = bill.get(key)
                        if val is not None:
                            raw_note = str(val).strip()
                            if raw_note:
                                break
                    mr_note = raw_note if raw_note else "N/A"

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
