// Electricity Bill & Theft Assessment Calculators
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
  const proRataRow = document.getElementById('proRataRow');
  const benefitContainer = document.getElementById('tariffBenefitContainer');

  if (cycle === 'Pro-Rata') {
    proRataRow.classList.remove('hidden');
    proRataRow.classList.add('grid');
    benefitContainer.classList.add('hidden');
  } else if (cycle === 'Benefit') {
    proRataRow.classList.add('hidden');
    proRataRow.classList.remove('grid');
    benefitContainer.classList.remove('hidden');
    // Run tariff benefit comparison calculation
    runDaysComparison();
  } else {
    proRataRow.classList.add('hidden');
    proRataRow.classList.remove('grid');
    benefitContainer.classList.add('hidden');
  }
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
    const energyEl = document.getElementById('resEnergy');
    const fixedEl = document.getElementById('resFixed');
    const minRow = document.getElementById('resMinRow');

    if (r.min_charge_override) {
      if (minRow) {
        minRow.classList.remove('hidden');
        minRow.classList.add('flex');
      }
      energyEl.innerHTML = `<span class="text-slate-400 font-normal italic">OVERRIDDEN</span>`;
      fixedEl.innerHTML = `<span class="text-slate-400 font-normal italic">OVERRIDDEN</span>`;
      document.getElementById('resMin').innerHTML = `\u20B9 ${(r.minimum_charge || 0).toFixed(2)}`;
    } else {
      if (minRow) {
        minRow.classList.add('hidden');
        minRow.classList.remove('flex');
      }
      energyEl.innerHTML = `\u20B9 ${r.energy_charge.toFixed(2)}`;
      fixedEl.innerHTML = `\u20B9 ${r.fixed_charge.toFixed(2)}`;
      document.getElementById('resMin').innerHTML = `\u20B9 ${(r.minimum_charge || 0).toFixed(2)}`;
    }

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

    // Auto-sync baseline comparator values if comparator is visible
    syncComparatorBaseline(payload, r);
  }
}

let isSyncingComparator = false;
function syncComparatorBaseline(payload, r) {
  if (isSyncingComparator) return;
  const container = document.getElementById('tariffBenefitContainer');
  if (!container || container.classList.contains('hidden')) return;

  const daysAEl = document.getElementById('compDaysA');
  const unitsAEl = document.getElementById('compUnitsA');
  if (!daysAEl || !unitsAEl) return;

  // Let baseline follow main calculator unless user has independently typed in comparator
  if (document.activeElement !== daysAEl && document.activeElement !== unitsAEl &&
      document.activeElement !== document.getElementById('compDaysB') &&
      document.activeElement !== document.getElementById('compUnitsB')) {
    daysAEl.value = payload.cycle === 'Quarterly' ? 90 : (payload.cycle === 'Monthly' ? 30 : payload.days);
    unitsAEl.value = payload.units;
    runDaysComparison(true);
  }
}

async function runDaysComparison(fromSync = false) {
  const cat = document.getElementById('billCategory').value;
  const phase = document.querySelector('input[name="phase"]:checked').value;
  const load = parseFloat(document.getElementById('billLoad').value || 1.0);
  const loadUnit = document.getElementById('billLoadUnit').value;
  const mvca = parseFloat(document.getElementById('billMvca').value || 0);
  const meterRent = document.getElementById('billMeterRent').checked;
  const isMonsoon = document.getElementById('billMonsoon').checked;

  const daysA = parseInt(document.getElementById('compDaysA').value || 90);
  let unitsA = parseInt(document.getElementById('compUnitsA').value || 0);

  const daysB = parseInt(document.getElementById('compDaysB').value || 354);
  let unitsB = parseInt(document.getElementById('compUnitsB').value || 0);

  // Calculate Scenario A
  const pA = {
    category: cat,
    cycle: 'Pro-Rata',
    days: daysA,
    units: unitsA,
    load: load,
    load_unit: loadUnit,
    mvca: mvca,
    meter_rent_applicable: meterRent,
    is_monsoon: isMonsoon,
    phase: phase
  };

  // Calculate Scenario B
  const pB = {
    category: cat,
    cycle: 'Pro-Rata',
    days: daysB,
    units: unitsB,
    load: load,
    load_unit: loadUnit,
    mvca: mvca,
    meter_rent_applicable: meterRent,
    is_monsoon: isMonsoon,
    phase: phase
  };

  const [resA, resB] = await Promise.all([
    callAPI('calculate_bill', pA),
    callAPI('calculate_bill', pB)
  ]);

  if (resA && resA.success && resB && resB.success) {
    const a = resA.result;
    const b = resB.result;

    // Populate Scenario A outputs
    document.getElementById('compEnergyFixedA').innerHTML = `\u20B9 ${(a.energy_charge + a.fixed_charge).toFixed(2)}`;
    document.getElementById('compReliefA').innerHTML = `- \u20B9 ${a.gov_relief.toFixed(2)}`;
    document.getElementById('compEdA').innerHTML = `\u20B9 ${a.ed_charge.toFixed(2)}`;
    document.getElementById('compNetA').innerHTML = `\u20B9 ${a.rounded_bill.toLocaleString('en-IN')}`;
    const dailyA = daysA > 0 ? (a.rounded_bill / daysA) : 0;
    document.getElementById('compDailyA').innerHTML = `\u20B9 ${dailyA.toFixed(2)}/day`;

    // Populate Scenario B outputs
    document.getElementById('compEnergyFixedB').innerHTML = `\u20B9 ${(b.energy_charge + b.fixed_charge).toFixed(2)}`;
    document.getElementById('compReliefB').innerHTML = `- \u20B9 ${b.gov_relief.toFixed(2)}`;
    document.getElementById('compEdB').innerHTML = `\u20B9 ${b.ed_charge.toFixed(2)}`;
    document.getElementById('compNetB').innerHTML = `\u20B9 ${b.rounded_bill.toLocaleString('en-IN')}`;
    const dailyB = daysB > 0 ? (b.rounded_bill / daysB) : 0;
    document.getElementById('compDailyB').innerHTML = `\u20B9 ${dailyB.toFixed(2)}/day`;

    // Variance summary
    const diffNet = b.rounded_bill - a.rounded_bill;
    const sign = diffNet >= 0 ? '+' : '-';
    document.getElementById('compDiffNet').innerHTML = `${sign}\u20B9 ${Math.abs(diffNet).toLocaleString('en-IN')}`;
    
    const dailyDiff = dailyB - dailyA;
    const dailyPct = dailyA > 0 ? ((dailyDiff / dailyA) * 100) : 0;
    const badge = document.getElementById('compDailyDeltaBadge');
    
    if (Math.abs(dailyPct) < 0.1) {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300";
      badge.innerText = `Equal Daily Rate (\u20B9 ${dailyB.toFixed(2)}/d)`;
    } else if (dailyDiff > 0) {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300";
      badge.innerText = `+${dailyPct.toFixed(1)}% daily avg (+ \u20B9 ${dailyDiff.toFixed(2)}/d)`;
    } else {
      badge.className = "px-2.5 py-1 rounded-lg text-xs font-bold font-mono bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300";
      badge.innerText = `${dailyPct.toFixed(1)}% daily avg (- \u20B9 ${Math.abs(dailyDiff).toFixed(2)}/d)`;
    }

    document.getElementById('compDiffTitle').innerText = `Diff: ${daysB} Days (\u20B9 ${b.rounded_bill.toLocaleString('en-IN')}) vs ${daysA} Days (\u20B9 ${a.rounded_bill.toLocaleString('en-IN')})`;
    document.getElementById('compDiffSubtitle').innerText = `Slab multipliers: ${a.months_multiplier} vs ${b.months_multiplier} mo | Monthly equivalent: \u20B9 ${(dailyA * 30).toFixed(0)} vs \u20B9 ${(dailyB * 30).toFixed(0)}/mo`;
  }
}
window.runDaysComparison = runDaysComparison;

// --- Theft Calculations ---
function formatDecimalHours(h) {
  const totalMinutes = Math.max(0, Math.min(24 * 60, Math.round(h * 60)));
  const hrs = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return `(${String(hrs).padStart(2, '0')}h ${String(mins).padStart(2, '0')}m)`;
}

let latestTheftRes = null;

function validateHoursAndRun(inputEl) {
  let val = parseFloat(inputEl.value);
  if (isNaN(val)) val = 0;
  if (val > 24) {
    inputEl.value = 24;
  } else if (val < 0) {
    inputEl.value = 0;
  }
  runTheftCalc();
}
window.validateHoursAndRun = validateHoursAndRun;

async function runTheftCalc() {
  let provHours = parseFloat(document.getElementById('theftProvHours').value || 24);
  let finalHours = parseFloat(document.getElementById('theftFinalHours').value || 19);

  if (provHours > 24) { provHours = 24; document.getElementById('theftProvHours').value = 24; }
  if (finalHours > 24) { finalHours = 24; document.getElementById('theftFinalHours').value = 24; }

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
    latestTheftRes = res;
    const p = res.provisional || res.prov;
    document.getElementById('provUnits').innerText = `${p.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('provEnergy').innerHTML = `\u20B9 ${p.penal_energy_charge.toFixed(2)}`;
    document.getElementById('provFixed').innerHTML = `\u20B9 ${p.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('provEd').innerHTML = `\u20B9 ${p.electricity_duty.toFixed(2)}`;
    document.getElementById('provGross').innerHTML = `\u20B9 ${p.gross_assessment.toFixed(2)}`;
    document.getElementById('provAdj').innerHTML = `- \u20B9 ${p.total_adjustments.toFixed(2)}`;
    const pRounded = Math.ceil(p.net_assessment !== undefined ? p.net_assessment : p.net);
    document.getElementById('provNet').innerHTML = `\u20B9 ${pRounded.toLocaleString('en-IN')}`;

    const f = res.final;
    document.getElementById('finalUnits').innerText = `${f.assessed_units.toLocaleString('en-IN')} kWh`;
    document.getElementById('finalEnergy').innerHTML = `\u20B9 ${f.penal_energy_charge.toFixed(2)}`;
    document.getElementById('finalFixed').innerHTML = `\u20B9 ${f.penal_fixed_charge.toFixed(2)}`;
    document.getElementById('finalEd').innerHTML = `\u20B9 ${f.electricity_duty.toFixed(2)}`;
    document.getElementById('finalGross').innerHTML = `\u20B9 ${f.gross_assessment.toFixed(2)}`;
    document.getElementById('finalAdj').innerHTML = `- \u20B9 ${f.total_adjustments.toFixed(2)}`;
    const fRounded = Math.ceil(f.net_assessment !== undefined ? f.net_assessment : f.net);
    document.getElementById('finalNet').innerHTML = `\u20B9 ${fRounded.toLocaleString('en-IN')}`;

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

    updateTheftFormulaBreakdown(p.breakdown || {});
  }
}

function updateTheftFormulaBreakdown(b) {
  if (!b || !b.units) return;
  const unitsTrace = document.getElementById('breakdownUnitsCalc');
  if (unitsTrace) {
    unitsTrace.innerHTML = `<b>Calculation:</b> ${b.load_kva} kVA × 0.85 PF × ${b.lf} LF × ${b.days} Days × ${b.hours} Hrs = <b>${b.units.toLocaleString('en-IN')} Units</b> (${b.units_per_month} units/mo over ${b.months} months)`;
  }

  const energyTrace = document.getElementById('breakdownEnergyCalc');
  if (energyTrace) {
    energyTrace.innerHTML = `<b>Calculation:</b> \u20B9 ${b.normal_monthly_energy.toFixed(2)} / month × ${b.months} months = \u20B9 ${b.normal_total_energy.toFixed(2)} normal × 2 = <b>\u20B9 ${b.penal_energy.toFixed(2)}</b>`;
  }

  const fixedTrace = document.getElementById('breakdownFixedCalc');
  if (fixedTrace) {
    fixedTrace.innerHTML = `<b>Calculation:</b> ${b.rounded_load} kVA × \u20B9 ${b.fixed_rate}/mo × ${b.rounded_months} billing months = \u20B9 ${b.normal_fc.toFixed(2)} normal × 2 = <b>\u20B9 ${b.penal_fc.toFixed(2)}</b>`;
  }

  const edTrace = document.getElementById('breakdownEdCalc');
  if (edTrace) {
    edTrace.innerHTML = `<b>Calculation:</b> (\u20B9 ${b.penal_energy.toFixed(2)} energy + \u20B9 ${b.penal_fc.toFixed(2)} fixed) × ${b.ed_percent}% = <b>\u20B9 ${b.ed_amount.toFixed(2)}</b>`;
  }
}

function toggleTheftBreakdownModal(show) {
  const modal = document.getElementById('theftBreakdownModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    if (latestTheftRes && latestTheftRes.prov && latestTheftRes.prov.breakdown) {
      updateTheftFormulaBreakdown(latestTheftRes.prov.breakdown);
    }
  } else {
    modal.classList.add('hidden');
  }
  safeCreateIcons();
}
window.toggleTheftBreakdownModal = toggleTheftBreakdownModal;

let estimatedLoadKva = 0;
function toggleReverseLoadModal(show) {
  const modal = document.getElementById('reverseLoadModal');
  if (!modal) return;
  if (show) {
    modal.classList.remove('hidden');
    // Pre-fill with current days/hours from theft screen if empty
    const theftHours = document.getElementById('theftProvHours');
    if (theftHours && theftHours.value) {
      document.getElementById('revHours').value = Math.min(24, parseFloat(theftHours.value));
    }
  } else {
    modal.classList.add('hidden');
  }
  safeCreateIcons();
}
window.toggleReverseLoadModal = toggleReverseLoadModal;

async function calculateReverseLoad() {
  const targetAmount = parseFloat(document.getElementById('revTargetAmount').value || 0);
  if (targetAmount <= 0) {
    showToast('Please enter an assessment amount greater than 0', 'warning');
    return;
  }

  let hours = parseFloat(document.getElementById('revHours').value || 24);
  if (hours > 24) { hours = 24; document.getElementById('revHours').value = 24; }
  const days = parseInt(document.getElementById('revDays').value || 365);

  const payload = {
    target_amount: targetAmount,
    hours: hours,
    days: days,
    category: document.getElementById('theftCategory').value,
    consumer_type: document.getElementById('theftConsumerType').value,
    adj_energy: parseFloat(document.getElementById('theftAdjEnergy').value || 0),
    adj_fixed: parseFloat(document.getElementById('theftAdjFixed').value || 0),
    adj_ed: parseFloat(document.getElementById('theftAdjEd').value || 0)
  };

  const res = await callAPI('calculate_theft_reverse_load', payload);
  if (res && res.success) {
    estimatedLoadKva = res.load_kva;
    document.getElementById('revLoadKva').innerText = `${res.load_kva.toFixed(2)} kVA`;
    document.getElementById('revLoadKw').innerText = `(${res.load_kw.toFixed(2)} kW @ 0.85 PF)`;
    document.getElementById('revGross').innerText = `\u20B9 ${Math.round(res.resulting_gross).toLocaleString('en-IN')}`;
    document.getElementById('revUnits').innerText = `${res.assessed_units.toLocaleString('en-IN')} kWh`;
    showToast(`Estimated Load: ${res.load_kva.toFixed(2)} kVA (${res.load_kw.toFixed(2)} kW)`, 'success');
  } else {
    showToast(res ? res.error : 'Failed to calculate load', 'error');
  }
}
window.calculateReverseLoad = calculateReverseLoad;

function applyEstimatedLoadToTheft() {
  if (estimatedLoadKva <= 0) {
    showToast('Please calculate an estimated load first', 'warning');
    return;
  }
  document.getElementById('theftLoad').value = estimatedLoadKva.toFixed(2);
  document.getElementById('theftLoadUnit').value = 'kVA';
  toggleReverseLoadModal(false);
  runTheftCalc();
  showToast(`Applied ${estimatedLoadKva.toFixed(2)} kVA to Connected Load`, 'success');
}
window.applyEstimatedLoadToTheft = applyEstimatedLoadToTheft;

