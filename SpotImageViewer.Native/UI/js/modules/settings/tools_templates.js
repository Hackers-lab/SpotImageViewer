// --- Tools, Templates, Consumer Data & Auto-Indexing Settings ---

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

// --- Consumer Data Management ---
async function generateConsumerTemplate() {
  const res = await callAPI('generate_consumer_template');
  if (res && res.success) {
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
  if (typeof lastImportedFilePath !== 'undefined' && lastImportedFilePath) {
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

// --- Smart Folder Monitoring & Auto-Index ---
let autoIndexCheckTimer = null;
let lastDetectedChangedFolders = null;

async function initAutoIndexing() {
  const res = await callAPI('get_auto_index_settings');
  const mode = (res && res.mode) ? res.mode : 'prompt';
  const sel = document.getElementById('selectAutoIndexMode');
  if (sel) sel.value = mode;

  // Initial check after short delay
  if (mode !== 'manual') {
    setTimeout(checkFolderChanges, 800);
  }

  // Periodic check every 20 seconds
  if (autoIndexCheckTimer) clearInterval(autoIndexCheckTimer);
  autoIndexCheckTimer = setInterval(() => {
    const currentMode = document.getElementById('selectAutoIndexMode')?.value || 'prompt';
    if (currentMode !== 'manual') {
      checkFolderChanges();
    }
  }, 20000);
}

async function changeAutoIndexMode(mode) {
  const res = await callAPI('set_auto_index_settings', mode);
  if (res && res.success) {
    if (mode === 'manual') {
      dismissFolderChangeBanner();
    } else {
      checkFolderChanges();
    }
  }
}

async function checkFolderChanges() {
  if (indexingPollTimer) return;

  try {
    const res = await callAPI('check_folder_changes');
    if (!res || !res.success) return;

    if (res.has_changes) {
      lastDetectedChangedFolders = res.changed_folders || null;
      const mode = document.getElementById('selectAutoIndexMode')?.value || 'prompt';
      if (mode === 'background') {
        console.log(`Auto-index (background): detected difference of ${res.diff} items. Triggering selective sync...`);
        startIndexing({ target_folders: lastDetectedChangedFolders, full: false });
      } else if (mode === 'prompt') {
        const banner = document.getElementById('folderChangeBanner');
        const text = document.getElementById('folderChangeBannerText');
        const badge = document.getElementById('folderChangeDiffBadge');
        if (banner && text) {
          const sign = (res.diff > 0) ? `+${res.diff}` : `${res.diff}`;
          const currentFiles = res.current_files ?? res.disk_files ?? 0;
          const folderNames = (res.changed_folder_names && res.changed_folder_names.length > 0)
            ? res.changed_folder_names.join(', ')
            : 'linked folder';
          const diffBadgeText = res.diff > 0 ? `+${res.diff.toLocaleString()} New Photo${res.diff > 1 ? 's' : ''}` : `${sign} Photos`;
          if (badge) badge.innerText = diffBadgeText;
          text.innerText = `Detected in [${folderNames}] (${currentFiles.toLocaleString()} files on disk). Quick sync index?`;
          banner.classList.remove('hidden');
          banner.classList.add('flex');
          safeCreateIcons();
        }
      }
    } else {
      dismissFolderChangeBanner();
    }
  } catch (err) {
    console.error('checkFolderChanges error:', err);
  }
}

function dismissFolderChangeBanner() {
  const banner = document.getElementById('folderChangeBanner');
  if (banner) {
    banner.classList.add('hidden');
    banner.classList.remove('flex');
  }
}

function triggerAutoIndexNow() {
  dismissFolderChangeBanner();
  startIndexing({ target_folders: lastDetectedChangedFolders, full: false });
}

window.exportNotes = exportNotes;
window.launchImageCheckGUI = launchImageCheckGUI;
window.showFileActionModal = showFileActionModal;
window.closeFileActionModal = closeFileActionModal;
window.openActionTargetFile = openActionTargetFile;
window.generateConsumerTemplate = generateConsumerTemplate;
window.importConsumerData = importConsumerData;
window.openSavedConsumerData = openSavedConsumerData;
window.closeImportConfirmModal = closeImportConfirmModal;
window.openImportedSourceFile = openImportedSourceFile;
window.initAutoIndexing = initAutoIndexing;
window.changeAutoIndexMode = changeAutoIndexMode;
window.checkFolderChanges = checkFolderChanges;
window.dismissFolderChangeBanner = dismissFolderChangeBanner;
window.triggerAutoIndexNow = triggerAutoIndexNow;
