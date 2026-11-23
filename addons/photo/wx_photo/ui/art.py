"""Painted pieces of Photo: a row of the list and the «было / стало» comparison."""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..core import opts
from ..core.engine import Result, Source
from ..core.i18n import fmt_size, t
from .theme import font, theme
from .widgets import ICONS, animate, icon_pixmap, mix

ICONS.update({
    "photo": '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
    "preset": '<path d="M4 6h10M4 12h16M4 18h7"/><circle cx="17" cy="6" r="2"/><circle cx="14" cy="18" r="2"/>',
    "format": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 14h6"/>',
    "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/>',
    "size": '<path d="M4 9V4h5M20 15v5h-5M4 4l7 7M20 20l-7-7"/>',
    "shield": '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/>',
    "zoom": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2M11 8v6M8 11h6"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
})

GREEN, RED = QColor("#8fd19e"), QColor("#e59a86")


@dataclass
class Item:
    id: int
    src: Source
    thumb: QPixmap | None = None
    st: str = "wait"               # wait | work | done | err
    progress: float = 0.0
    res: Result | None = None      # the estimate for res_key — real bytes, written as is on save
    res_key: tuple = field(default_factory=tuple)
    done_size: int = 0
    done_desc: str = ""
    out: str = ""
    err: str = ""


def rounded_pixmap(p: QPainter, r: QRectF, pm: QPixmap | None, radius: float, keep_bg: bool = False):
    p.save()
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    p.setClipPath(path)
    if pm is None or pm.isNull():
        if not keep_bg:
            p.fillRect(r, theme.c("panel2"))
    else:
        k = max(r.width() / pm.width(), r.height() / pm.height())
        w, h = pm.width() * k, pm.height() * k
        p.drawPixmap(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), pm, QRectF(pm.rect()))
    p.restore()


class PhotoRow(QWidget):
    compare = Signal(int)
    remove = Signal(int)
    H = 78

    def __init__(self, item: Item, o_getter, parent=None):
        super().__init__(parent)
        self.item = item
        self.o = o_getter                      # () -> Opts
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self._h = 0.0
        self._mouse = QPointF(-1, -1)

    def sizeHint(self):
        return QSize(500, self.H)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 200, self._set_h)

    def leaveEvent(self, e):
        self._mouse = QPointF(-1, -1)
        animate(self, self._h, 0, 220, self._set_h)

    def mouseMoveEvent(self, e):
        self._mouse = e.position()
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._thumb_rect().contains(self._mouse)
                       or self._x_rect().contains(self._mouse) else Qt.CursorShape.ArrowCursor)
        self.update()

    def _thumb_rect(self) -> QRectF:
        return QRectF(12, 9, 60, 60)

    def _x_rect(self) -> QRectF:
        return QRectF(self.width() - 34, (self.H - 24) / 2, 24, 24)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._h > 0.5 and self._x_rect().contains(e.position()) and self.item.st != "work":
            self.remove.emit(self.item.id)
        elif self._thumb_rect().contains(e.position()) and not self.item.src.error:
            self.compare.emit(self.item.id)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        it, s, o = self.item, self.item.src, self.o()
        r = QRectF(self.rect()).adjusted(1, 3, -1, -3)
        p.setPen(QPen(mix(theme.c("line"), theme.c("line2"), self._h), 1))
        p.setBrush(theme.c("panel"))
        p.drawRoundedRect(r, 14, 14)
        th = self._thumb_rect()
        if s.alpha:                                   # transparency shows as a checkerboard, like in editors
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(th, 10, 10)
            p.setClipPath(clip)
            p.fillRect(th, QColor("#e9e7e2"))
            for yy in range(0, 60, 10):
                for xx in range(0, 60, 10):
                    if (xx // 10 + yy // 10) % 2:
                        p.fillRect(QRectF(th.left() + xx, th.top() + yy, 10, 10), QColor("#c9c6bf"))
            p.restore()
        rounded_pixmap(p, th, it.thumb, 10, keep_bg=s.alpha)
        if it.st == "done":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(17, 17, 19, 150))
            p.drawRoundedRect(th, 10, 10)
            ic = icon_pixmap("check", QColor("#fff"), 22, self.devicePixelRatioF())
            p.drawPixmap(QPointF(th.center().x() - 11, th.center().y() - 11), ic)
        elif th.contains(self._mouse) and not s.error:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 120))
            p.drawRoundedRect(th, 10, 10)
            ic = icon_pixmap("zoom", QColor("#fff"), 20, self.devicePixelRatioF())
            p.drawPixmap(QPointF(th.center().x() - 10, th.center().y() - 10), ic)
        # right: size estimate
        right_w = 118
        er = QRectF(self.width() - right_w - 44, r.top() + 10, right_w, r.height() - 20)
        res = it.res if it.res_key == o.key() else None
        new_size = it.done_size if it.st == "done" else (len(res.data) if res else 0)
        if s.error:
            pass
        elif not new_size:
            p.setFont(font(8.2))
            p.setPen(theme.c("faint"))
            p.drawText(er, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, t("counting"))
        else:
            d = round((1 - new_size / max(1, s.size)) * 100)
            p.setFont(font(7.8, QFont.Weight.DemiBold))
            p.setPen(theme.c("faint"))
            p.drawText(QRectF(er.left(), er.top(), er.width(), 16), Qt.AlignmentFlag.AlignRight,
                       t("became") if it.st == "done" else t("will"))
            p.setFont(font(11, QFont.Weight.ExtraBold))
            p.setPen(theme.c("text"))
            p.drawText(QRectF(er.left(), er.top() + 14, er.width(), 22), Qt.AlignmentFlag.AlignRight, fmt_size(new_size))
            p.setFont(font(8.4, QFont.Weight.Bold))
            p.setPen(GREEN if d >= 0 else RED)
            p.drawText(QRectF(er.left(), er.top() + 36, er.width(), 16), Qt.AlignmentFlag.AlignRight,
                       (f"−{min(99, d)}%" if d >= 0 else f"+{-d}%"))
        # middle: name, meta, status
        x = th.right() + 14
        avail = er.left() - x - 12
        p.setFont(font(9.8, QFont.Weight.Bold))
        p.setPen(theme.c("text"))
        p.drawText(QRectF(x, r.top() + 8, avail, 20), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(s.path.replace("\\", "/").rsplit("/", 1)[-1], Qt.TextElideMode.ElideMiddle, int(avail)))
        p.setFont(font(8.4))
        p.setPen(theme.c("muted"))
        p.drawText(QRectF(x, r.top() + 28, avail, 18), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(self._meta(o), Qt.TextElideMode.ElideRight, int(avail)))
        st = {"wait": (t("st_wait"), theme.c("faint")), "work": (t("st_work"), theme.c("tint")),
              "done": (t("st_done", s=it.done_desc), GREEN), "err": (t("st_err", e=it.err[:80]), RED)}[it.st]
        if s.error:
            st = (t("unreadable"), RED)
        p.setFont(font(8, QFont.Weight.DemiBold))
        p.setPen(st[1])
        p.drawText(QRectF(x, r.top() + 46, avail, 16), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(st[0], Qt.TextElideMode.ElideRight, int(avail)))
        if it.st == "work":
            bar = QRectF(x, r.bottom() - 8, avail, 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("line"))
            p.drawRoundedRect(bar, 1.5, 1.5)
            p.setBrush(theme.c("tint"))
            p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * max(0.05, it.progress), 3), 1.5, 1.5)
        if self._h > 0.01 and it.st != "work":
            p.setOpacity(self._h)
            xr = self._x_rect()
            hot = xr.contains(self._mouse)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("panel3") if hot else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(xr, 8, 8)
            ic = icon_pixmap("x", theme.c("text") if hot else theme.c("muted"), 14, self.devicePixelRatioF())
            p.drawPixmap(QPointF(xr.left() + 5, xr.top() + 5), ic)

    def _meta(self, o) -> str:
        s = self.item.src
        if s.error:
            return fmt_size(s.size)
        w, h = opts.dims(s.w, s.h, o.long)
        src_f = opts.src_fmt(s.path).upper() if not opts.needs_ffmpeg(s.path) else s.path.rsplit(".", 1)[-1].upper()
        out_f = opts.out_fmt(s.path, o, s.alpha).upper()
        bits = [f"{s.w}×{s.h}" + (f" → {w}×{h}" if (w, h) != (s.w, s.h) else ""),
                src_f + (f" → {out_f}" if out_f != src_f else ""), fmt_size(s.size)]
        if s.gps:
            bits.append(t("geo") + " ✕" if o.strip else t("geo_keep"))
        return " · ".join(bits)


class CompareView(QWidget):
    """«Было / стало» over the list: drag to move the split, Z to zoom where the mouse is, Esc to close."""
    closed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.before: QImage | None = None
        self.after: QImage | None = None
        self.name = ""
        self.left_txt = ""
        self.right_txt = ""
        self.cut = 0.5
        self.zoom = False
        self.focus_pt = QPointF(0.5, 0.5)
        self._drag = False
        self._o = 0.0
        self.item_id = -1
        self.hide()

    # ------------------------------------------------------------ api
    def open(self, item_id: int, name: str, before: QImage | None, left_txt: str):
        self.item_id, self.name, self.before, self.left_txt = item_id, name, before, left_txt
        self.after, self.right_txt, self.cut, self.zoom = None, "…", 0.5, False
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.setFocus()
        animate(self, self._o, 1, 220, self._set_o)

    def set_before(self, img: QImage | None):
        self.before = img
        self.update()

    def set_after(self, img: QImage | None, txt: str):
        self.after, self.right_txt = img, txt
        self.update()

    def close_view(self):
        self.item_id = -1
        animate(self, self._o, 0, 180, self._set_o)
        self.closed.emit()

    def _set_o(self, v):
        self._o = float(v)
        self.update()
        if self._o <= 0.01 and self.item_id < 0:
            self.hide()

    # ------------------------------------------------------------ geometry
    def _stage(self) -> QRectF:
        return QRectF(self.rect()).adjusted(18, 56, -18, -42)

    def _rects(self) -> tuple[QRectF, QRectF] | None:
        """(where the picture is drawn, which part of the picture)."""
        img = self.before or self.after
        if img is None or img.isNull():
            return None
        st = self._stage()
        k = min(st.width() / img.width(), st.height() / img.height())
        if not self.zoom:
            w, h = img.width() * k, img.height() * k
            return QRectF(st.center().x() - w / 2, st.center().y() - h / 2, w, h), QRectF(0, 0, img.width(), img.height())
        z = max(1.0, k * 2.5)                                    # 1:1 pixels for big photos, ×2.5 for small ones
        sw, sh = min(img.width(), st.width() / z), min(img.height(), st.height() / z)
        cx = self.focus_pt.x() * img.width()
        cy = self.focus_pt.y() * img.height()
        sx = max(0.0, min(img.width() - sw, cx - sw / 2))
        sy = max(0.0, min(img.height() - sh, cy - sh / 2))
        dw, dh = sw * z, sh * z
        return QRectF(st.center().x() - dw / 2, st.center().y() - dh / 2, dw, dh), QRectF(sx, sy, sw, sh)

    # ------------------------------------------------------------ input
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close_view()
        elif e.key() == Qt.Key.Key_Z or e.text().lower() in ("z", "я"):
            self.zoom = not self.zoom
            self.update()
        else:
            super().keyPressEvent(e)

    def _close_rect(self) -> QRectF:
        return QRectF(self.width() - 110, 12, 92, 30)

    def _zoom_rect(self) -> QRectF:
        return QRectF(self.width() - 230, 12, 112, 30)

    def mousePressEvent(self, e):
        pos = e.position()
        if self._close_rect().contains(pos):
            self.close_view()
            return
        if self._zoom_rect().contains(pos):
            self.zoom = not self.zoom
            self.update()
            return
        self._drag = True
        self._move(pos)

    def mouseMoveEvent(self, e):
        if self._drag or self.zoom:
            self._move(e.position(), split=self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = False

    def _move(self, pos: QPointF, split: bool = True):
        rr = self._rects()
        if rr is None:
            return
        dst, _src = rr
        if split:
            self.cut = max(0.0, min(1.0, (pos.x() - dst.left()) / max(1.0, dst.width())))
        st = self._stage()
        if self.zoom:
            self.focus_pt = QPointF(max(0.0, min(1.0, (pos.x() - st.left()) / st.width())),
                                    max(0.0, min(1.0, (pos.y() - st.top()) / st.height())))
        self.update()

    # ------------------------------------------------------------ paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._o)
        p.fillRect(self.rect(), theme.c("win"))
        p.setFont(font(10.5, QFont.Weight.ExtraBold))
        p.setPen(theme.c("text"))
        p.drawText(QRectF(22, 12, self.width() - 280, 30), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(self.name, Qt.TextElideMode.ElideMiddle, self.width() - 280))
        for rect, txt, on in ((self._zoom_rect(), t("zoom"), self.zoom), (self._close_rect(), t("close"), False)):
            p.setPen(QPen(theme.c("line2"), 1))
            p.setBrush(theme.c("panel2") if on else theme.c("panel"))
            p.drawRoundedRect(rect, 10, 10)
            p.setFont(font(8.8, QFont.Weight.Bold))
            p.setPen(theme.c("text"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)
        rr = self._rects()
        st = self._stage()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel"))
        p.drawRoundedRect(st, 14, 14)
        if rr is not None:
            dst, src = rr
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, not self.zoom)
            xcut = dst.left() + dst.width() * self.cut
            if self.before is not None and not self.before.isNull():
                p.save()
                p.setClipRect(QRectF(dst.left(), dst.top(), xcut - dst.left(), dst.height()))
                p.drawImage(dst, self.before, src)
                p.restore()
            after = self.after if self.after is not None and not self.after.isNull() else None
            p.save()
            p.setClipRect(QRectF(xcut, dst.top(), dst.right() - xcut, dst.height()))
            if after is not None:
                # the result may be smaller (downsized): map the same part of the picture onto it
                kx, ky = after.width() / max(1, (self.before or after).width()), after.height() / max(1, (self.before or after).height())
                p.drawImage(dst, after, QRectF(src.left() * kx, src.top() * ky, src.width() * kx, src.height() * ky))
            else:
                p.fillRect(dst, QColor(0, 0, 0, 120))
            p.restore()
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawLine(QPointF(xcut, dst.top()), QPointF(xcut, dst.bottom()))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(xcut, dst.center().y()), 12, 12)
            p.setPen(QPen(QColor("#141416"), 2))
            cy = dst.center().y()
            p.drawLine(QPointF(xcut - 5, cy - 4), QPointF(xcut - 8, cy))
            p.drawLine(QPointF(xcut - 8, cy), QPointF(xcut - 5, cy + 4))
            p.drawLine(QPointF(xcut + 5, cy - 4), QPointF(xcut + 8, cy))
            p.drawLine(QPointF(xcut + 8, cy), QPointF(xcut + 5, cy + 4))
            self._label(p, QPointF(st.left() + 12, st.top() + 12), t("before"), self.left_txt, False)
            self._label(p, QPointF(st.right() - 12, st.top() + 12), t("after"), self.right_txt, True)
        p.setFont(font(8.2))
        p.setPen(theme.c("faint"))
        p.drawText(QRectF(18, self.height() - 34, self.width() - 36, 24), Qt.AlignmentFlag.AlignCenter,
                   p.fontMetrics().elidedText(t("cmp_hint"), Qt.TextElideMode.ElideRight, self.width() - 36))

    def _label(self, p: QPainter, at: QPointF, head: str, sub: str, right: bool):
        f1, f2 = font(9, QFont.Weight.ExtraBold), font(7.8, QFont.Weight.DemiBold)
        p.setFont(f2)
        w = max(p.fontMetrics().horizontalAdvance(sub), 40) + 20
        p.setFont(f1)
        w = max(w, p.fontMetrics().horizontalAdvance(head) + 20)
        r = QRectF(at.x() - w if right else at.x(), at.y(), w, 40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 170))
        p.drawRoundedRect(r, 9, 9)
        p.setPen(QColor("#ffffff"))
        p.drawText(r.adjusted(10, 4, -10, -20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, head)
        p.setFont(f2)
        p.setPen(QColor(255, 255, 255, 190))
        p.drawText(r.adjusted(10, 20, -10, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
