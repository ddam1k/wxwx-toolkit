"""Shell widgets: icons, sidebar with the cyberpunk background, nav buttons, switches, language cards."""
from __future__ import annotations

import math

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import HAIR_BLACK, HAIR_WHITE, font, theme
from .widgets import animate, mix

# ---------------------------------------------------------------- icons (24x24 stroke paths)
ICONS = {
    "store": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/>'
             '<rect x="3" y="14" width="7" height="7" rx="2"/><path d="M17.5 14v7M14 17.5h7"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1'
                'a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3'
                'l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0'
                ' 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3'
                'a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0'
                '-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "video": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9.5v5l4.5-2.5z"/>',
    "photo": '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    "dl": '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M4 17v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1"/>',
    "music": '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "addon": '<path d="M9 4h6v3a2 2 0 1 0 4 0V4h1v16H4V4h1v3a2 2 0 1 0 4 0z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
}


def icon_pixmap(name: str, color: QColor, size: int = 18, dpr: float = 1.0) -> QPixmap:
    body = ICONS.get(name, ICONS["addon"])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color.name()}" '
           f'stroke-opacity="{color.alphaF():.3f}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{body}</svg>')
    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


class IconTile(QWidget):
    """The split black/white tile with an icon, used on store cards."""

    def __init__(self, icon: str, size: int = 46, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 13, 13)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(HAIR_BLACK))
        g.setColorAt(0.4999, QColor(HAIR_BLACK))
        g.setColorAt(0.5, QColor(HAIR_WHITE))
        g.setColorAt(1, QColor(HAIR_WHITE))
        p.fillPath(path, g)
        inner = QRectF(r.center().x() - 15, r.center().y() - 15, 30, 30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRoundedRect(inner.translated(0, 1.5), 9, 9)
        p.setBrush(theme.c("win"))
        p.drawRoundedRect(inner, 9, 9)
        p.drawPixmap(QPointF(inner.center().x() - 9, inner.center().y() - 9),
                     icon_pixmap(self.icon, theme.c("text"), 18, self.devicePixelRatioF()))


# ---------------------------------------------------------------- nav button
class NavButton(QAbstractButton):
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)
        self.dot = False
        self._h = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def nextCheckState(self):
        pass

    def set_dot(self, on: bool) -> None:
        self.dot = on
        self._timer.start() if on else self._timer.stop()
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.02) % 1
        self.update()

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 180, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 220, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        on = self.isChecked()
        if on:
            bg = theme.c("panel3")
        else:
            bg = theme.c("panel2")
            bg.setAlpha(round(bg.alpha() * self._h))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 11, 11)
        tile = QRectF(12, (r.height() - 28) / 2, 28, 28)
        p.setBrush(theme.c("ink") if on else theme.c("panel2"))
        p.drawRoundedRect(tile, 9, 9)
        ic = theme.c("on_ink") if on else mix(theme.c("muted"), theme.c("text"), self._h)
        p.drawPixmap(QPointF(tile.center().x() - 8, tile.center().y() - 8),
                     icon_pixmap(self.icon, ic, 16, self.devicePixelRatioF()))
        p.setPen(theme.c("text") if on else mix(theme.c("muted"), theme.c("text"), self._h))
        p.setFont(font(10, QFont.Weight.DemiBold))
        p.drawText(QRectF(tile.right() + 11, 0, r.width() - tile.right() - 34, r.height()),
                   Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.dot:
            c = QPointF(r.right() - 15, r.center().y())
            ring = theme.c("tint", round(90 * (1 - self._pulse)))
            p.setBrush(ring)
            p.drawEllipse(c, 3.5 + 4 * self._pulse, 3.5 + 4 * self._pulse)
            p.setBrush(theme.c("tint"))
            p.drawEllipse(c, 3.5, 3.5)


# ---------------------------------------------------------------- cyberpunk background
class CyberArt:
    """Faint vector city + circuit board, bottom-anchored in a 224x760 design box."""
    W, H = 224, 760
    TRACES = [
        [(-5, 210), (38, 210), (64, 236), (64, 318), (88, 342), (136, 342)],
        [(229, 170), (182, 170), (158, 194), (158, 262)],
        [(148, 302), (148, 380), (122, 406), (70, 406), (46, 430), (46, 520)],
        [(184, 282), (204, 282), (216, 294), (216, 470), (196, 490), (150, 490)],
        [(10, 452), (10, 476), (28, 494), (96, 494), (112, 510), (112, 566)],
        [(229, 548), (182, 548), (164, 566), (164, 600)],
        [(-5, 380), (18, 380), (30, 392), (30, 412)],
    ]
    NODES = [(136, 342), (46, 520), (150, 490), (112, 566), (164, 600), (30, 412), (64, 236), (216, 294), (122, 406)]
    PULSES = [(0, 5.5, 0.0), (2, 7.0, 1.8), (3, 6.5, 3.2), (4, 8.0, 0.8)]   # trace, seconds per loop, phase
    BUILDINGS = [(0, 26, 690), (24, 20, 664), (42, 30, 640), (70, 18, 700), (86, 34, 612), (118, 22, 676),
                 (138, 28, 650), (164, 18, 700), (180, 26, 632), (204, 24, 684)]
    CIRCUIT_DY, CITY_DY = -40, -175

    def __init__(self):
        self.paths = []
        for pts in self.TRACES:
            path = QPainterPath(QPointF(*pts[0]))
            for pt in pts[1:]:
                path.lineTo(QPointF(*pt))
            self.paths.append(path)
        seed = 7

        def rnd():
            nonlocal seed
            seed = (seed * 9301 + 49297) % 233280
            return seed / 233280

        self.windows, self.lit = [], []
        for x, w, top in self.BUILDINGS:
            y = top + 8
            while y < 752:
                wx = x + 4
                while wx < x + w - 4:
                    r = rnd()
                    if r >= 0.55:
                        (self.lit if r > 0.93 else self.windows).append((wx, y, r))
                    wx += 6
                y += 9
        self._cache_key = None
        self._static: QPixmap | None = None

    def _static_layer(self, w: int, h: int, dpr: float) -> QPixmap:
        key = (w, h, dpr, theme.name)
        if key == self._cache_key and self._static:
            return self._static
        pm = QPixmap(round(w * dpr), round(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate((w - self.W) / 2, h - self.H)
        cy, panel = theme.c("cy"), theme.c("panel")
        pen = QPen(cy, 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        # dot grid
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cy)
        for gy in range(110, 580, 14):
            for gx in range(0, 224, 14):
                p.drawEllipse(QPointF(gx + 1, gy + 1), 0.7, 0.7)
        p.save()
        p.translate(0, self.CIRCUIT_DY)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        for path in self.paths:
            p.drawPath(path)
        p.setBrush(panel)
        for x, y in self.NODES:
            p.drawEllipse(QPointF(x, y), 2.6, 2.6)
        # chip with the split-hair motif
        p.drawRoundedRect(QRectF(120, 262, 56, 40), 4, 4)
        for i in range(4):
            y = 270 + i * 8
            p.drawLine(QPointF(112, y), QPointF(120, y))
            p.drawLine(QPointF(176, y), QPointF(184, y))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(148, 282), 9, 9)
        p.setBrush(cy)
        p.drawPie(QRectF(139, 273, 18, 18), 90 * 16, 180 * 16)
        # reticle
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(34, 296), 9, 9)
        for a, b in (((34, 282), (34, 288)), ((34, 304), (34, 310)), ((20, 296), (26, 296)), ((42, 296), (48, 296))):
            p.drawLine(QPointF(*a), QPointF(*b))
        # barcode
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cy)
        x = 176
        for bw in (2, 1, 3, 1, 1, 2, 1, 3, 2, 1):
            p.drawRect(QRectF(x, 214, bw, 14))
            x += bw + 2
        # hazard stripes
        for i in range(5):
            sx = 150 + i * 10
            stripe = QPainterPath(QPointF(sx, 430))
            for pt in ((sx + 6, 430), (sx, 440), (sx - 6, 440)):
                stripe.lineTo(QPointF(*pt))
            stripe.closeSubpath()
            p.drawPath(stripe)
        p.setPen(pen)
        for x1, x2 in ((8, 70), (78, 96), (104, 112)):
            p.drawLine(QPointF(x1, 606), QPointF(x2, 606))
        p.restore()
        # skyline (in front of the circuits)
        p.save()
        p.translate(0, self.CITY_DY)
        p.setPen(pen)
        p.setBrush(panel)
        for x, bw, top in self.BUILDINGS:
            p.drawRect(QRectF(x + 0.5, top, bw - 1, 770 - top))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cy)
        for wx, wy, _ in self.windows:
            p.drawRect(QRectF(wx, wy, 2.4, 3.2))
        p.setPen(pen)
        for a, b in (((103, 612), (103, 578)), ((97, 596), (109, 596)), ((99, 588), (107, 588)), ((193, 632), (193, 614)),
                     ((0, 759.5), (224, 759.5))):
            p.drawLine(QPointF(*a), QPointF(*b))
        p.restore()
        p.end()
        self._cache_key, self._static = key, pm
        return pm

    def paint(self, p: QPainter, w: int, h: int, t: float, dpr: float) -> None:
        img = QImage(round(w * dpr), round(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.drawPixmap(0, 0, self._static_layer(w, h, dpr))
        q.translate((w - self.W) / 2, h - self.H)
        tint = theme.c("cyt")
        # data pulses
        q.save()
        q.translate(0, self.CIRCUIT_DY)
        q.setPen(QPen(tint, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for idx, dur, phase in self.PULSES:
            path = self.paths[idx]
            length = path.length()
            start = ((t + phase) / dur % 1.0) * (length + 12) - 12
            seg = QPainterPath()
            for k in range(0, 11):
                d = min(max(start + k, 0), length)
                pt = path.pointAtPercent(path.percentAtLength(d))
                seg.moveTo(pt) if k == 0 else seg.lineTo(pt)
            q.drawPath(seg)
        q.restore()
        # lit windows + beacons
        q.save()
        q.translate(0, self.CITY_DY)
        q.setPen(Qt.PenStyle.NoPen)
        for wx, wy, r in self.lit:
            phase = (t / 4 + r * 10) % 1
            c = QColor(tint)
            c.setAlphaF(tint.alphaF() * (0.25 if 0.47 < phase < 0.53 else 1))
            q.setBrush(c)
            q.drawRect(QRectF(wx, wy, 2.4, 3.2))
        for (bx, by, rad, off) in ((103, 575, 2.2, 0), (193, 612, 1.6, 1.1)):
            c = QColor(tint)
            c.setAlphaF(tint.alphaF() * (0.15 + 0.85 * (0.5 + 0.5 * math.cos((t + off) / 2.2 * 2 * math.pi))))
            q.setBrush(c)
            q.drawEllipse(QPointF(bx, by), rad, rad)
        q.restore()
        # fade out towards the nav items (top) and the bottom section
        q.resetTransform()
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        g = QLinearGradient(0, 0, 0, h)
        for pos, a in ((0, 0), (0.16, 0.4), (0.40, 1), (0.63, 1), (0.77, 0), (1, 0)):
            g.setColorAt(pos, QColor(0, 0, 0, round(255 * a)))
        q.fillRect(QRectF(0, 0, w, h), g)
        q.end()
        p.drawImage(0, 0, img)


class Sidebar(QWidget):
    """Panel background + cyber art + scanlines + sliding active-item bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(224)
        self.art = CyberArt()
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._bar_y = -1.0
        self._bar_h = 0.0
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(10, 14, 10, 12)
        self.lay.setSpacing(2)

    def _tick(self):
        self._t += 0.05
        self.update()

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def point_bar_at(self, btn: QWidget | None) -> None:
        if btn is None:
            self._bar_h = 0
            self.update()
            return
        y = btn.mapTo(self, btn.rect().topLeft()).y() + 9
        h = btn.height() - 18
        if self._bar_y < 0 or not self.isVisible():
            self._bar_y, self._bar_h = y, h
            self.update()
            return
        self._bar_h = h
        animate(self, self._bar_y, y, 420, self._set_bar, QEasingCurve.Type.OutBack)

    def _set_bar(self, v):
        self._bar_y = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), theme.c("panel"))
        self.art.paint(p, w, h, self._t, self.devicePixelRatioF())
        p.setPen(Qt.PenStyle.NoPen)
        scan = theme.c("scan")
        for y in range(0, h, 3):
            p.fillRect(0, y, w, 1, scan)
        p.fillRect(w - 1, 0, 1, h, theme.c("line"))
        if self._bar_h > 0:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(theme.c("ink"))
            p.drawRoundedRect(QRectF(0, self._bar_y, 3, self._bar_h), 1.5, 1.5)


# ---------------------------------------------------------------- switch + rows
class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self.toggled.connect(lambda on: animate(self, self._t, 1 if on else 0, 380, self._set_t,
                                                QEasingCurve.Type.OutBack))

    def set_now(self, on: bool) -> None:
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._t = 1.0 if on else 0.0
        self.update()

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mix(theme.c("panel3"), theme.c("ink"), self._t))
        p.drawRoundedRect(r, 11, 11)
        k = QRectF(3 + 16 * self._t, 3, 16, 16)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(k.translated(0, 1))
        p.setBrush(theme.c("win"))
        p.drawEllipse(k)
        if self._t > 0.01:
            p.setOpacity(min(1.0, self._t))
            p.setBrush(QColor(HAIR_WHITE))
            p.drawEllipse(k)
            p.setBrush(QColor(HAIR_BLACK))
            p.drawPie(k, 90 * 16, 180 * 16)


class SwitchRow(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        txt = QVBoxLayout()
        txt.setSpacing(1)
        self.title = QLabel()
        self.title.setObjectName("rowTitle")
        self.sub = QLabel()
        self.sub.setObjectName("rowSub")
        txt.addWidget(self.title)
        txt.addWidget(self.sub)
        lay.addLayout(txt, 1)
        self.switch = Switch()
        self.switch.toggled.connect(self.toggled)
        lay.addWidget(self.switch)

    def set_texts(self, title: str, sub: str) -> None:
        self.title.setText(title)
        self.sub.setText(sub)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.switch.toggle()


class LangCard(QAbstractButton):
    def __init__(self, code: str, title: str, parent=None):
        super().__init__(parent)
        self.code, self.title, self.sub = code, title, ""
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(56)
        self._h = 0.0

    def nextCheckState(self):
        pass

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 180, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 220, self._set_h)

    def sizeHint(self):
        return QSize(220, 56)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        border = theme.c("ink") if on else mix(theme.c("line2"), theme.c("muted"), self._h)
        p.setPen(QPen(border, 2 if on else 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 13, 13)
        badge = QRectF(14, r.center().y() - 10, 28, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("ink") if on else theme.c("panel2"))
        p.drawRoundedRect(badge, 6, 6)
        p.setPen(theme.c("on_ink") if on else theme.c("muted"))
        p.setFont(font(7.6, QFont.Weight.ExtraBold, mono=True))
        p.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.code)
        p.setPen(theme.c("text") if on or self._h > 0.5 else theme.c("muted"))
        p.setFont(font(10, QFont.Weight.Bold))
        p.drawText(QRectF(54, r.top() + 9, r.width() - 60, 20), Qt.AlignmentFlag.AlignVCenter, self.title)
        p.setPen(theme.c("faint"))
        p.setFont(font(8.2))
        p.drawText(QRectF(54, r.top() + 28, r.width() - 60, 16), Qt.AlignmentFlag.AlignVCenter, self.sub)


# ---------------------------------------------------------------- settings tabs (toolkit 1.2)
class TabButton(QAbstractButton):
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self._h = 0.0

    def sizeHint(self):
        from PySide6.QtGui import QFontMetrics
        return QSize(QFontMetrics(font(10, QFont.Weight.Bold)).horizontalAdvance(self.text()) + 58, 44)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 180, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 220, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        tile = QRectF(10, 7, 26, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("ink") if on else theme.c("panel2"))
        p.drawRoundedRect(tile, 8, 8)
        ic = theme.c("on_ink") if on else mix(theme.c("muted"), theme.c("text"), self._h)
        p.drawPixmap(QPointF(tile.center().x() - 7, tile.center().y() - 7),
                     icon_pixmap(self.icon, ic, 14, self.devicePixelRatioF()))
        p.setPen(theme.c("text") if on else mix(theme.c("muted"), theme.c("text"), self._h))
        p.setFont(font(10, QFont.Weight.Bold))
        p.drawText(QRectF(tile.right() + 9, 0, self.width(), 40), Qt.AlignmentFlag.AlignVCenter, self.text())


class TabBar(QWidget):
    """Row of TabButtons with a sliding underline. changed(key)."""
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(2)
        self.lay.addStretch(1)
        self.buttons: dict[str, TabButton] = {}
        self.current = ""
        self._x, self._w = 0.0, 0.0
        self.setFixedHeight(46)

    def add(self, key: str, icon: str, text: str, separator: QWidget | None = None):
        if separator is not None:
            self.lay.insertWidget(self.lay.count() - 1, separator)
        b = TabButton(icon, text)
        b.clicked.connect(lambda _=False, k=key: self.select(k))
        self.lay.insertWidget(self.lay.count() - 1, b)
        self.buttons[key] = b
        return b

    def remove(self, key: str):
        b = self.buttons.pop(key, None)
        if b:
            self.lay.removeWidget(b)
            b.deleteLater()

    def select(self, key: str, animated: bool = True):
        if key not in self.buttons:
            return
        changed = key != self.current
        self.current = key
        self.buttons[key].setChecked(True)
        b = self.buttons[key]
        tx, tw = float(b.x()), float(b.width())
        if animated and self._w:
            x0, w0 = self._x, self._w

            def step(v):
                self._x, self._w = x0 + (tx - x0) * v, w0 + (tw - w0) * v
                self.update()
            animate(self, 0, 1, 380, step, QEasingCurve.Type.OutBack)
        else:
            self._x, self._w = tx, tw
            self.update()
        if changed:
            self.changed.emit(key)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, lambda: self.select(self.current, animated=False) if self.current else None)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), theme.c("line"))
        if self._w:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("ink"))
            p.drawRoundedRect(QRectF(self._x + 6, self.height() - 2.5, self._w - 12, 2.5), 1.2, 1.2)
