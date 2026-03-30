import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import math
import tariff_manager

class TheftCalculatorApp:
    def __init__(self, parent):
        self.tariff_data = tariff_manager.load_tariff()
        
        self.window = ttk.Toplevel(parent)
        self.window.title("Theft Assessment Calculator - SpotImageViewer")
        self.window.state('zoomed')

        # Fonts
        self.FONT_TITLE = ("Segoe UI", 15, "bold")
        self.FONT_LABEL = ("Segoe UI", 10)
        self.FONT_VALUE = ("Segoe UI", 10, "bold")
        self.FONT_GROSS = ("Segoe UI", 11, "bold")
        self.FONT_NET = ("Segoe UI", 14, "bold")

        # --- INSTANCE VARIABLES ---
        self.category_var = ttk.StringVar()
        self.consumer_type_var = ttk.StringVar(value="Consumer")
        self.load_var = ttk.StringVar(value="0")
        self.load_unit_var = ttk.StringVar(value="KVA")

        self.p_days_var = ttk.StringVar(value="365")
        self.p_hours_var = ttk.StringVar(value="24")
        self.f_days_var = ttk.StringVar(value="365")
        self.f_hours_var = ttk.StringVar(value="19")
        self.adj_e_var = ttk.StringVar(value="0")
        self.adj_f_var = ttk.StringVar(value="0")
        self.adj_ed_var = ttk.StringVar(value="0")

        self.setup_ui()
        self.bind_traces()
        self.window.after(100, self.calculate_all)

    def calculate_slab_bill(self, monthly_units, category_data):
        charge = 0.0; u = monthly_units
        if "slabs" in category_data:
            for slab in category_data["slabs"]:
                if u <= 0: break
                limit, rate = slab["limit"], slab["rate"]
                if limit is None:
                    charge += u * rate; u = 0
                else:
                    slab_units = min(u, limit)
                    charge += slab_units * rate; u -= slab_units
        elif "tod_slabs" in category_data:
            charge = u * category_data["tod_slabs"].get("Normal", 0.0)
        return charge

    def get_highest_slab_rate(self, category_data):
        if "slabs" in category_data: return max(slab["rate"] for slab in category_data["slabs"])
        elif "tod_slabs" in category_data: return max(category_data["tod_slabs"].values())
        return 0.0

    def get_ed_rate(self, monthly_units, category_data):
        for slab in category_data.get("ed_slabs", []):
            if slab["limit"] is None or monthly_units <= slab["limit"]: return slab["rate"]
        return 0.0

    def compute_assessment(self, category, load_kva, days, hours, consumer_type):
        cat_data = self.tariff_data[category]
        pf = 0.85
        lf = cat_data.get("load_factor", 0.5 if "domestic" in category.lower() else 0.75)
        months = days / (365 / 12)  
        total_units = round(load_kva * pf * lf * days * hours)
        units_per_month = total_units / months if months > 0 else 0
        
        if consumer_type == "Non-Consumer":
            highest_rate = self.get_highest_slab_rate(cat_data)
            normal_monthly_charge = units_per_month * highest_rate
        else:
            normal_monthly_charge = self.calculate_slab_bill(units_per_month, cat_data)
            
        normal_total_charge = normal_monthly_charge * months
        penal_energy_charge = normal_total_charge * 2

        # Fixed demand load rule: minimum 1 KVA, otherwise use actual assessed load.
        rounded_load = max(1.0, load_kva)
        rounded_months = math.ceil(months)
        normal_fc = rounded_load * cat_data["fixed_charge"] * rounded_months

        penal_fc = normal_fc * 2 
        ed_percent = self.get_ed_rate(units_per_month, cat_data)
        total_ed = (penal_energy_charge + penal_fc) * ed_percent
        gross_bill = penal_energy_charge + penal_fc + total_ed
        
        return {
            "units": total_units, "energy": penal_energy_charge, "fixed": penal_fc,
            "ed_percent": ed_percent, "ed": total_ed, "gross": gross_bill
        }

    def get_safe_float(self, var):
        try: return float(var.get().strip()) if var.get().strip() else 0.0
        except ValueError: return 0.0

    def get_safe_int(self, var):
        try: return int(var.get().strip()) if var.get().strip() else 0
        except ValueError: return 0

    def get_safe_hours_decimal(self, var):
        """Allow decimal hours and clamp to valid daily range [0, 24]."""
        try:
            value = float(var.get().strip()) if var.get().strip() else 0.0
        except ValueError:
            value = 0.0

        value = max(0.0, min(24.0, value))
        return value

    def normalize_hours_input(self, var):
        """Normalize hours text after editing is complete (on focus-out)."""
        value = self.get_safe_hours_decimal(var)
        normalized = f"{value:.2f}".rstrip("0").rstrip(".")
        var.set(normalized)
        return value

    def format_decimal_hours(self, decimal_hours):
        total_minutes = int(round(decimal_hours * 60))
        total_minutes = max(0, min(24 * 60, total_minutes))
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"({hours:02d} hr {minutes:02d} min)"

    def reset_adjustments(self, *args):
        self.adj_e_var.set("0")
        self.adj_f_var.set("0")
        self.adj_ed_var.set("0")
        self.calculate_all()

    def toggle_consumer_mode(self, *args):
        if self.consumer_type_var.get() == "Non-Consumer":
            self.adj_energy_entry.config(state="disabled")
            self.adj_fixed_entry.config(state="disabled")
            self.adj_ed_entry.config(state="disabled")
            self.reset_adjustments()
        else:
            self.adj_energy_entry.config(state="normal")
            self.adj_fixed_entry.config(state="normal")
            self.adj_ed_entry.config(state="normal")
            self.calculate_all()

    def calculate_all(self, *args):
        category_name = self.category_var.get()
        if not category_name or category_name not in self.tariff_data: return
        cons_type = self.consumer_type_var.get()
        
        raw_load = self.get_safe_float(self.load_var)
        unit_type = self.load_unit_var.get()
        load_kva = (raw_load / 0.85) if unit_type == "kW" else raw_load
        
        p_days = self.get_safe_int(self.p_days_var)
        f_days = self.get_safe_int(self.f_days_var)
        p_hours = self.get_safe_hours_decimal(self.p_hours_var)
        f_hours = self.get_safe_hours_decimal(self.f_hours_var)

        self.p_hours_exact_lbl.config(text=self.format_decimal_hours(p_hours))
        self.f_hours_exact_lbl.config(text=self.format_decimal_hours(f_hours))
        
        adj_e = self.get_safe_float(self.adj_e_var)
        adj_f = self.get_safe_float(self.adj_f_var)
        adj_ed = self.get_safe_float(self.adj_ed_var)
        total_adj = adj_e + adj_f + adj_ed

        prov = self.compute_assessment(category_name, load_kva, p_days, p_hours, cons_type)
        final = self.compute_assessment(category_name, load_kva, f_days, f_hours, cons_type)

        prov_net = prov['gross'] - total_adj
        final_net = final['gross'] - total_adj

        self.p_val_units.config(text=f"{prov['units']:,} kWh")
        self.p_val_energy.config(text=f"₹ {prov['energy']:,.2f}")
        self.p_val_fc.config(text=f"₹ {prov['fixed']:,.2f}")
        self.p_val_ed.config(text=f"₹ {prov['ed']:,.2f}  ({prov['ed_percent']*100:.0f}%)")
        self.p_val_gross.config(text=f"₹ {prov['gross']:,.2f}")
        self.p_val_adj.config(text=f"- ₹ {total_adj:,.2f}")
        self.p_val_net.config(text=f"₹ {prov_net:,.2f}")

        self.f_val_units.config(text=f"{final['units']:,} kWh")
        self.f_val_energy.config(text=f"₹ {final['energy']:,.2f}")
        self.f_val_fc.config(text=f"₹ {final['fixed']:,.2f}")
        self.f_val_ed.config(text=f"₹ {final['ed']:,.2f}  ({final['ed_percent']*100:.0f}%)")
        self.f_val_gross.config(text=f"₹ {final['gross']:,.2f}")
        
        self.f_adj_e_lbl.config(text=f"₹ {adj_e:,.2f}")
        self.f_adj_f_lbl.config(text=f"₹ {adj_f:,.2f}")
        self.f_adj_ed_lbl.config(text=f"₹ {adj_ed:,.2f}")
        self.f_val_adj.config(text=f"- ₹ {total_adj:,.2f}")
        self.f_val_net.config(text=f"₹ {final_net:,.2f}")

        diff_rs = prov_net - final_net
        diff_pct = (diff_rs / prov_net * 100) if prov_net > 0 else 0
        self.diff_lbl.config(text=f"Final Assessment Relief:  ₹ {diff_rs:,.2f}   ({diff_pct:.2f}%)")

    def on_hours_focus_out(self, var, label):
        value = self.normalize_hours_input(var)
        label.config(text=self.format_decimal_hours(value))
        self.calculate_all()

    def setup_ui(self):
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=BOTH, expand=YES, padx=15, pady=15)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=X, pady=(0, 15))

        ttk.Label(top_frame, text="Theft Assessment Calculator", font=self.FONT_TITLE, bootstyle=PRIMARY).pack(pady=(0, 15))

        input_bar = ttk.Frame(top_frame)
        input_bar.pack(fill=X, padx=20, pady=10)
        input_bar.columnconfigure(0, weight=0) 
        input_bar.columnconfigure(1, weight=1)

        ttk.Label(input_bar, text="Offender Type:", font=self.FONT_LABEL).grid(row=0, column=0, sticky=W, pady=5)
        offender_subframe = ttk.Frame(input_bar)
        offender_subframe.grid(row=0, column=1, sticky=W)
        ttk.Radiobutton(offender_subframe, text="Consumer", variable=self.consumer_type_var, value="Consumer", bootstyle="info").pack(side=LEFT, padx=5)
        ttk.Radiobutton(offender_subframe, text="Non-Consumer", variable=self.consumer_type_var, value="Non-Consumer", bootstyle="warning").pack(side=LEFT, padx=5)

        ttk.Label(input_bar, text="Tariff Category:", font=self.FONT_LABEL).grid(row=1, column=0, sticky=W, pady=5)
        cat_cb = ttk.Combobox(input_bar, textvariable=self.category_var, values=list(self.tariff_data.keys()), state="readonly")
        if list(self.tariff_data.keys()): cat_cb.current(0)
        cat_cb.grid(row=1, column=1, sticky=EW, padx=5)

        ttk.Label(input_bar, text="Assessed Load:", font=self.FONT_LABEL).grid(row=2, column=0, sticky=W, pady=5)
        load_subframe = ttk.Frame(input_bar)
        load_subframe.grid(row=2, column=1, sticky=W)
        ttk.Entry(load_subframe, textvariable=self.load_var, justify="center", width=12).pack(side=LEFT, padx=5)
        ttk.Combobox(load_subframe, textvariable=self.load_unit_var, values=["KVA", "kW"], state="readonly", width=6).pack(side=LEFT)

        panels_frame = ttk.Frame(main_frame)
        panels_frame.pack(fill=BOTH, expand=YES)
        panels_frame.columnconfigure(0, weight=1, uniform="pane")
        panels_frame.columnconfigure(1, weight=1, uniform="pane")

        def create_table_row(parent, row, label, is_gross=False, is_net=False):
            font_lbl = self.FONT_LABEL
            font_val = self.FONT_NET if is_net else (self.FONT_GROSS if is_gross else self.FONT_VALUE)
            ttk.Label(parent, text=label, font=font_lbl).grid(row=row, column=0, sticky=W, padx=10, pady=4)
            val_lbl = ttk.Label(parent, text="₹ 0.00", font=font_val)
            val_lbl.grid(row=row, column=1, sticky=E, padx=10, pady=4)
            ttk.Separator(parent, orient=HORIZONTAL).grid(row=row+1, column=0, columnspan=2, sticky=EW, pady=2)
            return val_lbl

        # PROVISIONAL
        prov_frame = ttk.LabelFrame(panels_frame, text=" PROVISIONAL ASSESSMENT ")
        prov_frame.grid(row=0, column=0, sticky=NSEW, padx=(0, 8), ipadx=10, ipady=10)

        p_inp_frame = ttk.Frame(prov_frame)
        p_inp_frame.pack(fill=X, pady=5)
        p_inp_frame.columnconfigure(1, weight=1); p_inp_frame.columnconfigure(3, weight=1)
        ttk.Label(p_inp_frame, text="Days:", font=self.FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
        ttk.Entry(p_inp_frame, textvariable=self.p_days_var, width=10, justify="right").grid(row=0, column=1, sticky=E, padx=10)
        ttk.Label(p_inp_frame, text="Hours/Day:", font=self.FONT_LABEL).grid(row=0, column=2, sticky=W, padx=10)
        self.p_hours_entry = ttk.Entry(p_inp_frame, textvariable=self.p_hours_var, width=10, justify="right")
        self.p_hours_entry.grid(row=0, column=3, sticky=E, padx=10)
        self.p_hours_exact_lbl = ttk.Label(p_inp_frame, text="(24 hr 00 min)", font=("Segoe UI", 9), bootstyle=SECONDARY)
        self.p_hours_exact_lbl.grid(row=0, column=4, sticky=W, padx=(0, 10))
        self.p_hours_entry.bind("<FocusOut>", lambda e: self.on_hours_focus_out(self.p_hours_var, self.p_hours_exact_lbl))

        ttk.Separator(prov_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

        ttk.Label(prov_frame, text="Deductions from Paid Bills (Manual)", font=("Segoe UI", 10, "bold"), bootstyle=SECONDARY).pack(anchor=W, padx=10, pady=(0,5))
        adj_frame = ttk.Frame(prov_frame); adj_frame.pack(fill=X); adj_frame.columnconfigure(1, weight=1)
        
        ttk.Label(adj_frame, text="Energy Charge (₹):", font=self.FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
        self.adj_energy_entry = ttk.Entry(adj_frame, textvariable=self.adj_e_var, width=14, justify="right")
        self.adj_energy_entry.grid(row=0, column=1, sticky=E, padx=10)

        ttk.Label(adj_frame, text="Fixed/Demand (₹):", font=self.FONT_LABEL).grid(row=1, column=0, sticky=W, padx=10)
        self.adj_fixed_entry = ttk.Entry(adj_frame, textvariable=self.adj_f_var, width=14, justify="right")
        self.adj_fixed_entry.grid(row=1, column=1, sticky=E, padx=10)

        ttk.Label(adj_frame, text="Electricity Duty (₹):", font=self.FONT_LABEL).grid(row=2, column=0, sticky=W, padx=10)
        self.adj_ed_entry = ttk.Entry(adj_frame, textvariable=self.adj_ed_var, width=14, justify="right")
        self.adj_ed_entry.grid(row=2, column=1, sticky=E, padx=10)

        ttk.Separator(prov_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

        p_table = ttk.Frame(prov_frame); p_table.pack(fill=BOTH, expand=YES); p_table.columnconfigure(1, weight=1)
        self.p_val_units = create_table_row(p_table, 0, "Total Units:")
        self.p_val_energy = create_table_row(p_table, 2, "Energy Charge (Penal):")
        self.p_val_fc = create_table_row(p_table, 4, "Fixed Charge (Penal):")
        self.p_val_ed = create_table_row(p_table, 6, "Electricity Duty:")
        self.p_val_gross = create_table_row(p_table, 8, "GROSS BILL:", is_gross=True)
        self.p_val_adj = create_table_row(p_table, 10, "Less: Total Deductions:")
        self.p_val_net = create_table_row(p_table, 12, "NET PAYABLE:", is_net=True)
        self.p_val_net.configure(bootstyle=WARNING)

        # FINAL
        final_frame = ttk.LabelFrame(panels_frame, text=" FINAL ASSESSMENT ")
        final_frame.grid(row=0, column=1, sticky=NSEW, padx=(8, 0), ipadx=10, ipady=10)

        f_inp_frame = ttk.Frame(final_frame); f_inp_frame.pack(fill=X, pady=5)
        f_inp_frame.columnconfigure(1, weight=1); f_inp_frame.columnconfigure(3, weight=1)
        ttk.Label(f_inp_frame, text="Days:", font=self.FONT_LABEL).grid(row=0, column=0, sticky=W, padx=10)
        ttk.Entry(f_inp_frame, textvariable=self.f_days_var, width=10, justify="right").grid(row=0, column=1, sticky=E, padx=10)
        ttk.Label(f_inp_frame, text="Hours/Day:", font=self.FONT_LABEL).grid(row=0, column=2, sticky=W, padx=10)
        self.f_hours_entry = ttk.Entry(f_inp_frame, textvariable=self.f_hours_var, width=10, justify="right")
        self.f_hours_entry.grid(row=0, column=3, sticky=E, padx=10)
        self.f_hours_exact_lbl = ttk.Label(f_inp_frame, text="(19 hr 00 min)", font=("Segoe UI", 9), bootstyle=SECONDARY)
        self.f_hours_exact_lbl.grid(row=0, column=4, sticky=W, padx=(0, 10))
        self.f_hours_entry.bind("<FocusOut>", lambda e: self.on_hours_focus_out(self.f_hours_var, self.f_hours_exact_lbl))

        ttk.Separator(final_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

        ttk.Label(final_frame, text="Deductions Applied (Auto-Mirrored)", font=("Segoe UI", 10, "bold"), bootstyle=SECONDARY).pack(anchor=W, padx=10, pady=(0,5))
        f_adj_frame = ttk.Frame(final_frame); f_adj_frame.pack(fill=X); f_adj_frame.columnconfigure(1, weight=1)
        
        ttk.Label(f_adj_frame, text="Energy Charge (₹):", font=self.FONT_LABEL, foreground="gray").grid(row=0, column=0, sticky=W, padx=10)
        self.f_adj_e_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=self.FONT_VALUE, foreground="gray")
        self.f_adj_e_lbl.grid(row=0, column=1, sticky=E, padx=10)

        ttk.Label(f_adj_frame, text="Fixed/Demand (₹):", font=self.FONT_LABEL, foreground="gray").grid(row=1, column=0, sticky=W, padx=10)
        self.f_adj_f_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=self.FONT_VALUE, foreground="gray")
        self.f_adj_f_lbl.grid(row=1, column=1, sticky=E, padx=10)

        ttk.Label(f_adj_frame, text="Electricity Duty (₹):", font=self.FONT_LABEL, foreground="gray").grid(row=2, column=0, sticky=W, padx=10)
        self.f_adj_ed_lbl = ttk.Label(f_adj_frame, text="₹ 0.00", font=self.FONT_VALUE, foreground="gray")
        self.f_adj_ed_lbl.grid(row=2, column=1, sticky=E, padx=10)

        ttk.Separator(final_frame, orient=HORIZONTAL).pack(fill=X, pady=10)

        f_table = ttk.Frame(final_frame); f_table.pack(fill=BOTH, expand=YES); f_table.columnconfigure(1, weight=1)
        self.f_val_units = create_table_row(f_table, 0, "Total Units:")
        self.f_val_energy = create_table_row(f_table, 2, "Energy Charge (Penal):")
        self.f_val_fc = create_table_row(f_table, 4, "Fixed Charge (Penal):")
        self.f_val_ed = create_table_row(f_table, 6, "Electricity Duty:")
        self.f_val_gross = create_table_row(f_table, 8, "GROSS BILL:", is_gross=True)
        self.f_val_adj = create_table_row(f_table, 10, "Less: Total Deductions:")
        self.f_val_net = create_table_row(f_table, 12, "NET PAYABLE:", is_net=True)
        self.f_val_net.configure(bootstyle=SUCCESS)

        # BANNER
        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill=X, pady=(15, 0))
        ttk.Separator(summary_frame, orient=HORIZONTAL).pack(fill=X)
        self.diff_lbl = ttk.Label(summary_frame, text="Final Assessment Relief: ₹ 0.00  (0.00%)", font=("Segoe UI", 12, "bold"), bootstyle=PRIMARY)
        self.diff_lbl.pack(pady=10)
        ttk.Separator(summary_frame, orient=HORIZONTAL).pack(fill=X)

    def bind_traces(self):
        self.category_var.trace_add("write", self.reset_adjustments)
        self.load_var.trace_add("write", self.reset_adjustments)
        self.consumer_type_var.trace_add("write", self.toggle_consumer_mode)
        self.load_unit_var.trace_add("write", self.calculate_all)
        for var in [self.p_days_var, self.p_hours_var, self.f_days_var, self.f_hours_var, self.adj_e_var, self.adj_f_var, self.adj_ed_var]:
            var.trace_add("write", self.calculate_all)

if __name__ == "__main__":
    root = ttk.Window(themename="cosmo")
    app = TheftCalculatorApp(root)
    root.mainloop()