// --- Settings & Software Update Manager ---
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
    window.latestUpdateInfo = res;
    const container = document.getElementById('statusUpdateContainer');
    const text = document.getElementById('statusUpdateText');
    if (res.has_update) {
      if (container) {
        container.classList.remove('hidden');
        container.classList.add('flex');
      }
      if (text) text.innerText = `Update Available (v${res.latest_version})`;
      populateUpdatePopupData();
    } else {
      if (container) {
        container.classList.add('hidden');
        container.classList.remove('flex');
      }
    }
  }
  renderUpdateCard(res);
}

// --- Inline Update Notification Popup Controllers ---
function toggleUpdatePopup(force) {
  const popup = document.getElementById('statusUpdatePopup');
  if (!popup) return;
  if (typeof force === 'boolean') {
    popup.classList.toggle('hidden', !force);
  } else {
    popup.classList.toggle('hidden');
  }
  if (!popup.classList.contains('hidden')) {
    populateUpdatePopupData();
    safeCreateIcons();
  }
}

function populateUpdatePopupData() {
  const info = window.latestUpdateInfo || latestUpdateInfo;
  if (!info) return;
  const title = document.getElementById('popupUpdateTitle');
  const sub = document.getElementById('popupUpdateSub');
  const notes = document.getElementById('popupUpdateNotes');
  if (title) title.innerText = `Spot Image Viewer v${info.latest_version}`;
  if (sub) sub.innerText = `Current installed: v${info.current_version}`;
  if (notes) notes.innerText = info.release_notes || "Performance optimizations and stability enhancements.";
}

function confirmAndStartUpdate() {
  const info = window.latestUpdateInfo || latestUpdateInfo;
  if (!info || !info.has_update) {
    alert("No update package available to install.");
    return;
  }
  const installerUrl = info.installer_url || info.download_url || '';
  if (!installerUrl) {
    alert("No installer download link found in release.");
    return;
  }
  toggleUpdatePopup(true);
  startUpdateFromPopup();
}

function startUpdateFromPopup() {
  const info = window.latestUpdateInfo || latestUpdateInfo;
  const installerUrl = info ? (info.installer_url || info.download_url || '') : '';
  const progBox = document.getElementById('popupUpdateProgressBox');
  const actBox = document.getElementById('popupUpdateActions');
  if (progBox) progBox.classList.remove('hidden');
  if (actBox) actBox.classList.add('hidden');
  startAppUpdate(installerUrl);
}

function dismissUpdateNotification() {
  const container = document.getElementById('statusUpdateContainer');
  if (container) container.classList.add('hidden');
  const popup = document.getElementById('statusUpdatePopup');
  if (popup) popup.classList.add('hidden');
}

// Close popup on outside click
document.addEventListener('click', (e) => {
  const container = document.getElementById('statusUpdateContainer');
  const popup = document.getElementById('statusUpdatePopup');
  if (popup && !popup.classList.contains('hidden')) {
    if (container && !container.contains(e.target)) {
      popup.classList.add('hidden');
    }
  }
});

async function startAppUpdate(installerUrl) {
  const info = window.latestUpdateInfo || latestUpdateInfo;
  if (!installerUrl && info) {
    installerUrl = info.installer_url || info.download_url || '';
  }

  const btn = document.getElementById('btnStartInstallUpdate');
  const progBox = document.getElementById('updateProgressBox');
  const progStatus = document.getElementById('updateProgressStatus');
  const progPct = document.getElementById('updateProgressPct');
  const progBar = document.getElementById('updateProgressBar');
  const progSub = document.getElementById('updateProgressSub');

  // Also elements in the inline popup
  const popupBar = document.getElementById('popupUpdateProgressBar');
  const popupPct = document.getElementById('popupUpdateProgressPct');
  const popupStatus = document.getElementById('popupUpdateProgressStatus');
  const popupBox = document.getElementById('popupUpdateProgressBox');
  if (popupBox) popupBox.classList.remove('hidden');

  if (btn) {
    btn.disabled = true;
    btn.classList.add('opacity-50', 'cursor-not-allowed');
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Initializing Download...`;
  }
  if (progBox) progBox.classList.remove('hidden');
  safeCreateIcons();

  const res = await callAPI('start_self_update', installerUrl);
  if (!res || !res.success) {
    const errMsg = res ? res.error : "Unknown error";
    if (progStatus) {
      progStatus.innerText = "Download failed to start";
      progStatus.className = "font-semibold text-rose-600 dark:text-rose-400";
    }
    if (progSub) progSub.innerText = errMsg;
    if (popupStatus) {
      popupStatus.innerText = "Failed: " + errMsg;
      popupStatus.className = "text-rose-600 dark:text-rose-400 font-semibold text-[10px]";
    }
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

      // Update inline popup
      if (popupBar) popupBar.style.width = `${pct}%`;
      if (popupPct) popupPct.innerText = `${pct}%`;
      if (popupStatus) popupStatus.innerText = `Downloading: ${dlMB} MB / ${totMB} MB (${pct}%)`;

      updateStatusBar(`Downloading update: ${pct}% (${dlMB}MB / ${totMB}MB)...`, "loading", pct);
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

      // Update inline popup
      if (popupBar) popupBar.style.width = '100%';
      if (popupPct) popupPct.innerText = '100%';
      if (popupStatus) {
        popupStatus.innerText = "Download complete! Launching Windows installer...";
        popupStatus.className = "font-bold text-emerald-600 dark:text-emerald-400 text-xs animate-pulse";
      }

      updateStatusBar("Update download complete! Launching installer...", "normal", 100);
      safeCreateIcons();

      // Close and exit to allow installer to execute
      setTimeout(async () => {
        await callAPI('exit_for_update');
      }, 1500);
    } else if (prog.status === 'error') {
      clearInterval(updatePollTimer);
      const errMsg = prog.error || "Failed to download update installer.";
      if (progStatus) {
        progStatus.innerText = "Download Failed";
        progStatus.className = "font-semibold text-rose-600 dark:text-rose-400";
      }
      if (progSub) progSub.innerText = errMsg;
      if (popupStatus) {
        popupStatus.innerText = "Failed: " + errMsg;
        popupStatus.className = "text-rose-600 dark:text-rose-400 font-semibold text-[10px]";
      }
      if (btn) {
        btn.disabled = false;
        btn.classList.remove('opacity-50', 'cursor-not-allowed');
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> Retry Update`;
      }
      updateStatusBar("Update download failed.", "error");
      safeCreateIcons();
    }
  }, 250);
}

window.renderUpdateCard = renderUpdateCard;
window.triggerUpdateCheck = triggerUpdateCheck;
window.toggleUpdatePopup = toggleUpdatePopup;
window.populateUpdatePopupData = populateUpdatePopupData;
window.confirmAndStartUpdate = confirmAndStartUpdate;
window.startUpdateFromPopup = startUpdateFromPopup;
window.dismissUpdateNotification = dismissUpdateNotification;
window.startAppUpdate = startAppUpdate;
