"""Painted pieces of Covers: the cover itself (as it will be stored), track rows, the big drop-target preview."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton, QWidget

from ..core import audio
from ..core.i18n import fmt_size, short, t
from ..core.model import Item
from .theme import font, theme
from .widgets import ICONS, icon_pixmap, mix

ICONS.update({
    "music": '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    "cover": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5L5 21"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
    "crop": '<path d="M6 2v14a2 2 0 0 0 2 2h14M2 6h14a2 2 0 0 1 2 2v14"/>',
    "size": '<path d="M4 9V4h5M20 15v5h-5M4 4l7 7M20 20l-7-7"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-2"/>',
    "wand": '<path d="M15 4V2M15 10V8M11 6h2M17 6h2M4 20L14 10"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
})

PAD_COLORS = {"black": QColor("#0b0b0c"), "white": QColor("#f3f1ec")}
_blur_cache: dict[int, QPixmap] = {}


def _blurred(pm: QPixmap) -> QPixmap:
    """Shrink → stretch: the same soft background ffmpeg makes, good enough for a preview."""
    k = pm.cacheKey()
    if k not in _blur_cache:
        if len(_blur_cache) > 40:
            _blur_cache.clear()
        side = min(pm.width(), pm.height())
        sq = pm.copy((pm.width() - side) // 2, (pm.height() - side) // 2, side, side)
        small = sq.scaled(10, 10, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        _blur_cache[k] = small.scaled(120, 120, Qt.AspectRatioMode.IgnoreAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
    return _blur_cache[k]


def paint_cover(p: QPainter, r: QRectF, pm: QPixmap | None, fit: str = "crop", pad: str = "blur",
                radius: float = 8, empty_icon: bool = True) -> None:
    """The square the player will show: the picture cropped, or whole on a padded background."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.setClipPath(path)
    if pm is None or pm.isNull():
        p.fillRect(r, theme.c("panel2"))
        if empty_icon:
            s = max(12.0, r.width() * 0.4)
            ip = icon_pixmap("music", theme.c("faint"), int(s), p.device().devicePixelRatioF())
            p.drawPixmap(QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s), ip, QRectF(ip.rect()))
        p.restore()
        return
    w, h = pm.width(), pm.height()
    whole = fit == "fit" and not audio.is_square(w, h)
    if whole:
        if pad == "blur":
            b = _blurred(pm)
            p.drawPixmap(r, b, QRectF(b.rect()))
            p.fillRect(r, QColor(0, 0, 0, 16))
        else:
            p.fillRect(r, PAD_COLORS.get(pad, PAD_COLORS["black"]))
        k = min(r.width() / w, r.height() / h)
    else:
        k = max(r.width() / w, r.height() / h)
    dw, dh = w * k, h * k
    p.drawPixmap(QRectF(r.center().x() - dw / 2, r.center().y() - dh / 2, dw, dh), pm, QRectF(0, 0, w, h))
    p.restore()


def draw_check(p: QPainter, box: QRectF, state: int, dpr: float) -> None:
    """state: 0 off, 1 on, 2 some."""
    on = state > 0
    p.setPen(QPen(theme.c("ink") if on else theme.c("line2"), 1.5))
    p.setBrush(theme.c("ink") if on else Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(box, 6, 6)
    if state == 1:
        pm = icon_pixmap("check", theme.c("on_ink"), 12, dpr)
        p.drawPixmap(QRectF(box.x() + 3, box.y() + 3, 12, 12), pm, QRectF(pm.rect()))
    elif state == 2:
        p.setPen(QPen(theme.c("on_ink"), 2, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(box.x() + 5, box.center().y()), QPointF(box.right() - 5, box.center().y()))


class CheckAll(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = 0
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_state(self, s: int):
        self.state = s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_check(p, QRectF(2, 2, 18, 18), self.state, self.devicePixelRatioF())


class TrackRow(QWidget):
    """One track: check, cover, name + meta, status. Click = pick only this one; ctrl / the box = add; shift = range."""
    clicked = Signal(int, object)          # item id, Qt.KeyboardModifiers
    box_clicked = Signal(int)

    H = 58

    def __init__(self, item: Item, pixmaps, parent=None):
        super().__init__(parent)
        self.item = item
        self.pixmaps = pixmaps               # callable(item) -> (QPixmap | None, fit, pad)
        self.setFixedHeight(self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover = False
        self.drop = False
        self.flash = 0.0

    def sizeHint(self):
        return QSize(400, self.H)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.rect().contains(e.position().toPoint()):
            return
        if e.position().x() < 40:
            self.box_clicked.emit(self.item.id)
        else:
            self.clicked.emit(self.item.id, e.modifiers())

    def _status(self) -> tuple[str, QColor] | None:
        it = self.item
        if it.track.error:
            return t("st_err"), QColor("#e59a86")
        if it.err:
            return it.err[:40], QColor("#e59a86")
        if it.dirty:
            return t("st_dirty"), theme.c("tint")
        if it.saved:
            return t("st_saved"), QColor("#8fd19e")
        if not it.has_cover:
            return t("st_nocover"), theme.c("faint")
        return None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        it = self.item
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if it.sel or self._hover or self.drop:
            p.setPen(QPen(theme.c("tint"), 1.4) if self.drop else Qt.PenStyle.NoPen)
            p.setBrush(theme.c("panel2") if it.sel else theme.c("panel"))
            p.drawRoundedRect(r, 12, 12)
        draw_check(p, QRectF(13, r.center().y() - 9, 18, 18), 1 if it.sel else 0, self.devicePixelRatioF())
        pm, fit, pad = self.pixmaps(it)
        cv = QRectF(44, r.center().y() - 20, 40, 40)
        paint_cover(p, cv, pm, fit, pad, 8)
        st = self._status()
        right = 12.0
        if st:
            p.setFont(font(8.2, QFont.Weight.Bold))
            sw = p.fontMetrics().horizontalAdvance(st[0]) + 4
            p.setPen(st[1])
            p.drawText(QRectF(r.right() - sw - 10, r.top(), sw, r.height() / 2 + 6),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, st[0])
            right = sw + 18
        if it.source:
            p.setFont(font(7.8, QFont.Weight.DemiBold))
            src = t("st_from", a=it.source)
            sw2 = p.fontMetrics().horizontalAdvance(src) + 4
            p.setPen(theme.c("faint"))
            p.drawText(QRectF(r.right() - sw2 - 10, r.center().y() + 2, sw2, r.height() / 2 - 4),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, src)
            right = max(right, sw2 + 18)
        x = 96.0
        avail = r.width() - x - right
        name = it.display_name()
        p.setFont(font(9.8, QFont.Weight.Bold))
        tag = "" if it.tags.get("title") else t("fn_tag")
        tag_w = 0
        if tag:
            p.setFont(font(7.6, QFont.Weight.Bold))
            tag_w = p.fontMetrics().horizontalAdvance(tag) + 14
            p.setFont(font(9.8, QFont.Weight.Bold))
        text = p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, int(max(40, avail - tag_w)))
        p.setPen(theme.c("text"))
        top = QRectF(x, r.top() + 9, avail, 20)
        p.drawText(top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if tag:
            tw = p.fontMetrics().horizontalAdvance(text)
            p.setFont(font(7.6, QFont.Weight.Bold))
            tr = QRectF(x + tw + 8, top.center().y() - 8, tag_w - 4, 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("panel3"))
            p.drawRoundedRect(tr, 5, 5)
            p.setPen(theme.c("muted"))
            p.drawText(tr, Qt.AlignmentFlag.AlignCenter, tag)
        bits = [it.tags.get("artist") or t("no_artist"), it.tags.get("album") or "", it.track.fmt.upper(),
                short(it.track.duration) if it.track.duration else "", fmt_size(it.track.size)]
        meta = " · ".join(b for b in bits if b)
        p.setFont(font(8.6))
        p.setPen(mix(theme.c("muted"), theme.c("faint"), 0.2))
        p.drawText(QRectF(x, r.top() + 29, avail, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(meta, Qt.TextElideMode.ElideRight, int(avail)))


class BigCover(QAbstractButton):
    """The preview in the panel; also a drop target for a picture. Shows up to 3 when the picked tracks differ."""

    def __init__(self, pixmaps, parent=None):
        super().__init__(parent)
        self.pixmaps = pixmaps
        self.items: list[Item] = []
        self.over = False
        self.setFixedSize(132, 132)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_items(self, items: list[Item]):
        self.items = items
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        looks = []
        for it in self.items:
            pm, fit, pad = self.pixmaps(it)
            key = (pm.cacheKey() if pm else 0, fit, pad)
            if key not in [k for k, _ in looks]:
                looks.append((key, (pm, fit, pad)))
        if len(looks) <= 1:
            pm, fit, pad = looks[0][1] if looks else (None, "crop", "blur")
            paint_cover(p, r, pm, fit, pad, 14)
        else:
            n = min(3, len(looks))
            s = r.width() * 0.62
            for i in range(n - 1, -1, -1):
                off = i * (r.width() - s) / max(1, n - 1)
                pm, fit, pad = looks[i][1]
                cr = QRectF(r.x() + off, r.y() + off * 0.5, s, s)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.c("win"))
                p.drawRoundedRect(cr.adjusted(-2, -2, 2, 2), 12, 12)
                paint_cover(p, cr, pm, fit, pad, 10)
            p.setFont(font(8, QFont.Weight.Bold))
            p.setPen(theme.c("muted"))
            p.drawText(QRectF(r.x(), r.bottom() - 18, r.width(), 18), Qt.AlignmentFlag.AlignCenter,
                       t("mixed", n=len(self.items)))
        if self.over or self.underMouse():
            pen = QPen(theme.c("tint") if self.over else theme.c("line2"), 1.6, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, 90) if self.over else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 14, 14)
            if self.over:
                p.setFont(font(10, QFont.Weight.ExtraBold))
                p.setPen(QColor("#ffffff"))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, t("drop_here"))

    def enterEvent(self, e):
        self.update()

    def leaveEvent(self, e):
        self.update()
