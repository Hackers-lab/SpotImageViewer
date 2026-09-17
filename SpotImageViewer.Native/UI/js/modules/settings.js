// Settings Two-Column Navigation & Shell Controller
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
    if (typeof triggerUpdateCheck === 'function') triggerUpdateCheck();
  }

  safeCreateIcons();
}

function handleUpdateBadgeClick() {
  switchTab('settings');
  switchSettingsSection('update');
}

window.switchSettingsSection = switchSettingsSection;
window.handleUpdateBadgeClick = handleUpdateBadgeClick;
