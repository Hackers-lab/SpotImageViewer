"""
This module defines the objects that are drawn on the canvas, such as
poles, spans, and homes. These objects contain their own properties and
visual representation logic.
"""
import math
from PyQt6.QtWidgets import QGraphicsPathItem
from PyQt6.QtGui import QPainterPath, QBrush, QColor, QPen, QFont
from PyQt6.QtCore import Qt

# Import custom components from other modules in the refactored app
from ui_components import DraggableLabel

class SmartPole(QGraphicsPathItem):
    """A pole on the canvas, which can be LT, HT, or DTR type."""
    def __init__(self, x, y, refresh_signal, pole_type="LT", is_existing=False):
        super().__init__()
        self.setPos(x, y)
        self.setZValue(10) 
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.refresh_signal = refresh_signal
        self.pole_type = pole_type
        self.is_existing = is_existing
        self.height = "8MTR" if pole_type == "LT" else "9MTR"
        self.has_extension = False
        self.override_auto_stay = False        
        self.structure_type = "DP/DTR"
        self.custom_note = ""
        self.dynamic_props = {}

        if self.is_existing:
            self.dtr_size = "None"
            self.earth_count = 0
            self.stay_count = 0
        elif self.pole_type == "DTR":
            self.dtr_size = "None"
            self.earth_count = 2
            self.stay_count = 4  
        else:
            self.dtr_size = "None"
            self.earth_count = 1
            self.stay_count = 0

        self.connected_spans = []
        self.label = DraggableLabel(self)
        self.label.setTextWidth(80)
        self.ext_label = DraggableLabel(self)
        self.ext_label.setFont(QFont("Arial", 6, QFont.Weight.Bold))
        self.ext_label.setPlainText("Ext")
        self.ext_label.setPos(-10, -30)
        self.update_visuals()

    def update_visuals(self):
        """Updates the pole's appearance based on its properties."""
        path = QPainterPath()
        if self.pole_type == "DTR":
            path.addEllipse(-8, -20, 16, 16)
            path.addEllipse(-8, 4, 16, 16)
            path.moveTo(0, -4)
            path.lineTo(0, 4)
            self.label.setPos(-40, 20) 
        else:
            if self.structure_type == "4P":
                path.addRect(-10, -10, 20, 20)
            elif self.structure_type == "TP":
                path.moveTo(-10, -10)
                path.lineTo(10, -10)
                path.lineTo(0, 10)
                path.addEllipse(-10, -10, 20, 20)
            else: # Default shape for LT/HT poles if structure_type is not 4P or TP
                path.addEllipse(-8, -8, 16, 16) # A simple circle
            self.label.setPos(-40, 12) 
        self.setPath(path)

        self.ext_label.setVisible(self.has_extension)

        if self.is_existing:
            self.setBrush(QBrush(QColor("#dddddd"))) # Lighter gray
            self.setPen(QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.SolidLine))
            lbl_text = "Existing DP/DTR" if self.pole_type == 'DTR' else f"Existing {self.pole_type} Pole"
        else:
            self.setPen(QPen(Qt.GlobalColor.black, 1))
            if self.pole_type == "LT":
                self.setBrush(QBrush(Qt.GlobalColor.blue))
                lbl_text = f"LT Pole ({self.height[:-2]})"
            elif self.pole_type == "HT":
                self.setBrush(QBrush(Qt.GlobalColor.red))
                lbl_text = f"HT Pole ({self.height[:-2]})"
            elif self.pole_type == "DTR":
                self.setBrush(QBrush(Qt.GlobalColor.green))
                lbl_text = "DP Structure" if self.dtr_size == "None" else f"DP Structure\n{self.dtr_size} DTR"
        
        if self.earth_count > 0: lbl_text += f"\n+ {self.earth_count} Earth"
        if self.stay_count > 0: lbl_text += f"\n+ {self.stay_count} Stay"
        if self.custom_note: lbl_text += f"\nNote: {self.custom_note}"
        self.label.setPlainText(lbl_text)

    def itemChange(self, change, value):
        """Called by Qt when the item's state changes, e.g., when it moves."""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans: 
                span.update_position()
            if self.refresh_signal:
                self.refresh_signal.emit()

        return super().itemChange(change, value)


class SmartHome(QGraphicsPathItem):
    """Represents a consumer's home on the canvas."""
    def __init__(self, x, y, refresh_signal):
        super().__init__()
        self.setPos(x, y)
        self.setZValue(10)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.refresh_signal = refresh_signal
        self.connected_spans = []
        self.custom_note = ""
        self.dynamic_props = {}
        
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
        self.label.setTextWidth(60)
        self.label.setPos(-30, 22)
        self.update_visuals()

    def update_visuals(self):
        """Updates the home's label."""
        lbl_text = "Consumer\nHome"
        if self.custom_note:
            lbl_text += f"\nNote: {self.custom_note}"
        self.label.setPlainText(lbl_text)

    def itemChange(self, change, value):
        """Called by Qt when the item's state changes."""
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            for span in self.connected_spans: 
                span.update_position()
            if self.refresh_signal:
                self.refresh_signal.emit()
        return super().itemChange(change, value)


class SmartSpan(QGraphicsPathItem):
    """Represents a span (cable/wire) between two poles or a pole and a home."""
    def __init__(self, pole1, pole2):
        super().__init__()
        self.p1 = pole1
        self.p2 = pole2
        self.setZValue(0)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
        
        self.is_existing_span = False
        self.custom_note = ""
        self.dynamic_props = {}

        self.is_service_drop = isinstance(self.p1, SmartHome) or isinstance(self.p2, SmartHome)
        if self.is_service_drop:
            self.conductor = "Service Drop"
            self.length = 20
            self.consider_cable = False
            self.cable_size = "10 SQMM"
            self.phase = "3 Phase"
            self.has_cg = False
            self.aug_type = "New"
            self.wire_count = "3"
            self.wire_size = "50SQMM"
        else:
            is_ht = getattr(self.p1, 'pole_type', 'LT') != 'LT' or getattr(self.p2, 'pole_type', 'LT') != 'LT'
            self.conductor = "ACSR" if is_ht else "AB Cable"
            self.length = 40
            self.aug_type = "New"
            self.wire_count = "3"
            self.wire_size = "50SQMM"
            self.cable_size = "25 SQMM"
            self.has_cg = False 

        self.label = DraggableLabel()
        self.label.setTextWidth(80)
        self.update_position()
        self.update_visuals()

    def update_position(self):
        """Recalculates the path of the line between the two connected points."""
        path = QPainterPath()
        path.moveTo(self.p1.x(), self.p1.y())
        dx = self.p2.x() - self.p1.x()
        dy = self.p2.y() - self.p1.y()
        px_length = math.hypot(dx, dy)

        # Draw a wavy line for flexible cables
        if self.conductor in ["AB Cable", "PVC Cable", "Service Drop"] and px_length > 0:
            steps = max(20, int(px_length / 2))
            nx = -dy / px_length
            ny = dx / px_length
            
            wave_wavelength_pixels = 15
            frequency = px_length / wave_wavelength_pixels
            amplitude = 4

            for i in range(1, steps + 1):
                t = i / float(steps)
                cx = self.p1.x() + dx * t
                cy = self.p1.y() + dy * t
                sine_offset = math.sin(t * frequency * 2 * math.pi) * amplitude
                path.lineTo(cx + nx * sine_offset, cy + ny * sine_offset)
        else:  # Draw a straight line for rigid conductors like ACSR
            path.lineTo(self.p2.x(), self.p2.y())

        self.setPath(path)
        
        # Reposition the label to the midpoint of the span
        if px_length > 0:
            nx_norm = -dy / px_length
            ny_norm = dx / px_length
            mid_x = (self.p1.x() + self.p2.x()) / 2
            mid_y = (self.p1.y() + self.p2.y()) / 2
            self.label.setPos(mid_x + (nx_norm * 15) - 40, mid_y + (ny_norm * 15) - 10)

    def update_visuals(self):
        """Updates the span's appearance (color, style) and text label."""
        self.update_position()
        pen = QPen(Qt.GlobalColor.black, 1.5)

        if self.is_existing_span:
            pen.setColor(Qt.GlobalColor.black)
            pen.setStyle(Qt.PenStyle.SolidLine)
        else: # New line
            if self.conductor == "ACSR":
                 pen.setStyle(Qt.PenStyle.DashLine)
            if self.conductor == "PVC Cable":
                pen.setColor(QColor("#107C41"))
        self.setPen(pen)
        
        if self.is_existing_span:
            lbl_text = f"Ex. {self.conductor}"
        elif self.is_service_drop:
            lbl_text = f"Service Cable {self.length}m\n{self.phase}"
            if self.consider_cable: lbl_text += f"\n({self.cable_size} PVC)"
        else:
            if self.conductor == "ACSR": lbl_text = f"{self.length}m\n{self.wire_count}W ACSR"
            elif self.conductor == "PVC Cable": lbl_text = f"{self.length}m\n{self.cable_size} PVC"
            else: lbl_text = f"{self.length}m\nABC"
            if self.aug_type != "New": lbl_text += f"\n({self.aug_type})"
            if self.has_cg: lbl_text += f"\n[+CG]"
        
        if self.custom_note: lbl_text += f"\nNote: {self.custom_note}"

        self.label.setPlainText(lbl_text)
        if not self.label.scene() and self.scene():
            self.scene().addItem(self.label)
