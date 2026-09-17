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
