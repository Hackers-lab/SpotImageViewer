import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from tkinter import messagebox
import tariff_manager
import json

class SlabEditor(ttk.Toplevel):
    """A dialog for editing a single slab's details."""
    def __init__(self, parent, slab_data=None, slab_type='rate'):
        super().__init__(parent)
        self.title = "Edit Slab" if slab_data else "Add Slab"
        self.geometry("300x150")
        self.parent = parent
        self.result = None

        self.data = slab_data if slab_data else {}
        
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=BOTH, expand=YES)

        # Fields
        ttk.Label(frame, text="Limit:").grid(row=0, column=0, sticky=W, pady=5)
        self.limit_var = ttk.StringVar(value=self.data.get("limit", ""))
        ttk.Entry(frame, textvariable=self.limit_var).grid(row=0, column=1)
        
        rate_label = "Rate:" if slab_type == 'rate' else "ED Rate (%):"
        ttk.Label(frame, text=rate_label).grid(row=1, column=0, sticky=W, pady=5)
        self.rate_var = ttk.StringVar(value=self.data.get("rate", ""))
        ttk.Entry(frame, textvariable=self.rate_var).grid(row=1, column=1)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=2, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="OK", command=self.on_ok, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle=DANGER).pack(side=LEFT, padx=5)
        
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def on_ok(self):
        try:
            limit_str = self.limit_var.get().strip()
            rate_str = self.rate_var.get().strip()
            
            limit = int(limit_str) if limit_str.lower() != 'none' and limit_str else None
            rate = float(rate_str)
            
            self.result = {"limit": limit, "rate": rate}
            self.destroy()
        except ValueError:
            Messagebox.show_error("Invalid input. Limit must be an integer (or 'None') and rate must be a number.", "Input Error")

class TariffEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("WBSEDCL Tariff Editor")
        self.root.geometry("900x600")
        self.data = tariff_manager.load_tariff()
        self.current_category = None

        # Main layout
        self.paned_window = ttk.Panedwindow(self.root, orient=HORIZONTAL)
        self.paned_window.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Left Pane: Category List
        left_frame = ttk.Frame(self.paned_window, padding=5)
        self.paned_window.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Tariff Categories", font="-weight bold").pack(anchor=W, pady=(0, 5))
        self.category_tree = ttk.Treeview(left_frame, show="tree", columns=("category",))
        self.category_tree.pack(fill=BOTH, expand=YES)
        self.category_tree.bind("<<TreeviewSelect>>", self.on_category_select)
        
        for category in self.data:
            self.category_tree.insert("", END, text=category, iid=category)

        # Right Pane: Details Editor
        self.right_frame = ttk.Frame(self.paned_window, padding=10)
        self.paned_window.add(self.right_frame, weight=3)
        
        # --- Widgets for the right frame ---
        self.details_frame = ttk.Frame(self.right_frame)
        self.details_frame.pack(fill=BOTH, expand=YES)

        # General details
        general_info_frame = ttk.Labelframe(self.details_frame, text="General", padding=10)
        general_info_frame.pack(fill=X, pady=5)
        general_info_frame.columnconfigure(1, weight=1)

        self.vars = {}
        for i, key in enumerate(["fixed_charge", "min_charge", "load_factor"]):
            self.vars[key] = ttk.StringVar()
            ttk.Label(general_info_frame, text=f"{key.replace('_', ' ').title()}:").grid(row=i, column=0, sticky=W, padx=5, pady=2)
            ttk.Entry(general_info_frame, textvariable=self.vars[key]).grid(row=i, column=1, sticky=EW, padx=5)

        # Slabs Notebook
        self.notebook = ttk.Notebook(self.details_frame)
        self.notebook.pack(fill=BOTH, expand=YES, pady=10)

        self.slabs_tree = self.create_slab_tab("slabs", "Rate Slabs")
        self.ed_slabs_tree = self.create_slab_tab("ed_slabs", "Electricity Duty Slabs")

        # Save Button
        save_button = ttk.Button(self.details_frame, text="Save Category Changes", command=self.save_category, bootstyle=SUCCESS)
        save_button.pack(pady=10)
        
        self.details_frame.pack_forget() # Hide until a category is selected

        # Initial Warning
        Messagebox.show_warning(
            "You are about to edit the live tariff configuration. Changes will directly impact calculations. Proceed with caution.",
            "Editor Warning"
        )

    def create_slab_tab(self, key, text):
        tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(tab, text=text)
        
        # Main content area for tree and scrollbar
        content_frame = ttk.Frame(tab)
        content_frame.pack(fill=BOTH, expand=YES, side=LEFT)

        cols = ("Limit", "Rate")
        tree = ttk.Treeview(content_frame, columns=cols, show="headings")
        tree.pack(fill=BOTH, expand=YES, side=LEFT)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor=CENTER)

        scrollbar = ttk.Scrollbar(content_frame, orient=VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Buttons Frame (arranged vertically)
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(side=RIGHT, fill=Y, padx=(10, 0))
        
        ttk.Button(btn_frame, text="Add", command=lambda t=tree, k=key: self.add_slab(t, k), bootstyle="outline").pack(pady=2, fill=X)
        ttk.Button(btn_frame, text="Edit", command=lambda t=tree, k=key: self.edit_slab(t, k), bootstyle="outline").pack(pady=2, fill=X)
        ttk.Button(btn_frame, text="Remove", command=lambda t=tree: self.remove_slab(t), bootstyle="outline-danger").pack(pady=2, fill=X)

        tree.bind("<Double-1>", lambda event, t=tree, k=key: self.edit_slab(t, k))
        return tree

    def on_category_select(self, event):
        selection = self.category_tree.selection()
        if not selection: return
        
        self.current_category = selection[0]
        category_data = self.data[self.current_category]

        # Show the details frame
        self.details_frame.pack(fill=BOTH, expand=YES)
        
        # Populate general fields
        for key in self.vars:
            self.vars[key].set(category_data.get(key, ""))
        
        # Populate slab trees
        self.populate_slab_tree(self.slabs_tree, category_data.get("slabs", []))
        self.populate_slab_tree(self.ed_slabs_tree, category_data.get("ed_slabs", []))

    def populate_slab_tree(self, tree, slabs):
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)
        # Insert new
        for i, slab in enumerate(slabs):
            limit = "None" if slab.get("limit") is None else slab.get("limit")
            rate = slab.get("rate", "")
            tree.insert("", END, values=(limit, rate), iid=i)

    def add_slab(self, tree, key):
        if not messagebox.askyesno("Confirm Add", "Are you sure you want to add a new slab?"):
            return
            
        slab_type = 'rate' if key == 'slabs' else 'ed'
        editor = SlabEditor(self.root, slab_type=slab_type)
        if editor.result:
            values = ("None" if editor.result['limit'] is None else editor.result['limit'], editor.result['rate'])
            tree.insert("", END, values=values)
    
    def edit_slab(self, tree, key):
        selected_item = tree.selection()
        if not selected_item:
            Messagebox.show_warning("No slab selected to edit.", "Selection Error")
            return
        
        if not messagebox.askyesno("Confirm Edit", "Are you sure you want to edit the selected slab?"):
            return
            
        item = tree.item(selected_item)
        values = item['values']
        
        current_data = {"limit": values[0], "rate": values[1]}
        slab_type = 'rate' if key == 'slabs' else 'ed'
        editor = SlabEditor(self.root, slab_data=current_data, slab_type=slab_type)

        if editor.result:
            new_values = ("None" if editor.result['limit'] is None else editor.result['limit'], editor.result['rate'])
            tree.item(selected_item, values=new_values)
    
    def remove_slab(self, tree):
        selected_items = tree.selection()
        if not selected_items:
            Messagebox.show_warning("No slab selected to remove.", "Selection Error")
            return

        if not messagebox.askyesno("Confirm Remove", f"Are you sure you want to remove {len(selected_items)} slab(s)? This cannot be undone from the UI."):
            return

        for item in selected_items:
            tree.delete(item)
            
    def save_category(self):
        if not self.current_category: return

        try:
            # Update general data
            for key in self.vars:
                val = self.vars[key].get()
                try:
                    self.data[self.current_category][key] = float(val)
                except (ValueError, TypeError):
                     self.data[self.current_category][key] = val # Keep as string if not floatable

            # Update slabs
            self.data[self.current_category]["slabs"] = self._get_slabs_from_tree(self.slabs_tree)
            self.data[self.current_category]["ed_slabs"] = self._get_slabs_from_tree(self.ed_slabs_tree)

            # Save the whole file
            tariff_manager.save_tariff(self.data)
            Messagebox.show_info("Category saved successfully!", "Success")

        except Exception as e:
            Messagebox.show_error(f"Failed to save category: {e}", "Save Error")

    def _get_slabs_from_tree(self, tree):
        slabs = []
        for child_iid in tree.get_children():
            item = tree.item(child_iid)
            values = item['values']
            limit_str = str(values[0]).strip()
            
            limit = None if limit_str.lower() == 'none' else int(limit_str)
            rate = float(values[1])
            slabs.append({"limit": limit, "rate": rate})
        return slabs

if __name__ == "__main__":
    app = ttk.Window(themename="cosmo")
    editor = TariffEditor(app)
    app.mainloop()
