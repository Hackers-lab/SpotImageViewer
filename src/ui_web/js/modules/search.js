// Consumer Search, Profile HUD & Notes Controller
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
  safeCreateIcons();
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
    safeCreateIcons();
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
    tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition';
    const addressStr = r.address ? r.address.trim() : '-';
    tr.innerHTML = `
      <td class="px-4 py-3 font-mono text-xs font-semibold text-sky-600 dark:text-sky-400">${r.consumer_id}</td>
      <td class="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-300">${r.meter_no || '-'}</td>
      <td class="px-4 py-3 text-xs font-semibold text-slate-900 dark:text-slate-100">${r.name || '-'}</td>
      <td class="px-4 py-3 text-xs text-slate-600 dark:text-slate-300 max-w-sm" title="${addressStr}">${addressStr}</td>
      <td class="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">${r.mobile_number || '-'}</td>
      <td class="px-4 py-3 text-center">
        <button class="bg-sky-600 hover:bg-sky-500 text-white font-medium px-3 py-1 rounded-md text-xs shadow-sm transition">Select</button>
      </td>
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

