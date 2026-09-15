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

// --- Comprehensive Tariff Editor ---
let selectedTariffCategory = null;

function renderTariffEditorList() {
  const container = document.getElementById('tariffList');
  if (!container) return;
  container.innerHTML = '';
  const cats = Object.keys(currentTariffs);
  if (cats.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-400 italic py-2 text-center">No tariff classes found.</p>';
    return;
  }
  if (!selectedTariffCategory || !currentTariffs[selectedTariffCategory]) {
    selectedTariffCategory = cats[0];
  }

  cats.forEach(cat => {
    const isSelected = cat === selectedTariffCategory;
    const div = document.createElement('div');
    div.className = `p-2.5 rounded-xl border text-xs font-semibold cursor-pointer transition flex items-center justify-between ${
      isSelected 
        ? 'bg-sky-500/10 border-sky-500/30 text-sky-600 dark:text-sky-400 shadow-sm' 
        : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60'
    }`;
    div.innerHTML = `
      <span class="truncate pr-1">${escapeHtml(cat)}</span>
      <i data-lucide="chevron-right" class="w-3.5 h-3.5 shrink-0 opacity-60"></i>
    `;
    div.onclick = () => {
      selectedTariffCategory = cat;
      renderTariffEditorList();
      loadTariffForEdit(cat);
    };
    container.appendChild(div);
  });
  safeCreateIcons();
  loadTariffForEdit(selectedTariffCategory);
}

function loadTariffForEdit(cat) {
  if (!cat || !currentTariffs[cat]) return;
  selectedTariffCategory = cat;
  const data = currentTariffs[cat];
  const editor = document.getElementById('tariffEditor');
  if (!editor) return;

  // Energy Slabs HTML
  let energySlabsHtml = '';
  if (data.slabs && Array.isArray(data.slabs)) {
    energySlabsHtml = `
      <div class="space-y-2 pt-2">
        <div class="flex items-center justify-between">
          <label class="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
            <i data-lucide="layers" class="w-3.5 h-3.5 text-sky-500"></i> Energy Charge Slabs (₹ / Unit)
          </label>
          <button onclick="addEnergySlab('${escapeHtml(cat)}')" class="text-[11px] font-semibold text-sky-600 dark:text-sky-400 hover:underline flex items-center gap-1 cursor-pointer">
            <i data-lucide="plus" class="w-3 h-3"></i> Add Energy Slab
          </button>
        </div>
        <div class="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50/50 dark:bg-slate-950/30">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-100 dark:bg-slate-800/80 text-[10.5px] uppercase font-semibold text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th class="px-3 py-2">Slab #</th>
                <th class="px-3 py-2">Upper Limit (Units)</th>
                <th class="px-3 py-2">Rate (₹ / Unit)</th>
                <th class="px-2 py-2 text-center w-10">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-200/70 dark:divide-slate-800/70">
              ${data.slabs.map((slab, idx) => {
                const isUnlimited = slab.limit === null || slab.limit === undefined || slab.limit === '' || slab.limit === 'Above' || isNaN(slab.limit);
                return `
                  <tr class="hover:bg-slate-100/50 dark:hover:bg-slate-800/30 transition">
                    <td class="px-3 py-2 font-mono text-slate-500 text-xs font-bold">${idx + 1}</td>
                    <td class="px-3 py-2">
                      <div class="flex items-center gap-2">
                        <input type="number" min="1" step="1" 
                          value="${isUnlimited ? '' : slab.limit}" 
                          ${isUnlimited ? 'disabled placeholder="Unlimited"' : 'placeholder="e.g. 100"'} 
                          onchange="updateEnergySlabLimit('${escapeHtml(cat)}', ${idx}, this.value)"
                          class="w-28 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500 disabled:opacity-50 disabled:bg-slate-100 dark:disabled:bg-slate-800" />
                        <label class="flex items-center gap-1 text-[11px] text-slate-500 cursor-pointer select-none">
                          <input type="checkbox" ${isUnlimited ? 'checked' : ''} onchange="toggleEnergySlabUnlimited('${escapeHtml(cat)}', ${idx}, this.checked)" class="rounded text-sky-600 focus:ring-0 cursor-pointer">
                          <span>Above</span>
                        </label>
                      </div>
                    </td>
                    <td class="px-3 py-2">
                      <div class="relative w-28">
                        <span class="absolute left-2.5 top-1 text-slate-400 text-xs font-bold">&#8377;</span>
                        <input type="number" min="0" step="0.01" value="${slab.rate !== undefined ? slab.rate : 0}"
                          onchange="updateEnergySlabRate('${escapeHtml(cat)}', ${idx}, this.value)"
                          class="w-full pl-6 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500" />
                      </div>
                    </td>
                    <td class="px-2 py-2 text-center">
                      <button onclick="deleteEnergySlab('${escapeHtml(cat)}', ${idx})" class="text-slate-400 hover:text-rose-500 p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 transition" title="Delete Slab">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                      </button>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  // ToD Slabs HTML (if applicable)
  let todSlabsHtml = '';
  if (data.tod_slabs) {
    todSlabsHtml = `
      <div class="space-y-2 pt-2">
        <label class="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
          <i data-lucide="clock" class="w-3.5 h-3.5 text-amber-500"></i> Time of Day (ToD) Rates (₹ / Unit)
        </label>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
            <span class="text-[11px] font-semibold text-slate-500 block">Normal Hours (06:00 - 17:00)</span>
            <div class="relative">
              <span class="absolute left-2.5 top-1.5 text-slate-400 text-xs font-bold">&#8377;</span>
              <input type="number" step="0.01" value="${data.tod_slabs.Normal !== undefined ? data.tod_slabs.Normal : 0}" 
                onchange="updateTodRate('${escapeHtml(cat)}', 'Normal', this.value)"
                class="w-full pl-6 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500">
            </div>
          </div>
          <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
            <span class="text-[11px] font-semibold text-rose-500 block">Peak Hours (17:00 - 23:00)</span>
            <div class="relative">
              <span class="absolute left-2.5 top-1.5 text-slate-400 text-xs font-bold">&#8377;</span>
              <input type="number" step="0.01" value="${data.tod_slabs.Peak !== undefined ? data.tod_slabs.Peak : 0}" 
                onchange="updateTodRate('${escapeHtml(cat)}', 'Peak', this.value)"
                class="w-full pl-6 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500">
            </div>
          </div>
          <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
            <span class="text-[11px] font-semibold text-emerald-500 block">Off-Peak (23:00 - 06:00)</span>
            <div class="relative">
              <span class="absolute left-2.5 top-1.5 text-slate-400 text-xs font-bold">&#8377;</span>
              <input type="number" step="0.01" value="${data.tod_slabs.Off_Peak !== undefined ? data.tod_slabs.Off_Peak : 0}" 
                onchange="updateTodRate('${escapeHtml(cat)}', 'Off_Peak', this.value)"
                class="w-full pl-6 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-1.5 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500">
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Electricity Duty (ED) Slabs HTML
  let edSlabsHtml = '';
  if (data.ed_slabs && Array.isArray(data.ed_slabs)) {
    edSlabsHtml = `
      <div class="space-y-2 pt-2">
        <div class="flex items-center justify-between">
          <label class="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
            <i data-lucide="percent" class="w-3.5 h-3.5 text-emerald-500"></i> Electricity Duty (ED) Charges
          </label>
          <button onclick="addEdSlab('${escapeHtml(cat)}')" class="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer">
            <i data-lucide="plus" class="w-3 h-3"></i> Add ED Slab
          </button>
        </div>
        <div class="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-slate-50/50 dark:bg-slate-950/30">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-100 dark:bg-slate-800/80 text-[10.5px] uppercase font-semibold text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th class="px-3 py-2">Slab #</th>
                <th class="px-3 py-2">Consumption Threshold (Units)</th>
                <th class="px-3 py-2">Duty Rate (%)</th>
                <th class="px-2 py-2 text-center w-10">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-200/70 dark:divide-slate-800/70">
              ${data.ed_slabs.map((ed, idx) => {
                const isUnlimited = ed.limit === null || ed.limit === undefined || ed.limit === '' || isNaN(ed.limit);
                const pctRate = (ed.rate * 100).toFixed(2).replace(/\.00$/, '');
                return `
                  <tr class="hover:bg-slate-100/50 dark:hover:bg-slate-800/30 transition">
                    <td class="px-3 py-2 font-mono text-slate-500 text-xs font-bold">${idx + 1}</td>
                    <td class="px-3 py-2">
                      <div class="flex items-center gap-2">
                        <input type="number" min="1" step="1" 
                          value="${isUnlimited ? '' : ed.limit}" 
                          ${isUnlimited ? 'disabled placeholder="Unlimited"' : 'placeholder="e.g. 300"'} 
                          onchange="updateEdSlabLimit('${escapeHtml(cat)}', ${idx}, this.value)"
                          class="w-28 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500 disabled:opacity-50 disabled:bg-slate-100 dark:disabled:bg-slate-800" />
                        <label class="flex items-center gap-1 text-[11px] text-slate-500 cursor-pointer select-none">
                          <input type="checkbox" ${isUnlimited ? 'checked' : ''} onchange="toggleEdSlabUnlimited('${escapeHtml(cat)}', ${idx}, this.checked)" class="rounded text-emerald-600 focus:ring-0 cursor-pointer">
                          <span>Above</span>
                        </label>
                      </div>
                    </td>
                    <td class="px-3 py-2">
                      <div class="flex items-center gap-1.5 w-28">
                        <input type="number" min="0" max="100" step="0.1" value="${pctRate}"
                          onchange="updateEdSlabRate('${escapeHtml(cat)}', ${idx}, this.value)"
                          class="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-emerald-500" />
                        <span class="text-slate-500 font-bold text-xs">%</span>
                      </div>
                    </td>
                    <td class="px-2 py-2 text-center">
                      <button onclick="deleteEdSlab('${escapeHtml(cat)}', ${idx})" class="text-slate-400 hover:text-rose-500 p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 transition" title="Delete ED Slab">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                      </button>
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  editor.innerHTML = `
    <div class="space-y-4 pb-4">
      <!-- Header with Action Buttons -->
      <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <span>${escapeHtml(cat)}</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 font-medium">Active Schedule</span>
          </h3>
          <p class="text-[11px] text-slate-500">Edit fixed charges, minimum billing floors, energy slabs, and state electricity duty.</p>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="resetCategoryTariff('${escapeHtml(cat)}')" class="bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 border border-slate-300 dark:border-slate-700 shadow-sm cursor-pointer" title="Reset this category to WBSEDCL defaults">
            <i data-lucide="rotate-ccw" class="w-3 h-3 text-amber-500"></i> Reset Defaults
          </button>
          <button onclick="saveTariffs()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-sm cursor-pointer">
            <i data-lucide="save" class="w-3.5 h-3.5"></i> Save Changes
          </button>
        </div>
      </div>

      <!-- Base Parameters -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
          <label class="text-[11px] font-semibold text-slate-600 dark:text-slate-400 block">Fixed Charge (₹/month or ₹/kVA)</label>
          <div class="relative">
            <span class="absolute left-2.5 top-2 text-slate-400 text-xs font-bold">&#8377;</span>
            <input type="number" step="0.5" id="editFC" value="${data.fixed_charge !== undefined ? data.fixed_charge : 0}" 
              class="w-full pl-6 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-2 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500" 
              onchange="updateTariffData('${escapeHtml(cat)}', 'fixed_charge', this.value)">
          </div>
        </div>
        <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
          <label class="text-[11px] font-semibold text-slate-600 dark:text-slate-400 block">Minimum Billing Charge (₹/mo)</label>
          <div class="relative">
            <span class="absolute left-2.5 top-2 text-slate-400 text-xs font-bold">&#8377;</span>
            <input type="number" step="0.5" id="editMin" value="${data.min_charge !== undefined ? data.min_charge : 0}" 
              class="w-full pl-6 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-2 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500" 
              onchange="updateTariffData('${escapeHtml(cat)}', 'min_charge', this.value)">
          </div>
        </div>
        <div class="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-1">
          <label class="text-[11px] font-semibold text-slate-600 dark:text-slate-400 block">Load Factor Coeff.</label>
          <input type="number" step="0.05" id="editLF" value="${data.load_factor !== undefined ? data.load_factor : 0.5}" 
            class="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg p-2 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 outline-none focus:border-sky-500" 
            onchange="updateTariffData('${escapeHtml(cat)}', 'load_factor', this.value)">
        </div>
      </div>

      <!-- Energy Slabs -->
      ${energySlabsHtml}

      <!-- ToD Rates -->
      ${todSlabsHtml}

      <!-- Electricity Duty Slabs -->
      ${edSlabsHtml}
    </div>
  `;
  safeCreateIcons();
}

function updateTariffData(cat, field, value) {
  if (currentTariffs[cat]) {
    currentTariffs[cat][field] = parseFloat(value) || 0;
  }
}

function updateEnergySlabLimit(cat, idx, value) {
  if (currentTariffs[cat] && currentTariffs[cat].slabs && currentTariffs[cat].slabs[idx]) {
    const v = parseInt(value, 10);
    currentTariffs[cat].slabs[idx].limit = isNaN(v) ? null : v;
  }
}

function updateEnergySlabRate(cat, idx, value) {
  if (currentTariffs[cat] && currentTariffs[cat].slabs && currentTariffs[cat].slabs[idx]) {
    currentTariffs[cat].slabs[idx].rate = parseFloat(value) || 0;
  }
}

function toggleEnergySlabUnlimited(cat, idx, isUnlimited) {
  if (currentTariffs[cat] && currentTariffs[cat].slabs && currentTariffs[cat].slabs[idx]) {
    currentTariffs[cat].slabs[idx].limit = isUnlimited ? null : 100;
    loadTariffForEdit(cat);
  }
}

function addEnergySlab(cat) {
  if (!currentTariffs[cat]) return;
  if (!currentTariffs[cat].slabs) currentTariffs[cat].slabs = [];
  currentTariffs[cat].slabs.push({ limit: null, rate: 8.00 });
  loadTariffForEdit(cat);
}

function deleteEnergySlab(cat, idx) {
  if (currentTariffs[cat] && currentTariffs[cat].slabs) {
    currentTariffs[cat].slabs.splice(idx, 1);
    loadTariffForEdit(cat);
  }
}

function updateTodRate(cat, period, value) {
  if (currentTariffs[cat] && currentTariffs[cat].tod_slabs) {
    currentTariffs[cat].tod_slabs[period] = parseFloat(value) || 0;
  }
}

function updateEdSlabLimit(cat, idx, value) {
  if (currentTariffs[cat] && currentTariffs[cat].ed_slabs && currentTariffs[cat].ed_slabs[idx]) {
    const v = parseInt(value, 10);
    currentTariffs[cat].ed_slabs[idx].limit = isNaN(v) ? null : v;
  }
}

function updateEdSlabRate(cat, idx, value) {
  if (currentTariffs[cat] && currentTariffs[cat].ed_slabs && currentTariffs[cat].ed_slabs[idx]) {
    const pct = parseFloat(value) || 0;
    currentTariffs[cat].ed_slabs[idx].rate = +(pct / 100).toFixed(4);
  }
}

function toggleEdSlabUnlimited(cat, idx, isUnlimited) {
  if (currentTariffs[cat] && currentTariffs[cat].ed_slabs && currentTariffs[cat].ed_slabs[idx]) {
    currentTariffs[cat].ed_slabs[idx].limit = isUnlimited ? null : 500;
    loadTariffForEdit(cat);
  }
}

function addEdSlab(cat) {
  if (!currentTariffs[cat]) return;
  if (!currentTariffs[cat].ed_slabs) currentTariffs[cat].ed_slabs = [];
  currentTariffs[cat].ed_slabs.push({ limit: null, rate: 0.10 });
  loadTariffForEdit(cat);
}

function deleteEdSlab(cat, idx) {
  if (currentTariffs[cat] && currentTariffs[cat].ed_slabs) {
    currentTariffs[cat].ed_slabs.splice(idx, 1);
    loadTariffForEdit(cat);
  }
}

async function resetCategoryTariff(cat) {
  if (confirm(`Reset tariff schedule for "${cat}" to official WBSEDCL gazette defaults?`)) {
    const res = await callAPI('reset_tariff_data', cat);
    if (res && res.success) {
      currentTariffs = res.tariffs;
      if (typeof populateTariffDropdowns === 'function') populateTariffDropdowns();
      renderTariffEditorList();
      alert(`Tariff schedule for "${cat}" reset to default.`);
    } else {
      alert("Failed to reset tariff: " + (res ? res.error : "Unknown error"));
    }
  }
}

async function saveTariffs() {
  const res = await callAPI('save_tariff_data', currentTariffs);
  if (res && res.success) {
    if (typeof populateTariffDropdowns === 'function') populateTariffDropdowns();
    alert("Tariff schedules successfully saved to database!");
  } else {
    alert("Failed to save tariffs: " + (res ? res.error : "Unknown error"));
  }
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
window.triggerUpdateCheck = triggerUpdateCheck;

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

window.toggleUpdatePopup = toggleUpdatePopup;
window.populateUpdatePopupData = populateUpdatePopupData;
window.confirmAndStartUpdate = confirmAndStartUpdate;
window.startUpdateFromPopup = startUpdateFromPopup;
window.dismissUpdateNotification = dismissUpdateNotification;

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
  dismissFolderChangeBanner();

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

// --- Smart Folder Monitoring & Auto-Index ---
let autoIndexCheckTimer = null;

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

let lastDetectedChangedFolders = null;

async function checkFolderChanges() {
  // If indexing is currently running, don't check
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

// Window Exports
window.renderTariffEditorList = renderTariffEditorList;
window.loadTariffForEdit = loadTariffForEdit;
window.updateTariffData = updateTariffData;
window.updateEnergySlabLimit = updateEnergySlabLimit;
window.updateEnergySlabRate = updateEnergySlabRate;
window.toggleEnergySlabUnlimited = toggleEnergySlabUnlimited;
window.addEnergySlab = addEnergySlab;
window.deleteEnergySlab = deleteEnergySlab;
window.updateTodRate = updateTodRate;
window.updateEdSlabLimit = updateEdSlabLimit;
window.updateEdSlabRate = updateEdSlabRate;
window.toggleEdSlabUnlimited = toggleEdSlabUnlimited;
window.addEdSlab = addEdSlab;
window.deleteEdSlab = deleteEdSlab;
window.resetCategoryTariff = resetCategoryTariff;
window.saveTariffs = saveTariffs;

window.renderFolders = renderFolders;
window.addFolder = addFolder;
window.removeFolder = removeFolder;
window.startIndexing = startIndexing;
window.exportNotes = exportNotes;
window.launchImageCheckGUI = launchImageCheckGUI;

window.initAutoIndexing = initAutoIndexing;
window.changeAutoIndexMode = changeAutoIndexMode;
window.checkFolderChanges = checkFolderChanges;
window.dismissFolderChangeBanner = dismissFolderChangeBanner;
window.triggerAutoIndexNow = triggerAutoIndexNow;

window.generateConsumerTemplate = generateConsumerTemplate;
window.importConsumerData = importConsumerData;
window.openSavedConsumerData = openSavedConsumerData;
window.closeImportConfirmModal = closeImportConfirmModal;
window.openImportedSourceFile = openImportedSourceFile;

