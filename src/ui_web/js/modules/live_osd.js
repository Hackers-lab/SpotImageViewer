// Live WBSEDCL OSD & Telemetry Controller
// --- Live WBSEDCL OSD & Connection Status Controller ---
let currentLiveOsdData = null;

function formatHudOffice(rawOffice) {
  if (!rawOffice || rawOffice === '-' || rawOffice === 'N/A') return '-';
  // Strip "customer care center", "customer care centre", "ccc", etc.
  let cleaned = String(rawOffice)
    .replace(/customer\s+care\s+cent(?:er|re)/gi, '')
    .replace(/\b(?:c\.?c\.?c\.?)\b/gi, '')
    .replace(/[(),]/g, ' ')
    .trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  return words.length > 0 ? words[0] : (String(rawOffice).split(/\s+/)[0] || '-');
}

async function loadLiveOSD(consumerId, forceRefresh = false) {
  const cid = String(consumerId || '').trim();
  const hud = document.getElementById('liveOsdHud');
  const statusBadge = document.getElementById('liveOsdStatusBadge');
  const statusText = document.getElementById('liveOsdStatusText');
  const totalDuesEl = document.getElementById('liveOsdTotalDues');
  const unpaidEl = document.getElementById('liveOsdUnpaid');
  const lpscEl = document.getElementById('liveOsdLpsc');
  const officeEl = document.getElementById('liveOsdOffice');
  const connDateEl = document.getElementById('liveOsdConnDate');
  const docTypeEl = document.getElementById('liveOsdDocType');
  const cachedIndicator = document.getElementById('liveOsdCachedIndicator');
  const btnPdf = document.getElementById('btnViewOsdPdf');
  const refreshIcon = document.getElementById('btnRefreshOsdIcon');

  if (!cid || !/^\d{9}$/.test(cid)) {
    if (hud) hud.classList.add('hidden');
    if (statusBadge) statusBadge.className = "";
    if (statusText) {
      statusText.className = "text-[10px] font-semibold text-slate-400";
      statusText.innerText = "Invalid CID";
    }
    if (totalDuesEl) totalDuesEl.innerText = "0.00";
    if (unpaidEl) unpaidEl.innerText = "\u20B9 0.00";
    if (lpscEl) lpscEl.innerText = "\u20B9 0.00";
    if (officeEl) { officeEl.innerText = "-"; officeEl.title = ""; }
    if (connDateEl) connDateEl.innerText = "-";
    if (docTypeEl) docTypeEl.innerText = "-";
    if (cachedIndicator) cachedIndicator.innerText = "";
    if (btnPdf) btnPdf.classList.add('hidden');
    currentLiveOsdData = null;
    return;
  }

  // Show floating HUD card in viewport
  if (hud) hud.classList.remove('hidden');

  // Set loading state
  if (statusBadge) statusBadge.className = "";
  if (statusText) {
    statusText.className = "text-[10px] font-semibold text-amber-500 dark:text-amber-400 animate-pulse";
    statusText.innerText = "Checking Portal...";
  }
  if (refreshIcon) refreshIcon.classList.add('animate-spin');

  try {
    const res = await callAPI('get_live_osd', cid, forceRefresh);

    // Non-blocking: Python returns {pending: true} and pushes result via onLiveOsdResult
    if (res && res.pending) {
      // Keep loading spinner — onLiveOsdResult will render the final data
      return;
    }

    // Cached data returned immediately (no pending)
    if (refreshIcon) refreshIcon.classList.remove('animate-spin');
    _renderLiveOsdData(res);
  } catch (err) {
    console.error("Failed to load live OSD:", err);
    if (refreshIcon) refreshIcon.classList.remove('animate-spin');
    if (statusBadge) statusBadge.className = "";
    if (statusText) {
      statusText.className = "text-[10px] font-semibold text-rose-500 dark:text-rose-400";
      statusText.innerText = "No Internet";
      statusText.title = "Network request failed. Please check your internet connection.";
    }
    if (totalDuesEl) totalDuesEl.innerText = "-";
    if (unpaidEl) unpaidEl.innerText = "-";
    if (lpscEl) lpscEl.innerText = "-";
  }
}

// Called by Python via evaluate_js when the background OSD fetch completes
function onLiveOsdResult(res) {
  const refreshIcon = document.getElementById('btnRefreshOsdIcon');
  if (refreshIcon) refreshIcon.classList.remove('animate-spin');
  _renderLiveOsdData(res);
}
window.onLiveOsdResult = onLiveOsdResult;

function _renderLiveOsdData(res) {
  // Discard out-of-order responses if the user has already switched consumers
  const respCid = res && (res.data ? res.data.consumerId : (res.consumer_id || res.cid));
  if (respCid && currentConsumerId && String(respCid).trim() !== String(currentConsumerId).trim()) {
    return;
  }

  const statusBadge = document.getElementById('liveOsdStatusBadge');
  const statusText = document.getElementById('liveOsdStatusText');
  const totalDuesEl = document.getElementById('liveOsdTotalDues');
  const unpaidEl = document.getElementById('liveOsdUnpaid');
  const lpscEl = document.getElementById('liveOsdLpsc');
  const officeEl = document.getElementById('liveOsdOffice');
  const connDateEl = document.getElementById('liveOsdConnDate');
  const docTypeEl = document.getElementById('liveOsdDocType');
  const cachedIndicator = document.getElementById('liveOsdCachedIndicator');
  const btnPdf = document.getElementById('btnViewOsdPdf');

  if (!res || !res.success || !res.data) {
    if (statusBadge) statusBadge.className = "";
    if (statusText) {
      statusText.className = "text-[10px] font-semibold text-rose-500 dark:text-rose-400";
      let displayError = "Unavailable";
      if (res && res.error) {
        displayError = res.error;
        if (displayError.length > 24) {
          displayError = (res.error_code === 'OFFLINE' || displayError.toLowerCase().includes('internet')) ? "No Internet" : "Service Error";
        }
      }
      statusText.innerText = displayError;
      statusText.title = res ? (res.error || res.raw_error || "Could not connect to service") : "Service Error";
    }
    if (totalDuesEl) totalDuesEl.innerText = "-";
    if (unpaidEl) unpaidEl.innerText = "-";
    if (lpscEl) lpscEl.innerText = "-";
    return;
  }

  const d = res.data;
  currentLiveOsdData = d;

  // Status styling - Simple clean text without pill
  if (statusBadge) statusBadge.className = "";
  if (statusText) {
    const rawStatus = (d.connectionStatus && d.connectionStatus !== 'N/A') ? String(d.connectionStatus).trim() : '';
    const connStatus = rawStatus.toUpperCase();
    if (d.isDeemed || connStatus.includes('DEEMED')) {
      statusText.className = "text-[10px] font-bold text-amber-600 dark:text-amber-400";
      statusText.innerText = rawStatus || "Deemed";
    } else if (d.isTempDisconnected || connStatus.includes('TEMP')) {
      statusText.className = "text-[10px] font-bold text-amber-600 dark:text-amber-400";
      statusText.innerText = rawStatus || "Temp Disconnected";
    } else if (d.isDisconnected || connStatus.includes('DISCONNECT') || connStatus.includes('DISCONN')) {
      statusText.className = "text-[10px] font-bold text-rose-600 dark:text-rose-400";
      statusText.innerText = rawStatus || "Disconnected";
    } else if (d.isLive || connStatus === 'LIVE' || (!connStatus.includes('DISCONNECT') && connStatus.includes('CONNECT'))) {
      statusText.className = "text-[10.5px] font-bold text-emerald-600 dark:text-emerald-400";
      statusText.innerText = rawStatus || "Connected";
    } else {
      statusText.className = "text-[10px] font-semibold text-slate-600 dark:text-slate-400";
      statusText.innerText = rawStatus || "-";
    }
  }

  if (totalDuesEl) totalDuesEl.innerText = Number(d.totalDues || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (unpaidEl) unpaidEl.innerText = `\u20B9 ${Number(d.osd || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (lpscEl) lpscEl.innerText = `\u20B9 ${Number(d.lpsc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (officeEl) {
    officeEl.innerText = formatHudOffice(d.office);
    officeEl.title = d.office || '-';
  }
  if (connDateEl) connDateEl.innerText = d.connDate || '-';
  if (docTypeEl) docTypeEl.innerText = d.docType || 'OUTSTANDING REPORT';
  if (cachedIndicator) cachedIndicator.innerText = d.cached ? '(cached)' : '(live)';
  if (btnPdf) btnPdf.classList.add('hidden');

  safeCreateIcons();
}

function refreshLiveOSD() {
  if (!currentConsumerId) {
    alert("Please select a consumer first.");
    return;
  }
  loadLiveOSD(currentConsumerId, true);
}

async function viewLiveOsdPdf() {
  if (!currentConsumerId) return;
  const res = await callAPI('open_live_osd_pdf', currentConsumerId);
  if (!res || !res.success) {
    alert("Failed to open PDF: " + (res ? res.error : "Unknown error"));
  }
}

window.loadLiveOSD = loadLiveOSD;
window.refreshLiveOSD = refreshLiveOSD;
window.viewLiveOsdPdf = viewLiveOsdPdf;


