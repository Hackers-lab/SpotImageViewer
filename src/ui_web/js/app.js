// Global Application State
let currentImages = [];
let currentImageIndex = 0;
let zoomScale = 1.0;
let rotationAngle = 0;
let isPanning = false;
let startX = 0, startY = 0, translateX = 0, translateY = 0;
let currentTariffs = {};
let currentConsumerId = null;

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// On window load
window.addEventListener('pywebviewready', () => {
  console.log("PyWebView Ready!");
  initApp();
});

// Fallback for browser testing
window.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  restoreLayoutPrefs();
  if (!window.pywebview) {
    console.warn("Running in standard browser mode (mocking API)");
    setTimeout(initApp, 300);
  }
});

// --- Collapsible Panes ---
const TAB_META = {
  viewer:   { title: 'Image Viewer',          icon: 'image' },
  bill:     { title: 'Bill Calculator',       icon: 'zap' },
  theft:    { title: 'Theft Assessment',      icon: 'scale' },
  audit:    { title: 'Low Cons. Audit',       icon: 'file-spreadsheet' },
  fuzzy:    { title: 'Batch Fuzzy Lookup',    icon: 'sparkles' },
  settings: { title: 'Global Settings',       icon: 'settings' },
};

function openHelpModal() {
  const modal = document.getElementById('helpModal');
  if (modal) modal.classList.remove('hidden');
  lucide.createIcons();
}

function closeHelpModal() {
  const modal = document.getElementById('helpModal');
  if (modal) modal.classList.add('hidden');
}

function toggleImportPopover(e) {
  if (e) {
    e.stopPropagation();
    e.preventDefault();
  }
  const folderPopover = document.getElementById('folderPopover');
  if (folderPopover) folderPopover.classList.add('hidden');

  const popover = document.getElementById('importPopover');
  if (!popover) return;
  const isHidden = popover.classList.toggle('hidden');
  if (!isHidden) {
    lucide.createIcons();
  }
}

function closeImportPopover() {
  const popover = document.getElementById('importPopover');
  if (popover) popover.classList.add('hidden');
}

function toggleFolderPopover(e) {
  if (e) {
    e.stopPropagation();
    e.preventDefault();
  }
  const importPopover = document.getElementById('importPopover');
  if (importPopover) importPopover.classList.add('hidden');

  const popover = document.getElementById('folderPopover');
  if (!popover) return;
  const isHidden = popover.classList.toggle('hidden');
  if (!isHidden) {
    lucide.createIcons();
  }
}

function closeFolderPopover() {
  const popover = document.getElementById('folderPopover');
  if (popover) popover.classList.add('hidden');
}

// Close popovers when clicking anywhere outside
document.addEventListener('click', (e) => {
  const importPopover = document.getElementById('importPopover');
  const importBtn = document.getElementById('btnImportToggle');
  if (importPopover && !importPopover.classList.contains('hidden')) {
    if (!importPopover.contains(e.target) && !importBtn?.contains(e.target)) {
      importPopover.classList.add('hidden');
    }
  }

  const folderPopover = document.getElementById('folderPopover');
  const folderBtn = document.getElementById('btnFolderToggle');
  if (folderPopover && !folderPopover.classList.contains('hidden')) {
    if (!folderPopover.contains(e.target) && !folderBtn?.contains(e.target)) {
      folderPopover.classList.add('hidden');
    }
  }

  const historyDropdown = document.getElementById('searchHistoryDropdown');
  const searchInput = document.getElementById('searchInput');
  if (historyDropdown && !historyDropdown.classList.contains('hidden')) {
    if (!historyDropdown.contains(e.target) && e.target !== searchInput) {
      historyDropdown.classList.add('hidden');
    }
  }
});

window.toggleImportPopover = toggleImportPopover;
window.closeImportPopover = closeImportPopover;
window.toggleFolderPopover = toggleFolderPopover;
window.closeFolderPopover = closeFolderPopover;
window.openHelpModal = openHelpModal;
window.closeHelpModal = closeHelpModal;

function updatePageHeader(tabId) {
  const meta = TAB_META[tabId];
  if (!meta) return;
  const titleEl = document.getElementById('pageTitle');
  const iconEl = document.getElementById('pageTitleIcon');
  if (titleEl) titleEl.innerText = meta.title;
  if (iconEl) iconEl.innerHTML = `<i data-lucide="${meta.icon}" class="w-4 h-4"></i>`;
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  const collapsing = !sidebar.classList.contains('hidden-panel');
  sidebar.classList.toggle('hidden-panel', collapsing);
  localStorage.setItem('siv_sidebar_collapsed', collapsing ? '1' : '0');
  lucide.createIcons();
}

function toggleDetailsPanel() {
  const panel = document.getElementById('detailsPanel');
  const rail = document.getElementById('detailsPanelRail');
  if (!panel || !rail) return;
  const collapsing = !panel.classList.contains('hidden-panel');
  panel.classList.toggle('hidden-panel', collapsing);
  rail.classList.toggle('hidden', !collapsing);
  rail.classList.toggle('flex', collapsing);
  localStorage.setItem('siv_details_collapsed', collapsing ? '1' : '0');
  lucide.createIcons();
}

function copyDetail(elementId, btn) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText.trim();
  if (!text || text === '-' || text === 'Not Recorded' || text === 'None') return;

  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const originalHtml = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-2.5 h-2.5 text-emerald-500"></i>`;
      lucide.createIcons();
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        lucide.createIcons();
      }, 1200);
    }
  }).catch(err => console.warn('Copy error:', err));
}

function toggleSection(sectionId) {
  const body = document.getElementById(`body-${sectionId}`);
  const icon = document.getElementById(`icon-${sectionId}`);
  if (!body) return;
  const isHidden = body.classList.toggle('hidden');
  if (icon) {
    icon.style.transform = isHidden ? 'rotate(-90deg)' : 'rotate(0deg)';
  }
}

function expandToSection(targetSectionId) {
  const panel = document.getElementById('detailsPanel');
  const rail = document.getElementById('detailsPanelRail');
  if (panel && rail) {
    panel.classList.remove('hidden-panel');
    rail.classList.add('hidden');
    rail.classList.remove('flex');
    localStorage.setItem('siv_details_collapsed', '0');
  }

  // Accordion behavior: open ONLY the targeted section, close the other two
  const allSections = ['section-profile', 'section-notes', 'section-cycles'];
  allSections.forEach(secId => {
    const body = document.getElementById(`body-${secId}`);
    const icon = document.getElementById(`icon-${secId}`);
    if (!body) return;
    if (secId === targetSectionId) {
      body.classList.remove('hidden');
      if (icon) icon.style.transform = 'rotate(0deg)';
    } else {
      body.classList.add('hidden');
      if (icon) icon.style.transform = 'rotate(-90deg)';
    }
  });

  // Scroll to section smoothly
  const secEl = document.getElementById(targetSectionId);
  if (secEl) {
    secEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  lucide.createIcons();
}

function applyTheme(theme) {
  const t = (theme === 'light') ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('siv_theme', t);
  const iconEl = document.getElementById('themeIcon');
  if (iconEl) {
    iconEl.setAttribute('data-lucide', t === 'dark' ? 'sun' : 'moon');
  }
  const labelEl = document.getElementById('themeLabel');
  if (labelEl) {
    labelEl.innerText = t.toUpperCase();
  }
  lucide.createIcons();
}

function restoreLayoutPrefs() {
  // Restore saved theme
  const savedTheme = localStorage.getItem('siv_theme');
  if (savedTheme) {
    applyTheme(savedTheme);
  }

  if (localStorage.getItem('siv_sidebar_collapsed') === '1') {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
      sidebar.classList.add('hidden-panel');
    }
  }
  if (localStorage.getItem('siv_details_collapsed') === '1') {
    const panel = document.getElementById('detailsPanel');
    const rail = document.getElementById('detailsPanelRail');
    if (panel && rail) {
      panel.classList.add('hidden-panel');
      rail.classList.remove('hidden');
      rail.classList.add('flex');
    }
  }
  lucide.createIcons();
}

async function callAPI(method, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      console.error(`API ${method} error:`, e);
      return { success: false, error: e.toString() };
    }
  }
  console.warn(`API method ${method} called without PyWebView`);
  return { success: false, error: "PyWebView API not available" };
}

async function initApp() {
  initAppFont();
  const info = await callAPI('get_app_info');
  if (info && info.theme) {
    applyTheme(info.theme);
  } else {
    const themeRes = await callAPI('get_theme');
    if (themeRes && themeRes.theme) {
      applyTheme(themeRes.theme);
    }
  }
  if (info && info.total_images !== undefined) {
    document.getElementById('statImages').innerText = `${info.total_images.toLocaleString()}`;
    document.getElementById('indexedCount').innerText = info.total_images;
  }
  if (info && info.version) {
    const curVer = info.version;
    const verEl = document.getElementById('statusAppVersion');
    if (verEl) verEl.innerText = `v${curVer} Studio`;
    const setVerEl = document.getElementById('currentAppVersionSettings');
    if (setVerEl) setVerEl.innerText = `v${curVer} Studio Edition`;
    const navVerEl = document.getElementById('navAppVersion');
    if (navVerEl) navVerEl.innerText = `v${curVer} Studio Edition`;
    const helpVerEl = document.getElementById('helpAppVersion');
    if (helpVerEl) helpVerEl.innerText = `v${curVer} Studio Edition Documentation`;
  }
  
  // Load folders
  if (info && info.folders) {
    renderFolders(info.folders);
  } else {
    const fRes = await callAPI('get_folder_status');
    if (fRes && fRes.success) renderFolders(fRes.folders);
  }

  // Load tariffs
  const tariffRes = await callAPI('get_tariffs');
  if (tariffRes && tariffRes.success) {
    currentTariffs = tariffRes.tariffs;
    populateTariffDropdowns();
    renderTariffEditorList();
    runBillCalc();
    runTheftCalc();
  }
  
  setupViewportEvents();
  updateStatusBar("Ready", "normal");
  // Consumer database status check & notification in status bar (right section)
  const dbWarningContainer = document.getElementById('statusDbWarningContainer');
  const dbWarningText = document.getElementById('statusDbWarningText');
  if (info && (!info.has_meter_data || info.consumer_count === 0)) {
    if (dbWarningContainer) {
      dbWarningContainer.classList.remove('hidden');
      dbWarningContainer.classList.add('flex');
    }
    if (dbWarningText) dbWarningText.innerText = "Consumer data not updated";
  } else if (info && info.has_meter_data) {
    if (dbWarningContainer) {
      dbWarningContainer.classList.add('hidden');
      dbWarningContainer.classList.remove('flex');
    }
  }

  // Background update check to notify user in status bar if new update arrives
  checkUpdateSilent();

  // Restore previous low consumption audit session if available
  loadAuditSession();

  // Initialize interactive manual fuzzy lookup rows
  initManualFuzzyLookup();

  lucide.createIcons();
}

let latestUpdateInfo = null;

async function checkUpdateSilent() {
  try {
    const res = await callAPI('check_for_updates');
    if (res && res.success) {
      latestUpdateInfo = res;
      if (res.has_update) {
        const badge = document.getElementById('statusUpdateBadge');
        const text = document.getElementById('statusUpdateText');
        if (badge) {
          badge.classList.remove('hidden');
          badge.classList.add('flex');
        }
        if (text) text.innerText = `Update Available (v${res.latest_version})`;
        updateStatusBar(`New version v${res.latest_version} available. Click update badge to install.`, "normal");
      }
    }
  } catch (e) {
    // Silent fail in background
  }
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  const activeTab = document.getElementById(`tab-${tabId}`);
  if (activeTab) activeTab.classList.remove('hidden');

  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tabId);
  });

  // Limit search bar and viewer actions strictly to Image Viewer tab
  const viewerActions = document.getElementById('viewerHeaderActions');
  if (viewerActions) {
    if (tabId === 'viewer') {
      viewerActions.classList.remove('hidden');
      viewerActions.classList.add('flex');
    } else {
      viewerActions.classList.add('hidden');
      viewerActions.classList.remove('flex');
    }
  }

  updatePageHeader(tabId);
  lucide.createIcons();
}

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
  callAPI('set_theme', newTheme);
}

// --- Universal Search Handling ---
async function showSearchHistoryDropdown() {
  const dropdown = document.getElementById('searchHistoryDropdown');
  const list = document.getElementById('searchHistoryList');
  if (!dropdown || !list) return;

  const res = await callAPI('get_search_history', 'consumer_ids');
  const history = (res && res.history) ? res.history : [];

  if (history.length === 0) {
    list.innerHTML = '<p class="text-[11px] text-slate-400 italic px-2 py-1.5 text-center">No recent searches</p>';
  } else {
    list.innerHTML = '';
    // Reverse so newest appears on top
    [...history].reverse().forEach(item => {
      const row = document.createElement('div');
      row.className = 'flex items-center justify-between px-2.5 py-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800/70 cursor-pointer text-xs transition group';
      row.innerHTML = `
        <div class="flex items-center gap-2 min-w-0">
          <i data-lucide="clock" class="w-3 h-3 text-slate-400"></i>
          <span class="font-mono text-slate-800 dark:text-slate-200">${item}</span>
        </div>
        <i data-lucide="arrow-up-right" class="w-3 h-3 opacity-0 group-hover:opacity-100 text-sky-500 transition"></i>
      `;
      row.onmousedown = (e) => {
        // Use onmousedown so it triggers before input blur
        e.preventDefault();
        const input = document.getElementById('searchInput');
        if (input) input.value = item;
        closeSearchHistoryDropdown();
        handleSearch();
      };
      list.appendChild(row);
    });
  }

  dropdown.classList.remove('hidden');
  lucide.createIcons();
}

function closeSearchHistoryDropdown(e) {
  if (e) {
    e.stopPropagation();
  }
  const dropdown = document.getElementById('searchHistoryDropdown');
  if (dropdown) dropdown.classList.add('hidden');
}

window.showSearchHistoryDropdown = showSearchHistoryDropdown;
window.closeSearchHistoryDropdown = closeSearchHistoryDropdown;

// --- Search Bar Clear Button & Viewer Reset ---
function toggleSearchClearBtn() {
  const input = document.getElementById('searchInput');
  const btn = document.getElementById('btnSearchClear');
  if (!btn) return;
  if (input && input.value.length > 0) {
    btn.classList.remove('hidden');
  } else {
    btn.classList.add('hidden');
  }
}

function clearSearchInput() {
  const input = document.getElementById('searchInput');
  if (input) {
    input.value = '';
    input.focus();
  }
  toggleSearchClearBtn();
  clearViewerState();
}

function clearViewerState() {
  // Reset consumer state
  currentConsumerId = null;
  currentImages = [];
  currentImageIndex = 0;

  // Clear profile panel
  ['profileName','profileCid','profileMeter','profileMobile','profileAddress','profileLoad','profileClass'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerText = '-';
  });

  // Clear viewport image
  const mainImg = document.getElementById('mainImage');
  if (mainImg) { mainImg.src = ''; mainImg.classList.add('hidden'); }
  
  resetZoom();

  // Show placeholder
  const placeholder = document.getElementById('imagePlaceholder');
  if (placeholder) {
    placeholder.classList.remove('hidden');
    placeholder.innerHTML = `
      <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-slate-400 dark:text-slate-600">
        <i data-lucide="image-off" class="w-8 h-8"></i>
      </div>
      <p class="text-sm font-medium text-slate-500">Search a Consumer ID or Meter to view spot images</p>
    `;
    lucide.createIcons();
  }

  // Hide date tag, toggle group, overview grid
  const dateTagContainer = document.getElementById('imgDateTagContainer');
  if (dateTagContainer) dateTagContainer.classList.add('hidden');
  const toggleGroup = document.getElementById('viewModeToggleGroup');
  if (toggleGroup) toggleGroup.classList.add('hidden');
  const overviewGridContainer = document.getElementById('overviewGridContainer');
  if (overviewGridContainer) overviewGridContainer.classList.add('hidden');
  const gridInner = document.getElementById('overviewGrid');
  if (gridInner) gridInner.innerHTML = '';
  const viewport = document.getElementById('viewport');
  if (viewport) viewport.classList.remove('hidden');
  currentImageViewMode = 'single';

  // Clear filmstrip
  const filmstrip = document.getElementById('filmstripContainer');
  if (filmstrip) filmstrip.innerHTML = '<p class="text-[11px] text-slate-400 italic px-2">Thumbnails will appear here once images are loaded.</p>';
  document.getElementById('filmstripCountBadge').innerText = '0';
  document.getElementById('searchResultCount').innerText = '0 photos';

  // Clear cycles list
  const cyclesList = document.getElementById('cyclesList');
  if (cyclesList) cyclesList.innerHTML = '';

  // Hide Live OSD HUD
  const hud = document.getElementById('liveOsdHud');
  if (hud) hud.classList.add('hidden');

  // Reset notes
  const noteCategory = document.getElementById('noteCategory');
  if (noteCategory) noteCategory.value = 'OK';
  const noteRemarks = document.getElementById('noteRemarks');
  if (noteRemarks) noteRemarks.value = '';
}

window.toggleSearchClearBtn = toggleSearchClearBtn;
window.clearSearchInput = clearSearchInput;
window.clearViewerState = clearViewerState;

async function handleSearch() {
  closeSearchHistoryDropdown();
  const query = document.getElementById('searchInput').value.trim();
  const filterType = document.getElementById('searchType')?.value || 'auto';
  if (!query) return;

  // Save to search history
  callAPI('save_search_history', 'consumer_ids', query);

  const res = await callAPI('search_consumer', query, filterType);
  if (!res || !res.success || !res.results || !res.results.length) {
    // Clear previous consumer state so stale images don't remain
    clearViewerState();
    alert(`No matching consumers found for "${query}"`);
    return;
  }

  if (res.results.length > 1) {
    showSearchModal(res.results);
  } else {
    selectConsumer(res.results[0]);
  }
}

function showSearchModal(results) {
  const tbody = document.getElementById('searchResultsTable');
  tbody.innerHTML = '';
  results.forEach(r => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer';
    tr.innerHTML = `
      <td class="px-4 py-3 font-mono text-sky-600 dark:text-sky-400">${r.consumer_id}</td>
      <td class="px-4 py-3 font-mono">${r.meter_no || '-'}</td>
      <td class="px-4 py-3">${r.name || '-'}</td>
      <td class="px-4 py-3">${r.mobile_number || '-'}</td>
      <td class="px-4 py-3"><button class="bg-sky-600 text-white px-3 py-1 rounded text-xs">Select</button></td>
    `;
    tr.onclick = () => {
      selectConsumer(r);
      closeSearchModal();
    };
    tbody.appendChild(tr);
  });
  document.getElementById('searchModal').classList.remove('hidden');
}

function closeSearchModal() {
  document.getElementById('searchModal').classList.add('hidden');
}

async function selectConsumer(profile) {
  currentConsumerId = profile.consumer_id;
  populateProfile(profile);
  
  // Load note
  const noteRes = await callAPI('get_consumer_note', profile.consumer_id);
  if (noteRes && noteRes.success && noteRes.note) {
    document.getElementById('noteCategory').value = noteRes.note;
    document.getElementById('noteRemarks').value = noteRes.remarks || '';
  } else {
    document.getElementById('noteCategory').value = 'OK';
    document.getElementById('noteRemarks').value = '';
  }

  // Load images
  await loadConsumerImages(profile.consumer_id);

  // Load Live WBSEDCL OSD & Connection Status in background
  loadLiveOSD(profile.consumer_id);
}

function populateProfile(p) {
  document.getElementById('profileName').innerText = p.name || 'Not Recorded';
  document.getElementById('profileCid').innerText = p.consumer_id || '-';
  document.getElementById('profileMeter').innerText = p.meter_no || '-';
  document.getElementById('profileMobile').innerText = p.mobile_number || 'None';
  document.getElementById('profileAddress').innerText = p.address || 'Not Recorded';
  document.getElementById('profileLoad').innerText = p.contractual_load || '1.0 kVA';
  document.getElementById('profileClass').innerText = p.class || 'Domestic';
}

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
    if (refreshIcon) refreshIcon.classList.remove('animate-spin');

    if (!res || !res.success || !res.data) {
      if (statusBadge) statusBadge.className = "";
      if (statusText) {
        statusText.className = "text-[10px] font-semibold text-rose-500 dark:text-rose-400";
        statusText.innerText = res ? (res.error || "Portal unreachable") : "Offline";
      }
      return;
    }

    const d = res.data;
    currentLiveOsdData = d;

    // Status styling - Simple clean text without pill
    if (statusBadge) statusBadge.className = "";
    if (statusText) {
      const connStatus = String(d.connectionStatus || '').toUpperCase();
      if (d.isLive || connStatus === 'LIVE') {
        statusText.className = "text-[10.5px] font-bold text-emerald-600 dark:text-emerald-400";
        statusText.innerText = "Connected";
      } else if (d.isDeemed || connStatus === 'DEEMED') {
        statusText.className = "text-[10px] font-bold text-amber-600 dark:text-amber-400";
        statusText.innerText = d.connectionStatus || "Deemed";
      } else if (d.isDisconnected || connStatus === 'DISCONNECTED') {
        statusText.className = "text-[10px] font-bold text-rose-600 dark:text-rose-400";
        statusText.innerText = d.connectionStatus || "Disconnected";
      } else {
        statusText.className = "text-[10px] font-semibold text-slate-600 dark:text-slate-400";
        statusText.innerText = d.connectionStatus || "-";
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

    lucide.createIcons();
  } catch (err) {
    console.error("Failed to load live OSD:", err);
    if (refreshIcon) refreshIcon.classList.remove('animate-spin');
    if (statusBadge) statusBadge.className = "";
    if (statusText) {
      statusText.className = "text-[10px] font-semibold text-rose-500 dark:text-rose-400";
      statusText.innerText = "Error";
    }
  }
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


async function saveNote() {
  if (!currentConsumerId) return alert("No consumer selected");
  const noteType = document.getElementById('noteCategory').value;
  const remarks = document.getElementById('noteRemarks').value;
  
  const res = await callAPI('save_consumer_note', currentConsumerId, noteType, remarks);
  if (res && res.success) {
    alert("Note saved successfully!");
  } else {
    alert("Failed to save note: " + (res ? res.error : "Unknown error"));
  }
}

async function deleteNote() {
  if (!currentConsumerId) return;
  const res = await callAPI('delete_consumer_note', currentConsumerId);
  if (res && res.success) {
    document.getElementById('noteCategory').value = 'OK';
    document.getElementById('noteRemarks').value = '';
    alert("Note deleted.");
  }
}

async function loadConsumerImages(consumerId) {
  const res = await callAPI('get_consumer_images', consumerId);
  if (!res || !res.success) {
    // Clear viewport and grid fully on failure or no images
    currentImages = [];
    currentImageIndex = 0;
    resetZoom();
    const mainImg = document.getElementById('mainImage');
    if (mainImg) {
      mainImg.src = '';
      mainImg.classList.add('hidden');
    }
    const errMsg = (res && res.error) ? res.error : "This consumer has no spot images";
    const placeholder = document.getElementById('imagePlaceholder');
    if (placeholder) {
      placeholder.classList.remove('hidden');
      placeholder.innerHTML = `
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">${escapeHtml(errMsg)}</p>
      `;
      lucide.createIcons();
    }
    const grid = document.getElementById('overviewGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
          <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
            <i data-lucide="image-off" class="w-8 h-8"></i>
          </div>
          <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
          <p class="text-sm font-medium text-slate-500">${escapeHtml(errMsg)}</p>
        </div>
      `;
      lucide.createIcons();
    }

    switchImageViewMode('single');

    const cyclesList = document.getElementById('cyclesList');
    if (cyclesList) cyclesList.innerHTML = '';
    const filmstrip = document.getElementById('filmstripContainer');
    if (filmstrip) filmstrip.innerHTML = `<p class="text-xs text-amber-500 px-4">${escapeHtml(errMsg)}</p>`;
    const filmBadge = document.getElementById('filmstripCountBadge');
    if (filmBadge) filmBadge.innerText = '0';
    const searchResCount = document.getElementById('searchResultCount');
    if (searchResCount) searchResCount.innerText = '0 photos';
    const countSpan = document.getElementById('viewAllPhotosCount');
    if (countSpan) countSpan.innerText = '0';
    const dateTag = document.getElementById('imgDateTagContainer');
    if (dateTag) dateTag.classList.add('hidden');
    const toggleGroup = document.getElementById('viewModeToggleGroup');
    if (toggleGroup) toggleGroup.classList.add('hidden');
    return;
  }

  currentImages = res.images || [];
  currentImageIndex = 0;
  document.getElementById('searchResultCount').innerText = `${res.total_images || 0} photos`;

  // Render cycles
  const cyclesList = document.getElementById('cyclesList');
  cyclesList.innerHTML = '';
  if (res.dates) {
    res.dates.forEach((dateStr) => {
      const btn = document.createElement('button');
      btn.dataset.date = dateStr;
      btn.className = "w-full text-left px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#303030] transition flex items-center justify-between group";
      const count = res.grouped[dateStr] ? res.grouped[dateStr].length : 0;
      btn.innerHTML = `
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="cycle-active-indicator hidden w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0"></span>
          <span class="font-mono">${dateStr}</span>
        </div>
        <span class="text-xs text-slate-500 font-mono">${count} img</span>
      `;
      btn.onclick = () => {
        const targetIdx = currentImages.findIndex(img => img.date_formatted === dateStr);
        if (targetIdx !== -1) showImage(targetIdx);
      };
      cyclesList.appendChild(btn);
    });
  }

  // Update all photos counter and show toggle button group
  const toggleGroup = document.getElementById('viewModeToggleGroup');
  const countSpan = document.getElementById('viewAllPhotosCount');
  if (toggleGroup) {
    toggleGroup.classList.remove('hidden');
    toggleGroup.classList.add('flex');
  }
  if (countSpan) countSpan.innerText = currentImages.length;

  // Render filmstrip
  renderFilmstrip();

  // Render Multi-Image Overview Grid
  renderOverviewGrid();

  if (currentImages.length > 0) {
    // Show Overview Grid first for overall consumer idea if more than 1 image exists,
    // or jump straight to single if only 1 photo exists
    if (currentImages.length > 1) {
      switchImageViewMode('grid');
    } else {
      switchImageViewMode('single');
      showImage(0);
    }
  } else {
    switchImageViewMode('single');
    resetZoom();
    const mainImg = document.getElementById('mainImage');
    if (mainImg) {
      mainImg.src = '';
      mainImg.classList.add('hidden');
    }
    const placeholder = document.getElementById('imagePlaceholder');
    if (placeholder) {
      placeholder.classList.remove('hidden');
      placeholder.innerHTML = `
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
      `;
      lucide.createIcons();
    }
    const grid = document.getElementById('overviewGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
          <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
            <i data-lucide="image-off" class="w-8 h-8"></i>
          </div>
          <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
          <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
        </div>
      `;
      lucide.createIcons();
    }
    const dateTagContainer = document.getElementById('imgDateTagContainer');
    if (dateTagContainer) dateTagContainer.classList.add('hidden');
    if (toggleGroup) toggleGroup.classList.add('hidden');
  }
}

let currentImageViewMode = 'single'; // 'single' | 'grid'

function switchImageViewMode(mode) {
  currentImageViewMode = mode;
  const viewport = document.getElementById('viewport');
  const gridContainer = document.getElementById('overviewGridContainer');
  const dateTag = document.getElementById('imgDateTagContainer');
  const btnPreview = document.getElementById('btnViewPreview');

  if (mode === 'grid') {
    if (viewport) viewport.classList.add('hidden');
    if (gridContainer) gridContainer.classList.remove('hidden');
    if (dateTag) dateTag.classList.add('hidden');
    if (btnPreview) {
      btnPreview.className = 'h-9 px-3 rounded-xl flex items-center gap-1.5 font-bold text-xs bg-sky-600 text-white shadow-xl transition';
    }
  } else {
    if (viewport) viewport.classList.remove('hidden');
    if (gridContainer) gridContainer.classList.add('hidden');
    if (currentImages.length > 0 && dateTag) {
      dateTag.classList.remove('hidden');
      dateTag.classList.add('flex');
    }
    if (btnPreview) {
      btnPreview.className = 'h-9 px-3 rounded-xl flex items-center gap-1.5 font-semibold text-xs transition bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-xl text-slate-700 dark:text-slate-200 hover:text-sky-600 dark:hover:text-sky-400 hover:border-sky-500/50';
    }

    // Ensure active image is rendered in viewport
    if (currentImages.length > 0) {
      showImage(currentImageIndex);
    }
  }
  lucide.createIcons();
}

async function renderOverviewGrid() {
  const grid = document.getElementById('overviewGrid');
  if (!grid) return;
  grid.innerHTML = '';

  if (!currentImages || currentImages.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  for (let idx = 0; idx < currentImages.length; idx++) {
    const img = currentImages[idx];
    const card = document.createElement('div');
    card.className = "group relative rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-[#1f1f1f] p-2 hover:border-sky-500/50 hover:shadow-lg transition cursor-pointer flex flex-col items-center";
    card.innerHTML = `
      <div class="w-full aspect-[4/3] bg-slate-100 dark:bg-black/50 rounded-lg overflow-hidden flex items-center justify-center mb-2 relative">
        <div id="grid-loader-${idx}" class="w-5 h-5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
        <img id="grid-img-${idx}" class="w-full h-full object-cover hidden group-hover:scale-105 transition-transform duration-200" />
        <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/70 text-[9px] font-mono text-white font-semibold">#${idx + 1}</span>
      </div>
      <div class="w-full flex items-center justify-center text-xs px-0.5">
        <span class="font-mono font-semibold text-slate-800 dark:text-slate-200 text-center">${img.date_formatted}</span>
      </div>
    `;

    card.onclick = () => {
      switchImageViewMode('single');
      showImage(idx);
    };
    grid.appendChild(card);

    // Asynchronously load thumbnail for card
    (async () => {
      const thumb = await callAPI('get_image_data', img.full_path, 350);
      const loader = document.getElementById(`grid-loader-${idx}`);
      const imgEl = document.getElementById(`grid-img-${idx}`);
      if (loader) loader.classList.add('hidden');
      if (imgEl && thumb && thumb.success) {
        imgEl.src = thumb.data;
        imgEl.classList.remove('hidden');
      }
    })();
  }
}

window.switchImageViewMode = switchImageViewMode;

async function renderFilmstrip() {
  const container = document.getElementById('filmstripContainer');
  const countBadge = document.getElementById('filmstripCountBadge');
  if (countBadge) countBadge.innerText = currentImages.length;
  if (!container) return;
  container.innerHTML = '';

  if (currentImages.length === 0) {
    container.innerHTML = '<p class="text-[11px] text-slate-400 italic px-2">Thumbnails will appear here once images are loaded.</p>';
    return;
  }

  for (let idx = 0; idx < currentImages.length; idx++) {
    const img = currentImages[idx];
    const item = document.createElement('div');
    item.className = `filmstrip-thumb flex flex-col items-center justify-center p-0.5 rounded cursor-pointer shrink-0 ${idx === currentImageIndex ? 'active' : ''}`;
    item.title = `${img.date_formatted} (${img.filename})`;
    
    // Try to get thumbnail
    const thumbRes = await callAPI('get_image_data', img.full_path, 150);
    if (thumbRes && thumbRes.success) {
      item.innerHTML = `
        <img src="${thumbRes.data}" class="w-full h-[26px] object-cover rounded mb-0.5" />
        <span class="text-[9px] font-mono leading-none text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
      `;
    } else {
      item.innerHTML = `
        <i data-lucide="image" class="w-4 h-4 text-slate-400 mb-0.5"></i>
        <span class="text-[9px] font-mono leading-none text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
      `;
    }
    
    item.onclick = () => showImage(idx);
    container.appendChild(item);
  }
  lucide.createIcons();
}

function toggleFilmstrip() {
  const wrapper = document.getElementById('filmstripWrapper');
  if (!wrapper) return;
  wrapper.classList.toggle('collapsed-strip');
  lucide.createIcons();
}

window.toggleFilmstrip = toggleFilmstrip;

async function showImage(index) {
  if (index < 0 || index >= currentImages.length) return;
  currentImageIndex = index;
  const item = currentImages[index];

  // If currently in preview grid mode, switch to single image inspector view
  if (currentImageViewMode === 'grid') {
    switchImageViewMode('single');
  }

  const dateTag = document.getElementById('imgDateTag');
  const dateContainer = document.getElementById('imgDateTagContainer');
  if (dateTag) dateTag.innerText = item.date_formatted;
  if (dateContainer) {
    dateContainer.classList.remove('hidden');
    dateContainer.classList.add('flex');
  }

  // Update active state on filmstrip
  document.querySelectorAll('.filmstrip-thumb').forEach((el, i) => {
    if (i === index) el.classList.add('active');
    else el.classList.remove('active');
  });

  // Highlight active date in the dates/cycles list
  document.querySelectorAll('#cyclesList button').forEach(btn => {
    const isSelected = btn.dataset.date === item.date_formatted;
    btn.classList.toggle('bg-sky-500/15', isSelected);
    btn.classList.toggle('dark:bg-sky-500/20', isSelected);
    btn.classList.toggle('text-sky-600', isSelected);
    btn.classList.toggle('dark:text-sky-400', isSelected);
    btn.classList.toggle('font-bold', isSelected);
    btn.classList.toggle('border', isSelected);
    btn.classList.toggle('border-sky-500/30', isSelected);

    // Indicator bullet / check icon
    const indicator = btn.querySelector('.cycle-active-indicator');
    if (indicator) {
      indicator.classList.toggle('hidden', !isSelected);
    }
  });

  const mainImg = document.getElementById('mainImage');
  const placeholder = document.getElementById('imagePlaceholder');

  placeholder.innerHTML = `<div class="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>`;
  placeholder.classList.remove('hidden');
  mainImg.classList.add('hidden');

  const imgData = await callAPI('get_image_data', item.full_path, 1600);
  if (imgData && imgData.success) {
    mainImg.src = imgData.data;
    mainImg.classList.remove('hidden');
    placeholder.classList.add('hidden');
    resetZoom();
  } else {
    placeholder.innerHTML = `<p class="text-xs text-rose-500">Failed to render image file</p>`;
  }
}

function stepImage(direction) {
  if (currentImages.length > 0) {
    let newIdx = currentImageIndex + direction;
    if (newIdx < 0) newIdx = currentImages.length - 1;
    if (newIdx >= currentImages.length) newIdx = 0;
    showImage(newIdx);
  }
}

async function printActiveImage() {
  if (!currentImages.length) return;
  const res = await callAPI('print_image', currentImages[currentImageIndex].full_path);
  if (res && !res.success) {
    alert("Failed to print image: " + (res.error || "Unknown error"));
  }
}

async function saveActiveImage() {
  if (!currentImages.length) return;
  const res = await callAPI('save_image_to', currentImages[currentImageIndex].full_path, '');
  if (res && res.success) {
    alert("Image saved successfully to:\n" + res.path);
  } else if (res && res.error) {
    alert("Failed to save image: " + res.error);
  }
}

async function saveAllImages() {
  if (!currentConsumerId) return;
  const res = await callAPI('save_all_images', currentConsumerId, '');
  if (res && res.success) {
    alert(`Successfully saved ${res.count} images to:\n${res.path}`);
  } else if (res && res.error) {
    alert("Failed to save all images: " + res.error);
  }
}

// --- Zoom & Pan Canvas ---
function zoomIn() {
  zoomScale = Math.min(zoomScale + 0.25, 4.0);
  applyTransform();
}
function zoomOut() {
  zoomScale = Math.max(zoomScale - 0.25, 0.5);
  applyTransform();
}
function resetZoom() {
  zoomScale = 1.0;
  rotationAngle = 0;
  translateX = 0;
  translateY = 0;
  applyTransform();
}
function rotateImage() {
  rotationAngle = (rotationAngle + 90) % 360;
  applyTransform();
}
function applyTransform() {
  const mainImg = document.getElementById('mainImage');
  mainImg.style.transform = `translate(${translateX}px, ${translateY}px) scale(${zoomScale}) rotate(${rotationAngle}deg)`;
  document.getElementById('zoomLevel').innerText = `${Math.round(zoomScale * 100)}%`;
}

function setupViewportEvents() {
  const vp = document.getElementById('viewport');
  vp.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (e.deltaY < 0) zoomIn();
    else zoomOut();
  });

  vp.addEventListener('mousedown', (e) => {
    if (e.button === 0) {
      isPanning = true;
      startX = e.clientX - translateX;
      startY = e.clientY - translateY;
    }
  });

  window.addEventListener('mousemove', (e) => {
    if (isPanning) {
      translateX = e.clientX - startX;
      translateY = e.clientY - startY;
      applyTransform();
    }
  });

  window.addEventListener('mouseup', () => {
    isPanning = false;
  });

  // Keyboard navigation for images:
  // ArrowLeft / ArrowUp -> Previous image (-1)
  // ArrowRight / ArrowDown -> Next image (+1)
  window.addEventListener('keydown', (e) => {
    // Only navigate if not focused on text inputs, textareas, selects, or contenteditable elements
    const tag = e.target.tagName ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) {
      return;
    }

    // Only active if viewer tab is visible
    const viewerTab = document.getElementById('tab-viewer');
    if (viewerTab && viewerTab.classList.contains('hidden')) {
      return;
    }

    // Directly step the image. Do NOT use button.click() because if the button
    // or container has focus, browsers will trigger native activation alongside keydown,
    // causing a double-step (1 -> 3 -> 5).
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (currentImageViewMode === 'grid') {
        switchImageViewMode('single');
      }
      stepImage(-1);
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (currentImageViewMode === 'grid') {
        switchImageViewMode('single');
      }
      stepImage(1);
    }
  });
}

// --- Bill Calculations ---
function populateTariffDropdowns() {
  const bSelect = document.getElementById('billCategory');
  const tSelect = document.getElementById('theftCategory');
  bSelect.innerHTML = '';
  tSelect.innerHTML = '';

  Object.keys(currentTariffs).forEach(cat => {
    const opt1 = document.createElement('option');
    opt1.value = cat;
    opt1.innerText = cat;
    bSelect.appendChild(opt1);

    const opt2 = document.createElement('option');
    opt2.value = cat;
    opt2.innerText = cat;
    tSelect.appendChild(opt2);
  });
}

function toggleBillCycle() {
  const cycle = document.getElementById('billCycle').value;
  const proRataRow = document.getElementById('proRataRow');
  const benefitContainer = document.getElementById('tariffBenefitContainer');

  if (cycle === 'Pro-Rata') {
    proRataRow.classList.remove('hidden');
    proRataRow.classList.add('grid');
    benefitContainer.classList.add('hidden');
  } else if (cycle === 'Benefit') {
    proRataRow.classList.add('hidden');
    proRataRow.classList.remove('grid');
    benefitContainer.classList.remove('hidden');
    // Run tariff benefit comparison calculation
    runDaysComparison();
  } else {
    proRataRow.classList.add('hidden');
    proRataRow.classList.remove('grid');
    benefitContainer.classList.add('hidden');
  }
  runBillCalc();
}

function calculateDaysAndRun() {
  const fd = new Date(document.getElementById('billFromDate').value);
  const td = new Date(document.getElementById('billToDate').value);
  if (!isNaN(fd) && !isNaN(td)) {
    const diffTime = Math.abs(td - fd);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; 
    document.getElementById('billDays').value = diffDays;
  }
  runBillCalc();
}

async function runBillCalc() {
  const cat = document.getElementById('billCategory').value;
  const tData = currentTariffs[cat];
  if (!tData) return;
  
  // Toggle TOD / Normal units visibility based on category or phase
  const phase = document.querySelector('input[name="phase"]:checked').value;
  const isTod = tData.tod_applicable || cat.includes("TOD");
  
  if (isTod) {
    document.getElementById('normalUnitsContainer').classList.add('hidden');
    document.getElementById('todUnitsContainer').classList.remove('hidden');
  } else {
    document.getElementById('normalUnitsContainer').classList.remove('hidden');
    document.getElementById('todUnitsContainer').classList.add('hidden');
  }
  
  const isAgri = cat.toLowerCase().includes('agri');
  if (isAgri && !isTod) document.getElementById('monsoonContainer').classList.remove('hidden');
  else document.getElementById('monsoonContainer').classList.add('hidden');

  let units = 0;
  let todData = null;
  if (isTod) {
    todData = {
      normal: parseInt(document.getElementById('todNormal').value || 0),
      peak: parseInt(document.getElementById('todPeak').value || 0),
      off_peak: parseInt(document.getElementById('todOffPeak').value || 0)
    };
    units = todData.normal + todData.peak + todData.off_peak;
  } else {
    units = parseInt(document.getElementById('billUnits').value || 0);
  }

  const payload = {
    category: cat,
    cycle: document.getElementById('billCycle').value,
    days: parseInt(document.getElementById('billDays').value || 30),
    units: units,
    tod_units: todData,
    load: parseFloat(document.getElementById('billLoad').value || 1.0),
    load_unit: document.getElementById('billLoadUnit').value,
    mvca: parseFloat(document.getElementById('billMvca').value || 0),
    meter_rent_applicable: document.getElementById('billMeterRent').checked,
    is_monsoon: document.getElementById('billMonsoon').checked,
    phase: phase
  };

  const res = await callAPI('calculate_bill', payload);
  if (res && res.success) {
    const r = res.result;
    const energyEl = document.getElementById('resEnergy');
    const fixedEl = document.getElementById('resFixed');
    const minRow = document.getElementById('resMinRow');

    if (r.min_charge_override) {
      if (minRow) {
        minRow.classList.remove('hidden');
        minRow.classList.add('flex');
      }
      energyEl.innerHTML = `<span class="text-slate-400 font-normal italic">OVERRIDDEN</span>`;
      fixedEl.innerHTML = `<span class="text-slate-400 font-normal italic">OVERRIDDEN</span>`;
      document.getElementById('resMin').innerHTML = `\u20B9 ${(r.minimum_charge || 0).toFixed(2)}`;
    } else {
      if (minRow) {
        minRow.classList.add('hidden');
        minRow.classList.remove('flex');
      }
      energyEl.innerHTML = `\u20B9 ${r.energy_charge.toFixed(2)}`;
      fixedEl.innerHTML = `\u20B9 ${r.fixed_charge.toFixed(2)}`;
      document.getElementById('resMin').innerHTML = `\u20B9 ${(r.minimum_charge || 0).toFixed(2)}`;
    }

    document.getElementById('resMeter').innerHTML = `\u20B9 ${r.meter_rent.toFixed(2)}`;
    document.getElementById('resMvca').innerHTML = `\u20B9 ${r.mvca_charge.toFixed(2)}`;
    document.getElementById('resEdRate').innerText = r.ed_percentage || 0;
    document.getElementById('resEd').innerHTML = `\u20B9 ${r.ed_charge.toFixed(2)}`;
    document.getElementById('resRelief').innerHTML = `- \u20B9 ${r.gov_relief.toFixed(2)}`;
    
    document.getElementById('resGross').innerHTML = `\u20B9 ${r.gross_bill.toFixed(2)}`;
    document.getElementById('resTimely').innerHTML = `- \u20B9 ${(r.rebate_timely || 0).toFixed(2)}`;
    document.getElementById('resEpay').innerHTML = `- \u20B9 ${(r.rebate_epay || 0).toFixed(2)}`;
    document.getElementById('resSpecial').innerHTML = `- \u20B9 ${(r.rebate_special || 0).toFixed(2)}`;
    
    document.getElementById('resNet').innerHTML = `\u20B9 ${r.rounded_bill.toLocaleString('en-IN')}`;

    // Auto-sync baseline comparator values if comparator is visible
    syncComparatorBaseline(payload, r);
  }
}

let isSyncingComparator = false;
function syncComparatorBaseline(payload, r) {
  if (isSyncingComparator) return;
  const container = document.getElementById('tariffBenefitContainer');
  if (!container || container.classList.contains('hidden')) return;

  const daysAEl = document.getElementById('compDaysA');
  const unitsAEl = document.getElementById('compUnitsA');
  if (!daysAEl || !unitsAEl) return;

  // Let baseline follow main calculator unless user has independently typed in comparator
  if (document.activeElement !== daysAEl && document.activeElement !== unitsAEl &&
      document.activeElement !== document.getElementById('compDaysB') &&
      document.activeElement !== document.getElementById('compUnitsB')) {
    daysAEl.value = payload.cycle === 'Quarterly' ? 90 : (payload.cycle === 'Monthly' ? 30 : payload.days);
    unitsAEl.value = payload.units;
    runDaysComparison(true);
  }
}

async function runDaysComparison(fromSync = false) {
  const cat = document.getElementById('billCategory').value;
  const phase = document.querySelector('input[name="phase"]:checked').value;
  const load = parseFloat(document.getElementById('billLoad').value || 1.0);
  const loadUnit = document.getElementById('billLoadUnit').value;
  const mvca = parseFloat(document.getElementById('billMvca').value || 0);
  const meterRent = document.getElementById('billMeterRent').checked;
  const isMonsoon = document.getElementById('billMonsoon').checked;

  const daysA = parseInt(document.getElementById('compDaysA').value || 90);
  let unitsA = parseInt(document.getElementById('compUnitsA').value || 0);

  const daysB = parseInt(document.getElementById('compDaysB').value || 354);
  let unitsB = parseInt(document.getElementById('compUnitsB').value || 0);

  // Calculate Scenario A
  const pA = {
    category: cat,
    cycle: 'Pro-Rata',
    days: daysA,
    units: unitsA,
    load: load,
    load_unit: loadUnit,
    mvca: mvca,
    meter_rent_applicable: meterRent,
    is_monsoon: isMonsoon,
    phase: phase
  };

  // Calculate Scenario B
  const pB = {
    category: cat,
    cycle: 'Pro-Rata',
    days: daysB,
    units: unitsB,
    load: load,
    load_unit: loadUnit,
    mvca: mvca,
    meter_rent_applicable: meterRent,
    is_monsoon: isMonsoon,
    phase: phase
  };

  const [resA, resB] = await Promise.all([
    callAPI('calculate_bill', pA),
    callAPI('calculate_bill', pB)
  ]);

  if (resA && resA.success && resB && resB.success) {
    const a = resA.result;
    const b = resB.result;

    // Populate Scenario A outputs
    document.getElementById('compEnergyFixedA').innerHTML = `\u20B9 ${(a.energy_charge + a.fixed_charge).toFixed(2)}`;
    document.getElementById('compReliefA').innerHTML = `- \u20B9 ${a.gov_relief.toFixed(2)}`;
    document.getElementById('compEdA').innerHTML = `\u20B9 ${a.ed_charge.toFixed(2)}`;
    document.getElementById('compNetA').innerHTML = `\u20B9 ${a.rounded_bill.toLocaleString('en-IN')}`;
    const dailyA = daysA > 0 ? (a.rounded_bill / daysA) : 0;
    document.getElementById('compDailyA').innerHTML = `\u20B9 ${dailyA.toFixed(2)}/day`;

    // Populate Scenario B outputs
    document.getElementById('compEnergyFixedB').innerHTML = `\u20B9 ${(b.energy_charge + b.fixed_charge).toFixed(2)}`;
    document.getElementById('compReliefB').innerHTML = `- \u20B9 ${b.gov_relief.toFixed(2)}`;
    document.getElementById('compEdB').innerHTML = `\u20B9 ${b.ed_charge.toFixed(2)}`;
    document.getElementById('compNetB').innerHTML = `\u20B9 ${b.rounded_bill.toLocaleString('en-IN')}`;
    const dailyB = daysB > 0 ? (b.rounded_bill / daysB) : 0;
    document.getElementById('compDailyB').innerHTML = `\u20B9 ${dailyB.toFixed(2)}/day`;

    // Variance summary
    const diffNet = b.rounded_bill - a.rounded_bill;
    const sign = diffNet >= 0 ? '+' : '-';
    document.getElementById('compDiffNet').innerHTML = `${sign}\u20B9 ${Math.abs(diffNet).toLocaleString('en-IN')}`;
    
    const dailyDiff = dailyB - dailyA;
    const dailyPct = dailyA > 0 ? ((dailyDiff / dailyA) * 100) : 0;
    const badge = document.getElementById('compDailyDeltaBadge');
    
    if (Math.abs(dailyPct) < 0.1) {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300";
      badge.innerText = `Equal Daily Rate (\u20B9 ${dailyB.toFixed(2)}/d)`;
    } else if (dailyDiff > 0) {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300";
      badge.innerText = `+${dailyPct.toFixed(1)}% daily avg (+ \u20B9 ${dailyDiff.toFixed(2)}/d)`;
    } else {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300";
      badge.innerText = `${dailyPct.toFixed(1)}% daily avg (- \u20B9 ${Math.abs(dailyDiff).toFixed(2)}/d)`;
    }

    document.getElementById('compDiffTitle').innerText = `Diff: ${daysB} Days (\u20B9 ${b.rounded_bill.toLocaleString('en-IN')}) vs ${daysA} Days (\u20B9 ${a.rounded_bill.toLocaleString('en-IN')})`;
    document.getElementById('compDiffSubtitle').innerText = `Slab multipliers: ${a.months_multiplier} vs ${b.months_multiplier} mo | Monthly equivalent: \u20B9 ${(dailyA * 30).toFixed(0)} vs \u20B9 ${(dailyB * 30).toFixed(0)}/mo`;
  }
}
window.runDaysComparison = runDaysComparison;

// --- Theft Calculations ---
function formatDecimalHours(h) {
  const totalMinutes = Math.max(0, Math.min(24 * 60, Math.round(h * 60)));
  const hrs = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return `(${String(hrs).padStart(2, '0')}h ${String(mins).padStart(2, '0')}m)`;
}

let latestTheftRes = null;

function validateHoursAndRun(inputEl) {
  let val = parseFloat(inputEl.value);
  if (isNaN(val)) val = 0;
  if (val > 24) {
    inputEl.value = 24;
  } else if (val < 0) {
    inputEl.value = 0;
  }
  runTheftCalc();
}
window.validateHoursAndRun = validateHoursAndRun;

async function runTheftCalc() {
  let provHours = parseFloat(document.getElementById('theftProvHours').value || 24);
  let finalHours = parseFloat(document.getElementById('theftFinalHours').value || 19);

  if (provHours > 24) { provHours = 24; document.getElementById('theftProvHours').value = 24; }
  if (finalHours > 24) { finalHours = 24; document.getElementById('theftFinalHours').value = 24; }

  const provHoursLabel = document.getElementById('provHoursLabel');
  if (provHoursLabel) provHoursLabel.innerText = formatDecimalHours(provHours);
  const finalHoursLabel = document.getElementById('finalHoursLabel');
  if (finalHoursLabel) finalHoursLabel.innerText = formatDecimalHours(finalHours);

  const payload = {
    category: document.getElementById('theftCategory').value,
    consumer_type: document.getElementById('theftConsumerType').value,
    load: parseFloat(document.getElementById('theftLoad').value || 1.5),
    load_unit: document.getElementById('theftLoadUnit').value,
    days_prov: parseInt(document.getElementById('theftProvDays').value || 365),
    days_final: parseInt(document.getElementById('theftFinalDays').value || 365),
    prov_hours: provHours,
    final_hours: finalHours,
    adj_energy: parseFloat(document.getElementById('theftAdjEnergy').value || 0),
    adj_fixed: parseFloat(document.getElementById('theftAdjFixed').value || 0),
    adj_ed: parseFloat(document.getElementById('theftAdjEd').value || 0)
  };

  const isNonConsumer = payload.consumer_type === 'Non-Consumer';
  if (isNonConsumer) {
    document.getElementById('theftAdjEnergy').disabled = true;
    document.getElementById('theftAdjFixed').disabled = true;
    document.getElementById('theftAdjEd').disabled = true;
  } else {
    document.getElementById('theftAdjEnergy').disabled = false;
    document.getElementById('theftAdjFixed').disabled = false;
    document.getElementById('theftAdjEd').disabled = false;
  }

  const res = await callAPI('calculate_theft_dual', payload);
  if (res && res.success) {
    latestTheftRes = res;
    const p = res.provisional || res.prov;
    document.getElementById('provUnits').innerText = `${p.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('provEnergy').innerHTML = `\u20B9 ${p.penal_energy_charge.toFixed(2)}`;
    document.getElementById('provFixed').innerHTML = `\u20B9 ${p.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('provEd').innerHTML = `\u20B9 ${p.electricity_duty.toFixed(2)}`;
    document.getElementById('provGross').innerHTML = `\u20B9 ${p.gross_assessment.toFixed(2)}`;
    document.getElementById('provAdj').innerHTML = `- \u20B9 ${p.total_adjustments.toFixed(2)}`;
    const pRounded = Math.ceil(p.net_assessment !== undefined ? p.net_assessment : p.net);
    document.getElementById('provNet').innerHTML = `\u20B9 ${pRounded.toLocaleString('en-IN')}`;

    const f = res.final;
    document.getElementById('finalUnits').innerText = `${f.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('finalEnergy').innerHTML = `\u20B9 ${f.penal_energy_charge.toFixed(2)}`;
    document.getElementById('finalFixed').innerHTML = `\u20B9 ${f.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('finalEd').innerHTML = `\u20B9 ${f.electricity_duty.toFixed(2)}`;
    document.getElementById('finalGross').innerHTML = `\u20B9 ${f.gross_assessment.toFixed(2)}`;
    document.getElementById('finalAdj').innerHTML = `- \u20B9 ${f.total_adjustments.toFixed(2)}`;
    const fRounded = Math.ceil(f.net_assessment !== undefined ? f.net_assessment : f.net);
    document.getElementById('finalNet').innerHTML = `\u20B9 ${fRounded.toLocaleString('en-IN')}`;

    const rel = res.relief || { diff_rs: res.diff_rs || 0, diff_pct: res.diff_pct || 0 };
    const rb = document.getElementById('reliefBar');
    if (rb) {
      rb.innerHTML = `Final Assessment Relief: \u20B9 ${rel.diff_rs.toFixed(2)} (${rel.diff_pct.toFixed(2)}%)`;
      if (rel.diff_pct > 25) {
        rb.className = "mt-2.5 p-2.5 rounded-lg bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 text-xs font-semibold text-center border border-rose-200 dark:border-rose-800/50";
      } else {
        rb.className = "mt-2.5 p-2.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-semibold text-center border border-emerald-200 dark:border-emerald-800/50";
      }
    }

    updateTheftFormulaBreakdown(p.breakdown || {});
  }
}

function updateTheftFormulaBreakdown(b) {
  if (!b || !b.units) return;
  const unitsTrace = document.getElementById('breakdownUnitsCalc');
  if (unitsTrace) {
    unitsTrace.innerHTML = `<b>Calculation:</b> ${b.load_kva} kVA × 0.85 PF × ${b.lf} LF × ${b.days} Days × ${b.hours} Hrs = <b>${b.units.toLocaleString('en-IN')} Units</b> (${b.units_per_month} units/mo over ${b.months} months)`;
  }

  const energyTrace = document.getElementById('breakdownEnergyCalc');
  if (energyTrace) {
    energyTrace.innerHTML = `<b>Calculation:</b> \u20B9 ${b.normal_monthly_energy.toFixed(2)} / month × ${b.months} months = \u20B9 ${b.normal_total_energy.toFixed(2)} normal × 2 = <b>\u20B9 ${b.penal_energy.toFixed(2)}</b>`;
  }

  const fixedTrace = document.getElementById('breakdownFixedCalc');
  if (fixedTrace) {
    fixedTrace.innerHTML = `<b>Calculation:</b> ${b.rounded_load} kVA × \u20B9 ${b.fixed_rate}/mo × ${b.rounded_months} billing months = \u20B9 ${b.normal_fc.toFixed(2)} normal × 2 = <b>\u20B9 ${b.penal_fc.toFixed(2)}</b>`;
  }

  const edTrace = document.getElementById('breakdownEdCalc');
  if (edTrace) {
    edTrace.innerHTML = `<b>Calculation:</b> (\u20B9 ${b.penal_energy.toFixed(2)} energy + \u20B9 ${b.penal_fc.toFixed(2)} fixed) × ${b.ed_percent}% = <b>\u20B9 ${b.ed_amount.toFixed(2)}</b>`;
  }
}

function toggleTheftBreakdownModal(show) {
  const modal = document.getElementById('theftBreakdownModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    if (latestTheftRes && latestTheftRes.prov && latestTheftRes.prov.breakdown) {
      updateTheftFormulaBreakdown(latestTheftRes.prov.breakdown);
    }
  } else {
    modal.classList.add('hidden');
  }
  lucide.createIcons();
}
window.toggleTheftBreakdownModal = toggleTheftBreakdownModal;

let estimatedLoadKva = 0;
function toggleReverseLoadModal(show) {
  const modal = document.getElementById('reverseLoadModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    // Pre-fill with current days/hours from theft screen if empty
    const theftHours = document.getElementById('theftProvHours');
    if (theftHours && theftHours.value) {
      document.getElementById('revHours').value = Math.min(24, parseFloat(theftHours.value));
    }
  } else {
    modal.classList.add('hidden');
  }
  lucide.createIcons();
}
window.toggleReverseLoadModal = toggleReverseLoadModal;

async function calculateReverseLoad() {
  const targetAmount = parseFloat(document.getElementById('revTargetAmount').value || 0);
  if (targetAmount <= 0) {
    showToast('Please enter an assessment amount greater than 0', 'warning');
    return;
  }

  let hours = parseFloat(document.getElementById('revHours').value || 24);
  if (hours > 24) { hours = 24; document.getElementById('revHours').value = 24; }
  const days = parseInt(document.getElementById('revDays').value || 365);

  const payload = {
    target_amount: targetAmount,
    hours: hours,
    days: days,
    category: document.getElementById('theftCategory').value,
    consumer_type: document.getElementById('theftConsumerType').value,
    adj_energy: parseFloat(document.getElementById('theftAdjEnergy').value || 0),
    adj_fixed: parseFloat(document.getElementById('theftAdjFixed').value || 0),
    adj_ed: parseFloat(document.getElementById('theftAdjEd').value || 0)
  };

  const res = await callAPI('calculate_theft_reverse_load', payload);
  if (res && res.success) {
    estimatedLoadKva = res.load_kva;
    document.getElementById('revLoadKva').innerText = `${res.load_kva.toFixed(2)} kVA`;
    document.getElementById('revLoadKw').innerText = `(${res.load_kw.toFixed(2)} kW @ 0.85 PF)`;
    document.getElementById('revGross').innerText = `\u20B9 ${Math.round(res.resulting_gross).toLocaleString('en-IN')}`;
    document.getElementById('revUnits').innerText = `${res.assessed_units.toLocaleString('en-IN')} kWh`;
    showToast(`Estimated Load: ${res.load_kva.toFixed(2)} kVA (${res.load_kw.toFixed(2)} kW)`, 'success');
  } else {
    showToast(res ? res.error : 'Failed to calculate load', 'error');
  }
}
window.calculateReverseLoad = calculateReverseLoad;

function applyEstimatedLoadToTheft() {
  if (estimatedLoadKva <= 0) {
    showToast('Please calculate an estimated load first', 'warning');
    return;
  }
  document.getElementById('theftLoad').value = estimatedLoadKva.toFixed(2);
  document.getElementById('theftLoadUnit').value = 'kVA';
  toggleReverseLoadModal(false);
  runTheftCalc();
  showToast(`Applied ${estimatedLoadKva.toFixed(2)} kVA to Connected Load`, 'success');
}
window.applyEstimatedLoadToTheft = applyEstimatedLoadToTheft;

// --- Settings Two-Column Navigation ---
function switchSettingsSection(sectionId) {
  // Hide all panels
  document.querySelectorAll('.settings-pane').forEach(el => el.classList.add('hidden'));

  // Reset all nav buttons
  document.querySelectorAll('.settings-nav-btn').forEach(btn => {
    btn.className = "settings-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800/60 border border-transparent transition text-left";
  });

  // Activate target panel
  const targetPane = document.getElementById(`setPane-${sectionId}`);
  if (targetPane) targetPane.classList.remove('hidden');

  // Activate target nav button
  const targetNav = document.getElementById(`setNav-${sectionId}`);
  if (targetNav) {
    targetNav.className = "settings-nav-btn w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/50 border border-sky-200 dark:border-sky-800/60 transition text-left";
  }

  if (sectionId === 'update') {
    triggerUpdateCheck();
  }

  lucide.createIcons();
}
window.switchSettingsSection = switchSettingsSection;

function handleUpdateBadgeClick() {
  switchTab('settings');
  switchSettingsSection('update');
}
window.handleUpdateBadgeClick = handleUpdateBadgeClick;

// --- Appearance & Font Switching ---
function setAppFont(fontName) {
  document.documentElement.style.setProperty('--app-font', fontName);
  try {
    localStorage.setItem('siv_selected_font', fontName);
  } catch (e) {}

  // Update font selector cards
  document.querySelectorAll('.font-card').forEach(card => {
    const isTarget = card.dataset.font === fontName;
    const badge = card.querySelector('.font-badge');
    if (badge) badge.classList.toggle('hidden', !isTarget);
    card.classList.toggle('border-sky-500', isTarget);
    card.classList.toggle('bg-sky-50/20', isTarget);
    card.classList.toggle('dark:bg-sky-500/10', isTarget);
  });
}

function initAppFont() {
  try {
    const saved = localStorage.getItem('siv_selected_font') || 'Plus Jakarta Sans';
    setAppFont(saved);
  } catch (e) {
    setAppFont('Plus Jakarta Sans');
  }
}
window.setAppFont = setAppFont;

// --- Tariff Editor ---
function renderTariffEditorList() {
  const container = document.getElementById('tariffList');
  container.innerHTML = '';
  Object.keys(currentTariffs).forEach(cat => {
    const div = document.createElement('div');
    div.className = "p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800";
    div.innerText = cat;
    div.onclick = () => loadTariffForEdit(cat);
    container.appendChild(div);
  });
}

function loadTariffForEdit(cat) {
  const data = currentTariffs[cat];
  if (!data) return;
  const editor = document.getElementById('tariffEditor');
  editor.innerHTML = `
    <div class="flex justify-between items-center">
      <h3 class="text-md font-bold text-slate-900 dark:text-slate-100">${cat}</h3>
      <button onclick="saveTariffs()" class="bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs hover:bg-emerald-500">Save Changes</button>
    </div>
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="text-xs text-slate-600 dark:text-slate-400">Fixed Charge</label>
        <input type="number" id="editFC" value="${data.fixed_charge}" class="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg text-sm p-2" onchange="updateTariffData('${cat}', 'fixed_charge', this.value)">
      </div>
      <div>
        <label class="text-xs text-slate-600 dark:text-slate-400">Min Charge</label>
        <input type="number" id="editMin" value="${data.min_charge || 0}" class="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg text-sm p-2" onchange="updateTariffData('${cat}', 'min_charge', this.value)">
      </div>
    </div>
    <p class="text-xs text-slate-500 mt-2">Energy Slabs and ED slabs can be edited by modifying the backend JSON directly for now.</p>
  `;
}

function updateTariffData(cat, field, value) {
  currentTariffs[cat][field] = parseFloat(value);
}

async function saveTariffs() {
  const res = await callAPI('save_tariff_data', currentTariffs);
  if (res && res.success) alert("Tariffs saved!");
  else alert("Failed to save tariffs");
}

// --- Settings & Software Update ---
let updatePollTimer = null;

function renderUpdateCard(res) {
  const box = document.getElementById('updateStatusBox');
  if (!box) return;

  if (res && res.success) {
    if (res.has_update) {
      const installerUrl = res.installer_url || res.download_url || '';
      box.className = "p-5 rounded-2xl border border-emerald-300 dark:border-emerald-500/30 bg-emerald-50/70 dark:bg-emerald-950/20 text-slate-800 dark:text-slate-100 text-xs space-y-4 shadow-sm";
      box.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <span class="px-2.5 py-0.5 rounded-md bg-emerald-500/20 border border-emerald-500/40 text-emerald-700 dark:text-emerald-300 font-bold text-xs uppercase tracking-wide">
                Update Available
              </span>
              <span class="font-bold text-sm text-slate-900 dark:text-white">v${res.latest_version}</span>
            </div>
            <p class="text-[11px] text-slate-500 dark:text-slate-400">Current installed: <span class="font-semibold text-slate-700 dark:text-slate-300">v${res.current_version}</span></p>
          </div>
          <div class="w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <i data-lucide="arrow-down-circle" class="w-5 h-5"></i>
          </div>
        </div>

        <div class="bg-white/90 dark:bg-slate-900/90 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-inner">
          <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">What's New in v${res.latest_version}</span>
          <div class="max-h-48 overflow-y-auto whitespace-pre-line text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-sans pr-2">
            ${escapeHtml(res.release_notes || 'Stability enhancements and performance updates.')}
          </div>
        </div>

        <div id="updateActionContainer" class="flex flex-wrap items-center gap-2.5 pt-1">
          <button id="btnStartInstallUpdate" onclick="startAppUpdate('${installerUrl}')" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow-md hover:shadow-lg transition-all flex items-center gap-2 cursor-pointer active:scale-95">
            <i data-lucide="download" class="w-4 h-4"></i> Download & Install Update
          </button>
          ${installerUrl ? `
            <button onclick="callAPI('open_url_external', '${installerUrl}')" class="bg-slate-200/80 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold px-4 py-2.5 rounded-xl transition flex items-center gap-1.5 cursor-pointer">
              <i data-lucide="external-link" class="w-3.5 h-3.5"></i> Download in Browser
            </button>
          ` : ''}
        </div>

        <div id="updateProgressBox" class="hidden space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
          <div class="flex items-center justify-between text-xs">
            <span id="updateProgressStatus" class="font-semibold text-emerald-700 dark:text-emerald-400">Downloading update installer...</span>
            <span id="updateProgressPct" class="font-mono font-bold text-slate-800 dark:text-slate-200">0%</span>
          </div>
          <div class="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <div id="updateProgressBar" class="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-200 w-0"></div>
          </div>
          <p id="updateProgressSub" class="text-[11px] text-slate-400 italic">Please wait while the update installer is downloaded...</p>
        </div>
      `;
    } else {
      box.className = "p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-900/60 text-slate-700 dark:text-slate-300 text-xs space-y-1.5 shadow-sm";
      box.innerHTML = `
        <div class="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold">
          <i data-lucide="check-circle" class="w-4 h-4"></i>
          <span>You are running the latest version (v${res.current_version})</span>
        </div>
        <p class="text-[11px] text-slate-500 pl-6">Spot Image Viewer is completely up to date. No new updates available.</p>
      `;
    }
  } else {
    box.className = "p-4 rounded-xl border border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs space-y-2 shadow-sm";
    box.innerHTML = `
      <div class="flex items-center gap-2 font-bold">
        <i data-lucide="alert-circle" class="w-4 h-4"></i>
        <span>Update check failed</span>
      </div>
      <p class="text-[11px]">${escapeHtml(res ? (res.error || "Unable to reach update server.") : "Failed to check update.")}</p>
      <button onclick="triggerUpdateCheck()" class="mt-1 bg-rose-600 hover:bg-rose-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition inline-flex items-center gap-1 cursor-pointer">
        <i data-lucide="refresh-cw" class="w-3 h-3"></i> Retry
      </button>
    `;
  }
  lucide.createIcons();
}

async function triggerUpdateCheck() {
  const box = document.getElementById('updateStatusBox');
  if (!box) return;
  box.classList.remove('hidden');

  // If already fetched during silent check and has update, show it immediately first
  if (latestUpdateInfo && latestUpdateInfo.has_update) {
    renderUpdateCard(latestUpdateInfo);
  } else {
    box.className = "p-4 rounded-xl border border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs flex items-center gap-3";
    box.innerHTML = `
      <div class="w-4 h-4 border-2 border-sky-600 dark:border-sky-400 border-t-transparent rounded-full animate-spin shrink-0"></div>
      <span>Checking for updates from GitHub releases...</span>
    `;
  }

  const res = await callAPI('check_for_updates');
  if (res && res.success) {
    latestUpdateInfo = res;
    const badge = document.getElementById('statusUpdateBadge');
    const text = document.getElementById('statusUpdateText');
    if (res.has_update) {
      if (badge) {
        badge.classList.remove('hidden');
        badge.classList.add('flex');
      }
      if (text) text.innerText = `Update Available (v${res.latest_version})`;
    } else {
      if (badge) {
        badge.classList.add('hidden');
        badge.classList.remove('flex');
      }
    }
  }
  renderUpdateCard(res);
}
window.triggerUpdateCheck = triggerUpdateCheck;

async function startAppUpdate(installerUrl) {
  const btn = document.getElementById('btnStartInstallUpdate');
  const progBox = document.getElementById('updateProgressBox');
  const progStatus = document.getElementById('updateProgressStatus');
  const progPct = document.getElementById('updateProgressPct');
  const progBar = document.getElementById('updateProgressBar');
  const progSub = document.getElementById('updateProgressSub');

  if (btn) {
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Initializing Download...`;
  }
  if (progBox) progBox.classList.remove('hidden');
  lucide.createIcons();

  const res = await callAPI('start_self_update', installerUrl);
  if (!res || !res.success) {
    if (progStatus) {
      progStatus.innerText = "Download failed to start";
      progStatus.className = "font-semibold text-rose-600 dark:text-rose-400";
    }
    if (progSub) progSub.innerText = res ? res.error : "Unknown error";
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('opacity-50', 'cursor-not-allowed');
      btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> Retry Update`;
    }
    lucide.createIcons();
    return;
  }

  if (updatePollTimer) clearInterval(updatePollTimer);
  updatePollTimer = setInterval(async () => {
    const prog = await callAPI('get_update_progress');
    if (!prog) return;

    if (prog.status === 'downloading') {
      const pct = prog.percent || 0;
      const dlMB = (prog.downloaded / (1024 * 1024)).toFixed(1);
      const totMB = prog.total ? (prog.total / (1024 * 1024)).toFixed(1) : '?';
      if (progBar) progBar.style.width = `${pct}%`;
      if (progPct) progPct.innerText = `${pct}%`;
      if (progStatus) progStatus.innerText = `Downloading Update: ${dlMB} MB / ${totMB} MB (${pct}%)`;
      if (progSub) progSub.innerText = `Downloading latest installer package from GitHub...`;
    } else if (prog.status === 'ready') {
      clearInterval(updatePollTimer);
      if (progBar) progBar.style.width = '100%';
      if (progPct) progPct.innerText = '100%';
      if (progStatus) {
        progStatus.innerText = "Download complete!";
        progStatus.className = "font-bold text-emerald-600 dark:text-emerald-400 text-sm";
      }
      if (progSub) {
        progSub.innerText = "Launching Windows Setup installer... Spot Image Viewer will close in a moment.";
        progSub.className = "text-xs font-semibold text-slate-700 dark:text-slate-200 animate-pulse";
      }
      if (btn) {
        btn.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4"></i> Launching Installer...`;
      }
      lucide.createIcons();

      // Close and exit to allow installer to execute
      setTimeout(async () => {
        await callAPI('exit_for_update');
      }, 1500);
    } else if (prog.status === 'error') {
      clearInterval(updatePollTimer);
      if (progStatus) {
        progStatus.innerText = "Download Failed";
        progStatus.className = "font-semibold text-rose-600 dark:text-rose-400";
      }
      if (progSub) progSub.innerText = prog.error || "Failed to download update installer.";
      if (btn) {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> Retry Update`;
      }
      lucide.createIcons();
    }
  }, 250);
}
window.startAppUpdate = startAppUpdate;

function renderFolders(folders) {
  if (!folders) return;

  const c1 = document.getElementById('folderList');
  const c2 = document.getElementById('topbarFolderList');

  if (c1) c1.innerHTML = '';
  if (c2) c2.innerHTML = '';

  if (folders.length === 0) {
    const emptyMsg = '<p class="text-xs text-slate-400 italic py-2 text-center">No image directories registered.</p>';
    if (c1) c1.innerHTML = emptyMsg;
    if (c2) c2.innerHTML = emptyMsg;
    return;
  }

  folders.forEach(f => {
    const path = typeof f === 'string' ? f : (f.path || "");
    const isAccessible = typeof f === 'object' && f.accessible !== undefined ? f.accessible : true;
    const isPrimary = typeof f === 'object' && f.is_primary !== undefined ? f.is_primary : false;

    if (!path) return;

    // Render for Settings Tab
    if (c1) {
      const div1 = document.createElement('div');
      div1.className = "flex items-center justify-between bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 transition";
      div1.innerHTML = `
        <div class="flex items-center gap-2.5 min-w-0 pr-2">
          <span class="w-2 h-2 rounded-full shrink-0 ${isAccessible ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-rose-500'}" title="${isAccessible ? 'Online & Accessible' : 'Folder Not Found / Offline'}"></span>
          <div class="min-w-0">
            <span class="text-xs text-slate-800 dark:text-slate-200 truncate block font-medium" title="${path}">${path}</span>
            ${isPrimary ? '<span class="text-[10px] text-sky-600 dark:text-sky-400 font-semibold block leading-none">Primary Root Folder</span>' : ''}
          </div>
        </div>
        ${!isPrimary ? `
          <button onclick="removeFolder('${path.replace(/\\/g, '\\\\')}')" class="text-slate-400 hover:text-rose-500 p-1 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 transition shrink-0" title="Remove Folder">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        ` : '<span class="text-[10px] text-slate-400 font-mono shrink-0 px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">Fixed</span>'}
      `;
      c1.appendChild(div1);
    }

    // Render for Topbar Popover
    if (c2) {
      const div2 = document.createElement('div');
      div2.className = "flex items-center justify-between p-2 rounded-lg transition" +
                       " style='background: var(--surface-1); border: 1px solid var(--border);'";
      div2.innerHTML = `
        <div class="flex items-center gap-2 min-w-0 pr-2">
          <span class="w-2 h-2 rounded-full shrink-0 ${isAccessible ? 'bg-emerald-500' : 'bg-rose-500'}" title="${isAccessible ? 'Accessible' : 'Unavailable'}"></span>
          <div class="min-w-0">
            <span class="text-xs truncate block font-medium" style="color: var(--text);" title="${path}">${path}</span>
            ${isPrimary ? '<span class="text-[10px] text-sky-500 font-semibold block leading-none">Primary Folder</span>' : ''}
          </div>
        </div>
        ${!isPrimary ? `
          <button onclick="removeFolder('${path.replace(/\\/g, '\\\\')}')" class="text-slate-400 hover:text-rose-500 p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition shrink-0" title="Remove Folder">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        ` : '<span class="text-[10px] text-slate-400 font-mono px-1 py-0.5 rounded border border-slate-300 dark:border-slate-700">Root</span>'}
      `;
      c2.appendChild(div2);
    }
  });

  lucide.createIcons();
}

async function addFolder() {
  const res = await callAPI('add_network_folder');
  if (res && res.success) {
    await initApp(); // reload folder list & status
  } else if (res && res.error) {
    alert("Failed to add folder: " + res.error);
  }
}

async function removeFolder(p) {
  if (confirm(`Remove folder ${p}?`)) {
    await callAPI('remove_network_folder', p);
    initApp();
  }
}

let indexingPollTimer = null;

async function startIndexing() {
  const icon = document.getElementById('reloadIndexIcon');
  const prog = document.getElementById('indexProgress');
  const topBadge = document.getElementById('topIndexStatusBadge');
  const topText = document.getElementById('topIndexStatusText');
  const topTimeline = document.getElementById('topIndexTimeline');
  const topTimelineBar = document.getElementById('topIndexTimelineBar');

  if (icon) icon.classList.add('animate-spin');
  if (prog) prog.classList.remove('hidden');
  if (topBadge) {
    topBadge.classList.remove('hidden');
    topBadge.classList.add('flex');
    if (topText) topText.innerText = 'Scanning...';
  }
  if (topTimeline) topTimeline.classList.remove('hidden');
  if (topTimelineBar) topTimelineBar.style.width = '15%';
  updateStatusBar("Scanning image folders for spot bills...", "loading", 15);

  const res = await callAPI('start_indexing');
  if (!res || !res.success) {
    if (icon) icon.classList.remove('animate-spin');
    if (prog) prog.classList.add('hidden');
    if (topBadge) {
      topBadge.classList.add('hidden');
      topBadge.classList.remove('flex');
    }
    if (topTimeline) topTimeline.classList.add('hidden');
    updateStatusBar("Indexing failed to start.", "error");
    alert("Failed to start indexing: " + (res ? res.error : "Unknown error"));
    return;
  }

  // Poll indexing status until finished
  if (indexingPollTimer) clearInterval(indexingPollTimer);
  indexingPollTimer = setInterval(async () => {
    const stat = await callAPI('get_indexing_status');
    if (!stat) return;

    const count = stat.scanned || stat.total || 0;
    const elapsed = stat.elapsed || 0;
    const speed = stat.speed || 0;
    const folder = stat.current_folder || '';
    const filesSeen = stat.files_seen || 0;

    let statusStr = "";
    let badgeStr = "";

    if (count > 0) {
      const speedStr = speed > 0 ? ` • ${speed.toLocaleString()} img/s` : '';
      statusStr = `Indexing: ${count.toLocaleString()} images (${elapsed}s${speedStr}) ${folder ? '[' + folder + ']' : ''}`;
      badgeStr = `${count.toLocaleString()} imgs (${elapsed}s${speed > 0 ? ' • ' + speed + '/s' : ''})`;
    } else if (filesSeen > 0) {
      statusStr = `Scanning: ${filesSeen.toLocaleString()} files inspected (${elapsed}s)...`;
      badgeStr = `Scanning (${filesSeen.toLocaleString()} files)...`;
    } else {
      statusStr = `Scanning directories... (${elapsed}s) ${folder ? '[' + folder + ']' : ''}`;
      badgeStr = `Scanning... (${elapsed}s)`;
    }

    if (topText) {
      topText.innerText = badgeStr;
    }

    // Dynamic progress bar percentage: animate smoothly across time
    const dynamicPct = count > 0 
      ? Math.min(95, 20 + Math.floor(Math.log10(count + 1) * 15)) 
      : Math.min(45, 10 + (elapsed * 2));

    if (topTimelineBar) {
      topTimelineBar.style.width = `${dynamicPct}%`;
    }
    updateStatusBar(statusStr, "loading", `${dynamicPct}%`);

    if (!stat.running) {
      clearInterval(indexingPollTimer);
      indexingPollTimer = null;

      if (topTimelineBar) topTimelineBar.style.width = '100%';
      const finalSpeed = speed > 0 ? ` @ ${speed.toLocaleString()} img/s` : '';
      updateStatusBar(`Indexing complete: ${count.toLocaleString()} images cataloged in ${elapsed}s${finalSpeed}`, "normal", 100);

      // Immediately stop spin and reset indicators
      if (icon) icon.classList.remove('animate-spin');
      if (prog) prog.classList.add('hidden');
      if (topBadge) {
        topBadge.classList.add('hidden');
        topBadge.classList.remove('flex');
      }
      setTimeout(() => {
        if (topTimeline) topTimeline.classList.add('hidden');
        if (topTimelineBar) topTimelineBar.style.width = '0%';
        updateStatusBar("Ready", "normal");
      }, 3000);

      await initApp();
      if (stat.error) {
        alert(`Image indexing encountered an error:\n${stat.error}`);
      } else {
        alert(`Image re-indexing complete!\n\nIndexed: ${count.toLocaleString()} images\nElapsed Time: ${elapsed}s\nAverage Speed: ${speed > 0 ? speed.toLocaleString() + ' images/sec' : 'N/A'}`);
      }
    }
  }, 350);
}

async function exportNotes() {
  const res = await callAPI('export_notes_csv');
  if (res && res.success) {
    showFileActionModal({
      title: "Notes Exported",
      subtitle: "CSV report ready",
      msg: "Your consumer inspection remarks have been saved. Would you like to open the CSV now?",
      filePath: res.path,
      icon: "download",
      btnText: "Open CSV"
    });
  } else if (res && res.error) {
    alert("Failed to export notes: " + res.error);
  }
}

// --- Image Check GUI ---
async function launchImageCheckGUI() {
  const res = await callAPI('launch_image_check_gui');
  if (res && res.success) {
    alert(res.message || "Image Check GUI launched successfully.");
  } else {
    alert("Failed to launch Image Check GUI: " + (res ? res.error : "Unknown error"));
  }
}

// --- Action Target Modal (Open Downloaded Template / File) ---
let currentActionTargetFile = "";

function showFileActionModal(opts) {
  currentActionTargetFile = opts.filePath || "";
  const modal = document.getElementById('fileActionModal');
  const titleEl = document.getElementById('fileActionTitle');
  const subEl = document.getElementById('fileActionSub');
  const msgEl = document.getElementById('fileActionMsg');
  const pathTextEl = document.getElementById('fileActionPathText');
  const pathBoxEl = document.getElementById('fileActionPathBox');
  const btnOpen = document.getElementById('btnOpenFileAction');

  if (titleEl) titleEl.innerText = opts.title || "File Ready";
  if (subEl) subEl.innerText = opts.subtitle || "Action complete";
  if (msgEl) msgEl.innerText = opts.msg || "Would you like to open the file now?";
  if (btnOpen && opts.btnText) btnOpen.innerHTML = `<i data-lucide="external-link" class="w-3.5 h-3.5"></i> ${opts.btnText}`;

  if (pathTextEl && pathBoxEl) {
    if (currentActionTargetFile) {
      pathBoxEl.classList.remove('hidden');
      pathTextEl.innerText = currentActionTargetFile;
    } else {
      pathBoxEl.classList.add('hidden');
    }
  }

  if (modal) {
    modal.classList.remove('hidden');
    lucide.createIcons();
  }
}

function closeFileActionModal() {
  const modal = document.getElementById('fileActionModal');
  if (modal) modal.classList.add('hidden');
}

async function openActionTargetFile() {
  if (currentActionTargetFile) {
    await callAPI('open_file_external', currentActionTargetFile);
  }
  closeFileActionModal();
}

window.showFileActionModal = showFileActionModal;
window.closeFileActionModal = closeFileActionModal;
window.openActionTargetFile = openActionTargetFile;

// --- Consumer Data Management ---
async function generateConsumerTemplate() {
  const res = await callAPI('generate_consumer_template');
  if (res && res.success) {
    // Show sleek action popup that asks to open the file
    showFileActionModal({
      title: "Template Created",
      subtitle: "Excel template saved",
      msg: "Blank consumer data template has been created. Would you like to open it now?",
      filePath: res.path,
      icon: "file-spreadsheet",
      btnText: "Open Template"
    });
  } else if (res && res.error) {
    alert("Failed to generate template: " + res.error);
  }
}

async function importConsumerData() {
  const res = await callAPI('import_consumer_data');
  if (res && res.success) {
    initApp();

    showFileActionModal({
      title: "Consumer Data Imported",
      subtitle: "SQLite cache updated",
      msg: `Successfully imported ${res.count.toLocaleString()} consumer records. Would you like to view the source file?`,
      filePath: res.file_path || "",
      icon: "check-circle",
      btnText: "Open Source Excel"
    });
  } else if (res && res.error) {
    alert("Failed to import consumer data: " + res.error);
  }
}

function closeImportConfirmModal() {
  const confirmModal = document.getElementById('importConfirmModal');
  if (confirmModal) confirmModal.classList.add('hidden');
}

async function openImportedSourceFile() {
  if (lastImportedFilePath) {
    await callAPI('open_file_external', lastImportedFilePath);
  }
  closeImportConfirmModal();
}

async function openSavedConsumerData() {
  const res = await callAPI('export_consumer_data_file');
  if (res && res.success) {
    // Automatically exported and opened via backend
  } else if (res && res.error) {
    alert("Failed to export/open consumer data: " + res.error);
  }
}

window.openSavedConsumerData = openSavedConsumerData;
window.closeImportConfirmModal = closeImportConfirmModal;
window.openImportedSourceFile = openImportedSourceFile;

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
  lucide.createIcons();
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

  lucide.createIcons();
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
    lucide.createIcons();
  }

  const t0 = performance.now();
  const res = await callAPI('lookup_fuzzy_rows', validRows, threshold, topN);
  const elapsedMs = Math.round(performance.now() - t0);

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="search" class="w-3.5 h-3.5"></i><span>Find Matches</span>`;
    lucide.createIcons();
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
    lucide.createIcons();
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

  lucide.createIcons();
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
  lucide.createIcons();

  try {
    const res = await callAPI('get_live_osd', cid);
    if (!res || !res.success || !res.data) {
      cell.innerHTML = `
        <button onclick="fetchCandidateLiveOsd('${cid}', ${qIdx}, ${cIdx})" class="px-1.5 py-0.5 rounded text-[9.5px] font-semibold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition" title="${escapeHtml(res ? res.error : 'Retry')}">
          Failed ↻
        </button>
      `;
      return;
    }

    const d = res.data;
    let statusClass = "text-slate-500";
    if (d.isLive) statusClass = "text-emerald-600 dark:text-emerald-400 font-bold";
    else if (d.isDeemed) statusClass = "text-amber-600 dark:text-amber-400 font-bold";
    else if (d.isDisconnected) statusClass = "text-rose-600 dark:text-rose-400 font-bold";

    const totalFmt = Number(d.totalDues || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const duesClass = (d.totalDues > 0) ? "text-amber-600 dark:text-amber-400 font-bold" : "text-emerald-600 dark:text-emerald-400 font-medium";

    cell.innerHTML = `
      <div class="text-left py-0.5 leading-tight">
        <div class="font-mono text-[10.5px] ${duesClass}">\u20B9 ${totalFmt}</div>
        <div class="text-[9px] ${statusClass} flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full ${d.isLive ? 'bg-emerald-500' : (d.isDeemed ? 'bg-amber-500' : 'bg-rose-500')}"></span>
          <span>${escapeHtml(d.connectionStatus || 'LIVE')}</span>
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
  lucide.createIcons();
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
  lucide.createIcons();
}

function toggleAuditGuideModal(show = true) {
  const modal = document.getElementById('auditGuideModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
  } else {
    modal.classList.add('hidden');
  }
  lucide.createIcons();
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
    lucide.createIcons();
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

  lucide.createIcons();
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
    lucide.createIcons();
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

    (async () => {
      const thumb = await callAPI('get_image_data', img.full_path, 400);
      const loader = document.getElementById(`audit-img-loader-${idx}`);
      const imgEl = document.getElementById(`audit-img-${idx}`);
      if (loader) loader.classList.add('hidden');
      if (imgEl && thumb && thumb.success) {
        imgEl.src = thumb.data;
        imgEl.classList.remove('hidden');
      }
    })();
  });

  lucide.createIcons();
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
  lucide.createIcons();
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

// --- Status Bar Helpers ---
function updateStatusBar(msg, type = "normal", progress = null) {
  const msgEl = document.getElementById('statusMessage');
  const dotEl = document.getElementById('statusDot');
  const badgeEl = document.getElementById('statusProgressBadge');
  const textEl = document.getElementById('statusProgressText');
  const trackEl = document.getElementById('statusProgressTrack');
  const barEl = document.getElementById('statusProgressBar');

  if (msgEl && msg !== undefined) msgEl.innerText = msg;

  if (dotEl) {
    dotEl.className = "w-2 h-2 rounded-full shrink-0";
    if (type === "loading" || type === "busy") {
      dotEl.classList.add("bg-amber-500", "animate-pulse");
      dotEl.title = "Processing...";
    } else if (type === "error") {
      dotEl.classList.add("bg-rose-500");
      dotEl.title = "Attention Required";
    } else {
      dotEl.classList.add("bg-emerald-500");
      dotEl.title = "System Ready";
    }
  }

  if (progress !== null && progress !== undefined) {
    if (badgeEl) {
      badgeEl.classList.remove('hidden');
      badgeEl.classList.add('flex');
    }
    if (textEl) textEl.innerText = typeof progress === 'number' ? `${Math.round(progress)}%` : progress;
    if (trackEl) trackEl.classList.remove('hidden');
    if (barEl) barEl.style.width = typeof progress === 'number' ? `${Math.min(100, Math.max(0, progress))}%` : '60%';
  } else {
    if (badgeEl) {
      badgeEl.classList.add('hidden');
      badgeEl.classList.remove('flex');
    }
    if (trackEl) trackEl.classList.add('hidden');
    if (barEl) barEl.style.width = '0%';
  }
}

async function openAppWebsite() {
  await callAPI('open_url_external', 'https://wbtools.co.in');
}

window.updateStatusBar = updateStatusBar;
window.openAppWebsite = openAppWebsite;

