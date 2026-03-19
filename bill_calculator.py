import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tariff_manager

class BillCalculatorApp:
    def __init__(self, parent):
        self.tariff_data = tariff_manager.load_tariff()
        
        self.window = ttk.Toplevel(parent)
        self.window.title("Electricity Bill Calculator - SpotImageViewer")
        self.window.state('zoomed')

        # --- INSTANCE VARIABLES ---
        self.category_var = ttk.StringVar()
        self.cycle_var = ttk.StringVar(value="Quarterly")
        self.days_var = ttk.StringVar(value="30")
        self.phase_var = ttk.StringVar(value="1-Phase")
        self.load_var = ttk.StringVar(value="0")
        self.load_unit_var = ttk.StringVar(value="KVA")
        self.monsoon_var = ttk.BooleanVar(value=False)
        self.units_var = ttk.StringVar(value="0")
        self.tod_n_var = ttk.StringVar(value="0")
        self.tod_p_var = ttk.StringVar(value="0")
        self.tod_o_var = ttk.StringVar(value="0")
        self.mvca_var = ttk.StringVar(value="0.00")

        self.setup_ui()
        self.bind_traces()
        self.update_ui_visibility()
        self.window.after(100, self.calculate_all)

    def get_safe_float(self, var):
        try: return float(var.get().strip()) if var.get().strip() else 0.0
        except ValueError: return 0.0

    def get_safe_int(self, var):
        try: return int(var.get().strip()) if var.get().strip() else 0
        except ValueError: return 0

    def calculate_state_subsidy(self, units, category_name, phase, months_multiplier):
        if "domestic" not in category_name.lower(): return 0.0
        subsidy = 0.0
        u = units
        s1, s2, s3 = 34 * months_multiplier, 26 * months_multiplier, 40 * months_multiplier
        
        if u > 0: slab = min(u, s1); subsidy += slab * 0.90; u -= slab
        if u > 0: slab = min(u, s2); subsidy += slab * 0.90; u -= slab
        if u > 0: slab = min(u, s3); subsidy += slab * 0.74; u -= slab
        if u > 0: subsidy += u * 0.79
        if phase == "1-Phase": subsidy += (10.0 * months_multiplier)
        return subsidy

    def update_ui_visibility(self, *args):
        cat = self.category_var.get().lower()
        cycle = self.cycle_var.get()
        
        if cycle == "Pro-Rata": self.days_input_frame.pack(side=LEFT, padx=(10, 0))
        else: self.days_input_frame.pack_forget()

        if "tod" in cat:
            self.frame_normal_units.grid_remove()
            self.frame_tod_units.grid(row=6, column=0, columnspan=2, sticky=EW, pady=5)
        else:
            self.frame_tod_units.grid_remove()
            self.frame_normal_units.grid(row=6, column=0, columnspan=2, sticky=EW, pady=5)
            
        if "agriculture" in cat and "tod" not in cat:
            self.monsoon_frame.grid(row=5, column=0, columnspan=2, sticky=W, padx=10, pady=5)
        else:
            self.monsoon_frame.grid_remove()
            self.monsoon_var.set(False)

    def calculate_all(self, *args):
        category = self.category_var.get()
        if not category or category not in self.tariff_data: return
        cat_data = self.tariff_data[category]
        cat_lower = category.lower()
        is_tod = "tod" in cat_lower
        
        cycle = self.cycle_var.get()
        if cycle == "Quarterly": months_multiplier = 3.0
        elif cycle == "Monthly": months_multiplier = 1.0
        else: 
            days_billed = self.get_safe_int(self.days_var)
            if days_billed <= 0: days_billed = 1
            months_multiplier = days_billed / 30.0
            
        phase = self.phase_var.get()
        mvca_rate = self.get_safe_float(self.mvca_var)
        
        raw_load = self.get_safe_float(self.load_var)
        load_kva = (raw_load / 0.85) if self.load_unit_var.get() == "kW" else raw_load
        if "commercial" in cat_lower and 0 < load_kva < 1.0: load_kva = 1.0 
            
        energy_charge = 0.0
        total_units = 0
        
        if is_tod:
            n, p, o = self.get_safe_int(self.tod_n_var), self.get_safe_int(self.tod_p_var), self.get_safe_int(self.tod_o_var)
            total_units = n + p + o
            if "tod_slabs" in cat_data:
                energy_charge += n * cat_data["tod_slabs"].get("Normal", 0)
                energy_charge += p * cat_data["tod_slabs"].get("Peak", 0)
                energy_charge += o * cat_data["tod_slabs"].get("Off_Peak", 0)
        else:
            total_units = self.get_safe_int(self.units_var)
            if "commercial" in cat_lower:
                energy_charge -= (min(total_units, 100 * months_multiplier) * 0.02)
                
            u = total_units
            for slab in cat_data.get("slabs", []):
                if u <= 0: break
                limit, rate = slab["limit"], slab["rate"]
                if limit is None:
                    energy_charge += u * rate; u = 0
                else:
                    slab_units = min(u, limit * months_multiplier)
                    energy_charge += slab_units * rate; u -= slab_units
                    
        base_fc = load_kva * cat_data["fixed_charge"] * months_multiplier
        if self.monsoon_var.get(): base_fc /= 2.0
        if "domestic" in cat_lower: base_fc = max(base_fc, 30.0 * months_multiplier)
            
        min_floor = load_kva * cat_data.get("min_charge", 0.0) * months_multiplier
        is_minimum = (energy_charge + base_fc) < min_floor and min_floor > 100.0 
        
        if is_minimum:
            base_amount = min_floor
            self.val_energy.config(text="OVERRIDDEN", foreground="gray")
            self.val_fixed.config(text="OVERRIDDEN", foreground="gray")
            self.val_minimum.config(text=f"₹ {min_floor:,.2f}")
            self.val_minimum_row.grid()
        else:
            base_amount = energy_charge + base_fc
            self.val_energy.config(text=f"₹ {energy_charge:,.2f}", foreground="")
            self.val_fixed.config(text=f"₹ {base_fc:,.2f}", foreground="")
            self.val_minimum_row.grid_remove()

        mvca_charge = total_units * mvca_rate
        meter_rent = 0.0
        if phase != "Own Meter":
            if is_tod: base_rent = 25.0
            elif "domestic" in cat_lower and phase == "1-Phase": base_rent = 10.0
            elif "commercial" in cat_lower and phase == "1-Phase": base_rent = 15.0
            else: base_rent = 50.0
            meter_rent = base_rent * months_multiplier
            
        subsidy_amount = self.calculate_state_subsidy(total_units, category, phase, months_multiplier)
        rebateable_amount = base_amount + mvca_charge
        timely_rebate = rebateable_amount * 0.01 
        
        ed_base = base_amount - timely_rebate if "domestic" in cat_lower or "commercial" in cat_lower else base_amount
        ed_percent = 0.0
        for slab in cat_data.get("ed_slabs", []):
            scaled_limit = slab["limit"] * months_multiplier if slab["limit"] else None
            if scaled_limit is None or total_units <= scaled_limit:
                ed_percent = slab["rate"]; break
                    
        total_ed = ed_base * ed_percent
        gross_bill = base_amount + mvca_charge + meter_rent + total_ed - subsidy_amount
        
        special_rebate = total_units * 0.10 if ("domestic" in cat_lower or "commercial" in cat_lower) and months_multiplier > 2.0 else 0.0
        net_after_timely = gross_bill - special_rebate - timely_rebate
        epay_rebate = net_after_timely * 0.01 if net_after_timely > 0 else 0.0
        total_rebates = special_rebate + timely_rebate + epay_rebate
        
        self.val_mvca.config(text=f"₹ {mvca_charge:,.2f}")
        self.val_rent.config(text=f"₹ {meter_rent:,.2f}")
        self.val_subsidy.config(text=f"- ₹ {subsidy_amount:,.2f}" if subsidy_amount > 0 else "₹ 0.00", bootstyle=SUCCESS if subsidy_amount > 0 else DEFAULT)
        self.val_ed.config(text=f"₹ {total_ed:,.2f}  ({ed_percent*100:.2f}%)")
        self.val_gross.config(text=f"₹ {gross_bill:,.2f}")
        self.val_reb_spec.config(text=f"- ₹ {special_rebate:,.2f}")
        self.val_reb_time.config(text=f"- ₹ {timely_rebate:,.2f}")
        self.val_reb_epay.config(text=f"- ₹ {epay_rebate:,.2f}")
        self.val_net.config(text=f"₹ {round(gross_bill - total_rebates):,.2f}")

    def setup_ui(self):
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=BOTH, expand=YES, padx=20, pady=20)
        ttk.Label(main_frame, text="Electricity Bill Calculator", font=("Segoe UI", 16, "bold"), bootstyle=PRIMARY).pack(pady=(0, 20))

        panels_frame = ttk.Frame(main_frame)
        panels_frame.pack(fill=BOTH, expand=YES)
        panels_frame.columnconfigure(0, weight=1, uniform="pane")
        panels_frame.columnconfigure(1, weight=1, uniform="pane")

        # LEFT PANEL
        inp_frame = ttk.LabelFrame(panels_frame, text=" CONSUMER DETAILS & READINGS ")
        inp_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 10), ipadx=15, ipady=15)

        def create_input_row(row, label, widget):
            ttk.Label(inp_frame, text=label, font=("Segoe UI", 11)).grid(row=row, column=0, sticky=W, padx=10, pady=8)
            widget.grid(row=row, column=1, sticky=E, padx=10, pady=8)

        cat_cb = ttk.Combobox(inp_frame, textvariable=self.category_var, values=list(self.tariff_data.keys()), state="readonly", width=25)
        if list(self.tariff_data.keys()): cat_cb.current(0) 
        create_input_row(0, "Tariff Category:", cat_cb)

        cycle_frame = ttk.Frame(inp_frame)
        ttk.Radiobutton(cycle_frame, text="Monthly", variable=self.cycle_var, value="Monthly", bootstyle="info").pack(side=LEFT, padx=(0, 10))
        ttk.Radiobutton(cycle_frame, text="Quarterly", variable=self.cycle_var, value="Quarterly", bootstyle="info").pack(side=LEFT, padx=(0, 10))
        ttk.Radiobutton(cycle_frame, text="Pro-Rata", variable=self.cycle_var, value="Pro-Rata", bootstyle="info").pack(side=LEFT)
        self.days_input_frame = ttk.Frame(cycle_frame)
        ttk.Label(self.days_input_frame, text="Days:").pack(side=LEFT, padx=(0, 5))
        ttk.Entry(self.days_input_frame, textvariable=self.days_var, width=5).pack(side=LEFT)
        create_input_row(1, "Billing Mode:", cycle_frame)

        phase_frame = ttk.Frame(inp_frame)
        ttk.Radiobutton(phase_frame, text="1-Phase", variable=self.phase_var, value="1-Phase").pack(side=LEFT, padx=(0, 5))
        ttk.Radiobutton(phase_frame, text="3-Phase", variable=self.phase_var, value="3-Phase").pack(side=LEFT, padx=(0, 5))
        ttk.Radiobutton(phase_frame, text="Own", variable=self.phase_var, value="Own Meter").pack(side=LEFT)
        create_input_row(2, "Meter Type:", phase_frame)

        load_frame = ttk.Frame(inp_frame)
        ttk.Entry(load_frame, textvariable=self.load_var, width=10, justify="right").pack(side=LEFT, padx=(0, 5))
        ttk.Combobox(load_frame, textvariable=self.load_unit_var, values=["KVA", "kW"], state="readonly", width=5).pack(side=LEFT)
        create_input_row(3, "Contractual Load:", load_frame)

        self.monsoon_frame = ttk.Checkbutton(inp_frame, text="Apply Monsoon Discount (Jul-Oct)", variable=self.monsoon_var, bootstyle="success-round-toggle")

        self.frame_normal_units = ttk.Frame(inp_frame)
        ttk.Label(self.frame_normal_units, text="Total Units Consumed:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky=W, padx=10)
        ttk.Entry(self.frame_normal_units, textvariable=self.units_var, width=14, justify="right").grid(row=0, column=1, sticky=E, padx=10)

        self.frame_tod_units = ttk.Frame(inp_frame)
        ttk.Label(self.frame_tod_units, text="TOD Units [ N | P | O ]:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky=W, padx=10)
        tod_inputs = ttk.Frame(self.frame_tod_units)
        tod_inputs.grid(row=0, column=1, sticky=E, padx=10)
        ttk.Entry(tod_inputs, textvariable=self.tod_n_var, width=5).pack(side=LEFT, padx=2)
        ttk.Entry(tod_inputs, textvariable=self.tod_p_var, width=5).pack(side=LEFT, padx=2)
        ttk.Entry(tod_inputs, textvariable=self.tod_o_var, width=5).pack(side=LEFT, padx=2)

        create_input_row(7, "MVCA Rate (₹):", ttk.Entry(inp_frame, textvariable=self.mvca_var, width=14, justify="right"))

        # RIGHT PANEL
        out_frame = ttk.LabelFrame(panels_frame, text=" ITEMIZED BILL BREAKDOWN ")
        out_frame.grid(row=0, column=1, sticky=NSEW, padx=(10, 0), ipadx=15, ipady=15)
        out_frame.columnconfigure(1, weight=1)

        def create_table_row(row, label, is_bold=False):
            font = ("Segoe UI", 12, "bold") if is_bold else ("Segoe UI", 11, "bold")
            ttk.Label(out_frame, text=label, font=("Segoe UI", 11)).grid(row=row, column=0, sticky=W, padx=10, pady=4)
            val = ttk.Label(out_frame, text="₹ 0.00", font=font)
            val.grid(row=row, column=1, sticky=E, padx=10, pady=4)
            ttk.Separator(out_frame, orient=HORIZONTAL).grid(row=row+1, column=0, columnspan=2, sticky=EW, pady=2)
            return val

        self.val_energy = create_table_row(0, "Energy Charge:")
        self.val_fixed = create_table_row(2, "Fixed Charge:")

        self.val_minimum_row = ttk.Frame(out_frame)
        ttk.Label(self.val_minimum_row, text="MINIMUM CHARGE APPLIED:", font=("Segoe UI", 11, "bold"), bootstyle=DANGER).grid(row=0, column=0, sticky=W, padx=10, pady=4)
        self.val_minimum = ttk.Label(self.val_minimum_row, text="₹ 0.00", font=("Segoe UI", 11, "bold"), bootstyle=DANGER)
        self.val_minimum.grid(row=0, column=1, sticky=E, padx=10, pady=4)
        self.val_minimum_row.grid(row=4, column=0, columnspan=2, sticky=EW)
        self.val_minimum_row.columnconfigure(1, weight=1)

        self.val_mvca = create_table_row(6, "MVCA Surcharge:")
        self.val_rent = create_table_row(8, "Meter Rent:")
        self.val_subsidy = create_table_row(10, "Govt. Subsidy / Relief:")
        self.val_ed = create_table_row(12, "Electricity Duty (ED):")
        self.val_gross = create_table_row(14, "GROSS BILL AMOUNT:", is_bold=True)

        ttk.Label(out_frame, text="Deductions & Rebates", font=("Segoe UI", 9, "bold"), bootstyle=SECONDARY).grid(row=16, column=0, sticky=W, padx=10, pady=(10,0))
        self.val_reb_spec = create_table_row(17, "Special Rebate:"); self.val_reb_spec.config(foreground="gray")
        self.val_reb_time = create_table_row(19, "Timely Rebate (1%):"); self.val_reb_time.config(foreground="gray")
        self.val_reb_epay = create_table_row(21, "e-Payment Rebate (1%):"); self.val_reb_epay.config(foreground="gray")

        self.val_net = create_table_row(23, "ESTIMATED NET PAYABLE:", is_bold=True)
        self.val_net.config(font=("Segoe UI", 18, "bold"), bootstyle=WARNING)

    def bind_traces(self):
        for var in [self.category_var, self.cycle_var, self.days_var, self.phase_var, self.load_var, 
                    self.load_unit_var, self.units_var, self.mvca_var, self.tod_n_var, self.tod_p_var, self.tod_o_var, self.monsoon_var]:
            var.trace_add("write", self.calculate_all)
        self.category_var.trace_add("write", self.update_ui_visibility)
        self.cycle_var.trace_add("write", self.update_ui_visibility)

if __name__ == "__main__":
    root = ttk.Window(themename="cosmo")
    app = BillCalculatorApp(root)
    root.mainloop()