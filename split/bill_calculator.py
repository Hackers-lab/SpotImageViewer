import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tariff_manager

# Load the global tariff dictionary
TARIFF_DATA = tariff_manager.load_tariff()

def get_safe_float(var):
    try:
        val = var.get().strip()
        return float(val) if val else 0.0
    except ValueError:
        return 0.0

def get_safe_int(var):
    try:
        val = var.get().strip()
        return int(val) if val else 0
    except ValueError:
        return 0

def calculate_state_subsidy(units, category_name, phase, months_multiplier):
    if "domestic" not in category_name.lower(): 
        return 0.0
        
    subsidy = 0.0
    u = units
    s1 = 34 * months_multiplier
    s2 = 26 * months_multiplier
    s3 = 40 * months_multiplier
    
    if u > 0:
        slab = min(u, s1)
        subsidy += slab * 0.90
        u -= slab
    if u > 0:
        slab = min(u, s2)
        subsidy += slab * 0.90
        u -= slab
    if u > 0:
        slab = min(u, s3)
        subsidy += slab * 0.74
        u -= slab
    if u > 0: 
        subsidy += u * 0.79
        
    if phase == "1-Phase": 
        subsidy += (10.0 * months_multiplier)
        
    return subsidy

def update_ui_visibility(*args):
    cat = category_var.get().lower()
    cycle = cycle_var.get()
    
    # Days Input Visibility
    if cycle == "Pro-Rata":
        days_input_frame.pack(side=LEFT, padx=(10, 0))
    else:
        days_input_frame.pack_forget()

    # TOD vs Normal Units
    if "tod" in cat:
        frame_normal_units.grid_remove()
        frame_tod_units.grid(row=6, column=0, columnspan=2, sticky=EW, pady=5)
    else:
        frame_tod_units.grid_remove()
        frame_normal_units.grid(row=6, column=0, columnspan=2, sticky=EW, pady=5)
        
    # Monsoon Checkbox
    if "agriculture" in cat and "tod" not in cat:
        monsoon_frame.grid(row=5, column=0, columnspan=2, sticky=W, padx=10, pady=5)
    else:
        monsoon_frame.grid_remove()
        monsoon_var.set(False)

def calculate_all(*args):
    category = category_var.get()
    if not category or category not in TARIFF_DATA: return
    cat_data = TARIFF_DATA[category]
    cat_lower = category.lower()
    is_tod = "tod" in cat_lower
    
    # 1. Hybrid Multiplier Logic
    cycle = cycle_var.get()
    if cycle == "Quarterly":
        months_multiplier = 3.0
    elif cycle == "Monthly":
        months_multiplier = 1.0
    else: # Pro-Rata
        days_billed = get_safe_int(days_var)
        if days_billed <= 0: days_billed = 1
        months_multiplier = days_billed / 30.0
        
    phase = phase_var.get()
    mvca_rate = get_safe_float(mvca_var)
    
    # 2. Load Flooring Logic (<1 kVA treated as 1 kVA for Commercial)
    raw_load = get_safe_float(load_var)
    unit_type = load_unit_var.get()
    load_kva = (raw_load / 0.85) if unit_type == "kW" else raw_load
    if "commercial" in cat_lower and load_kva > 0 and load_kva < 1.0:
        load_kva = 1.0 
        
    # 3. Units & Energy Charge
    energy_charge = 0.0
    total_units = 0
    
    if is_tod:
        n = get_safe_int(tod_n_var); p = get_safe_int(tod_p_var); o = get_safe_int(tod_o_var)
        total_units = n + p + o
        if "tod_slabs" in cat_data:
            energy_charge += n * cat_data["tod_slabs"]["Normal"]
            energy_charge += p * cat_data["tod_slabs"]["Peak"]
            energy_charge += o * cat_data["tod_slabs"]["Off_Peak"]
    else:
        total_units = get_safe_int(units_var)
        
        # Apply the 2-paise Rural Commercial Bonus
        if "commercial" in cat_lower:
            max_bonus_units = 100 * months_multiplier
            bonus_units = min(total_units, max_bonus_units)
            energy_charge -= (bonus_units * 0.02)
            
        u = total_units
        for slab in cat_data.get("slabs", []):
            if u <= 0: break
            limit = slab["limit"]
            rate = slab["rate"]
            if limit is None:
                energy_charge += u * rate; u = 0
            else:
                slab_units = min(u, limit * months_multiplier)
                energy_charge += slab_units * rate; u -= slab_units
                
    # 4. Fixed Charge & Monsoon Discount
    base_fc = load_kva * cat_data["fixed_charge"] * months_multiplier
    if monsoon_var.get():
        base_fc = base_fc / 2.0
        
    # NEW: Restore the strict Fixed Charge Floor for Domestic consumers (₹30/month)
    if "domestic" in cat_lower:
        base_fc = max(base_fc, 30.0 * months_multiplier)
        
    # 5. Minimum Charge Override Verification (For Industry)
    min_floor = load_kva * cat_data.get("min_charge", 0.0) * months_multiplier
    # Only override if the total bill is lower than the floor AND it's an industry-style floor
    is_minimum = (energy_charge + base_fc) < min_floor and min_floor > 100.0 
    
    if is_minimum:
        base_amount = min_floor
        val_energy.config(text="OVERRIDDEN", foreground="gray")
        val_fixed.config(text="OVERRIDDEN", foreground="gray")
        val_minimum.config(text=f"₹ {min_floor:,.2f}")
        val_minimum_row.grid()
    else:
        base_amount = energy_charge + base_fc
        val_energy.config(text=f"₹ {energy_charge:,.2f}", foreground="")
        val_fixed.config(text=f"₹ {base_fc:,.2f}", foreground="")
        val_minimum_row.grid_remove()

    # 6. Surcharges & Rent
    mvca_charge = total_units * mvca_rate
    meter_rent = 0.0
    if phase != "Own Meter":
        if is_tod:
            base_rent = 25.0
        elif "domestic" in cat_lower and phase == "1-Phase":
            base_rent = 10.0
        elif "commercial" in cat_lower and phase == "1-Phase":
            base_rent = 15.0
        else:
            base_rent = 50.0
            
        meter_rent = base_rent * months_multiplier
        
    # 7. Subsidy
    subsidy_amount = calculate_state_subsidy(total_units, category, phase, months_multiplier)
    
    # 8. Timely Rebate & Electricity Duty
    rebateable_amount = base_amount + mvca_charge
    timely_rebate = rebateable_amount * 0.01 
    
    # Domestic/Commercial pay ED on the Net Base. Industrial pays on Gross.
    if "domestic" in cat_lower or "commercial" in cat_lower:
        ed_base = base_amount - timely_rebate
    else:
        ed_base = base_amount
        
    ed_percent = 0.0
    
    # Pure JSON-driven ED Slabs (Cleaned up)
    for slab in cat_data.get("ed_slabs", []):
        scaled_limit = slab["limit"] * months_multiplier if slab["limit"] else None
        if scaled_limit is None or total_units <= scaled_limit:
            ed_percent = slab["rate"]; break
                
    total_ed = ed_base * ed_percent
    
    # 9. Gross & Remaining Rebates
    gross_bill = base_amount + mvca_charge + meter_rent + total_ed - subsidy_amount
    
    special_rebate = 0.0
    if ("domestic" in cat_lower or "commercial" in cat_lower) and months_multiplier > 2.0:
        special_rebate = total_units * 0.10
        
    net_after_timely = gross_bill - special_rebate - timely_rebate
    epay_rebate = net_after_timely * 0.01 if net_after_timely > 0 else 0.0
    total_rebates = special_rebate + timely_rebate + epay_rebate
    
    # --- UPDATE UI FINANCIALS ---
    val_mvca.config(text=f"₹ {mvca_charge:,.2f}")
    val_rent.config(text=f"₹ {meter_rent:,.2f}")
    val_subsidy.config(text=f"- ₹ {subsidy_amount:,.2f}" if subsidy_amount > 0 else "₹ 0.00", bootstyle=SUCCESS if subsidy_amount > 0 else DEFAULT)
    val_ed.config(text=f"₹ {total_ed:,.2f}  ({ed_percent*100:.2f}%)")
    val_gross.config(text=f"₹ {gross_bill:,.2f}")
    val_reb_spec.config(text=f"- ₹ {special_rebate:,.2f}")
    val_reb_time.config(text=f"- ₹ {timely_rebate:,.2f}")
    val_reb_epay.config(text=f"- ₹ {epay_rebate:,.2f}")
    val_net.config(text=f"₹ {round(gross_bill - total_rebates):,.2f}")

# --- UI SETUP ---
app = ttk.Window(themename="cosmo") 
app.title("Ultimate WBSEDCL Bill Estimator")
app.geometry("1100x800")

main_frame = ttk.Frame(app)
main_frame.pack(fill=BOTH, expand=YES, padx=20, pady=20)
ttk.Label(main_frame, text="Real-Time Standard Bill Estimator", font=("Segoe UI", 16, "bold"), bootstyle=PRIMARY).pack(pady=(0, 20))

panels_frame = ttk.Frame(main_frame)
panels_frame.pack(fill=BOTH, expand=YES)
panels_frame.columnconfigure(0, weight=1, uniform="pane")
panels_frame.columnconfigure(1, weight=1, uniform="pane")

# === LEFT PANEL ===
inp_frame = ttk.LabelFrame(panels_frame, text=" CONSUMER DETAILS & READINGS ")
inp_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 10), ipadx=15, ipady=15)

category_var = ttk.StringVar()
cycle_var = ttk.StringVar(value="Quarterly")
days_var = ttk.StringVar(value="30")
phase_var = ttk.StringVar(value="1-Phase")
load_var = ttk.StringVar(value="0.73")
load_unit_var = ttk.StringVar(value="KVA")
monsoon_var = ttk.BooleanVar(value=False)
units_var = ttk.StringVar(value="489")
tod_n_var = ttk.StringVar(value="0")
tod_p_var = ttk.StringVar(value="0")
tod_o_var = ttk.StringVar(value="0")
mvca_var = ttk.StringVar(value="0.00")

def create_input_row(parent, row, label, widget):
    ttk.Label(parent, text=label, font=("Segoe UI", 11)).grid(row=row, column=0, sticky=W, padx=10, pady=8)
    widget.grid(row=row, column=1, sticky=E, padx=10, pady=8)

cat_cb = ttk.Combobox(inp_frame, textvariable=category_var, values=list(TARIFF_DATA.keys()), state="readonly", width=25)
if list(TARIFF_DATA.keys()): cat_cb.current(0) 
create_input_row(inp_frame, 0, "Tariff Category:", cat_cb)

cycle_frame = ttk.Frame(inp_frame)
ttk.Radiobutton(cycle_frame, text="Monthly", variable=cycle_var, value="Monthly", bootstyle="info").pack(side=LEFT, padx=(0, 10))
ttk.Radiobutton(cycle_frame, text="Quarterly", variable=cycle_var, value="Quarterly", bootstyle="info").pack(side=LEFT, padx=(0, 10))
ttk.Radiobutton(cycle_frame, text="Pro-Rata", variable=cycle_var, value="Pro-Rata", bootstyle="info").pack(side=LEFT)

days_input_frame = ttk.Frame(cycle_frame)
ttk.Label(days_input_frame, text="Days:").pack(side=LEFT, padx=(0, 5))
ttk.Entry(days_input_frame, textvariable=days_var, width=5).pack(side=LEFT)
create_input_row(inp_frame, 1, "Billing Mode:", cycle_frame)

phase_frame = ttk.Frame(inp_frame)
ttk.Radiobutton(phase_frame, text="1-Phase", variable=phase_var, value="1-Phase").pack(side=LEFT, padx=(0, 5))
ttk.Radiobutton(phase_frame, text="3-Phase", variable=phase_var, value="3-Phase").pack(side=LEFT, padx=(0, 5))
ttk.Radiobutton(phase_frame, text="Own", variable=phase_var, value="Own Meter").pack(side=LEFT)
create_input_row(inp_frame, 2, "Meter Type:", phase_frame)

load_frame = ttk.Frame(inp_frame)
ttk.Entry(load_frame, textvariable=load_var, width=10, justify="right").pack(side=LEFT, padx=(0, 5))
ttk.Combobox(load_frame, textvariable=load_unit_var, values=["KVA", "kW"], state="readonly", width=5).pack(side=LEFT)
create_input_row(inp_frame, 3, "Contractual Load:", load_frame)

monsoon_frame = ttk.Checkbutton(inp_frame, text="Apply Monsoon Discount (Jul-Oct)", variable=monsoon_var, bootstyle="success-round-toggle")

frame_normal_units = ttk.Frame(inp_frame)
ttk.Label(frame_normal_units, text="Total Units Consumed:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky=W, padx=10)
ttk.Entry(frame_normal_units, textvariable=units_var, width=14, justify="right").grid(row=0, column=1, sticky=E, padx=10)

frame_tod_units = ttk.Frame(inp_frame)
ttk.Label(frame_tod_units, text="TOD Units [ N | P | O ]:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky=W, padx=10)
tod_inputs = ttk.Frame(frame_tod_units)
tod_inputs.grid(row=0, column=1, sticky=E, padx=10)
ttk.Entry(tod_inputs, textvariable=tod_n_var, width=5).pack(side=LEFT, padx=2)
ttk.Entry(tod_inputs, textvariable=tod_p_var, width=5).pack(side=LEFT, padx=2)
ttk.Entry(tod_inputs, textvariable=tod_o_var, width=5).pack(side=LEFT, padx=2)

create_input_row(inp_frame, 7, "MVCA Rate (₹):", ttk.Entry(inp_frame, textvariable=mvca_var, width=14, justify="right"))

# === RIGHT PANEL ===
out_frame = ttk.LabelFrame(panels_frame, text=" ITEMIZED BILL BREAKDOWN ")
out_frame.grid(row=0, column=1, sticky=NSEW, padx=(10, 0), ipadx=15, ipady=15)
out_frame.columnconfigure(1, weight=1)

def create_table_row(parent, row, label, is_bold=False):
    font = ("Segoe UI", 12, "bold") if is_bold else ("Segoe UI", 11, "bold")
    ttk.Label(parent, text=label, font=("Segoe UI", 11)).grid(row=row, column=0, sticky=W, padx=10, pady=4)
    val = ttk.Label(parent, text="₹ 0.00", font=font)
    val.grid(row=row, column=1, sticky=E, padx=10, pady=4)
    ttk.Separator(parent, orient=HORIZONTAL).grid(row=row+1, column=0, columnspan=2, sticky=EW, pady=2)
    return val

val_energy = create_table_row(out_frame, 0, "Energy Charge:")
val_fixed = create_table_row(out_frame, 2, "Fixed Charge:")

val_minimum_row = ttk.Frame(out_frame)
ttk.Label(val_minimum_row, text="MINIMUM CHARGE APPLIED:", font=("Segoe UI", 11, "bold"), bootstyle=DANGER).grid(row=0, column=0, sticky=W, padx=10, pady=4)
val_minimum = ttk.Label(val_minimum_row, text="₹ 0.00", font=("Segoe UI", 11, "bold"), bootstyle=DANGER)
val_minimum.grid(row=0, column=1, sticky=E, padx=10, pady=4)
val_minimum_row.grid(row=4, column=0, columnspan=2, sticky=EW)
val_minimum_row.columnconfigure(1, weight=1)

val_mvca = create_table_row(out_frame, 6, "MVCA Surcharge:")
val_rent = create_table_row(out_frame, 8, "Meter Rent:")
val_subsidy = create_table_row(out_frame, 10, "Govt. Subsidy / Relief:")
val_ed = create_table_row(out_frame, 12, "Electricity Duty (ED):")
val_gross = create_table_row(out_frame, 14, "GROSS BILL AMOUNT:", is_bold=True)

ttk.Label(out_frame, text="Deductions & Rebates", font=("Segoe UI", 9, "bold"), bootstyle=SECONDARY).grid(row=16, column=0, sticky=W, padx=10, pady=(10,0))
val_reb_spec = create_table_row(out_frame, 17, "Special Rebate:"); val_reb_spec.config(foreground="gray")
val_reb_time = create_table_row(out_frame, 19, "Timely Rebate (1%):"); val_reb_time.config(foreground="gray")
val_reb_epay = create_table_row(out_frame, 21, "e-Payment Rebate (1%):"); val_reb_epay.config(foreground="gray")

val_net = create_table_row(out_frame, 23, "ESTIMATED NET PAYABLE:", is_bold=True)
val_net.config(font=("Segoe UI", 18, "bold"), bootstyle=WARNING)

# Bindings
for var in [category_var, cycle_var, days_var, phase_var, load_var, load_unit_var, units_var, mvca_var, tod_n_var, tod_p_var, tod_o_var, monsoon_var]:
    var.trace_add("write", calculate_all)

category_var.trace_add("write", update_ui_visibility)
cycle_var.trace_add("write", update_ui_visibility)

# Init
update_ui_visibility()
app.after(100, calculate_all)
app.mainloop()