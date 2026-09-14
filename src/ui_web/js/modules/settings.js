// Settings, Tariff Management, Folders, Indexing & Data Templates
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

  safeCreateIcons();
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
  safeCreateIcons();
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
  safeCreateIcons();

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
    safeCreateIcons();
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
      safeCreateIcons();

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
      safeCreateIcons();
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

  safeCreateIcons();
}

async function addFolder() {
  const res = await callAPI('add_network_folder');
  if (res && res.success) {
    const fRes = await callAPI('get_folder_status');
    if (fRes && fRes.success) renderFolders(fRes.folders);
  } else if (res && res.error) {
    alert("Failed to add folder: " + res.error);
  }
}

async function removeFolder(p) {
  if (confirm(`Remove folder ${p}?`)) {
    const res = await callAPI('remove_network_folder', p);
    if (res && res.success) {
      const fRes = await callAPI('get_folder_status');
      if (fRes && fRes.success) renderFolders(fRes.folders);
    }
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
    safeCreateIcons();
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

