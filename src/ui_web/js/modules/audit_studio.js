// Low Consumption Verification Studio Controller
// --- Low Consumption Audit Studio Logic ---
let auditData = [];
let auditFilteredIndices = [];
let auditCurrentId = null;
let auditFilterStatusMode = 'ALL'; // 'ALL' | 'PENDING' | 'OK' | 'CHECK'
let auditActiveImages = [];
let auditLightboxCurrentIndex = 0;
let auditLightboxZoom = 1.0;

function setAuditFilterStatus(mode) {
  auditFilterStatusMode = mode;
  ['All', 'Pending', 'Ok', 'Check'].forEach(k => {
    const btn = document.getElementById(`auditFilter${k}`);
    if (btn) {
      const isSelected = k.toUpperCase() === mode;
      btn.className = `flex-1 py-1 rounded-lg text-center transition ${
        isSelected
          ? 'font-bold bg-slate-200 dark:bg-white/[0.12] text-slate-900 dark:text-white shadow-xs'
          : 'font-medium text-slate-500 hover:bg-slate-100 dark:hover:bg-white/[0.05]'
      }`;
    }
  });
  filterAuditQueue();
}

function setAuditRemarkTag(tag) {
  const input = document.getElementById('auditRemarksInput');
  if (!input) return;
  if (!input.value.trim()) {
    input.value = tag;
  } else if (!input.value.includes(tag)) {
    input.value = `${input.value.trim()}, ${tag}`;
  }
  input.focus();
}

function updateDecisionStyles() {
  // Pure UI update, lucide refreshing if needed
  safeCreateIcons();
}

function toggleAuditPasteModal(show = true) {
  const modal = document.getElementById('auditPasteModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    const textarea = document.getElementById('auditPasteTextarea');
    if (textarea) setTimeout(() => textarea.focus(), 100);
  } else {
    modal.classList.add('hidden');
  }
  safeCreateIcons();
}

function toggleAuditGuideModal(show = true) {
  const modal = document.getElementById('auditGuideModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
  } else {
    modal.classList.add('hidden');
  }
  safeCreateIcons();
}

async function pasteAuditFromSystemClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    const textarea = document.getElementById('auditPasteTextarea');
    if (textarea) {
      textarea.value = text;
      textarea.focus();
    }
  } catch (err) {
    alert("Clipboard read permission was blocked. Please press Ctrl+V directly into the text box.");
  }
}

async function importAuditPastedText() {
  const textarea = document.getElementById('auditPasteTextarea');
  if (!textarea) return;
  const raw = textarea.value.trim();
  if (!raw) {
    alert("Please paste consumer data before clicking Import.");
    return;
  }

  const lines = raw.split(/\r?\n/);
  const newItems = [];
  let rowId = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    let parts = [];
    if (line.includes('\t')) {
      parts = line.split('\t');
    } else if (line.includes('|')) {
      parts = line.split('|');
    } else if (line.includes(',')) {
      parts = line.split(',');
    } else {
      parts = line.split(/\s+/);
    }

    parts = parts.map(p => p.trim()).filter(p => p !== '');
    if (parts.length === 0) continue;

    const cid = parts[0];
    if (i === 0 && (cid.toLowerCase().includes('cid') || cid.toLowerCase().includes('consumer'))) {
      continue;
    }
    if (cid.toLowerCase() === 'none' || cid.toLowerCase() === 'nan') continue;

    const meter = parts.length > 1 ? parts[1] : '';
    const unit = parts.length > 2 ? parts[2] : '0';

    newItems.push({
      id: rowId++,
      cid: cid,
      meter: meter,
      unit: unit,
      status: 'PENDING',
      remarks: ''
    });
  }

  if (newItems.length === 0) {
    alert("No valid consumer rows detected. Format should be: ConsumerID  [MeterNo]  [BilledUnits]");
    return;
  }

  auditData = newItems;
  await callAPI('save_low_consumption_session', auditData);
  toggleAuditPasteModal(false);
  textarea.value = '';

  filterAuditQueue();
  updateStatusBar(`Loaded ${auditData.length} records into audit queue.`, "normal");

  if (auditData.length > 0) {
    selectAuditItem(auditData[0].id);
  }
}

async function triggerLoadAuditExcel() {
  const picked = await callAPI('pick_file', "Select Low Consumption Excel", [["Excel Files", "*.xlsx;*.xls"], ["All Files", "*.*"]]);
  if (picked && typeof picked === 'string' && picked.trim() !== '') {
    updateStatusBar("Reading Excel records...", "loading");
    const res = await callAPI('parse_low_consumption_file', picked);
    if (res && res.success) {
      auditData = res.data || [];
      filterAuditQueue();
      updateStatusBar(`Loaded ${auditData.length} records from Excel.`, "normal");
      if (auditData.length > 0) {
        selectAuditItem(auditData[0].id);
      }
      return;
    } else if (res && res.error) {
      alert("Error parsing Excel file: " + res.error);
      updateStatusBar("Excel load failed.", "error");
      return;
    }
  }

  const fileInput = document.getElementById('auditFileInput');
  if (fileInput) fileInput.click();
}

async function handleAuditFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (file.path) {
    const res = await callAPI('parse_low_consumption_file', file.path);
    if (res && res.success) {
      auditData = res.data || [];
      filterAuditQueue();
      if (auditData.length > 0) selectAuditItem(auditData[0].id);
      event.target.value = '';
      return;
    }
  }

  alert("To load Excel on this platform, please use 'Paste Clipboard' (copy cells from Excel and paste), or select the file via the system dialog.");
  event.target.value = '';
}

async function loadAuditSession() {
  const res = await callAPI('get_low_consumption_session');
  if (res && res.success && res.data && res.data.length > 0) {
    auditData = res.data;
    filterAuditQueue();
    const firstPending = auditData.find(item => item.status === 'PENDING') || auditData[0];
    if (firstPending) {
      selectAuditItem(firstPending.id);
    }
  }
}

function filterAuditQueue() {
  const query = (document.getElementById('auditSearchInput')?.value || '').toLowerCase().trim();
  const queueEl = document.getElementById('auditQueueList');
  const countBadge = document.getElementById('auditCountBadge');
  const verifiedEl = document.getElementById('auditVerifiedCount');
  const pendingEl = document.getElementById('auditPendingCount');

  if (!queueEl) return;

  const verifiedCount = auditData.filter(x => x.status === 'OK' || x.status === 'CHECK').length;
  const pendingCount = auditData.filter(x => x.status === 'PENDING').length;

  if (countBadge) countBadge.innerText = `${auditData.length} records (${verifiedCount} verified)`;
  if (verifiedEl) verifiedEl.innerHTML = `<i data-lucide="check-circle" class="w-3.5 h-3.5"></i> Verified: ${verifiedCount}`;
  if (pendingEl) pendingEl.innerHTML = `<i data-lucide="clock" class="w-3.5 h-3.5"></i> Pending: ${pendingCount}`;

  if (auditData.length === 0) {
    queueEl.innerHTML = `
      <div class="p-8 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-2">
        <i data-lucide="file-spreadsheet" class="w-8 h-8 opacity-40"></i>
        <span>No records loaded yet. Click <b>Load Excel</b> or <b>Paste Clipboard</b> to begin.</span>
      </div>
    `;
    auditFilteredIndices = [];
    safeCreateIcons();
    return;
  }

  auditFilteredIndices = [];
  queueEl.innerHTML = '';

  auditData.forEach(item => {
    // Status filter
    if (auditFilterStatusMode !== 'ALL') {
      if (auditFilterStatusMode === 'PENDING' && item.status !== 'PENDING') return;
      if (auditFilterStatusMode === 'OK' && item.status !== 'OK') return;
      if (auditFilterStatusMode === 'CHECK' && item.status !== 'CHECK') return;
    }

    // Search query filter
    const match = !query || item.cid.toLowerCase().includes(query) || (item.meter && item.meter.toLowerCase().includes(query));
    if (!match) return;

    auditFilteredIndices.push(item.id);
    const row = document.createElement('div');
    const isSelected = item.id === auditCurrentId;

    let statusBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-100 dark:bg-white/[0.06] text-slate-400 text-[10px]" title="Pending Inspection"><i data-lucide="clock" class="w-3 h-3"></i></span>`;
    if (item.status === 'OK') {
      statusBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-black text-xs" title="OK / Normal"><i data-lucide="check" class="w-3.5 h-3.5"></i></span>`;
    } else if (item.status === 'CHECK') {
      statusBadge = `<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-500/20 text-rose-600 dark:text-rose-400 font-black text-xs" title="Suspicious / CHECK"><i data-lucide="alert-triangle" class="w-3.5 h-3.5"></i></span>`;
    }

    row.className = `grid grid-cols-12 px-3 py-2.5 cursor-pointer transition-all items-center text-xs select-none ${
      isSelected
        ? 'bg-sky-500/10 dark:bg-sky-500/15 border-l-3 border-sky-500 font-bold text-sky-600 dark:text-sky-400'
        : 'hover:bg-slate-100/60 dark:hover:bg-white/[0.04] text-slate-700 dark:text-slate-300'
    }`;

    row.id = `audit-row-${item.id}`;
    row.innerHTML = `
      <div class="col-span-2 flex justify-center">${statusBadge}</div>
      <div class="col-span-4 font-mono truncate font-bold">${item.cid}</div>
      <div class="col-span-4 font-mono text-slate-400 truncate text-[11px]">${item.meter || '-'}</div>
      <div class="col-span-2 font-mono font-bold text-right text-rose-600 dark:text-rose-400">${item.unit || '0'}</div>
    `;

    row.onclick = () => selectAuditItem(item.id);
    queueEl.appendChild(row);
  });

  safeCreateIcons();
}

async function selectAuditItem(id) {
  auditCurrentId = id;
  const item = auditData.find(x => x.id === id);
  if (!item) return;

  // Highlight active row in queue
  document.querySelectorAll('#auditQueueList > div').forEach(r => {
    const isThis = r.id === `audit-row-${id}`;
    r.classList.toggle('bg-sky-500/10', isThis);
    r.classList.toggle('dark:bg-sky-500/15', isThis);
    r.classList.toggle('border-l-3', isThis);
    r.classList.toggle('border-sky-500', isThis);
    r.classList.toggle('font-bold', isThis);
    r.classList.toggle('text-sky-600', isThis);
    r.classList.toggle('dark:text-sky-400', isThis);
  });

  const activeRow = document.getElementById(`audit-row-${id}`);
  if (activeRow) {
    activeRow.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  // Update inspection banner
  const cidEl = document.getElementById('auditActiveCid');
  const meterEl = document.getElementById('auditActiveMeter');
  const nameEl = document.getElementById('auditActiveName');
  const unitsEl = document.getElementById('auditActiveUnits');
  const remarksInput = document.getElementById('auditRemarksInput');
  const photoCountEl = document.getElementById('auditActivePhotoCount');
  const galleryCountEl = document.getElementById('auditGalleryCount');

  if (cidEl) cidEl.innerText = item.cid;
  if (meterEl) meterEl.innerText = `Meter: ${item.meter || '--'}`;
  if (nameEl) nameEl.innerText = `Name: Loading...`;
  if (unitsEl) unitsEl.innerText = item.unit || '0';
  if (remarksInput) remarksInput.value = item.remarks || '';

  // Decision radio
  const currentStatus = item.status === 'CHECK' ? 'CHECK' : 'OK';
  const radio = document.querySelector(`input[name="auditDecision"][value="${currentStatus}"]`);
  if (radio) radio.checked = true;

  // Load consumer profile details & images from database
  const gallery = document.getElementById('auditGalleryGrid');
  if (!gallery) return;

  gallery.innerHTML = `
    <div class="col-span-full py-20 flex flex-col items-center justify-center text-slate-400 gap-2">
      <div class="w-7 h-7 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
      <span class="text-xs font-medium">Scanning spot meter archives for CID ${item.cid}...</span>
    </div>
  `;

  const res = await callAPI('get_consumer_images', item.cid);
  auditActiveImages = (res && res.images) ? res.images : [];

  if (nameEl) {
    nameEl.innerText = (res && res.profile && res.profile.name) ? `Name: ${res.profile.name}` : `Name: --`;
  }
  if (photoCountEl) photoCountEl.innerText = `${auditActiveImages.length} Photos`;
  if (galleryCountEl) galleryCountEl.innerText = `${auditActiveImages.length} images`;

  if (!res || !res.success || !res.images || res.images.length === 0) {
    gallery.innerHTML = `
      <div class="col-span-full py-20 flex flex-col items-center justify-center text-slate-400 gap-2">
        <div class="w-12 h-12 rounded-2xl bg-slate-200/50 dark:bg-white/[0.04] flex items-center justify-center text-slate-400">
          <i data-lucide="image-off" class="w-6 h-6"></i>
        </div>
        <span class="text-xs font-bold text-slate-600 dark:text-slate-300">No Spot Meter Images Cataloged</span>
        <span class="text-[11px] text-slate-400">No photos matching Consumer ID ${item.cid} were found in active image folders.</span>
      </div>
    `;
    safeCreateIcons();
    return;
  }

  gallery.innerHTML = '';
  res.images.forEach((img, idx) => {
    const card = document.createElement('div');
    card.className = "group relative rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#1f1f1f] p-1.5 hover:border-sky-500 hover:shadow-md transition flex flex-col items-center cursor-pointer";
    card.innerHTML = `
      <div class="w-full aspect-[4/3] bg-slate-100 dark:bg-black/50 rounded overflow-hidden flex items-center justify-center mb-1.5 relative">
        <div id="audit-img-loader-${idx}" class="w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
        <img id="audit-img-${idx}" class="w-full h-full object-cover hidden group-hover:scale-105 transition-transform duration-200" />
        <span class="absolute top-1 left-1 px-1.5 py-0.2 rounded bg-black/75 text-[9px] font-mono text-white font-bold leading-tight">#${idx + 1}</span>
        <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
          <span class="px-2 py-0.5 rounded bg-black/80 text-[10px] font-semibold text-white flex items-center gap-1">
            <i data-lucide="maximize-2" class="w-2.5 h-2.5 text-sky-400"></i> View
          </span>
        </div>
      </div>
      <div class="w-full flex items-center justify-between text-[10.5px] px-1 font-mono">
        <span class="font-bold text-slate-800 dark:text-slate-200">${img.date_formatted}</span>
        <span class="text-[9.5px] text-slate-400 truncate max-w-[85px]">${img.filename}</span>
      </div>
    `;

    card.onclick = () => openAuditImageLightbox(idx);
    gallery.appendChild(card);
  });

  loadWithConcurrency(res.images, 4, async (img, idx) => {
    const thumb = await callAPI('get_image_data', img.full_path, 400);
    const loader = document.getElementById(`audit-img-loader-${idx}`);
    const imgEl = document.getElementById(`audit-img-${idx}`);
    if (loader) loader.classList.add('hidden');
    if (imgEl && thumb && thumb.success) {
      imgEl.src = thumb.data;
      imgEl.classList.remove('hidden');
    }
  });

  safeCreateIcons();
}

function copyAuditConsumerCid() {
  const item = auditData.find(x => x.id === auditCurrentId);
  if (!item) return;
  navigator.clipboard.writeText(item.cid);
  updateStatusBar(`Copied Consumer ID: ${item.cid}`, "normal");
}

function jumpActiveAuditToViewer() {
  const item = auditData.find(x => x.id === auditCurrentId);
  if (!item) return;
  document.getElementById('searchInput').value = item.cid;
  switchTab('viewer');
  executeSearch();
}

// Lightbox modal functionality
function openAuditImageLightbox(idx) {
  if (!auditActiveImages || idx < 0 || idx >= auditActiveImages.length) return;
  auditLightboxCurrentIndex = idx;
  auditLightboxZoom = 1.0;

  const modal = document.getElementById('auditImageLightboxModal');
  if (!modal) return;
  modal.classList.remove('hidden');

  renderAuditLightboxImage();
  safeCreateIcons();
}

function closeAuditImageLightbox() {
  const modal = document.getElementById('auditImageLightboxModal');
  if (modal) modal.classList.add('hidden');
}

async function renderAuditLightboxImage() {
  const img = auditActiveImages[auditLightboxCurrentIndex];
  if (!img) return;

  const dateEl = document.getElementById('auditLightboxDate');
  const fileEl = document.getElementById('auditLightboxFilename');
  const imgEl = document.getElementById('auditLightboxImg');
  const loader = document.getElementById('auditLightboxLoader');
  const zoomLevelEl = document.getElementById('auditLightboxZoomLevel');

  if (dateEl) dateEl.innerText = `${img.date_formatted} (${auditLightboxCurrentIndex + 1} of ${auditActiveImages.length})`;
  if (fileEl) fileEl.innerText = img.filename;
  if (zoomLevelEl) zoomLevelEl.innerText = `${Math.round(auditLightboxZoom * 100)}%`;

  if (loader) loader.classList.remove('hidden');
  if (imgEl) {
    imgEl.classList.add('hidden');
    imgEl.style.transform = `scale(${auditLightboxZoom})`;
  }

  const res = await callAPI('get_image_data', img.full_path, 1400);
  if (loader) loader.classList.add('hidden');
  if (imgEl && res && res.success) {
    imgEl.src = res.data;
    imgEl.classList.remove('hidden');
  }
}

function zoomAuditLightbox(delta) {
  auditLightboxZoom = Math.max(0.5, Math.min(3.0, auditLightboxZoom + delta));
  const zoomLevelEl = document.getElementById('auditLightboxZoomLevel');
  const imgEl = document.getElementById('auditLightboxImg');
  if (zoomLevelEl) zoomLevelEl.innerText = `${Math.round(auditLightboxZoom * 100)}%`;
  if (imgEl) imgEl.style.transform = `scale(${auditLightboxZoom})`;
}

function resetAuditLightboxZoom() {
  auditLightboxZoom = 1.0;
  const zoomLevelEl = document.getElementById('auditLightboxZoomLevel');
  const imgEl = document.getElementById('auditLightboxImg');
  if (zoomLevelEl) zoomLevelEl.innerText = '100%';
  if (imgEl) imgEl.style.transform = 'scale(1.0)';
}

function stepAuditLightboxImage(step) {
  if (!auditActiveImages || auditActiveImages.length === 0) return;
  auditLightboxCurrentIndex = (auditLightboxCurrentIndex + step + auditActiveImages.length) % auditActiveImages.length;
  auditLightboxZoom = 1.0;
  renderAuditLightboxImage();
}

async function saveAuditDecisionAndNext() {
  if (auditCurrentId === null) return;
  const item = auditData.find(x => x.id === auditCurrentId);
  if (!item) return;

  const decision = document.querySelector('input[name="auditDecision"]:checked')?.value || 'OK';
  const remarks = document.getElementById('auditRemarksInput')?.value || '';

  item.status = decision;
  item.remarks = remarks;

  await callAPI('save_low_consumption_session', auditData);
  filterAuditQueue();

  advanceAuditQueue(1);
}

function skipAuditItem() {
  advanceAuditQueue(1);
}

function advanceAuditQueue(delta = 1) {
  if (auditFilteredIndices.length === 0) return;
  const currPos = auditFilteredIndices.indexOf(auditCurrentId);
  let nextPos = currPos + delta;
  if (nextPos >= auditFilteredIndices.length) {
    nextPos = 0;
  } else if (nextPos < 0) {
    nextPos = auditFilteredIndices.length - 1;
  }
  selectAuditItem(auditFilteredIndices[nextPos]);
}

async function exportAuditReport() {
  if (auditData.length === 0) {
    alert("No audit records to export. Please load an Excel or paste data first.");
    return;
  }

  updateStatusBar("Exporting Low Consumption Audit CSV...", "loading");
  const res = await callAPI('export_low_consumption_report', auditData);
  if (res && res.success) {
    updateStatusBar(`Report exported: ${res.count} records.`, "normal");
    alert(`Audit report exported successfully!\n\nLocation:\n${res.file_path}`);
  } else {
    updateStatusBar("Export failed.", "error");
    alert("Failed to export report: " + (res ? res.error : "Unknown error"));
  }
}

// Global hotkeys for Audit Studio
document.addEventListener('keydown', (e) => {
  const auditTab = document.getElementById('tab-audit');
  if (!auditTab || auditTab.classList.contains('hidden')) return;

  // Lightbox keyboard navigation
  const lightbox = document.getElementById('auditImageLightboxModal');
  if (lightbox && !lightbox.classList.contains('hidden')) {
    if (e.key === 'Escape') {
      closeAuditImageLightbox();
      return;
    }
    if (e.key === 'ArrowLeft') {
      stepAuditLightboxImage(-1);
      return;
    }
    if (e.key === 'ArrowRight') {
      stepAuditLightboxImage(1);
      return;
    }
  }

  // Verification hotkeys
  if (e.altKey && (e.key === 's' || e.key === 'S')) {
    e.preventDefault();
    saveAuditDecisionAndNext();
  } else if (e.altKey && (e.key === 'n' || e.key === 'N')) {
    e.preventDefault();
    skipAuditItem();
  } else if (e.key === 'ArrowDown' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault();
    advanceAuditQueue(1);
  } else if (e.key === 'ArrowUp' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault();
    advanceAuditQueue(-1);
  }
});

// Window-level exports for Low Consumption Audit
window.toggleAuditPasteModal = toggleAuditPasteModal;
window.toggleAuditGuideModal = toggleAuditGuideModal;
window.pasteAuditFromSystemClipboard = pasteAuditFromSystemClipboard;
window.importAuditPastedText = importAuditPastedText;
window.triggerLoadAuditExcel = triggerLoadAuditExcel;
window.handleAuditFileSelected = handleAuditFileSelected;
window.filterAuditQueue = filterAuditQueue;
window.selectAuditItem = selectAuditItem;
window.saveAuditDecisionAndNext = saveAuditDecisionAndNext;
window.skipAuditItem = skipAuditItem;
window.exportAuditReport = exportAuditReport;
window.setAuditFilterStatus = setAuditFilterStatus;
window.setAuditRemarkTag = setAuditRemarkTag;
window.copyAuditConsumerCid = copyAuditConsumerCid;
window.jumpActiveAuditToViewer = jumpActiveAuditToViewer;
window.openAuditImageLightbox = openAuditImageLightbox;
window.closeAuditImageLightbox = closeAuditImageLightbox;
window.zoomAuditLightbox = zoomAuditLightbox;
window.resetAuditLightboxZoom = resetAuditLightboxZoom;
window.stepAuditLightboxImage = stepAuditLightboxImage;
window.updateDecisionStyles = updateDecisionStyles;

