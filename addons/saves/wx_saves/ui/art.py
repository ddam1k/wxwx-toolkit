"""Painted bits of Saves: the «Видео / Только звук» cards, preview pictures, the loading shimmer."""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from .theme import font, theme
from .widgets import HINTS, ICONS, animate, icon_pixmap, mix

ICONS.update({
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z"/>',
    "pause": '<path d="M9 6v12M15 6v12"/>',
    "retry": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/>',
    "dl": '<path d="M12 4v11M7 10l5 5 5-5M4 19h16"/>',
})

SITE_COLORS = {"YouTube": "#ff5a4f", "Instagram": "#e4589a", "TikTok": "#3fe0e6", "site": "#b8a8e2"}


def site_color(site: str) -> QColor:
    return QColor(SITE_COLORS.get(site, SITE_COLORS["site"]))


def site_html(site: str, text: str) -> str:
    return f'<span style="color:{SITE_COLORS.get(site, SITE_COLORS["site"])}">●</span>&nbsp;{text}'


class ModeCard(QAbstractButton):
    """«Видео» (frames + play + a running progress line) or «Только звук» (a breathing wave)."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.sub = ""
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._h = 0.0
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.toggled.connect(lambda _c: self._sync())
        self._fit()

    def _fit(self):
        self.setFixedHeight(92 if HINTS["on"] else 76)

    def hints_changed(self):
        self._fit()
        self.update()

    def set_texts(self, title: str, sub: str):
        self.setText(title)
        self.sub = sub
        self.update()

    def sizeHint(self):
        return QSize(150, self.height())

    def _sync(self):
        run = self.isChecked() or self._h > 0.01
        if run and not self._timer.isActive():
            self._timer.start()
        elif not run:
            self._timer.stop()
        self.update()

    def _tick(self):
        self._t += 0.033
        self.update()

    def _set_h(self, v):
        self._h = float(v)
        self._sync()

    def enterEvent(self, e):
        animate(self, self._h, 1, 200, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 260, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(theme.c("ink") if on else mix(theme.c("line2"), theme.c("muted"), self._h * 0.4), 1.6 if on else 1))
        p.setBrush(theme.c("panel2") if on else theme.c("panel"))
        p.drawRoundedRect(r, 14, 14)
        x, y = 14.0, 13.0
        p.setPen(theme.c("text"))
        p.setFont(font(10.4, QFont.Weight.ExtraBold))
        p.drawText(QRectF(x, y, r.width() - 28, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        if HINTS["on"] and self.sub:
            p.setPen(theme.c("faint"))
            p.setFont(font(8.2))
            p.drawText(QRectF(x, y + 19, r.width() - 28, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self.sub)
        art = QRectF(x, r.bottom() - 13 - 26, r.width() - 28, 26)
        live = on or self._h > 0.01
        if self.kind == "audio":
            self._wave(p, art, on, live)
        else:
            self._frames(p, art, on, live)

    def _wave(self, p: QPainter, a: QRectF, on: bool, live: bool):
        n = 22
        gap = 3.0
        bw = (a.width() - gap * (n - 1)) / n
        col = theme.c("tint") if on else theme.c("faint")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        for i in range(n):
            base = 0.35 + 0.65 * abs(math.sin(i * 0.9) * math.cos(i * 0.37))
            k = base
            if live:
                k = base * (0.45 + 0.55 * (0.5 + 0.5 * math.sin(self._t * 5.7 - i * 0.55)))
            h = max(3.0, a.height() * k)
            p.drawRoundedRect(QRectF(a.x() + i * (bw + gap), a.center().y() - h / 2, bw, h), 1.5, 1.5)

    def _frames(self, p: QPainter, a: QRectF, on: bool, live: bool):
        clip = QPainterPath()
        clip.addRoundedRect(a, 7, 7)
        p.save()
        p.setClipPath(clip)
        n = 6
        gap = 3.0
        fw = (a.width() - gap * (n - 1)) / n
        for i in range(n):
            fr = QRectF(a.x() + i * (fw + gap), a.y(), fw, a.height())
            g = QLinearGradient(fr.topLeft(), fr.bottomRight())
            c1 = mix(theme.c("panel3"), theme.c("ink"), 0.38 if on else 0.0)
            c2 = mix(theme.c("panel2"), theme.c("ink"), 0.12 if on else 0.0)
            if i % 2:
                c1, c2 = c1.darker(112), c2.darker(112)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(fr, 4, 4)
        p.setBrush(QColor(0, 0, 0, 64))
        p.drawRect(QRectF(a.x(), a.bottom() - 3, a.width(), 3))
        if live:
            k = (self._t / 2.6) % 1.0
            p.setBrush(theme.c("tint"))
            p.drawRect(QRectF(a.x(), a.bottom() - 3, a.width() * k, 3))
        p.restore()
        d = 18 * (1 + 0.15 * self._h)
        c = QRectF(a.center().x() - d / 2, a.center().y() - d / 2, d, d)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("win"))
        p.drawEllipse(c)
        tri = QPainterPath()
        cx, cy, s = c.center().x() + 1, c.center().y(), d * 0.22
        tri.moveTo(cx - s, cy - s * 1.15)
        tri.lineTo(cx + s * 1.2, cy)
        tri.lineTo(cx - s, cy + s * 1.15)
        tri.closeSubpath()
        p.setBrush(theme.c("text"))
        p.drawPath(tri)


class Picture(QWidget):
    """A rounded preview: the real thumbnail when loaded, a soft gradient until then; optional duration badge."""
    clicked = Signal()

    def __init__(self, w: int, h: int, radius: float = 11, parent=None):
        super().__init__(parent)
        self.setFixedSize(w, h)
        self.radius = radius
        self.pm: QPixmap | None = None
        self.badge = ""
        self.site = "site"
        self.play = True
        self.icon = ""                    # e.g. "music" for audio rows
        self.done = False
        self.dim = False

    def set_pixmap(self, pm: QPixmap | None):
        self.pm = pm if pm is not None and not pm.isNull() else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.setClipPath(path)
        if self.pm is not None:
            s = self.pm.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            x = (self.width() - s.width()) / 2
            y = (self.height() - s.height()) / 2
            p.drawPixmap(QRectF(x, y, s.width(), s.height()), self.pm, QRectF(self.pm.rect()))
        else:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, mix(theme.c("panel3"), site_color(self.site), 0.35))
            g.setColorAt(1, theme.c("panel2"))
            p.fillRect(r, g)
        if self.dim:
            p.fillRect(r, QColor(0, 0, 0, 120))
        if self.icon:
            sz = min(self.width(), self.height()) * 0.45
            pm = icon_pixmap(self.icon, QColor("#ffffff"), int(sz), self.devicePixelRatioF())
            p.drawPixmap(QRectF((self.width() - sz) / 2, (self.height() - sz) / 2, sz, sz), pm, QRectF(pm.rect()))
        elif self.play and self.width() > 60:
            d = 30.0
            c = QRectF(self.width() / 2 - d / 2, self.height() / 2 - d / 2, d, d)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawEllipse(c)
            tri = QPainterPath()
            cx, cy, s = c.center().x() + 1.5, c.center().y(), 5.5
            tri.moveTo(cx - s, cy - s * 1.2)
            tri.lineTo(cx + s * 1.3, cy)
            tri.lineTo(cx - s, cy + s * 1.2)
            tri.closeSubpath()
            p.setBrush(QColor("#ffffff"))
            p.drawPath(tri)
        if self.badge:
            f = font(7.6, QFont.Weight.Bold, mono=True)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(self.badge) + 12
            b = QRectF(self.width() - tw - 6, self.height() - 22, tw, 17)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(b, 6, 6)
            p.setPen(QColor("#ffffff"))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, self.badge)
        if self.done:
            p.fillRect(r, QColor(17, 17, 19, 140))
            pm = icon_pixmap("check", QColor("#ffffff"), 16, self.devicePixelRatioF())
            p.drawPixmap(QRectF(self.width() / 2 - 8, self.height() / 2 - 8, 16, 16), pm, QRectF(pm.rect()))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class Shimmer(QWidget):
    """The «looking at the link…» placeholder."""

    def __init__(self, height: int = 143, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._x = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.text = ""

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def _tick(self):
        self._x = (self._x + 0.012) % 1.4
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(theme.c("line"), 1))
        p.setBrush(theme.c("panel"))
        p.drawRoundedRect(r, 16, 16)
        blocks = [QRectF(12, 12, 208, self.height() - 24), QRectF(236, 18, 180, 14), QRectF(236, 44, 300, 18),
                  QRectF(236, 70, 220, 14)]
        g = QLinearGradient(self.width() * (self._x - 0.4), 0, self.width() * self._x, 0)
        g.setColorAt(0, theme.c("panel2"))
        g.setColorAt(0.5, theme.c("panel3"))
        g.setColorAt(1, theme.c("panel2"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        for b in blocks:
            if b.right() < self.width() - 12:
                p.drawRoundedRect(b, 8, 8)
        if self.text:
            p.setPen(theme.c("faint"))
            p.setFont(font(9))
            p.drawText(QRectF(236, 96, self.width() - 250, 20), Qt.AlignmentFlag.AlignLeft, self.text)


class Elide(QLabel):
    """A one-line label that shortens itself with «…» instead of widening its parent (titles, paths)."""

    def __init__(self, name: str, mode=Qt.TextElideMode.ElideRight, parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setObjectName(name)
        self._full = ""
        self.setMinimumWidth(40)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full(self, text: str):
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        self.setText(self.fontMetrics().elidedText(self._full, self._mode, max(20, self.width())))
