// =============================================================================
// Consumer Dues & Verification Studio Controller
// =============================================================================

let currentSingleOsdData = null;
let bulkOsdState = {
  running: false,
  pollTimer: null,
  results: [],
  selectedFilter: 'all',
  fileIds: []
};

// --- Mode Switching (Single vs Bulk) ---
function switchOsdMode(mode) {
  const btnSingle = document.getElementById('osdModeBtnSingle');
  const btnBulk = document.getElementById('osdModeBtnBulk');
  const viewSingle = document.getElementById('osdSingleView');
  const viewBulk = document.getElementById('osdBulkView');

  if (mode === 'single') {
    if (btnSingle) {
      btnSingle.className = "px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
    }
    if (btnBulk) {
      btnBulk.className = "px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer";
    }
    if (viewSingle) viewSingle.classList.remove('hidden');
    if (viewBulk) viewBulk.classList.add('hidden');
  } else {
    if (btnSingle) {
      btnSingle.className = "px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer";
    }
    if (btnBulk) {
      btnBulk.className = "px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
    }
    if (viewSingle) viewSingle.classList.add('hidden');
    if (viewBulk) viewBulk.classList.remove('hidden');
  }
  safeCreateIcons();
}

// =============================================================================
// 1. Single Consumer Dues Check
// =============================================================================
async function executeSingleOsdCheck(forceRefresh = false) {
  const inputEl = document.getElementById('osdSingleInput');
  const cid = String(inputEl ? inputEl.value : '').trim();

  if (!cid || !/^\d{9}$/.test(cid)) {
    alert("Please enter a valid 9-digit Consumer ID.");
    if (inputEl) inputEl.focus();
    return;
  }

  const loadingCard = document.getElementById('osdSingleLoading');
  const resultCard = document.getElementById('osdSingleResultCard');
  const errorCard = document.getElementById('osdSingleErrorCard');
  const btnCheck = document.getElementById('btnOsdSingleCheck');

  if (loadingCard) loadingCard.classList.remove('hidden');
  if (resultCard) resultCard.classList.add('hidden');
  if (errorCard) errorCard.classList.add('hidden');
  if (btnCheck) btnCheck.disabled = true;

  try {
    const res = await callAPI('check_single_osd', cid, forceRefresh);
    if (loadingCard) loadingCard.classList.add('hidden');
    if (btnCheck) btnCheck.disabled = false;

    if (res && res.success && res.data) {
      renderSingleOsdResult(res.data);
    } else {
      showSingleOsdError(res ? (res.error || "Unable to retrieve consumer record.") : "Service response error");
    }
  } catch (err) {
    console.error("Single check failed:", err);
    if (loadingCard) loadingCard.classList.add('hidden');
    if (btnCheck) btnCheck.disabled = false;
    showSingleOsdError("Network connection timeout. Please check your internet connection.");
  }
}

function renderSingleOsdResult(d) {
  currentSingleOsdData = d;
  const card = document.getElementById('osdSingleResultCard');
  if (!card) return;

  // Header Data & Prominent Address
  const cidEl = document.getElementById('osdResCid');
  const nameEl = document.getElementById('osdResName');
  const addrHeaderEl = document.getElementById('osdResAddrHeader');
  const officeEl = document.getElementById('osdResOffice');
  const addrEl = document.getElementById('osdResAddr');
  const connDateEl = document.getElementById('osdResConnDate');

  if (cidEl) cidEl.innerText = d.consumerId || '-';
  if (nameEl) nameEl.innerText = d.name || 'N/A';
  if (addrHeaderEl) addrHeaderEl.innerText = d.address || 'Address not available';
  if (officeEl) {
    officeEl.innerText = d.office || 'N/A';
    officeEl.title = d.office || '';
  }
  if (addrEl) addrEl.innerText = d.address || 'Address not available';
  if (connDateEl) connDateEl.innerText = d.connDate || '-';

  // Connection Status Badge
  const statusBadge = document.getElementById('osdResStatusBadge');
  const rawStatus = (d.connectionStatus && d.connectionStatus !== 'N/A') ? String(d.connectionStatus).trim() : '';
  const normStatus = rawStatus.toUpperCase();
  if (statusBadge) {
    if (d.isDeemed || normStatus.includes('DEEMED')) {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex items-center gap-1";
      statusBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span> ${escapeHtml(rawStatus || 'Deemed Disconnected')}`;
    } else if (d.isTempDisconnected || normStatus.includes('TEMP')) {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex items-center gap-1";
      statusBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span> ${escapeHtml(rawStatus || 'Temp Disconnected')}`;
    } else if (d.isDisconnected || normStatus.includes('DISCONNECT') || normStatus.includes('DISCONN')) {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30 flex items-center gap-1";
      statusBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span> ${escapeHtml(rawStatus || 'Disconnected')}`;
    } else if (d.isLive || normStatus === 'LIVE' || (!normStatus.includes('DISCONNECT') && normStatus.includes('CONNECT'))) {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1";
      statusBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> ${escapeHtml(rawStatus || 'Connected')}`;
    } else if (rawStatus) {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/30";
      statusBadge.innerText = rawStatus;
    } else {
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/30";
      statusBadge.innerText = 'Status Unknown';
    }
  }

  // Financial Metrics
  const osdVal = Number(d.osd || 0);
  const lpscVal = Number(d.lpsc || 0);
  const totalVal = Number(d.totalDues || 0);

  const osdEl = document.getElementById('osdResOsd');
  const lpscEl = document.getElementById('osdResLpsc');
  const totalEl = document.getElementById('osdResTotal');

  if (osdEl) osdEl.innerText = `\u20B9 ${osdVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (lpscEl) lpscEl.innerText = `\u20B9 ${lpscVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  
  if (totalEl) {
    totalEl.innerText = `\u20B9 ${totalVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (totalVal > 0) {
      totalEl.className = "text-xl font-bold font-mono text-rose-600 dark:text-rose-400 mt-1 block";
    } else {
      totalEl.className = "text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1 block";
    }
  }

  // Cached notice
  const cachedBadge = document.getElementById('osdResCachedBadge');
  if (cachedBadge) {
    cachedBadge.innerText = d.cached ? '(Cached)' : '(Live)';
  }

  card.classList.remove('hidden');
  safeCreateIcons();
}

function showSingleOsdError(msg) {
  const errorCard = document.getElementById('osdSingleErrorCard');
  const errorText = document.getElementById('osdSingleErrorText');
  if (errorText) errorText.innerText = msg;
  if (errorCard) errorCard.classList.remove('hidden');
  safeCreateIcons();
}

function jumpToViewerFromOsd(consumerId) {
  const cid = consumerId || (currentSingleOsdData && currentSingleOsdData.consumerId);
  if (!cid) return;
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = cid;
  if (typeof switchTab === 'function') switchTab('viewer');
  if (typeof handleSearch === 'function') handleSearch();
}

// =============================================================================
// Floating Top Notification Bar for Progress
// =============================================================================
function showOsdNotification(title, subtitle, percent = 0, isRunning = true) {
  const bar = document.getElementById('osdNotificationBar');
  const titleEl = document.getElementById('osdNotifTitle');
  const subEl = document.getElementById('osdNotifSubtitle');
  const percentEl = document.getElementById('osdNotifPercent');
  const progBar = document.getElementById('osdNotifProgress');
  const spinner = document.getElementById('osdNotifSpinner');
  const stopBtn = document.getElementById('osdNotifStopBtn');
  const closeBtn = document.getElementById('osdNotifCloseBtn');

  if (!bar) return;

  if (titleEl) titleEl.innerText = title;
  if (subEl) subEl.innerText = subtitle;
  if (percentEl) percentEl.innerText = `${percent}%`;
  if (progBar) progBar.style.width = `${percent}%`;

  if (isRunning) {
    if (spinner) spinner.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    if (closeBtn) closeBtn.classList.add('hidden');
  } else {
    if (spinner) spinner.classList.add('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
    if (closeBtn) closeBtn.classList.remove('hidden');
  }

  bar.classList.remove('hidden');
  safeCreateIcons();
}

function hideOsdNotification() {
  const bar = document.getElementById('osdNotificationBar');
  if (bar) bar.classList.add('hidden');
}

// =============================================================================
// 2. Bulk Consumer Verification
// =============================================================================
function handleBulkInputMethodChange(method) {
  const textContainer = document.getElementById('bulkTextContainer');
  const fileContainer = document.getElementById('bulkFileContainer');
  const btnText = document.getElementById('btnBulkInputText');
  const btnFile = document.getElementById('btnBulkInputFile');

  if (method === 'text') {
    if (textContainer) textContainer.classList.remove('hidden');
    if (fileContainer) fileContainer.classList.add('hidden');
    if (btnText) btnText.className = "px-3 py-1 rounded-md text-xs font-bold bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
    if (btnFile) btnFile.className = "px-3 py-1 rounded-md text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer";
  } else {
    if (textContainer) textContainer.classList.add('hidden');
    if (fileContainer) fileContainer.classList.remove('hidden');
    if (btnText) btnText.className = "px-3 py-1 rounded-md text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer";
    if (btnFile) btnFile.className = "px-3 py-1 rounded-md text-xs font-bold bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs cursor-pointer";
  }
  safeCreateIcons();
}

function updateBulkTextCount() {
  const text = document.getElementById('bulkTextInput')?.value || '';
  const matches = text.match(/\b\d{9}\b/g) || [];
  const unique = Array.from(new Set(matches));
  const badge = document.getElementById('bulkIdCountBadge');
  if (badge) {
    badge.innerText = `${unique.length} Consumer IDs detected`;
    badge.className = unique.length > 0 
      ? "text-[11px] font-mono font-bold text-cyan-600 dark:text-cyan-400 px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20"
      : "text-[11px] text-slate-400";
  }
}

async function pickBulkOsdFile() {
  try {
    const res = await callAPI('select_osd_batch_file');
    if (res && res.success) {
      bulkOsdState.fileIds = res.consumer_ids || [];
      const fileLabel = document.getElementById('bulkSelectedFileName');
      const countLabel = document.getElementById('bulkSelectedFileCount');
      if (fileLabel) fileLabel.innerText = res.path.split(/[\\/]/).pop();
      if (countLabel) countLabel.innerText = `${res.count} unique 9-digit Consumer IDs detected`;
      document.getElementById('bulkFileSelectedCard')?.classList.remove('hidden');
    }
  } catch (err) {
    console.error("File selection failed:", err);
  }
}

function clearBulkSelectedFile() {
  bulkOsdState.fileIds = [];
  document.getElementById('bulkFileSelectedCard')?.classList.add('hidden');
}

async function startBulkOsdVerification() {
  if (bulkOsdState.running) return;

  // Determine IDs from text or selected file
  const isFileMode = !document.getElementById('bulkFileContainer')?.classList.contains('hidden');
  let ids = [];

  if (isFileMode) {
    ids = bulkOsdState.fileIds;
  } else {
    const text = document.getElementById('bulkTextInput')?.value || '';
    const matches = text.match(/\b\d{9}\b/g) || [];
    ids = Array.from(new Set(matches));
  }

  if (!ids || ids.length === 0) {
    alert("Please paste or upload at least one valid 9-digit Consumer ID.");
    return;
  }

  // Setup UI for running state
  bulkOsdState.running = true;
  bulkOsdState.results = [];

  const btnStart = document.getElementById('btnStartBulkOsd');
  const exportBar = document.getElementById('bulkExportBar');
  const emptyState = document.getElementById('bulkTableEmptyState');

  if (btnStart) {
    btnStart.disabled = true;
    btnStart.classList.add('opacity-60', 'cursor-not-allowed');
  }
  if (exportBar) exportBar.classList.add('hidden');
  if (emptyState) emptyState.classList.add('hidden');

  showOsdNotification("Verifying Records...", `Initializing verification for ${ids.length} consumers...`, 0, true);
  renderBulkTable([]);

  try {
    const res = await callAPI('start_bulk_osd', ids, false);
    if (!res || !res.success) {
      alert("Failed to start bulk verification: " + (res ? res.error : "Unknown error"));
      stopBulkOsdPolling();
      return;
    }

    // Start polling loop with friendly interval to prevent CPU churn
    bulkOsdState.pollTimer = setInterval(pollBulkOsdProgress, 1500);
  } catch (err) {
    console.error("Error starting bulk verification:", err);
    alert("Error starting bulk job: " + err);
    stopBulkOsdPolling();
  }
}

async function pollBulkOsdProgress() {
  try {
    const status = await callAPI('get_bulk_osd_status');
    if (!status || !status.success) return;

    const processed = status.processed || 0;
    const total = status.total || 1;
    const percent = Math.min(100, Math.round((processed / total) * 100));

    // Update Notification Banner
    if (status.running) {
      const sub = status.current_cid 
        ? `Checking Consumer: ${status.current_cid} (${processed} of ${total})` 
        : `Processed ${processed} of ${total} records...`;
      showOsdNotification("Verifying Records...", sub, percent, true);
    }

    // Update table with live results (updates when new results arrive, up to 150 rows max)
    if (status.results && status.results.length > 0) {
      const prevLen = bulkOsdState.results ? bulkOsdState.results.length : 0;
      if (status.results.length !== prevLen || !status.running) {
        bulkOsdState.results = status.results;
        renderBulkTable(status.results);
      }
    }

    // Completion or Cancellation
    if (!status.running) {
      stopBulkOsdPolling();
      const exportBar = document.getElementById('bulkExportBar');
      if (exportBar) exportBar.classList.remove('hidden');

      const btnStart = document.getElementById('btnStartBulkOsd');
      if (btnStart) {
        btnStart.disabled = false;
        btnStart.classList.remove('opacity-60', 'cursor-not-allowed');
      }

      // Count dues
      let withDues = 0;
      let zeroDues = 0;
      (status.results || []).forEach(r => {
        if (Number(r.totalDues || 0) > 0) withDues++;
        else if (r.status === 'Success') zeroDues++;
      });

      const finishTitle = status.cancelled ? "Verification Cancelled" : "Verification Complete";
      const finishSub = `Processed ${processed} records (${withDues} with dues, ${zeroDues} cleared).`;
      showOsdNotification(finishTitle, finishSub, percent, false);
    }
  } catch (err) {
    console.error("Error in bulk poll:", err);
  }
}

function stopBulkOsdPolling() {
  if (bulkOsdState.pollTimer) {
    clearInterval(bulkOsdState.pollTimer);
    bulkOsdState.pollTimer = null;
  }
  bulkOsdState.running = false;
  safeCreateIcons();
}

async function cancelBulkOsd() {
  if (!bulkOsdState.running) return;
  await callAPI('cancel_bulk_osd');
  showOsdNotification("Cancelling...", "Stopping batch verification...", 0, true);
}

// --- Bulk Preview Table Rendering ---
function renderBulkTable(results) {
  const tbody = document.getElementById('bulkOsdTableBody');
  const tableContainer = document.getElementById('bulkTableContainer');
  const emptyState = document.getElementById('bulkTableEmptyState');
  if (!tbody) return;

  if (!results || results.length === 0) {
    tbody.innerHTML = "";
    if (tableContainer) tableContainer.classList.add('hidden');
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (tableContainer) tableContainer.classList.remove('hidden');
  if (emptyState) emptyState.classList.add('hidden');

  // Filter items
  const filter = bulkOsdState.selectedFilter || 'all';
  const filtered = results.filter(r => {
    const tot = Number(r.totalDues || 0);
    const st = String(r.connectionStatus || '').toUpperCase();
    if (filter === 'dues') return tot > 0;
    if (filter === 'nodues') return tot === 0 && r.status === 'Success';
    if (filter === 'disconnected') return st.includes('DISCONNECT') || st.includes('DEEMED') || st.includes('TEMP');
    return true;
  });

  let html = "";
  filtered.forEach((r, idx) => {
    const osdVal = Number(r.osd || 0);
    const lpscVal = Number(r.lpsc || 0);
    const totVal = Number(r.totalDues || 0);
    const rawStatus = (r.connectionStatus && r.connectionStatus !== 'N/A') ? String(r.connectionStatus).trim() : '';
    const st = rawStatus.toUpperCase();

    // Status Pill - displays actual status fetched from PDF
    let statusPill = `<span class="text-[10px] text-slate-400 font-semibold">-</span>`;
    if (r.status === 'Failed') {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20" title="${escapeHtml(r.error || '')}">Error</span>`;
    } else if (r.isDeemed || st.includes('DEEMED')) {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">${escapeHtml(rawStatus || 'Deemed')}</span>`;
    } else if (r.isTempDisconnected || st.includes('TEMP')) {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/25">${escapeHtml(rawStatus || 'Temp Disconnected')}</span>`;
    } else if (r.isDisconnected || st.includes('DISCONNECT') || st.includes('DISCONN')) {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/25">${escapeHtml(rawStatus || 'Disconnected')}</span>`;
    } else if (r.isLive || st === 'LIVE' || (!st.includes('DISCONNECT') && st.includes('CONNECT'))) {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25">${escapeHtml(rawStatus || 'Connected')}</span>`;
    } else if (rawStatus) {
      statusPill = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/25">${escapeHtml(rawStatus)}</span>`;
    }

    // Office snippet
    const officeSnippet = (r.office && r.office !== 'N/A') 
      ? r.office.replace(/customer\s+care\s+cent(?:er|re)/gi, '').replace(/\bccc\b/gi, '').trim()
      : '-';

    html += `
      <tr class="border-b border-slate-100 dark:border-slate-800/60 hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition text-xs">
        <td class="py-2.5 px-3 text-center text-slate-400 font-mono text-[11px]">${idx + 1}</td>
        <td class="py-2.5 px-3 font-mono font-bold text-cyan-600 dark:text-cyan-400 hover:underline cursor-pointer" onclick="jumpToViewerFromOsd('${r.consumerId}')" title="Click to inspect spot images">
          ${r.consumerId}
        </td>
        <td class="py-2.5 px-3 font-medium text-slate-900 dark:text-slate-100 max-w-[160px] truncate" title="${escapeHtml(r.name || '')}">
          ${escapeHtml(r.name || 'N/A')}
        </td>
        <td class="py-2.5 px-3 text-slate-600 dark:text-slate-300 max-w-[220px] truncate" title="${escapeHtml(r.address || '')}">
          ${escapeHtml(r.address || '-')}
        </td>
        <td class="py-2.5 px-3 text-slate-500 dark:text-slate-400 max-w-[150px] truncate" title="${escapeHtml(r.office || '')}">
          ${escapeHtml(officeSnippet)}
        </td>
        <td class="py-2.5 px-3 text-center">${statusPill}</td>
        <td class="py-2.5 px-3 text-right font-mono text-slate-700 dark:text-slate-300">
          ${osdVal > 0 ? `\u20B9 ${osdVal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '-'}
        </td>
        <td class="py-2.5 px-3 text-right font-mono text-slate-500">
          ${lpscVal > 0 ? `\u20B9 ${lpscVal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '-'}
        </td>
        <td class="py-2.5 px-3 text-right font-mono font-bold ${totVal > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}">
          ${totVal > 0 ? `\u20B9 ${totVal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '\u20B9 0.00'}
        </td>
        <td class="py-2.5 px-3 text-center">
          <button onclick="jumpToViewerFromOsd('${r.consumerId}')" class="p-1.5 rounded-lg text-slate-400 hover:text-sky-600 dark:hover:text-sky-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition cursor-pointer" title="Inspect Spot Photos">
            <i data-lucide="image" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `;
  });

  if (filtered.length > 150) {
    html += `
      <tr>
        <td colspan="10" class="py-2.5 px-4 text-center text-xs text-slate-400 italic bg-slate-50/50 dark:bg-slate-900/30">
          Showing first 150 of ${filtered.length} records in preview. Export full dataset to Excel.
        </td>
      </tr>
    `;
  }

  tbody.innerHTML = html;
  safeCreateIcons(tbody);
}

function filterBulkOsdTable(filter) {
  bulkOsdState.selectedFilter = filter;
  const buttons = ['all', 'dues', 'nodues', 'disconnected'];
  buttons.forEach(f => {
    const btn = document.getElementById(`bulkFilterBtn_${f}`);
    if (btn) {
      if (f === filter) {
        btn.className = "px-2.5 py-1 rounded-md text-[11px] font-bold bg-white dark:bg-slate-900 text-cyan-600 dark:text-cyan-400 shadow-xs border border-slate-200 dark:border-slate-700/80 cursor-pointer";
      } else {
        btn.className = "px-2.5 py-1 rounded-md text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 border border-transparent cursor-pointer";
      }
    }
  });
  renderBulkTable(bulkOsdState.results);
}

async function exportBulkOsdReport(format) {
  if (!bulkOsdState.results || bulkOsdState.results.length === 0) {
    alert("No records to export.");
    return;
  }

  const apiMethod = format === 'csv' ? 'export_bulk_osd_csv' : 'export_bulk_osd_excel';
  try {
    const res = await callAPI(apiMethod, bulkOsdState.results);
    if (res && res.success) {
      alert(`Report exported successfully to:\n${res.path}`);
    } else if (res && !res.cancelled) {
      alert("Failed to export report: " + (res.error || "Unknown error"));
    }
  } catch (err) {
    alert("Export failed: " + err);
  }
}

async function downloadOsdBulkTemplate() {
  try {
    const res = await callAPI('generate_bulk_osd_template');
    if (res && res.success) {
      alert(`Template saved successfully to:\n${res.path}`);
    } else if (res && !res.cancelled) {
      alert("Failed to generate template: " + (res.error || "Unknown error"));
    }
  } catch (err) {
    alert("Template download failed: " + err);
  }
}

// --- Window Bindings ---
window.switchOsdMode = switchOsdMode;
window.executeSingleOsdCheck = executeSingleOsdCheck;
window.jumpToViewerFromOsd = jumpToViewerFromOsd;
window.showOsdNotification = showOsdNotification;
window.hideOsdNotification = hideOsdNotification;
window.handleBulkInputMethodChange = handleBulkInputMethodChange;
window.updateBulkTextCount = updateBulkTextCount;
window.pickBulkOsdFile = pickBulkOsdFile;
window.clearBulkSelectedFile = clearBulkSelectedFile;
window.startBulkOsdVerification = startBulkOsdVerification;
window.cancelBulkOsd = cancelBulkOsd;
window.filterBulkOsdTable = filterBulkOsdTable;
window.exportBulkOsdReport = exportBulkOsdReport;
window.downloadOsdBulkTemplate = downloadOsdBulkTemplate;
