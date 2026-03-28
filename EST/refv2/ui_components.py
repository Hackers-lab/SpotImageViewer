"""
ui_components.py
================
Custom reusable Qt widgets for ERP Estimate Generator v5.0.

Classes
-------
InteractiveView
    A QGraphicsView subclass that handles:
      • Mouse-wheel zooming anchored under the cursor
      • Middle-mouse-button panning (drag to scroll)
      • Forwarding left/right click events to app.handle_canvas_click()
      • Ctrl+Scroll for fine zoom steps
      • Keyboard shortcuts: Space = pan mode, Escape = select mode

DraggableLabel
    A QGraphicsTextItem subclass used for all on-canvas text labels
    (pole labels, span labels). Features:
      • Movable and selectable independently of its parent item
      • White pill-shaped background behind each line for legibility
      • Double-click to edit text inline
      • Automatic Z-ordering above all other items (Z=20)
      • Compact 7pt Arial font by default
"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsTextItem
from PyQt6.QtGui import QColor, QPainter, QTextOption, QFont, QPen, QBrush
from PyQt6.QtCore import Qt, QRectF, QPointF


# ─────────────────────────────────────────────────────────────────────────────
#  InteractiveView
# ─────────────────────────────────────────────────────────────────────────────

class InteractiveView(QGraphicsView):
    """
    Enhanced QGraphicsView for the drawing canvas.

    Zoom
    ----
    Mouse wheel          — zoom in / out (×1.15 per step)
    Ctrl + mouse wheel   — fine zoom (×1.05 per step)
    Middle-mouse drag    — pan the canvas

    Tool integration
    ----------------
    Left click           → forwarded to app.handle_canvas_click()
    Right click          → forwarded to app.handle_canvas_click()
                           (app uses this to revert to SELECT tool)
    Space bar (hold)     → temporarily switch to scroll-hand drag
    Escape               → call app.set_tool("SELECT")
    """

    _ZOOM_NORMAL = 1.15
    _ZOOM_FINE   = 1.05

    def __init__(self, scene, parent_app):
        super().__init__(scene)
        self.parent_app   = parent_app
        self._panning     = False          # middle-mouse pan state
        self._pan_start   = QPointF()
        self._space_held  = False

        # Render quality
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.TextAntialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )

        # Zoom anchors under the mouse cursor
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        # Allow the scene to grow as items are added
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        # Canvas background
        self.setBackgroundBrush(QBrush(QColor("#f9f9f9")))

        # Enable keyboard focus so key events reach this widget
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── Zoom ─────────────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        modifiers = event.modifiers()
        factor = (
            self._ZOOM_FINE
            if modifiers & Qt.KeyboardModifier.ControlModifier
            else self._ZOOM_NORMAL
        )
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor

        self.scale(factor, factor)
        self.parent_app.update_view_drag_mode()

    # ── Middle-mouse pan ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning   = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Forward left / right clicks to the application tool handler
        self.parent_app.handle_canvas_click(event, self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not self._space_held:
            self._space_held = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.parent_app.set_tool("SELECT")
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            self.parent_app.update_view_drag_mode()
            event.accept()
            return
        super().keyReleaseEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  DraggableLabel
# ─────────────────────────────────────────────────────────────────────────────

class DraggableLabel(QGraphicsTextItem):
    """
    An on-canvas text label that can be dragged independently of its
    parent item (pole, span, structure, consumer).

    Background rendering
    --------------------
    Each line of text gets a white rounded-rectangle background drawn
    behind it so the text remains legible over lines, symbols, and
    other canvas elements.  The background pill is sized to the
    natural width of each line plus 4 px horizontal padding.

    Editing
    -------
    Double-clicking the label enters inline text-edit mode.
    Clicking elsewhere (focusOut) locks the text again.
    """

    # Pill background colour — white with slight transparency feel
    _BG_COLOR   = QColor(255, 255, 255, 230)
    _FONT       = QFont("Arial", 7)
    _H_PADDING  = 4     # horizontal px added each side of text
    _CORNER_R   = 2     # corner radius for background pill

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.document().setDefaultTextOption(
            QTextOption(Qt.AlignmentFlag.AlignCenter)
        )
        self.setZValue(20)
        self.setFont(self._FONT)

    # ── Inline editing ────────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction
        )
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)

    # ── Paint override — white pill backgrounds ───────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        """
        Draw a white pill-shaped background behind each line of text,
        then delegate to the default QGraphicsTextItem paint for the
        actual text rendering.
        """
        painter.save()
        painter.setBrush(QBrush(self._BG_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)

        doc    = self.document()
        layout = doc.documentLayout()

        for block_idx in range(doc.blockCount()):
            block = doc.findBlockByNumber(block_idx)
            if not block.isValid():
                continue

            text_layout = block.layout()
            if not text_layout:
                continue

            block_rect = layout.blockBoundingRect(block)

            # Iterate lines within the block (usually 1 per block for
            # short labels, but respects text-wrapping correctly)
            for line_idx in range(text_layout.lineCount()):
                line = text_layout.lineAt(line_idx)
                if not line.isValid():
                    continue

                used_w  = line.naturalTextWidth()
                line_r  = line.rect()

                # Centre the pill horizontally within the block width
                offset_x = (block_rect.width() - used_w) / 2

                pill = QRectF(
                    block_rect.left() + offset_x - self._H_PADDING,
                    block_rect.top() + line_r.top(),
                    used_w + self._H_PADDING * 2,
                    line_r.height(),
                )
                painter.drawRoundedRect(pill, self._CORNER_R, self._CORNER_R)

        painter.restore()

        # Render the actual text on top
        super().paint(painter, option, widget)
