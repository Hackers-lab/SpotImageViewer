import tkinter as tk
from tkinter import ttk, LEFT, RIGHT, BOTH, Y, X, END
import ttkbootstrap as tb
import config

# --- 1. The Content Dictionary ---
# Updated for V18.3 to include time-input and UI refinements
HELP_CONTENT = {
    "1. Introduction": {
        "_text": f"Welcome to Spot Image Viewer V{config.CURRENT_VERSION}.\n\n continues this utility suite for WBSEDCL personnel with updated tariff management, dark mode improvements, and assessment workflows.",
        "Key Features": "• Advanced Billing & Assessment Suite\n• Dynamic Tariff Management\n• Lightning-fast SQLite Indexing\n• Low Consumption Verification Module\n• Consumer Note Tracking"
    },
    "2. Getting Started": {
        "_text": "Follow these steps to set up the application for the first time.",
        "Adding Folders": "1. Go to the 'Networks' pane on the right side of the main window.\n2. Click 'Add Folder'.\n3. Select the network drive or folder containing your meter images.\n4. You can add as many folders as you need.",
        "Indexing Images": "Once your folders are added, click the 'Reload Images' button at the top right.\n\nThe application will scan the folders and build a fast database. Do this whenever new images are added to your folders."
    },
    "3. Search & View": {
        "_text": "How to find and interact with consumer images.",
        "Searching": "Enter a 9-digit Consumer ID or Meter Number in the top bar and press Enter (or click Search).\n\nTip: Press the Spacebar inside the search box to view your recent search history!",
        "Viewing Images": "When a consumer is found, all available image dates will appear on the left.\n\nClick a date to load the high-resolution image into the main canvas. Use the '+' and '-' buttons below the image to zoom in and out."
    },
    "4. Verification Module": {
        "_text": "The Low Consumption Verification mode is a dedicated tool for auditors.",
        "Loading Data": "1. Go to Verification -> Low Consumption Check.\n2. Click 'Load Data'.\n3. Import an Excel file containing (Column A: ID, Column B: Meter, Column C: Unit).",
        "Auditing": "Select a row to view the historical images for that consumer. Mark the consumer as 'OK (Verified)' or 'Suspicious / Not OK'.\n\nKeyboard Shortcuts:\n• Alt + S: Save & move to next\n• Alt + N: Skip to next"
    },
    "5. Billing & Assessment": {
        "_text": "The Tools menu now contains professional-grade calculation engines.",
        "Energy Bill Calculator": "Calculate exact bills for Domestic, Commercial, Industrial, and STW (TOD/Whole-day) consumers. Simply enter the units and load to generate a bill based on the latest 2025-26 tariff rates. You can also calculate 'Tariff Benefits' for consumers billed abruptly.",
        "Theft Assessment": "Generate Provisional and Final assessments for theft cases instantly. Enter the assessed load and category to get exact penal figures. The tool automatically verifies if a Final Assessment falls within the legal 25% reduction limit.",
        "Tariff Manager": "View and manage active rate charts directly in the app. Use the Editor to update slabs and charges to ensure your calculations always remain 100% accurate as new regulatory orders are released."
    },
    "6. Notes & Backups": {
        "_text": "Managing your data and saving records.",
        "Taking Notes": "Open the 'Notes' pane on the right. You can select a predefined issue (like 'Meter Defective') and type custom remarks. Click 'Save Note' to link it to the current consumer.",
        "Exporting Notes": "Go to File -> Notes -> Export Notes to save a CSV report of every note you have taken.",
        "Backing Up Images": "Go to Backup -> Backup Images. Enter a date limit (DD-MM-YYYY). The app will copy all images older than or equal to that date into a new, safe folder of your choosing."
    },
    "7. Credits & Contact": {
        "_text": "This application was developed with care. For support or to join the community, please use the links below.",
        "Developer": "Pramod Verma",
        "Contact Email": "je.kushidaccc@gmail.com",
        "WhatsApp Community": "https://chat.whatsapp.com/LZKLg40n8FxCLdnAIO9HGE"
    }
}

class HelpViewer(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Spot Image Viewer Help")
        self.geometry("900x600")
        
        self.transient(parent)
        self.focus_force()
        
        self.content_map = {} 
        
        self.create_widgets()
        self.populate_tree("", HELP_CONTENT)
        
        first_child = self.tree.get_children()[0]
        self.tree.selection_set(first_child)
        self.tree.see(first_child)
        self.on_select(None)

    def create_widgets(self):
        header = tb.Frame(self, bootstyle="primary", padding=10)
        header.pack(fill=X, side=tk.TOP)
        tb.Label(header, text="Documentation & Help Guide", font=("Segoe UI", 16, "bold"), bootstyle="inverse-primary").pack(side=LEFT)

        split = tb.Panedwindow(self, orient=tk.HORIZONTAL)
        split.pack(fill=BOTH, expand=True, padx=10, pady=10)

        left_frame = tb.Frame(split, width=250)
        split.add(left_frame)
        
        self.tree = ttk.Treeview(left_frame, show="tree", selectmode="browse")
        tree_scroll = tb.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        tree_scroll.pack(side=RIGHT, fill=Y)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        right_frame = tb.Frame(split)
        split.add(right_frame)
        
        self.text_area = tk.Text(
            right_frame, 
            wrap="word", 
            font=("Segoe UI", 11), 
            bg="#f8f9fa", 
            relief="flat", 
            padx=20, 
            pady=20
        )
        text_scroll = tb.Scrollbar(right_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scroll.set)
        
        self.text_area.pack(side=LEFT, fill=BOTH, expand=True)
        text_scroll.pack(side=RIGHT, fill=Y)

    def populate_tree(self, parent_node, data_dict):
        for key, value in data_dict.items():
            if key == "_text":
                continue 
            
            node_id = self.tree.insert(parent_node, "end", text=key, open=True)
            
            if isinstance(value, dict):
                self.populate_tree(node_id, value)
                content = value.get("_text", "")
            else:
                content = value
                
            self.content_map[node_id] = content

    def on_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        item_id = selected[0]
        topic_title = self.tree.item(item_id, "text")
        content_text = self.content_map.get(item_id, "Please select a sub-topic.")
        
        self.text_area.config(state="normal")
        self.text_area.delete("1.0", END)
        
        self.text_area.insert("1.0", f"{topic_title}\n\n", "header")
        self.text_area.insert(END, content_text)
        self.text_area.tag_config("header", font=("Segoe UI", 16, "bold"), foreground="#0d6efd")
        self.text_area.config(state="disabled")

def show_documentation(parent):
    HelpViewer(parent)