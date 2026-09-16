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
window.initAppFont = initAppFont;
