// Dual-Mode Fuzzy Consumer Lookup (Manual Table & Batch Excel)
// --- Fuzzy Lookup Tool Engine (Dual Mode: Instant Manual & Batch File) ---
let currentFuzzyMode = 'manual'; // 'manual' | 'batch'
let manualFuzzyRows = [
  { name: "", co: "", address: "", mobile: "" },
  { name: "", co: "", address: "", mobile: "" }
];

function switchFuzzyMode(mode) {
  currentFuzzyMode = mode;
  const btnManual = document.getElementById('fuzzyModeBtnManual');
  const btnBatch = document.getElementById('fuzzyModeBtnBatch');
  const contManual = document.getElementById('fuzzyContainerManual');
  const contBatch = document.getElementById('fuzzyContainerBatch');

  if (mode === 'manual') {
    if (btnManual) {
      btnManual.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-xs";
    }
    if (btnBatch) {
      btnBatch.className = "px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200";
    }
    if (contManual) contManual.classList.remove('hidden');
    if (contBatch) contBatch.classList.add('hidden');
  } else {
    if (btnManual) {
      btnManual.className = "px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200";
    }
    if (btnBatch) {
      btnBatch.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-xs";
    }
    if (contManual) contManual.classList.add('hidden');
    if (contBatch) contBatch.classList.remove('hidden');
  }
  safeCreateIcons();
}

function initManualFuzzyLookup() {
  const cachedEl = document.getElementById('fuzzyCachedRecordsCount');
  const indexedCountEl = document.getElementById('indexedCount');
  if (cachedEl && indexedCountEl) {
    cachedEl.innerText = indexedCountEl.innerText || "0";
  }
  renderManualFuzzyTable();
}

function escapeHtml(val) {
  if (val === null || val === undefined) return '';
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function syncCurrentInputValues() {
  const tbody = document.getElementById('manualFuzzyTableBody');
  if (!tbody) return;
  tbody.querySelectorAll('input').forEach(inp => {
    const field = inp.getAttribute('data-field');
    const idx = parseInt(inp.getAttribute('data-index'), 10);
    if (manualFuzzyRows[idx] && field) {
      manualFuzzyRows[idx][field] = inp.value;
    }
  });
}

function renderManualFuzzyTable() {
  const tbody = document.getElementById('manualFuzzyTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  manualFuzzyRows.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.className = "hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition group";
    tr.innerHTML = `
      <td class="py-1 px-1.5 text-center text-slate-400 font-mono text-[11px] font-medium">${idx + 1}</td>
      <td class="py-1 px-1.5">
        <input type="text" data-field="name" data-index="${idx}" value="${escapeHtml(row.name)}" placeholder="e.g. PAVAN SINGH" class="w-full px-2 py-1 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/60 text-slate-800 dark:text-slate-200 focus:border-amber-500 focus:bg-white dark:focus:bg-slate-900 outline-none text-[11px] transition">
      </td>
      <td class="py-1 px-1.5">
        <input type="text" data-field="co" data-index="${idx}" value="${escapeHtml(row.co)}" placeholder="e.g. ROTON SINGHA" class="w-full px-2 py-1 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/60 text-slate-800 dark:text-slate-200 focus:border-amber-500 focus:bg-white dark:focus:bg-slate-900 outline-none text-[11px] transition">
      </td>
      <td class="py-1 px-1.5">
        <input type="text" data-field="address" data-index="${idx}" value="${escapeHtml(row.address)}" placeholder="e.g. UTTAR RAMPUR, BOROI" class="w-full px-2 py-1 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/60 text-slate-800 dark:text-slate-200 focus:border-amber-500 focus:bg-white dark:focus:bg-slate-900 outline-none text-[11px] transition">
      </td>
      <td class="py-1 px-1.5">
        <input type="text" data-field="mobile" data-index="${idx}" value="${escapeHtml(row.mobile)}" placeholder="10 digits" maxlength="12" class="w-full px-2 py-1 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/60 text-slate-800 dark:text-slate-200 focus:border-amber-500 focus:bg-white dark:focus:bg-slate-900 outline-none text-[11px] font-mono transition">
      </td>
      <td class="py-1 px-1.5 text-center">
        <button type="button" onclick="deleteManualFuzzyRow(${idx})" class="w-6 h-6 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 flex items-center justify-center transition mx-auto" title="Delete row">
          <i data-lucide="trash-2" class="w-3 h-3"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach input sync listeners & Enter / Ctrl+Enter support
  tbody.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', (e) => {
      const field = e.target.getAttribute('data-field');
      const idx = parseInt(e.target.getAttribute('data-index'), 10);
      if (manualFuzzyRows[idx]) {
        manualFuzzyRows[idx][field] = e.target.value;
      }
    });

    inp.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        runManualFuzzyLookup();
      }
    });
  });

  safeCreateIcons();
}

function addManualFuzzyRow() {
  syncCurrentInputValues();
  manualFuzzyRows.push({ name: "", co: "", address: "", mobile: "" });
  renderManualFuzzyTable();
  const tbody = document.getElementById('manualFuzzyTableBody');
  const inputs = tbody?.querySelectorAll(`input[data-index="${manualFuzzyRows.length - 1}"][data-field="name"]`);
  if (inputs && inputs[0]) inputs[0].focus();
}

function deleteManualFuzzyRow(idx) {
  syncCurrentInputValues();
  if (manualFuzzyRows.length <= 1) {
    manualFuzzyRows = [{ name: "", co: "", address: "", mobile: "" }];
  } else {
    manualFuzzyRows.splice(idx, 1);
  }
  renderManualFuzzyTable();
}

function clearManualFuzzyRows() {
  manualFuzzyRows = [
    { name: "", co: "", address: "", mobile: "" },
    { name: "", co: "", address: "", mobile: "" }
  ];
  renderManualFuzzyTable();
  const resBox = document.getElementById('fuzzyManualResultsBox');
  if (resBox) resBox.classList.add('hidden');
}

function parseAndApplyFuzzyText(text) {
  if (!text || !text.trim()) return false;
  const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
  if (!lines.length) return false;

  const parsedRows = [];
  lines.forEach((line) => {
    let cells = line.split('\t').map(c => c.trim());
    if (cells.length === 1 && line.includes(',')) {
      cells = line.split(',').map(c => c.trim());
    }
    const first = (cells[0] || "").toLowerCase();
    if (first === 'name' || first === 'consumer name' || first === '#' || first === 'consumer id') {
      return;
    }
    parsedRows.push({
      name: cells[0] || "",
      co: cells[1] || "",
      address: cells[2] || "",
      mobile: cells[3] || ""
    });
  });

  if (parsedRows.length > 0) {
    manualFuzzyRows = parsedRows;
    renderManualFuzzyTable();
    updateStatusBar(`Pasted ${parsedRows.length} row(s) from clipboard`, "normal");
    return true;
  }
  return false;
}

async function pasteFuzzyClipboard() {
  let clipboardText = "";

  // 1. Try Python RPC bridge first (works 100% reliably in PyWebView Windows without permission prompts)
  try {
    const bridgeRes = await callAPI('get_system_clipboard');
    if (bridgeRes && bridgeRes.success && bridgeRes.text) {
      clipboardText = bridgeRes.text;
    }
  } catch (e) {
    console.warn("Backend clipboard call failed:", e);
  }

  // 2. Try Web Navigator Clipboard API as secondary
  if (!clipboardText && navigator.clipboard && navigator.clipboard.readText) {
    try {
      clipboardText = await navigator.clipboard.readText();
    } catch (e) {
      console.warn("Navigator clipboard read failed:", e);
    }
  }

  // If text successfully retrieved, parse directly
  if (clipboardText && clipboardText.trim()) {
    const ok = parseAndApplyFuzzyText(clipboardText);
    if (ok) return;
  }

  // 3. Prompt modal fallback (foolproof fallback if OS clipboard is empty or blocked)
  showFuzzyPasteModal();
}

function showFuzzyPasteModal() {
  const modal = document.getElementById('fuzzyPasteModal');
  const area = document.getElementById('fuzzyPasteArea');
  if (modal && area) {
    area.value = '';
    modal.classList.remove('hidden');
    setTimeout(() => area.focus(), 50);
  }
}

function closeFuzzyPasteModal() {
  const modal = document.getElementById('fuzzyPasteModal');
  if (modal) modal.classList.add('hidden');
}

function handleFuzzyModalPasteSubmit() {
  const area = document.getElementById('fuzzyPasteArea');
  if (area && area.value.trim()) {
    parseAndApplyFuzzyText(area.value);
    closeFuzzyPasteModal();
  } else {
    alert("Please paste data into the box first.");
  }
}

async function runManualFuzzyLookup() {
  syncCurrentInputValues();

  // Validate that there is at least one row with a name or address
  const validRows = manualFuzzyRows.filter(r => (r.name && r.name.trim()) || (r.address && r.address.trim()));
  if (validRows.length === 0) {
    alert("Please enter at least one Consumer Name or Address to perform a lookup.");
    return;
  }

  const threshold = parseFloat(document.getElementById('fuzzyThreshold')?.value || '0.85');
  const topN = parseInt(document.getElementById('fuzzyTopN')?.value || '5', 10);

  const btn = document.getElementById('btnRunManualFuzzy');
  const speedEl = document.getElementById('fuzzyResultsSpeed');
  const resultsBox = document.getElementById('fuzzyManualResultsBox');
  const badgeCount = document.getElementById('fuzzyResultsBadgeCount');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Searching...</span>`;
    safeCreateIcons();
  }

  const t0 = performance.now();
  const res = await callAPI('lookup_fuzzy_rows', validRows, threshold, topN);
  const elapsedMs = Math.round(performance.now() - t0);

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="search" class="w-3.5 h-3.5"></i><span>Find Matches</span>`;
    safeCreateIcons();
  }

  if (!res || !res.success) {
    alert("Fuzzy Lookup failed: " + (res ? res.error : "Unknown error"));
    return;
  }

  if (speedEl) speedEl.innerText = `${elapsedMs} ms`;
  if (resultsBox) resultsBox.classList.remove('hidden');

  let totalFound = 0;
  res.results.forEach(r => {
    totalFound += (r.candidates ? r.candidates.length : 0);
  });

  if (badgeCount) {
    badgeCount.innerText = `${totalFound} candidate(s) found across ${res.results.length} query row(s)`;
  }

  renderManualFuzzyResults(res.results);
}

function renderManualFuzzyResults(queryResults) {
  const container = document.getElementById('fuzzyResultsList');
  if (!container) return;
  container.innerHTML = '';

  if (!queryResults || queryResults.length === 0) {
    container.innerHTML = `
      <div class="p-5 text-center text-slate-500 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
        <i data-lucide="search-x" class="w-6 h-6 mx-auto mb-1.5 text-slate-400"></i>
        <p class="text-xs font-semibold">No matches found for the entered query.</p>
        <p class="text-[10px] text-slate-400">Try reducing the similarity threshold or checking name/C/O spelling.</p>
      </div>
    `;
    safeCreateIcons();
    return;
  }

  queryResults.forEach((qItem, qIdx) => {
    const inp = qItem.input;
    const candidates = qItem.candidates || [];

    const card = document.createElement('div');
    card.className = "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3.5 shadow-xs space-y-2.5";

    // Query Header
    const inpSummary = [
      inp.name ? `<strong class="text-slate-800 dark:text-slate-200 font-bold">${escapeHtml(inp.name)}</strong>` : null,
      inp.co ? `<span class="text-slate-500 font-medium">C/O ${escapeHtml(inp.co)}</span>` : null,
      inp.address ? `<span class="text-slate-600 dark:text-slate-400">${escapeHtml(inp.address)}</span>` : null,
      inp.mobile ? `<span class="font-mono text-sky-600 dark:text-sky-400">📱 ${escapeHtml(inp.mobile)}</span>` : null,
    ].filter(Boolean).join(' • ');

    card.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 pb-2 border-b border-slate-100 dark:border-slate-800">
        <div class="flex items-center gap-2">
          <span class="w-4 h-4 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold text-[10px]">
            ${qIdx + 1}
          </span>
          <div class="text-[11px]">
            <span class="text-slate-400 font-medium mr-1">Query:</span>
            ${inpSummary || '<span class="text-slate-400 italic">Empty Query</span>'}
          </div>
        </div>
        <div class="text-[11px]">
          ${candidates.length > 0
            ? `<span class="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 font-bold text-[10px]">${candidates.length} Ranked Match${candidates.length > 1 ? 'es' : ''}</span>`
            : `<span class="px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-500/20 text-rose-700 dark:text-rose-400 font-semibold text-[10px]">No Matches Above Threshold</span>`
          }
        </div>
      </div>
    `;

    if (candidates.length === 0) {
      const emptyDiv = document.createElement('div');
      emptyDiv.className = "py-3 text-center text-[11px] text-slate-400 italic";
      emptyDiv.innerText = "No candidates matched identity and address criteria. Try lowering the threshold.";
      card.appendChild(emptyDiv);
    } else {
      const tableWrapper = document.createElement('div');
      tableWrapper.className = "overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-800/80";

      let rowsHtml = '';
      candidates.forEach((cand, cIdx) => {
        // Badge color based on final score
        let badgeColor = "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
        if (cand.final_score >= 90) {
          badgeColor = "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800/60";
        } else if (cand.final_score >= 75) {
          badgeColor = "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-300 dark:border-amber-800/60";
        }

        // Relation badge: SELF vs RELATIVE
        const isRelative = cand.relation === 'RELATIVE';
        const relationBadge = isRelative
          ? `<span class="px-1.5 py-0.5 rounded text-[9.5px] font-bold bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60">RELATIVE</span>`
          : `<span class="px-1.5 py-0.5 rounded text-[9.5px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300 border border-sky-200 dark:border-sky-800/60">SELF</span>`;

        rowsHtml += `
          <tr class="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
            <td class="py-1.5 px-2 text-center font-mono font-bold text-slate-400 text-[10px]">#${cIdx + 1}</td>
            <td class="py-1.5 px-2 whitespace-nowrap">
              <span class="px-2 py-0.5 rounded-md font-mono font-bold text-[10.5px] ${badgeColor}">
                ${cand.final_score.toFixed(1)}%
              </span>
              <span class="block text-[9.5px] text-slate-400 font-medium mt-0.5">${cand.match_type}</span>
            </td>
            <td class="py-1.5 px-2 text-center whitespace-nowrap">
              ${relationBadge}
            </td>
            <td class="py-1.5 px-2">
              <span class="font-mono font-semibold text-sky-600 dark:text-sky-400 text-[11px]">${cand.consumer_id}</span>
            </td>
            <td class="py-1.5 px-2 min-w-[130px]">
              <div class="font-bold text-slate-900 dark:text-slate-100 text-[11px]">${escapeHtml(cand.name)}</div>
              <div class="text-[9.5px] text-slate-400">Identity: ${cand.identity_score.toFixed(0)}% (Name: ${cand.name_score.toFixed(0)}%, C/O: ${cand.co_score.toFixed(0)}%)</div>
            </td>
            <td class="py-1.5 px-2 min-w-[150px]">
              <div class="text-slate-700 dark:text-slate-300 text-[11px] leading-snug">${escapeHtml(cand.address)}</div>
              <div class="text-[9.5px] text-slate-400">Address Match: ${cand.address_score.toFixed(0)}%</div>
            </td>
            <td class="py-1.5 px-2 whitespace-nowrap font-mono text-[10.5px] text-slate-600 dark:text-slate-400">
              ${cand.mobile_number ? (cand.mobile_score === 100 ? `<span class="text-emerald-600 dark:text-emerald-400 font-bold">✓ ${cand.mobile_number}</span>` : cand.mobile_number) : '-'}
            </td>
            <!-- Live OSD Column -->
            <td class="py-1.5 px-2 text-center whitespace-nowrap" id="candOsdCell_${qIdx}_${cIdx}">
              <button onclick="fetchCandidateLiveOsd('${cand.consumer_id}', ${qIdx}, ${cIdx})" class="px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-900/50 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400 text-[10px] font-bold transition flex items-center gap-1 shadow-xs mx-auto">
                <i data-lucide="zap" class="w-3 h-3 text-amber-500"></i>
                <span>Check OSD</span>
              </button>
            </td>
            <td class="py-1.5 px-2 text-center whitespace-nowrap">
              <button onclick="searchConsumerAndOpenViewer('${cand.consumer_id}')" class="px-2 py-0.5 rounded-md bg-sky-50 dark:bg-sky-950/50 hover:bg-sky-100 dark:hover:bg-sky-900/60 border border-sky-200 dark:border-sky-800 text-sky-600 dark:text-sky-400 text-[10.5px] font-semibold transition flex items-center gap-1 shadow-xs mx-auto">
                <i data-lucide="image" class="w-3 h-3"></i>
                <span>View Photos</span>
              </button>
            </td>
          </tr>
        `;
      });

      tableWrapper.innerHTML = `
        <table class="w-full text-left text-[11px] border-collapse">
          <thead class="bg-slate-50/80 dark:bg-slate-950/50 text-slate-500 uppercase font-semibold text-[9px] tracking-wider border-b border-slate-100 dark:border-slate-800">
            <tr>
              <th class="py-1.5 px-2 w-8 text-center">Rank</th>
              <th class="py-1.5 px-2 w-20">Match Score</th>
              <th class="py-1.5 px-2 w-16 text-center">Relation</th>
              <th class="py-1.5 px-2 w-24">Consumer ID</th>
              <th class="py-1.5 px-2">Database Name</th>
              <th class="py-1.5 px-2">Database Address</th>
              <th class="py-1.5 px-2 w-24">Mobile</th>
              <th class="py-1.5 px-2 w-28 text-center">Live OSD</th>
              <th class="py-1.5 px-2 w-20 text-center">Viewer</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800/50">
            ${rowsHtml}
          </tbody>
        </table>
      `;
      card.appendChild(tableWrapper);
    }

    container.appendChild(card);
  });

  safeCreateIcons();
}

async function fetchCandidateLiveOsd(consumerId, qIdx, cIdx) {
  const cell = document.getElementById(`candOsdCell_${qIdx}_${cIdx}`);
  if (!cell) return;

  const cid = String(consumerId || '').trim();
  if (!/^\d{9}$/.test(cid)) {
    cell.innerHTML = `<span class="text-[10px] text-slate-400 italic">Invalid CID</span>`;
    return;
  }

  cell.innerHTML = `
    <div class="inline-flex items-center gap-1 text-[10px] text-amber-600 dark:text-amber-400 font-medium">
      <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i>
      <span>Checking...</span>
    </div>
  `;
  safeCreateIcons();

  try {
    const res = await callAPI('get_live_osd', cid);
    if (!res || !res.success || !res.data) {
      const isOffline = res && (res.error_code === 'OFFLINE' || String(res.error).toLowerCase().includes('internet'));
      const btnLabel = isOffline ? "Offline ↻" : "Failed ↻";
      const tooltip = res ? (res.error || "Connection failed - Click to retry") : "Network error - Click to retry";
      cell.innerHTML = `
        <button onclick="fetchCandidateLiveOsd('${cid}', ${qIdx}, ${cIdx})" class="px-1.5 py-0.5 rounded text-[9.5px] font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition" title="${escapeHtml(tooltip)}">
          ${btnLabel}
        </button>
      `;
      return;
    }

    const d = res.data;
    const rawStatus = (d.connectionStatus && d.connectionStatus !== 'N/A') ? String(d.connectionStatus).trim() : '';
    const normStatus = rawStatus.toUpperCase();
    let statusClass = "text-slate-500";
    let dotClass = "bg-slate-400";
    if (d.isDeemed || normStatus.includes('DEEMED')) {
      statusClass = "text-amber-600 dark:text-amber-400 font-bold";
      dotClass = "bg-amber-500";
    } else if (d.isTempDisconnected || normStatus.includes('TEMP')) {
      statusClass = "text-amber-600 dark:text-amber-400 font-bold";
      dotClass = "bg-amber-500";
    } else if (d.isDisconnected || normStatus.includes('DISCONNECT') || normStatus.includes('DISCONN')) {
      statusClass = "text-rose-600 dark:text-rose-400 font-bold";
      dotClass = "bg-rose-500";
    } else if (d.isLive || normStatus === 'LIVE' || (!normStatus.includes('DISCONNECT') && normStatus.includes('CONNECT'))) {
      statusClass = "text-emerald-600 dark:text-emerald-400 font-bold";
      dotClass = "bg-emerald-500";
    }

    const totalFmt = Number(d.totalDues || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const duesClass = (d.totalDues > 0) ? "text-amber-600 dark:text-amber-400 font-bold" : "text-emerald-600 dark:text-emerald-400 font-medium";

    cell.innerHTML = `
      <div class="text-left py-0.5 leading-tight">
        <div class="font-mono text-[10.5px] ${duesClass}">\u20B9 ${totalFmt}</div>
        <div class="text-[9px] ${statusClass} flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full ${dotClass}"></span>
          <span>${escapeHtml(rawStatus || 'LIVE')}</span>
        </div>
      </div>
    `;
  } catch (e) {
    cell.innerHTML = `
      <button onclick="fetchCandidateLiveOsd('${cid}', ${qIdx}, ${cIdx})" class="px-1.5 py-0.5 rounded text-[9.5px] font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition">
        Retry ↻
      </button>
    `;
  }
}

async function searchConsumerAndOpenViewer(consumerId) {
  if (!consumerId) return;
  // Switch to Viewer tab
  switchTab('viewer');
  // Set search bar input
  const searchInput = document.getElementById('searchBar');
  if (searchInput) {
    searchInput.value = consumerId;
  }
  // Trigger search
  await handleSearch();
}

window.switchFuzzyMode = switchFuzzyMode;
window.addManualFuzzyRow = addManualFuzzyRow;
window.deleteManualFuzzyRow = deleteManualFuzzyRow;
window.clearManualFuzzyRows = clearManualFuzzyRows;
window.pasteFuzzyClipboard = pasteFuzzyClipboard;
window.runManualFuzzyLookup = runManualFuzzyLookup;
window.searchConsumerAndOpenViewer = searchConsumerAndOpenViewer;
window.fetchCandidateLiveOsd = fetchCandidateLiveOsd;

async function generateFuzzyTemplate() {
  const res = await callAPI('generate_fuzzy_template');
  if (res && res.success) {
    alert("Fuzzy lookup template created at:\n" + res.path);
  } else if (res && res.error) {
    alert("Failed to generate fuzzy template: " + res.error);
  }
}

let fuzzyPollTimer = null;

async function runFuzzyLookup() {
  const threshold = parseFloat(document.getElementById('fuzzyThreshold')?.value || 0.85);
  const topN = parseInt(document.getElementById('fuzzyTopN')?.value || 5);
  const includeOsd = Boolean(document.getElementById('fuzzyIncludeOsd')?.checked);

  const statusBox = document.getElementById('fuzzyStatusBox');
  const statusText = document.getElementById('fuzzyStatusText');
  const countText = document.getElementById('fuzzyProgressCount');
  const progBar = document.getElementById('fuzzyProgressBar');
  const linkBox = document.getElementById('fuzzyOutputLink');
  const runBtn = document.getElementById('btnRunFuzzy');

  if (statusBox) statusBox.classList.remove('hidden');
  if (linkBox) linkBox.classList.add('hidden');
  if (runBtn) runBtn.disabled = true;
  if (statusText) statusText.innerText = "Selecting input file...";

  const res = await callAPI('run_fuzzy_lookup', '', '', threshold, topN, includeOsd);
  if (!res || !res.success) {
    if (runBtn) runBtn.disabled = false;
    if (res && res.cancelled) {
      if (statusBox) statusBox.classList.add('hidden');
      return;
    }
    alert("Failed to start fuzzy lookup: " + (res ? res.error : "Unknown error"));
    if (statusBox) statusBox.classList.add('hidden');
    return;
  }

  // Start polling fuzzy progress
  if (fuzzyPollTimer) clearInterval(fuzzyPollTimer);
  fuzzyPollTimer = setInterval(async () => {
    const stat = await callAPI('get_fuzzy_status');
    if (!stat) return;

    const pct = stat.total > 0 ? Math.round((stat.processed / stat.total) * 100) : 0;
    if (statusText) statusText.innerText = stat.status || "Matching...";
    if (countText) countText.innerText = `${pct}% (${stat.processed}/${stat.total}) | ${stat.elapsed}s`;
    if (progBar) progBar.style.width = `${pct}%`;
    updateStatusBar(`Fuzzy Lookup: ${stat.status || "Processing"} (${stat.processed}/${stat.total})`, "loading", pct);

    if (!stat.running) {
      clearInterval(fuzzyPollTimer);
      fuzzyPollTimer = null;
      if (runBtn) runBtn.disabled = false;

      if (stat.error) {
        updateStatusBar("Fuzzy Lookup error: " + stat.error, "error");
        alert("Fuzzy Lookup encountered an error: " + stat.error);
        if (statusText) statusText.innerText = "Error: " + stat.error;
      } else {
        if (progBar) progBar.style.width = '100%';
        if (countText) countText.innerText = `100% | ${stat.elapsed}s`;
        updateStatusBar(`Fuzzy Lookup Complete! Results saved to excel.`, "normal", 100);
        setTimeout(() => updateStatusBar("Ready", "normal"), 3000);
        if (linkBox) {
          linkBox.classList.remove('hidden');
          linkBox.innerHTML = `<strong>Results Saved:</strong> ${stat.output_path}`;
        }
        alert("Fuzzy Lookup Complete!\nResults exported to:\n" + stat.output_path);
      }
    }
  }, 400);
}

