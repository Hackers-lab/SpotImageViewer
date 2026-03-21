import sys
import math
import json
import os
import sqlite3
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QGraphicsView, QGraphicsScene, 
                             QGraphicsTextItem, QFormLayout, QGroupBox, QSpinBox, QGraphicsPathItem, 
                             QLineEdit, QFileDialog, QMessageBox, QCheckBox)
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QTextOption, QPainter, QPageLayout
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtPrintSupport import QPrinter

# --- 1. DATABASE SETUP (V6 FULL MASTER SET) ---
def setup_database():
    conn = sqlite3.connect('dr_enterprises_master.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS materials (item_name TEXT PRIMARY KEY, rate REAL, unit TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS labor (task_name TEXT PRIMARY KEY, rate REAL, unit TEXT)''')
    
    materials = [
        ("PCC Pole 8M", 5363.44, "Nos"), ("PCC Pole 9M", 7663.31, "Nos"),
        ("DTR 16 KVA", 50906.51, "Nos"), ("DTR 25 KVA", 103528.11, "Nos"),
        ("DTR 63 KVA", 107589.53, "Nos"), ("DTR 100 KVA", 144370.09, "Nos"),
        ("M.S. Channel (per MT)", 76451.71, "MT"), ("M.S. Angle (per MT)", 73741.59, "MT"),
        ("M.S. Flat (per MT)", 79505.78, "MT"), ("Suspension Clamp", 367.62, "Nos"),
        ("D-Iron Clamp", 33.02, "Nos"), ("Shackle Insulator", 45.00, "Nos"), 
        ("Disc Insulator (11KV)", 350.00, "Nos"), ("Pin Insulator (11KV)", 150.00, "Nos"),
        ("ACSR Conductor (per KM)", 38676.40, "KM"), ("LT AB Cable (per KM)", 315558.99, "KM"), 
        ("Earthing Set", 1250.00, "Nos"), ("Stay Set Complete", 1850.00, "Nos"),
        ("5mm GI Wire (per MT)", 65000.00, "MT"), ("HT Stay Wire (per MT)", 70000.00, "MT"),
        ("G.I. 8 SWG Wire (4mm)", 60000.00, "MT"), ("Caution Board-11KVA", 160.18, "Nos"),
        ("UH-LT BKT 4 WAY", 500.00, "Nos"), ("UH-CLAMP FOR 8 MTR PCC POLE", 150.00, "Nos"),
        ("UH-Diron Clump", 40.00, "Nos"), ("LT Spacer 3 PHASE 4 WIRE", 77.62, "Nos")
    ]
    labor = [
        ("Pole Erection 8M", 1501.00, "Nos"), ("Pole Erection 9M", 2534.00, "Nos"),
        ("DTR Erection", 3214.00, "Nos"), ("Stringing ACSR (per KM)", 8289.00, "KM"), 
        ("Stringing AB Cable (per KM)", 46000.00, "KM"), ("Dismantle 2W ACSR (per KM)", 1981.00, "KM"),
        ("Earthing Labor", 313.00, "Nos"), ("Stay Labor", 641.00, "Nos"),
        ("Fabrication & Fixing of Cattle Guard Bracket (SP)", 237.00, "Nos"),
        ("Fabrication & Fixing of Cattle Guard Bracket (DP)", 369.00, "Nos"),
        ("Extension of 8 mtr PCC Pole (Without Painted)HT", 1506.00, "Nos"),
        ("Fixing Cross lacing", 15.00, "Nos"), ("Lead Wire above 60 Mtrs (2 Wire)", 506.00, "Nos"),
        ("Fixing of Caution Board", 24.00, "Nos"), ("Fixing of LT Bkt", 596.00, "Nos")
    ]
    cursor.executemany('INSERT OR IGNORE INTO materials VALUES (?,?,?)', materials)
    cursor.executemany('INSERT OR IGNORE INTO labor VALUES (?,?,?)', labor)
    conn.commit(); conn.close()

# --- 2. CUSTOM UI ELEMENTS & INTERACTIVE VIEW ---
class InteractiveView(QGraphicsView):
    def __init__(self, scene, parent_app):
        super().__init__(scene)
        self.parent_app = parent_app
        self.setRenderHints(self.renderHints() | self.renderHints().Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        zoom_in, zoom_out = 1.15, 1.0 / 1.15
        self.scale(zoom_in if event.angleDelta().y() > 0 else zoom_out, zoom_in if event.angleDelta().y() > 0 else zoom_out)

    def mousePressEvent(self, event):
        self.parent_app.handle_canvas_click(event, self)
        super().mousePressEvent(event)

class DraggableLabel(QGraphicsTextItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignCenter))
        self.setZValue(20) 

    def paint(self, painter, option, widget):
        painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
        painter.setPen(QPen(Qt.PenStyle.NoPen)) 
        painter.drawRect(self.boundingRect())
        super().paint(painter, option, widget)
        
    def avoid_overlap(self):
        if not self.scene(): return
        for item in self.collidingItems():
            if isinstance(item, DraggableLabel) and item != self:
                self.moveBy(0, 25); self.avoid_overlap(); break

# --- 3. SMART GRAPHICS OBJECTS ---
class SmartPole(QGraphicsPathItem):
    def __init__(self, x, y, pole_type="LT", is_existing=False):
        super().__init__()
        self.setPos(x, y); self.setZValue(10) 
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.pole_type = pole_type; self.is_existing = is_existing
        self.height = "8M" if pole_type == "LT" else "9M"
        
        if self.pole_type == "DTR":
            self.dtr_size = "None"; self.earth_count = 2; self.stay_count = 4  
        else:
            self.dtr_size = "None"; self.earth_count = 0 if self.is_existing else 1; self.stay_count = 0

        self.connected_spans = []
        self.label = DraggableLabel(self); self.label.setTextWidth(120)
        self.update_visuals()

    def update_visuals(self):
        path = QPainterPath()
        if self.pole_type == "DTR":
            path.addEllipse(-8, -20, 16, 16); path.addEllipse(-8, 4, 16, 16)   
            path.moveTo(0, -4); path.lineTo(0, 4); self.label.setPos(-60, 25) 
        else:
            path.addEllipse(-10, -10, 20, 20); self.label.setPos(-60, 15) 
            
        self.setPath(path)

        if self.is_existing:
            self.setBrush(QBrush(Qt.GlobalColor.lightGray)); self.setPen(QPen(Qt.GlobalColor.darkGray, 1, Qt.PenStyle.DashLine))
            lbl_text = "Existing Pole"
        else:
            self.setPen(QPen(Qt.GlobalColor.black, 1))
            if self.pole_type == "LT": self.setBrush(QBrush(Qt.GlobalColor.blue)); lbl_text = f"LT Pole ({self.height})"
            elif self.pole_type == "HT": self.setBrush(QBrush(Qt.GlobalColor.red)); lbl_text = f"HT Pole ({self.height})"
            elif self.pole_type == "DTR": self.setBrush(QBrush(Qt.GlobalColor.green)); lbl_text = "DP Structure" if self.dtr_size == "None" else f"DP Structure\n{self.dtr_size} DTR"
            
        if self.earth_count > 0: lbl_text += f"\n+ {self.earth_count} Earth"
        if self.stay_count > 0: lbl_text += f"\n+ {self.stay_count} Stay"
        self.label.setPlainText(lbl_text)
        QTimer.singleShot(10, self.label.avoid_overlap)

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans: span.update_position()
        return super().itemChange(change, value)

class SmartHome(QGraphicsPathItem):
    def __init__(self, x, y):
        super().__init__()
        self.setPos(x, y); self.setZValue(10)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.connected_spans = []

        path = QPainterPath()
        path.addRect(-10, 0, 20, 20); path.moveTo(-15, 0); path.lineTo(0, -15); path.lineTo(15, 0); path.closeSubpath()
        self.setPath(path); self.setBrush(QBrush(Qt.GlobalColor.yellow)); self.setPen(QPen(Qt.GlobalColor.black, 1))

        self.label = DraggableLabel(self)
        self.label.setTextWidth(100); self.label.setPos(-50, 25); self.label.setPlainText("Consumer\nHome")

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans: span.update_position()
        return super().itemChange(change, value)

class SmartSpan(QGraphicsPathItem):
    def __init__(self, pole1, pole2):
        super().__init__()
        self.p1 = pole1; self.p2 = pole2; self.setZValue(0) 
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        
        self.conductor = "AB Cable" if getattr(self.p1, 'pole_type', 'LT') == "LT" else "ACSR"
        self.length = 40; self.aug_type = "New"; self.wire_count = "3"; self.wire_size = "50"
        self.has_cg = False # Cattle Guard Logic
        
        self.label = DraggableLabel(); self.label.setTextWidth(100)
        self.update_position(); self.update_visuals()

    def update_position(self):
        path = QPainterPath(); path.moveTo(self.p1.x(), self.p1.y())
        dx = self.p2.x() - self.p1.x(); dy = self.p2.y() - self.p1.y(); px_length = math.hypot(dx, dy)
        
        if self.conductor == "AB Cable" and px_length > 0:
            steps = max(1, int(px_length / 6)); nx, ny = -dy/px_length, dx/px_length 
            for i in range(1, steps + 1):
                t = i / steps; cx, cy = self.p1.x() + dx * t, self.p1.y() + dy * t
                amp = (4 if i % 2 == 0 else -4) if i != steps else 0 
                path.lineTo(cx + nx*amp, cy + ny*amp)
        else:
            path.lineTo(self.p2.x(), self.p2.y())
            
        self.setPath(path)
        nx_norm = -dy / (px_length if px_length>0 else 1); ny_norm = dx / (px_length if px_length>0 else 1)
        mid_x, mid_y = (self.p1.x() + self.p2.x()) / 2, (self.p1.y() + self.p2.y()) / 2
        self.label.setPos(mid_x + (nx_norm*30) - 50, mid_y + (ny_norm*30) - 15)

    def update_visuals(self):
        self.update_position(); self.setPen(QPen(Qt.GlobalColor.black, 1.5)) 
        if self.conductor == "ACSR": lbl_text = f"{self.length}m\n{self.wire_count}W ACSR"
        else: lbl_text = f"{self.length}m\nABC"
            
        if self.aug_type != "New": lbl_text += f"\n({self.aug_type})"
        if self.has_cg: lbl_text += f"\n[+CG]"
        self.label.setPlainText(lbl_text)
        
        if not self.label.scene() and self.scene(): self.scene().addItem(self.label)
        QTimer.singleShot(10, self.label.avoid_overlap)

# --- 4. MAIN APPLICATION UI ---
class EstimateAppV6(QMainWindow):
    def __init__(self):
        super().__init__()
        setup_database()
        self.setWindowTitle("D.R. Enterprises - Smart CAD Builder V6.0 (ULTIMATE)")
        self.setGeometry(50, 50, 1400, 800)
        self.current_tool = "SELECT"; self.span_start_pole = None; self.autosave_file = "autosave_drawing.json"

        main_widget = QWidget(); main_layout = QHBoxLayout(main_widget); self.setCentralWidget(main_widget)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel); main_layout.addWidget(left_panel, stretch=3)

        file_toolbar = QHBoxLayout()
        for txt, cmd in [("📄 New", self.new_drawing), ("📂 Open", self.load_from_file), ("💾 Save", self.save_to_file)]:
            btn = QPushButton(txt); btn.clicked.connect(cmd); btn.setStyleSheet("padding: 5px; font-weight: bold;"); file_toolbar.addWidget(btn)
        
        file_toolbar.addStretch()
        pdf_btn = QPushButton("🗺️ Export PDF Blueprint"); pdf_btn.clicked.connect(self.export_pdf)
        pdf_btn.setStyleSheet("padding: 5px; font-weight: bold; background-color: #d32f2f; color: white;")
        xl_btn = QPushButton("📊 Generate ERP Excel"); xl_btn.clicked.connect(self.generate_excel)
        xl_btn.setStyleSheet("padding: 5px; font-weight: bold; background-color: #107C41; color: white;")
        file_toolbar.addWidget(pdf_btn); file_toolbar.addWidget(xl_btn)
        left_layout.addLayout(file_toolbar)

        draw_toolbar = QHBoxLayout(); self.tools_btns = {}
        self.tools = { "SELECT": "🖱 Select / Edit", "ADD_LT": "🔵 Add LT", "ADD_HT": "🔴 Add HT", "ADD_DTR": "🟩 DP/DTR", "ADD_EXISTING": "⚪ Existing", "ADD_HOME": "🏠 Home", "ADD_SPAN": "📏 Span"}
        for key, txt in self.tools.items():
            btn = QPushButton(txt); btn.clicked.connect(lambda checked, t=key: self.set_tool(t))
            btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: lightgray;"); 
            draw_toolbar.addWidget(btn); self.tools_btns[key] = btn
        left_layout.addLayout(draw_toolbar)

        self.scene = QGraphicsScene(); self.scene.selectionChanged.connect(self.on_selection_changed)
        self.view = InteractiveView(self.scene, self); left_layout.addWidget(self.view)

        right_panel = QWidget(); self.right_layout = QVBoxLayout(right_panel); main_layout.addWidget(right_panel, stretch=1)
        
        # Project Headers & Global UH Toggle
        self.subject_input = QLineEdit(); self.subject_input.setPlaceholderText("Enter Project Name / Subject...")
        self.right_layout.addWidget(QLabel("<b>Project Subject:</b>")); self.right_layout.addWidget(self.subject_input)
        
        self.uh_checkbox = QCheckBox("Use UH (Readymade) Materials instead of Raw Steel")
        self.uh_checkbox.setStyleSheet("font-weight: bold; color: #107C41;")
        self.right_layout.addWidget(self.uh_checkbox); self.right_layout.addSpacing(15)
        
        self.editor_group = QGroupBox("Properties Editor"); self.editor_layout = QFormLayout(); self.editor_group.setLayout(self.editor_layout)
        self.right_layout.addWidget(self.editor_group); self.right_layout.addStretch()

        self.set_tool("SELECT"); self.load_autosave() 

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace): self.delete_selected_items()
        super().keyPressEvent(event)

    def delete_selected_items(self):
        items = self.scene.selectedItems()
        for item in items:
            if isinstance(item, SmartSpan): self.delete_item(item)
        for item in items:
            if isinstance(item, (SmartPole, SmartHome)): self.delete_item(item)

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        if self.span_start_pole: self.span_start_pole.setPen(QPen(Qt.GlobalColor.black, 1))
        self.span_start_pole = None
        
        # FIX: Solid Button Highlights
        for key, btn in self.tools_btns.items():
            btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: " + ("lightblue" if key == tool_name else "lightgray"))
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag if tool_name == "SELECT" else QGraphicsView.DragMode.NoDrag)

    def handle_canvas_click(self, event, view):
        if event.button() == Qt.MouseButton.RightButton: self.set_tool("SELECT"); return
        if self.current_tool == "SELECT": return

        pos = view.mapToScene(event.pos())
        item_clicked = self.scene.itemAt(pos, view.transform())

        if self.current_tool in ["ADD_LT", "ADD_HT", "ADD_DTR", "ADD_EXISTING"]:
            p_type = "LT" if self.current_tool == "ADD_EXISTING" else self.current_tool.split("_")[1]
            self.scene.addItem(SmartPole(pos.x(), pos.y(), p_type, self.current_tool == "ADD_EXISTING"))
        elif self.current_tool == "ADD_HOME":
            self.scene.addItem(SmartHome(pos.x(), pos.y()))
        elif self.current_tool == "ADD_SPAN" and isinstance(item_clicked, (SmartPole, SmartHome)):
            if not self.span_start_pole:
                self.span_start_pole = item_clicked; item_clicked.setPen(QPen(Qt.GlobalColor.yellow, 3)) 
            elif self.span_start_pole != item_clicked: 
                span = SmartSpan(self.span_start_pole, item_clicked)
                self.span_start_pole.connected_spans.append(span); item_clicked.connected_spans.append(span)
                self.scene.addItem(span); self.scene.addItem(span.label) 
                self.span_start_pole.setPen(QPen(Qt.GlobalColor.black, 1)); self.span_start_pole = None

    def on_selection_changed(self):
        while self.editor_layout.count():
            child = self.editor_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        sel = self.scene.selectedItems()
        if not sel: self.editor_group.setTitle("Select an item to edit"); return
        if len(sel) > 1: self.editor_group.setTitle(f"{len(sel)} Items Selected"); return
        item = sel[0]
        
        if isinstance(item, DraggableLabel): self.editor_group.setTitle("Text Label Selected"); return
        if isinstance(item, SmartPole):
            self.editor_group.setTitle(f"Editing {'Existing ' if item.is_existing else ''}{item.pole_type} Structure")
            if not item.is_existing:
                height_cb = QComboBox(); height_cb.addItems(["8M", "9M"]); height_cb.setCurrentText(item.height)
                height_cb.currentTextChanged.connect(lambda t: self.update_pole(item, "height", t)); self.editor_layout.addRow("Height:", height_cb)
                if item.pole_type == "DTR":
                    dtr_cb = QComboBox(); dtr_cb.addItems(["None", "16 KVA", "25 KVA", "63 KVA", "100 KVA", "160 KVA"])
                    dtr_cb.setCurrentText(item.dtr_size); dtr_cb.currentTextChanged.connect(lambda t: self.update_dtr_logic(item, t)); self.editor_layout.addRow("DTR Size:", dtr_cb)
            
            earth_spin = QSpinBox(); earth_spin.setRange(0, 10); earth_spin.setValue(item.earth_count)
            earth_spin.valueChanged.connect(lambda v: self.update_pole(item, "earth_count", v)); self.editor_layout.addRow("Earthing Sets:", earth_spin)
            stay_spin = QSpinBox(); stay_spin.setRange(0, 10); stay_spin.setValue(item.stay_count)
            stay_spin.valueChanged.connect(lambda v: self.update_pole(item, "stay_count", v)); self.editor_layout.addRow("Stay Sets:", stay_spin)

        elif isinstance(item, SmartSpan):
            self.editor_group.setTitle("Editing Span")
            length_spin = QSpinBox(); length_spin.setRange(1, 150); length_spin.setValue(int(item.length))
            length_spin.valueChanged.connect(lambda v: self.update_span(item, "length", v)); self.editor_layout.addRow("Length (Meters):", length_spin)
            
            cg_chk = QCheckBox(); cg_chk.setChecked(item.has_cg)
            cg_chk.stateChanged.connect(lambda v: self.update_span(item, "has_cg", v == 2)); self.editor_layout.addRow("Cattle Guard:", cg_chk)
            
            cond_cb = QComboBox(); cond_cb.addItems(["ACSR", "AB Cable"]); cond_cb.setCurrentText(item.conductor)
            cond_cb.currentTextChanged.connect(lambda t: self.update_conductor_logic(item, t)); self.editor_layout.addRow("Conductor:", cond_cb)
            
            if item.conductor == "ACSR":
                wire_cnt_cb = QComboBox(); wire_cnt_cb.addItems(["2", "3", "4"]); wire_cnt_cb.setCurrentText(item.wire_count)
                wire_cnt_cb.currentTextChanged.connect(lambda t: self.update_span(item, "wire_count", t)); self.editor_layout.addRow("Wire Count:", wire_cnt_cb)
                wire_sz_cb = QComboBox(); wire_sz_cb.addItems(["30", "50"]); wire_sz_cb.setCurrentText(item.wire_size)
                wire_sz_cb.currentTextChanged.connect(lambda t: self.update_span(item, "wire_size", t)); self.editor_layout.addRow("Wire Size:", wire_sz_cb)
                
            aug_cb = QComboBox(); aug_cb.addItems(["New", "Replace 2W->4W", "Add-on 2W"]); aug_cb.setCurrentText(item.aug_type)
            aug_cb.currentTextChanged.connect(lambda t: self.update_span(item, "aug_type", t)); self.editor_layout.addRow("Work Nature:", aug_cb)

        del_btn = QPushButton("🗑 Delete Selected Item"); del_btn.setStyleSheet("background-color: #ff4c4c; color: white;")
        del_btn.clicked.connect(lambda: self.delete_item(item)); self.editor_layout.addRow(del_btn)

    def update_pole(self, item, prop, value): setattr(item, prop, value); item.update_visuals()
    def update_span(self, item, prop, value): setattr(item, prop, value); item.update_visuals()
    def update_dtr_logic(self, item, size): item.dtr_size = size; item.earth_count = 5 if size != "None" else 2; item.update_visuals()
    def update_conductor_logic(self, item, conductor): item.conductor = conductor; item.update_visuals(); QTimer.singleShot(50, self.on_selection_changed) 
    def delete_item(self, item):
        if not item or not item.scene(): return
        if hasattr(item, 'connected_spans'):
            for span in list(item.connected_spans):
                if span.label.scene(): self.scene.removeItem(span.label)
                if span.scene(): self.scene.removeItem(span)
                if span in getattr(span.p1, 'connected_spans', []): span.p1.connected_spans.remove(span)
                if span in getattr(span.p2, 'connected_spans', []): span.p2.connected_spans.remove(span)
        if isinstance(item, SmartSpan) and item.label.scene(): self.scene.removeItem(item.label)
        if item.scene(): self.scene.removeItem(item)
        self.on_selection_changed()

    # --- 5. EXPORT ENGINES ---
    
    def export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export Blueprint", "Project_Blueprint.pdf", "PDF Files (*.pdf)")
        if not filename: return
        
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(filename); printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        
        source_rect = self.scene.itemsBoundingRect()
        if source_rect.isNull(): QMessageBox.warning(self, "Empty", "Canvas is empty."); return
        source_rect.adjust(-50, -50, 50, 50) 
        
        painter = QPainter(printer); page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        title_font = painter.font(); title_font.setPointSize(20); title_font.setBold(True); title_font.setUnderline(True); painter.setFont(title_font)
        painter.drawText(page_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.subject_input.text() or 'D.R. ENTERPRISES - PROJECT BLUEPRINT')
        
        legend_font = painter.font(); legend_font.setPointSize(10); painter.setFont(legend_font)
        legend_text = "LEGEND:\n\n🔵 Blue Circle = LT Pole\n🔴 Red Circle = HT Pole\n🟩 Green o-|-o = DP / Substation\n🟡 Yellow Square = Consumer Home\n〰〰 Wavy Line = AB Cable\n── Straight Line = ACSR Conductor\n[+CG] = Cattle Guard Installed"
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        legend_bounds = painter.boundingRect(QRectF(0, 0, page_rect.width(), page_rect.height()), flags, legend_text)
        
        pad, margin = 15, 40; box_width, box_height = legend_bounds.width() + (pad * 2), legend_bounds.height() + (pad * 2)
        legend_rect = QRectF(page_rect.width() - box_width - margin, page_rect.height() - box_height - margin, box_width, box_height)
        
        painter.setBrush(QBrush(Qt.GlobalColor.white)); painter.setPen(QPen(Qt.GlobalColor.black, 2)); painter.drawRect(legend_rect) 
        painter.setPen(QPen(Qt.GlobalColor.black)); painter.drawText(legend_rect.adjusted(pad, pad, -pad, -pad), flags, legend_text) 
        
        target_rect = QRectF(margin, 60, page_rect.width() - (2 * margin), page_rect.height() - 60 - box_height - margin - 20)
        self.scene.render(painter, target_rect, source_rect, Qt.AspectRatioMode.KeepAspectRatio)
        painter.end(); QMessageBox.information(self, "Success", f"Blueprint PDF exported to:\n{filename}")

    def generate_excel(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export ERP Estimate", "ERP_Estimate.xlsx", "Excel Files (*.xlsx)")
        if not filename: return
        
        raw_bom = {}; total_lab_tasks = {}
        use_uh = self.uh_checkbox.isChecked()
        
        for item in self.scene.items():
            if isinstance(item, SmartPole):
                if not item.is_existing:
                    p_type = f"PCC Pole {item.height}"
                    raw_bom[p_type] = raw_bom.get(p_type, 0) + 1
                    total_lab_tasks[f"Pole Erection {item.height}"] = total_lab_tasks.get(f"Pole Erection {item.height}", 0) + 1
                
                total_lab_tasks["Pole GIS survey"] = total_lab_tasks.get("Pole GIS survey", 0) + 1
                boards = 2 if item.pole_type == "DTR" else 1
                raw_bom["Caution Board-11KVA"] = raw_bom.get("Caution Board-11KVA", 0) + boards
                total_lab_tasks["Fixing of Caution Board"] = total_lab_tasks.get("Fixing of Caution Board", 0) + boards

                if item.height == "8M" and item.pole_type in ["HT", "DTR"]:
                    raw_bom["M.S. Channel (per MT)"] = raw_bom.get("M.S. Channel (per MT)", 0) + (6.0 * 7.5 / 1000)
                    raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + (3.0 * 3.5 / 1000)
                    total_lab_tasks["Extension of 8 mtr PCC Pole (Without Painted)HT"] = total_lab_tasks.get("Extension of 8 mtr PCC Pole (Without Painted)HT", 0) + 1

                if item.earth_count > 0:
                    raw_bom["Earthing Set"] = raw_bom.get("Earthing Set", 0) + item.earth_count
                    raw_bom["5mm GI Wire (per MT)"] = raw_bom.get("5mm GI Wire (per MT)", 0) + (item.earth_count * 0.003)
                    total_lab_tasks["Earthing Labor"] = total_lab_tasks.get("Earthing Labor", 0) + item.earth_count
                if item.stay_count > 0:
                    raw_bom["Stay Set Complete"] = raw_bom.get("Stay Set Complete", 0) + item.stay_count
                    raw_bom["HT Stay Wire (per MT)"] = raw_bom.get("HT Stay Wire (per MT)", 0) + (item.stay_count * 0.006)
                    total_lab_tasks["Stay Labor"] = total_lab_tasks.get("Stay Labor", 0) + item.stay_count
                
                has_cg = any(getattr(s, 'has_cg', False) for s in item.connected_spans)
                if has_cg:
                    if item.pole_type == "DTR":
                        raw_bom["M.S. Angle (per MT)"] = raw_bom.get("M.S. Angle (per MT)", 0) + (2.75 * 6.5 / 1000)
                        raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + (0.5 * 3.5 / 1000)
                        total_lab_tasks["Fabrication & Fixing of Cattle Guard Bracket (DP)"] = total_lab_tasks.get("Fabrication & Fixing of Cattle Guard Bracket (DP)", 0) + 1
                    else:
                        raw_bom["M.S. Angle (per MT)"] = raw_bom.get("M.S. Angle (per MT)", 0) + (1.9 * 6.5 / 1000)
                        raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + (0.5 * 3.5 / 1000)
                        total_lab_tasks["Fabrication & Fixing of Cattle Guard Bracket (SP)"] = total_lab_tasks.get("Fabrication & Fixing of Cattle Guard Bracket (SP)", 0) + 1

                if item.pole_type == "HT":
                    ht_spans = [s for s in item.connected_spans if s.conductor == "ACSR"]
                    if len(ht_spans) == 1: raw_bom["Disc Insulator (11KV)"] = raw_bom.get("Disc Insulator (11KV)", 0) + 3 
                    elif len(ht_spans) == 2: raw_bom["Pin Insulator (11KV)"] = raw_bom.get("Pin Insulator (11KV)", 0) + 3 
                    elif len(ht_spans) >= 3:
                        raw_bom["Disc Insulator (11KV)"] = raw_bom.get("Disc Insulator (11KV)", 0) + 3 
                        raw_bom["M.S. Channel (per MT)"] = raw_bom.get("M.S. Channel (per MT)", 0) + 0.015
                        raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + 0.005
                
                if item.pole_type == "DTR":
                    if item.dtr_size != "None":
                        raw_bom[f"DTR {item.dtr_size}"] = raw_bom.get(f"DTR {item.dtr_size}", 0) + 1
                        total_lab_tasks["DTR Erection"] = total_lab_tasks.get("DTR Erection", 0) + 1
                        raw_bom["M.S. Channel (per MT)"] = raw_bom.get("M.S. Channel (per MT)", 0) + 0.1087
                        raw_bom["M.S. Angle (per MT)"] = raw_bom.get("M.S. Angle (per MT)", 0) + 0.0796
                        raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + 0.0490
                        raw_bom["Disc Insulator (11KV)"] = raw_bom.get("Disc Insulator (11KV)", 0) + 9
                        raw_bom["Pin Insulator (11KV)"] = raw_bom.get("Pin Insulator (11KV)", 0) + 9
                        raw_bom["ACSR Conductor (per KM)"] = raw_bom.get("ACSR Conductor (per KM)", 0) + 0.030 
                    else:
                        raw_bom["M.S. Channel (per MT)"] = raw_bom.get("M.S. Channel (per MT)", 0) + 0.0375
                        raw_bom["M.S. Angle (per MT)"] = raw_bom.get("M.S. Angle (per MT)", 0) + 0.0125
                        raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + 0.0105
                        raw_bom["Disc Insulator (11KV)"] = raw_bom.get("Disc Insulator (11KV)", 0) + 6

            elif isinstance(item, SmartSpan):
                length_km = item.length / 1000.0
                cond_mat = "ACSR Conductor (per KM)" if item.conductor == "ACSR" else "LT AB Cable (per KM)"
                cond_lab = f"Stringing {item.conductor} (per KM)"
                
                if item.length > 60:
                    total_lab_tasks["Lead Wire above 60 Mtrs (2 Wire)"] = total_lab_tasks.get("Lead Wire above 60 Mtrs (2 Wire)", 0) + 1
                
                if item.has_cg:
                    raw_bom["G.I. 8 SWG Wire (4mm)"] = raw_bom.get("G.I. 8 SWG Wire (4mm)", 0) + (item.length * 0.001)
                    total_lab_tasks["Fixing Cross lacing"] = total_lab_tasks.get("Fixing Cross lacing", 0) + int(item.length / 2)

                wire_multiplier = int(item.wire_count) if item.conductor == "ACSR" else 1
                total_wire_km = length_km * wire_multiplier
                
                if item.aug_type in ["New", "Add-on 2W", "Replace 2W->4W"]:
                    raw_bom[cond_mat] = raw_bom.get(cond_mat, 0) + total_wire_km
                    total_lab_tasks[cond_lab] = total_lab_tasks.get(cond_lab, 0) + total_wire_km
                    
                if item.aug_type == "Replace 2W->4W":
                    total_lab_tasks["Dismantle 2W ACSR (per KM)"] = total_lab_tasks.get("Dismantle 2W ACSR (per KM)", 0) + (length_km * 2)
                    
                if item.conductor == "ACSR" and getattr(item.p1, 'pole_type', '') == "LT":
                    raw_bom["LT Spacer 3 PHASE 4 WIRE"] = raw_bom.get("LT Spacer 3 PHASE 4 WIRE", 0) + 4
                    if use_uh:
                        raw_bom["UH-LT BKT 4 WAY"] = raw_bom.get("UH-LT BKT 4 WAY", 0) + 1
                        raw_bom["UH-CLAMP FOR 8 MTR PCC POLE"] = raw_bom.get("UH-CLAMP FOR 8 MTR PCC POLE", 0) + 4
                        raw_bom["UH-Diron Clump"] = raw_bom.get("UH-Diron Clump", 0) + wire_multiplier
                        raw_bom["Shackle Insulator"] = raw_bom.get("Shackle Insulator", 0) + wire_multiplier
                        total_lab_tasks["Fixing of LT Bkt"] = total_lab_tasks.get("Fixing of LT Bkt", 0) + 1
                    else:
                        raw_bom["M.S. Angle (per MT)"] = raw_bom.get("M.S. Angle (per MT)", 0) + 0.009
                        raw_bom["D-Iron Clamp"] = raw_bom.get("D-Iron Clamp", 0) + wire_multiplier
                        raw_bom["Shackle Insulator"] = raw_bom.get("Shackle Insulator", 0) + wire_multiplier
                elif item.conductor == "AB Cable":
                    raw_bom["M.S. Flat (per MT)"] = raw_bom.get("M.S. Flat (per MT)", 0) + 0.0023
                    raw_bom["Suspension Clamp"] = raw_bom.get("Suspension Clamp", 0) + 1

        for key in raw_bom: raw_bom[key] = raw_bom[key] * 1.03

        conn = sqlite3.connect('dr_enterprises_master.db'); cursor = conn.cursor()
        bom_data = []; total_mat = 0; total_lab = 0
        
        for name, qty in raw_bom.items():
            cursor.execute("SELECT rate, unit FROM materials WHERE item_name=?", (name,)); res = cursor.fetchone()
            if res: amt = qty * res[0]; total_mat += amt; bom_data.append({"type": "Material", "name": name, "qty": qty, "unit": res[1], "rate": res[0], "amt": amt})
                
        for name, qty in total_lab_tasks.items():
            cursor.execute("SELECT rate, unit FROM labor WHERE task_name=?", (name,)); res = cursor.fetchone()
            if res: amt = qty * res[0]; total_lab += amt; bom_data.append({"type": "Labor", "name": name, "qty": qty, "unit": res[1], "rate": res[0], "amt": amt})
        conn.close()

        esc = total_mat * 0.05; sun = total_mat * 0.05; mat_subtotal = total_mat + esc + sun
        sup = (mat_subtotal + total_lab) * 0.10; gst = (total_lab + sup) * 0.18; g_tot = (mat_subtotal + total_lab + sup + gst) * 1.01

        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Estimate"
        ws.merge_cells('A1:F1'); ws['A1'] = "D.R. ENTERPRISES - AUTOMATED ESTIMATE"
        ws['A1'].font = Font(bold=True, size=14, color="FFFFFF"); ws['A1'].fill = PatternFill("solid", fgColor="4F81BD"); ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A2:F2'); ws['A2'] = f"Subject: {self.subject_input.text()} | Date: {datetime.now().strftime('%d-%m-%Y')}"
        ws.append(["Sl No.", "Description", "Qty (inc 3% waste)", "Unit", "Rate", "Amount"])
        for col_num, cell in enumerate(ws[3], 1): cell.font = Font(bold=True); ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = 15
        ws.column_dimensions['B'].width = 45

        row = 4
        ws.cell(row, 2, "A. MATERIALS").font = Font(bold=True); row += 1
        for i, item in enumerate([x for x in bom_data if x['type'] == 'Material'], 1):
            ws.append([i, item['name'], round(item['qty'],3), item['unit'], item['rate'], round(item['amt'],2)]); row += 1
        
        ws.append(["", "Material Base Total", "", "", "", round(total_mat, 2)]); row += 1
        ws.append(["", "Add: Escalation @ 5%", "", "", "", round(esc, 2)]); row += 1
        ws.append(["", "Add: Sundries @ 5%", "", "", "", round(sun, 2)]); row += 1
        ws.append(["", "TOTAL MATERIAL COST (A)", "", "", "", round(mat_subtotal, 2)])
        ws.cell(row, 2).font = Font(bold=True); ws.cell(row, 6).font = Font(bold=True); row += 2
        
        ws.cell(row, 2, "B. ERECTION / LABOR").font = Font(bold=True); row += 1
        for i, item in enumerate([x for x in bom_data if x['type'] == 'Labor'], 1):
            ws.append([i, item['name'], round(item['qty'],3), item['unit'], item['rate'], round(item['amt'],2)]); row += 1
            
        ws.append(["", "TOTAL LABOR COST (B)", "", "", "", round(total_lab, 2)])
        ws.cell(row, 2).font = Font(bold=True); ws.cell(row, 6).font = Font(bold=True); row += 2

        ws.append(["", "C. OVERHEADS & TAXES"]); ws.cell(row, 2).font = Font(bold=True); row += 1
        ws.append(["", "Supervision @ 10% on (A+B)", "", "", "", round(sup, 2)]); row += 1
        ws.append(["", "GST @ 18% on (Labor + Sup)", "", "", "", round(gst, 2)]); row += 1
        sub_c = mat_subtotal + total_lab + sup + gst
        ws.append(["", "Sub-Total", "", "", "", round(sub_c, 2)]); row += 1
        ws.append(["", "Add: Cess @ 1%", "", "", "", round(sub_c * 0.01, 2)]); row += 1
        ws.append(["", "GRAND TOTAL", "", "", "", round(g_tot, 2)])
        ws.cell(row, 2).font = Font(bold=True, size=12); ws.cell(row, 6).font = Font(bold=True, size=12, color="FF0000")
        
        wb.save(filename); QMessageBox.information(self, "Success", f"ERP Estimate Excel saved to:\n{filename}")

    # File Management (Kept identical)
    def new_drawing(self):
        if QMessageBox.question(self, 'New Canvas', 'Clear canvas?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.scene.clear(); self.subject_input.clear(); self.span_start_pole = None; self.uh_checkbox.setChecked(False)
            while self.editor_layout.count():
                child = self.editor_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            
    def compile_save_data(self):
        state = {'subject': self.subject_input.text(), 'uh_toggle': self.uh_checkbox.isChecked(), 'nodes': [], 'spans': []}; node_map = {}
        for i, item in enumerate(self.scene.items()):
            if isinstance(item, (SmartPole, SmartHome)):
                item._temp_id = i; node_map[i] = item
                node_data = {'id': i, 'type': 'Pole' if isinstance(item, SmartPole) else 'Home', 'x': item.x(), 'y': item.y(), 'label_x': item.label.pos().x(), 'label_y': item.label.pos().y(), 'label_text': item.label.toPlainText()}
                if isinstance(item, SmartPole): node_data.update({'pole_type': item.pole_type, 'is_existing': item.is_existing, 'height': item.height, 'dtr_size': item.dtr_size, 'earth_count': item.earth_count, 'stay_count': item.stay_count})
                state['nodes'].append(node_data)
        for item in self.scene.items():
            if isinstance(item, SmartSpan): state['spans'].append({'p1_id': item.p1._temp_id, 'p2_id': item.p2._temp_id, 'length': item.length, 'conductor': item.conductor, 'has_cg': item.has_cg, 'aug_type': item.aug_type, 'wire_count': item.wire_count, 'wire_size': item.wire_size, 'label_x': item.label.pos().x(), 'label_y': item.label.pos().y(), 'label_text': item.label.toPlainText()})
        return state

    def parse_load_data(self, state):
        self.scene.clear(); self.subject_input.setText(state.get('subject', '')); self.uh_checkbox.setChecked(state.get('uh_toggle', False)); node_map = {}
        for n_data in state.get('nodes', []):
            if n_data['type'] == 'Pole':
                pole = SmartPole(n_data['x'], n_data['y'], n_data['pole_type'], n_data.get('is_existing', False)); pole.height = n_data['height']; pole.dtr_size = n_data['dtr_size']; pole.earth_count = n_data['earth_count']; pole.stay_count = n_data['stay_count']; pole.update_visuals(); pole.label.setPos(n_data['label_x'], n_data['label_y']); pole.label.setPlainText(n_data['label_text']); self.scene.addItem(pole); node_map[n_data['id']] = pole
            else:
                home = SmartHome(n_data['x'], n_data['y']); home.label.setPos(n_data['label_x'], n_data['label_y']); home.label.setPlainText(n_data['label_text']); self.scene.addItem(home); node_map[n_data['id']] = home
        for s_data in state.get('spans', []):
            p1 = node_map.get(s_data['p1_id']); p2 = node_map.get(s_data['p2_id'])
            if p1 and p2:
                span = SmartSpan(p1, p2); span.length = s_data['length']; span.conductor = s_data['conductor']; span.has_cg = s_data.get('has_cg', False); span.aug_type = s_data['aug_type']; span.wire_count = s_data.get('wire_count', '3'); span.wire_size = s_data.get('wire_size', '50'); span.update_visuals(); span.label.setPos(s_data['label_x'], s_data['label_y']); span.label.setPlainText(s_data['label_text']); p1.connected_spans.append(span); p2.connected_spans.append(span); self.scene.addItem(span); self.scene.addItem(span.label)

    def save_to_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'w') as f: json.dump(self.compile_save_data(), f)

    def load_from_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f: self.parse_load_data(json.load(f))

    def load_autosave(self):
        if os.path.exists(self.autosave_file):
            with open(self.autosave_file, 'r') as f: self.parse_load_data(json.load(f))

    def closeEvent(self, event):
        with open(self.autosave_file, 'w') as f: json.dump(self.compile_save_data(), f)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EstimateAppV6()
    window.show()
    sys.exit(app.exec())