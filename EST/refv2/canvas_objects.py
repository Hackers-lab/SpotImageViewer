"""
canvas_objects.py
=================
Defines the four interactive canvas objects for ERP Estimate Generator v5.0:

    SmartPole      — LT or HT single pole (PCC / STP / H-BEAM)
    SmartStructure — Multi-pole HT structures (DP / TP / 4P / DTR sub-station)
    SmartSpan      — Conductor span between any two endpoints
    SmartConsumer  — Consumer service point (replaces SmartHome)

Visual improvements over v4
----------------------------
  • Stay wire — diagonal line + anchor drawn attached to pole/structure symbol
  • Earth symbol — standard ⏚ (3 decreasing horizontal bars) below pole base
  • CG symbol — small crosshatch bracket drawn at span midpoint below the line
  • TP symbol — 3 circles in triangular arrangement
  • 4P symbol — 4 circles in square arrangement
  • Detail-view toggle — stay/earth/CG symbols hidden when detail_view=False
  • Pole colour coding: LT=blue, HT=red, Existing=grey
  • Structure colour coding: DP/TP/4P=dark-green, DTR=orange
"""

import math
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsItemGroup
from PyQt6.QtGui import (
    QPainterPath, QBrush, QColor, QPen, QFont, QPainter
)
from PyQt6.QtCore import Qt, QRectF, QPointF

from ui_components import DraggableLabel


# ─────────────────────────────────────────────────────────────────────────────
#  SHARED DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _earth_path(x_off: float = 0, y_off: float = 0) -> QPainterPath:
    """
    Draws the standard IEC earth / ground symbol (⏚):
      a short vertical stem, then 3 horizontal bars of decreasing width.
    Origin is the top of the stem (where it meets the pole base).
    """
    p = QPainterPath()
    # Vertical stem
    p.moveTo(x_off,      y_off)
    p.lineTo(x_off,      y_off + 6)
    # Bar 1 (widest)
    p.moveTo(x_off - 6,  y_off + 6)
    p.lineTo(x_off + 6,  y_off + 6)
    # Bar 2
    p.moveTo(x_off - 4,  y_off + 9)
    p.lineTo(x_off + 4,  y_off + 9)
    # Bar 3 (narrowest)
    p.moveTo(x_off - 2,  y_off + 12)
    p.lineTo(x_off + 2,  y_off + 12)
    return p


def _stay_path(angle_deg: float = 225) -> QPainterPath:
    """
    Draws a stay-wire symbol: a diagonal line from pole centre outward,
    with a small filled diamond anchor at the far end.
    angle_deg — direction of stay wire (default: lower-left = 225°)
    """
    length = 18
    rad    = math.radians(angle_deg)
    ex     = math.cos(rad) * length
    ey     = math.sin(rad) * length

    p = QPainterPath()
    p.moveTo(0, 0)
    p.lineTo(ex, ey)
    # Small diamond anchor
    d = 3
    p.moveTo(ex,       ey - d)
    p.lineTo(ex + d,   ey)
    p.lineTo(ex,       ey + d)
    p.lineTo(ex - d,   ey)
    p.closeSubpath()
    return p


def _cg_path() -> QPainterPath:
    """
    Draws the CG (Cattle Guard) bracket symbol: a small downward bracket
    with two diagonal crosshatch lines, centred at (0,0).
    Placed below the span midpoint.
    """
    p = QPainterPath()
    # Bracket outline
    p.moveTo(-7, 0)
    p.lineTo(-7, 7)
    p.lineTo( 7, 7)
    p.lineTo( 7, 0)
    # Crosshatch lines inside bracket
    p.moveTo(-7, 0)
    p.lineTo( 7, 7)
    p.moveTo( 7, 0)
    p.lineTo(-7, 7)
    return p


# ─────────────────────────────────────────────────────────────────────────────
#  BASE MIXIN  — common flags + itemChange + detail_view propagation
# ─────────────────────────────────────────────────────────────────────────────

class _NodeMixin:
    """
    Mixin providing shared setup for all node-type canvas items
    (SmartPole, SmartStructure, SmartConsumer).
    Call _init_node() from the subclass __init__ after super().__init__().
    """
    def _init_node(self, x, y, refresh_signal, detail_view=True):
        self.setPos(x, y)
        self.setZValue(10)
        F = QGraphicsPathItem.GraphicsItemFlag
        self.setFlag(F.ItemIsSelectable)
        self.setFlag(F.ItemIsMovable)
        self.setFlag(F.ItemSendsGeometryChanges)

        self.refresh_signal  = refresh_signal
        self.detail_view     = detail_view
        self.connected_spans = []
        self.custom_note     = ""
        self.dynamic_props   = {}

    def _on_position_changed(self):
        for span in self.connected_spans:
            span.update_position()
        if self.refresh_signal:
            self.refresh_signal.emit()


# ─────────────────────────────────────────────────────────────────────────────
#  SmartPole
# ─────────────────────────────────────────────────────────────────────────────

class SmartPole(_NodeMixin, QGraphicsPathItem):
    """
    A single LT or HT pole on the canvas.

    Properties
    ----------
    pole_type        : "LT" | "HT"
    pole_type2       : "PCC" | "STP" | "H-BEAM"
    height           : "8MTR" | "9MTR" | "9.5MTR" | "11MTR" | "13MTR"
    is_existing      : bool
    has_extension    : bool
    extension_height : float  (metres, only used when has_extension=True)
    earth_count      : int
    stay_count       : int
    override_auto_stay : bool
    detail_view      : bool   (show stay/earth symbols)
    """

    def __init__(
        self, x, y, refresh_signal,
        pole_type="LT", is_existing=False,
        detail_view=True
    ):
        QGraphicsPathItem.__init__(self)
        self._init_node(x, y, refresh_signal, detail_view)

        self.pole_type          = pole_type
        self.pole_type2         = "PCC"
        self.is_existing        = is_existing
        self.height             = "8MTR" if pole_type == "LT" else "9MTR"
        self.has_extension      = False
        self.extension_height   = 3.0
        self.override_auto_stay = False

        if is_existing:
            self.earth_count = 0
            self.stay_count  = 0
        else:
            self.earth_count = 1
            self.stay_count  = 0

        # Label — child of this item so it moves with the pole
        self.label = DraggableLabel(self)
        self.label.setTextWidth(90)

        self.update_visuals()

    # ── Visual update ─────────────────────────────────────────────────────────

    def update_visuals(self):
        path = QPainterPath()

        # Main pole circle
        r = 9
        path.addEllipse(-r, -r, r * 2, r * 2)

        # Extension indicator — small square on top
        if self.has_extension:
            path.addRect(-4, -(r + 10), 8, 8)

        # Earth symbol — drawn below pole centre
        if self.detail_view and self.earth_count > 0:
            for i in range(min(self.earth_count, 3)):
                x_off = (i - (min(self.earth_count, 3) - 1) / 2) * 14
                path.addPath(_earth_path(x_off, r + 2))

        # Stay wire symbols — one per stay set
        if self.detail_view and self.stay_count > 0:
            stay_angles = [225, 315, 180, 0]
            for i in range(min(self.stay_count, 4)):
                path.addPath(_stay_path(stay_angles[i % 4]))

        self.setPath(path)

        # Colours
        black_pen = QPen(Qt.GlobalColor.black, 1)
        if self.is_existing:
            self.setBrush(QBrush(QColor("#cccccc")))
            self.setPen(QPen(Qt.GlobalColor.darkGray, 1, Qt.PenStyle.DashLine))
        elif self.pole_type == "LT":
            self.setBrush(QBrush(QColor("#2980b9")))   # blue
            self.setPen(black_pen)
        else:  # HT
            self.setBrush(QBrush(QColor("#c0392b")))   # red
            self.setPen(black_pen)

        # Label text
        if self.is_existing:
            txt = f"Ex. {self.pole_type} Pole"
        else:
            ht_m = self.height.replace("MTR", "m")
            txt  = f"{self.pole_type} Pole\n{self.pole_type2} {ht_m}"
            if self.has_extension:
                txt += f"\n+Ext {self.extension_height:.1f}m"

        if not self.is_existing:
            if self.earth_count > 0:
                txt += f"\n⏚ {self.earth_count} Earth"
            if self.stay_count > 0:
                txt += f"\nS×{self.stay_count} Stay"
        if self.custom_note:
            txt += f"\n📝 {self.custom_note}"

        self.label.setPlainText(txt)
        self.label.setPos(-(self.label.boundingRect().width() / 2), 14)

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            self._on_position_changed()
        return super().itemChange(change, value)


# ─────────────────────────────────────────────────────────────────────────────
#  SmartStructure
# ─────────────────────────────────────────────────────────────────────────────

class SmartStructure(_NodeMixin, QGraphicsPathItem):
    """
    An HT multi-pole structure on the canvas.

    Structure types and their canvas symbols
    ----------------------------------------
    DP  — 2 circles side by side  (like old DTR symbol)
    TP  — 3 circles in triangle
    4P  — 4 circles in square (2×2)
    DTR — 2 circles + horizontal transformer body between them

    Earth defaults: DP=2, TP=3, 4P=4, DTR=5
    Stay default  : 4 for all types
    """

    _EARTH_DEFAULTS = {"DP": 2, "TP": 3, "4P": 4, "DTR": 5}
    _COLORS = {
        "DP":  QColor("#27ae60"),   # green
        "TP":  QColor("#1abc9c"),   # teal
        "4P":  QColor("#16a085"),   # dark teal
        "DTR": QColor("#e67e22"),   # orange
    }

    def __init__(self, x, y, refresh_signal, detail_view=True):
        QGraphicsPathItem.__init__(self)
        self._init_node(x, y, refresh_signal, detail_view)

        self.structure_type   = "DP"
        self.pole_type2       = "PCC"
        self.height           = "9MTR"
        self.has_extension    = False
        self.extension_height = 3.0
        self.earth_count      = self._EARTH_DEFAULTS["DP"]
        self.stay_count       = 4
        self.dtr_size         = "None"

        self.label = DraggableLabel(self)
        self.label.setTextWidth(100)

        self.update_visuals()

    # ── Visual update ─────────────────────────────────────────────────────────

    def update_visuals(self):
        path = QPainterPath()
        r    = 8   # circle radius
        gap  = 6   # gap between circles

        st = self.structure_type

        if st == "DP":
            # Two circles side by side
            cx = r + gap // 2
            path.addEllipse(-cx - r, -r, r * 2, r * 2)
            path.addEllipse( cx - r, -r, r * 2, r * 2)
            # Connecting bar
            path.moveTo(-cx + r, 0)
            path.lineTo( cx - r, 0)

        elif st == "TP":
            # Triangle: top + bottom-left + bottom-right
            offsets = [
                (0,           -(r + gap // 2)),          # top
                (-(r + gap),   (r + gap // 2)),           # bottom-left
                ( (r + gap),   (r + gap // 2)),           # bottom-right
            ]
            for ox, oy in offsets:
                path.addEllipse(ox - r, oy - r, r * 2, r * 2)

        elif st == "4P":
            # 2×2 square grid
            d = r + gap // 2
            for ox, oy in [(-d, -d), (d, -d), (-d, d), (d, d)]:
                path.addEllipse(ox - r, oy - r, r * 2, r * 2)

        elif st == "DTR":
            # Two circles with transformer body between
            cx = r + gap // 2 + 4
            path.addEllipse(-cx - r, -r, r * 2, r * 2)
            path.addEllipse( cx - r, -r, r * 2, r * 2)
            # Transformer body — rectangle
            path.addRect(-gap // 2 - 2, -r // 2, gap + 4, r)
            # HV/LV winding hint lines
            path.moveTo(-gap // 2 - 2, 0)
            path.lineTo( gap // 2 + 2, 0)

        # Extension indicator
        if self.has_extension:
            path.addRect(-4, -(r * 2 + 14), 8, 8)

        # Earth symbols below structure
        if self.detail_view and self.earth_count > 0:
            bottom_y = r + 2 if st in ("DP", "DTR") else r + gap // 2 + r + 2
            for i in range(min(self.earth_count, 5)):
                x_off = (i - (min(self.earth_count, 5) - 1) / 2) * 14
                path.addPath(_earth_path(x_off, bottom_y))

        # Stay wire symbols
        if self.detail_view and self.stay_count > 0:
            stay_angles = [225, 315, 180, 0, 270, 90]
            for i in range(min(self.stay_count, 6)):
                path.addPath(_stay_path(stay_angles[i % 6]))

        self.setPath(path)

        # Colour
        color = self._COLORS.get(st, QColor("#27ae60"))
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.GlobalColor.black, 1.5))

        # Label
        ht_m = self.height.replace("MTR", "m")
        txt  = f"{st} Structure\n{self.pole_type2} {ht_m}"
        if st == "DTR" and self.dtr_size != "None":
            txt += f"\n{self.dtr_size} DTR"
        if self.has_extension:
            txt += f"\n+Ext {self.extension_height:.1f}m"
        if self.earth_count > 0:
            txt += f"\n⏚ {self.earth_count} Earth"
        if self.stay_count > 0:
            txt += f"\nS×{self.stay_count} Stay"
        if self.custom_note:
            txt += f"\n📝 {self.custom_note}"

        self.label.setPlainText(txt)
        self.label.setPos(-(self.label.boundingRect().width() / 2), 26)

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            self._on_position_changed()
        return super().itemChange(change, value)


# ─────────────────────────────────────────────────────────────────────────────
#  SmartConsumer
# ─────────────────────────────────────────────────────────────────────────────

class SmartConsumer(_NodeMixin, QGraphicsPathItem):
    """
    A consumer service point on the canvas (replaces SmartHome).

    Symbol: house shape (same as before) — yellow fill.
    Agency supply shown as 'A' badge on the symbol when True.

    Properties
    ----------
    phase         : "1 Phase" | "3 Phase"
    cable_size    : e.g. "10 SQMM"
    agency_supply : bool  — True = agency supplied, False = WBSEDCL
    """

    def __init__(self, x, y, refresh_signal, detail_view=True):
        QGraphicsPathItem.__init__(self)
        self._init_node(x, y, refresh_signal, detail_view)

        self.phase         = "3 Phase"
        self.cable_size    = "10 SQMM"
        self.agency_supply = False

        # Build house path (static — does not change)
        house = QPainterPath()
        house.addRect(-10, 0, 20, 18)       # walls
        house.moveTo(-14, 0)
        house.lineTo(0, -14)                 # roof left
        house.lineTo(14, 0)                  # roof right
        self.setPath(house)
        self.setBrush(QBrush(QColor("#f1c40f")))   # yellow
        self.setPen(QPen(Qt.GlobalColor.black, 1))

        self.label = DraggableLabel(self)
        self.label.setTextWidth(70)
        self.label.setPos(-35, 20)

        self.update_visuals()

    # ── Visual update ─────────────────────────────────────────────────────────

    def update_visuals(self):
        phase_short = "1φ" if self.phase == "1 Phase" else "3φ"
        supply_tag  = " [A]" if self.agency_supply else ""
        txt = f"Consumer\n{phase_short}{supply_tag}"
        if self.custom_note:
            txt += f"\n📝 {self.custom_note}"
        self.label.setPlainText(txt)

        # Colour hint for agency vs WBSEDCL
        if self.agency_supply:
            self.setBrush(QBrush(QColor("#f39c12")))   # darker amber = agency
        else:
            self.setBrush(QBrush(QColor("#f1c40f")))   # bright yellow = WBSEDCL

    # ── Qt overrides ──────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsPathItem.GraphicsItemChange.ItemPositionHasChanged:
            self._on_position_changed()
        return super().itemChange(change, value)


# ─────────────────────────────────────────────────────────────────────────────
#  SmartSpan
# ─────────────────────────────────────────────────────────────────────────────

class SmartSpan(QGraphicsPathItem):
    """
    A conductor span between two canvas endpoints
    (SmartPole, SmartStructure, or SmartConsumer).

    Voltage auto-detection
    ----------------------
    is_lt_span = True  when at least one endpoint is a SmartPole with
                       pole_type == "LT", or when either endpoint is a
                       SmartConsumer. HT structures always produce HT spans.

    Conductor defaults
    ------------------
    Service drop (Consumer endpoint) → "Service Drop" / 20 m
    LT span                          → "AB Cable" / 40 m
    HT span                          → "ACSR" / 40 m

    Visual style
    ------------
    ACSR new       — dashed black line
    ACSR existing  — solid black line
    AB Cable new   — wavy dark-blue line
    AB Cable exist — solid dark-blue line
    PVC Cable      — wavy dark-green line
    Service Drop   — wavy orange line
    CG symbol      — small crosshatch bracket below span midpoint
                     (only when detail_view=True and has_cg=True)
    """

    # Pen colours per conductor type
    _PEN_COLORS = {
        "ACSR":         QColor("#222222"),
        "AB Cable":     QColor("#1a5276"),   # dark blue
        "PVC Cable":    QColor("#107C41"),   # dark green
        "Service Drop": QColor("#d35400"),   # orange
    }

    def __init__(self, pole1, pole2, detail_view=True):
        super().__init__()
        self.p1          = pole1
        self.p2          = pole2
        self.detail_view = detail_view
        self.setZValue(0)
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)

        self.is_existing_span = False
        self.custom_note      = ""
        self.dynamic_props    = {}

        # ── Auto-detect service drop ───────────────────────────────────────
        self.is_service_drop = (
            isinstance(self.p1, SmartConsumer) or
            isinstance(self.p2, SmartConsumer)
        )

        # ── Auto-detect voltage level ──────────────────────────────────────
        self.is_lt_span = self._detect_lt()

        # ── Set defaults ───────────────────────────────────────────────────
        if self.is_service_drop:
            self.conductor      = "Service Drop"
            self.conductor_size = "10 SQMM"
            self.length         = 20
            self.consider_cable = False
            self.phase          = "3 Phase"
            self.has_cg         = False
            self.aug_type       = "New"
            self.wire_count     = "3"
        else:
            self.conductor      = "AB Cable" if self.is_lt_span else "ACSR"
            self.conductor_size = "3CX50+1CX35" if self.is_lt_span else "50SQMM"
            self.length         = 40
            self.aug_type       = "New"
            self.wire_count     = "3"
            self.has_cg         = False
            self.consider_cable = False
            self.phase          = "3 Phase"

        # Label is a standalone item (not a child) so it can be
        # added separately to the scene and remain independent.
        self.label = DraggableLabel()
        self.label.setTextWidth(90)

        self.update_position()
        self.update_visuals()

    # ── Voltage detection ─────────────────────────────────────────────────────

    def _detect_lt(self) -> bool:
        """
        Returns True (LT span) when either endpoint is:
          - a SmartPole with pole_type == "LT"
          - a SmartConsumer
        Returns False (HT span) when both endpoints are HT poles or structures.
        """
        for ep in (self.p1, self.p2):
            if isinstance(ep, SmartConsumer):
                return True
            if isinstance(ep, SmartPole) and ep.pole_type == "LT":
                return True
        return False

    # ── Position update ───────────────────────────────────────────────────────

    def update_position(self):
        """Redraws the span path and repositions the label."""
        # Recalculate LT flag in case connected poles changed type
        self.is_lt_span = self._detect_lt()

        path   = QPainterPath()
        x1, y1 = self.p1.x(), self.p1.y()
        x2, y2 = self.p2.x(), self.p2.y()
        dx, dy  = x2 - x1, y2 - y1
        px_len  = math.hypot(dx, dy)

        path.moveTo(x1, y1)

        wavy_conductors = {"AB Cable", "PVC Cable", "Service Drop"}
        if self.conductor in wavy_conductors and px_len > 0:
            steps     = max(20, int(px_len / 2))
            nx        = -dy / px_len
            ny        =  dx / px_len
            frequency = px_len / 15        # ~one wave per 15 px
            amplitude = 4

            for i in range(1, steps + 1):
                t          = i / float(steps)
                cx_        = x1 + dx * t
                cy_        = y1 + dy * t
                sine_off   = math.sin(t * frequency * 2 * math.pi) * amplitude
                path.lineTo(cx_ + nx * sine_off, cy_ + ny * sine_off)
        else:
            path.lineTo(x2, y2)

        self.setPath(path)

        # Label position — perpendicular offset from midpoint
        if px_len > 0:
            nx_n   = -dy / px_len
            ny_n   =  dx / px_len
            mid_x  = (x1 + x2) / 2
            mid_y  = (y1 + y2) / 2
            lw     = self.label.boundingRect().width()
            self.label.setPos(
                mid_x + nx_n * 16 - lw / 2,
                mid_y + ny_n * 16 - 10
            )

    # ── Visual update ─────────────────────────────────────────────────────────

    def update_visuals(self):
        self.update_position()

        # ── Pen style ─────────────────────────────────────────────────────
        color = self._PEN_COLORS.get(self.conductor, QColor("#222222"))
        pen   = QPen(color, 1.8)

        if self.is_existing_span:
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setWidthF(1.2)
        elif self.conductor == "ACSR":
            pen.setStyle(Qt.PenStyle.DashLine)

        self.setPen(pen)

        # ── Label text ────────────────────────────────────────────────────
        if self.is_existing_span:
            txt = f"Existing\n{self.conductor}"
        elif self.is_service_drop:
            phase_s = "1φ" if self.phase == "1 Phase" else "3φ"
            txt = f"Service {self.length}m\n{phase_s}"
            if self.consider_cable:
                txt += f"\n{self.conductor_size}"
        else:
            size_s = self.conductor_size or ""
            if self.conductor == "ACSR":
                txt = f"{self.length}m\n{self.wire_count}W ACSR {size_s}"
            elif self.conductor == "AB Cable":
                txt = f"{self.length}m\nABC {size_s}"
            else:
                txt = f"{self.length}m\nPVC {size_s}"
            if self.aug_type != "New":
                txt += f"\n({self.aug_type})"
            if self.has_cg:
                txt += "\n[CG]"

        if self.custom_note:
            txt += f"\n📝 {self.custom_note}"

        self.label.setPlainText(txt)

        # Ensure label is in scene
        if not self.label.scene() and self.scene():
            self.scene().addItem(self.label)

    # ── Custom paint for CG symbol ────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        # Draw the span line itself
        super().paint(painter, option, widget)

        # Draw CG bracket at midpoint if enabled
        if not self.detail_view or not self.has_cg or self.is_existing_span:
            return

        x1, y1 = self.p1.x(), self.p1.y()
        x2, y2 = self.p2.x(), self.p2.y()
        dx, dy  = x2 - x1, y2 - y1
        px_len  = math.hypot(dx, dy)
        if px_len == 0:
            return

        # Midpoint in scene coords — convert to item (path) local coords
        mid_sx = (x1 + x2) / 2
        mid_sy = (y1 + y2) / 2

        # Perpendicular direction pointing "down" relative to span
        nx = -dy / px_len
        ny =  dx / px_len

        # Offset 10 px below midpoint in perpendicular direction
        cg_sx = mid_sx + nx * 10
        cg_sy = mid_sy + ny * 10

        # Transform scene point to item-local coordinates for painting
        # (SmartSpan path is in scene space, so this maps correctly)
        painter.save()
        painter.translate(cg_sx, cg_sy)
        painter.setPen(QPen(QColor("#e74c3c"), 1.5))   # red bracket
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cg = _cg_path()
        painter.drawPath(cg)
        painter.restore()
