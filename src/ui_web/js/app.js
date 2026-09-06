// Global Application State
let currentImages = [];
let currentImageIndex = 0;
let zoomScale = 1.0;
let rotationAngle = 0;
let isPanning = false;
let startX = 0, startY = 0, translateX = 0, translateY = 0;
let currentTariffs = {};
let currentConsumerId = null;

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

function restoreLayoutPrefs() {
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
  if (info && info.total_images !== undefined) {
    document.getElementById('statImages').innerText = `${info.total_images.toLocaleString()}`;
    document.getElementById('indexedCount').innerText = info.total_images;
  }
  if (info && info.version) {
    const verEl = document.getElementById('statusAppVersion');
    if (verEl) verEl.innerText = `v${info.version} Studio`;
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
  lucide.createIcons();
}

async function checkUpdateSilent() {
  try {
    const res = await callAPI('check_for_updates');
    if (res && res.success && res.has_update) {
      const badge = document.getElementById('statusUpdateBadge');
      const text = document.getElementById('statusUpdateText');
      if (badge) {
        badge.classList.remove('hidden');
        badge.classList.add('flex');
      }
      if (text) text.innerText = `New v${res.latest_version} Available!`;
      updateStatusBar(`New version v${res.latest_version} available. Click update badge to install.`, "normal");
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
  html.setAttribute('data-theme', newTheme);
  
  const iconEl = document.getElementById('themeIcon');
  if (iconEl) {
    iconEl.setAttribute('data-lucide', newTheme === 'dark' ? 'sun' : 'moon');
  }
  const labelEl = document.getElementById('themeLabel');
  if (labelEl) {
    labelEl.innerText = newTheme.toUpperCase();
  }
  lucide.createIcons();
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

async function handleSearch() {
  closeSearchHistoryDropdown();
  const query = document.getElementById('searchInput').value.trim();
  const filterType = document.getElementById('searchType')?.value || 'auto';
  if (!query) return;

  // Save to search history
  callAPI('save_search_history', 'consumer_ids', query);

  const res = await callAPI('search_consumer', query, filterType);
  if (!res || !res.success || !res.results || !res.results.length) {
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
    document.getElementById('filmstripContainer').innerHTML = `<p class="text-xs text-rose-500 px-4">${res ? res.error : "Failed to load images"}</p>`;
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
    document.getElementById('mainImage').classList.add('hidden');
    document.getElementById('imagePlaceholder').classList.remove('hidden');
    document.getElementById('imgDateTag').innerText = 'No images found';
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

  lucide.createIcons();
}
window.switchSettingsSection = switchSettingsSection;

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

// --- Settings & Utils ---
async function triggerUpdateCheck() {
  const box = document.getElementById('updateStatusBox');
  box.classList.remove('hidden');
  box.className = "p-4 rounded-xl border border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs";
  box.innerText = "Checking for updates...";

  const res = await callAPI('check_for_updates');
  if (res && res.success) {
    if (res.has_update) {
      box.className = "p-4 rounded-xl border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs space-y-2";
      box.innerHTML = `
        <p class="font-bold">\u20B9 New Version ${res.latest_version} Available!</p>
        <p class="whitespace-pre-line">${res.release_notes}</p>
      `;
    } else {
      box.className = "p-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-400 text-xs";
      box.innerText = `You are running the latest version (${res.current_version}).`;
    }
  } else {
    box.className = "p-4 rounded-xl border border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs";
    box.innerText = res ? res.error : "Failed to check update.";
  }
}

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

    const statusStr = count > 0 ? `Indexed ${count.toLocaleString()} images (${elapsed}s)` : `Scanning directories... (${elapsed}s)`;
    if (topText) {
      topText.innerText = count > 0 ? `${count.toLocaleString()} imgs (${elapsed}s)` : `Scanning... (${elapsed}s)`;
    }

    const approxPct = count > 0 ? 75 : 35;
    if (topTimelineBar) {
      topTimelineBar.style.width = `${approxPct}%`;
    }
    updateStatusBar(statusStr, "loading", `${approxPct}%`);

    if (!stat.running) {
      clearInterval(indexingPollTimer);
      indexingPollTimer = null;

      if (topTimelineBar) topTimelineBar.style.width = '100%';
      updateStatusBar(`Indexing complete: ${count.toLocaleString()} images cataloged (${elapsed}s)`, "normal", 100);

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
      }, 2500);

      await initApp();
      alert(`Image re-indexing complete!\nIndexed: ${count.toLocaleString()} images in ${elapsed}s.`);
    }
  }, 400);
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

// --- Fuzzy Lookup Tool Engine ---
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

  const res = await callAPI('run_fuzzy_lookup', '', '', threshold, topN);
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
