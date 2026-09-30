// =============================================================================
// Consumer Bill Downloader & Batch Print Controller
// =============================================================================

let spotaiBatchState = {
  running: false,
  pollTimer: null,
  results: [],
  fileIds: [],
  session: null
};

// Fixed available columns for custom Excel export
const AVAILABLE_EXPORT_COLUMNS = [
  { id: "consumer_id", label: "Consumer ID" },
  { id: "name", label: "Consumer Name" },
  { id: "address", label: "Address" },
  { id: "mobile", label: "Mobile Number" },
  { id: "meter_no", label: "Meter Number" },
  { id: "class_desc", label: "Class / Category" },
  { id: "tariff", label: "Tariff / Phase" },
  { id: "conn_status", label: "Connection Status" },
  { id: "conn_load", label: "Connected Load" },
  { id: "bill_month", label: "Bill Month" },
  { id: "invoice_no", label: "Invoice Number" },
  { id: "due_date", label: "Bill Due Date" },
  { id: "bill_amount", label: "Bill Amount (₹)" },
  { id: "osd_principal", label: "Total Principal OSD (₹)" },
  { id: "lpsc", label: "Current Live LPSC (₹)" },
  { id: "total_dues", label: "Total Dues (OSD + LPSC) (₹)" },
  { id: "last_pay_date", label: "Last Payment Date" },
  { id: "last_pay_amt", label: "Last Payment Amount (₹)" },
  { id: "last_pay_mode", label: "Last Payment Mode" },
  { id: "status", label: "Download Status" },
  { id: "file_path", label: "PDF File Path" },
  { id: "error", label: "Error Details" }
];

const COLUMN_PRESETS = {
  disconnection: [
    "consumer_id", "name", "address", "class_desc", "tariff", "osd_principal", "lpsc", "total_dues", "due_date"
  ],
  standard: [
    "consumer_id", "name", "bill_month", "invoice_no", "due_date", "bill_amount", "osd_principal", "lpsc", "total_dues", "status"
  ],
  payment: [
    "consumer_id", "name", "address", "mobile", "osd_principal", "lpsc", "total_dues", "last_pay_date", "last_pay_amt"
  ],
  full: [
    "consumer_id", "name", "address", "mobile", "meter_no", "class_desc", "tariff", "conn_status",
    "bill_month", "invoice_no", "due_date", "bill_amount", "osd_principal", "lpsc", "total_dues",
    "last_pay_date", "last_pay_amt", "status"
  ]
};

let customExportColumns = loadColumnPreferences();

function loadColumnPreferences() {
  try {
    const saved = localStorage.getItem('siv_bill_export_columns');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (e) {
    console.error("Failed to load export column preferences:", e);
  }
  return [...COLUMN_PRESETS.disconnection];
}

function saveColumnPreferences() {
  try {
    localStorage.setItem('siv_bill_export_columns', JSON.stringify(customExportColumns));
  } catch (e) {
    console.error("Failed to save export column preferences:", e);
  }
}

// --- Initialization & Session State ---
async function initSpotAIModule() {
  renderColumnCustomizer();

  // 1. Verify module license access
  try {
    const accessRes = await callAPI('spotai_check_access');
    const lockedCard = document.getElementById('spotaiAccessLockedCard');
    const workspace = document.getElementById('spotaiUnlockedWorkspace');
    const reqCodeInput = document.getElementById('spotaiMyRequestCode');

    const headerActions = document.getElementById('spotaiHeaderActions');

    if (accessRes && accessRes.allowed) {
      if (lockedCard) lockedCard.classList.add('hidden');
      if (workspace) workspace.classList.remove('hidden');
      if (headerActions) {
        headerActions.classList.remove('hidden');
        headerActions.classList.add('flex');
      }
    } else {
      if (lockedCard) lockedCard.classList.remove('hidden');
      if (workspace) workspace.classList.add('hidden');
      if (headerActions) {
        headerActions.classList.add('hidden');
        headerActions.classList.remove('flex');
      }
      if (reqCodeInput && accessRes && accessRes.request_code) {
        reqCodeInput.value = accessRes.request_code;
      }
      safeCreateIcons();
      return; // Stop initialization until activated
    }
  } catch (err) {
    console.warn("Failed to check license status:", err);
  }

  // 2. Load portal session
  try {
    const res = await callAPI('spotai_get_session');
    if (res && res.authenticated) {
      spotaiBatchState.session = res;
      updateSpotAISessionUI(res);
    } else {
      spotaiBatchState.session = null;
      updateSpotAISessionUI(null);
    }
  } catch (err) {
    console.error("Failed to fetch session:", err);
  }
}


function updateSpotAISessionUI(session) {
  const badge = document.getElementById('spotaiSessionBadge');
  const btnLogin = document.getElementById('btnOpenSpotAILogin');
  const officerText = document.getElementById('spotaiOfficerText');

  if (session && session.authenticated) {
    if (badge) badge.classList.remove('hidden');
    if (badge) badge.classList.add('flex');
    if (btnLogin) btnLogin.classList.add('hidden');
    if (officerText) {
      const name = session.name || session.username || 'Officer';
      const office = session.off_name ? ` (${session.off_name})` : '';
      officerText.innerText = `${name}${office}`;
    }
  } else {
    if (badge) badge.classList.add('hidden');
    if (badge) badge.classList.remove('flex');
    if (btnLogin) btnLogin.classList.remove('hidden');
  }
  safeCreateIcons();
}

// --- Column Customizer UI Controls ---
function renderColumnCustomizer() {
  const container = document.getElementById('spotaiColumnsList');
  const badge = document.getElementById('spotaiColCountBadge');
  if (!container) return;

  if (badge) {
    badge.innerText = `${customExportColumns.length} Columns`;
  }

  const previewEl = document.getElementById('spotaiColPreviewText');
  if (previewEl) {
    const labels = customExportColumns.map(id => {
      const found = AVAILABLE_EXPORT_COLUMNS.find(c => c.id === id);
      return found ? found.label.replace(/\s*\(.*?\)/, '') : id;
    });
    previewEl.innerText = labels.join(" → ");
  }

  let html = "";
  customExportColumns.forEach((colId, idx) => {
    const isFirst = idx === 0;
    const isLast = idx === customExportColumns.length - 1;

    let optionsHtml = "";
    AVAILABLE_EXPORT_COLUMNS.forEach(opt => {
      const selected = opt.id === colId ? "selected" : "";
      optionsHtml += `<option value="${opt.id}" ${selected}>${opt.label}</option>`;
    });

    html += `
      <div class="flex items-center gap-1.5 p-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-2xs group">
        <span class="w-11 text-center font-mono font-bold text-[10px] text-cyan-600 dark:text-cyan-400 bg-cyan-500/10 px-1 py-1 rounded shrink-0">
          Col ${idx + 1}
        </span>
        <select 
          onchange="changeExportColumn(${idx}, this.value)" 
          class="flex-1 min-w-0 px-2 py-1 bg-slate-50 dark:bg-slate-950 text-xs font-medium text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 rounded-md focus:outline-none focus:border-cyan-500">
          ${optionsHtml}
        </select>
        <div class="flex items-center gap-0.5 shrink-0">
          <button type="button" onclick="moveExportColumn(${idx}, -1)" ${isFirst ? 'disabled class="opacity-25 p-1 text-slate-400"' : 'class="p-1 text-slate-400 hover:text-cyan-500 transition cursor-pointer"'} title="Move left/up">
            <i data-lucide="chevron-left" class="w-3.5 h-3.5"></i>
          </button>
          <button type="button" onclick="moveExportColumn(${idx}, 1)" ${isLast ? 'disabled class="opacity-25 p-1 text-slate-400"' : 'class="p-1 text-slate-400 hover:text-cyan-500 transition cursor-pointer"'} title="Move right/down">
            <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
          </button>
          <button type="button" onclick="removeExportColumn(${idx})" class="p-1 text-slate-400 hover:text-rose-500 transition cursor-pointer" title="Remove column">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  safeCreateIcons();
}

function changeExportColumn(idx, newKey) {
  if (idx >= 0 && idx < customExportColumns.length) {
    customExportColumns[idx] = newKey;
    saveColumnPreferences();
    renderColumnCustomizer();
  }
}

function moveExportColumn(idx, dir) {
  const target = idx + dir;
  if (target < 0 || target >= customExportColumns.length) return;
  const temp = customExportColumns[idx];
  customExportColumns[idx] = customExportColumns[target];
  customExportColumns[target] = temp;
  saveColumnPreferences();
  renderColumnCustomizer();
}

function removeExportColumn(idx) {
  if (customExportColumns.length <= 1) {
    alert("You must keep at least 1 column for Excel export.");
    return;
  }
  customExportColumns.splice(idx, 1);
  saveColumnPreferences();
  renderColumnCustomizer();
}

function addExportColumn() {
  const existingSet = new Set(customExportColumns);
  const nextCol = AVAILABLE_EXPORT_COLUMNS.find(c => !existingSet.has(c.id)) || AVAILABLE_EXPORT_COLUMNS[0];
  customExportColumns.push(nextCol.id);
  saveColumnPreferences();
  renderColumnCustomizer();
}

function applyColumnPreset(presetKey) {
  if (presetKey === 'reset') {
    customExportColumns = [...COLUMN_PRESETS.disconnection];
  } else if (COLUMN_PRESETS[presetKey]) {
    customExportColumns = [...COLUMN_PRESETS[presetKey]];
  }
  saveColumnPreferences();
  renderColumnCustomizer();
}

async function exportCustomExcelNow() {
  if (!spotaiBatchState.results || spotaiBatchState.results.length === 0) {
    alert("No downloaded records available to export. Run a batch first.");
    return;
  }
  const btn = document.getElementById('btnExportCustomExcel');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Exporting...</span>`;
    safeCreateIcons();
  }
  try {
    const res = await callAPI('spotai_export_custom_excel', customExportColumns);
    if (res && res.success) {
      alert(`Excel report exported successfully!\nFile: ${res.file_path}`);
    } else if (res && res.cancelled) {
      // User cancelled file picker
    } else {
      alert("Failed to export Excel: " + (res ? res.error : "Unknown error"));
    }
  } catch (err) {
    alert("Export error: " + err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="file-spreadsheet" class="w-4 h-4"></i><span>Export Custom Excel</span>`;
      safeCreateIcons();
    }
  }
}

// --- Custom Column Modal Controls ---
function openColumnCustomizerModal() {
  renderColumnCustomizer();
  const modal = document.getElementById('spotaiColumnCustomizerModal');
  if (modal) modal.classList.remove('hidden');
  safeCreateIcons();
}

function closeColumnCustomizerModal() {
  const modal = document.getElementById('spotaiColumnCustomizerModal');
  if (modal) modal.classList.add('hidden');
}

// --- Login Modal Controls ---
function openSpotAILoginModal() {
  resetSpotAILoginStep();
  const modal = document.getElementById('spotaiLoginModal');
  if (modal) modal.classList.remove('hidden');
  safeCreateIcons();
}

function closeSpotAILoginModal() {
  const modal = document.getElementById('spotaiLoginModal');
  if (modal) modal.classList.add('hidden');
}

function resetSpotAILoginStep() {
  const step1 = document.getElementById('spotaiAuthStep1');
  const step2 = document.getElementById('spotaiAuthStep2');
  const err1 = document.getElementById('spotaiLoginError');
  const err2 = document.getElementById('spotaiOtpError');
  if (step1) step1.classList.remove('hidden');
  if (step2) step2.classList.add('hidden');
  if (err1) { err1.classList.add('hidden'); err1.innerText = ''; }
  if (err2) { err2.classList.add('hidden'); err2.innerText = ''; }
}

async function handleSpotAIRequestOtp() {
  const userEl = document.getElementById('spotaiLoginUser');
  const passEl = document.getElementById('spotaiLoginPass');
  const errEl = document.getElementById('spotaiLoginError');
  const btn = document.getElementById('btnSpotAISendOtp');

  const u = (userEl?.value || '').trim();
  const p = (passEl?.value || '').trim();

  if (!u || !p) {
    if (errEl) {
      errEl.innerText = "Please enter both Username and Password.";
      errEl.classList.remove('hidden');
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Sending OTP...</span>`;
    safeCreateIcons();
  }
  if (errEl) errEl.classList.add('hidden');

  try {
    const res = await callAPI('spotai_request_otp', u, p);
    if (res && res.success) {
      const step1 = document.getElementById('spotaiAuthStep1');
      const step2 = document.getElementById('spotaiAuthStep2');
      if (step1) step1.classList.add('hidden');
      if (step2) step2.classList.remove('hidden');
      const otpInput = document.getElementById('spotaiLoginOtp');
      if (otpInput) {
        otpInput.value = '';
        otpInput.focus();
      }
    } else {
      if (errEl) {
        errEl.innerText = res ? (res.error || "Failed to dispatch OTP") : "Server connection failed";
        errEl.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = `Network error: ${err.message || err}`;
      errEl.classList.remove('hidden');
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Send OTP</span>`;
      safeCreateIcons();
    }
  }
}

async function handleSpotAIVerifyOtp() {
  const userEl = document.getElementById('spotaiLoginUser');
  const otpEl = document.getElementById('spotaiLoginOtp');
  const errEl = document.getElementById('spotaiOtpError');
  const btn = document.getElementById('btnSpotAIVerifyOtp');

  const u = (userEl?.value || '').trim();
  const o = (otpEl?.value || '').trim();

  if (!o || o.length < 4) {
    if (errEl) {
      errEl.innerText = "Please enter the OTP received on your mobile.";
      errEl.classList.remove('hidden');
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Verifying...</span>`;
    safeCreateIcons();
  }
  if (errEl) errEl.classList.add('hidden');

  try {
    const res = await callAPI('spotai_verify_otp', u, o);
    if (res && res.success) {
      closeSpotAILoginModal();
      await initSpotAIModule();
    } else {
      if (errEl) {
        errEl.innerText = res ? (res.error || "Invalid OTP entered") : "Verification failed";
        errEl.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = `Error: ${err.message || err}`;
      errEl.classList.remove('hidden');
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="check-circle-2" class="w-3.5 h-3.5"></i><span>Verify & Activate</span>`;
      safeCreateIcons();
    }
  }
}

async function handleSpotAILogout() {
  if (!confirm("Are you sure you want to log out from the portal?")) return;
  try {
    await callAPI('spotai_logout');
    await initSpotAIModule();
  } catch (err) {
    console.error("Logout failed:", err);
  }
}

// --- Input Mode Toggling ---
function switchSpotAIInputMode(mode) {
  const btnPaste = document.getElementById('btnInputModePaste');
  const btnFile = document.getElementById('btnInputModeFile');
  const pasteBox = document.getElementById('spotaiPasteContainer');
  const fileBox = document.getElementById('spotaiFileContainer');

  if (mode === 'paste') {
    if (btnPaste) btnPaste.className = "px-2.5 py-1 rounded-md font-bold bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
    if (btnFile) btnFile.className = "px-2.5 py-1 rounded-md font-medium text-slate-500 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer";
    if (pasteBox) pasteBox.classList.remove('hidden');
    if (fileBox) fileBox.classList.add('hidden');
  } else {
    if (btnPaste) btnPaste.className = "px-2.5 py-1 rounded-md font-medium text-slate-500 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer";
    if (btnFile) btnFile.className = "px-2.5 py-1 rounded-md font-bold bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
    if (pasteBox) pasteBox.classList.add('hidden');
    if (fileBox) fileBox.classList.remove('hidden');
  }
  safeCreateIcons();
}

function handleSpotAITextInput() {
  const text = document.getElementById('spotaiIdsInput')?.value || '';
  const matches = text.match(/\b\d{9}\b/g) || [];
  const unique = Array.from(new Set(matches));
  const countEl = document.getElementById('spotaiDetectedCount');
  if (countEl) {
    countEl.innerText = `${unique.length} valid IDs detected`;
  }
}

async function pickSpotAIConsumerFile() {
  try {
    const res = await callAPI('spotai_pick_consumer_file');
    if (res && res.success) {
      spotaiBatchState.fileIds = res.consumer_ids || [];
      const nameEl = document.getElementById('spotaiSelectedFileName');
      const countEl = document.getElementById('spotaiSelectedFileCount');
      const card = document.getElementById('spotaiFileSelectedCard');
      if (nameEl) nameEl.innerText = res.path.split(/[\\/]/).pop();
      if (countEl) countEl.innerText = `${res.count} consumer IDs extracted`;
      if (card) card.classList.remove('hidden');
    }
  } catch (err) {
    console.error("File selection error:", err);
  }
}

function clearSpotAISelectedFile() {
  spotaiBatchState.fileIds = [];
  const card = document.getElementById('spotaiFileSelectedCard');
  if (card) card.classList.add('hidden');
}

function toggleSpotAIMonthInput() {
  const selectedOpt = document.querySelector('input[name="spotaiBillOpt"]:checked')?.value;
  const wrapper = document.getElementById('spotaiMonthInputWrapper');
  if (wrapper) {
    if (selectedOpt === 'month') {
      wrapper.classList.remove('hidden');
      const input = document.getElementById('spotaiTargetMonth');
      if (input) input.focus();
    } else {
      wrapper.classList.add('hidden');
    }
  }
}

async function pickSpotAIDownloadFolder() {
  try {
    const res = await callAPI('spotai_pick_download_folder');
    if (res && res.success && res.folder) {
      const input = document.getElementById('spotaiOutputDir');
      if (input) input.value = res.folder;
    }
  } catch (err) {
    console.error("Pick folder error:", err);
  }
}

function clearSpotAIInputs() {
  const textInput = document.getElementById('spotaiIdsInput');
  if (textInput) textInput.value = '';
  handleSpotAITextInput();
  clearSpotAISelectedFile();
  const monthInput = document.getElementById('spotaiTargetMonth');
  if (monthInput) monthInput.value = '';
}

// --- Batch Download Execution ---
async function startSpotAIBatchDownload() {
  if (spotaiBatchState.running) return;

  // Check login
  if (!spotaiBatchState.session || !spotaiBatchState.session.authenticated) {
    openSpotAILoginModal();
    return;
  }

  // Determine Consumer IDs
  const isPasteMode = !document.getElementById('spotaiPasteContainer')?.classList.contains('hidden');
  let ids = [];
  if (isPasteMode) {
    const text = document.getElementById('spotaiIdsInput')?.value || '';
    const matches = text.match(/\b\d{9}\b/g) || [];
    ids = Array.from(new Set(matches));
  } else {
    ids = spotaiBatchState.fileIds || [];
  }

  if (!ids || ids.length === 0) {
    alert("Please enter or upload at least one valid 9-digit Consumer ID.");
    return;
  }

  const billOpt = document.querySelector('input[name="spotaiBillOpt"]:checked')?.value || 'latest';
  const targetMonth = (document.getElementById('spotaiTargetMonth')?.value || '').trim();
  const outputDir = (document.getElementById('spotaiOutputDir')?.value || '').trim();
  const speedOpt = document.querySelector('input[name="spotaiSpeedOpt"]:checked')?.value || '8';
  const maxWorkers = parseInt(speedOpt, 10) || 8;

  if (billOpt === 'month' && !targetMonth) {
    alert("Please enter a billing month (e.g. 08.2026).");
    document.getElementById('spotaiTargetMonth')?.focus();
    return;
  }

  // Setup UI for running state
  spotaiBatchState.running = true;
  spotaiBatchState.results = [];

  const btnStart = document.getElementById('btnStartSpotAIBatch');
  const banner = document.getElementById('spotaiProgressBanner');
  const postBar = document.getElementById('spotaiPostActionBar');
  const tableCont = document.getElementById('spotaiTableContainer');

  if (btnStart) {
    btnStart.disabled = true;
    btnStart.classList.add('opacity-60', 'cursor-not-allowed');
  }
  if (banner) banner.classList.remove('hidden');
  if (postBar) postBar.classList.add('hidden');
  if (tableCont) tableCont.classList.add('hidden');

  // Reset banner indicators
  const titleEl = document.getElementById('spotaiProgressTitle');
  const percentEl = document.getElementById('spotaiProgressPercent');
  const subtitleEl = document.getElementById('spotaiProgressSubtitle');
  const barEl = document.getElementById('spotaiProgressBar');

  if (titleEl) titleEl.innerText = `Downloading Bills (0 of ${ids.length})...`;
  if (percentEl) percentEl.innerText = '0%';
  if (subtitleEl) subtitleEl.innerText = `Initializing ${maxWorkers} high-speed parallel workers...`;
  if (barEl) barEl.style.width = '0%';

  renderSpotAITable([]);

  try {
    const res = await callAPI(
      'spotai_start_batch_download',
      ids,
      billOpt,
      targetMonth,
      outputDir,
      maxWorkers,
      customExportColumns
    );
    if (!res || !res.success) {
      alert("Failed to start batch download: " + (res ? res.error : "Unknown error"));
      stopSpotAIBatchPolling();
      return;
    }

    // Start fast polling (500ms) for real-time streaming updates
    spotaiBatchState.pollTimer = setInterval(pollSpotAIBatchProgress, 500);
  } catch (err) {
    console.error("Batch download trigger error:", err);
    alert("Error starting batch: " + err);
    stopSpotAIBatchPolling();
  }
}

async function pollSpotAIBatchProgress() {
  try {
    const status = await callAPI('spotai_get_batch_status');
    if (!status) return;

    const processed = Number(status.processed) || 0;
    const total = Math.max(1, Number(status.total) || 1);
    const rawPercent = Math.round((processed / total) * 100);
    const percent = status.running
      ? Math.min(99, Math.max(0, rawPercent))
      : 100;

    // Update banner
    const titleEl = document.getElementById('spotaiProgressTitle');
    const percentEl = document.getElementById('spotaiProgressPercent');
    const subtitleEl = document.getElementById('spotaiProgressSubtitle');
    const barEl = document.getElementById('spotaiProgressBar');

    if (percentEl) percentEl.innerText = `${percent}%`;
    if (barEl) barEl.style.width = `${percent}%`;

    if (status.running) {
      if (titleEl) titleEl.innerText = `Downloading Bills (${processed} of ${total})...`;
      if (subtitleEl) {
        subtitleEl.innerText = status.current_cid 
          ? `Processing Consumer: ${status.current_cid} (Dues & Bill)`
          : `Processing batch downloads...`;
      }
      if (status.results && status.results.length > 0) {
        spotaiBatchState.results = status.results;
        renderSpotAITable(status.results);
      }
    } else {
      // Completed or cancelled
      stopSpotAIBatchPolling();
      const bannerEl = document.getElementById('spotaiProgressBanner');
      if (bannerEl) bannerEl.classList.add('hidden');

      spotaiBatchState.results = status.results || [];
      renderSpotAITable(spotaiBatchState.results);

      // Show summary action bar
      const postBar = document.getElementById('spotaiPostActionBar');
      const succEl = document.getElementById('spotaiStatSuccess');
      const failEl = document.getElementById('spotaiStatFailed');
      if (postBar) postBar.classList.remove('hidden');
      if (succEl) succEl.innerText = `${status.success_count || 0} Downloaded`;
      if (failEl) failEl.innerText = `${status.failed_count || 0} Failed / Missing`;

      const btnStart = document.getElementById('btnStartSpotAIBatch');
      if (btnStart) {
        btnStart.disabled = false;
        btnStart.classList.remove('opacity-60', 'cursor-not-allowed');
      }
      safeCreateIcons();
    }
  } catch (err) {
    console.error("Error polling batch progress:", err);
  }
}

function stopSpotAIBatchPolling() {
  if (spotaiBatchState.pollTimer) {
    clearInterval(spotaiBatchState.pollTimer);
    spotaiBatchState.pollTimer = null;
  }
  spotaiBatchState.running = false;
  safeCreateIcons();
}

async function cancelSpotAIBatch() {
  if (!spotaiBatchState.running) return;
  try {
    await callAPI('spotai_cancel_batch');
    const titleEl = document.getElementById('spotaiProgressTitle');
    if (titleEl) titleEl.innerText = "Cancelling Batch...";
  } catch (err) {
    console.error("Cancel batch error:", err);
  }
}

// --- Table Rendering with Comprehensive Dues Breakdown ---
function renderSpotAITable(results) {
  const tbody = document.getElementById('spotaiTableBody');
  const tableCont = document.getElementById('spotaiTableContainer');
  const countEl = document.getElementById('spotaiTableCount');
  if (!tbody) return;

  if (!results || results.length === 0) {
    tbody.innerHTML = "";
    if (tableCont) tableCont.classList.add('hidden');
    return;
  }

  if (tableCont) tableCont.classList.remove('hidden');
  if (countEl) countEl.innerText = `${results.length} total records`;

  let html = "";
  results.forEach((r, idx) => {
    const isSuccess = r.status === 'Success';
    const statusPill = isSuccess
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">Success</span>`
      : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20" title="${r.error || ''}">${r.status}</span>`;

    const actionBtn = isSuccess && r.file_path
      ? `<div class="flex items-center justify-center gap-1">
           <button onclick="openSpotAIPdf('${r.file_path.replace(/\\/g, '\\\\')}')" class="px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-[11px] font-medium transition flex items-center gap-1 cursor-pointer" title="Open PDF">
             <i data-lucide="eye" class="w-3 h-3 text-cyan-500"></i> View
           </button>
         </div>`
      : `<span class="text-slate-400 text-[10px]" title="${r.error || ''}">${r.error ? (r.error.length > 20 ? r.error.substring(0, 18) + '...' : r.error) : '-'}</span>`;

    const nameText = r.name && r.name !== '-' ? r.name : '-';
    const subDetails = (r.class_desc && r.class_desc !== '-')
      ? `<span class="block text-[10px] text-slate-400 font-normal truncate max-w-[140px]">${r.class_desc}${r.tariff && r.tariff !== '-' ? ` (${r.tariff})` : ''}</span>`
      : '';

    html += `
      <tr class="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-3 text-center text-slate-400 font-mono text-[11px]">${idx + 1}</td>
        <td class="py-2.5 px-3 font-bold text-slate-800 dark:text-slate-100 font-mono">${r.consumer_id}</td>
        <td class="py-2.5 px-3 font-medium text-slate-700 dark:text-slate-200">
          <div class="truncate max-w-[150px] font-semibold">${nameText}</div>
          ${subDetails}
        </td>
        <td class="py-2.5 px-3 text-slate-600 dark:text-slate-300 font-mono text-[11px]">${r.bill_month || '-'}</td>
        <td class="py-2.5 px-3 text-right font-mono text-slate-600 dark:text-slate-300">${r.bill_amount ? `₹${r.bill_amount}` : '-'}</td>
        <td class="py-2.5 px-3 text-right font-mono font-medium text-amber-600 dark:text-amber-400">${r.osd_principal ? `₹${r.osd_principal}` : '₹0.00'}</td>
        <td class="py-2.5 px-3 text-right font-mono text-rose-500 dark:text-rose-400">${r.lpsc ? `₹${r.lpsc}` : '₹0.00'}</td>
        <td class="py-2.5 px-3 text-right font-mono font-bold text-slate-900 dark:text-slate-100">${r.total_dues ? `₹${r.total_dues}` : '₹0.00'}</td>
        <td class="py-2.5 px-3 text-center">${statusPill}</td>
        <td class="py-2.5 px-3 text-center">${actionBtn}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
  safeCreateIcons();
}

// --- Batch Post-Actions (Print & Folder) ---
async function printAllDownloadedBills() {
  const btn = document.getElementById('btnPrintAllBills');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Preparing Print...</span>`;
    safeCreateIcons();
  }

  try {
    const res = await callAPI('spotai_print_all_bills');
    if (res && res.success) {
      alert(res.message || "Sent all bills to printer");
    } else {
      alert("Printing failed: " + (res ? res.error : "Unknown error"));
    }
  } catch (err) {
    alert("Print error: " + err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="printer" class="w-4 h-4"></i><span>Print All Bills</span>`;
      safeCreateIcons();
    }
  }
}

async function openSpotAIDownloadFolder() {
  try {
    await callAPI('spotai_open_download_folder');
  } catch (err) {
    console.error("Open folder error:", err);
  }
}

async function openSpotAIPdf(path) {
  try {
    await callAPI('spotai_open_file', path);
  } catch (err) {
    console.error("Open PDF error:", err);
  }
}

// --- License & Access Control Handlers ---
function copySpotAIRequestCode() {
  const input = document.getElementById('spotaiMyRequestCode');
  if (input && input.value) {
    navigator.clipboard.writeText(input.value).then(() => {
      alert("Request Code copied to clipboard: " + input.value);
    }).catch(() => {
      input.select();
      document.execCommand('copy');
      alert("Request Code copied to clipboard!");
    });
  }
}

function openTelegramSupport() {
  const input = document.getElementById('spotaiMyRequestCode');
  const code = (input?.value || '').trim();
  if (code) {
    navigator.clipboard.writeText(code).catch(() => {});
  }
  // Open Telegram support group link
  const tgUrl = 'https://t.me/wbtools_support';
  try {
    callAPI('system_open_external', tgUrl);
  } catch (e) {
    window.open(tgUrl, '_blank');
  }
}


async function applySpotAIActivationKey() {
  const keyInput = document.getElementById('spotaiActivationKeyInput');
  const msgEl = document.getElementById('spotaiActivationMsg');
  const btn = document.getElementById('btnApplyActivationKey');

  const key = (keyInput?.value || '').trim();
  if (!key) {
    if (msgEl) {
      msgEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-500/10 text-rose-600 block";
      msgEl.innerText = "Please enter an Activation Key.";
    }
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Activating...</span>`;
    safeCreateIcons();
  }

  try {
    const res = await callAPI('spotai_activate_module', key);
    if (res && res.success) {
      if (msgEl) {
        msgEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-emerald-500/10 text-emerald-600 block";
        msgEl.innerText = "Activated successfully! Unlocking module...";
      }
      setTimeout(() => {
        initSpotAIModule();
      }, 1000);
    } else {
      if (msgEl) {
        msgEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-500/10 text-rose-600 block";
        msgEl.innerText = res ? (res.error || "Activation failed.") : "Verification failed.";
      }
    }
  } catch (err) {
    if (msgEl) {
      msgEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-rose-500/10 text-rose-600 block";
      msgEl.innerText = "Error: " + err;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="unlock" class="w-3.5 h-3.5"></i><span>Activate</span>`;
      safeCreateIcons();
    }
  }
}

// Admin Key Generator Modal
function openAdminKeyGenModal() {
  const modal = document.getElementById('spotaiAdminKeyGenModal');
  const err = document.getElementById('adminKeyGenError');
  const resBox = document.getElementById('adminKeyGenResultBox');
  const pinInput = document.getElementById('adminKeyGenPin');
  if (err) err.classList.add('hidden');
  if (resBox) resBox.classList.add('hidden');
  if (pinInput) pinInput.value = '';
  if (modal) modal.classList.remove('hidden');
  safeCreateIcons();
}

function closeAdminKeyGenModal() {
  const modal = document.getElementById('spotaiAdminKeyGenModal');
  if (modal) modal.classList.add('hidden');
}

async function handleAdminGenerateKeySubmit() {
  const pinInput = document.getElementById('adminKeyGenPin');
  const reqInput = document.getElementById('adminKeyGenReqCode');
  const errEl = document.getElementById('adminKeyGenError');
  const resBox = document.getElementById('adminKeyGenResultBox');
  const outInput = document.getElementById('adminKeyGenOutput');

  const pin = (pinInput?.value || '').trim();
  const req = (reqInput?.value || '').trim();

  if (!pin) {
    if (errEl) {
      errEl.innerText = "Enter Admin Security PIN.";
      errEl.classList.remove('hidden');
    }
    return;
  }
  if (!req) {
    if (errEl) {
      errEl.innerText = "Enter User Request Code.";
      errEl.classList.remove('hidden');
    }
    return;
  }

  if (errEl) errEl.classList.add('hidden');

  try {
    const res = await callAPI('spotai_admin_generate_key', req, pin);
    if (res && res.success && res.activation_key) {
      if (outInput) outInput.value = res.activation_key;
      if (resBox) resBox.classList.remove('hidden');
      safeCreateIcons();
    } else {
      if (errEl) {
        errEl.innerText = res ? (res.error || "Generation failed.") : "Failed to generate key.";
        errEl.classList.remove('hidden');
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = "Error: " + err;
      errEl.classList.remove('hidden');
    }
  }
}

function copyAdminGeneratedKey() {
  const outInput = document.getElementById('adminKeyGenOutput');
  if (outInput && outInput.value) {
    navigator.clipboard.writeText(outInput.value).then(() => {
      alert("Activation Key copied: " + outInput.value);
    }).catch(() => {
      outInput.select();
      document.execCommand('copy');
      alert("Activation Key copied!");
    });
  }
}

function toggleSpotAIAdminMenu(forceState) {
  const menu = document.getElementById('spotaiAdminDropdownMenu');
  if (!menu) return;
  if (typeof forceState === 'boolean') {
    if (forceState) menu.classList.remove('hidden');
    else menu.classList.add('hidden');
  } else {
    menu.classList.toggle('hidden');
  }
  safeCreateIcons();
}

// Close admin dropdown when clicking outside
document.addEventListener('click', (e) => {
  const btn = document.getElementById('btnSpotAIAdminDropdown');
  const menu = document.getElementById('spotaiAdminDropdownMenu');
  if (btn && menu && !btn.contains(e.target) && !menu.contains(e.target)) {
    menu.classList.add('hidden');
  }
});

// Secret Admin Shortcut: Press Ctrl + Shift + A anytime to open Key Generator!
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
    e.preventDefault();
    openAdminKeyGenModal();
  }
});

async function handleRelockSpotAIModule() {
  if (!confirm("Are you sure you want to re-lock the module on this PC?\nThis will remove the local license and return to the Activation Required screen.")) {
    return;
  }
  try {
    const res = await callAPI('spotai_reset_license');
    if (res && res.success) {
      alert("Module re-locked! Reloading access check...");
      initSpotAIModule();
    } else {
      alert("Failed to reset license: " + (res ? res.error : "Unknown error"));
    }
  } catch (err) {
    alert("Error resetting license: " + err);
  }
}

// Window exports
window.initSpotAIModule = initSpotAIModule;
window.openColumnCustomizerModal = openColumnCustomizerModal;
window.closeColumnCustomizerModal = closeColumnCustomizerModal;
window.renderColumnCustomizer = renderColumnCustomizer;
window.changeExportColumn = changeExportColumn;
window.moveExportColumn = moveExportColumn;
window.removeExportColumn = removeExportColumn;
window.addExportColumn = addExportColumn;
window.applyColumnPreset = applyColumnPreset;
window.exportCustomExcelNow = exportCustomExcelNow;
window.openSpotAILoginModal = openSpotAILoginModal;
window.closeSpotAILoginModal = closeSpotAILoginModal;
window.resetSpotAILoginStep = resetSpotAILoginStep;
window.handleSpotAIRequestOtp = handleSpotAIRequestOtp;
window.handleSpotAIVerifyOtp = handleSpotAIVerifyOtp;
window.handleSpotAILogout = handleSpotAILogout;
window.switchSpotAIInputMode = switchSpotAIInputMode;
window.handleSpotAITextInput = handleSpotAITextInput;
window.pickSpotAIConsumerFile = pickSpotAIConsumerFile;
window.clearSpotAISelectedFile = clearSpotAISelectedFile;
window.toggleSpotAIMonthInput = toggleSpotAIMonthInput;
window.pickSpotAIDownloadFolder = pickSpotAIDownloadFolder;
window.clearSpotAIInputs = clearSpotAIInputs;
window.startSpotAIBatchDownload = startSpotAIBatchDownload;
window.cancelSpotAIBatch = cancelSpotAIBatch;
window.printAllDownloadedBills = printAllDownloadedBills;
window.openSpotAIDownloadFolder = openSpotAIDownloadFolder;
window.openSpotAIPdf = openSpotAIPdf;
window.copySpotAIRequestCode = copySpotAIRequestCode;
window.openTelegramSupport = openTelegramSupport;
window.applySpotAIActivationKey = applySpotAIActivationKey;
window.openAdminKeyGenModal = openAdminKeyGenModal;
window.closeAdminKeyGenModal = closeAdminKeyGenModal;
window.handleAdminGenerateKeySubmit = handleAdminGenerateKeySubmit;
window.copyAdminGeneratedKey = copyAdminGeneratedKey;
window.toggleSpotAIAdminMenu = toggleSpotAIAdminMenu;
window.handleRelockSpotAIModule = handleRelockSpotAIModule;



