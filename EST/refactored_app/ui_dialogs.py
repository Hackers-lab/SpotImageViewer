"""
This module contains all QDialog-based windows for the application,
such as the settings, search, database manager, and rule manager dialogs.
"""

import sqlite3
import json
import re
import openpyxl

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget, QPushButton, 
                             QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QHBoxLayout, 
                             QFileDialog, QMessageBox, QGroupBox, QFormLayout, QComboBox, 
                             QSpinBox, QHeaderView, QInputDialog, QWidget)
from PyQt6.QtCore import Qt

# Import shared constants
from constants import PROPERTY_DATA, FORMULA_VARS

class SearchDialog(QDialog):
    """
    A dialog for searching the materials or labor database and adding
    an item to the estimate.
    """
    def __init__(self, db_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Search & Add {db_type}")
        self.setFixedSize(600, 400)
        self.layout = QVBoxLayout(self)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type to search official items...")
        self.layout.addWidget(self.search_box)
        
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        self.search_box.textChanged.connect(self.filter_list)
        
        self.add_btn = QPushButton("Add Selected to Estimate")
        self.add_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.add_btn.clicked.connect(self.accept)
        self.layout.addWidget(self.add_btn)

        self.items_data = {}
        self.load_data(db_type)

    def load_data(self, db_type):
        """Loads data from the specified database table."""
        conn = sqlite3.connect('erp_master.db')
        cursor = conn.cursor()
        if db_type == "Material":
            cursor.execute("SELECT item_code, item_name, unit, rate FROM materials")
        else:
            cursor.execute("SELECT labor_code, task_name, unit, rate FROM labor")
        
        for row in cursor.fetchall():
            display_text = f"{row[1]} ({row[2]}) - Rs. {row[3]}"
            self.items_data[display_text] = {"code": row[0], "name": row[1], "unit": row[2], "rate": row[3], "type": db_type}
            self.list_widget.addItem(display_text)
        conn.close()

    def filter_list(self, text):
        """Filters the list widget based on the search box text."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def get_selected(self):
        """Returns the data for the currently selected item."""
        selected = self.list_widget.currentItem()
        if selected:
            return self.items_data[selected.text()]
        return None


class SettingsDialog(QDialog):
    """
    A dialog for accessing advanced application settings like the rule
    engine toggle and the database/ruleset managers.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.setWindowTitle("Advanced Settings")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)
        
        db_sync_btn = QPushButton("🗃️ Master DB (Excel Sync)")
        db_sync_btn.clicked.connect(self.parent_app.open_db_manager)
        layout.addWidget(db_sync_btn)

        rules_btn = QPushButton("🧠 Ruleset Manager")
        rules_btn.clicked.connect(self.parent_app.open_rule_manager)
        layout.addWidget(rules_btn)

        layout.addStretch()


class DatabaseManagerDialog(QDialog):
    """
    A dialog for managing the master database, allowing import from and
    export to Excel files.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Master DB Sync (Excel)")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout(self)
        
        button_layout = QHBoxLayout()
        import_btn = QPushButton("📥 Import from Excel")
        import_btn.clicked.connect(self.import_from_excel)
        export_btn = QPushButton("📤 Export to Excel")
        export_btn.clicked.connect(self.export_to_excel)
        button_layout.addWidget(import_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)
        
        self.tabs = QTabWidget()
        self.materials_table = QTableWidget()
        self.labor_table = QTableWidget()
        self.tabs.addTab(self.materials_table, "Materials")
        self.tabs.addTab(self.labor_table, "Labor")
        layout.addWidget(self.tabs)
        
        self.load_table_data()

    def populate_table(self, table_widget, data, headers):
        """Fills a table widget with data."""
        table_widget.setRowCount(0)
        table_widget.setColumnCount(len(headers))
        table_widget.setHorizontalHeaderLabels(headers)
        for row_num, row_data in enumerate(data):
            table_widget.insertRow(row_num)
            for col_num, col_data in enumerate(row_data):
                table_widget.setItem(row_num, col_num, QTableWidgetItem(str(col_data)))
        table_widget.resizeColumnsToContents()

    def load_table_data(self):
        """Loads data from the database and populates the tables."""
        self.materials_table.clear()
        self.labor_table.clear()
        
        conn = sqlite3.connect('erp_master.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM materials")
        self.populate_table(self.materials_table, cursor.fetchall(), ["Item Code", "Item Name", "Rate", "Unit"])
        
        cursor.execute("SELECT * FROM labor")
        self.populate_table(self.labor_table, cursor.fetchall(), ["Labor Code", "Task Name", "Rate", "Unit"])
        
        conn.close()

    def export_to_excel(self):
        """Exports the database tables to an Excel file."""
        filename, _ = QFileDialog.getSaveFileName(self, "Export DB to Excel", "master_database.xlsx", "Excel Files (*.xlsx)")
        if not filename:
            return

        try:
            wb = openpyxl.Workbook()
            if "Sheet" in wb.sheetnames:
                wb.remove(wb["Sheet"])

            conn = sqlite3.connect('erp_master.db')
            cursor = conn.cursor()

            for table_name in ["materials", "labor"]:
                ws = wb.create_sheet(title=table_name)
                cursor.execute(f"PRAGMA table_info({table_name})")
                headers = [info[1] for info in cursor.fetchall()]
                ws.append(headers)

                cursor.execute(f"SELECT * FROM {table_name}")
                for row in cursor.fetchall():
                    ws.append(row)
            
            conn.close()
            wb.save(filename)
            QMessageBox.information(self, "Success", f"Database exported to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export database: {e}")

    def import_from_excel(self):
        """Imports data from an Excel file into the database."""
        filename, _ = QFileDialog.getOpenFileName(self, "Import DB from Excel", "", "Excel Files (*.xlsx)")
        if not filename:
            return

        try:
            wb = openpyxl.load_workbook(filename)
            conn = sqlite3.connect('erp_master.db')
            cursor = conn.cursor()

            for table_name in ["materials", "labor"]:
                if table_name in wb.sheetnames:
                    ws = wb[table_name]
                    cursor.execute(f"DELETE FROM {table_name}")
                    headers = [cell.value for cell in ws[1]]
                    placeholders = ', '.join(['?'] * len(headers))
                    query = f"INSERT OR REPLACE INTO {table_name} ({', '.join(headers)}) VALUES ({placeholders})"
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if any(row):
                            cursor.execute(query, row)
            conn.commit()
            conn.close()
            self.load_table_data()
            QMessageBox.information(self, "Success", "Database imported successfully. Please restart or refresh to see updates in 'Add Custom' lists.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import database: {e}")


class RulesetManagerDialog(QDialog):
    """
    The main UI for creating, viewing, and deleting rules for the
    DynamicRuleEngine.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Ruleset Manager")
        self.setGeometry(150, 150, 1100, 800)
        
        self.main_layout = QVBoxLayout(self)
        self.rules = []
        self.selected_item = None
        self.condition_widgets = []

        # Use the imported constant data
        self.property_data = PROPERTY_DATA
        self.formula_vars = FORMULA_VARS

        # --- UI: Rule Builder ---
        builder_group = QGroupBox("Rule Builder")
        builder_layout = QFormLayout(builder_group)

        self.obj_combo = QComboBox()
        self.obj_combo.addItems(self.property_data.keys())
        self.obj_combo.currentTextChanged.connect(self.on_object_change)
        builder_layout.addRow("Canvas Object:", self.obj_combo)

        cond_group = QGroupBox("Conditions (IF)")
        self.cond_layout = QVBoxLayout(cond_group)
        self.conditions_container = QWidget()
        self.cond_rows_layout = QVBoxLayout(self.conditions_container)
        self.cond_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.cond_layout.addWidget(self.conditions_container)
        add_cond_btn = QPushButton("➕ Add Condition")
        add_cond_btn.clicked.connect(self.add_condition_row)
        self.cond_layout.addWidget(add_cond_btn)
        self.cond_layout.addStretch()
        builder_layout.addRow(cond_group)

        item_group = QGroupBox("Result (THEN)")
        item_layout = QFormLayout(item_group)
        item_select_layout = QHBoxLayout()
        self.item_label = QLineEdit()
        self.item_label.setPlaceholderText("Select an item from the database...")
        self.item_label.setReadOnly(True)
        search_btn = QPushButton("🔍 Search DB")
        search_btn.clicked.connect(self.search_database)
        item_select_layout.addWidget(self.item_label)
        item_select_layout.addWidget(search_btn)
        item_layout.addRow("Item:", item_select_layout)

        formula_group_widget = QWidget()
        formula_layout = QHBoxLayout(formula_group_widget)
        formula_layout.setContentsMargins(0,0,0,0)
        self.formula_chips_layout = QHBoxLayout()
        self.formula_input = QLineEdit("1")
        self.formula_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chips_widget = QWidget()
        chips_widget.setLayout(self.formula_chips_layout)
        formula_layout.addWidget(chips_widget)
        formula_layout.addWidget(self.formula_input)
        item_layout.addRow("Quantity Formula:", formula_group_widget)
        builder_layout.addRow(item_group)

        self.add_update_btn = QPushButton("💾 Add Rule")
        self.add_update_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        self.add_update_btn.clicked.connect(self.add_rule)
        builder_layout.addRow(self.add_update_btn)
        self.main_layout.addWidget(builder_group)

        # --- UI: Rules Table ---
        table_group = QGroupBox("Current Ruleset")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Object", "Condition", "Item Code", "Item Name", "Qty Formula"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.selectionModel().selectionChanged.connect(self.on_rule_selected)
        table_layout.addWidget(self.table)
        delete_rule_btn = QPushButton("🗑️ Delete Selected Rule")
        delete_rule_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 5px;")
        delete_rule_btn.clicked.connect(self.delete_rule)
        table_layout.addWidget(delete_rule_btn)
        self.main_layout.addWidget(table_group)

        self.load_rules()
        self.on_object_change(self.obj_combo.currentText())

    def on_object_change(self, obj_name):
        """Resets the condition builder when the target object type changes."""
        self.clear_condition_rows()
        self.add_condition_row()
        self.update_formula_chips(obj_name)

    def add_condition_row(self, condition=None):
        """Adds a new row of widgets for building a rule condition."""
        cond_row_widget = QWidget()
        row_layout = QHBoxLayout(cond_row_widget)
        
        logical_op_combo = QComboBox()
        logical_op_combo.addItems(["AND", "OR"])
        logical_op_combo.setVisible(len(self.condition_widgets) > 0)

        prop_combo = QComboBox()
        prop_combo.addItems(list(self.property_data[self.obj_combo.currentText()].keys()))
        
        op_combo = QComboBox()
        op_combo.addItems(['==', '!=', '>', '<', '>=', '<='])

        value_widget = QLineEdit() # Default placeholder
        
        rem_button = QPushButton("➖")
        rem_button.setFixedWidth(30)
        
        row_layout.addWidget(logical_op_combo)
        row_layout.addWidget(prop_combo)
        row_layout.addWidget(op_combo)
        row_layout.addWidget(value_widget)
        row_layout.addWidget(rem_button)

        widget_map = {
            'widget': cond_row_widget, 'logical_op': logical_op_combo,
            'prop': prop_combo, 'op': op_combo, 'value': value_widget,
            'rem_btn': rem_button
        }
        self.condition_widgets.append(widget_map)
        self.cond_rows_layout.addWidget(cond_row_widget)
        
        prop_combo.currentTextChanged.connect(lambda text, w=widget_map: self.on_property_change(text, w))
        rem_button.clicked.connect(lambda ch, w=cond_row_widget: self.remove_condition_row(w))
        
        self.on_property_change(prop_combo.currentText(), widget_map)

        if condition:
            if 'logical' in condition: logical_op_combo.setCurrentText(condition['logical'])
            prop_combo.setCurrentText(condition['prop'])
            op_combo.setCurrentText(condition['op'])

            value_widget = widget_map['value']
            val_str = str(condition['val'])
            if isinstance(value_widget, QComboBox): value_widget.setCurrentText(val_str)
            elif isinstance(value_widget, QSpinBox):
                try: value_widget.setValue(int(float(val_str)))
                except (ValueError, TypeError): pass
            elif isinstance(value_widget, QLineEdit): value_widget.setText(val_str)

    def remove_condition_row(self, widget_to_remove):
        """Removes a condition row from the UI."""
        if len(self.condition_widgets) <= 1: return
        for i, w_map in enumerate(self.condition_widgets):
            if w_map['widget'] == widget_to_remove:
                self.condition_widgets.pop(i)
                break
        widget_to_remove.deleteLater()
        if len(self.condition_widgets) > 0:
            self.condition_widgets[0]['logical_op'].setVisible(False)
    
    def clear_condition_rows(self):
        """Removes all condition rows from the UI."""
        for w_map in self.condition_widgets:
            w_map['widget'].deleteLater()
        self.condition_widgets.clear()

    def on_property_change(self, prop_name, widget_map):
        """
        Updates the value input widget (e.g., to a QComboBox or QSpinBox)
        based on the selected property.
        """
        obj_name = self.obj_combo.currentText()
        if not obj_name or not prop_name:
            return

        prop_info = self.property_data[obj_name].get(prop_name)
        current_widget = widget_map['value']
        
        # Determine the target widget type
        target_class = QLineEdit
        if isinstance(prop_info, list):
            target_class = QComboBox
        elif prop_info == 'int':
            target_class = QSpinBox

        # If the widget is not of the correct type, replace it
        if not isinstance(current_widget, target_class):
            new_widget = target_class()
            if isinstance(new_widget, QSpinBox):
                new_widget.setRange(-10000, 10000)
            
            layout = widget_map['widget'].layout()
            # The value widget is at index 3 in the row's layout
            layout.replaceWidget(current_widget, new_widget)
            current_widget.deleteLater()
            widget_map['value'] = new_widget
            current_widget = new_widget

        # Now that we have the correct widget type, update its contents
        if isinstance(current_widget, QComboBox):
            current_widget.clear()
            if isinstance(prop_info, list):
                current_widget.addItems([str(p) for p in prop_info])

    def update_formula_chips(self, obj_name):
        """Updates the formula helper chips based on the selected object type."""
        while self.formula_chips_layout.count():
            child = self.formula_chips_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        for var in self.formula_vars.get(obj_name, []) + ['+', '-', '*', '/', '(', ')', ' ']:
            btn = QPushButton(var)
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda ch, v=var: self.add_to_formula(v))
            self.formula_chips_layout.addWidget(btn)
        self.formula_chips_layout.addStretch()

    def add_to_formula(self, text):
        """Appends text to the formula input field."""
        current_text = self.formula_input.text()
        if current_text == "1" and text not in ['+', '-', '*', '/', '(', ')', ' ']:
            self.formula_input.setText(text)
        else:
            self.formula_input.setText(current_text + text)

    def search_database(self):
        """Opens the search dialog to select a result item for the rule."""
        db_type, ok = QInputDialog.getItem(self, "Select Database", "Source:", ["Material", "Labor"], 0, False)
        if ok and db_type:
            dialog = SearchDialog(db_type, self)
            if dialog.exec():
                self.selected_item = dialog.get_selected()
                if self.selected_item:
                    self.item_label.setText(f"({self.selected_item['type']}) {self.selected_item['name']}")

    def add_rule(self):
        """Compiles the UI fields into a rule dictionary and saves it."""
        if not self.selected_item:
            QMessageBox.warning(self, "Incomplete Rule", "Please select a result item from the database first.")
            return

        condition_parts = []
        for i, w_map in enumerate(self.condition_widgets):
            prop = w_map['prop'].currentText()
            if not prop: continue

            if i > 0:
                condition_parts.append(w_map['logical_op'].currentText().lower())
            
            op = w_map['op'].currentText()
            
            value_widget = w_map['value']
            if isinstance(value_widget, QComboBox): val = value_widget.currentText()
            elif isinstance(value_widget, QSpinBox): val = value_widget.value()
            else: val = value_widget.text()
            
            if str(val).lower() == 'true': val = True
            elif str(val).lower() == 'false': val = False
            
            if isinstance(val, str) and not val.isnumeric():
                val = f"'{val}'"

            condition_parts.append(f"{prop} {op} {val}")
        
        condition_str = " ".join(condition_parts) if condition_parts else "True"

        new_rule = {
            "object": self.obj_combo.currentText(),
            "condition": condition_str,
            "type": self.selected_item['type'],
            "item_code": self.selected_item['code'],
            "item_name": self.selected_item.get('name') or self.selected_item.get('item_name'),
            "formula": self.formula_input.text()
        }

        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            self.rules[selected_rows[0].row()] = new_rule
        else:
            self.rules.append(new_rule)
        
        self.populate_table()
        self.save_rules()
        self.clear_builder()

    def delete_rule(self):
        """Deletes the selected rule from the table and `rules.json`."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a rule to delete.")
            return
        
        del self.rules[selected_rows[0].row()]
        self.populate_table()
        self.save_rules()
    
    def on_rule_selected(self, selected, deselected):
        """Populates the rule builder with the data from the selected rule."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.clear_builder()
            return
        
        rule = self.rules[selected_rows[0].row()]
        self.clear_builder()
        self.obj_combo.setCurrentText(rule['object'])

        self.clear_condition_rows()
        conditions = re.split(r'\s+(?:and|or)\s+', rule['condition'], flags=re.IGNORECASE)
        logicals = re.findall(r'\s+(and|or)\s+', rule['condition'], flags=re.IGNORECASE)
        
        for i, cond_str in enumerate(conditions):
            parts = cond_str.strip().split(' ', 2)
            if len(parts) != 3: continue
            
            condition_data = {
                'prop': parts[0], 'op': parts[1], 'val': parts[2].strip("'\"")
            }
            if i > 0: condition_data['logical'] = logicals[i-1].upper()

            self.add_condition_row(condition_data)

        self.selected_item = rule
        self.item_label.setText(f"({rule.get('type', '')}) {rule.get('item_name', '')}")
        self.formula_input.setText(rule['formula'])
        self.add_update_btn.setText("💾 Update Rule")

    def clear_builder(self):
        """Resets the rule builder fields to their default state."""
        self.table.clearSelection()
        self.clear_condition_rows()
        self.add_condition_row()
        self.item_label.clear()
        self.selected_item = None
        self.formula_input.setText("1")
        self.add_update_btn.setText("💾 Add Rule")

    def load_rules(self):
        """Loads rules from `rules.json` into memory."""
        try:
            with open('rules.json', 'r') as f:
                self.rules = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.rules = []
        self.populate_table()

    def save_rules(self):
        """Saves the current set of rules to `rules.json`."""
        try:
            with open('rules.json', 'w') as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rules.json: {e}")

    def populate_table(self):
        """Fills the rules table with the current rules."""
        self.table.setRowCount(0)
        for i, rule in enumerate(self.rules):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(rule.get('object', '')))
            self.table.setItem(i, 1, QTableWidgetItem(rule.get('condition', '')))
            self.table.setItem(i, 2, QTableWidgetItem(rule.get('item_code', '')))
            self.table.setItem(i, 3, QTableWidgetItem(rule.get('item_name', 'MISSING_NAME')))
            self.table.setItem(i, 4, QTableWidgetItem(rule.get('formula', '')))
