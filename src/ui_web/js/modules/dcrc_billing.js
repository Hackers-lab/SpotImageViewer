/**
 * Agency PO & DCRC Billing Generator - Frontend Controller
 * Handles SAP file picking, Zone mapping selection, live processing,
 * interactive PO summary matrix, and 1-click agency workbook export.
 */

window.DcrcState = {
  dcrcFiles: [],
  cashFiles: [],
  zoneFile: '',
  consumerFile: '',
  outputFolder: 'C:\\spotbillfiles\\DCRC_PO_Output',
  isProcessing: false,
  isExporting: false,
  lastResult: null,
  activeView: 'summary', // 'summary' | 'discrepancies' | 'preview' | 'rates'
  rates: {
    "1PH": { "DC": 65, "RC": 65, "DR": 130 },
    "3PH": { "DC": 88, "RC": 88, "DR": 176 }
  }
};

async function initDcrcModule() {
  try {
    if (window.pywebview && window.pywebview.api) {
      const defs = await window.pywebview.api.get_dcrc_defaults();
      if (defs && defs.success) {
        if (!DcrcState.zoneFile && defs.zone_template) {
          DcrcState.zoneFile = defs.zone_template;
          updateDcrcBadge('dcrcZoneBadge', defs.zone_template);
        }
        if (!DcrcState.consumerFile && defs.consumer_template) {
          DcrcState.consumerFile = defs.consumer_template;
          updateDcrcBadge('dcrcConsumerBadge', defs.consumer_template);
        }
        if (defs.default_output) {
          DcrcState.outputFolder = defs.default_output;
          const outEl = document.getElementById('dcrcOutputFolderDisplay');
          if (outEl) outEl.value = defs.default_output;
        }
      }
    }
  } catch (err) {
    console.error('[initDcrcModule error]:', err);
  }
}

function updateDcrcBadge(elementId, text, isCount = false) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (!text || (Array.isArray(text) && text.length === 0)) {
    el.textContent = 'None Selected';
    el.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 truncate max-w-xs';
  } else if (isCount) {
    el.textContent = `${text} files selected`;
    el.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold truncate max-w-xs';
  } else {
    const filename = String(text).split(/[\\/]/).pop();
    el.textContent = filename;
    el.title = text;
    el.className = 'text-[11px] font-mono px-2 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 font-bold truncate max-w-xs';
  }
}

async function pickDcrcEventsFiles() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.pick_dcrc_events_files();
    if (res && res.success && res.files && res.files.length > 0) {
      DcrcState.dcrcFiles = res.files;
      updateDcrcBadge('dcrcEventsBadge', res.files.length, true);
    }
  } catch (err) {
    alert('Error selecting DCRC files: ' + err);
  }
}

async function pickDcrcCashFiles() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.pick_cash_payment_files();
    if (res && res.success && res.files && res.files.length > 0) {
      DcrcState.cashFiles = res.files;
      updateDcrcBadge('dcrcCashBadge', res.files.length, true);
    }
  } catch (err) {
    alert('Error selecting payment files: ' + err);
  }
}

async function pickDcrcZoneFile() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.pick_zone_mapping_file();
    if (res && res.success && res.file) {
      DcrcState.zoneFile = res.file;
      updateDcrcBadge('dcrcZoneBadge', res.file);
    }
  } catch (err) {
    alert('Error selecting Zone mapping file: ' + err);
  }
}

async function pickDcrcConsumerFile() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.pick_consumer_master_file();
    if (res && res.success && res.file) {
      DcrcState.consumerFile = res.file;
      updateDcrcBadge('dcrcConsumerBadge', res.file);
    }
  } catch (err) {
    alert('Error selecting Consumer Master file: ' + err);
  }
}

async function pickDcrcOutputFolder() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.pick_dcrc_output_folder();
    if (res && res.success && res.folder) {
      DcrcState.outputFolder = res.folder;
      const outEl = document.getElementById('dcrcOutputFolderDisplay');
      if (outEl) outEl.value = res.folder;
    }
  } catch (err) {
    alert('Error picking output folder: ' + err);
  }
}

async function loadDefaultDcrcTemplates() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const defs = await window.pywebview.api.get_dcrc_defaults();
    if (defs && defs.success) {
      if (defs.zone_template) {
        DcrcState.zoneFile = defs.zone_template;
        updateDcrcBadge('dcrcZoneBadge', defs.zone_template);
      }
      if (defs.consumer_template) {
        DcrcState.consumerFile = defs.consumer_template;
        updateDcrcBadge('dcrcConsumerBadge', defs.consumer_template);
      }
      showDcrcToast('Loaded default templates from ' + defs.template_dir);
    }
  } catch (err) {
    alert('Error loading defaults: ' + err);
  }
}

async function runDcrcProcessing() {
  if (DcrcState.isProcessing) return;

  if (!DcrcState.dcrcFiles || DcrcState.dcrcFiles.length === 0) {
    alert('Please select at least one DCRC SAP file (e.g. DC.XLS, RC.XLS, DR.xls, ONLINE DR.XLS).');
    return;
  }
  if (!DcrcState.zoneFile) {
    alert('Please select the Zone Mapping file (Zones.xlsx).');
    return;
  }

  DcrcState.isProcessing = true;
  setDcrcProcessingUI(true);

  try {
    const res = await window.pywebview.api.process_dcrc_data(
      DcrcState.dcrcFiles,
      DcrcState.cashFiles,
      DcrcState.zoneFile,
      DcrcState.consumerFile,
      null
    );

    if (res && res.success) {
      DcrcState.lastResult = res;
      renderDcrcResults(res);
      showDcrcToast(`Processed ${res.total_records_processed} records successfully!`);
    } else {
      alert('Error processing DCRC files: ' + (res?.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Exception running processing: ' + err);
  } finally {
    DcrcState.isProcessing = false;
    setDcrcProcessingUI(false);
  }
}

function setDcrcProcessingUI(isProcessing) {
  const btn = document.getElementById('btnRunDcrcProcess');
  const spinner = document.getElementById('dcrcProcessSpinner');
  const btnText = document.getElementById('dcrcProcessBtnText');

  if (btn) btn.disabled = isProcessing;
  if (spinner) spinner.classList.toggle('hidden', !isProcessing);
  if (btnText) btnText.textContent = isProcessing ? 'Processing Transactions...' : 'Process & Generate PO';
}

function switchDcrcSubView(viewName) {
  DcrcState.activeView = viewName;
  ['summary', 'discrepancies', 'preview'].forEach(v => {
    const section = document.getElementById(`dcrcView-${v}`);
    const tabBtn = document.getElementById(`dcrcTabBtn-${v}`);
    if (section) section.classList.toggle('hidden', v !== viewName);
    if (tabBtn) {
      if (v === viewName) {
        tabBtn.className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-xs cursor-pointer';
      } else {
        tabBtn.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer';
      }
    }
  });
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

function renderDcrcResults(res) {
  const resultsContainer = document.getElementById('dcrcResultsContainer');
  if (resultsContainer) resultsContainer.classList.remove('hidden');

  // 1. Stat cards
  const t = res.totals || {};
  document.getElementById('dcrcStatTotalRecords').textContent = (res.total_records_processed || 0).toLocaleString();
  document.getElementById('dcrcStat1phRecords').textContent = (t['1ph_total'] || 0).toLocaleString();
  document.getElementById('dcrcStat3phRecords').textContent = (t['3ph_total'] || 0).toLocaleString();
  document.getElementById('dcrcStatTotalAmount').textContent = '₹ ' + (t.total_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

  const discCount = res.total_discrepancies || 0;
  const discBadge = document.getElementById('dcrcDiscrepancyBadge');
  if (discBadge) {
    discBadge.textContent = discCount;
    discBadge.className = discCount > 0
      ? 'px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-bold'
      : 'px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold';
  }

  // 2. Summary Table
  const tbody = document.getElementById('dcrcSummaryTableBody');
  if (tbody) {
    tbody.innerHTML = '';
    const summary = res.summary || [];
    summary.forEach((row, idx) => {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition';
      tr.innerHTML = `
        <td class="p-2.5 font-bold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
          ${row.agency}
        </td>
        <td class="p-2.5 text-center font-mono text-xs">${row.c_1ph_dc}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_1ph_dc}</td>
        <td class="p-2.5 text-center font-mono text-xs">${row.c_1ph_rc}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_1ph_rc}</td>
        <td class="p-2.5 text-center font-mono text-xs">${row.c_1ph_dr}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_1ph_dr}</td>
        <td class="p-2.5 text-center font-mono text-xs border-l border-slate-200 dark:border-slate-800">${row.c_3ph_dc}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_3ph_dc}</td>
        <td class="p-2.5 text-center font-mono text-xs">${row.c_3ph_rc}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_3ph_rc}</td>
        <td class="p-2.5 text-center font-mono text-xs">${row.c_3ph_dr}</td>
        <td class="p-2.5 text-center font-mono text-xs text-slate-400">${row.r_3ph_dr}</td>
        <td class="p-2.5 text-right font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400 border-l border-slate-200 dark:border-slate-800">
          ₹ ${row.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </td>
        <td class="p-2.5 text-right font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
          ${row.total_count}
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Grand total row
    const footTr = document.createElement('tr');
    footTr.className = 'bg-slate-100/90 dark:bg-slate-900/90 font-bold border-t-2 border-slate-300 dark:border-slate-700';
    footTr.innerHTML = `
      <td class="p-2.5 text-xs text-slate-900 dark:text-slate-100">TOTAL</td>
      <td class="p-2.5 text-center font-mono text-xs">${t['1ph_dc'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-center font-mono text-xs">${t['1ph_rc'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-center font-mono text-xs">${t['1ph_dr'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-center font-mono text-xs border-l border-slate-200 dark:border-slate-800">${t['3ph_dc'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-center font-mono text-xs">${t['3ph_rc'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-center font-mono text-xs">${t['3ph_dr'] || 0}</td>
      <td class="p-2.5 text-center font-mono text-xs text-slate-400">-</td>
      <td class="p-2.5 text-right font-mono text-xs text-emerald-600 dark:text-emerald-400 border-l border-slate-200 dark:border-slate-800">
        ₹ ${(t.total_amount || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
      </td>
      <td class="p-2.5 text-right font-mono text-xs text-slate-900 dark:text-slate-100">
        ${(t.total_records || 0).toLocaleString()}
      </td>
    `;
    tbody.appendChild(footTr);
  }

  // 3. Discrepancies Table
  const discTbody = document.getElementById('dcrcDiscrepanciesTableBody');
  if (discTbody) {
    discTbody.innerHTML = '';
    const discs = res.discrepancies || [];
    if (discs.length === 0) {
      discTbody.innerHTML = `
        <tr>
          <td colspan="6" class="p-6 text-center text-xs text-slate-400 font-medium">
            <i data-lucide="check-circle" class="w-6 h-6 text-emerald-500 mx-auto mb-1"></i>
            All transactions matched cleanly! Zero discrepancies found.
          </td>
        </tr>
      `;
    } else {
      discs.forEach(d => {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-slate-200/60 dark:border-slate-800/60 text-xs';
        tr.innerHTML = `
          <td class="p-2.5 font-mono">${d.consumer_id}</td>
          <td class="p-2.5 font-bold">${d.payment_type}</td>
          <td class="p-2.5 font-mono">₹ ${d.amount}</td>
          <td class="p-2.5 font-mono">${d.payment_date}</td>
          <td class="p-2.5 font-mono">${d.zone || '<span class="text-rose-400">Blank</span>'}</td>
          <td class="p-2.5 text-rose-500 font-semibold">${d.issue}</td>
        `;
        discTbody.appendChild(tr);
      });
    }
  }

  // 4. Sample Preview Table
  const prevTbody = document.getElementById('dcrcPreviewTableBody');
  if (prevTbody) {
    prevTbody.innerHTML = '';
    const sample = res.sample_records || [];
    sample.forEach(r => {
      const tr = document.createElement('tr');
      tr.className = 'border-b border-slate-200/60 dark:border-slate-800/60 text-xs font-mono';
      tr.innerHTML = `
        <td class="p-2 text-slate-400">${r.sl}</td>
        <td class="p-2 font-bold text-slate-800 dark:text-slate-200">${r.consumer_id}</td>
        <td class="p-2">${r.payment_type}</td>
        <td class="p-2">₹ ${r.amount}</td>
        <td class="p-2">${r.payment_date}</td>
        <td class="p-2 text-sky-600 dark:text-sky-400">${r.doc_number || '-'}</td>
        <td class="p-2">${r.zone || '-'}</td>
        <td class="p-2 font-bold text-emerald-600 dark:text-emerald-400">${r.agency || '-'}</td>
        <td class="p-2">${r.phase}PH</td>
      `;
      prevTbody.appendChild(tr);
    });
  }

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

async function exportDcrcAgencyWorkbooks() {
  if (DcrcState.isExporting) return;
  if (!DcrcState.lastResult) {
    alert('Please process transactions before exporting.');
    return;
  }

  const outFolder = DcrcState.outputFolder || 'C:\\spotbillfiles\\DCRC_PO_Output';
  DcrcState.isExporting = true;
  const btn = document.getElementById('btnExportDcrc');
  if (btn) btn.disabled = true;

  try {
    const res = await window.pywebview.api.export_dcrc_files(outFolder);
    if (res && res.success) {
      showDcrcToast(`Exported ${res.agency_files_count} agency workbooks & PO report!`);
      // Ask user to open folder
      if (confirm(`Successfully generated:\n• ${res.agency_files_count} Agency Workbooks\n• PO Summary Report\n• Master Enriched List\n\nOpen output folder now?`)) {
        window.pywebview.api.open_folder_in_explorer(outFolder);
      }
    } else {
      alert('Error during export: ' + (res?.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Export error: ' + err);
  } finally {
    DcrcState.isExporting = false;
    if (btn) btn.disabled = false;
  }
}

function openDcrcOutputFolderInExplorer() {
  if (!window.pywebview || !window.pywebview.api) return;
  const outFolder = DcrcState.outputFolder || 'C:\\spotbillfiles\\DCRC_PO_Output';
  window.pywebview.api.open_folder_in_explorer(outFolder);
}

function showDcrcToast(msg) {
  const toast = document.getElementById('dcrcToast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove('hidden');
  toast.classList.add('flex');
  setTimeout(() => {
    toast.classList.add('hidden');
    toast.classList.remove('flex');
  }, 4000);
}

async function downloadDcrcSample(sampleType) {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.download_dcrc_sample(sampleType);
    if (res && res.success) {
      showDcrcToast(`Saved sample ${res.filename} successfully!`);
      if (confirm(`Sample template saved to:\n${res.saved_path}\n\nDo you want to open it in Excel now?`)) {
        window.pywebview.api.open_dcrc_sample(sampleType);
      }
    } else if (res && res.error) {
      alert('Could not save sample: ' + res.error);
    }
  } catch (err) {
    alert('Error downloading sample: ' + err);
  }
}

async function openDcrcTemplatesFolder() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    await window.pywebview.api.open_dcrc_templates_folder();
  } catch (err) {
    alert('Error opening templates folder: ' + err);
  }
}

// Explicit window bindings for inline HTML onclick handlers
window.initDcrcModule = initDcrcModule;
window.pickDcrcEventsFiles = pickDcrcEventsFiles;
window.pickDcrcCashFiles = pickDcrcCashFiles;
window.pickDcrcZoneFile = pickDcrcZoneFile;
window.pickDcrcConsumerFile = pickDcrcConsumerFile;
window.pickDcrcOutputFolder = pickDcrcOutputFolder;
window.loadDefaultDcrcTemplates = loadDefaultDcrcTemplates;
window.runDcrcProcessing = runDcrcProcessing;
window.switchDcrcSubView = switchDcrcSubView;
window.exportDcrcAgencyWorkbooks = exportDcrcAgencyWorkbooks;
window.openDcrcOutputFolderInExplorer = openDcrcOutputFolderInExplorer;
window.downloadDcrcSample = downloadDcrcSample;
window.openDcrcTemplatesFolder = openDcrcTemplatesFolder;


