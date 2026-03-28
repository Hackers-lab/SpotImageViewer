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
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF

from ui_components import DraggableLabel


# ─────────────────────────────────────────────────────────────────────────────
#  SHARED DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _earth_path(x_off: float = 0, y_off: float = 0, angle_deg: float = 90) -> QPainterPath:
    """
    Draws the standard IEC earth / ground symbol (⏚) in any direction.
    (x_off, y_off) — attachment point at pole edge.
    angle_deg — direction away from pole (default 90° = downward in screen coords).
    Symbol is kept compact so it doesn't overlap the pole or label.
    """
    p = QPainterPath()
    rad      = math.radians(angle_deg)
    perp_rad = math.radians(angle_deg + 90)
    # Short stem in angle_deg direction
    p.moveTo(x_off, y_off)
    p.lineTo(x_off + math.cos(rad) * 3, y_off + math.sin(rad) * 3)
    # Three bars perpendicular to stem, decreasing width (compact)
    for dist, half_w in ((3, 4), (5, 3), (7, 2)):
        bx = x_off + math.cos(rad) * dist
        by = y_off + math.sin(rad) * dist
        px = math.cos(perp_rad) * half_w
        py = math.sin(perp_rad) * half_w
        p.moveTo(bx - px, by - py)
        p.lineTo(bx + px, by + py)
    return p


def _stay_path(angle_deg: float = 225) -> QPainterPath:
    """
    Draws a stay-wire symbol: a diagonal line from pole centre outward,
    with an arrowhead at the far end pointing in the stay direction.
    angle_deg — direction of stay wire (default: lower-left = 225°)
    """
    length = 18
    rad    = math.radians(angle_deg)
    ex     = math.cos(rad) * length
    ey     = math.sin(rad) * length

    p = QPainterPath()
    p.moveTo(0, 0)
    p.lineTo(ex, ey)
    # Arrowhead — two wings going back from tip at ±140° from forward direction
    arrow_len = 6
    for wing_offset in (+140, -140):
        wing_rad = math.radians(angle_deg + wing_offset)
        p.moveTo(ex, ey)
        p.lineTo(ex + math.cos(wing_rad) * arrow_len,
                 ey + math.sin(wing_rad) * arrow_len)
    return p


def _existing_struct_path(st: str) -> QPainterPath:
    """
    Returns the outline path for an existing structure symbol used on a SmartPole
    when existing_subtype is DP/TP/4P/DTR. Matches SmartStructure geometry.
    """
    p   = QPainterPath()
    r   = 8
    gap = 6

    def _cl(path, offsets, radius):
        for i in range(len(offsets)):
            p1 = offsets[i]
            p2 = offsets[(i + 1) % len(offsets)]
            vx, vy = p2[0] - p1[0], p2[1] - p1[1]
            dist = math.hypot(vx, vy)
            if dist == 0:
                continue
            nx, ny = vx / dist, vy / dist
            path.moveTo(p1[0] + nx * radius, p1[1] + ny * radius)
            path.lineTo(p2[0] - nx * radius, p2[1] - ny * radius)

    if st == "DP":
        cx = r + gap // 2
        p.addEllipse(-cx - r, -r, r * 2, r * 2)
        p.addEllipse( cx - r, -r, r * 2, r * 2)
        p.moveTo(-cx + r, 0)
        p.lineTo( cx - r, 0)
    elif st == "TP":
        offs = [(0, -(r + gap // 2)), (-(r + gap), r + gap // 2), (r + gap, r + gap // 2)]
        for ox, oy in offs:
            p.addEllipse(ox - r, oy - r, r * 2, r * 2)
        _cl(p, offs, r)
    elif st == "4P":
        d = r + gap // 2
        offs = [(-d, -d), (d, -d), (d, d), (-d, d)]
        for ox, oy in offs:
            p.addEllipse(ox - r, oy - r, r * 2, r * 2)
        _cl(p, offs, r)
    elif st == "DTR":
        cx = r + gap // 2 + 4
        p.addEllipse(-cx - r, -r, r * 2, r * 2)
        p.addEllipse( cx - r, -r, r * 2, r * 2)
        p.addRect(-gap // 2 - 2, -r // 2, gap + 4, r)
        p.moveTo(-gap // 2 - 2, 0)
        p.lineTo( gap // 2 + 2, 0)
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
        self.existing_subtype   = pole_type   # LT | HT | DP | TP | 4P | DTR
        self.existing_dtr_size  = "None"
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

        # Angle overrides for stay/earth symbols (None = auto-calculate from spans)
        self.stay_angle_override  = None   # float degrees, or None
        self.earth_angle_override = None   # float degrees, or None

        # Label — child of this item so it moves with the pole
        self.label = DraggableLabel(self)
        self.label.setTextWidth(90)

        self.update_visuals()

    # ── Stay / Earth angle calculation ────────────────────────────────────────

    def _calc_stay_angle(self) -> float:
        """
        Returns the direction (degrees, screen coords) in which the stay wire
        should point, based on connected span tensions.

        For an end pole (1 active span):  stay points opposite to the span
        direction so the anchor resists the wire tension.
        For a turning pole (2+ spans):  stay points opposite to the resultant
        of all span unit-vectors (toward the net tension source).
        Default 225° when no spans are connected.
        """
        active_spans = [
            s for s in self.connected_spans
            if not s.is_service_drop and not s.is_existing_span
        ]
        if not active_spans:
            return 225.0

        sum_x, sum_y = 0.0, 0.0
        my_x, my_y = self.x(), self.y()

        for span in active_spans:
            other = span.p1 if span.p2 is self else span.p2
            dx = other.x() - my_x
            dy = other.y() - my_y
            mag = math.hypot(dx, dy)
            if mag > 0:
                sum_x += dx / mag
                sum_y += dy / mag

        if math.hypot(sum_x, sum_y) < 0.01:
            return 225.0   # balanced / through pole — no net tension

        # Net tension direction (toward spans); stay opposes it → +180°
        tension_angle = math.degrees(math.atan2(sum_y, sum_x)) % 360
        return (tension_angle + 180) % 360

    def _calc_earth_angle(self, stay_angle: float) -> float:
        """
        Finds a "free" direction for the earth symbol that avoids all span
        directions and the stay direction.

        Priority order:
          1. Cardinal directions: left(180°), top(270°), bottom(90°), right(0°)
          2. Diagonals: lower-left(225°), lower-right(315°), upper-left(135°), upper-right(45°)
          3. Fallback: opposite of stay

        A direction is blocked if it is within 50° of any span or the stay.
        Only applies to new (non-existing) poles; existing poles use stay+180°.
        """
        if self.is_existing:
            return (stay_angle + 180) % 360

        # Collect all occupied angles (span directions + stay)
        occupied = []
        my_x, my_y = self.x(), self.y()
        for span in self.connected_spans:
            other = span.p1 if span.p2 is self else span.p2
            dx = other.x() - my_x
            dy = other.y() - my_y
            if math.hypot(dx, dy) > 0:
                occupied.append(math.degrees(math.atan2(dy, dx)) % 360)
        occupied.append(stay_angle % 360)

        def _is_free(angle: float) -> bool:
            for occ in occupied:
                diff = abs((angle - occ + 180) % 360 - 180)
                if diff < 50:
                    return False
            return True

        # 1. Try cardinal directions in preference order
        for candidate in (180.0, 270.0, 90.0, 0.0):
            if _is_free(candidate):
                return candidate
        # 2. Try 45° diagonals
        for candidate in (225.0, 315.0, 135.0, 45.0):
            if _is_free(candidate):
                return candidate
        # 3. Fallback
        return (stay_angle + 180) % 360

    # ── Visual update ─────────────────────────────────────────────────────────

    def update_visuals(self):
        path = QPainterPath()

        # Main pole symbol
        r = 9
        if self.is_existing and self.existing_subtype in ("DP", "TP", "4P", "DTR"):
            path.addPath(_existing_struct_path(self.existing_subtype))
        else:
            path.addEllipse(-r, -r, r * 2, r * 2)

        # Extension indicator — small square on top
        if self.has_extension:
            path.addRect(-4, -(r + 10), 8, 8)

        # ── Determine stay / earth angles ─────────────────────────────────
        if self.stay_angle_override is not None:
            stay_angle = self.stay_angle_override % 360
        else:
            stay_angle = self._calc_stay_angle()

        if self.earth_angle_override is not None:
            earth_angle = self.earth_angle_override % 360
        else:
            earth_angle = self._calc_earth_angle(stay_angle)

        # ── Earth symbol at pole edge in earth_angle direction ────────────
        if self.detail_view and self.earth_count > 0:
            n         = min(self.earth_count, 3)
            erad      = math.radians(earth_angle)
            perp_rad  = math.radians(earth_angle + 90)
            # attachment point on pole edge
            att_x = math.cos(erad) * (r + 2)
            att_y = math.sin(erad) * (r + 2)
            for i in range(n):
                offset = (i - (n - 1) / 2) * 10   # tighter spacing for smaller symbol
                ex = att_x + math.cos(perp_rad) * offset
                ey = att_y + math.sin(perp_rad) * offset
                path.addPath(_earth_path(ex, ey, earth_angle))

        # ── Stay wire symbols in stay_angle direction ─────────────────────
        if self.detail_view and self.stay_count > 0:
            # For multiple stays, fan them around the main stay angle
            spread = [0, -25, 25, -50]
            for i in range(min(self.stay_count, 4)):
                ang = (stay_angle + spread[i]) % 360
                path.addPath(_stay_path(ang))

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
            _sub = self.existing_subtype
            _sfx = " Struct" if _sub in ("DP", "TP", "4P", "DTR") else " Pole"
            txt = f"Ex. {_sub}{_sfx}"
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

        # ── Label position: centered below the pole symbol ────────────────
        # Only reposition on first draw (label at default 0,0); after that the
        # user may have dragged it, so leave it where it is.
        lw = self.label.boundingRect().width()
        lh = self.label.boundingRect().height()
        if self.label.pos() == QPointF(0, 0):
            if self.is_existing and self.existing_subtype in ("TP", "4P"):
                lbl_y = 27   # taller structure symbol
            else:
                lbl_y = r + 8
            self.label.setPos(-lw / 2, lbl_y)

    # ── Qt overrides ──────────────────────────────────────────────────────────
    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.has_extension:
            r = 9
            painter.save()
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setFont(QFont("Arial", 5, QFont.Weight.Bold))
            painter.drawText(QRectF(-4, -(r + 10), 8, 8),
                             Qt.AlignmentFlag.AlignCenter, "E")
            painter.restore()
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

        def _draw_connecting_lines(path, offsets, radius):
            for i in range(len(offsets)):
                p1 = offsets[i]
                p2 = offsets[(i + 1) % len(offsets)]
                
                # Vector from p1 to p2
                vx, vy = p2[0] - p1[0], p2[1] - p1[1]
                dist = math.hypot(vx, vy)
                
                if dist == 0:
                    continue
                
                # Normalized vector
                nx, ny = vx / dist, vy / dist
                
                # Points on the circumference
                start_x, start_y = p1[0] + nx * radius, p1[1] + ny * radius
                end_x, end_y = p2[0] - nx * radius, p2[1] - ny * radius
                
                path.moveTo(start_x, start_y)
                path.lineTo(end_x, end_y)

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
            # Connecting lines
            _draw_connecting_lines(path, offsets, r)

        elif st == "4P":
            # 2×2 square grid
            d = r + gap // 2
            offsets = [(-d, -d), (d, -d), (d, d), (-d, d)]
            for ox, oy in offsets:
                path.addEllipse(ox - r, oy - r, r * 2, r * 2)
            # Connecting lines
            _draw_connecting_lines(path, offsets, r)

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
    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.has_extension:
            r = 8
            painter.save()
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setFont(QFont("Arial", 5, QFont.Weight.Bold))
            painter.drawText(QRectF(-4, -(r * 2 + 14), 8, 8),
                             Qt.AlignmentFlag.AlignCenter, "E")
            painter.restore()
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
          - a SmartPole whose effective type is "LT"  (uses existing_subtype when is_existing)
          - a SmartConsumer
        Returns False (HT span) when both endpoints are HT poles or structures.
        """
        for ep in (self.p1, self.p2):
            if isinstance(ep, SmartConsumer):
                return True
            if isinstance(ep, SmartPole):
                eff = ep.existing_subtype if ep.is_existing else ep.pole_type
                if eff == "LT":
                    return True
        return False

    # ── Position update ───────────────────────────────────────────────────────

    def update_position(self):
        """Redraws the span path and repositions the label."""
        self.is_lt_span = self._detect_lt()

        p1_pos = self.p1.pos()
        p2_pos = self.p2.pos()

        def _get_line_rect_intersection(line, rect):
            intersection_point = QPointF()
            
            # Check for intersection with each of the 4 lines of the rectangle
            rect_lines = [
                QLineF(rect.topLeft(), rect.topRight()),
                QLineF(rect.topRight(), rect.bottomRight()),
                QLineF(rect.bottomRight(), rect.bottomLeft()),
                QLineF(rect.bottomLeft(), rect.topLeft())
            ]
            
            for rect_line in rect_lines:
                # Use QLineF.intersects() which returns a tuple (IntersectionType, QPointF)
                intersection_type, intersect_pt = line.intersects(rect_line)
                if intersection_type == QLineF.IntersectionType.BoundedIntersection:
                    return intersect_pt
            
            return intersection_point

        def get_connection_point(item, other_item_pos):
            item_pos = item.pos()
            line = QLineF(other_item_pos, item_pos)
            
            if isinstance(item, SmartPole):
                # For SmartPole, connect to the edge of the circle
                direction = line.unitVector()
                return item_pos - QPointF(direction.dx() * 9, direction.dy() * 9)
            
            if isinstance(item, SmartStructure):
                st = getattr(item, 'structure_type', None)
                # For TP and 4P, connect to the midpoint of one of the interconnecting lines
                if st == "TP":
                    # Use the bottom edge (between bottom-left and bottom-right)
                    r = 8
                    gap = 6
                    left = item_pos + QPointF(-(r + gap), (r + gap // 2))
                    right = item_pos + QPointF((r + gap), (r + gap // 2))
                    return (left + right) / 2
                elif st == "4P":
                    # Use the bottom edge (between bottom-left and bottom-right)
                    d = 8 + 6 // 2
                    left = item_pos + QPointF(-d, d)
                    right = item_pos + QPointF(d, d)
                    return (left + right) / 2
                else:
                    # For DP, DTR, fallback to bounding rect edge
                    brect = item.boundingRect()
                    brect.moveTopLeft(item.pos() - brect.center())
                    intersection = _get_line_rect_intersection(line, brect)
                    if not intersection.isNull():
                        return intersection
            
            return item_pos

        x1, y1 = get_connection_point(self.p1, p2_pos).x(), get_connection_point(self.p1, p2_pos).y()
        x2, y2 = get_connection_point(self.p2, p1_pos).x(), get_connection_point(self.p2, p1_pos).y()

        path = QPainterPath()
        path.moveTo(x1, y1)

        dx, dy = x2 - x1, y2 - y1
        px_len = math.hypot(dx, dy)

        wavy_conductors = {"AB Cable", "PVC Cable", "Service Drop"}
        if self.conductor in wavy_conductors and px_len > 0:
            steps     = max(20, int(px_len / 2))
            nx        = -dy / px_len
            ny        =  dx / px_len
            frequency = px_len / 15
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
