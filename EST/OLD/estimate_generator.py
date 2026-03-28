import sys
import math
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QGraphicsView, QGraphicsScene, 
                             QGraphicsTextItem, QFormLayout, QGroupBox, QSpinBox, QGraphicsPathItem, 
                             QLineEdit, QFileDialog, QMessageBox)
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QTextOption
from PyQt6.QtCore import Qt, QTimer

# --- 1. CUSTOM UI ELEMENTS & INTERACTIVE VIEW ---

class InteractiveView(QGraphicsView):
    """Custom View to handle Mouse Wheel Zooming and Drag Selection"""
    def __init__(self, scene, parent_app):
        super().__init__(scene)
        self.parent_app = parent_app
        self.setRenderHints(self.renderHints() | self.renderHints().Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        # Handle Zoom In/Out
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        # Route clicks to the main app logic first
        self.parent_app.handle_canvas_click(event, self)
        # Then let QGraphicsView handle standard selection/dragging
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
                self.moveBy(0, 25) 
                self.avoid_overlap() 
                break

# --- 2. SMART GRAPHICS OBJECTS ---
# (SmartPole, SmartHome, and SmartSpan remain identical to previous version)

class SmartPole(QGraphicsPathItem):
    def __init__(self, x, y, pole_type="LT", is_existing=False):
        super().__init__()
        self.setPos(x, y)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(10) 
        
        self.pole_type = pole_type 
        self.is_existing = is_existing
        self.height = "8M" if pole_type == "LT" else "9M"
        
        if self.pole_type == "DTR":
            self.dtr_size = "None"
            self.earth_count = 2 
            self.stay_count = 4  
        else:
            self.dtr_size = "None"
            self.earth_count = 0 if self.is_existing else 1 
            self.stay_count = 0

        self.connected_spans = []
        self.label = DraggableLabel(self)
        self.label.setTextWidth(120)
        self.update_visuals()

    def update_visuals(self):
        path = QPainterPath()
        if self.pole_type == "DTR":
            path.addEllipse(-8, -20, 16, 16) 
            path.addEllipse(-8, 4, 16, 16)   
            path.moveTo(0, -4)
            path.lineTo(0, 4)                
            self.label.setPos(-60, 25) 
        else:
            path.addEllipse(-10, -10, 20, 20) 
            self.label.setPos(-60, 15) 
            
        self.setPath(path)

        if self.is_existing:
            self.setBrush(QBrush(Qt.GlobalColor.lightGray))
            self.setPen(QPen(Qt.GlobalColor.darkGray, 1, Qt.PenStyle.DashLine))
            lbl_text = "Existing Pole"
        else:
            self.setPen(QPen(Qt.GlobalColor.black, 1))
            if self.pole_type == "LT":
                self.setBrush(QBrush(Qt.GlobalColor.blue))
                lbl_text = f"LT Pole ({self.height})"
            elif self.pole_type == "HT":
                self.setBrush(QBrush(Qt.GlobalColor.red))
                lbl_text = f"HT Pole ({self.height})"
            elif self.pole_type == "DTR":
                self.setBrush(QBrush(Qt.GlobalColor.green))
                lbl_text = "DP Structure" if self.dtr_size == "None" else f"DP Structure\n{self.dtr_size} DTR"
            
        if self.earth_count > 0: lbl_text += f"\n+ {self.earth_count} Earth"
        if self.stay_count > 0: lbl_text += f"\n+ {self.stay_count} Stay"
        
        self.label.setPlainText(lbl_text)
        QTimer.singleShot(10, self.label.avoid_overlap)

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans:
                span.update_position()
        return super().itemChange(change, value)


class SmartHome(QGraphicsPathItem):
    def __init__(self, x, y):
        super().__init__()
        self.setPos(x, y)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(10)
        self.connected_spans = []

        path = QPainterPath()
        path.addRect(-10, 0, 20, 20) 
        path.moveTo(-15, 0)
        path.lineTo(0, -15) 
        path.lineTo(15, 0) 
        path.closeSubpath()
        
        self.setPath(path)
        self.setBrush(QBrush(Qt.GlobalColor.yellow))
        self.setPen(QPen(Qt.GlobalColor.black, 1))

        self.label = DraggableLabel(self)
        self.label.setTextWidth(100)
        self.label.setPos(-50, 25) 
        self.label.setPlainText("Consumer\nHome")

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans:
                span.update_position()
        return super().itemChange(change, value)


class SmartSpan(QGraphicsPathItem):
    def __init__(self, pole1, pole2):
        super().__init__()
        self.p1 = pole1
        self.p2 = pole2
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(0) 
        
        self.conductor = "AB Cable" if getattr(self.p1, 'pole_type', 'LT') == "LT" else "ACSR"
        self.length = 40
        self.aug_type = "New"
        self.wire_count = "3"
        self.wire_size = "50"
        
        self.label = DraggableLabel()
        self.label.setTextWidth(100)
        
        self.update_position()
        self.update_visuals()

    def update_position(self):
        path = QPainterPath()
        path.moveTo(self.p1.x(), self.p1.y())
        
        dx = self.p2.x() - self.p1.x()
        dy = self.p2.y() - self.p1.y()
        px_length = math.hypot(dx, dy)
        
        if self.conductor == "AB Cable" and px_length > 0:
            steps = int(px_length / 6)
            if steps == 0: steps = 1
            ux, uy = dx/px_length, dy/px_length
            nx, ny = -uy, ux 
            for i in range(1, steps + 1):
                t = i / steps
                cx = self.p1.x() + dx * t
                cy = self.p1.y() + dy * t
                amp = 4 if i % 2 == 0 else -4
                if i == steps: amp = 0 
                path.lineTo(cx + nx*amp, cy + ny*amp)
        else:
            path.lineTo(self.p2.x(), self.p2.y())
            
        self.setPath(path)
        
        if px_length == 0: px_length = 1
        nx_norm = -dy / px_length
        ny_norm = dx / px_length
        mid_x = (self.p1.x() + self.p2.x()) / 2
        mid_y = (self.p1.y() + self.p2.y()) / 2
        
        offset_x = nx_norm * 30
        offset_y = ny_norm * 30
        
        self.label.setPos(mid_x + offset_x - 50, mid_y + offset_y - 15)

    def update_visuals(self):
        self.update_position() 
        self.setPen(QPen(Qt.GlobalColor.black, 1.5)) 
        
        if self.conductor == "ACSR":
            lbl_text = f"{self.length}m\n{self.wire_count}W ACSR"
        else:
            lbl_text = f"{self.length}m\nABC"
            
        if self.aug_type != "New":
            lbl_text += f"\n({self.aug_type})"
            
        self.label.setPlainText(lbl_text)
        
        if not self.label.scene() and self.scene():
            self.scene().addItem(self.label)
            
        QTimer.singleShot(10, self.label.avoid_overlap)


# --- 3. MAIN APPLICATION UI & WORKFLOW ---

class EstimateAppV4(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("D.R. Enterprises - Smart CAD Builder V5")
        self.setGeometry(50, 50, 1400, 800)
        
        self.current_tool = "SELECT"
        self.span_start_pole = None
        self.autosave_file = "autosave_drawing.json"

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        main_layout.addWidget(left_panel, stretch=3)

        # File Management Toolbar
        file_toolbar = QHBoxLayout()
        new_btn = QPushButton("📄 New Canvas"); new_btn.clicked.connect(self.new_drawing)
        open_btn = QPushButton("📂 Open Plan"); open_btn.clicked.connect(self.load_from_file)
        save_btn = QPushButton("💾 Save As..."); save_btn.clicked.connect(self.save_to_file)
        for btn in [new_btn, open_btn, save_btn]:
            btn.setStyleSheet("padding: 5px; font-weight: bold;")
            file_toolbar.addWidget(btn)
        file_toolbar.addStretch()
        left_layout.addLayout(file_toolbar)

        # Drawing Toolbar
        draw_toolbar = QHBoxLayout()
        self.tools = {
            "SELECT": QPushButton("🖱 Select / Edit"),
            "ADD_LT": QPushButton("🔵 Add LT"),
            "ADD_HT": QPushButton("🔴 Add HT"),
            "ADD_DTR": QPushButton("🟩 DP/DTR"),
            "ADD_EXISTING": QPushButton("⚪ Existing"),
            "ADD_HOME": QPushButton("🏠 Home"),
            "ADD_SPAN": QPushButton("📏 Span")
        }
        for key, btn in self.tools.items():
            btn.clicked.connect(lambda checked, t=key: self.set_tool(t))
            btn.setStyleSheet("padding: 8px; font-weight: bold;")
            draw_toolbar.addWidget(btn)
        left_layout.addLayout(draw_toolbar)

        # Canvas Setup with the new InteractiveView
        self.scene = QGraphicsScene()
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.view = InteractiveView(self.scene, self)
        left_layout.addWidget(self.view)

        right_panel = QWidget()
        self.right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel, stretch=1)
        
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Enter Project Name / Subject...")
        self.right_layout.addWidget(QLabel("<b>Project Subject (For PDF Export):</b>"))
        self.right_layout.addWidget(self.subject_input)
        self.right_layout.addSpacing(15)
        
        self.editor_group = QGroupBox("Properties Editor")
        self.editor_layout = QFormLayout()
        self.editor_group.setLayout(self.editor_layout)
        self.right_layout.addWidget(self.editor_group)
        self.right_layout.addStretch()

        self.set_tool("SELECT")
        self.load_autosave() 

    # --- KEYBOARD SHORTCUTS ---
    def keyPressEvent(self, event):
        # Handle Delete Key for bulk deletion
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            self.delete_selected_items()
        super().keyPressEvent(event)

    def delete_selected_items(self):
        items = self.scene.selectedItems()
        if not items: return
        
        # We must delete lines first to avoid crashing when deleting connected poles
        for item in items:
            if isinstance(item, SmartSpan): self.delete_item(item)
        for item in items:
            if isinstance(item, (SmartPole, SmartHome)): self.delete_item(item)

    # --- CANVAS LOGIC ---
    def set_tool(self, tool_name):
        self.current_tool = tool_name
        if self.span_start_pole:
            self.span_start_pole.setPen(QPen(Qt.GlobalColor.black, 1))
        self.span_start_pole = None
        
        for key, btn in self.tools.items():
            btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: " + 
                              ("lightblue" if key == tool_name else "lightgray"))
                              
        # Enable Drag Selection ONLY when the Select tool is active
        if tool_name == "SELECT":
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def handle_canvas_click(self, event, view):
        if event.button() == Qt.MouseButton.RightButton:
            self.set_tool("SELECT")
            return

        if self.current_tool == "SELECT":
            return # Let standard QGraphicsView handle selection clicking

        pos = view.mapToScene(event.pos())
        item_clicked = self.scene.itemAt(pos, view.transform())

        if self.current_tool in ["ADD_LT", "ADD_HT", "ADD_DTR", "ADD_EXISTING"]:
            p_type = "LT" if self.current_tool == "ADD_EXISTING" else self.current_tool.split("_")[1]
            is_exist = (self.current_tool == "ADD_EXISTING")
            pole = SmartPole(pos.x(), pos.y(), p_type, is_exist)
            self.scene.addItem(pole)

        elif self.current_tool == "ADD_HOME":
            home = SmartHome(pos.x(), pos.y())
            self.scene.addItem(home)

        elif self.current_tool == "ADD_SPAN":
            if isinstance(item_clicked, (SmartPole, SmartHome)):
                if not self.span_start_pole:
                    self.span_start_pole = item_clicked 
                    item_clicked.setPen(QPen(Qt.GlobalColor.yellow, 3)) 
                else:
                    if self.span_start_pole != item_clicked: 
                        span = SmartSpan(self.span_start_pole, item_clicked)
                        self.span_start_pole.connected_spans.append(span)
                        item_clicked.connected_spans.append(span)
                        self.scene.addItem(span)
                        self.scene.addItem(span.label) 
                    
                    self.span_start_pole.setPen(QPen(Qt.GlobalColor.black, 1)) 
                    self.span_start_pole = None

    def clear_editor(self):
        while self.editor_layout.count():
            child = self.editor_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def on_selection_changed(self):
        self.clear_editor()
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.editor_group.setTitle("Select an item to edit")
            return
            
        if len(selected_items) > 1:
            self.editor_group.setTitle(f"{len(selected_items)} Items Selected")
            self.editor_layout.addRow(QLabel("Press 'Delete' to remove items."))
            return

        item = selected_items[0]
        
        if isinstance(item, DraggableLabel):
            self.editor_group.setTitle("Text Label Selected")
            self.editor_layout.addRow(QLabel("<i>Drag text to move it.<br>Double-click text to edit.</i>"))
            return

        if isinstance(item, SmartPole):
            self.editor_group.setTitle(f"Editing {'Existing ' if item.is_existing else ''}{item.pole_type} Structure")
            
            if not item.is_existing:
                height_cb = QComboBox()
                height_cb.addItems(["8M", "9M"])
                height_cb.setCurrentText(item.height)
                height_cb.currentTextChanged.connect(lambda t: self.update_pole(item, "height", t))
                self.editor_layout.addRow("Height:", height_cb)

                if item.pole_type == "DTR":
                    dtr_cb = QComboBox()
                    dtr_cb.addItems(["None", "16 KVA", "25 KVA", "63 KVA", "100 KVA", "160 KVA"])
                    dtr_cb.setCurrentText(item.dtr_size)
                    dtr_cb.currentTextChanged.connect(lambda t: self.update_dtr_logic(item, t))
                    self.editor_layout.addRow("DTR Size:", dtr_cb)

            earth_spin = QSpinBox(); earth_spin.setRange(0, 10)
            earth_spin.setValue(item.earth_count)
            earth_spin.valueChanged.connect(lambda v: self.update_pole(item, "earth_count", v))
            self.editor_layout.addRow("Earthing Sets:", earth_spin)

            stay_spin = QSpinBox(); stay_spin.setRange(0, 10)
            stay_spin.setValue(item.stay_count)
            stay_spin.valueChanged.connect(lambda v: self.update_pole(item, "stay_count", v))
            self.editor_layout.addRow("Stay Sets:", stay_spin)

        elif isinstance(item, SmartHome):
            self.editor_group.setTitle("Editing Consumer Home")
            self.editor_layout.addRow(QLabel("Service connection target."))

        elif isinstance(item, SmartSpan):
            self.editor_group.setTitle("Editing Span")
            
            length_spin = QSpinBox(); length_spin.setRange(1, 150)
            length_spin.setValue(int(item.length))
            length_spin.valueChanged.connect(lambda v: self.update_span(item, "length", v))
            self.editor_layout.addRow("Length (Meters):", length_spin)

            cond_cb = QComboBox()
            cond_cb.addItems(["ACSR", "AB Cable"])
            cond_cb.setCurrentText(item.conductor)
            cond_cb.currentTextChanged.connect(lambda t: self.update_conductor_logic(item, t))
            self.editor_layout.addRow("Conductor:", cond_cb)

            if item.conductor == "ACSR":
                wire_cnt_cb = QComboBox()
                wire_cnt_cb.addItems(["2", "3", "4"])
                wire_cnt_cb.setCurrentText(item.wire_count)
                wire_cnt_cb.currentTextChanged.connect(lambda t: self.update_span(item, "wire_count", t))
                self.editor_layout.addRow("Wire Count:", wire_cnt_cb)

                wire_sz_cb = QComboBox()
                wire_sz_cb.addItems(["30", "50"]) 
                wire_sz_cb.setCurrentText(item.wire_size)
                wire_sz_cb.currentTextChanged.connect(lambda t: self.update_span(item, "wire_size", t))
                self.editor_layout.addRow("Wire Size (sqmm):", wire_sz_cb)

            aug_cb = QComboBox()
            aug_cb.addItems(["New", "Replace 2W->4W", "Add-on 2W"])
            aug_cb.setCurrentText(item.aug_type)
            aug_cb.currentTextChanged.connect(lambda t: self.update_span(item, "aug_type", t))
            self.editor_layout.addRow("Work Nature:", aug_cb)

        del_btn = QPushButton("🗑 Delete Selected Item")
        del_btn.setStyleSheet("background-color: #ff4c4c; color: white; padding: 5px;")
        del_btn.clicked.connect(lambda: self.delete_item(item))
        self.editor_layout.addRow(del_btn)

    # --- Property Updaters ---
    def update_pole(self, item, prop, value):
        setattr(item, prop, value)
        item.update_visuals()

    def update_span(self, item, prop, value):
        setattr(item, prop, value)
        item.update_visuals()

    def update_dtr_logic(self, item, size):
        item.dtr_size = size
        item.earth_count = 5 if size != "None" else 2
        item.update_visuals()

    def update_conductor_logic(self, item, conductor):
        item.conductor = conductor
        item.update_visuals()
        QTimer.singleShot(50, self.on_selection_changed) 

    def delete_item(self, item):
        if not item or not item.scene(): return
        if hasattr(item, 'connected_spans'):
            for span in list(item.connected_spans):
                if span.label.scene(): self.scene.removeItem(span.label)
                if span.scene(): self.scene.removeItem(span)
                if span in getattr(span.p1, 'connected_spans', []): span.p1.connected_spans.remove(span)
                if span in getattr(span.p2, 'connected_spans', []): span.p2.connected_spans.remove(span)
        if isinstance(item, SmartSpan) and item.label.scene():
            self.scene.removeItem(item.label)
        if item.scene():
            self.scene.removeItem(item)
        self.on_selection_changed()

    # --- FILE MANAGEMENT ENGINE ---
    def new_drawing(self):
        reply = QMessageBox.question(self, 'New Canvas', 'Clear canvas? Unsaved progress will be lost.', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.subject_input.clear()
            self.span_start_pole = None
            self.clear_editor()
            
    def compile_save_data(self):
        state = {'subject': self.subject_input.text(), 'nodes': [], 'spans': []}
        node_map = {}
        for i, item in enumerate(self.scene.items()):
            if isinstance(item, (SmartPole, SmartHome)):
                item._temp_id = i
                node_map[i] = item
                node_data = {
                    'id': i, 'type': 'Pole' if isinstance(item, SmartPole) else 'Home',
                    'x': item.x(), 'y': item.y(),
                    'label_x': item.label.pos().x(), 'label_y': item.label.pos().y(),
                    'label_text': item.label.toPlainText()
                }
                if isinstance(item, SmartPole):
                    node_data.update({
                        'pole_type': item.pole_type, 'is_existing': item.is_existing,
                        'height': item.height, 'dtr_size': item.dtr_size,
                        'earth_count': item.earth_count, 'stay_count': item.stay_count
                    })
                state['nodes'].append(node_data)
                
        for item in self.scene.items():
            if isinstance(item, SmartSpan):
                state['spans'].append({
                    'p1_id': item.p1._temp_id, 'p2_id': item.p2._temp_id,
                    'length': item.length, 'conductor': item.conductor,
                    'aug_type': item.aug_type, 'wire_count': item.wire_count,
                    'wire_size': item.wire_size,
                    'label_x': item.label.pos().x(), 'label_y': item.label.pos().y(),
                    'label_text': item.label.toPlainText()
                })
        return state

    def parse_load_data(self, state):
        self.scene.clear()
        self.subject_input.setText(state.get('subject', ''))
        node_map = {}
        
        for n_data in state.get('nodes', []):
            if n_data['type'] == 'Pole':
                pole = SmartPole(n_data['x'], n_data['y'], n_data['pole_type'], n_data.get('is_existing', False))
                pole.height = n_data['height']
                pole.dtr_size = n_data['dtr_size']
                pole.earth_count = n_data['earth_count']
                pole.stay_count = n_data['stay_count']
                pole.update_visuals()
                pole.label.setPos(n_data['label_x'], n_data['label_y'])
                pole.label.setPlainText(n_data['label_text'])
                self.scene.addItem(pole)
                node_map[n_data['id']] = pole
            else:
                home = SmartHome(n_data['x'], n_data['y'])
                home.label.setPos(n_data['label_x'], n_data['label_y'])
                home.label.setPlainText(n_data['label_text'])
                self.scene.addItem(home)
                node_map[n_data['id']] = home
                
        for s_data in state.get('spans', []):
            p1 = node_map.get(s_data['p1_id'])
            p2 = node_map.get(s_data['p2_id'])
            if p1 and p2:
                span = SmartSpan(p1, p2)
                span.length = s_data['length']
                span.conductor = s_data['conductor']
                span.aug_type = s_data['aug_type']
                span.wire_count = s_data.get('wire_count', '3')
                span.wire_size = s_data.get('wire_size', '50')
                span.update_visuals()
                span.label.setPos(s_data['label_x'], s_data['label_y'])
                span.label.setPlainText(s_data['label_text'])
                p1.connected_spans.append(span)
                p2.connected_spans.append(span)
                self.scene.addItem(span)
                self.scene.addItem(span.label)

    def save_to_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.compile_save_data(), f)
            QMessageBox.information(self, "Saved", f"Project successfully saved to:\n{filename}")

    def load_from_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                self.parse_load_data(json.load(f))

    def load_autosave(self):
        if os.path.exists(self.autosave_file):
            with open(self.autosave_file, 'r') as f:
                self.parse_load_data(json.load(f))

    def closeEvent(self, event):
        with open(self.autosave_file, 'w') as f:
            json.dump(self.compile_save_data(), f)
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EstimateAppV4()
    window.show()
    sys.exit(app.exec())