import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tariff_manager

# Load the global tariff dictionary
TARIFF_DATA = tariff_manager.load_tariff()

def calculate_slab_bill(monthly_units, category_data):
    """Calculates the cascading energy charge for Consumers."""
    charge = 0.0
    u = monthly_units
    
    # Handle normal slabs
    if "slabs" in category_data:
        for slab in category_data["slabs"]:
            if u <= 0: break
            limit = slab["limit"]
            rate = slab["rate"]
            if limit is None:
                charge += u * rate
                u = 0
            else:
                slab_units = min(u, limit)
                charge += slab_units * rate
                u -= slab_units
    # Handle TOD categories safely
    elif "tod_slabs" in category_data:
        # For consumer bypassing meter on TOD, charge at base Normal rate
        charge = u * category_data["tod_slabs"].get("Normal", 0.0)
        
    return charge

def get_highest_slab_rate(category_data):
    """Finds the maximum rate in the category for Non-Consumers."""
    if "slabs" in category_data:
        return max(slab["rate"] for slab in category_data["slabs"])
    elif "tod_slabs" in category_data:
        return max(category_data["tod_slabs"].values())
    return 0.0

def get_ed_rate(monthly_units, category_data):
    """Finds the correct Electricity Duty percentage based on Govt slabs."""
    for slab in category_data.get("ed_slabs", []):
        if slab["limit"] is None or monthly_units <= slab["limit"]:
            return slab["rate"]
    return 0.0

def compute_assessment(category, load_kva, days, hours, consumer_type):
    """The master WBSEDCL math engine."""
    cat_data = TARIFF_DATA[category]
    pf = 0.85
    
    # CRITICAL FIX: Dynamically apply WBSEDCL Load Factors if missing from JSON
    lf = cat_data.get("load_factor", 0.5 if "domestic" in category.lower() else 0.75)
    
    months = days / (365 / 12)  
    
    # Total units (WBSEDCL rounds to nearest integer)
    total_units = round(load_kva * pf * lf * days * hours)
    units_per_month = total_units / months if months > 0 else 0
    
    # ---------------------------------------------------------
    # ENERGY CHARGE LOGIC
    # ---------------------------------------------------------
    if consumer_type == "Non-Consumer":
        # Hooking: Assessed entirely at the highest slab rate
        highest_rate = get_highest_slab_rate(cat_data)
        normal_monthly_charge = units_per_month * highest_rate
    else:
        # Bypassing: Assessed using cascading slabs
        normal_monthly_charge = calculate_slab_bill(units_per_month, cat_data)
        
    normal_total_charge = normal_monthly_charge * months
    penal_energy_charge = normal_total_charge * 2
    
    # ---------------------------------------------------------
    # FIXED CHARGE LOGIC
    # Both Consumers and Non-Consumers pay Fixed Charge on Assessed Load
    # ---------------------------------------------------------
    normal_fc = load_kva * cat_data["fixed_charge"] * months
    penal_fc = normal_fc * 2 
    
    # ED applied on combined Energy + Fixed
    ed_percent = get_ed_rate(units_per_month, cat_data)
    total_ed = (penal_energy_charge + penal_fc) * ed_percent
    
    gross_bill = penal_energy_charge + penal_fc + total_ed
    
    return {
        "units": total_units,
        "energy": penal_energy_charge,
        "fixed": penal_fc,
        "ed_percent": ed_percent,
        "ed": total_ed,
        "gross": gross_bill
    }

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

def reset_adjustments(*args):
    """Resets the manual deductions if the core parameters change."""
    adj_e_var.set("0")
    adj_f_var.set("0")
    adj_ed_var.set("0")
    calculate_all()

def toggle_consumer_mode(*args):
    """Locks/Unlocks adjustments based on Consumer/Non-Consumer status."""
    if consumer_type_var.get() == "Non-Consumer":
        adj_energy_entry.config(state="disabled")
        adj_fixed_entry.config(state="disabled")
        adj_ed_entry.config(state="disabled")
        reset_adjustments()
    else:
        adj_energy_entry.config(state="normal")
        adj_fixed_entry.config(state="normal")
        adj_ed_entry.config(state="normal")
        calculate_all()

def calculate_all(*args):
    """The real-time calculation engine."""
    category_name = category_var.get()
    cons_type = consumer_type_var.get()
    
    # Handle kW to KVA Conversion Automatically
    raw_load = get_safe_float(load_var)
    unit_type = load_unit_var.get()
    load_kva = (raw_load / 0.85) if unit_type == "kW" else raw_load
    
    p_days = get_safe_int(p_days_var)
    p_hours = get_safe_int(p_hours_var)
    f_days = get_safe_int(f_days_var)
    f_hours = get_safe_int(f_hours_var)
    
    # Adjustments
    adj_e = get_safe_float(adj_e_var)
    adj_f = get_safe_float(adj_f_var)
    adj_ed = get_safe_float(adj_ed_var)
    total_adj = adj_e + adj_f + adj_ed

    # Compute
    prov = compute_assessment(category_name, load_kva, p_days, p_hours, cons_type)
    final = compute_assessment(category_name, load_kva, f_days, f_hours, cons_type)

    prov_net = prov['gross'] - total_adj
    final_net = final['gross'] - total_adj

    # Update Provisional Table
    p_val_units.config(text=f"{prov['units']:,} kWh")
    p_val_energy.config(text=f"₹ {prov['energy']:,.2f}")
    p_val_fc.config(text=f"₹ {prov['fixed']:,.2f}")
    p_val_ed.config(text=f"₹ {prov['ed']:,.2f}  ({prov['ed_percent']*100:.0f}%)")
    p_val_gross.config(text=f"₹ {prov['gross']:,.2f}")
    p_val_adj.config(text=f"- ₹ {total_adj:,.2f}")
    p_val_net.config(text=f"₹ {prov_net:,.2f}")

    # Update Final Table
    f_val_units.config(text=f"{final['units']:,} kWh")
    f_val_energy.config(text=f"₹ {final['energy']:,.2f}")
    f_val_fc.config(text=f"₹ {final['fixed']:,.2f}")
    f_val_ed.config(text=f"₹ {final['ed']:,.2f}  ({final['ed_percent']*100:.0f}%)")
    f_val_gross.config(text=f"₹ {final['gross']:,.2f}")
    
    # Mirror Adjustments to Final Side
    f_adj_e_lbl.config(text=f"₹ {adj_e:,.2f}")
    f_adj_f_lbl.config(text=f"₹ {adj_f:,.2f}")
    f_adj_ed_lbl.config(text=f"₹ {adj_ed:,.2f}")
    f_val_adj.config(text=f"- ₹ {total_adj:,.2f}")
    f_val_net.config(text=f"₹ {final_net:,.2f}")

    # Difference
    diff_rs = prov_net - final_net
    diff_pct = (diff_rs / prov_net * 100) if prov_net > 0 else 0
    diff_lbl.config(text=f"Final Assessment Relief:  ₹ {diff_rs:,.2f}   ({diff_pct:.2f}%)")

# --- UI SETUP ---
app = ttk.Window(themename="cosmo") 
app.title("Real-Time WBSEDCL Assessor")
app.geometry("1050x760")

# Fonts
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_VALUE = ("Segoe UI", 10, "bold")
FONT_GROSS = ("Segoe UI", 11, "bold")
FONT_NET = ("Segoe UI", 14, "bold")

main_frame = ttk.Frame(app)
main_frame.pack(fill=BOTH, expand=YES, padx=15, pady=15)

# ================= TOP SECTION (CORE VARIABLES) =================
top_frame = ttk.Frame(main_frame)
top_frame.pack(fill=X, pady=(0, 15))

ttk.Label(top_frame, text="Section 135 Theft Assessment Calculator", font=FONT_TITLE, bootstyle=PRIMARY).pack(pady=(0, 15))

input_bar = ttk.Frame(top_frame)
input_bar.pack()

# Variables
category_var = ttk.StringVar()
consumer_type_var = ttk.StringVar(value="Consumer")
load_var = ttk.StringVar(value="4.38")
load_unit_var = ttk.StringVar(value="KVA") 

p_days_var = ttk.StringVar(value="365")
p_hours_var = ttk.StringVar(value="24")
f_days_var = ttk.StringVar(value="365")
f_hours_var = ttk.StringVar(value="19")
adj_e_var = ttk.StringVar(value="0")
adj_f_var = ttk.StringVar(value="0")
adj_ed_var = ttk.StringVar(value="0")

ttk.Label(input_bar, text="Offender Type:", font=FONT_LABEL).grid(row=0, column=0, padx=5)
ttk.Radiobutton(input_bar, text="Consumer", variable=consumer_type_var, value="Consumer", bootstyle="info").grid(row=0, column=1, padx=5)
ttk.Radiobutton(input_bar, text="Non-Consumer", variable=consumer_type_var, value="Non-Consumer", bootstyle="warning").grid(row=0, column=2, padx=5)

ttk.Label(input_bar, text="Tariff Category:", font=FONT_LABEL).grid(row=0, column=3, padx=(25,5))
category_cb = ttk.Combobox(input_bar, textvariable=category_var, values=list(TARIFF_DATA.keys()), state="readonly", width=25)
if list(TARIFF_DATA.keys()): category_cb.current(0)
category_cb.grid(row=0, column=4, padx=5)

ttk.Label(input_bar, text="Assessed Load:", font=FONT_LABEL).grid(row=0, column=5, padx=(25,5))
ttk.Entry(input_bar, textvariable=load_var, justify="center", width=8).grid(row=0, column=6, padx=2)
unit_cb = ttk.Combobox(input_bar, textvariable=load_unit_var, values=["KVA", "kW"], state="readonly", width=5)
unit_cb.grid(row=0, column=7, padx=2)

# ================= MIDDLE PANELS (PERFECT SYMMETRY GRID) =================
panels_frame = ttk.Frame(main_frame)
panels_frame.pack(fill=BOTH, expand=YES)

panels_frame.columnconfigure(0, weight=1, uniform="pane")
panels_frame.columnconfigure(1, weight=1, uniform="pane")

def create_table_row(parent, row, label, is_gross=False, is_net=False):
    font_lbl = FONT_LABEL
    font_val = FONT_NET if is_net else (FONT_GROSS if is_gross else FONT_VALUE)
    
    ttk.Label(parent, text=label, font=font_lbl).grid(row=row, column=0, sticky=W, padx=10, pady=4)
    val_lbl = ttk.Label(parent, text="₹ 0.00", font=font_val)
    val_lbl.grid(row=row, column=1, sticky=E, padx=10, pady=4)
    
    ttk.Separator(parent, orient=HORIZONTAL).grid(row=row+1, column=0, columnspan=2, sticky=EW, pady=2)
    return val_lbl

# ----------------- LEFT: PROVISIONAL -----------------
prov_frame = ttk.LabelFrame(panels_frame, text=" PROVISIONAL ASSESSMENT ")
prov_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), ipadx=10, ipady=10)

p_inp_frame = ttk.Frame(prov_frame)
p_inp_frame.pack(fill=X, pady=5)
p_inp_frame.columnconfigure(1, weight=1)
p_inp_frame.columnconfigure(3, weight=1)

ttk.Label(p_inp_frame, text="Days:", font=FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
ttk.Entry(p_inp_frame, textvariable=p_days_var, width=10, justify="right").grid(row=0, column=1, sticky=E, padx=10)
ttk.Label(p_inp_frame, text="Hours/Day:", font=FONT_LABEL).grid(row=0, column=2, sticky=W, padx=10)
ttk.Entry(p_inp_frame, textvariable=p_hours_var, width=10, justify="right").grid(row=0, column=3, sticky=E, padx=10)

ttk.Separator(prov_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

ttk.Label(prov_frame, text="Deductions from Paid Bills (Manual)", font=("Segoe UI", 10, "bold"), bootstyle=SECONDARY).pack(anchor=W, padx=10, pady=(0,5))
adj_frame = ttk.Frame(prov_frame)
adj_frame.pack(fill=X)
adj_frame.columnconfigure(1, weight=1)

adj_frame.rowconfigure(0, minsize=35)
adj_frame.rowconfigure(1, minsize=35)
adj_frame.rowconfigure(2, minsize=35)

ttk.Label(adj_frame, text="Energy Charge (₹):", font=FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
adj_energy_entry = ttk.Entry(adj_frame, textvariable=adj_e_var, width=14, justify="right")
adj_energy_entry.grid(row=0, column=1, sticky=E, padx=10)

ttk.Label(adj_frame, text="Fixed/Demand (₹):", font=FONT_LABEL).grid(row=1, column=0, sticky=W, padx=10)
adj_fixed_entry = ttk.Entry(adj_frame, textvariable=adj_f_var, width=14, justify="right")
adj_fixed_entry.grid(row=1, column=1, sticky=E, padx=10)

ttk.Label(adj_frame, text="Electricity Duty (₹):", font=FONT_LABEL).grid(row=2, column=0, sticky=W, padx=10)
adj_ed_entry = ttk.Entry(adj_frame, textvariable=adj_ed_var, width=14, justify="right")
adj_ed_entry.grid(row=2, column=1, sticky=E, padx=10)

ttk.Separator(prov_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

p_table = ttk.Frame(prov_frame)
p_table.pack(fill=BOTH, expand=YES)
p_table.columnconfigure(1, weight=1)

p_val_units = create_table_row(p_table, 0, "Total Units:")
p_val_energy = create_table_row(p_table, 2, "Energy Charge (Penal):")
p_val_fc = create_table_row(p_table, 4, "Fixed Charge (Penal):")
p_val_ed = create_table_row(p_table, 6, "Electricity Duty:")
p_val_gross = create_table_row(p_table, 8, "GROSS BILL:", is_gross=True)
p_val_adj = create_table_row(p_table, 10, "Less: Total Deductions:")
p_val_net = create_table_row(p_table, 12, "NET PAYABLE:", is_net=True)
p_val_net.configure(bootstyle=WARNING)

# ----------------- RIGHT: FINAL -----------------
final_frame = ttk.LabelFrame(panels_frame, text=" FINAL ASSESSMENT ")
final_frame.grid(row=0, column=1, sticky=NSEW, padx=(8, 0), ipadx=10, ipady=10)

f_inp_frame = ttk.Frame(final_frame)
f_inp_frame.pack(fill=X, pady=5)
f_inp_frame.columnconfigure(1, weight=1)
f_inp_frame.columnconfigure(3, weight=1)

ttk.Label(f_inp_frame, text="Days:", font=FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
ttk.Entry(f_inp_frame, textvariable=f_days_var, width=10, justify="right").grid(row=0, column=1, sticky=E, padx=10)
ttk.Label(f_inp_frame, text="Hours/Day:", font=FONT_LABEL).grid(row=0, column=2, sticky=W, padx=10)
ttk.Entry(f_inp_frame, textvariable=f_hours_var, width=10, justify="right").grid(row=0, column=3, sticky=E, padx=10)

ttk.Separator(final_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

ttk.Label(final_frame, text="Deductions Applied (Auto-Mirrored)", font=("Segoe UI", 10, "bold"), bootstyle=SECONDARY).pack(anchor=W, padx=10, pady=(0,5))
f_adj_frame = ttk.Frame(final_frame)
f_adj_frame.pack(fill=X)
f_adj_frame.columnconfigure(1, weight=1)

f_adj_frame.rowconfigure(0, minsize=35)
f_adj_frame.rowconfigure(1, minsize=35)
f_adj_frame.rowconfigure(2, minsize=35)

ttk.Label(f_adj_frame, text="Energy Charge (₹):", font=FONT_LABEL, foreground="gray").grid(row=0, column=0, sticky=W, padx=10)
f_adj_e_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=FONT_VALUE, foreground="gray")
f_adj_e_lbl.grid(row=0, column=1, sticky=E, padx=10)

ttk.Label(f_adj_frame, text="Fixed/Demand (₹):", font=FONT_LABEL, foreground="gray").grid(row=1, column=0, sticky=W, padx=10)
f_adj_f_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=FONT_VALUE, foreground="gray")
f_adj_f_lbl.grid(row=1, column=1, sticky=E, padx=10)

ttk.Label(f_adj_frame, text="Electricity Duty (₹):", font=FONT_LABEL, foreground="gray").grid(row=2, column=0, sticky=W, padx=10)
f_adj_ed_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=FONT_VALUE, foreground="gray")
f_adj_ed_lbl.grid(row=2, column=1, sticky=E, padx=10)

ttk.Separator(final_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

f_table = ttk.Frame(final_frame)
f_table.pack(fill=BOTH, expand=YES)
f_table.columnconfigure(1, weight=1)

f_val_units = create_table_row(f_table, 0, "Total Units:")
f_val_energy = create_table_row(f_table, 2, "Energy Charge (Penal):")
f_val_fc = create_table_row(f_table, 4, "Fixed Charge (Penal):")
f_val_ed = create_table_row(f_table, 6, "Electricity Duty:")
f_val_gross = create_table_row(f_table, 8, "GROSS BILL:", is_gross=True)
f_val_adj = create_table_row(f_table, 10, "Less: Total Deductions:")
f_val_net = create_table_row(f_table, 12, "NET PAYABLE:", is_net=True)
f_val_net.configure(bootstyle=SUCCESS)

# ================= BOTTOM SECTION (NEW BANNER PLACEMENT) =================
summary_frame = ttk.Frame(main_frame)
summary_frame.pack(fill=X, pady=(15, 0))

ttk.Separator(summary_frame, orient=HORIZONTAL).pack(fill=X)
diff_lbl = ttk.Label(summary_frame, text="Final Assessment Relief: ₹ 0.00  (0.00%)", font=("Segoe UI", 12, "bold"), bootstyle=PRIMARY)
diff_lbl.pack(pady=10)
ttk.Separator(summary_frame, orient=HORIZONTAL).pack(fill=X)

# --- REAL-TIME BINDINGS ---
category_var.trace_add("write", reset_adjustments)
load_var.trace_add("write", reset_adjustments)
consumer_type_var.trace_add("write", toggle_consumer_mode)
load_unit_var.trace_add("write", calculate_all)

for var in [p_days_var, p_hours_var, f_days_var, f_hours_var, adj_e_var, adj_f_var, adj_ed_var]:
    var.trace_add("write", calculate_all)

app.after(100, calculate_all)
app.mainloop()