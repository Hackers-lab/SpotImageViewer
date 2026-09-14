// Spot Image Viewer, Filmstrip, Overview Grid & Canvas Navigation
async function loadConsumerImages(consumerId) {
  const res = await callAPI('get_consumer_images', consumerId);
  if (!res || !res.success) {
    // Clear viewport and grid fully on failure or no images
    currentImages = [];
    currentImageIndex = 0;
    resetZoom();
    const mainImg = document.getElementById('mainImage');
    if (mainImg) {
      mainImg.src = '';
      mainImg.classList.add('hidden');
    }
    const errMsg = (res && res.error) ? res.error : "This consumer has no spot images";
    const placeholder = document.getElementById('imagePlaceholder');
    if (placeholder) {
      placeholder.classList.remove('hidden');
      placeholder.innerHTML = `
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">${escapeHtml(errMsg)}</p>
      `;
      safeCreateIcons();
    }
    const grid = document.getElementById('overviewGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
          <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
            <i data-lucide="image-off" class="w-8 h-8"></i>
          </div>
          <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
          <p class="text-sm font-medium text-slate-500">${escapeHtml(errMsg)}</p>
        </div>
      `;
      safeCreateIcons();
    }

    switchImageViewMode('single');

    const cyclesList = document.getElementById('cyclesList');
    if (cyclesList) cyclesList.innerHTML = '';
    const filmstrip = document.getElementById('filmstripContainer');
    if (filmstrip) filmstrip.innerHTML = `<p class="text-xs text-amber-500 px-4">${escapeHtml(errMsg)}</p>`;
    const filmBadge = document.getElementById('filmstripCountBadge');
    if (filmBadge) filmBadge.innerText = '0';
    const searchResCount = document.getElementById('searchResultCount');
    if (searchResCount) searchResCount.innerText = '0 photos';
    const countSpan = document.getElementById('viewAllPhotosCount');
    if (countSpan) countSpan.innerText = '0';
    const dateTag = document.getElementById('imgDateTagContainer');
    if (dateTag) dateTag.classList.add('hidden');
    const toggleGroup = document.getElementById('viewModeToggleGroup');
    if (toggleGroup) toggleGroup.classList.add('hidden');
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
      btn.dataset.date = dateStr;
      btn.className = "w-full text-left px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#303030] transition flex items-center justify-between group";
      const count = res.grouped[dateStr] ? res.grouped[dateStr].length : 0;
      btn.innerHTML = `
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="cycle-active-indicator hidden w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0"></span>
          <span class="font-mono">${dateStr}</span>
        </div>
        <span class="text-xs text-slate-500 font-mono">${count} img</span>
      `;
      btn.onclick = () => {
        const targetIdx = currentImages.findIndex(img => img.date_formatted === dateStr);
        if (targetIdx !== -1) showImage(targetIdx);
      };
      cyclesList.appendChild(btn);
    });
  }

  // Update all photos counter and show toggle button group
  const toggleGroup = document.getElementById('viewModeToggleGroup');
  const countSpan = document.getElementById('viewAllPhotosCount');
  if (toggleGroup) {
    toggleGroup.classList.remove('hidden');
    toggleGroup.classList.add('flex');
  }
  if (countSpan) countSpan.innerText = currentImages.length;

  // Render filmstrip
  renderFilmstrip();

  // Render Multi-Image Overview Grid
  renderOverviewGrid();

  if (currentImages.length > 0) {
    // Show Overview Grid first for overall consumer idea if more than 1 image exists,
    // or jump straight to single if only 1 photo exists
    if (currentImages.length > 1) {
      switchImageViewMode('grid');
    } else {
      switchImageViewMode('single');
      showImage(0);
    }
  } else {
    switchImageViewMode('single');
    resetZoom();
    const mainImg = document.getElementById('mainImage');
    if (mainImg) {
      mainImg.src = '';
      mainImg.classList.add('hidden');
    }
    const placeholder = document.getElementById('imagePlaceholder');
    if (placeholder) {
      placeholder.classList.remove('hidden');
      placeholder.innerHTML = `
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
      `;
      safeCreateIcons();
    }
    const grid = document.getElementById('overviewGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
          <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
            <i data-lucide="image-off" class="w-8 h-8"></i>
          </div>
          <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
          <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
        </div>
      `;
      safeCreateIcons();
    }
    const dateTagContainer = document.getElementById('imgDateTagContainer');
    if (dateTagContainer) dateTagContainer.classList.add('hidden');
    if (toggleGroup) toggleGroup.classList.add('hidden');
    updateCanvasNavButtons();
  }
}

let currentImageViewMode = 'single'; // 'single' | 'grid'

function switchImageViewMode(mode) {
  currentImageViewMode = mode;
  const viewport = document.getElementById('viewport');
  const gridContainer = document.getElementById('overviewGridContainer');
  const dateTag = document.getElementById('imgDateTagContainer');
  const btnPreview = document.getElementById('btnViewPreview');

  if (mode === 'grid') {
    if (viewport) viewport.classList.add('hidden');
    if (gridContainer) gridContainer.classList.remove('hidden');
    if (dateTag) dateTag.classList.add('hidden');
    if (btnPreview) {
      btnPreview.className = 'h-9 px-3 rounded-xl flex items-center gap-1.5 font-bold text-xs bg-sky-600 text-white shadow-xl transition';
    }
  } else {
    if (viewport) viewport.classList.remove('hidden');
    if (gridContainer) gridContainer.classList.add('hidden');
    if (currentImages.length > 0 && dateTag) {
      dateTag.classList.remove('hidden');
      dateTag.classList.add('flex');
    }
    if (btnPreview) {
      btnPreview.className = 'h-9 px-3 rounded-xl flex items-center gap-1.5 font-semibold text-xs transition bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border border-slate-200 dark:border-slate-800 shadow-xl text-slate-700 dark:text-slate-200 hover:text-sky-600 dark:hover:text-sky-400 hover:border-sky-500/50';
    }

    // Ensure active image is rendered in viewport
    if (currentImages.length > 0) {
      showImage(currentImageIndex);
    }
  }
  updateCanvasNavButtons();
  safeCreateIcons();
}

async function renderOverviewGrid() {
  const grid = document.getElementById('overviewGrid');
  if (!grid) return;
  grid.innerHTML = '';

  if (!currentImages || currentImages.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
        <div class="w-16 h-16 rounded-2xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 flex items-center justify-center text-amber-400 dark:text-amber-500">
          <i data-lucide="image-off" class="w-8 h-8"></i>
        </div>
        <p class="text-base font-semibold text-slate-700 dark:text-slate-300">No Spot Images</p>
        <p class="text-sm font-medium text-slate-500">This consumer has no spot images</p>
      </div>
    `;
    safeCreateIcons();
    return;
  }

  for (let idx = 0; idx < currentImages.length; idx++) {
    const img = currentImages[idx];
    const card = document.createElement('div');
    card.className = "group relative rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white dark:bg-[#1f1f1f] p-2 hover:border-sky-500/50 hover:shadow-lg transition cursor-pointer flex flex-col items-center";
    card.innerHTML = `
      <div class="w-full aspect-[4/3] bg-slate-100 dark:bg-black/50 rounded-lg overflow-hidden flex items-center justify-center mb-2 relative">
        <div id="grid-loader-${idx}" class="w-5 h-5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
        <img id="grid-img-${idx}" class="w-full h-full object-cover hidden group-hover:scale-105 transition-transform duration-200" />
        <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/70 text-[9px] font-mono text-white font-semibold">#${idx + 1}</span>
      </div>
      <div class="w-full flex items-center justify-center text-xs px-0.5">
        <span class="font-mono font-semibold text-slate-800 dark:text-slate-200 text-center">${img.date_formatted}</span>
      </div>
    `;

    card.onclick = () => {
      switchImageViewMode('single');
      showImage(idx);
    };
    grid.appendChild(card);
  }

  await loadWithConcurrency(currentImages, 6, async (img, idx) => {
    const thumb = await callAPI('get_image_data', img.full_path, 350);
    const loader = document.getElementById(`grid-loader-${idx}`);
    const imgEl = document.getElementById(`grid-img-${idx}`);
    if (loader) loader.classList.add('hidden');
    if (imgEl && thumb && thumb.success) {
      imgEl.src = thumb.data;
      imgEl.classList.remove('hidden');
    }
  });
}

window.switchImageViewMode = switchImageViewMode;

async function renderFilmstrip() {
  const container = document.getElementById('filmstripContainer');
  const countBadge = document.getElementById('filmstripCountBadge');
  if (countBadge) countBadge.innerText = currentImages.length;
  if (!container) return;
  container.innerHTML = '';

  if (currentImages.length === 0) {
    container.innerHTML = '<p class="text-[11px] text-slate-400 italic px-2">Thumbnails will appear here once images are loaded.</p>';
    return;
  }

  for (let idx = 0; idx < currentImages.length; idx++) {
    const img = currentImages[idx];
    const item = document.createElement('div');
    item.id = `filmstrip-item-${idx}`;
    item.className = `filmstrip-thumb flex flex-col items-center justify-center p-0.5 rounded cursor-pointer shrink-0 ${idx === currentImageIndex ? 'active' : ''}`;
    item.title = `${img.date_formatted} (${img.filename})`;
    
    item.innerHTML = `
      <div class="w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mb-[5px] mt-[5px]"></div>
      <span class="text-[9px] font-mono leading-none text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
    `;
    item.onclick = () => showImage(idx);
    container.appendChild(item);
  }

  await loadWithConcurrency(currentImages, 4, async (img, idx) => {
    const thumbRes = await callAPI('get_image_data', img.full_path, 150);
    const item = document.getElementById(`filmstrip-item-${idx}`);
    if (!item) return;

    if (thumbRes && thumbRes.success) {
      item.innerHTML = `
        <img src="${thumbRes.data}" class="w-full h-[26px] object-cover rounded mb-0.5" />
        <span class="text-[9px] font-mono leading-none text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
      `;
    } else {
      item.innerHTML = `
        <i data-lucide="image" class="w-4 h-4 text-slate-400 mb-0.5"></i>
        <span class="text-[9px] font-mono leading-none text-slate-700 dark:text-slate-300 truncate w-full text-center">${img.date_formatted}</span>
      `;
      safeCreateIcons();
    }
  });

  safeCreateIcons();
}

function toggleFilmstrip() {
  const wrapper = document.getElementById('filmstripWrapper');
  if (!wrapper) return;
  wrapper.classList.toggle('collapsed-strip');
  safeCreateIcons();
}

window.toggleFilmstrip = toggleFilmstrip;

async function showImage(index) {
  if (index < 0 || index >= currentImages.length) return;
  currentImageIndex = index;
  const item = currentImages[index];

  // If currently in preview grid mode, switch to single image inspector view
  if (currentImageViewMode === 'grid') {
    switchImageViewMode('single');
  }

  const dateTag = document.getElementById('imgDateTag');
  const dateContainer = document.getElementById('imgDateTagContainer');
  if (dateTag) dateTag.innerText = item.date_formatted;
  if (dateContainer) {
    dateContainer.classList.remove('hidden');
    dateContainer.classList.add('flex');
  }

  // Update active state on filmstrip
  document.querySelectorAll('.filmstrip-thumb').forEach((el, i) => {
    if (i === index) el.classList.add('active');
    else el.classList.remove('active');
  });

  // Highlight active date in the dates/cycles list
  document.querySelectorAll('#cyclesList button').forEach(btn => {
    const isSelected = btn.dataset.date === item.date_formatted;
    btn.classList.toggle('bg-sky-500/15', isSelected);
    btn.classList.toggle('dark:bg-sky-500/20', isSelected);
    btn.classList.toggle('text-sky-600', isSelected);
    btn.classList.toggle('dark:text-sky-400', isSelected);
    btn.classList.toggle('font-bold', isSelected);
    btn.classList.toggle('border', isSelected);
    btn.classList.toggle('border-sky-500/30', isSelected);

    // Indicator bullet / check icon
    const indicator = btn.querySelector('.cycle-active-indicator');
    if (indicator) {
      indicator.classList.toggle('hidden', !isSelected);
    }
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
  updateCanvasNavButtons();
}

function updateCanvasNavButtons() {
  const btnPrev = document.getElementById('btnCanvasPrev');
  const btnNext = document.getElementById('btnCanvasNext');
  if (!btnPrev || !btnNext) return;

  const hasMultiple = currentImages && currentImages.length > 1;
  const isSingleMode = currentImageViewMode === 'single';
  const isVisible = hasMultiple && isSingleMode;

  if (isVisible) {
    btnPrev.classList.remove('hidden');
    btnPrev.classList.add('flex');
    btnNext.classList.remove('hidden');
    btnNext.classList.add('flex');
  } else {
    btnPrev.classList.add('hidden');
    btnPrev.classList.remove('flex');
    btnNext.classList.add('hidden');
    btnNext.classList.remove('flex');
  }
}
window.updateCanvasNavButtons = updateCanvasNavButtons;

function stepImage(direction) {
  if (currentImages.length > 0) {
    let newIdx = currentImageIndex + direction;
    if (newIdx < 0) newIdx = currentImages.length - 1;
    if (newIdx >= currentImages.length) newIdx = 0;
    showImage(newIdx);
  }
}
window.stepImage = stepImage;

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
  document.getElementById('zoomLevel').textContent = `${Math.round(zoomScale * 100)}%`;
}

function setupViewportEvents() {
  const vp = document.getElementById('viewport');
  let rafPending = false;
  vp.addEventListener('wheel', (e) => {
    e.preventDefault();
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      if (e.deltaY < 0) zoomIn();
      else zoomOut();
    });
  });

  vp.addEventListener('mousedown', (e) => {
    if (e.target.closest('#singleViewControls') || e.target.closest('#viewModeToggleGroup') || e.target.closest('#btnCanvasPrev') || e.target.closest('#btnCanvasNext')) {
      return;
    }
    if (e.button === 0) {
      isPanning = true;
      startX = e.clientX - translateX;
      startY = e.clientY - translateY;
    }
  });

  let panRafPending = false;
  window.addEventListener('mousemove', (e) => {
    if (!isPanning) return;
    translateX = e.clientX - startX;
    translateY = e.clientY - startY;
    if (panRafPending) return;
    panRafPending = true;
    requestAnimationFrame(() => {
      panRafPending = false;
      applyTransform();
    });
  });

  window.addEventListener('mouseup', () => {
    isPanning = false;
  });

  // Keyboard navigation for images:
  // ArrowLeft / ArrowUp -> Previous image (-1)
  // ArrowRight / ArrowDown -> Next image (+1)
  window.addEventListener('keydown', (e) => {
    // Only navigate if not focused on text inputs, textareas, selects, or contenteditable elements
    const tag = e.target.tagName ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) {
      return;
    }

    // Only active if viewer tab is visible
    const viewerTab = document.getElementById('tab-viewer');
    if (viewerTab && viewerTab.classList.contains('hidden')) {
      return;
    }

    // Directly step the image. Do NOT use button.click() because if the button
    // or container has focus, browsers will trigger native activation alongside keydown,
    // causing a double-step (1 -> 3 -> 5).
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (currentImageViewMode === 'grid') {
        switchImageViewMode('single');
      }
      stepImage(-1);
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (currentImageViewMode === 'grid') {
        switchImageViewMode('single');
      }
      stepImage(1);
      return;
    }

    // Check if any modal overlay is active
    const searchModal = document.getElementById('searchModal');
    if (searchModal && !searchModal.classList.contains('hidden')) return;
    const helpModal = document.getElementById('helpModal');
    if (helpModal && !helpModal.classList.contains('hidden')) return;

    // Ctrl+F / Cmd+F: Focus and select search input
    if ((e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F')) {
      e.preventDefault();
      const searchInput = document.getElementById('searchInput');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // Instant Type-To-Search: Any alphanumeric or symbol key typed while in viewer tab focuses and types into search bar
    if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key && e.key.length === 1) {
      const searchInput = document.getElementById('searchInput');
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
        if (currentConsumerId && searchInput.value.trim() === String(currentConsumerId).trim()) {
          searchInput.value = e.key;
        } else {
          searchInput.value += e.key;
        }
        const len = searchInput.value.length;
        searchInput.setSelectionRange(len, len);
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        if (typeof toggleSearchClearBtn === 'function') {
          toggleSearchClearBtn();
        }
      }
      return;
    }

    // Backspace: Delete character and focus search input
    if (e.key === 'Backspace') {
      const searchInput = document.getElementById('searchInput');
      if (searchInput && searchInput.value.length > 0) {
        e.preventDefault();
        searchInput.focus();
        searchInput.value = searchInput.value.slice(0, -1);
        const len = searchInput.value.length;
        searchInput.setSelectionRange(len, len);
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        if (typeof toggleSearchClearBtn === 'function') {
          toggleSearchClearBtn();
        }
      }
      return;
    }
  });
}

