// Global State, RPC Communication & Common Utilities

window._debounce = function(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
};

window._throttle = function(fn, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};

// Global Application State
let currentImages = [];
let currentImageIndex = 0;
let zoomScale = 1.0;
let rotationAngle = 0;
let isPanning = false;
let startX = 0, startY = 0, translateX = 0, translateY = 0;
let currentTariffs = {};
let currentConsumerId = null;

async function loadWithConcurrency(items, limit, fn) {
  const results = [];
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const i = index++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return results;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Safe Lucide icon generator that never throws unhandled errors
window.lucide = window.lucide || { createIcons: function() {} };
if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
  const _origCreateIcons = lucide.createIcons.bind(lucide);
  lucide.createIcons = function(...args) {
    try {
      return _origCreateIcons(...args);
    } catch (e) {
      console.warn("lucide.createIcons caught:", e);
    }
  };
}
let _safeCreateIconsTimer = null;
let _pendingRoots = new Set();

function safeCreateIcons(targetRoot = null) {
  if (targetRoot) {
    if (typeof targetRoot === 'string') {
      const el = document.querySelector(targetRoot);
      if (el) _pendingRoots.add(el);
    } else if (targetRoot instanceof Element) {
      _pendingRoots.add(targetRoot);
    }
  }

  if (_safeCreateIconsTimer) clearTimeout(_safeCreateIconsTimer);
  _safeCreateIconsTimer = setTimeout(() => {
    _safeCreateIconsTimer = null;
    if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
      try {
        if (_pendingRoots.size > 0) {
          _pendingRoots.forEach(root => {
            if (root && root.isConnected) {
              lucide.createIcons({ root: root });
            }
          });
        } else {
          lucide.createIcons();
        }
      } catch (e) {
        console.warn("safeCreateIcons warning:", e);
      } finally {
        _pendingRoots.clear();
      }
    }
  }, 30);
}


async function callAPI(method, ...args) {
  // If pywebview is not ready yet, wait up to 15 seconds before giving up
  if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api[method] !== 'function') {
    let waited = 0;
    while ((!window.pywebview || !window.pywebview.api || typeof window.pywebview.api[method] !== 'function') && waited < 15000) {
      await new Promise(r => setTimeout(r, 50));
      waited += 50;
    }
  }

  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api[method] === 'function') {
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      console.error(`API ${method} error:`, e);
      return { success: false, error: e.toString() };
    }
  }
  console.warn(`API method ${method} called without PyWebView (waited 15s)`);
  return { success: false, error: "PyWebView API not available" };
}


function copyDetail(elementId, btn) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText.trim();
  if (!text || text === '-' || text === 'Not Recorded' || text === 'None') return;

  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const originalHtml = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-2.5 h-2.5 text-emerald-500"></i>`;
      safeCreateIcons();
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        safeCreateIcons();
      }, 1200);
    }
  }).catch(err => console.warn('Copy error:', err));
}


// --- Status Bar Helpers ---
function updateStatusBar(msg, type = "normal", progress = null) {
  const msgEl = document.getElementById('statusMessage');
  const dotEl = document.getElementById('statusDot');
  const badgeEl = document.getElementById('statusProgressBadge');
  const textEl = document.getElementById('statusProgressText');
  const trackEl = document.getElementById('statusProgressTrack');
  const barEl = document.getElementById('statusProgressBar');

  if (msgEl && msg !== undefined) msgEl.innerText = msg;

  if (dotEl) {
    dotEl.className = "w-2 h-2 rounded-full shrink-0";
    if (type === "loading" || type === "busy") {
      dotEl.classList.add("bg-amber-500", "animate-pulse");
      dotEl.title = "Processing...";
    } else if (type === "error") {
      dotEl.classList.add("bg-rose-500");
      dotEl.title = "Attention Required";
    } else {
      dotEl.classList.add("bg-emerald-500");
      dotEl.title = "System Ready";
    }
  }

  if (progress !== null && progress !== undefined) {
    if (badgeEl) {
      badgeEl.classList.remove('hidden');
      badgeEl.classList.add('flex');
    }
    if (textEl) textEl.innerText = typeof progress === 'number' ? `${Math.round(progress)}%` : progress;
    if (trackEl) trackEl.classList.remove('hidden');
    if (barEl) barEl.style.width = typeof progress === 'number' ? `${Math.min(100, Math.max(0, progress))}%` : '60%';
  } else {
    if (badgeEl) {
      badgeEl.classList.add('hidden');
      badgeEl.classList.remove('flex');
    }
    if (trackEl) trackEl.classList.add('hidden');
    if (barEl) barEl.style.width = '0%';
  }
}

async function openAppWebsite() {
  await callAPI('open_url_external', 'https://wbtools.co.in');
}

window.updateStatusBar = updateStatusBar;
window.openAppWebsite = openAppWebsite;

