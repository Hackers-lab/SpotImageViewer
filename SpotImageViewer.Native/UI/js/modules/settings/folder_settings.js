// --- Folder Management & Indexing Settings ---
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

  let totalImagesAll = 0;
  let availableImagesAll = 0;

  folders.forEach(f => {
    const path = typeof f === 'string' ? f : (f.path || "");
    const isAccessible = typeof f === 'object' && f.accessible !== undefined ? f.accessible : true;
    const isPrimary = typeof f === 'object' && f.is_primary !== undefined ? f.is_primary : false;
    const imgCount = typeof f === 'object' && f.image_count !== undefined ? Number(f.image_count || 0) : 0;

    totalImagesAll += imgCount;
    if (isAccessible) {
      availableImagesAll += imgCount;
    }

    if (!path) return;

    const countBadgeHtml = `
      <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${isAccessible ? 'bg-slate-200/80 dark:bg-slate-800 text-slate-700 dark:text-slate-300' : 'bg-rose-500/15 text-rose-600 dark:text-rose-400 font-semibold'} shrink-0" title="${imgCount.toLocaleString()} indexed images in this folder">
        ${imgCount.toLocaleString()} img${!isAccessible ? ' (Offline)' : ''}
      </span>
    `;

    // Render for Settings Tab
    if (c1) {
      const div1 = document.createElement('div');
      div1.className = "flex items-center justify-between bg-slate-50 dark:bg-slate-950 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 transition";
      div1.innerHTML = `
        <div class="flex items-center gap-2.5 min-w-0 pr-2">
          <span class="w-2 h-2 rounded-full shrink-0 ${isAccessible ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-rose-500'}" title="${isAccessible ? 'Online & Accessible' : 'Folder Not Found / Offline'}"></span>
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs text-slate-800 dark:text-slate-200 truncate font-medium" title="${path}">${path}</span>
              ${countBadgeHtml}
            </div>
            ${isPrimary ? '<span class="text-[10px] text-sky-600 dark:text-sky-400 font-semibold block leading-none mt-0.5">Primary Root Folder</span>' : ''}
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
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-xs truncate font-medium" style="color: var(--text);" title="${path}">${path}</span>
              ${countBadgeHtml}
            </div>
            ${isPrimary ? '<span class="text-[10px] text-sky-500 font-semibold block leading-none mt-0.5">Primary Folder</span>' : ''}
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

  // Dynamically update the top-right #statImages with available count vs total
  if (totalImagesAll > 0 && typeof updateAppCounts === 'function') {
    updateAppCounts(totalImagesAll, null, availableImagesAll);
  }

  safeCreateIcons();
}

let isAddingFolder = false;
async function addFolder() {
  if (isAddingFolder) return;
  isAddingFolder = true;
  try {
    const res = await callAPI('add_network_folder');
    if (res && res.success) {
      const fRes = await callAPI('get_folder_status');
      if (fRes && fRes.success) renderFolders(fRes.folders);
    } else if (res && res.error) {
      alert("Failed to add folder: " + res.error);
    }
  } finally {
    isAddingFolder = false;
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

async function startIndexing(options = {}) {
  const icon = document.getElementById('reloadIndexIcon');
  const prog = document.getElementById('indexProgress');
  const topBadge = document.getElementById('topIndexStatusBadge');
  const topText = document.getElementById('topIndexStatusText');
  const topTimeline = document.getElementById('topIndexTimeline');
  const topTimelineBar = document.getElementById('topIndexTimelineBar');

  const isFull = options && (options.full === true || options.full_reindex === true);
  const targetFolders = options && options.target_folders ? options.target_folders : null;

  if (icon) icon.classList.add('animate-spin');
  if (prog) prog.classList.remove('hidden');
  if (topBadge) {
    topBadge.classList.remove('hidden');
    topBadge.classList.add('flex');
    if (topText) topText.innerText = isFull ? 'Re-indexing all...' : 'Syncing images...';
  }
  if (topTimeline) topTimeline.classList.remove('hidden');
  if (topTimelineBar) topTimelineBar.style.width = '15%';
  updateStatusBar(isFull ? "Full re-indexing of all image folders in progress..." : "Scanning folders for new spot bill images...", "loading", 15);

  const res = await callAPI('start_indexing', { target_folders: targetFolders, full_reindex: isFull });
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

  // Dismiss any folder change banner since indexing is active
  if (typeof dismissFolderChangeBanner === 'function') dismissFolderChangeBanner();

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
    const newAdded = stat.new_added || 0;

    let statusStr = "";
    let badgeStr = "";

    if (!isFull) {
      if (newAdded > 0) {
        statusStr = `Quick Sync: ${newAdded.toLocaleString()} new photo(s) added (${filesSeen.toLocaleString()} checked, ${elapsed}s)...`;
        badgeStr = `+${newAdded.toLocaleString()} new (${elapsed}s)`;
      } else if (filesSeen > 0) {
        statusStr = `Quick Sync: Inspecting ${folder ? '[' + folder + ']' : 'folders'} (${filesSeen.toLocaleString()} checked, ${elapsed}s)...`;
        badgeStr = `Checking (${elapsed}s)...`;
      } else {
        statusStr = `Quick Sync starting... (${elapsed}s)`;
        badgeStr = `Quick Sync...`;
      }
    } else {
      if (count > 0) {
        const speedStr = speed > 0 ? ` • ${speed.toLocaleString()} img/s` : '';
        statusStr = `Full Index: ${count.toLocaleString()} images (${elapsed}s${speedStr}) ${folder ? '[' + folder + ']' : ''}`;
        badgeStr = `${count.toLocaleString()} imgs (${elapsed}s${speed > 0 ? ' • ' + speed + '/s' : ''})`;
      } else if (filesSeen > 0) {
        statusStr = `Full Index: ${filesSeen.toLocaleString()} files inspected (${elapsed}s)...`;
        badgeStr = `Scanning (${filesSeen.toLocaleString()} files)...`;
      } else {
        statusStr = `Scanning directories... (${elapsed}s) ${folder ? '[' + folder + ']' : ''}`;
        badgeStr = `Scanning... (${elapsed}s)`;
      }
    }

    if (topText) {
      topText.innerText = badgeStr;
    }

    // Dynamic progress bar percentage
    const dynamicPct = count > 0 
      ? Math.min(95, 20 + Math.floor(Math.log10(count + 1) * 15)) 
      : (filesSeen > 0 
          ? Math.min(85, 15 + Math.floor(Math.log10(filesSeen + 1) * 14)) 
          : Math.min(45, 10 + (elapsed * 2)));

    if (topTimelineBar) {
      topTimelineBar.style.width = `${dynamicPct}%`;
    }
    updateStatusBar(statusStr, "loading", `${dynamicPct}%`);

    if (!stat.running) {
      clearInterval(indexingPollTimer);
      indexingPollTimer = null;

      if (topTimelineBar) topTimelineBar.style.width = '100%';
      const finalSpeed = speed > 0 ? ` @ ${speed.toLocaleString()} img/s` : '';
      const summaryMsg = (!isFull && newAdded > 0)
        ? `Quick sync complete: ${newAdded.toLocaleString()} new photo(s) added (${filesSeen.toLocaleString()} checked in ${elapsed}s)`
        : (newAdded > 0
          ? `Sync complete: ${newAdded.toLocaleString()} new photos added (${count.toLocaleString()} total)`
          : `Index up to date: ${count.toLocaleString()} images cataloged`);
      updateStatusBar(`${summaryMsg}${finalSpeed}`, "normal", 100);

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
      } else if (isFull) {
        alert(`Image re-indexing complete!\n\nIndexed: ${count.toLocaleString()} images\nElapsed Time: ${elapsed}s\nAverage Speed: ${speed > 0 ? speed.toLocaleString() + ' images/sec' : 'N/A'}`);
      }
    }
  }, 350);
}

window.renderFolders = renderFolders;
window.addFolder = addFolder;
window.removeFolder = removeFolder;
window.startIndexing = startIndexing;
