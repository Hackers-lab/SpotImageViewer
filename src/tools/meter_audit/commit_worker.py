import time
import threading
import logging
from .client import SessionExpiredException


class BatchCommitWorker:
    """Handles background batch submission of audit decisions to WBSEDCL Tomcat API."""

    def __init__(self, api_client):
        self.api_client = api_client
        self.is_committing = False
        self.cancel_requested = False
        self._thread = None

    def start(
        self,
        records,
        decisions,
        audited_ids,
        allow_submission_without_lookup,
        session_username,
        session_token,
        session_off_code,
        acc_month,
        acc_year,
        pacing,
        on_log,
        on_progress,
        on_success_record,
        on_session_expired,
        on_complete
    ):
        if self.is_committing:
            return

        self.is_committing = True
        self.cancel_requested = False

        def _worker():
            work_records = list(records)
            if not allow_submission_without_lookup:
                work_records = [r for r in work_records if str(r.get("con_id")) in audited_ids]

            total = len(work_records)
            if total == 0:
                on_log("BATCH_EMPTY")
                self.is_committing = False
                on_complete(0, 0, 0, was_empty=True)
                return

            success_count = 0
            failure_count = 0

            on_log(f"\n--- Batch Upload Initiated ({total} records) ---")

            for idx, rec in enumerate(work_records, start=1):
                if self.cancel_requested:
                    on_log("STOPPED_BY_USER")
                    break

                con_id = rec.get("con_id")
                decision = decisions.get(str(con_id), {"verification_stat": "C"})
                status = decision.get("verification_stat", "C")

                # Format meter note dynamically
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

                ccc_code = rec.get("ccc_code", session_off_code)
                ccc_name = rec.get("ccc_name", "KUSHIDA CCC")
                smrdn = rec.get("smrd", rec.get("smrdn", " "))
                if not smrdn or str(smrdn).strip().lower() == "none":
                    smrdn = " "

                on_log(f"[{idx}/{total}] Uploading Consumer ID {con_id} (Status: {status}, Sapdata: {sapdata_val}, Tariff: {tariff_val})...")

                try:
                    success, server_msg = self.api_client.submit_audit_record(
                        username=session_username,
                        token=session_token,
                        off_code=session_off_code,
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
                        on_log(f"   ──► Success: {server_msg}")
                        on_success_record(con_id)
                    else:
                        failure_count += 1
                        on_log(f"   ──► Failed: {server_msg}")
                except SessionExpiredException as se:
                    self.is_committing = False
                    on_session_expired(se)
                    return
                except Exception as e:
                    failure_count += 1
                    on_log(f"   ──► Network Fault: {str(e)}")

                on_progress(idx / total)
                time.sleep(pacing)

            on_log(f"--- Batch Upload Completed. Success: {success_count} | Failed: {failure_count} ---")
            self.is_committing = False
            on_complete(success_count, failure_count, total, was_empty=False, cancelled=self.cancel_requested)

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def cancel(self):
        if self.is_committing:
            self.cancel_requested = True
