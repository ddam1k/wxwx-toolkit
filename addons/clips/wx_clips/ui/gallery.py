"""Home of the add-on: new clips, game folders (sortable), or a big drop zone when no NVIDIA folder is set."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..core.i18n import clips_n, fmt_mb, pl, t
from ..core.library import ClipFile, GameFolder
from .common import SmoothScroll, TabRow, badge, button, draw_cover, fade_change, label, pixmap, rounded, short, text_w, when
from .theme import HAIR_BLACK, HAIR_WHITE, font, theme
from .widgets import DropZone, FlowLayout, Segmented, Switch, animate, icon_pixmap, mix

CARD_W = 214
THUMB_H = round(CARD_W * 9 / 16)


# ---------------------------------------------------------------- one clip card
class ClipCard(QWidget):
    clicked = Signal(str)
    double = Signal(str)

    def __init__(self, ctx, clip: ClipFile, in_folder: bool, delay: int = 0):
        super().__init__()
        self.ctx, self.clip, self.in_folder = ctx, clip, in_folder
        self.setFixedSize(CARD_W, THUMB_H + 54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._h = 0.0
        self._scrub = -1.0
        self._in = 0.0
        QTimer.singleShot(delay, self._start_in)

    def _set_in(self, v):
        self._in = float(v)
        self.update()

    def _start_in(self):
        animate(self, 0, 1, 400, self._set_in)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 260, self._set_h)
        self.ctx.frames(self.clip.path)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 260, self._set_h)
        self._scrub = -1
        self.update()

    def mouseMoveEvent(self, e):
        x = e.position().x()
        self._scrub = max(0.0, min(0.999, x / self.width())) if e.position().y() < THUMB_H + 4 else -1
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.clip.path)

    def mouseDoubleClickEvent(self, e):
        self.double.emit(self.clip.path)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._in)
        lift = 3 * self._h + 8 * (1 - self._in)
        p.translate(0, 3 - lift)
        c = self.clip
        picked = c.path in self.ctx.picks
        done = c.path in self.ctx.done
        is_open = c.path in self.ctx.open_set()
        info = self.ctx.info(c.path)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 4)
        p.setPen(QPen(theme.c("ink") if picked else mix(theme.c("line"), theme.c("line2"), self._h), 2 if picked else 1))
        p.setBrush(theme.c("panel"))
        p.drawRoundedRect(r, 14, 14)
        th = QRectF(1, 1, self.width() - 2, THUMB_H)
        frames = self.ctx.frames(c.path) if self._scrub >= 0 else []
        src = frames[int(self._scrub * len(frames))] if frames else self.ctx.thumb(c.path)
        pm = pixmap(src)
        if done:
            p.setOpacity(self._in * 0.55)
        draw_cover(p, th, pm, 13, top_only=True)
        p.setOpacity(self._in)
        if self._scrub >= 0:
            p.fillRect(QRectF(th.left(), th.bottom() - 3, th.width() * self._scrub, 3), theme.c("tint"))
        # tag
        tag = (t("tag_done"), QColor("#6fcf97")) if done else (t("tag_open"), QColor(241, 239, 234, 235)) if is_open \
            else (t("tag_new"), theme.c("tint")) if c.path in self.ctx.new_set else None
        if tag:
            f = font(7, QFont.Weight.ExtraBold)
            w = text_w(tag[0], f) + 12
            badge(p, QRectF(th.right() - w - 7, th.top() + 7, w, 16), tag[0], tag[1], QColor("#141416"), 7,
                  QFont.Weight.ExtraBold)
        # duration
        if info:
            f = font(7.4, QFont.Weight.Bold, mono=True)
            txt = short(info.duration)
            w = text_w(txt, f) + 12
            badge(p, QRectF(th.right() - w - 7, th.bottom() - 24, w, 16), txt, QColor(0, 0, 0, 160), QColor("#fff"),
                  7.4, QFont.Weight.Bold, mono=True)
        # check circle
        k = 1.0 if picked else self._h
        if k > 0.01:
            p.setOpacity(self._in * k)
            cc = QPointF(th.left() + 19, th.top() + 19)
            p.setPen(QPen(theme.c("ink") if picked else QColor(255, 255, 255, 215), 2))
            p.setBrush(theme.c("ink") if picked else QColor(0, 0, 0, 70))
            p.drawEllipse(cc, 10, 10)
            if picked:
                p.drawPixmap(QPointF(cc.x() - 7, cc.y() - 7), icon_pixmap("check", theme.c("on_ink"), 14, self.devicePixelRatioF()))
            p.setOpacity(self._in)
        # texts
        title = when(c.mtime) if self.in_folder else c.game
        sub = (short(info.duration) if info else "…") if self.in_folder else when(c.mtime)
        sub = f"{sub} · {fmt_mb(c.size / 1048576)}"
        if self.in_folder and not c.folder:
            sub = c.name
        p.setPen(theme.c("text"))
        p.setFont(font(9.6, QFont.Weight.Bold))
        p.drawText(QRectF(11, th.bottom() + 7, self.width() - 22, 20), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                   p.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, self.width() - 22))
        p.setPen(theme.c("faint"))
        p.setFont(font(8.2))
        p.drawText(QRectF(11, th.bottom() + 26, self.width() - 22, 16), Qt.AlignmentFlag.AlignVCenter,
                   p.fontMetrics().elidedText(sub, Qt.TextElideMode.ElideRight, self.width() - 22))


# ---------------------------------------------------------------- folders list
COLS = (62, 0, 70, 104, 140, 22)   # cover, name (flex), clips, size, latest, chevron
GAP, PADX = 14, 12


def col_rects(w: float, h: float) -> list[QRectF]:
    fixed = sum(c for c in COLS if c) + GAP * (len(COLS) - 1) + PADX * 2
    name_w = max(80.0, w - fixed)
    x, out = PADX, []
    for c in COLS:
        cw = c or name_w
        out.append(QRectF(x, 0, cw, h))
        x += cw + GAP
    return out


class FolderHeader(QWidget):
    sort = Signal(str)
    KEYS = (None, "name", "count", "size", "date", None)

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        for r, k in zip(col_rects(self.width(), self.height()), self.KEYS):
            if k and r.contains(e.position()):
                self.sort.emit(k)

    def paintEvent(self, _):
        p = QPainter(self)
        rects = col_rects(self.width(), self.height())
        names = (None, t("col_game"), t("col_count"), t("col_size"), t("col_last"), None)
        f = font(7.4, QFont.Weight.ExtraBold)
        for r, k, n in zip(rects, self.KEYS, names):
            if not n:
                continue
            on = self.ctx.fsort[0] == k
            txt = n + ("  ▲" if on and self.ctx.fsort[1] > 0 else "  ▼" if on else "")
            p.setFont(f)
            p.setPen(theme.c("text") if on else theme.c("faint"))
            al = Qt.AlignmentFlag.AlignLeft if k == "name" else Qt.AlignmentFlag.AlignRight
            p.drawText(r.adjusted(0, 0, 0, -8), al | Qt.AlignmentFlag.AlignVCenter, txt)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), theme.c("line"))


class FolderRow(QWidget):
    clicked = Signal(object)

    def __init__(self, ctx, folder: GameFolder, delay: int = 0):
        super().__init__()
        self.ctx, self.folder = ctx, folder
        self.setFixedHeight(52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._h = 0.0
        self._in = 0.0
        QTimer.singleShot(delay, self._start_in)

    def _set_in(self, v):
        self._in = float(v)
        self.update()

    def _start_in(self):
        animate(self, 0, 1, 400, self._set_in)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def enterEvent(self, e):
        animate(self, self._h, 1, 180, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 220, self._set_h)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.folder)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._in * (0.75 if self.folder.root else 1))
        p.translate(0, 6 * (1 - self._in))
        f = self.folder
        bg = theme.c("panel")
        bg.setAlpha(round(bg.alpha() * self._h))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        rects = col_rects(self.width(), self.height())
        cov = QRectF(rects[0].x(), 8, 62, 36)
        if self.ctx.folder_previews:
            back = cov.translated(4 + 2 * self._h, -3 - 2 * self._h)
            p.setBrush(theme.c("panel3"))
            p.drawRoundedRect(back, 7, 7)
            first = f.clips[0].path if f.clips else None
            draw_cover(p, cov.translated(-2 * self._h, self._h), pixmap(self.ctx.thumb(first)) if first else None, 7)
        else:
            tile = QRectF(cov.center().x() - 18, cov.center().y() - 18, 36, 36)
            p.setBrush(mix(theme.c("panel2"), theme.c("panel3"), self._h))
            p.drawRoundedRect(tile, 10, 10)
            p.save()
            p.translate(tile.center())
            p.rotate(-6 * self._h)
            p.drawPixmap(QPointF(-10, -10), icon_pixmap("folder", mix(theme.c("muted"), theme.c("tint"), self._h), 20,
                                                        self.devicePixelRatioF()))
            p.restore()
        # name + pills
        nr = rects[1]
        fn = font(10, QFont.Weight.Bold)
        name = t("root_files") if f.root else f.name
        p.setFont(fn)
        p.setPen(theme.c("muted") if f.root else theme.c("text"))
        new_n = sum(1 for c in f.clips if c.path in self.ctx.new_set)
        picked = sum(1 for c in f.clips if c.path in self.ctx.picks)
        extra = (text_w(f"{new_n} NEW", font(7, QFont.Weight.ExtraBold)) + 20 if new_n else 0) + \
                (text_w(f"✓ {picked}", font(7.4, QFont.Weight.ExtraBold)) + 20 if picked else 0)
        shown = p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, int(nr.width() - extra))
        p.drawText(nr, Qt.AlignmentFlag.AlignVCenter, shown)
        x = nr.x() + text_w(shown, fn) + 8
        if new_n:
            b = badge(p, QRectF(x, nr.center().y() - 8, 0, 16), f"{new_n} NEW", theme.c("tint"), QColor("#141416"), 7,
                      QFont.Weight.ExtraBold)
            x = b.right() + 6
        if picked:
            badge(p, QRectF(x, nr.center().y() - 8, 0, 16), f"✓ {picked}", theme.c("ink"), theme.c("on_ink"), 7.4,
                  QFont.Weight.ExtraBold)
        mono = font(8.8, QFont.Weight.DemiBold, mono=True)
        p.setFont(mono)
        p.setPen(theme.c("muted"))
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        p.drawText(rects[2], right, str(f.count))
        p.drawText(rects[3], right, fmt_mb(f.size / 1048576))
        p.setFont(font(8.8, QFont.Weight.DemiBold))
        p.setPen(theme.c("faint"))
        p.drawText(rects[4], right, when(f.last) if f.last else "—")
        ch = rects[5]
        p.drawPixmap(QPointF(ch.x() + 3 + 3 * self._h, ch.center().y() - 8),
                     icon_pixmap("chev", mix(theme.c("faint"), theme.c("text"), self._h), 16, self.devicePixelRatioF()))


# ---------------------------------------------------------------- no folder yet
class BigDrop(QWidget):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(520, 260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._h = 0.0
        self._f = 0.0
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(40)

    def _tick(self):
        self._f = (self._f + 0.01) % 1
        self.update()

    def _set_h(self, v):
        self._h = float(v)

    def enterEvent(self, e):
        animate(self, self._h, 1, 220, self._set_h)

    def leaveEvent(self, e):
        animate(self, self._h, 0, 260, self._set_h)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = theme.c("panel")
        bg.setAlpha(round(bg.alpha() * self._h))
        p.setBrush(bg)
        pen = QPen(mix(theme.c("line2"), theme.c("muted"), self._h), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.drawRoundedRect(r, 22, 22)
        dy = -6 * math.sin(self._f * 2 * math.pi)
        tile = QRectF(r.center().x() - 36, 44 + dy, 72, 72)
        p.save()
        p.translate(tile.center())
        p.rotate(-3 * math.sin(self._f * 2 * math.pi))
        p.translate(-tile.center())
        g = QLinearGradient(tile.topLeft(), tile.bottomRight())
        g.setColorAt(0, QColor(HAIR_BLACK))
        g.setColorAt(0.4999, QColor(HAIR_BLACK))
        g.setColorAt(0.5, QColor(HAIR_WHITE))
        g.setColorAt(1, QColor(HAIR_WHITE))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(tile, 20, 20)
        inner = QRectF(tile.center().x() - 23, tile.center().y() - 23, 46, 46)
        p.setBrush(theme.c("win"))
        p.drawRoundedRect(inner, 14, 14)
        p.drawPixmap(QPointF(inner.center().x() - 12, inner.center().y() - 12),
                     icon_pixmap("clips", theme.c("text"), 24, self.devicePixelRatioF()))
        p.restore()
        p.setPen(theme.c("text"))
        p.setFont(font(14, QFont.Weight.ExtraBold))
        p.drawText(QRectF(0, 140, self.width(), 30), Qt.AlignmentFlag.AlignCenter, t("drop_t"))
        p.setPen(theme.c("muted"))
        p.setFont(font(9.6))
        p.drawText(QRectF(0, 172, self.width(), 22), Qt.AlignmentFlag.AlignCenter, t("drop_s"))


class MiniThumbs(QWidget):
    def __init__(self, paths: list[str], ctx):
        super().__init__()
        self.paths, self.ctx = paths[:4], ctx
        self.setFixedSize(58 + 42 * max(0, len(self.paths) - 1), 38)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, path in enumerate(self.paths):
            r = QRectF(i * 42, 2, 58, 34)
            p.setPen(QPen(theme.c("panel"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            draw_cover(p, r, pixmap(self.ctx.thumb(path)), 7)
            p.drawRoundedRect(r, 7, 7)


# ---------------------------------------------------------------- the home view
class HomeView(QWidget):
    open_paths = Signal(list)
    resume = Signal()
    pick_files = Signal()
    open_settings = Signal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.tab = "new"
        self.folder: GameFolder | None = None
        self.in_sort = "new"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = SmoothScroll()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)
        self.cards: list[QWidget] = []
        self.render()

    # -------------------------------------------- building
    def render(self):
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(28, 24, 28, 28)
        col.setSpacing(0)
        self.cards = []
        ctx = self.ctx
        # header
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(4)
        tv.addWidget(label(t("title"), "h1"))
        if ctx.nv_dir:
            line = QHBoxLayout()
            line.setSpacing(6)
            ic = QWidget()
            ic.setFixedSize(16, 16)
            ic.paintEvent = lambda _e, w=ic: QPainter(w).drawPixmap(0, 0, icon_pixmap("nvidia", theme.c("tint"), 16, w.devicePixelRatioF()))
            line.addWidget(ic)
            line.addWidget(label(t("nv_folder"), "sub"))
            line.addWidget(label(ctx.nv_dir, "monoPath"))
            ch = button(t("change_lc"), "link")
            ch.clicked.connect(self.open_settings)
            line.addWidget(ch)
            line.addStretch()
            tv.addLayout(line)
        else:
            tv.addWidget(label(t("sub_nofolder"), "sub"))
        head.addLayout(tv, 1)
        self.unpick = button(t("unpick"), "ghost")
        self.unpick.clicked.connect(self._unpick)
        self.open_btn = button("", "accent")
        self.open_btn.clicked.connect(self._open_picked)
        head.addWidget(self.unpick, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        col.addLayout(head)
        # resume banner
        if ctx.session_paths():
            col.addSpacing(18)
            col.addWidget(self._resume_row())
        if not ctx.nv_dir:
            self.unpick.hide()
            self.open_btn.hide()
            col.addSpacing(40)
            big = BigDrop()
            big.clicked.connect(self.pick_files)
            col.addWidget(big, 0, Qt.AlignmentFlag.AlignHCenter)
            col.addSpacing(14)
            col.addWidget(self._tip_row(), 0, Qt.AlignmentFlag.AlignHCenter)
            col.addStretch()
            self._set_body(body)
            return
        # tabs
        col.addSpacing(18)
        self.tabs = TabRow()
        self.tabs.add("new", t("tab_new")).set_count(len(ctx.new_list))
        self.tabs.add("folders", t("tab_folders")).set_count(sum(1 for f in ctx.folders if not f.root), tint=False)
        self.tabs.select(self.tab, animated=False)
        self.tabs.changed.connect(self._tab)
        self.tabs.tabs["folders"].clicked.connect(lambda: self._up() if self.tab == "folders" and self.folder else None)
        col.addWidget(self.tabs)
        if ctx.state == "scanning" and not ctx.folders:
            col.addSpacing(30)
            col.addWidget(label(t("scanning"), "empty"), 0, Qt.AlignmentFlag.AlignHCenter)
        elif ctx.state == "missing":
            col.addSpacing(30)
            col.addWidget(label(t("folder_missing", p=ctx.nv_dir), "empty"), 0, Qt.AlignmentFlag.AlignHCenter)
        elif self.tab == "new":
            self._new_tab(col)
        elif self.folder is None:
            self._folders_tab(col)
        else:
            self._folder_detail(col)
        col.addStretch()
        self._set_body(body)
        self.sync_pick()

    def _set_body(self, body):
        pos = self.scroll.verticalScrollBar().value()
        self.scroll.setWidget(body)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(pos))

    def _resume_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("row")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 10, 12, 10)
        lay.setSpacing(14)
        lay.addWidget(MiniThumbs(self.ctx.session_paths(), self.ctx))
        tv = QVBoxLayout()
        tv.setSpacing(1)
        tv.addWidget(label(t("resume_t", n=clips_n(len(self.ctx.session_paths()))), "rowTitle"))
        tv.addWidget(label(t("resume_s"), "rowSub"))
        lay.addLayout(tv, 1)
        b = button(t("resume_btn"), "accent")
        b.clicked.connect(self.resume)
        lay.addWidget(b)
        return row

    def _tip_row(self) -> QWidget:
        row = QFrame()
        row.setObjectName("row")
        row.setFixedWidth(520)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(12)
        ic = QWidget()
        ic.setFixedSize(22, 22)
        ic.paintEvent = lambda _e, w=ic: QPainter(w).drawPixmap(0, 0, icon_pixmap("nvidia", theme.c("tint"), 22, w.devicePixelRatioF()))
        lay.addWidget(ic)
        tv = QVBoxLayout()
        tv.setSpacing(1)
        tv.addWidget(label(t("tip_t"), "rowTitle"))
        tv.addWidget(label(t("tip_s"), "rowSub", wrap=True))
        lay.addLayout(tv, 1)
        b = button(t("tip_btn"), "accent")
        b.clicked.connect(self.open_settings)
        lay.addWidget(b)
        return row

    def _grid(self, col, clips: list[ClipFile], in_folder: bool):
        box = QWidget()
        flow = FlowLayout(box, 14)
        for i, c in enumerate(clips):
            card = ClipCard(self.ctx, c, in_folder, delay=min(i, 12) * 35)
            card.clicked.connect(self._card_click)
            card.double.connect(lambda p: self.open_paths.emit([p]))
            flow.addWidget(card)
            self.cards.append(card)
        col.addWidget(box)

    def _section(self, col, title_widget: QWidget, right: QWidget | None = None):
        row = QHBoxLayout()
        row.addWidget(title_widget)
        row.addStretch()
        if right is not None:
            row.addWidget(right)
        col.addLayout(row)
        col.addSpacing(12)

    def _new_tab(self, col):
        ctx = self.ctx
        col.addSpacing(18)
        n = len(ctx.new_list)
        kind = {"day": "since_day", "week": "since_week"}.get(ctx.new_range, "since_last")
        head = label(f"{pl(n, 'новый клип', 'новых клипа', 'новых клипов', 'new clip', 'new clips')}"
                     f"  <span style='font-size:9pt;font-weight:600;color:{theme.p['faint']}'>{t(kind)}</span>"
                     if n else t("no_new"), "h3")
        head.setTextFormat(Qt.TextFormat.RichText)
        sel = button("", "ghost")
        sel.setText(t("unselect_all") if n and all(c.path in ctx.picks for c in ctx.new_list) else t("select_all"))
        sel.clicked.connect(lambda: self._pick_all(ctx.new_list))
        sel.setVisible(bool(n))
        self._section(col, head, sel)
        self.sel_btn = sel
        self._grid(col, ctx.new_list, False)
        col.addSpacing(22)
        dz = DropZone()
        dz.texts = (t("not_nv_t"), "", t("not_nv_s"))
        dz.clicked.connect(self.pick_files)
        col.addWidget(dz)

    def _folders_tab(self, col):
        ctx = self.ctx
        col.addSpacing(16)
        games = [f for f in ctx.folders if not f.root]
        w = t("folders_w")
        fw = pl(len(games), *w, "folder", "folders") if True else ""
        top = QHBoxLayout()
        top.addWidget(label(t("folders_sum", f=fw, c=clips_n(sum(f.count for f in ctx.folders)),
                              size=fmt_mb(sum(f.size for f in ctx.folders) / 1048576)), "hint"))
        top.addStretch()
        top.addWidget(label(t("folder_previews"), "hint"))
        sw = Switch()
        sw.set_now(ctx.folder_previews)
        sw.toggled.connect(lambda on: QTimer.singleShot(300, lambda: ctx.set_folder_previews(on)))
        top.addWidget(sw)
        col.addLayout(top)
        col.addSpacing(10)
        hdr = FolderHeader(ctx)
        hdr.sort.connect(self._sort)
        col.addWidget(hdr)
        col.addSpacing(4)
        k, d = ctx.fsort
        key = {"name": lambda f: f.name.lower(), "count": lambda f: f.count, "size": lambda f: f.size,
               "date": lambda f: f.last}[k]
        rows = sorted(games, key=key, reverse=d < 0) + [f for f in ctx.folders if f.root]
        for i, f in enumerate(rows):
            r = FolderRow(ctx, f, delay=min(i, 16) * 22)
            r.clicked.connect(self._open_folder)
            col.addWidget(r)
            col.addSpacing(2)
            self.cards.append(r)

    def _folder_detail(self, col):
        f = self.folder
        col.addSpacing(16)
        crumb = QHBoxLayout()
        crumb.setSpacing(8)
        up = button("‹  " + t("all_games"), "ghost")
        up.clicked.connect(self._up)
        crumb.addWidget(up)
        crumb.addWidget(label("/", "faintBig"))
        crumb.addWidget(label(t("root_files") if f.root else f.name, "h3"))
        crumb.addWidget(label(f"{clips_n(f.count)} · {fmt_mb(f.size / 1048576)}", "hint"))
        crumb.addStretch()
        col.addLayout(crumb)
        col.addSpacing(12)
        seg = Segmented([("new", t("sort_new"), ""), ("old", t("sort_old"), ""), ("big", t("sort_big"), "")])
        seg.setFixedWidth(400)
        seg.set_value(self.in_sort, animated=False)
        seg.changed.connect(self._in_sort)
        sel = button("", "ghost")
        sel.setText(t("unselect_all") if all(c.path in self.ctx.picks for c in f.clips) else t("select_all"))
        sel.clicked.connect(lambda: self._pick_all(f.clips))
        self.sel_btn = sel
        self._section(col, seg, sel)
        clips = sorted(f.clips, key=(lambda c: c.size) if self.in_sort == "big" else (lambda c: c.mtime),
                       reverse=self.in_sort != "old")
        if not clips:
            col.addWidget(label(t("folder_empty"), "empty"))
        self._grid(col, clips, True)

    # -------------------------------------------- actions
    def _top(self) -> int:
        try:
            from PySide6.QtCore import QPoint
            return self.tabs.mapTo(self.scroll.viewport(), QPoint(0, self.tabs.height())).y()
        except (RuntimeError, AttributeError):
            return 0

    def _fade(self, dx: float, ms: int = 340):
        fade_change(self.scroll.viewport(), self.render, ms, dx, top=self._top())

    def _tab(self, key):
        self.tab = key
        self._fade(-48 if key == "folders" else 48)

    def _up(self):
        self.folder = None
        self._fade(48)

    def _open_folder(self, f):
        self.folder = f

        def go():
            self.render()
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(0))
        fade_change(self.scroll.viewport(), go, 340, -48, top=self._top())

    def _sort(self, k):
        cur, d = self.ctx.fsort
        self.ctx.fsort = (k, -d) if cur == k else (k, 1 if k == "name" else -1)
        self._fade(0, 240)

    def _in_sort(self, v):
        self.in_sort = v
        self._fade(0, 240)

    def _card_click(self, path):
        ctx = self.ctx
        if path in ctx.open_set() and not ctx.picks:
            self.open_paths.emit([path])
            return
        ctx.picks.symmetric_difference_update({path})
        self.sync_pick()

    def _pick_all(self, clips):
        ctx = self.ctx
        paths = {c.path for c in clips}
        if paths <= ctx.picks:
            ctx.picks -= paths
        else:
            ctx.picks |= paths
        self.sync_pick()

    def _unpick(self):
        self.ctx.picks.clear()
        self.sync_pick()

    def _open_picked(self):
        if self.ctx.picks:
            self.open_paths.emit(sorted(self.ctx.picks, key=lambda p: -self.ctx.mtime(p)))

    def sync_pick(self):
        n = len(self.ctx.picks)
        if hasattr(self, "open_btn"):
            self.open_btn.setText(t("open_n", n=clips_n(n)) if n else t("pick"))
            self.open_btn.setEnabled(bool(n))
            self.unpick.setVisible(bool(n) and bool(self.ctx.nv_dir))
        sb = getattr(self, "sel_btn", None)
        if sb is not None:
            try:
                group = self.folder.clips if (self.tab == "folders" and self.folder) else self.ctx.new_list
                sb.setText(t("unselect_all") if group and all(c.path in self.ctx.picks for c in group) else t("select_all"))
            except RuntimeError:
                pass
        self.repaint_cards()

    def repaint_cards(self):
        for c in self.cards:
            try:
                c.update()
            except RuntimeError:
                pass
