"""The trim timeline: frame strip, dimmed cut-away parts, the cut or colored segments, playhead, ruler."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..core.session import Clip
from .common import SEGC, pixmap, short, tcode, text_w
from .theme import HAIR_BLACK, HAIR_WHITE, font, theme
from .widgets import animate

PAD = 20          # room for the handles of the single cut
TOP, STRIP_H = 40, 50
HANDLE_W = 18


class Timeline(QWidget):
    seek = Signal(float)             # user scrubs
    cut_changed = Signal()           # single cut handles moved (live)
    cut_done = Signal()              # … and released
    play_seg = Signal(int)
    select_seg = Signal(int)
    scrubbing = Signal(bool)
    released = Signal(str)          # what was dragged: a | b | seek

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clip: Clip | None = None
        self.pos = 0.0
        self.setFixedHeight(TOP + STRIP_H + 34)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = -1.0
        self._drag: str | None = None        # a | b | seek
        self._tags: list[tuple[QRectF, int]] = []
        self._tip: tuple[float, str] | None = None
        self._intro = 1.0
        self._pulse: dict[int, float] = {}

    def intro(self):
        self._intro = 0.0
        animate(self, 0, 1, 620, self._set_intro)

    def _set_intro(self, v):
        self._intro = float(v)
        self.update()

    def pulse(self, seg):
        key = id(seg)

        def step(v, k=key):
            self._pulse[k] = float(v)
            self.update()
        animate(self, 1, 0, 900, step)

    # ------------------------------------------------ geometry
    def track(self) -> QRectF:
        return QRectF(PAD, TOP, max(10.0, self.width() - 2 * PAD), STRIP_H)

    def X(self, s: float) -> float:
        r = self.track()
        d = self.clip.dur if self.clip and self.clip.dur else 1.0
        return r.left() + max(0.0, min(1.0, s / d)) * r.width()

    def T(self, x: float) -> float:
        r = self.track()
        d = self.clip.dur if self.clip and self.clip.dur else 0.0
        return max(0.0, min(d, (x - r.left()) / r.width() * d))

    def set_clip(self, clip: Clip | None):
        self.clip = clip
        self.update()

    def set_pos(self, t: float):
        if abs(t - self.pos) > 1e-4:
            self.pos = t
            self.update()

    # ------------------------------------------------ mouse
    def _handle_at(self, p: QPointF) -> str | None:
        c = self.clip
        if not c or c.mode != "single" or not c.single:
            return None
        if not (TOP - 6 <= p.y() <= TOP + STRIP_H + 6):
            return None
        xa, xb = self.X(c.single.a), self.X(c.single.b)
        if xa - HANDLE_W - 2 <= p.x() <= xa + 3:
            return "a"
        if xb - 3 <= p.x() <= xb + HANDLE_W + 2:
            return "b"
        return None

    def mousePressEvent(self, e):
        c = self.clip
        if not c or not c.dur or e.button() != Qt.MouseButton.LeftButton:
            return
        p = e.position()
        for r, i in self._tags:
            if r.contains(p):
                self.play_seg.emit(i)
                return
        h = self._handle_at(p)
        self.scrubbing.emit(True)
        if h:
            self._drag = h
            self._move(p.x())
            return
        self._drag = "seek"
        t = self.T(p.x())
        self.seek.emit(t)
        if c.mode == "multi":
            i = c.seg_at(t)
            if i >= 0 and i != c.sel:
                self.select_seg.emit(i)
        self._tip = (self.X(t), tcode(t))
        self.update()

    def mouseMoveEvent(self, e):
        p = e.position()
        self._hover = p.x()
        if self._drag:
            self._move(p.x())
        else:
            self.setCursor(Qt.CursorShape.SizeHorCursor if self._handle_at(p) else Qt.CursorShape.PointingHandCursor)
        self.update()

    def _move(self, x: float):
        c = self.clip
        t = self.T(x)
        if self._drag == "seek":
            self.seek.emit(t)
            self._tip = (self.X(t), tcode(t))
            return
        s = c.single
        if self._drag == "a":
            s.a = max(0.0, min(t, s.b - 0.5))
            v = s.a
        else:
            s.b = min(c.dur, max(t, s.a + 0.5))
            v = s.b
        self.seek.emit(v)
        self._tip = (self.X(v), tcode(v))
        self.cut_changed.emit()

    def mouseReleaseEvent(self, e):
        kind = self._drag
        if kind in ("a", "b"):
            self.cut_done.emit()
        if kind:
            self.scrubbing.emit(False)
            self.released.emit(kind)
        self._drag = None
        self._tip = None
        self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    # ------------------------------------------------ painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.clip
        r = self.track()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(r, 9, 9)
        if self._intro < 1:                       # the strip unrolls from the left
            from PySide6.QtCore import QRectF as _R
            reveal = QPainterPath()
            reveal.addRect(_R(r.left(), r.top() - 30, r.width() * self._intro, r.height() + 60))
            clip_path = clip_path.intersected(reveal)
        p.save()
        p.setClipPath(clip_path)
        p.fillRect(r, QColor("#000"))
        frames = c.frames if c else []
        if frames:
            n = len(frames)
            fw = r.width() / n
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            for i, f in enumerate(frames):
                pm = pixmap(f)
                if pm is None:
                    continue
                cell = QRectF(r.left() + i * fw, r.top(), fw + 0.6, r.height())
                k = max(cell.width() / pm.width(), cell.height() / pm.height())
                w, h = pm.width() * k, pm.height() * k
                p.drawPixmap(QRectF(cell.center().x() - w / 2, cell.center().y() - h / 2, w, h), pm,
                             QRectF(0, 0, pm.width(), pm.height()))
        else:
            p.fillRect(r, theme.c("panel2"))
        segs = c.segs() if c and c.dur else []
        dim = QColor(9, 9, 11, 184) if theme.dark else QColor(247, 245, 241, 200)
        if segs:
            pos, gaps = 0.0, []
            for s in sorted(segs, key=lambda x: x.a):
                if s.a > pos + 1e-3:
                    gaps.append((pos, s.a))
                pos = max(pos, s.b)
            if pos < c.dur - 1e-3:
                gaps.append((pos, c.dur))
            for a, b in gaps:
                p.fillRect(QRectF(self.X(a), r.top(), self.X(b) - self.X(a), r.height()), dim)
        p.restore()
        self._tags = []
        if c and c.dur:
            p.setOpacity(self._intro)
            if c.mode == "single" and c.single:
                self._paint_single(p, c, r)
            else:
                self._paint_multi(p, c, r)
            if c.mode == "multi" and c.pend is not None:
                x = self.X(c.pend)
                p.fillRect(QRectF(x - 1, r.top() - 8, 2, r.height() + 16), theme.c("tint"))
                f = font(7.2, QFont.Weight.ExtraBold)
                txt = "▸"
                br = QRectF(x + 1, r.top() - 9, text_w(txt, f) + 10, 15)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(theme.c("tint"))
                p.drawRoundedRect(br, 4, 4)
                p.setPen(QColor("#141416"))
                p.setFont(f)
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, txt)
            p.setOpacity(1)
            if c.mode == "multi" and not c.multi and c.pend is None:
                p.setPen(QColor(255, 255, 255, 230))
                p.setFont(font(9, QFont.Weight.Bold))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, "I  →  O")
        # hover line
        if self._hover >= r.left() and not self._drag:
            p.fillRect(QRectF(self._hover, r.top(), 1, r.height()), QColor(255, 255, 255, 110))
        # playhead
        if c and c.dur:
            x = self.X(self.pos)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            p.drawRect(QRectF(x - 1.5, r.top() - 10, 3, r.height() + 20))
            p.setBrush(QColor(HAIR_WHITE) if theme.dark else QColor(HAIR_BLACK))
            p.drawRect(QRectF(x - 1, r.top() - 10, 2, r.height() + 20))
            knob = QRectF(x - 7, r.top() - 17, 14, 14)
            p.setPen(QPen(theme.c("line2"), 1.5))
            p.setBrush(QColor(HAIR_WHITE))
            p.drawEllipse(knob)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(HAIR_BLACK))
            p.drawPie(knob, 90 * 16, 180 * 16)
        # ruler
        if c and c.dur:
            steps = [5, 10, 15, 30, 60, 120, 300, 600]
            st = next((s for s in steps if c.dur / s <= 8), 900)
            f = font(7.2, QFont.Weight.DemiBold, mono=True)
            p.setFont(f)
            v = 0.0
            while v <= c.dur + 0.01:
                x = self.X(v)
                p.fillRect(QRectF(x, r.bottom() + 6, 1, 4), theme.c("line2"))
                txt = short(v)
                p.setPen(theme.c("faint"))
                p.drawText(QRectF(x - 30, r.bottom() + 10, 60, 16), Qt.AlignmentFlag.AlignCenter, txt)
                v += st
        # tooltip while dragging
        if self._tip:
            x, txt = self._tip
            f = font(8, QFont.Weight.Bold, mono=True)
            w = text_w(txt, f) + 14
            br = QRectF(max(0, min(self.width() - w, x - w / 2)), 0, w, 0)
            br.setTop(r.top() - 1 - 20 - 13)
            br.setHeight(20)
            # keep it inside the widget: draw above the knob, clipped at top
            br.moveTop(max(0.0, r.top() - 36))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("ink"))
            p.drawRoundedRect(br, 6, 6)
            p.setPen(theme.c("on_ink"))
            p.setFont(f)
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, txt)

    def _paint_single(self, p: QPainter, c: Clip, r: QRectF):
        s = c.single
        xa, xb = self.X(s.a), self.X(s.b)
        ink, on = theme.c("ink"), theme.c("on_ink")
        glow = theme.c("tint", 90)
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            g = QColor(glow)
            g.setAlpha(30 - k * 9)
            p.setBrush(g)
            p.drawRoundedRect(QRectF(xa - 2 - 3 * k, r.top() - 5 - 3 * k, xb - xa + 4 + 6 * k, r.height() + 10 + 6 * k), 6, 6)
        p.setBrush(ink)
        p.drawRect(QRectF(xa, r.top() - 3, xb - xa, 3))
        p.drawRect(QRectF(xa, r.bottom(), xb - xa, 3))
        for x, left in ((xa, True), (xb, False)):
            hr = QRectF(x - HANDLE_W if left else x, r.top() - 5, HANDLE_W, r.height() + 10)
            path = QPainterPath()
            rad = 8
            path.addRoundedRect(hr, rad, rad)
            sq = QPainterPath()
            sq.addRect(QRectF(hr.right() - rad, hr.top(), rad, hr.height()) if left else QRectF(hr.left(), hr.top(), rad, hr.height()))
            p.setBrush(ink)
            p.drawPath(path.united(sq))
            p.setBrush(on)
            cx = hr.center().x()
            for dx in (-2.5, 2.5):
                p.drawRoundedRect(QRectF(cx + dx - 1, hr.center().y() - 10, 2, 20), 1, 1)

    def _paint_multi(self, p: QPainter, c: Clip, r: QRectF):
        editing = c.edit is not None
        for i, s in enumerate(c.multi):
            col = QColor(SEGC[s.col % len(SEGC)])
            xa, xb = self.X(s.a), self.X(s.b)
            sel = i == c.sel
            is_edit = s is c.edit
            p.save()
            if editing and not is_edit:
                p.setOpacity(0.45)
            fill = QColor(col)
            fill.setAlpha(26)
            seg_r = QRectF(xa, r.top() - 3, max(2.0, xb - xa), r.height() + 6)
            pu = self._pulse.get(id(s), 0.0)
            if pu > 0.01:
                for k in range(4):
                    g = QColor(col)
                    g.setAlpha(int((70 - k * 15) * pu))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(g)
                    grow = 3 + 4 * k + 10 * (1 - pu)
                    p.drawRoundedRect(seg_r.adjusted(-grow, -grow, grow, grow), 8, 8)
            if sel or is_edit:
                for k in range(3):
                    g = QColor(col)
                    g.setAlpha((40 if is_edit else 28) - k * 9)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(g)
                    p.drawRoundedRect(seg_r.adjusted(-2 - 3 * k, -2 - 3 * k, 2 + 3 * k, 2 + 3 * k), 6, 6)
            p.setPen(QPen(col, 3 if is_edit else 2.4))
            p.setBrush(fill)
            p.drawRoundedRect(seg_r, 4, 4)
            # number tag = play button
            f = font(7.2, QFont.Weight.ExtraBold)
            txt = f"▶ {i + 1}"
            tw = text_w(txt, f) + 10
            tag = QRectF(xa + 2, r.top() - 3, tw, 15)
            if xb - xa > tw + 4:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                path = QPainterPath()
                path.addRoundedRect(tag, 4, 4)
                p.drawPath(path)
                p.setPen(QColor("#141416"))
                p.setFont(f)
                p.drawText(tag, Qt.AlignmentFlag.AlignCenter, txt)
                self._tags.append((tag.adjusted(-2, -3, 2, 3), i))
            p.restore()
