"""«Клип в корзине · Вернуть» — a bar at the bottom of the page for a few seconds after a delete."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ..core.i18n import t
from .theme import font, theme
from .common import text_w
from .widgets import animate

SHOW_MS = 7000


class UndoBar(QWidget):
    undo = Signal()
    expired = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.text = ""
        self._o = 0.0
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._expire)
        self.hide()

    def _set_o(self, v):
        self._o = float(v)
        self._place()
        self.update()
        if self._o <= 0.01 and not self._timer.isActive():
            self.hide()

    def _btn(self) -> str:
        return t("undo_trash")

    def _place(self):
        par = self.parentWidget()
        f = font(9.8, QFont.Weight.Bold)
        w = text_w(self.text, f) + text_w(self._btn(), f) + 70
        y = par.height() - 74 + round(24 * (1 - self._o))
        self.setGeometry((par.width() - w) // 2, y, w, 44)

    def show_text(self, text: str):
        self.text = text
        self.show()
        self.raise_()
        self._place()
        animate(self, self._o, 1, 420, self._set_o)
        self._timer.start(SHOW_MS)

    def _expire(self):
        animate(self, self._o, 0, 280, self._set_o)
        self.expired.emit()

    def dismiss(self):
        """Hide now without undoing (the next delete takes the bar)."""
        if self._timer.isActive():
            self._timer.stop()
            self.expired.emit()
        animate(self, self._o, 0, 200, self._set_o)

    def enterEvent(self, e):
        self._hover = True
        self._timer.stop()                 # reading it — don't let it run away
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        if self.isVisible() and self._o > 0.5:
            self._timer.start(2500)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._o > 0.5:
            self._timer.stop()
            animate(self, self._o, 0, 200, self._set_o)
            self.undo.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(max(0.0, min(1.0, self._o)))
        r = QRectF(self.rect()).adjusted(1, 1, -1, -4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRoundedRect(r.translated(0, 3), 12, 12)
        p.setBrush(theme.c("ink"))
        p.drawRoundedRect(r, 12, 12)
        f = font(9.8, QFont.Weight.Bold)
        p.setFont(f)
        tw = text_w(self.text, f)
        bw = text_w(self._btn(), f)
        x = r.left() + (r.width() - tw - bw - 26) / 2
        p.setPen(theme.c("on_ink"))
        p.drawText(QRectF(x, r.top(), tw + 2, r.height()), Qt.AlignmentFlag.AlignVCenter, self.text)
        p.setPen(theme.c("tint"))
        f.setUnderline(self._hover)
        p.setFont(f)
        p.drawText(QRectF(x + tw + 26, r.top(), bw + 4, r.height()), Qt.AlignmentFlag.AlignVCenter, self._btn())
