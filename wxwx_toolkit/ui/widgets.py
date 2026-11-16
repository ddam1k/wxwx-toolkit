"""Custom-painted widgets: split logo, theme toggle, segmented control, chips, sliders, etc."""
from __future__ import annotations

import math

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap)
from PySide6.QtWidgets import QAbstractButton, QLayout, QSlider, QSizePolicy, QStyle, QWidget

from .theme import HAIR_BLACK, HAIR_WHITE, font, theme


# ---------- helpers ----------
def animate(owner, start: float, end: float, ms: int, on_value, curve=QEasingCurve.Type.OutCubic,
            on_done=None) -> QVariantAnimation:
    a = QVariantAnimation(owner)
    a.setStartValue(float(start))
    a.setEndValue(float(end))
    a.setDuration(ms)
    a.setEasingCurve(curve)
    a.valueChanged.connect(on_value)
    if on_done:
        a.finished.connect(on_done)
    a.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return a


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t), round(a.alpha() + (b.alpha() - a.alpha()) * t))


def hair_path(size: float) -> QPainterPath:
    """Left 'black hair' half of the logo circle, with a wavy parting line (32x32 design grid)."""
    k = size / 32
    p = QPainterPath(QPointF(16 * k, 1 * k))
    p.cubicTo(10.5 * k, 7 * k, 21.5 * k, 12 * k, 16 * k, 18 * k)
    p.cubicTo(11.5 * k, 22.5 * k, 19 * k, 26.5 * k, 16 * k, 31 * k)
    p.arcTo(QRectF(1 * k, 1 * k, 30 * k, 30 * k), 270, -180)
    p.closeSubpath()
    return p


def paint_logo(p: QPainter, size: float, ring: QColor | None = None) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(HAIR_WHITE))
    p.drawEllipse(QRectF(size / 32, size / 32, size * 30 / 32, size * 30 / 32))
    p.setBrush(QColor(HAIR_BLACK))
    p.drawPath(hair_path(size))
    if ring:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(ring, 1))
        p.drawEllipse(QRectF(size / 32, size / 32, size * 30 / 32, size * 30 / 32))


def logo_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_logo(p, size)
    p.end()
    return pm


# ---------- flow layout ----------
class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def clear(self):
        while self._items:
            it = self._items.pop()
            if it.widget():
                it.widget().setParent(None)
                it.widget().deleteLater()
        self.invalidate()

    def _do(self, rect: QRect, test: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for it in self._items:
            if it.widget() and it.widget().isHidden():
                continue
            hint = it.sizeHint()
            nx = x + hint.width() + self._sp
            if nx - self._sp > rect.right() + 1 and line > 0:
                x, y = rect.x(), y + line + self._sp
                nx = x + hint.width() + self._sp
                line = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x, line = nx, max(line, hint.height())
        return y + line - rect.y()


# ---------- logo ----------
class Logo(QWidget):
    def __init__(self, size: int = 28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._spin = QVariantAnimation(self)
        self._spin.setStartValue(0.0)
        self._spin.setEndValue(360.0)
        self._spin.setDuration(2400)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._set_angle)

    def _set_angle(self, v):
        self._angle = float(v)
        self.update()

    def set_busy(self, busy: bool) -> None:
        if busy:
            self._spin.start()
        else:
            self._spin.stop()
            animate(self, self._angle, 360 if self._angle > 180 else 0, 500, self._set_angle,
                    on_done=lambda: self._set_angle(0))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width()
        p.translate(s / 2, s / 2)
        p.rotate(self._angle)
        p.translate(-s / 2, -s / 2)
        paint_logo(p, s, theme.c("text", 46))


# ---------- theme toggle ----------
class ThemeToggle(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(58, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Чёрная / белая сторона")
        self._pos = 0.0
        self._hover = 0.0

    def set_light(self, light: bool, animated: bool = True) -> None:
        end = 1.0 if light else 0.0
        if animated:
            animate(self, self._pos, end, 550, self._set_pos, QEasingCurve.Type.OutBack)
        else:
            self._set_pos(end)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._hover, 1, 200, self._set_hover)

    def leaveEvent(self, e):
        animate(self, self._hover, 0, 200, self._set_hover)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        pill = QPainterPath()
        pill.addRoundedRect(r, r.height() / 2, r.height() / 2)
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        g.setColorAt(0, QColor(HAIR_BLACK))
        g.setColorAt(0.4999, QColor(HAIR_BLACK))
        g.setColorAt(0.5, QColor(HAIR_WHITE))
        g.setColorAt(1, QColor(HAIR_WHITE))
        p.fillPath(pill, g)
        p.setPen(QPen(theme.c("line2"), 1))
        p.drawPath(pill)
        kw = 22 + 4 * self._hover
        x = 3 + self._pos * (self.width() - 6 - kw)
        knob = QRectF(x, 3, kw, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRoundedRect(knob.translated(0, 1.5), 11, 11)
        p.setBrush(mix(QColor(HAIR_WHITE), QColor(HAIR_BLACK), self._pos))
        p.drawRoundedRect(knob, 11, 11)


# ---------- segmented control ----------
class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str, str]], parent=None):
        super().__init__(parent)
        self.options = options
        self._value = options[0][0]
        self._ind = 0.0
        self._hover = -1
        self._disabled: set[str] = set()
        self._anim: QVariantAnimation | None = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48 if any(o[2] for o in options) else 36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def value(self) -> str:
        return self._value

    def _index(self, v: str) -> int:
        return next((i for i, o in enumerate(self.options) if o[0] == v), 0)

    def set_value(self, v: str, animated: bool = True) -> None:
        if v == self._value and self._anim is None:
            return
        self._value = v
        end = float(self._index(v))
        if animated and self.isVisible():
            if self._anim:
                self._anim.stop()
            self._anim = animate(self, self._ind, end, 450, self._set_ind, QEasingCurve.Type.OutBack,
                                 on_done=self._anim_done)
        else:
            self._set_ind(end)

    def _anim_done(self):
        self._anim = None

    def _set_ind(self, v):
        self._ind = float(v)
        self.update()

    def set_disabled(self, v: str, disabled: bool) -> None:
        (self._disabled.add if disabled else self._disabled.discard)(v)
        self.update()

    def _seg_w(self) -> float:
        return (self.width() - 6) / len(self.options)

    def _hit(self, x: float) -> int:
        i = int((x - 3) // self._seg_w())
        return i if 0 <= i < len(self.options) else -1

    def mouseMoveEvent(self, e):
        h = self._hit(e.position().x())
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        i = self._hit(e.position().x())
        if i < 0:
            return
        v = self.options[i][0]
        if v in self._disabled or v == self._value:
            return
        self.set_value(v)
        self.changed.emit(v)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel2"))
        p.drawRoundedRect(r, 11, 11)
        sw = self._seg_w()
        ind = QRectF(3 + self._ind * sw, 3, sw, r.height() - 6)
        p.setBrush(QColor(0, 0, 0, 35 if theme.dark else 18))
        p.drawRoundedRect(ind.translated(0, 1), 8, 8)
        p.setBrush(theme.c("seg_ind"))
        p.setPen(QPen(theme.c("line"), 1))
        p.drawRoundedRect(ind, 8, 8)
        f_title = font(9.4, QFont.Weight.Bold)
        f_sub = font(7.4, QFont.Weight.DemiBold)
        for i, (v, title, sub) in enumerate(self.options):
            cell = QRectF(3 + i * sw, 3, sw, r.height() - 6)
            off = v in self._disabled
            sel = abs(self._ind - i) < 0.5
            col = theme.c("text") if (sel or i == self._hover) and not off else theme.c("muted")
            if off:
                col.setAlpha(90)
            p.setPen(col)
            p.setFont(f_title)
            if sub:
                top = QRectF(cell.left(), cell.top() + 3, cell.width(), 19)
                p.drawText(top, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, title)
                sc = theme.c("faint")
                if off:
                    sc.setAlpha(80)
                p.setPen(sc)
                p.setFont(f_sub)
                bottom = QRectF(cell.left(), cell.top() + 23, cell.width(), cell.height() - 24)
                p.drawText(bottom, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, sub)
            else:
                p.drawText(cell, Qt.AlignmentFlag.AlignCenter, title)


# ---------- chip ----------
class Chip(QAbstractButton):
    def __init__(self, text: str, sub: str = "", dot: bool = False, small: bool = False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.sub = sub
        self.dot = dot
        self.small = small
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 0.0
        self._h = 0.0
        self.toggled.connect(lambda c: animate(self, self._t, 1 if c else 0, 260, self._set_t))

    def nextCheckState(self):  # checked state is driven from outside
        pass

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 160, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 220, self._set_h)

    def _fonts(self):
        size = 8.6 if self.small else 9.3
        return font(size, QFont.Weight.DemiBold), font(7.6, QFont.Weight.Bold)

    def sizeHint(self):
        f, fs = self._fonts()
        w = QFontMetricsF(f).horizontalAdvance(self.text())
        if self.sub:
            w += 6 + QFontMetricsF(fs).horizontalAdvance(self.sub)
        if self.dot:
            w += 13
        pad = 10 if self.small else 12
        return QSize(math.ceil(w + pad * 2 + 2), 26 if self.small else 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        on = self._t
        border = mix(mix(theme.c("line2"), theme.c("muted"), self._h), theme.c("ink"), on)
        bg = theme.c("ink")
        bg.setAlpha(round(255 * on))
        fg = mix(mix(theme.c("muted"), theme.c("text"), self._h), theme.c("on_ink"), on)
        if not self.isEnabled():
            fg.setAlpha(80)
            border.setAlpha(60)
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        f, fs = self._fonts()
        pad = 10 if self.small else 12
        x = r.left() + pad
        if self.dot:
            d = QRectF(x, r.center().y() - 3.5, 7, 7)
            p.setPen(QPen(theme.c("line2"), 1))
            p.setBrush(QColor(HAIR_BLACK))
            p.drawEllipse(d)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(HAIR_WHITE))
            p.drawPie(d, -90 * 16, 180 * 16)
            x += 13
        p.setFont(f)
        p.setPen(fg)
        tw = QFontMetricsF(f).horizontalAdvance(self.text())
        p.drawText(QRectF(x, r.top(), tw + 2, r.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.sub:
            sc = QColor(fg)
            sc.setAlpha(round(sc.alpha() * 0.6))
            p.setPen(sc)
            p.setFont(fs)
            p.drawText(QRectF(x + tw + 6, r.top(), 200, r.height()), Qt.AlignmentFlag.AlignVCenter, self.sub)


# ---------- slider with a split black/white thumb ----------
class SplitSlider(QSlider):
    M = 10  # side margin = thumb radius

    def __init__(self, lo: int, hi: int, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(lo, hi)
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._h = 0.0
        self._press = 0.0
        self._rot = 0.0

    def _set(self, attr, v):
        setattr(self, attr, float(v))
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 200, lambda v: self._set("_h", v))

    def leaveEvent(self, e):
        animate(self, self._h, 0, 250, lambda v: self._set("_h", v))

    def _value_at(self, x: float) -> int:
        span = self.width() - 2 * self.M
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x - self.M), max(1, span))

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.setSliderDown(True)
        self.setValue(self._value_at(e.position().x()))
        animate(self, self._press, 1, 300, lambda v: self._set("_press", v), QEasingCurve.Type.OutBack)
        animate(self, self._rot, 180, 450, lambda v: self._set("_rot", v), QEasingCurve.Type.OutCubic)

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setValue(self._value_at(e.position().x()))

    def mouseReleaseEvent(self, e):
        if self.isSliderDown():
            self.setSliderDown(False)
            animate(self, self._press, 0, 300, lambda v: self._set("_press", v))
            animate(self, self._rot, 0, 450, lambda v: self._set("_rot", v))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        span = self.width() - 2 * self.M
        rng = max(1, self.maximum() - self.minimum())
        frac = (self.value() - self.minimum()) / rng
        x = self.M + frac * span
        cy = self.height() / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel3"))
        p.drawRoundedRect(QRectF(self.M, cy - 2, span, 4), 2, 2)
        p.setBrush(theme.c("ink"))
        p.drawRoundedRect(QRectF(self.M, cy - 2, x - self.M, 4), 2, 2)
        rad = 9 * (1 + 0.1 * self._h + 0.18 * self._press)
        if self._press > 0.01:
            g = theme.c("tint", round(70 * self._press))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, cy), rad + 5 * self._press, rad + 5 * self._press)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawEllipse(QPointF(x, cy + 1.5), rad, rad)
        p.save()
        p.translate(x, cy)
        p.rotate(self._rot + 20 * self._h)
        circle = QRectF(-rad, -rad, 2 * rad, 2 * rad)
        p.setBrush(QColor(HAIR_WHITE))
        p.drawEllipse(circle)
        p.setBrush(QColor(HAIR_BLACK))
        p.drawPie(circle, 90 * 16, 180 * 16)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(theme.c("line2"), 1.2))
        p.drawEllipse(QPointF(x, cy), rad, rad)


# ---------- main action button with progress fill ----------
class ProgressButton(QAbstractButton):
    def __init__(self, text: str, parent=None, height: int = 48, font_size: float = 11.0, radius: float = 13):
        super().__init__(parent)
        self.setText(text)
        self.setFixedHeight(height)
        self.font_size = font_size
        self.radius = radius
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress = 0.0
        self._shine = -0.4
        self._h = 0.0
        self._down = 0.0

    def set_progress(self, v: float) -> None:
        self.progress = v
        self.update()

    def _set(self, attr, v):
        setattr(self, attr, float(v))
        self.update()

    def enterEvent(self, e):
        animate(self, -0.4, 1.4, 900, lambda v: self._set("_shine", v))
        animate(self, self._h, 1, 200, lambda v: self._set("_h", v))

    def leaveEvent(self, e):
        animate(self, self._h, 0, 250, lambda v: self._set("_h", v))

    def mousePressEvent(self, e):
        animate(self, self._down, 1, 120, lambda v: self._set("_down", v))
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        animate(self, self._down, 0, 350, lambda v: self._set("_down", v), QEasingCurve.Type.OutBack)
        super().mouseReleaseEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        k = 1 - 0.02 * self._down
        r = QRectF(self.rect())
        r = QRectF(r.center().x() - r.width() * k / 2, r.center().y() - r.height() * k / 2,
                   r.width() * k, r.height() * k)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.fillPath(path, mix(theme.c("ink"), theme.c("tint"), 0.12 * self._h))
        p.setClipPath(path)
        if self.progress > 0:
            p.fillRect(QRectF(r.left(), r.top(), r.width() * self.progress, r.height()), theme.c("tint", 110))
        sx = r.left() + self._shine * r.width()
        g = QLinearGradient(sx - 60, 0, sx + 60, 0)
        shine = QColor(theme.c("tint", 90) if theme.dark else QColor(255, 255, 255, 70))
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(0.5, shine)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(r, g)
        p.setClipping(False)
        p.setPen(theme.c("on_ink"))
        p.setFont(font(self.font_size, QFont.Weight.ExtraBold))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())

    def sizeHint(self):
        w = QFontMetricsF(font(self.font_size, QFont.Weight.ExtraBold)).horizontalAdvance(self.text())
        return QSize(math.ceil(w) + 36, self.height())


# ---------- thin progress bar ----------
class ThinBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self.value = 0.0
        self.active = False
        self._off = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._off = (self._off + 0.02) % 1
        self.update()

    def set_state(self, value: float, active: bool) -> None:
        self.value = value
        if active != self.active:
            self.active = active
            self._timer.start() if active else self._timer.stop()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel3"))
        p.drawRoundedRect(r, 1.5, 1.5)
        if self.value <= 0:
            return
        fill = QRectF(0, 0, r.width() * self.value, r.height())
        if self.active:
            w = max(80.0, r.width() / 2)
            g = QLinearGradient(-self._off * w * 2, 0, -self._off * w * 2 + w * 2, 0)
            g.setSpread(QLinearGradient.Spread.RepeatSpread)
            g.setColorAt(0, theme.c("ink"))
            g.setColorAt(0.5, theme.c("tint"))
            g.setColorAt(1, theme.c("ink"))
            p.setBrush(g)
        else:
            p.setBrush(theme.c("ink"))
        p.drawRoundedRect(fill, 1.5, 1.5)


# ---------- thumbnail ----------
class Thumb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(84, 52)
        self.pixmap: QPixmap | None = None
        self.duration = ""
        self._done = 0.0

    def set_done(self, done: bool) -> None:
        animate(self, self._done, 1 if done else 0, 500, self._set_done, QEasingCurve.Type.OutBack)

    def _set_done(self, v):
        self._done = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        if self.pixmap and not self.pixmap.isNull():
            pm = self.pixmap
            s = max(r.width() / pm.width(), r.height() / pm.height())
            w, h = pm.width() * s, pm.height() * s
            p.drawPixmap(QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h), pm, QRectF(pm.rect()))
        else:
            g = QLinearGradient(0, 0, r.width(), r.height())
            g.setColorAt(0, theme.c("panel3"))
            g.setColorAt(1, theme.c("panel2"))
            p.fillRect(r, g)
        if self._done > 0.01:
            p.fillRect(r, QColor(17, 17, 19, round(140 * min(1, self._done))))
            k = self._done
            p.save()
            p.translate(r.center())
            p.scale(k, k)
            pen = QPen(QColor(255, 255, 255), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                       Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            check = QPainterPath(QPointF(-8, 0.5))
            check.lineTo(-2.5, 5.5)
            check.lineTo(8, -5.5)
            p.drawPath(check)
            p.restore()
        if self.duration:
            f = font(7.2, QFont.Weight.Bold, mono=True)
            p.setFont(f)
            tw = QFontMetricsF(f).horizontalAdvance(self.duration) + 9
            badge = QRectF(r.right() - tw - 4, r.bottom() - 17, tw, 13)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(badge, 4, 4)
            p.setPen(QColor(255, 255, 255))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.duration)


# ---------- drop zone ----------
class DropZone(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(66)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._h = 0.0

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 250, self._set_h, QEasingCurve.Type.OutBack)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 250, self._set_h)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = theme.c("panel")
        bg.setAlpha(round(255 * min(1, self._h)))
        p.setBrush(bg)
        pen = QPen(mix(theme.c("line2"), theme.c("muted"), self._h), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)
        # icon tile
        ic = QRectF(r.left() + 15, r.center().y() - 19, 38, 38)
        p.save()
        p.translate(ic.center())
        p.rotate(-6 * self._h)
        p.translate(0, -2 * self._h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel2"))
        p.drawRoundedRect(QRectF(-19, -19, 38, 38), 11, 11)
        pen = QPen(mix(theme.c("muted"), theme.c("text"), self._h), 1.7, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        arrow = QPainterPath(QPointF(0, 4))
        arrow.lineTo(0, -7)
        arrow.moveTo(-4.5, -2.5)
        arrow.lineTo(0, -7)
        arrow.lineTo(4.5, -2.5)
        arrow.moveTo(-7, 3)
        arrow.lineTo(-7, 6)
        arrow.quadTo(-7, 8, -5, 8)
        arrow.lineTo(5, 8)
        arrow.quadTo(7, 8, 7, 6)
        arrow.lineTo(7, 3)
        p.drawPath(arrow)
        p.restore()
        x = ic.right() + 14
        fb = font(9.6, QFont.Weight.Bold)
        fn = font(9.6)
        fs = font(8.2)
        bold = "Перетащи видео сюда"
        p.setFont(fb)
        p.setPen(theme.c("text"))
        bw = QFontMetricsF(fb).horizontalAdvance(bold)
        p.drawText(QPointF(x, r.center().y() - 2), bold)
        p.setFont(fn)
        p.setPen(mix(theme.c("muted"), theme.c("text"), self._h))
        p.drawText(QPointF(x + bw + 4, r.center().y() - 2), "или выбери файлы")
        p.setFont(fs)
        p.setPen(theme.c("faint"))
        p.drawText(QPointF(x, r.center().y() + 15), "MP4, MOV, MKV, WebM, AVI, GIF · можно пачкой или папкой")


# ---------- drag overlay ----------
class DropOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._o = 0.0
        self._dash = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def _tick(self):
        self._dash = (self._dash + 0.6) % 22
        self.update()

    def _set_o(self, v):
        self._o = float(v)
        self.update()
        if self._o <= 0.01 and not self._timer.isActive():
            self.hide()

    def show_overlay(self, on: bool) -> None:
        if on:
            self.setGeometry(self.parentWidget().rect())
            self.show()
            self.raise_()
            self._timer.start()
            animate(self, self._o, 1, 220, self._set_o)
        else:
            self._timer.stop()
            animate(self, self._o, 0, 220, self._set_o)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._o)
        r = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("win", 225))
        p.drawRoundedRect(r, 14, 14)
        pen = QPen(theme.c("ink"), 2, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([6, 5])
        pen.setDashOffset(-self._dash)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 14, 14)
        s = 44 * (0.95 + 0.05 * self._o)
        p.save()
        p.translate(r.center().x() - s / 2, r.center().y() - s - 6)
        paint_logo(p, s)
        p.restore()
        p.setPen(theme.c("text"))
        p.setFont(font(14, QFont.Weight.ExtraBold))
        p.drawText(QRectF(r.left(), r.center().y() + 4, r.width(), 30), Qt.AlignmentFlag.AlignHCenter,
                   "Отпусти — добавлю в очередь")


# ---------- toast ----------
class Toast(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text = ""
        self.right_inset = 0
        self._o = 0.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: animate(self, self._o, 0, 300, self._set_o))
        self.hide()

    def _set_o(self, v):
        self._o = float(v)
        self._place()
        self.update()
        if self._o <= 0.01:
            self.hide()

    def _place(self):
        par = self.parentWidget()
        f = font(9.8, QFont.Weight.Bold)
        # boundingRect lays the text out with fallback fonts (emoji, « ») — advance alone can come out short
        fm = QFontMetricsF(f)
        w = int(max(fm.horizontalAdvance(self.text), fm.boundingRect(self.text).width(),
                    fm.boundingRect(QRectF(0, 0, 4000, 60), Qt.AlignmentFlag.AlignLeft, self.text).width())) + 52
        w = min(w, max(120, par.width() - 40))
        y = par.height() - 70 + round(24 * (1 - self._o))
        area = max(w, par.width() - self.right_inset)
        self.setGeometry((area - w) // 2, y, w, 42)

    def show_text(self, text: str, ms: int = 2600) -> None:
        self.text = text
        self.show()
        self.raise_()
        animate(self, self._o, 1, 450, self._set_o, QEasingCurve.Type.OutBack)
        self._timer.start(ms)

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
        p.setPen(theme.c("on_ink"))
        p.setFont(font(9.8, QFont.Weight.Bold))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text)


# ---------- circular theme reveal ----------
class RevealOverlay(QWidget):
    """Shows a snapshot of the old theme and cuts a growing circle out of it."""

    def __init__(self, parent: QWidget, snapshot: QPixmap, center: QPointF):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.snapshot = snapshot
        self.center = center
        self.radius = 0.0
        self.setGeometry(parent.rect())
        w, h = parent.width(), parent.height()
        self.max_r = max(math.hypot(center.x() - x, center.y() - y) for x in (0, w) for y in (0, h)) + 4
        self.show()
        self.raise_()
        animate(self, 0, self.max_r, 750, self._set_r, QEasingCurve.Type.InOutCubic, on_done=self.deleteLater)

    def _set_r(self, v):
        self.radius = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRect(QRectF(self.rect()))
        hole = QPainterPath()
        hole.addEllipse(self.center, self.radius, self.radius)
        p.setClipPath(clip.subtracted(hole))
        p.drawPixmap(0, 0, self.snapshot)
