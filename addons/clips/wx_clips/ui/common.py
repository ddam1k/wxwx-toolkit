"""Small shared pieces: time formats, async loading, pixmap cache, painting helpers, tab row."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget

from ..core.i18n import t
from .theme import font, theme
from .widgets import ICONS, animate, icon_pixmap, mix

SEGC = ["#b8a8e2", "#eea883", "#7fd1a8", "#82b9ea", "#ea92b4", "#dcc574"]

ICONS.update({
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "segs": '<rect x="2" y="8" width="6" height="8" rx="1.5"/><rect x="10" y="8" width="4" height="8" rx="1.5"/><rect x="16" y="8" width="6" height="8" rx="1.5"/>',
    "merge": '<path d="M4 6h5l3 6-3 6H4M20 12h-8M16 8l4 4-4 4"/>',
    "nvidia": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M10 11.5v4l3.5-2z"/>',
    "chev": '<path d="M9 6l6 6-6 6"/>',
    "back": '<path d="M15 6l-6 6 6 6"/>',
    "loop": '<path d="M17 2l3 3-3 3M3 11V9a4 4 0 0 1 4-4h13M7 22l-3-3 3-3M21 13v2a4 4 0 0 1-4 4H4"/>',
    "pencil": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "clips": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "play": '<path d="M8 5.5v13l10.5-6.5z"/>',
    "pause": '<path d="M9 6v12M15 6v12"/>',
})


# ---------------------------------------------------------------- time
def pad(n: float) -> str:
    return f"{int(n):02d}"


def tcode(s: float) -> str:
    s = max(0.0, s)
    return f"{pad(s // 60)}:{pad(s % 60)}.{pad((s % 1) * 100)}"


def short(s: float) -> str:
    s = round(max(0.0, s))
    return f"{s // 60}:{pad(s % 60)}"


def parse_t(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    if not text:
        return None
    total = 0.0
    try:
        for part in text.split(":"):
            total = total * 60 + float(part or 0)
    except ValueError:
        return None
    return total


def when(ts: float) -> str:
    d = datetime.fromtimestamp(ts)
    now = datetime.now()
    days = (now.date() - d.date()).days
    hm = d.strftime("%H:%M")
    if days == 0:
        return t("today", t=hm)
    if days == 1:
        return t("yesterday", t=hm)
    m = t("months")[d.month - 1]
    return f"{d.day} {m}" + (f" {d.year}" if d.year != now.year else "")


def since(kind: str, last_launch: float) -> float:
    if kind == "day":
        return time.time() - 86400
    if kind == "week":
        return time.time() - 7 * 86400
    return last_launch


# ---------------------------------------------------------------- async work
class Loader(QObject):
    """Runs functions on a small thread pool; results come back on the GUI thread as done(key, value)."""
    done = Signal(str, object)

    def __init__(self, workers: int = 3, parent=None):
        super().__init__(parent)
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.pending: set[str] = set()
        self.done.connect(lambda k, _v: self.pending.discard(k))

    def submit(self, key: str, fn, *args) -> None:
        if key in self.pending:
            return
        self.pending.add(key)

        def run():
            try:
                v = fn(*args)
            except Exception:
                v = None
            try:
                self.done.emit(key, v)
            except RuntimeError:          # page already destroyed
                pass
        self.pool.submit(run)

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


_pix: dict[str, QPixmap] = {}


def pixmap(path: str | None) -> QPixmap | None:
    if not path:
        return None
    pm = _pix.get(path)
    if pm is None:
        pm = QPixmap(path)
        if pm.isNull():
            return None
        if len(_pix) > 1500:
            _pix.clear()
        _pix[path] = pm
    return pm


# ---------------------------------------------------------------- painting
def rounded(rect: QRectF, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


def draw_cover(p: QPainter, rect: QRectF, pm: QPixmap | None, radius: float = 0, top_only: bool = False) -> None:
    """Pixmap scaled to cover rect (cropped), clipped to a rounded rect. Black if no pixmap."""
    p.save()
    if radius:
        path = QPainterPath()
        if top_only:
            path.addRoundedRect(rect.adjusted(0, 0, 0, radius), radius, radius)
            clip = QPainterPath()
            clip.addRect(rect)
            path = path.intersected(clip)
        else:
            path.addRoundedRect(rect, radius, radius)
        p.setClipPath(path)
    p.fillRect(rect, QColor("#050506"))
    if pm is not None and not pm.isNull():
        sw, sh = pm.width(), pm.height()
        k = max(rect.width() / sw, rect.height() / sh)
        w, h = sw * k, sh * k
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QRectF(rect.center().x() - w / 2, rect.center().y() - h / 2, w, h), pm, QRectF(0, 0, sw, sh))
    p.restore()


def badge(p: QPainter, rect: QRectF, text: str, bg: QColor, fg: QColor, size: float = 7.4,
          weight=QFont.Weight.Bold, mono: bool = False, radius: float = 6) -> QRectF:
    """Small pill with text; rect gives the anchor (right/top aligned by caller). Returns its rect."""
    f = font(size, weight, mono)
    fm = QFontMetrics(f)
    w = fm.horizontalAdvance(text) + 12
    h = fm.height() + 4
    r = QRectF(rect.x(), rect.y(), w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(r, radius, radius)
    p.setPen(fg)
    p.setFont(f)
    p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
    return r


def text_w(text: str, f: QFont) -> float:
    return QFontMetrics(f).horizontalAdvance(text)


def label(text: str, name: str, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, name: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


# ---------------------------------------------------------------- tabs with a sliding underline
class HomeTab(QAbstractButton):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.count = 0
        self.count_tint = True
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self._h = 0.0

    def sizeHint(self):
        w = text_w(self.text(), font(10.6, QFont.Weight.ExtraBold)) + 26
        if self.count:
            w += text_w(str(self.count), font(8, QFont.Weight.ExtraBold)) + 20
        return QSize(int(w), 42)

    def set_count(self, n: int, tint: bool = True):
        self.count, self.count_tint = n, tint
        self.updateGeometry()
        self.update()

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 160, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 200, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        f = font(10.6, QFont.Weight.ExtraBold)
        p.setFont(f)
        p.setPen(theme.c("text") if on else mix(theme.c("muted"), theme.c("text"), self._h))
        tw = text_w(self.text(), f)
        p.drawText(QRectF(12, 0, tw + 4, 38), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.count:
            cf = font(8, QFont.Weight.ExtraBold)
            cw = max(20.0, text_w(str(self.count), cf) + 12)
            r = QRectF(12 + tw + 8, 9, cw, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("tint") if self.count_tint else theme.c("panel2"))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(QColor("#141416") if self.count_tint else theme.c("faint"))
            p.setFont(cf)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(self.count))


class TabRow(QWidget):
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self.lay.addStretch()
        self.tabs: dict[str, HomeTab] = {}
        self.current = ""
        self._x = self._w = 0.0
        self.setFixedHeight(44)

    def add(self, key: str, text: str) -> HomeTab:
        b = HomeTab(text)
        b.clicked.connect(lambda _=False, k=key: self.select(k, emit=True))
        self.lay.insertWidget(self.lay.count() - 1, b)
        self.tabs[key] = b
        return b

    def select(self, key: str, emit: bool = False, animated: bool = True):
        b = self.tabs.get(key)
        if not b:
            return
        b.setChecked(True)
        was = self.current
        self.current = key
        tx, tw = float(b.x()), float(b.width())
        if animated and self._w:
            x0, w0 = self._x, self._w

            def step(v):
                self._x, self._w = x0 + (tx - x0) * v, w0 + (tw - w0) * v
                self.update()
            animate(self, 0, 1, 360, step)
        else:
            self._x, self._w = tx, tw
            self.update()
        if emit and key != was:
            self.changed.emit(key)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.current:
            b = self.tabs[self.current]
            self._x, self._w = float(b.x()), float(b.width())

    def showEvent(self, e):
        super().showEvent(e)
        if self.current:
            self.select(self.current, animated=False)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), theme.c("line"))
        if self._w:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("ink"))
            p.drawRoundedRect(QRectF(self._x + 6, self.height() - 2.5, self._w - 12, 2.5), 1.2, 1.2)


class IconButton(QAbstractButton):
    """Round/rounded icon-only button (✎, ✕, loop…)."""

    def __init__(self, icon: str, size: int = 28, icon_size: int = 15, tip: str = "", parent=None):
        super().__init__(parent)
        self.icon = icon
        self.icon_size = icon_size
        self.setFixedSize(size, size)
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.active = False
        self.fill: QColor | None = None
        self._h = 0.0

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 150, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 200, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self.fill is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.fill)
            p.drawRoundedRect(r, 8, 8)
            col = QColor("#141416")
        else:
            bg = theme.c("panel3")
            bg.setAlpha(round(bg.alpha() * self._h))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r, 8, 8)
            col = theme.c("tint") if self.active else mix(theme.c("faint"), theme.c("text"), self._h)
        o = QPointF((r.width() - self.icon_size) / 2, (r.height() - self.icon_size) / 2)
        p.drawPixmap(o, icon_pixmap(self.icon, col, self.icon_size, self.devicePixelRatioF()))


# ---------------------------------------------------------------- smooth wheel scrolling
class SmoothScroll(QScrollArea):
    """Mouse wheel glides instead of jumping (touchpads keep their native pixel scrolling)."""

    def __init__(self, horizontal: bool = False, parent=None):
        super().__init__(parent)
        self.horizontal = horizontal
        self._target = None
        self._anim = QVariantAnimation(self)          # one long-lived animation, reused
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.bar().setValue(round(float(v))))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def bar(self):
        return self.horizontalScrollBar() if self.horizontal else self.verticalScrollBar()

    def wheelEvent(self, e):
        if not e.pixelDelta().isNull():
            return super().wheelEvent(e)
        d = e.angleDelta().y() or e.angleDelta().x()
        bar = self.bar()
        if not d or bar.maximum() <= bar.minimum():
            return super().wheelEvent(e)
        running = self._anim.state() == QVariantAnimation.State.Running
        start = float(bar.value())
        base = self._target if (running and self._target is not None) else start
        self._target = max(float(bar.minimum()), min(float(bar.maximum()), base - d * 1.1))
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(self._target)
        self._anim.start()
        e.accept()


# ---------------------------------------------------------------- cross-fade between two states of a widget
class _Ghost(QWidget):
    def __init__(self, parent: QWidget, pm: QPixmap, dx: float, dy: float, top: int = 0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.pm, self.dx, self.dy, self.k, self.top = pm, dx, dy, 1.0, top
        self.setGeometry(parent.rect().adjusted(0, top, 0, 0))
        self.show()
        self.raise_()

    def set_k(self, v):
        self.k = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setOpacity(self.k)
        p.translate(self.dx * (1 - self.k), self.dy * (1 - self.k))
        dpr = self.pm.devicePixelRatio()
        p.drawPixmap(QPointF(0, 0), self.pm, QRectF(0, self.top * dpr, self.pm.width(), self.pm.height() - self.top * dpr))


def snapshot(w: QWidget, bg: QColor) -> QPixmap:
    """Like grab(), but on our theme color — grab() fills unpainted areas with the (light) system palette."""
    dpr = w.devicePixelRatioF()
    pm = QPixmap(max(1, round(w.width() * dpr)), max(1, round(w.height() * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(bg)
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QRegion
    w.render(pm, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return pm


def fade_change(w: QWidget, change, ms: int = 320, dx: float = 0, dy: float = 0, top: int = 0, bg: str = "win"):
    """Snapshot w, apply change(), then let the snapshot fade (and drift by dx/dy) away over the new state.
    Only the part below `top` px is faded (headers above it stay put)."""
    if not w.isVisible() or w.width() < 4:
        change()
        return
    try:
        pm = snapshot(w, theme.c(bg))
    except Exception:
        pm = None
    change()
    if pm is None:
        return
    g = _Ghost(w, pm, dx, dy, max(0, top))
    animate(g, 1, 0, ms, g.set_k, QEasingCurve.Type.OutCubic, on_done=g.deleteLater)
    QTimer.singleShot(ms + 400, g.deleteLater)          # never leave a ghost behind
