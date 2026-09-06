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
  viewer:   { title: 'Image Viewer',       icon: 'image' },
  bill:     { title: 'Bill Calculator',    icon: 'zap' },
  theft:    { title: 'Theft Assessment',   icon: 'scale' },
  tariffs:  { title: 'Tariff Manager',     icon: 'sliders' },
  audit:    { title: 'Low Cons. Audit',    icon: 'file-spreadsheet' },
  tools:    { title: 'Tools & Utilities',  icon: 'wrench' },
  settings: { title: 'Settings & Update',  icon: 'settings' },
};

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
  const rail = document.getElementById('sidebarRail');
  if (!sidebar || !rail) return;
  const collapsing = !sidebar.classList.contains('hidden-panel');
  sidebar.classList.toggle('hidden-panel', collapsing);
  rail.classList.toggle('hidden', !collapsing);
  rail.classList.toggle('flex', collapsing);
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
    const rail = document.getElementById('sidebarRail');
    if (sidebar && rail) {
      sidebar.classList.add('hidden-panel');
      rail.classList.remove('hidden');
      rail.classList.add('flex');
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
  const info = await callAPI('get_app_info');
  if (info && info.total_images) {
    document.getElementById('statImages').innerText = `${info.total_images} Imgs`;
    document.getElementById('indexedCount').innerText = info.total_images;
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
  lucide.createIcons();
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  const activeTab = document.getElementById(`tab-${tabId}`);
  if (activeTab) activeTab.classList.remove('hidden');

  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.tab === tabId);
  });
  updatePageHeader(tabId);
  lucide.createIcons();
}

function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute('data-theme') || 'dark';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', newTheme);
  document.getElementById('themeLabel').innerText = newTheme.toUpperCase();
  lucide.createIcons();
}

// --- Universal Search Handling ---
async function handleSearch() {
  const query = document.getElementById('searchInput').value.trim();
  const filterType = document.getElementById('searchType').value;
  if (!query) return;

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

  const badge = document.getElementById('consumerBadge');
  const badgeText = document.getElementById('consumerBadgeText');
  badge.classList.remove('hidden');
  badgeText.innerText = `CID: ${p.consumer_id}`;
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
      btn.className = "w-full text-left px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#303030] transition flex items-center justify-between";
      const count = res.grouped[dateStr] ? res.grouped[dateStr].length : 0;
      btn.innerHTML = `<span class="font-mono font-semibold">${dateStr}</span><span class="text-xs text-slate-500 font-mono">${count} img</span>`;
      btn.onclick = () => {
        const targetIdx = currentImages.findIndex(img => img.date_formatted === dateStr);
        if (targetIdx !== -1) showImage(targetIdx);
      };
      cyclesList.appendChild(btn);
    });
  }

  // Render filmstrip
  renderFilmstrip();
  if (currentImages.length > 0) {
    showImage(0);
  } else {
    document.getElementById('mainImage').classList.add('hidden');
    document.getElementById('imagePlaceholder').classList.remove('hidden');
    document.getElementById('imgDateTag').innerText = 'No images found';
  }
}

async function renderFilmstrip() {
  const container = document.getElementById('filmstripContainer');
  container.innerHTML = '';

  for (let idx = 0; idx < currentImages.length; idx++) {
    const img = currentImages[idx];
    const item = document.createElement('div');
    item.className = `filmstrip-thumb flex flex-col items-center justify-center p-1 rounded-lg bg-white dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 cursor-pointer w-24 h-20 shrink-0 ${idx === currentImageIndex ? 'active' : ''}`;
    
    // Try to get thumbnail
    const thumbRes = await callAPI('get_image_data', img.full_path, 200);
    if (thumbRes && thumbRes.success) {
      item.innerHTML = `
        <img src="${thumbRes.data}" class="w-full h-12 object-cover rounded mb-1" />
        <span class="text-xs font-mono text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
      `;
    } else {
      item.innerHTML = `
        <i data-lucide="image" class="w-6 h-6 text-slate-400 mb-1"></i>
        <span class="text-xs font-mono text-slate-700 dark:text-slate-300">${img.date_formatted}</span>
      `;
    }
    
    item.onclick = () => showImage(idx);
    container.appendChild(item);
  }
  lucide.createIcons();
}

async function showImage(index) {
  if (index < 0 || index >= currentImages.length) return;
  currentImageIndex = index;
  const item = currentImages[index];

  document.getElementById('imgDateTag').innerText = `${item.date_formatted} (${item.filename})`;

  // Update active state on filmstrip
  document.querySelectorAll('.filmstrip-thumb').forEach((el, i) => {
    if (i === index) el.classList.add('active');
    else el.classList.remove('active');
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
  const row = document.getElementById('proRataRow');
  if (cycle === 'Pro-Rata') row.classList.remove('hidden');
  else row.classList.add('hidden');
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
    document.getElementById('resEnergy').innerHTML = `\u20B9 ${r.energy_charge.toFixed(2)}`;
    document.getElementById('resFixed').innerHTML = `\u20B9 ${r.fixed_charge.toFixed(2)}`;
    
    const minTag = document.getElementById('resMinTag');
    if (r.min_charge_override) minTag.classList.remove('hidden');
    else minTag.classList.add('hidden');
    document.getElementById('resMin').innerHTML = `\u20B9 ${(r.minimum_charge || 0).toFixed(2)}`;

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
  }
}

// --- Theft Calculations ---
function formatDecimalHours(h) {
  const totalMinutes = Math.max(0, Math.min(24 * 60, Math.round(h * 60)));
  const hrs = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return `(${String(hrs).padStart(2, '0')}h ${String(mins).padStart(2, '0')}m)`;
}

async function runTheftCalc() {
  const provHours = parseFloat(document.getElementById('theftProvHours').value || 24);
  const finalHours = parseFloat(document.getElementById('theftFinalHours').value || 19);

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
    const p = res.provisional || res.prov;
    document.getElementById('provUnits').innerText = `${p.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('provEnergy').innerHTML = `\u20B9 ${p.penal_energy_charge.toFixed(2)}`;
    document.getElementById('provFixed').innerHTML = `\u20B9 ${p.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('provEd').innerHTML = `\u20B9 ${p.electricity_duty.toFixed(2)}`;
    document.getElementById('provGross').innerHTML = `\u20B9 ${p.gross_assessment.toFixed(2)}`;
    document.getElementById('provAdj').innerHTML = `- \u20B9 ${p.total_adjustments.toFixed(2)}`;
    document.getElementById('provNet').innerHTML = `\u20B9 ${p.rounded_assessment.toLocaleString('en-IN')}`;

    const f = res.final;
    document.getElementById('finalUnits').innerText = `${f.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('finalEnergy').innerHTML = `\u20B9 ${f.penal_energy_charge.toFixed(2)}`;
    document.getElementById('finalFixed').innerHTML = `\u20B9 ${f.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('finalEd').innerHTML = `\u20B9 ${f.electricity_duty.toFixed(2)}`;
    document.getElementById('finalGross').innerHTML = `\u20B9 ${f.gross_assessment.toFixed(2)}`;
    document.getElementById('finalAdj').innerHTML = `- \u20B9 ${f.total_adjustments.toFixed(2)}`;
    document.getElementById('finalNet').innerHTML = `\u20B9 ${f.rounded_assessment.toLocaleString('en-IN')}`;

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
  }
}

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
  const c = document.getElementById('folderList');
  if (!c) return;
  c.innerHTML = '';
  folders.forEach(f => {
    const div = document.createElement('div');
    div.className = "flex items-center justify-between bg-slate-50 dark:bg-slate-950 p-2 rounded-lg border border-slate-200 dark:border-slate-800";
    div.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full ${f.accessible ? 'bg-emerald-500' : 'bg-rose-500'}"></span>
        <span class="text-xs text-slate-700 dark:text-slate-300 truncate w-48" title="${f.path}">${f.path}</span>
      </div>
      <button onclick="removeFolder('${f.path}')" class="text-rose-600 hover:text-rose-500 text-xs"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
    `;
    c.appendChild(div);
  });
  lucide.createIcons();
}

async function addFolder() {
  const p = prompt("Enter folder path:");
  if (p) {
    await callAPI('add_network_folder', p);
    initApp(); // reload info
  }
}

async function removeFolder(p) {
  if (confirm(`Remove folder ${p}?`)) {
    await callAPI('remove_network_folder', p);
    initApp();
  }
}

async function startIndexing() {
  document.getElementById('indexProgress').classList.remove('hidden');
  const res = await callAPI('start_indexing');
  if (res && res.success) {
    alert("Indexing started");
    setTimeout(initApp, 2000);
  } else {
    alert("Failed to start indexing");
  }
}

async function exportNotes() {
  const res = await callAPI('export_notes_csv');
  if (res && res.success) {
    alert("Exported notes successfully to:\n" + res.path);
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

// --- Consumer Data Management ---
async function generateConsumerTemplate() {
  const res = await callAPI('generate_consumer_template');
  if (res && res.success) {
    alert("Consumer data template created at:\n" + res.path);
  } else if (res && res.error) {
    alert("Failed to generate template: " + res.error);
  }
}

async function importConsumerData() {
  const res = await callAPI('import_consumer_data');
  if (res && res.success) {
    alert(`Successfully imported ${res.count} consumer records into local database.`);
    initApp();
  } else if (res && res.error) {
    alert("Failed to import consumer data: " + res.error);
  }
}

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

    if (!stat.running) {
      clearInterval(fuzzyPollTimer);
      fuzzyPollTimer = null;
      if (runBtn) runBtn.disabled = false;

      if (stat.error) {
        alert("Fuzzy Lookup encountered an error: " + stat.error);
        if (statusText) statusText.innerText = "Error: " + stat.error;
      } else {
        if (progBar) progBar.style.width = '100%';
        if (countText) countText.innerText = `100% | ${stat.elapsed}s`;
        if (linkBox) {
          linkBox.classList.remove('hidden');
          linkBox.innerHTML = `<strong>Results Saved:</strong> ${stat.output_path}`;
        }
        alert("Fuzzy Lookup Complete!\nResults exported to:\n" + stat.output_path);
      }
    }
  }, 400);
}

