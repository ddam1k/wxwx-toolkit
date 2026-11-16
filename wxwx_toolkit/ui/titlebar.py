"""One combined title bar (like VS Code): logo + name + theme toggle + our own window buttons.

Built on PySide6-Frameless-Window: the window keeps its native frame behaviour (resize edges,
shadow, Win+arrows, double-click to maximize, drag to move), only the caption is drawn by us.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qframelesswindow import TitleBar
from qframelesswindow.titlebar.title_bar_buttons import TitleBarButton, TitleBarButtonState
from qframelesswindow.utils import toggleMaxState

from .theme import theme
from .widgets import Logo, ThemeToggle

HEIGHT = 54


class WinButton(TitleBarButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._isMax = False
        self.setFixedSize(46, HEIGHT)

    def setMaxState(self, is_max: bool) -> None:
        if self._isMax != is_max:
            self._isMax = is_max
            self.setState(TitleBarButtonState.NORMAL)

    def paintEvent(self, e):
        p = QPainter(self)
        color, bg = self._getColors()
        p.fillRect(self.rect(), bg)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 1.15)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = QPointF(self.width() / 2, self.height() / 2)
        if self.kind == "min":
            p.drawLine(QPointF(c.x() - 5, c.y()), QPointF(c.x() + 5, c.y()))
        elif self.kind == "max":
            if not self._isMax:
                p.drawRoundedRect(QRectF(c.x() - 5, c.y() - 5, 10, 10), 1.6, 1.6)
            else:
                p.drawRoundedRect(QRectF(c.x() - 5, c.y() - 3, 8, 8), 1.4, 1.4)
                p.drawLine(QPointF(c.x() - 3, c.y() - 5), QPointF(c.x() + 3.5, c.y() - 5))
                p.drawLine(QPointF(c.x() + 5, c.y() - 3.5), QPointF(c.x() + 5, c.y() + 3))
        else:
            p.drawLine(QPointF(c.x() - 5, c.y() - 5), QPointF(c.x() + 5, c.y() + 5))
            p.drawLine(QPointF(c.x() + 5, c.y() - 5), QPointF(c.x() - 5, c.y() + 5))


class HeaderBar(TitleBar):
    def __init__(self, window, title: str):
        super().__init__(window)
        self.setFixedHeight(HEIGHT)
        # replace the library's buttons with ours (same roles, our drawing)
        for old in (self.minBtn, self.maxBtn, self.closeBtn):
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self.minBtn, self.maxBtn, self.closeBtn = WinButton("min", self), WinButton("max", self), WinButton("close", self)
        self.minBtn.clicked.connect(self.window().showMinimized)
        self.maxBtn.clicked.connect(lambda: toggleMaxState(self.window()))
        self.closeBtn.clicked.connect(self.window().close)

        lay: QHBoxLayout = self.hBoxLayout
        while lay.count():
            lay.takeAt(0)
        lay.setContentsMargins(18, 0, 0, 0)
        lay.setSpacing(0)
        self.logo = Logo(28)
        lay.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(11)
        names = QWidget()
        names.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        nv = QVBoxLayout(names)
        nv.setContentsMargins(0, 0, 0, 0)
        nv.setSpacing(0)
        t1 = QLabel(title)
        t1.setObjectName("appTitle")
        t2 = QLabel("by yuyu")
        t2.setObjectName("appBy")
        nv.addWidget(t1)
        nv.addWidget(t2)
        lay.addWidget(names, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        self.toggle = ThemeToggle()
        lay.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(14)
        for b in (self.minBtn, self.maxBtn, self.closeBtn):
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        self.logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.apply_theme()

    def apply_theme(self) -> None:
        for b in (self.minBtn, self.maxBtn, self.closeBtn):
            b.setNormalColor(theme.c("muted"))
            b.setHoverColor(theme.c("text"))
            b.setPressedColor(theme.c("text"))
            b.setNormalBackgroundColor(QColor(0, 0, 0, 0))
            b.setHoverBackgroundColor(theme.c("panel2"))
            b.setPressedBackgroundColor(theme.c("panel3"))
        self.closeBtn.setHoverColor(QColor("#ffffff"))
        self.closeBtn.setPressedColor(QColor("#ffffff"))
        self.closeBtn.setHoverBackgroundColor(QColor("#c94b5a"))
        self.closeBtn.setPressedBackgroundColor(QColor("#a83a48"))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), theme.c("win"))
        p.fillRect(0, self.height() - 1, self.width(), 1, theme.c("line"))
