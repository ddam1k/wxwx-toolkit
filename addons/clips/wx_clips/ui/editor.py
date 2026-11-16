"""The cutting screen: film strip, player, timeline and the two-step panel (cutting → compress & save)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFileDialog, QFrame, QHBoxLayout, QLineEdit, QScrollArea,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from ..core import encode
from ..core.encode import out_folder, plan_clip
from ..core.i18n import clips_n, files_n, fmt_mb, segs_n, t
from ..core.runner import ClipJob
from ..core.session import Clip
from ..core.settings import GPU_ENCODERS, EncodeSettings
from .common import SEGC, IconButton, badge, button, draw_cover, label, parse_t, pixmap, short, tcode, text_w, when
from .player import Player, PlayerView
from .theme import font, theme
from .timeline import Timeline
from .widgets import (Chip, FlowLayout, Led, ProgressButton, SectionHeader, Segmented, SwitchRow, animate,
                      icon_pixmap, mix)

PANEL_W = 368


# ================================================================ film strip
class StripCard(QWidget):
    picked = Signal(int)
    removed = Signal(int)

    def __init__(self, ctx, index: int):
        super().__init__()
        self.ctx, self.index = ctx, index
        self.setFixedSize(134, 112)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._h = 0.0
        self._in = 0.0
        QTimer.singleShot(index * 40, lambda: animate(self, 0, 1, 380, self._set_in))

    def _set_in(self, v):
        self._in = float(v)
        self.update()

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 200, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 240, self._set_h)

    def _x_rect(self) -> QRectF:
        return QRectF(self.width() - 27, 5, 22, 22)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._h > 0.5 and self._x_rect().contains(e.position()):
            self.removed.emit(self.index)
        else:
            self.picked.emit(self.index)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._in)
        c: Clip = self.ctx.clips[self.index]
        on = self.index == self.ctx.cur
        p.translate(0, 2 - 2 * self._h)
        r = QRectF(1, 1, self.width() - 2, self.height() - 5)
        p.setPen(QPen(theme.c("ink"), 2) if on else QPen(mix(theme.c("line"), theme.c("line2"), self._h), 1))
        p.setBrush(theme.c("panel"))
        p.drawRoundedRect(r, 12, 12)
        th = QRectF(2, 2, self.width() - 4, 70)
        draw_cover(p, th, pixmap(c.thumb), 11, top_only=True)
        if c.dur:
            k = c.kept()
            tr = c.trimmed()
            txt = (f"{short(k)} / " if tr else "") + short(c.dur)
            f = font(7, QFont.Weight.Bold, mono=True)
            w = text_w(txt, f) + 12
            badge(p, QRectF(th.right() - w - 5, th.bottom() - 20, 0, 0), txt, QColor(0, 0, 0, 160), QColor("#fff"), 7,
                  QFont.Weight.Bold, mono=True)
            if tr:
                lbl = f"✂ {len(c.multi)} · {short(k)}" if c.mode == "multi" else f"✂ {short(k)}"
                badge(p, QRectF(th.left() + 5, th.top() + 5, 0, 0), lbl, theme.c("ink"), theme.c("on_ink"), 7,
                      QFont.Weight.ExtraBold)
        if c.status == "done":
            p.fillRect(th, QColor(17, 17, 19, 140))
            p.drawPixmap(QPointF(th.center().x() - 12, th.center().y() - 12), icon_pixmap("check", QColor("#fff"), 24, self.devicePixelRatioF()))
        if c.status == "error":
            p.fillRect(th, QColor(120, 30, 40, 120))
        if c.progress > 0 and c.status in ("work", "done"):
            p.fillRect(QRectF(th.left(), th.bottom() - 3, th.width() * c.progress, 3), theme.c("tint"))
        if self._h > 0.01 and c.status != "work":
            p.setOpacity(self._in * self._h)
            xr = self._x_rect()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(xr, 7, 7)
            p.drawPixmap(QPointF(xr.left() + 4, xr.top() + 4), icon_pixmap("x", QColor("#fff"), 14, self.devicePixelRatioF()))
            p.setOpacity(self._in)
        game = self.ctx.game(c.path)
        p.setPen(theme.c("text"))
        p.setFont(font(8.4, QFont.Weight.Bold))
        p.drawText(QRectF(9, th.bottom() + 4, self.width() - 18, 16), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(game, Qt.TextElideMode.ElideRight, self.width() - 18))
        p.setPen(theme.c("faint"))
        p.setFont(font(7.4))
        sub = f"{when(os.path.getmtime(c.path)) if os.path.exists(c.path) else ''} · {fmt_mb(os.path.getsize(c.path) / 1048576) if os.path.exists(c.path) else ''}"
        p.drawText(QRectF(9, th.bottom() + 19, self.width() - 18, 14), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(sub, Qt.TextElideMode.ElideRight, self.width() - 18))


class AddCard(QWidget):
    clicked = Signal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFixedSize(134, 112)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._h = 0.0

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 200, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 240, self._set_h)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 3, self.width() - 2, self.height() - 7)
        pen = QPen(mix(theme.c("line2"), theme.c("muted"), self._h), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 12, 12)
        tile = QRectF(r.center().x() - 14, 18, 28, 28)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel2"))
        p.drawRoundedRect(tile, 9, 9)
        p.drawPixmap(QPointF(tile.left() + 7, tile.top() + 7), icon_pixmap("plus", mix(theme.c("muted"), theme.c("text"), self._h), 14, self.devicePixelRatioF()))
        p.setPen(mix(theme.c("muted"), theme.c("text"), self._h))
        p.setFont(font(8.6, QFont.Weight.Bold))
        p.drawText(QRectF(0, 52, self.width(), 16), Qt.AlignmentFlag.AlignCenter, t("add"))
        p.setPen(theme.c("faint"))
        p.setFont(font(7.4))
        p.drawText(QRectF(0, 68, self.width(), 30), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   t("add_sub") if self.ctx.nv_dir else t("add_sub_nf"))


# ================================================================ small controls
class PlayButton(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.playing = False

    def paintEvent(self, _):
        from PySide6.QtGui import QPolygonF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("ink"))
        p.drawEllipse(QRectF(self.rect()))
        p.setBrush(theme.c("on_ink"))
        c = QRectF(self.rect()).center()
        if self.playing:
            p.drawRoundedRect(QRectF(c.x() - 6, c.y() - 7, 4.4, 14), 1.2, 1.2)
            p.drawRoundedRect(QRectF(c.x() + 1.6, c.y() - 7, 4.4, 14), 1.2, 1.2)
        else:
            p.drawPolygon(QPolygonF([QPointF(c.x() - 4.5, c.y() - 7.5), QPointF(c.x() - 4.5, c.y() + 7.5), QPointF(c.x() + 8, c.y())]))


class KeyButton(QAbstractButton):
    """'Начало [I]'."""

    def __init__(self, text: str, key: str):
        super().__init__()
        self.setText(text)
        self.key = key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self._h = 0.0

    def sizeHint(self):
        return QSize(int(text_w(self.text(), font(9, QFont.Weight.Bold)) + 42), 32)

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
        bg = theme.c("panel2")
        bg.setAlpha(round(bg.alpha() * self._h))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), 9, 9)
        f = font(9, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(mix(theme.c("muted"), theme.c("text"), self._h))
        tw = text_w(self.text(), f)
        p.drawText(QRectF(10, 0, tw + 2, 32), Qt.AlignmentFlag.AlignVCenter, self.text())
        kr = QRectF(10 + tw + 7, 8, 16, 16)
        p.setPen(QPen(theme.c("line2"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(kr, 4, 4)
        p.setPen(theme.c("faint"))
        p.setFont(font(7.4, QFont.Weight.ExtraBold, mono=True))
        p.drawText(kr, Qt.AlignmentFlag.AlignCenter, self.key)


class LenPill(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setToolTip(t("playcut_tip"))
        self.value = "00:00.00"
        self._bump = 0.0

    def set_value(self, v: str):
        if v != self.value:
            self.value = v
            animate(self, 1, 0, 300, self._set_bump)
            self.updateGeometry()

    def _set_bump(self, v):
        self._bump = float(v)
        self.update()

    def sizeHint(self):
        return QSize(int(text_w(self.value, font(9.4, QFont.Weight.ExtraBold, mono=True)) + 44), 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = 1 + 0.08 * self._bump
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(k, k)
        p.translate(-self.width() / 2, -self.height() / 2)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("ink"))
        p.drawRoundedRect(r, 9, 9)
        p.drawPixmap(QPointF(r.left() + 9, r.center().y() - 6), icon_pixmap("play", theme.c("on_ink"), 12, self.devicePixelRatioF()))
        p.setPen(theme.c("on_ink"))
        p.setFont(font(9.4, QFont.Weight.ExtraBold, mono=True))
        p.drawText(r.adjusted(26, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, self.value)


class ModeCard(QAbstractButton):
    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(92)
        self._h = 0.0

    def nextCheckState(self):
        pass

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 300, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 300, self._set_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(theme.c("ink"), 2) if on else QPen(mix(theme.c("line2"), theme.c("muted"), self._h), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 13, 13)
        title, sub = (t("mode_single"), t("mode_single_s")) if self.mode == "single" else (t("mode_multi"), t("mode_multi_s"))
        p.setPen(theme.c("text"))
        p.setFont(font(9.8, QFont.Weight.ExtraBold))
        p.drawText(QRectF(13, 10, r.width() - 20, 20), Qt.AlignmentFlag.AlignVCenter, title)
        p.setPen(theme.c("faint"))
        p.setFont(font(8))
        p.drawText(QRectF(13, 30, r.width() - 22, 32), Qt.TextFlag.TextWordWrap, sub)
        bar = QRectF(13, r.bottom() - 22, r.width() - 26, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.c("panel2"))
        p.drawRoundedRect(bar, 4, 4)
        p.setOpacity(1 if on else 0.55)
        sh = 4 * self._h
        if self.mode == "single":
            p.setBrush(theme.c("ink"))
            p.drawRoundedRect(QRectF(bar.left() + bar.width() * 0.3 + sh, bar.top(), bar.width() * 0.38, bar.height()), 3, 3)
        else:
            for (a, w, c), d in zip(((0.06, 0.2, 0), (0.38, 0.14, 1), (0.64, 0.26, 2)), (1, -1, 1)):
                p.setBrush(QColor(SEGC[c]))
                p.drawRoundedRect(QRectF(bar.left() + bar.width() * a + sh * d, bar.top(), bar.width() * w, bar.height()), 3, 3)


class TimeBox(QFrame):
    edited = Signal(float)

    def __init__(self, title: str, readonly: bool = False):
        super().__init__()
        self.setObjectName("timeBox")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(1)
        self.title = label(title, "tbTitle")
        lay.addWidget(self.title)
        self.edit = QLineEdit()
        self.edit.setObjectName("tbEdit" if not readonly else "tbEditRo")
        self.edit.setReadOnly(readonly)
        self.edit.editingFinished.connect(self._done)
        lay.addWidget(self.edit)

    def _done(self):
        v = parse_t(self.edit.text())
        if v is not None:
            self.edited.emit(v)

    def set_value(self, s: float):
        if not self.edit.hasFocus():
            self.edit.setText(tcode(s))


class SegRow(QWidget):
    play = Signal(int)
    pick = Signal(int)
    edit = Signal(int)
    delete = Signal(int)
    typed = Signal(int, str, float)

    def __init__(self, ctx, clip: Clip, i: int):
        super().__init__()
        self.ctx, self.clip, self.i = ctx, clip, i
        s = clip.multi[i]
        self.color = QColor(SEGC[s.col % len(SEGC)])
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 6, 6)
        lay.setSpacing(8)
        self.pl = IconButton("play", 28, 13)
        self.pl.fill = self.color
        self.pl.clicked.connect(lambda: self.play.emit(self.i))
        lay.addWidget(self.pl)
        mid = QVBoxLayout()
        mid.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(2)
        num = label(str(i + 1), "segNum")
        num.setStyleSheet(f"color:{self.color.name()}")
        top.addWidget(num)
        top.addSpacing(4)
        self.ea, self.eb = QLineEdit(tcode(s.a)), QLineEdit(tcode(s.b))
        for e, which in ((self.ea, "a"), (self.eb, "b")):
            e.setObjectName("segTime")
            e.setFixedWidth(78)
            e.editingFinished.connect(lambda e=e, w=which: self._typed(e, w))
            e.installEventFilter(self)
        top.addWidget(self.ea)
        top.addWidget(label("–", "faint"))
        top.addWidget(self.eb)
        top.addStretch()
        mid.addLayout(top)
        secs = f"{s.length:.2f}"
        mid.addWidget(label(t("seg_sub", s=secs.replace(".", ",") if t("t_len") == "ДЛИНА" else secs,
                              f=round(s.length * clip.fps)), "segSub"))
        lay.addLayout(mid, 1)
        self.ed = IconButton("pencil", 28, 14, "✎")
        self.ed.clicked.connect(lambda: self.edit.emit(self.i))
        self.x = IconButton("x", 28, 13, "Del")
        self.x.clicked.connect(lambda: self.delete.emit(self.i))
        if clip.edit is s:
            self.ed.fill = self.color
        lay.addWidget(self.ed)
        lay.addWidget(self.x)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.FocusIn:
            self.pick.emit(self.i)
        return False

    def _typed(self, e: QLineEdit, which: str):
        v = parse_t(e.text())
        if v is None:
            self.ctx.toast(t("time_bad"))
            e.setText(tcode(getattr(self.clip.multi[self.i], which)) if self.i < len(self.clip.multi) else "")
            return
        self.typed.emit(self.i, which, v)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.pick.emit(self.i)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.clip
        s = c.multi[self.i] if self.i < len(c.multi) else None
        sel = self.i == c.sel
        editing = s is not None and s is c.edit
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        bg = mix(theme.c("panel2"), self.color, 0.16 if editing else 0.1 if sel else 0)
        pen = QPen(self.color if (sel or editing) else Qt.GlobalColor.transparent, 1.2)
        if editing:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 11, 11)


class KeepBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self.clip: Clip | None = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 3, 3)
        p.setClipPath(path)
        p.fillRect(r, theme.c("panel2"))
        c = self.clip
        if not c or not c.dur:
            return
        x = 0.0
        for s in c.multi:
            w = r.width() * s.length / c.dur
            p.fillRect(QRectF(x, 0, w, r.height()), QColor(SEGC[s.col % len(SEGC)]))
            x += w


class StepButton(QAbstractButton):
    def __init__(self, n: int):
        super().__init__()
        self.n = n
        self.state = "todo"         # on | done | todo
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)

    def sizeHint(self):
        return QSize(int(text_w(self.text(), font(9.2, QFont.Weight.Bold)) + 36), 30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QRectF(1, 3, 24, 24)
        on = self.state == "on"
        p.setPen(QPen(theme.c("ink") if on else theme.c("panel2") if self.state == "done" else theme.c("line2"), 1.5))
        p.setBrush(theme.c("ink") if on else theme.c("panel2") if self.state == "done" else Qt.BrushStyle.NoBrush)
        p.drawEllipse(c)
        p.setPen(theme.c("on_ink") if on else theme.c("tint") if self.state == "done" else theme.c("faint"))
        p.setFont(font(8, QFont.Weight.ExtraBold))
        p.drawText(c, Qt.AlignmentFlag.AlignCenter, str(self.n))
        p.setPen(theme.c("text") if on else theme.c("faint"))
        p.setFont(font(9.2, QFont.Weight.Bold))
        p.drawText(QRectF(32, 0, self.width() - 32, 30), Qt.AlignmentFlag.AlignVCenter, self.text())


class StepLine(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)
        self.setMinimumWidth(18)
        self.k = 0.0

    def set_k(self, v):
        self.k = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        y = self.height() / 2 - 1
        p.fillRect(QRectF(0, y, self.width(), 2), theme.c("line2"))
        p.fillRect(QRectF(0, y, self.width() * self.k, 2), theme.c("ink"))


def block(*widgets_or_layouts) -> QWidget:
    w = QWidget()
    w.setObjectName("block")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 16, 0, 16)
    lay.setSpacing(10)
    for x in widgets_or_layouts:
        (lay.addLayout if isinstance(x, (QHBoxLayout, QVBoxLayout)) else lay.addWidget)(x)
    return w


# ================================================================ the editor
class EditorView(QWidget):
    go_home = Signal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.player = Player(self)
        self.player.frame.connect(lambda img: self.view.set_image(img))
        self.player.position.connect(self._on_pos)
        self.player.playing_changed.connect(self._on_playing)
        self.player.finished_ranges.connect(lambda: self._set_playing_label(""))
        self.step = 1
        self._strip_cards: list = []
        self._seg_rows: list = []
        self.jobs: list = []
        self.running = False
        self.stop_requested = False
        self._build()

    # ------------------------------------------------ layout
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(20, 16, 20, 12)
        lv.setSpacing(8)
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label(t("title"), "h1"))
        self.meta = label("", "sub")
        tv.addWidget(self.meta)
        head.addLayout(tv, 1)
        self.b_gallery = button(t("gallery"), "ghost")
        self.b_gallery.clicked.connect(self.go_home)
        self.b_clear = button(t("clear"), "ghost")
        self.b_clear.clicked.connect(self._clear)
        head.addWidget(self.b_gallery, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.b_clear, 0, Qt.AlignmentFlag.AlignBottom)
        lv.addLayout(head)
        self.strip_area = QScrollArea()
        self.strip_area.setWidgetResizable(True)
        self.strip_area.setFixedHeight(126)
        self.strip_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strip_area.setObjectName("strip")
        lv.addWidget(self.strip_area)
        self.view = PlayerView()
        self.view.clicked.connect(self._click_player)
        self.view.edit_done.connect(lambda: self._toggle_edit(None))
        lv.addWidget(self.view, 1)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        self.b_play = PlayButton()
        self.b_play.clicked.connect(self._toggle_play)
        ctrl.addWidget(self.b_play)
        self.tc = label("", "tc")
        self.tc.setTextFormat(Qt.TextFormat.RichText)
        ctrl.addSpacing(4)
        ctrl.addWidget(self.tc)
        ctrl.addSpacing(4)
        self.b_in = KeyButton(t("start"), "I")
        self.b_in.clicked.connect(self.key_in)
        self.b_out = KeyButton(t("end"), "O")
        self.b_out.clicked.connect(self.key_out)
        ctrl.addWidget(self.b_in)
        ctrl.addWidget(self.b_out)
        self.b_loop = IconButton("loop", 32, 16, t("loop_tip"))
        self.b_loop.clicked.connect(self._toggle_loop)
        ctrl.addWidget(self.b_loop)
        ctrl.addStretch()
        self.len_pill = LenPill()
        self.len_pill.clicked.connect(lambda: self.play_cut(all_segments=True))
        ctrl.addWidget(self.len_pill)
        lv.addLayout(ctrl)
        self.timeline = Timeline()
        self.timeline.seek.connect(self._scrub)
        self.timeline.cut_changed.connect(self._cut_live)
        self.timeline.cut_done.connect(self.changed)
        self.timeline.play_seg.connect(lambda i: self.play_cut(i))
        self.timeline.select_seg.connect(self._select_seg)
        self.timeline.scrubbing.connect(lambda on: (self.player.pause(), self.player.stop_ranges(), self._set_playing_label("")) if on else None)
        lv.addWidget(self.timeline)
        self.hint = label("", "hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lv.addWidget(self.hint)
        root.addWidget(left, 1)
        seam = QWidget()
        seam.setObjectName("seam")
        seam.setFixedWidth(1)
        root.addWidget(seam)
        root.addWidget(self._build_panel())

    def _build_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panelRight")
        panel.setFixedWidth(PANEL_W)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(0)
        sp = QWidget()
        sp.setObjectName("stepper")
        sl = QHBoxLayout(sp)
        sl.setContentsMargins(18, 12, 18, 12)
        sl.setSpacing(10)
        self.st1, self.st2 = StepButton(1), StepButton(2)
        self.st1.setText(t("step1"))
        self.st2.setText(t("step2"))
        self.st_line = StepLine()
        self.st1.clicked.connect(lambda: self.go_step(1))
        self.st2.clicked.connect(lambda: self.go_step(2))
        sl.addWidget(self.st1)
        sl.addWidget(self.st_line, 1)
        sl.addWidget(self.st2)
        pv.addWidget(sp)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._page1())
        self.pages.addWidget(self._page2())
        pv.addWidget(self.pages, 1)
        return panel

    def _scroll_page(self) -> tuple[QWidget, QVBoxLayout, QVBoxLayout]:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 0, 20, 6)
        bl.setSpacing(0)
        sc.setWidget(body)
        v.addWidget(sc, 1)
        foot = QWidget()
        foot.setObjectName("panelFooter")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(20, 14, 20, 14)
        fl.setSpacing(10)
        v.addWidget(foot)
        return page, bl, fl

    def _page1(self) -> QWidget:
        page, bl, fl = self._scroll_page()
        h = SectionHeader("scissors")
        h.title.setText(t("sec_how"))
        modes = QHBoxLayout()
        modes.setSpacing(8)
        self.mode_cards = {m: ModeCard(m) for m in ("single", "multi")}
        for m, card in self.mode_cards.items():
            card.clicked.connect(lambda _=False, m=m: self.set_mode(m))
            modes.addWidget(card)
        bl.addWidget(block(h, modes))
        # single
        h = SectionHeader("clock")
        h.title.setText(t("sec_cut"))
        b = h.add_action(t("reset"))
        b.clicked.connect(self._reset)
        b = h.add_action(t("apply_all"))
        b.clicked.connect(self._apply_all)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.tb_a, self.tb_b, self.tb_len = TimeBox(t("t_start")), TimeBox(t("t_end")), TimeBox(t("t_len"), True)
        self.tb_a.edited.connect(lambda v: self._type_single("a", v))
        self.tb_b.edited.connect(lambda v: self._type_single("b", v))
        for x in (self.tb_a, self.tb_b, self.tb_len):
            row.addWidget(x)
        self.box_single = block(h, row, label(t("note_single"), "note", wrap=True))
        bl.addWidget(self.box_single)
        # multi
        h = SectionHeader("segs")
        h.title.setText(t("sec_segs"))
        b = h.add_action(t("clear"))
        b.clicked.connect(self._clear_segs)
        self.seg_list = QVBoxLayout()
        self.seg_list.setSpacing(6)
        self.seg_empty = label(t("seg_empty"), "segEmpty")
        self.seg_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        srow = QHBoxLayout()
        srow.addWidget(label(t("type_hint"), "note"))
        srow.addStretch()
        tv = QVBoxLayout()
        tv.setSpacing(0)
        tl = label(t("total_lc"), "note")
        tl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.seg_total = label("", "segTotal")
        self.seg_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        tv.addWidget(tl)
        tv.addWidget(self.seg_total)
        srow.addLayout(tv)
        self.keepbar = KeepBar()
        note = label(t("note_multi"), "note", wrap=True)
        note.setTextFormat(Qt.TextFormat.RichText)
        self.box_multi = block(h, self.seg_list, self.seg_empty, srow, self.keepbar, note)
        bl.addWidget(self.box_multi)
        h = SectionHeader("merge")
        h.title.setText(t("sec_merge"))
        self.seg_merge = Segmented([("1", t("merge_one"), t("merge_one_s")), ("0", t("merge_sep"), t("merge_sep_s"))])
        self.seg_merge.changed.connect(self._merge)
        self.box_merge = block(h, self.seg_merge)
        bl.addWidget(self.box_merge)
        bl.addStretch()
        tr = QHBoxLayout()
        tr.addWidget(label(t("after_cut"), "totalLabel"))
        tr.addStretch()
        self.keep_total = label("", "totalValue")
        self.keep_total.setTextFormat(Qt.TextFormat.RichText)
        tr.addWidget(self.keep_total)
        fl.addLayout(tr)
        self.b_next = ProgressButton(t("next"), height=46, font_size=10.4, radius=12)
        self.b_next.clicked.connect(lambda: self.go_step(2))
        fl.addWidget(self.b_next)
        self.keep_sub = label("", "saveTo")
        self.keep_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.keep_sub.setTextFormat(Qt.TextFormat.RichText)
        fl.addWidget(self.keep_sub)
        return page

    def _page2(self) -> QWidget:
        page, bl, fl = self._scroll_page()
        h = SectionHeader("preset")
        h.title.setText(t("sec_comp"))
        self.chips_box = QWidget()
        self.chips_flow = FlowLayout(self.chips_box, 6)
        self.preset_note = label("", "note", wrap=True)
        enc = QHBoxLayout()
        enc.setSpacing(8)
        self.led = Led()
        self.gpu_text = label("", "gpuText", wrap=True)
        enc.addWidget(self.led, 0, Qt.AlignmentFlag.AlignTop)
        enc.addWidget(self.gpu_text, 1)
        self.seg_enc = Segmented([("gpu", t("enc_gpu"), t("enc_gpu_s")), ("cpu", t("enc_cpu"), t("enc_cpu_s"))])
        self.seg_enc.changed.connect(self._encoder)
        bl.addWidget(block(h, self.chips_box, self.preset_note, self.seg_enc, enc))
        h = SectionHeader("sound")
        h.title.setText(t("sec_sound"))
        self.track_for = h.add_action("")
        self.track_for.setEnabled(False)
        self.tracks_box = QVBoxLayout()
        self.tracks_box.setSpacing(2)
        bl.addWidget(block(h, self.tracks_box, label(t("sound_note"), "note", wrap=True)))
        h = SectionHeader("folder")
        h.title.setText(t("sec_dest"))
        self.sw_tk = SwitchRow()
        self.sw_tk.title.setText(t("same_tk"))
        self.sw_tk.sub.setText(t("same_tk_s"))
        self.sw_tk.toggled.connect(self._use_tk)
        self.seg_dest = Segmented([("beside", t("d_beside"), ""), ("subfolder", t("d_subfolder"), ""), ("custom", t("d_custom"), "")])
        self.seg_dest.changed.connect(self._dest_mode)
        self.dest_box = QFrame()
        self.dest_box.setObjectName("destBox")
        dl = QHBoxLayout(self.dest_box)
        dl.setContentsMargins(12, 10, 8, 10)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        self.dest_path = label("", "destPath")
        self.dest_sub = label("", "destSub")
        tv.addWidget(self.dest_path)
        tv.addWidget(self.dest_sub)
        dl.addLayout(tv, 1)
        self.b_dest_change = button(t("change"), "destBtn")
        self.b_dest_change.clicked.connect(self._pick_dir)
        self.b_dest_open = button(t("open"), "destBtn")
        self.b_dest_open.clicked.connect(self._open_dir)
        dl.addWidget(self.b_dest_change)
        dl.addWidget(self.b_dest_open)
        bl.addWidget(block(h, self.sw_tk, self.seg_dest, self.dest_box))
        bl.addStretch()
        tr = QHBoxLayout()
        tr.addWidget(label(t("total"), "totalLabel"))
        tr.addStretch()
        self.total = label("", "totalValue")
        self.total.setTextFormat(Qt.TextFormat.RichText)
        tr.addWidget(self.total)
        fl.addLayout(tr)
        self.b_go = ProgressButton("", height=46, font_size=10.4, radius=12)
        self.b_go.clicked.connect(self.export)
        fl.addWidget(self.b_go)
        self.saveto = label("", "saveTo")
        self.saveto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.saveto.setTextFormat(Qt.TextFormat.RichText)
        fl.addWidget(self.saveto)
        return page

    # ------------------------------------------------ state helpers
    @property
    def clip(self) -> Clip | None:
        c = self.ctx.clips
        return c[self.ctx.cur] if 0 <= self.ctx.cur < len(c) else None

    def toast(self, text: str):
        self.ctx.toast(text)

    def load_current(self, at: float | None = None):
        c = self.clip
        self.player.pause()
        self.player.stop_ranges()
        self._set_playing_label("")
        self.view.clear()
        if not c:
            return
        self.view.name = self.ctx.game(c.path)
        self.view.res = f"{c.info.width}×{c.info.height} · {c.info.fps:g} fps" if c.info else ""
        self.view.loading = True
        if c.info:
            start = at if at is not None else (c.segs()[0].a if c.segs() else 0.0)
            self.player.load(c.path, c.dur, start)
        self.timeline.set_clip(c)
        self.render()
        self.setFocus()

    def render(self):
        self.render_strip()
        self.render_side()
        self.render_totals()
        self.timeline.update()

    def changed(self):
        """Cut / segments changed: everything that shows them."""
        self.player.stop_ranges()
        self._set_playing_label("")
        self.render_side()
        self.render_totals()
        self.timeline.update()
        for w in self._strip_cards:
            w.update()

    # ------------------------------------------------ strip
    def render_strip(self):
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(2, 4, 2, 4)
        lay.setSpacing(10)
        self._strip_cards = []
        for i in range(len(self.ctx.clips)):
            card = StripCard(self.ctx, i)
            card.picked.connect(self.select)
            card.removed.connect(self._remove)
            lay.addWidget(card)
            self._strip_cards.append(card)
        add = AddCard(self.ctx)
        add.clicked.connect(lambda: self.go_home.emit() if self.ctx.nv_dir else self.ctx.pick_files())
        lay.addWidget(add)
        lay.addStretch()
        x = self.strip_area.horizontalScrollBar().value()
        self.strip_area.setWidget(box)
        QTimer.singleShot(0, lambda: self.strip_area.horizontalScrollBar().setValue(x))
        n = len(self.ctx.clips)
        self.meta.setText(f"{clips_n(n)} · {fmt_mb(sum(os.path.getsize(c.path) for c in self.ctx.clips if os.path.exists(c.path)) / 1048576)}")

    def select(self, i: int):
        if i == self.ctx.cur:
            return
        self.ctx.cur = i
        self.load_current()
        if 0 <= i < len(self._strip_cards):
            QTimer.singleShot(50, lambda: self.strip_area.ensureWidgetVisible(self._strip_cards[i], 40, 0))

    def _remove(self, i: int):
        if self.running:
            return
        self.ctx.remove_clip(i)
        if not self.ctx.clips:
            self.player.pause()
            self.go_home.emit()
            return
        self.load_current()

    def _clear(self):
        if self.running:
            return
        self.player.pause()
        self.ctx.clear_clips()
        self.go_home.emit()
        self.toast(t("cleared"))

    # ------------------------------------------------ player
    def _on_pos(self, s: float):
        self.timeline.set_pos(s)
        c = self.clip
        self.tc.setText(f"<b>{tcode(s)}</b> <span style='color:{theme.p['faint']}'>/ {tcode(c.dur if c else 0)}</span>")
        if self.player.ranges and c and c.mode == "multi" and len(self.player.ranges) > 1:
            k = next((i for i, x in enumerate(c.multi) if x.a - 0.02 <= s < x.b), -1)
            self._mark_playing(k)

    def _on_playing(self, on: bool):
        self.b_play.playing = on
        self.b_play.update()
        if not on:
            self._mark_playing(-1)

    def _toggle_play(self):
        if not self.player.playing:
            self.player.stop_ranges()
            self._set_playing_label("")
        self.player.toggle()
        self.view.flash(not self.player.playing)
        self.setFocus()

    def _click_player(self):
        self._toggle_play()

    def _toggle_loop(self):
        self.player.loop = not self.player.loop
        self.b_loop.active = self.player.loop
        self.b_loop.update()
        self.view.loop = self.player.loop
        self.view.update()

    def _scrub(self, s: float):
        self.player.seek(s)
        self.setFocus()

    def _set_playing_label(self, text: str):
        self.view.playing_label = text
        self.view.update()

    def _mark_playing(self, k: int):
        for w in self._seg_rows:
            try:
                w.pl.icon = "pause" if w.i == k else "play"
                w.pl.update()
            except RuntimeError:
                pass

    def play_cut(self, i: int | None = None, all_segments: bool = False):
        c = self.clip
        if not c or not c.info:
            return
        segs = c.segs()
        if not segs:
            self.toast(t("no_segs"))
            return
        if i is not None and 0 <= i < len(c.multi):
            if self.player.playing and self.player.ranges == [(c.multi[i].a, c.multi[i].b)]:
                self.player.pause()
                return
            c.sel, c.c_idx = i, i
            self.player.play_ranges([(c.multi[i].a, c.multi[i].b)])
            more = t("pl_next") if len(c.multi) > 1 else ""
            self._set_playing_label(t("pl_seg", n=i + 1) + more)
            self._mark_playing(i)
            self.timeline.update()
            self.render_seg_states()
        else:
            self.player.play_ranges(c.ranges())
            self._set_playing_label(t("pl_all") if c.mode == "multi" and len(segs) > 1 else t("pl_cut"))
        self.setFocus()

    # ------------------------------------------------ keys
    def key_in(self):
        c = self.clip
        if not c or not c.info:
            return
        r = c.key_in(self.player.t)
        if r == "pending":
            self.toast(t("key_pending"))
            self.timeline.update()
            return
        self.changed()

    def key_out(self):
        c = self.clip
        if not c or not c.info:
            return
        r = c.key_out(self.player.t)
        if r in ("too_short", "no_room"):
            self.toast(t(r))
            return
        self.changed()

    def _letter(self, e) -> str:
        vk = e.nativeVirtualKey()
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        ch = (e.text() or "").lower()
        return {"ш": "i", "щ": "o", "с": "c", "д": "l"}.get(ch, ch)

    def event(self, e):
        if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and not isinstance(self.focusWidget(), QLineEdit):
            n = len(self.ctx.clips)
            if n:
                back = e.key() == Qt.Key.Key_Backtab
                self.select((self.ctx.cur + (-1 if back else 1)) % n)
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        c = self.clip
        if not c:
            return super().keyPressEvent(e)
        k = e.key()
        ch = self._letter(e)
        shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if k == Qt.Key.Key_Space:
            self._toggle_play()
        elif ch == "i":
            self.key_in()
        elif ch == "o":
            self.key_out()
        elif ch == "c":
            if c.mode == "multi" and c.multi:
                self.play_cut(c.next_c())
            else:
                self.play_cut()
        elif ch == "l":
            self._toggle_loop()
        elif k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if c.mode == "multi":
                if c.pend is not None:
                    c.pend = None
                    self.timeline.update()
                else:
                    c.delete(c.sel)
                    self.changed()
        elif k == Qt.Key.Key_Escape:
            if c.edit is not None:
                self._toggle_edit(None)
            elif c.pend is not None:
                c.pend = None
                self.timeline.update()
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.player.pause()
            step = 1.0 if shift else 1.0 / max(c.fps, 1)
            self.player.seek(self.player.t + (step if k == Qt.Key.Key_Right else -step))
        elif k == Qt.Key.Key_Home:
            s = c.segs()
            self.player.seek(s[0].a if s else 0)
        elif k == Qt.Key.Key_End:
            s = c.segs()
            self.player.seek(s[-1].b if s else c.dur)
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------ step 1 actions
    def set_mode(self, m: str):
        c = self.clip
        if not c or not c.info or c.mode == m:
            return
        c.set_mode(m)
        self.changed()
        if m == "multi" and not c.multi:
            self.toast(t("multi_tip"))

    def _type_single(self, which: str, v: float):
        c = self.clip
        if not c or not c.single:
            return
        if not c.set_time(0, which, v):
            self.toast(t("clamped"))
        self.player.seek(getattr(c.single, which))
        self.changed()

    def _cut_live(self):
        c = self.clip
        if c and c.single:
            self.tb_a.set_value(c.single.a)
            self.tb_b.set_value(c.single.b)
            self.tb_len.set_value(c.single.length)
            self.len_pill.set_value(tcode(c.kept()))

    def _reset(self):
        c = self.clip
        if c and c.info:
            c.single.a, c.single.b = 0.0, c.dur
            self.changed()
            self.toast(t("reset_done"))

    def _apply_all(self):
        c = self.clip
        if not c or not c.single:
            return
        length = c.single.length
        for k in self.ctx.clips:
            if k is not c and k.info:
                k.mode = "single"
                a = min(c.single.a, max(0.0, k.dur - length))
                k.single.a, k.single.b = a, min(k.dur, a + length)
        self.changed()
        self.toast(t("applied_all", a=tcode(c.single.a), b=tcode(c.single.b)))

    def _clear_segs(self):
        c = self.clip
        if c:
            c.multi, c.pend, c.edit = [], None, None
            self.changed()
            self.toast(t("cleared_segs"))

    def _select_seg(self, i: int):
        c = self.clip
        if c:
            c.sel = i
            self.render_seg_states()
            self.timeline.update()

    def _pick_seg(self, i: int):
        c = self.clip
        if not c or i >= len(c.multi):
            return
        self.player.pause()
        self.player.stop_ranges()
        self._set_playing_label("")
        c.sel = i
        self.player.seek(c.multi[i].a)
        self.render_seg_states()
        self.timeline.update()

    def _toggle_edit(self, i: int | None):
        c = self.clip
        if not c:
            return
        if i is None:
            c.edit = None
        else:
            c.toggle_edit(i)
            if c.edit is not None:
                self.player.pause()
                self.player.seek(c.edit.a)
        self.changed()
        self.setFocus()

    def _typed(self, i: int, which: str, v: float):
        c = self.clip
        if not c or i >= len(c.multi):
            return
        if not c.set_time(i, which, v):
            self.toast(t("clamped"))
        self.player.seek(getattr(c.multi[c.sel], which))
        self.changed()

    def _delete_seg(self, i: int):
        c = self.clip
        if c:
            c.delete(i)
            self.changed()

    def _merge(self, v: str):
        c = self.clip
        if c:
            c.merge = v == "1"
            self.render_totals()

    # ------------------------------------------------ side panel rendering
    def render_side(self):
        c = self.clip
        if not c:
            return
        multi = c.mode == "multi"
        for m, card in self.mode_cards.items():
            card.setChecked(m == c.mode)
            card.update()
        self.box_single.setVisible(not multi)
        self.box_multi.setVisible(multi)
        self.box_merge.setVisible(multi and len(c.multi) > 1)
        self.seg_merge.set_value("1" if c.merge else "0", animated=False)
        self.hint.setText(t("hint_multi") if multi else t("hint_single"))
        if c.single and not multi:
            self.tb_a.set_value(c.single.a)
            self.tb_b.set_value(c.single.b)
            self.tb_len.set_value(c.single.length)
        self.len_pill.set_value(tcode(c.kept()))
        self.render_segments()
        self.render_edit_bar()
        if self.step == 2:
            self.render_step2()

    def render_segments(self):
        c = self.clip
        while self.seg_list.count():
            w = self.seg_list.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._seg_rows = []
        if not c or c.mode != "multi":
            return
        for i in range(len(c.multi)):
            row = SegRow(self.ctx, c, i)
            row.play.connect(lambda i: self.play_cut(i))
            row.pick.connect(self._pick_seg)
            row.edit.connect(self._toggle_edit)
            row.delete.connect(self._delete_seg)
            row.typed.connect(self._typed)
            self.seg_list.addWidget(row)
            self._seg_rows.append(row)
        self.seg_empty.setVisible(not c.multi)
        self.seg_total.setText(tcode(sum(s.length for s in c.multi)))
        self.keepbar.clip = c
        self.keepbar.update()

    def render_seg_states(self):
        for r in getattr(self, "_seg_rows", []):
            r.update()

    def render_edit_bar(self):
        c = self.clip
        if c and c.mode == "multi" and c.edit is not None and c.edit in c.multi:
            self.view.edit_text = t("edit_bar", n=c.multi.index(c.edit) + 1)
            self.view.edit_color = QColor(SEGC[c.edit.col % len(SEGC)])
        else:
            self.view.edit_text = ""
        self.view.update()

    def render_totals(self):
        clips = self.ctx.clips
        if not clips:
            return
        kept = sum(c.kept() for c in clips if c.info)
        dur = sum(c.dur for c in clips if c.info)
        files = sum(c.out_files() for c in clips)
        self.keep_total.setText(f"{short(kept)} <span style='font-size:9pt;color:{theme.p['tint']}'>{t('of', d=short(dur))}</span>")
        whole = sum(1 for c in clips if c.mode == "multi" and not c.multi)
        self.keep_sub.setText(t("files_line", c=clips_n(len(clips)), f=f"<b>{files_n(files)}</b>")
                              + (f"<span style='color:#d0a060'>{t('whole_line', n=whole)}</span>" if whole else ""))
        if self.step == 2:
            self.render_step2_totals()

    # ------------------------------------------------ step 2
    def go_step(self, n: int):
        if self.running:
            return
        self.step = n
        self.pages.setCurrentIndex(n - 1)
        w = self.pages.currentWidget()
        w.move(40 if n == 2 else -40, 0)
        animate(w, 40 if n == 2 else -40, 0, 420, lambda v: w.move(int(v), 0))
        self.st1.state = "on" if n == 1 else "done"
        self.st2.state = "on" if n == 2 else "todo"
        self.st1.update()
        self.st2.update()
        animate(self.st_line, self.st_line.k, 1 if n == 2 else 0, 500, self.st_line.set_k)
        if n == 2:
            self.player.pause()
            self.render_step2()

    def render_step2(self):
        ctx = self.ctx
        self.chips_flow.clear()
        self._chips = {}
        for pid, title, _values, own in ctx.presets():
            ch = Chip(title)
            ch.setChecked(pid == ctx.preset_id)
            ch.clicked.connect(lambda _=False, p=pid: self._preset(p))
            self.chips_flow.addWidget(ch)
            self._chips[pid] = ch
        self.preset_note.setText(ctx.preset_desc())
        gpu = ctx.gpu
        copy = ctx.preset_id == "none"
        self.seg_enc.setVisible(bool(gpu and gpu[0]) and not copy)
        self.led.setVisible(not (gpu and gpu[0]) and not copy)
        self.gpu_text.setVisible(not (gpu and gpu[0]) and not copy)
        if gpu is None:
            self.led.set_color("#8d8b95")
            self.gpu_text.setText(t("gpu_checking"))
        elif not gpu[0]:
            self.led.set_color("#d0a060")
            self.gpu_text.setText(t("gpu_none"))
        else:
            self.seg_enc.set_options([("gpu", f"{t('enc_gpu')}", gpu[1] or t("enc_gpu_s")), ("cpu", t("enc_cpu"), t("enc_cpu_s"))])
            self.seg_enc.set_value(ctx.encoder, animated=False)
        # tracks of the current clip
        while self.tracks_box.count():
            w = self.tracks_box.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        c = self.clip
        self.track_for.setText(self.ctx.game(c.path) if c else "")
        if c and c.info:
            names = c.info.audio_tracks
            if not names:
                self.tracks_box.addWidget(label(t("no_audio"), "note"))
            for i, nm in enumerate(names):
                row = SwitchRow()
                default = (t("track_game") if i == 0 else t("track_mic")) if len(names) == 2 else t("track_x")
                row.title.setText(nm or default)
                row.sub.setText(t("track_n", n=i + 1))
                row.switch.set_now(c.tracks[i])
                row.toggled.connect(lambda on, i=i: self._track(i, on))
                self.tracks_box.addWidget(row)
        self.sw_tk.switch.set_now(ctx.use_tk)
        self.seg_dest.setVisible(not ctx.use_tk)
        self.seg_dest.set_value(ctx.own_mode, animated=False)
        self.render_dest()
        self.render_step2_totals()

    def _preset(self, pid: str):
        self.ctx.set_preset(pid)
        for k, ch in self._chips.items():
            ch.setChecked(k == pid)
        self.render_step2()

    def _encoder(self, v: str):
        self.ctx.set_encoder(v)
        self.render_step2_totals()

    def _track(self, i: int, on: bool):
        c = self.clip
        if c and i < len(c.tracks):
            c.tracks[i] = on
            if not any(c.tracks):
                self.toast(t("muted"))
            self.render_step2_totals()

    def _use_tk(self, on: bool):
        self.ctx.set_dest(use_tk=on)
        self.seg_dest.setVisible(not on)
        self.render_dest()

    def _dest_mode(self, v: str):
        self.ctx.set_dest(own_mode=v)
        if v == "custom" and not self.ctx.own_dir:
            self._pick_dir()
        self.render_dest()

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, t("choose_folder"), self.ctx.own_dir or str(Path.home()))
        if d:
            self.ctx.set_dest(own_mode="custom", own_dir=os.path.normpath(d))
            self.seg_dest.set_value("custom")
        self.render_dest()

    def _open_dir(self):
        d = self.ctx.dest_dir()
        if d:
            os.makedirs(d, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def render_dest(self):
        ctx = self.ctx
        d = ctx.dest_dir()
        mode = "toolkit" if ctx.use_tk else ctx.own_mode
        self.dest_box.setVisible(mode in ("toolkit", "custom"))
        if mode == "toolkit":
            self.dest_path.setText(d or "—")
            self.dest_sub.setText(t("same_tk_s"))
            self.b_dest_change.hide()
        elif mode == "custom":
            self.dest_path.setText(d or t("d_custom_none"))
            self.dest_sub.setText(t("d_custom_s"))
            self.b_dest_change.show()
        self.b_dest_open.setVisible(bool(d))
        where = d if mode in ("toolkit", "custom") else (t("beside_orig") if mode == "beside" else t("subfolder_orig"))
        self.saveto.setText(f"<span style='color:{theme.p['muted']}'>{t('saveto')}</span>&nbsp; <b>{where or '—'}</b>")

    def render_step2_totals(self):
        clips = [c for c in self.ctx.clips if c.info]
        if not clips:
            return
        s = self.ctx.encode_settings()
        o = sum(c.info.size_mb for c in clips)
        e = sum(encode.estimate(c.info, c.ranges(), c.track_indexes(), s, c.merge or c.mode == "single") for c in clips)
        pct = max(0, round((1 - e / o) * 100)) if o else 0
        self.total.setText(f"{fmt_mb(o)} → ≈ {fmt_mb(e)} <span style='font-size:9pt;color:{theme.p['tint']}'>−{pct}%</span>")
        if not self.running:
            files = sum(c.out_files() for c in self.ctx.clips)
            self.b_go.setText(t("go_copy" if s is None else "go", f=files_n(files)))

    # ------------------------------------------------ export
    def export(self):
        if self.running:
            self.stop_requested = True
            for j in self.jobs:
                j.stop()
            return
        clips = [c for c in self.ctx.clips if c.info]
        if not clips:
            return
        self.player.pause()
        self.running = True
        self.stop_requested = False
        self.ctx.set_busy(True)
        for c in self.ctx.clips:
            c.status, c.progress, c.error = "queued", 0.0, ""
        self._reserved: set[str] = set()
        self._queue = [i for i, c in enumerate(self.ctx.clips) if c.info]
        self._n = len(self._queue)
        self._done_out: list[str] = []
        self._errors = 0
        self._mb_in = sum(c.info.size_mb for c in clips)
        self._next_job()

    def _next_job(self):
        if self.stop_requested or not self._queue:
            return self._finish()
        i = self._queue.pop(0)
        c = self.ctx.clips[i]
        c.status = "work"
        s = self.ctx.encode_settings()
        folder = Path(self.ctx.folder_for(c.path))
        tmp = Path(tempfile.gettempdir())
        try:
            plan = plan_clip(c.info, c.ranges() if c.trimmed() else [], c.track_indexes(), s,
                             c.merge or c.mode == "single", folder, tmp, self._reserved)
        except Exception as ex:
            c.status, c.error = "error", str(ex)
            self._errors += 1
            QTimer.singleShot(0, self._next_job)
            return
        job = ClipJob(plan, self)
        self.jobs = [job]
        k = self._n - len(self._queue)

        def prog(f, c=c, k=k):
            c.progress = f
            self.b_go.set_progress((k - 1 + f) / max(1, self._n))
            self.b_go.setText(t("stop", k=k, n=self._n))
            self._repaint_card(c)

        def fin(ok, err, c=c, plan=plan):
            c.status = "done" if ok else "error"
            c.error = err
            if ok:
                self._done_out += plan.outputs
            elif not self.stop_requested:
                self._errors += 1
                self.toast(t("failed", e=(err.strip().splitlines() or ["?"])[-1][:110]))
            self._repaint_card(c)
            QTimer.singleShot(0, self._next_job)

        job.progress.connect(prog)
        job.finished.connect(fin)
        job.start()
        self.b_go.setText(t("stop", k=k, n=self._n))
        self._repaint_card(c)

    def _repaint_card(self, c: Clip):
        try:
            i = self.ctx.clips.index(c)
            self._strip_cards[i].update()
        except (ValueError, IndexError, RuntimeError):
            pass

    def _finish(self):
        self.running = False
        self.jobs = []
        self.ctx.set_busy(False)
        self.b_go.set_progress(0)
        if self.stop_requested:
            self.toast(t("stopped"))
            for c in self.ctx.clips:
                if c.status in ("queued", "work"):
                    c.status, c.progress = "", 0.0
        else:
            self.ctx.mark_done([c.path for c in self.ctx.clips if c.status == "done"])
            mb = sum(os.path.getsize(p) for p in self._done_out if os.path.exists(p)) / 1048576
            if self._errors:
                self.toast(t("done_errors", n=self._errors))
            else:
                self.toast(t("done", f=files_n(len(self._done_out)), a=fmt_mb(self._mb_in), b=fmt_mb(mb)))
        self.render_step2_totals()
        for w in self._strip_cards:
            w.update()

    def is_busy(self) -> bool:
        return self.running

    def shutdown(self):
        self.stop_requested = True
        for j in self.jobs:
            j.stop()
        self.player.shutdown()
