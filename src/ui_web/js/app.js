// Application Shell, Layout Management & Bootloader
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
  safeCreateIcons();
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
    safeCreateIcons();
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
    safeCreateIcons();
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
  safeCreateIcons();
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
  safeCreateIcons();
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
  safeCreateIcons();
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
  safeCreateIcons();
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
  safeCreateIcons();
}


function updateAppCounts(totalImages, consumerCount) {
  if (totalImages !== null && totalImages !== undefined) {
    const statEl = document.getElementById('statImages');
    const idxEl = document.getElementById('indexedCount');
    if (statEl) statEl.innerText = Number(totalImages).toLocaleString();
    if (idxEl) idxEl.innerText = totalImages;
    try { localStorage.setItem('siv_cached_total_images', String(totalImages)); } catch (e) {}
  }
  if (consumerCount !== null && consumerCount !== undefined) {
    const dbWarningContainer = document.getElementById('statusDbWarningContainer');
    const dbWarningText = document.getElementById('statusDbWarningText');
    const hasData = Number(consumerCount) > 0;
    if (!hasData) {
      if (dbWarningContainer) {
        dbWarningContainer.classList.remove('hidden');
        dbWarningContainer.classList.add('flex');
      }
      if (dbWarningText) dbWarningText.innerText = "Consumer data not updated";
    } else {
      if (dbWarningContainer) {
        dbWarningContainer.classList.add('hidden');
        dbWarningContainer.classList.remove('flex');
      }
    }
    try { localStorage.setItem('siv_cached_consumer_count', String(consumerCount)); } catch (e) {}
  }
}

async function initApp() {
  initAppFont();

  // Instant optimistic render from localStorage to prevent 0 / missing flash
  try {
    const savedImgCount = localStorage.getItem('siv_cached_total_images');
    const savedConsumerCount = localStorage.getItem('siv_cached_consumer_count');
    if (savedImgCount !== null || savedConsumerCount !== null) {
      updateAppCounts(
        savedImgCount !== null ? parseInt(savedImgCount, 10) : null,
        savedConsumerCount !== null ? parseInt(savedConsumerCount, 10) : null
      );
    }
  } catch (e) {}

  const info = await callAPI('get_app_info');
  if (!info || info.success === false) {
    console.warn("get_app_info failed or returned error:", info);
    return false;
  }
  if (info && info.theme) {
    applyTheme(info.theme);
  } else {
    const themeRes = await callAPI('get_theme');
    if (themeRes && themeRes.theme) {
      applyTheme(themeRes.theme);
    }
  }
  if (info && info.total_images !== undefined) {
    updateAppCounts(info.total_images, info.consumer_count);
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
  const hasConsumers = Boolean(info && (info.has_meter_data || (info.consumer_count && info.consumer_count > 0)));
  if (!hasConsumers) {
    if (dbWarningContainer) {
      dbWarningContainer.classList.remove('hidden');
      dbWarningContainer.classList.add('flex');
    }
    if (dbWarningText) dbWarningText.innerText = "Consumer data not updated";
  } else {
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

  // Initialize smart folder change monitoring & auto-index
  if (typeof initAutoIndexing === 'function') initAutoIndexing();

  // Auto-detect empty database and prompt/start initial indexing
  if (info && info.total_images === 0) {
    console.log("Database contains 0 images. Auto-checking if image folders exist to index...");
    setTimeout(async () => {
      try {
        const fRes = await callAPI('get_folder_status');
        if (fRes && fRes.folders && fRes.folders.length > 0 && fRes.folders[0].exists) {
          updateStatusBar("Empty database detected. Starting initial image index...", "loading", 10);
          await startIndexing();
        }
      } catch (err) {
        console.warn("Auto-index check error:", err);
      }
    }, 1200);
  }

  safeCreateIcons();
  return true;
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
  safeCreateIcons();
}

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
  callAPI('set_theme', newTheme);
}


// Robust PyWebView lifecycle & bootloader
let appInitialized = false;
let appInitializing = false;

window.safeInitApp = async function() {
  if (appInitialized || appInitializing) return;
  
  // PyWebView must be injected and ready
  if (!window.pywebview || !window.pywebview.api) {
    return;
  }

  appInitializing = true;
  try {
    const success = await initApp();
    if (success !== false) {
      appInitialized = true;
      console.log("App initialization completed successfully");
    } else {
      console.warn("initApp indicated partial failure, allowing retry on next signal");
    }
  } catch (err) {
    console.error("Error during initApp execution:", err);
  } finally {
    appInitializing = false;
  }
};

function bootApp() {
  safeCreateIcons();
  restoreLayoutPrefs();

  // 1. Check if already injected
  if (window.pywebview && window.pywebview.api) {
    console.log("PyWebView API already ready at boot");
    window.safeInitApp();
    return;
  }

  // 2. Listen on window and document for pywebviewready
  const onReady = () => {
    console.log("PyWebView Ready event received");
    window.safeInitApp();
  };
  window.addEventListener('pywebviewready', onReady);
  document.addEventListener('pywebviewready', onReady);

  // 3. Continuous polling (up to 30s) — never prematurely sets appInitialized = true!
  let elapsed = 0;
  const pollTimer = setInterval(() => {
    elapsed += 50;
    if (window.pywebview && window.pywebview.api) {
      clearInterval(pollTimer);
      console.log(`PyWebView API detected via poll after ${elapsed}ms`);
      window.safeInitApp();
    } else if (elapsed >= 30000) {
      clearInterval(pollTimer);
      if (!appInitialized) {
        console.error("PyWebView API not detected within 30s");
        updateStatusBar("Bridge connection timeout. Please restart application.", "error");
      }
    }
  }, 50);
}

if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', bootApp);
} else {
  bootApp();
}

