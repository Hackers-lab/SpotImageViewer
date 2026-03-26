"""
This module contains custom, reusable Qt widgets for the application's UI,
such as the interactive canvas view and draggable text labels.
"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsTextItem
from PyQt6.QtGui import QColor, QTextOption, QFont
from PyQt6.QtCore import Qt, QRectF

class InteractiveView(QGraphicsView):
    """
    A custom QGraphicsView that handles zooming with the mouse wheel and
    forwards mouse clicks to the main application for tool handling.
    """
    def __init__(self, scene, parent_app):
        super().__init__(scene)
        self.parent_app = parent_app
        self.setRenderHints(self.renderHints() | self.renderHints().Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        zoom = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(zoom, zoom)
        self.parent_app.update_view_drag_mode()

    def mousePressEvent(self, event):
        self.parent_app.handle_canvas_click(event, self)
        super().mousePressEvent(event)

class DraggableLabel(QGraphicsTextItem):
    """
    A QGraphicsTextItem that can be moved and selected. It's used for
    displaying text labels on the canvas for poles and spans.
    It has a white background for better readability.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.document().setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignCenter))
        self.setZValue(20)
        self.setFont(QFont("Arial", 7))

    def mouseDoubleClickEvent(self, event):
        """Enable text editing on double-click."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        """Disable text editing when focus is lost."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)

    def paint(self, painter, option, widget):
        """
        Overridden paint method to draw a white background rectangle behind the text
        for improved visibility against the lines and other items on the canvas.
        """
        painter.setBrush(QColor(255, 255, 255)) # White, 100% opacity
        painter.setPen(Qt.PenStyle.NoPen)
        
        doc = self.document()
        layout = doc.documentLayout()
        
        # Iterate over text blocks to calculate the bounding box of the actual text
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            if not block.isValid():
                continue
            
            text_layout = block.layout()
            if not text_layout:
                continue
                
            block_rect = layout.blockBoundingRect(block)
            line = text_layout.lineAt(0)
            if line.isValid():
                # Center the background rect on the actual text width
                used_width = line.naturalTextWidth()
                offset_x = (block_rect.width() - used_width) / 2
                
                highlighter_rect = QRectF(
                    block_rect.left() + offset_x, 
                    block_rect.top(), 
                    used_width, 
                    block_rect.height()
                )
                # Adjust for padding
                painter.drawRect(highlighter_rect.adjusted(-3, 0, 3, 0))

        # Call the original paint method to draw the text itself
        super().paint(painter, option, widget)
