// Global Application State
let currentImages = [];
let currentImageIndex = 0;
let zoomScale = 1.0;
let rotationAngle = 0;
let isPanning = false;
let startX = 0, startY = 0, translateX = 0, translateY = 0;
let currentTariffs = {};

// On window load
window.addEventListener('pywebviewready', () => {
  console.log("PyWebView Ready!");
  initApp();
});

// Fallback for browser testing
window.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  if (!window.pywebview) {
    console.warn("Running in standard browser mode (mocking API)");
    setTimeout(initApp, 300);
  }
});

async function callAPI(method, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
    return await window.pywebview.api[method](...args);
  }
  console.warn(`API method ${method} called without PyWebView`);
  return { success: false, error: "PyWebView API not available" };
}

async function initApp() {
  const info = await callAPI('get_app_info');
  if (info && info.total_images) {
    document.getElementById('statImages').innerText = `${info.total_images} Imgs`;
  }
  
  // Load tariffs
  const tariffRes = await callAPI('get_tariffs');
  if (tariffRes && tariffRes.success) {
    currentTariffs = tariffRes.tariffs;
    populateTariffDropdowns();
    renderTariffCards();
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
    if (el.dataset.tab === tabId) {
      el.classList.add('active', 'bg-slate-800', 'text-white');
    } else {
      el.classList.remove('active', 'bg-slate-800', 'text-white');
    }
  });
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
  if (!res || !res.success || !res.results.length) {
    alert(`No matching consumers found for "${query}"`);
    return;
  }

  const profile = res.results[0];
  populateProfile(profile);

  // Load images for this consumer
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

async function loadConsumerImages(consumerId) {
  const res = await callAPI('get_consumer_images', consumerId);
  if (!res || !res.success) {
    document.getElementById('filmstripContainer').innerHTML = `<p class="text-xs text-rose-400 px-4">${res ? res.error : "Failed to load images"}</p>`;
    return;
  }

  currentImages = res.images;
  currentImageIndex = 0;
  document.getElementById('searchResultCount').innerText = `${res.total_images} photos`;

  // Render cycles
  const cyclesList = document.getElementById('cyclesList');
  cyclesList.innerHTML = '';
  res.dates.forEach((dateStr, idx) => {
    const btn = document.createElement('button');
    btn.className = "w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition flex items-center justify-between";
    btn.innerHTML = `<span>${dateStr}</span><span class="text-[10px] text-slate-500">${res.grouped[dateStr].length} img</span>`;
    btn.onclick = () => {
      const targetIdx = currentImages.findIndex(img => img.date_formatted === dateStr);
      if (targetIdx !== -1) showImage(targetIdx);
    };
    cyclesList.appendChild(btn);
  });

  // Render filmstrip
  renderFilmstrip();
  if (currentImages.length > 0) {
    showImage(0);
  }
}

function renderFilmstrip() {
  const container = document.getElementById('filmstripContainer');
  container.innerHTML = '';

  currentImages.forEach((img, idx) => {
    const item = document.createElement('div');
    item.className = `filmstrip-thumb flex flex-col items-center justify-center p-2 rounded-xl bg-slate-950/80 border border-slate-800 cursor-pointer min-w-[85px] h-20 shrink-0 ${idx === currentImageIndex ? 'active' : ''}`;
    item.innerHTML = `
      <i data-lucide="image" class="w-6 h-6 text-slate-400 mb-1"></i>
      <span class="text-[10px] font-mono text-slate-300">${img.date_formatted}</span>
    `;
    item.onclick = () => showImage(idx);
    container.appendChild(item);
  });
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
    placeholder.innerHTML = `<p class="text-xs text-rose-400">Failed to render image file</p>`;
  }
}

function stepImage(direction) {
  showImage(currentImageIndex + direction);
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

// --- Bill & Theft Calculations ---
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

async function runBillCalc() {
  const payload = {
    category: document.getElementById('billCategory').value,
    cycle: document.getElementById('billCycle').value,
    days: parseInt(document.getElementById('billDays').value || 30),
    units: parseInt(document.getElementById('billUnits').value || 0),
    load: parseFloat(document.getElementById('billLoad').value || 1.0),
    load_unit: document.getElementById('billLoadUnit').value,
    mvca: parseFloat(document.getElementById('billMvca').value || 0),
    meter_rent_applicable: document.getElementById('billMeterRent').checked,
    is_monsoon: document.getElementById('billMonsoon').checked
  };

  const res = await callAPI('calculate_bill', payload);
  if (res && res.success) {
    const r = res.result;
    document.getElementById('resEnergy').innerText = `? ${r.energy_charge.toFixed(2)}`;
    document.getElementById('resFixed').innerText = `? ${r.fixed_charge.toFixed(2)}`;
    document.getElementById('resMeter').innerText = `? ${r.meter_rent.toFixed(2)}`;
    document.getElementById('resMvca').innerText = `? ${r.mvca_charge.toFixed(2)}`;
    document.getElementById('resEd').innerText = `? ${r.ed_charge.toFixed(2)} (${r.ed_percentage}%)`;
    document.getElementById('resRelief').innerText = `- ? ${r.gov_relief.toFixed(2)}`;
    document.getElementById('resNet').innerText = `? ${r.rounded_bill.toLocaleString('en-IN')}`;
  }
}

async function runTheftCalc() {
  const payload = {
    category: document.getElementById('theftCategory').value,
    consumer_type: document.getElementById('theftConsumerType').value,
    load: parseFloat(document.getElementById('theftLoad').value || 1.5),
    load_unit: document.getElementById('theftLoadUnit').value,
    days: parseInt(document.getElementById('theftDays').value || 365),
    hours: parseFloat(document.getElementById('theftHours').value || 8),
    adj_energy: parseFloat(document.getElementById('theftAdjEnergy').value || 0),
    adj_fixed: parseFloat(document.getElementById('theftAdjFixed').value || 0),
    adj_ed: parseFloat(document.getElementById('theftAdjEd').value || 0)
  };

  const res = await callAPI('calculate_theft', payload);
  if (res && res.success) {
    const r = res.result;
    document.getElementById('theftUnits').innerText = `${r.assessed_units.toLocaleString('en-IN')} kWh (${r.months} mos)`;
    document.getElementById('theftEnergy').innerText = `? ${r.penal_energy_charge.toFixed(2)}`;
    document.getElementById('theftFixed').innerText = `? ${r.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('theftEd').innerText = `? ${r.electricity_duty.toFixed(2)} (${r.ed_rate}%)`;
    document.getElementById('theftAdjustments').innerText = `- ? ${r.total_adjustments.toFixed(2)}`;
    document.getElementById('theftNet').innerText = `? ${r.rounded_assessment.toLocaleString('en-IN')}`;
  }
}

function renderTariffCards() {
  const container = document.getElementById('tariffCardsContainer');
  container.innerHTML = '';

  Object.entries(currentTariffs).forEach(([catName, data]) => {
    const card = document.createElement('div');
    card.className = "p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3";
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <h4 class="text-sm font-bold text-slate-100">${catName}</h4>
        <span class="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-400 font-medium">?${data.fixed_charge}/kVA</span>
      </div>
      <div class="text-xs text-slate-400 space-y-1">
        <p>Min Demand Floor: ?${data.min_charge}/kVA</p>
        <p>Load Factor: ${data.load_factor || 0.5}</p>
      </div>
    `;
    container.appendChild(card);
  });
}

async function triggerUpdateCheck() {
  const box = document.getElementById('updateStatusBox');
  box.classList.remove('hidden');
  box.className = "p-4 rounded-xl border border-sky-500/30 bg-sky-500/10 text-sky-300 text-xs";
  box.innerText = "Checking for updates...";

  const res = await callAPI('check_for_updates');
  if (res && res.success) {
    if (res.has_update) {
      box.className = "p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs space-y-2";
      box.innerHTML = `
        <p class="font-bold">? New Version ${res.latest_version} Available!</p>
        <p class="text-slate-300 whitespace-pre-line">${res.release_notes}</p>
      `;
    } else {
      box.className = "p-4 rounded-xl border border-slate-700 bg-slate-900 text-slate-400 text-xs";
      box.innerText = `You are running the latest version (${res.current_version}).`;
    }
  } else {
    box.className = "p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs";
    box.innerText = res ? res.error : "Failed to check update.";
  }
}
