"""Rows of the «Сейчас» and «История» lists and the picks list of a playlist."""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..core import ytdlp
from ..core.i18n import fmt_size, t
from ..core.runner import Job
from ..kit.common import IconButton, label
from .art import Elide, Picture, site_color
from .theme import font, theme
from .widgets import ThinBar, icon_pixmap, mix


def clock(sec: float | None) -> str:
    if sec is None or sec < 0:
        return "—"
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}" if sec < 3600 else f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def meta_of(site: str, o: ytdlp.Opts, height: int) -> str:
    s = t("site") if site == "site" else site
    if o.what == "audio":
        return f"{s} · {o.afmt.upper()}"
    fmt = {"mp4o": "MP4", "mp4": "MP4 · H.264", "orig": "WebM/MKV"}[o.fmt]
    return f"{s} · {ytdlp.label(height) if height else t('q_best')} · {fmt}"


class DlRow(QFrame):
    """One download in «Сейчас»."""
    action = Signal(int, str)            # job id, action

    def __init__(self, job: Job, can_send: bool, parent=None):
        super().__init__(parent)
        self.job = job
        self.can_send = can_send
        self.setObjectName("item")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(14)
        audio = job.opts.what == "audio"
        self.pic = Picture(40 if audio else (30 if job.vertical else 68), 40, 8)
        self.pic.site = job.site
        self.pic.play = False
        self.pic.icon = "sound" if audio else ""
        lay.addWidget(self.pic)
        mid = QVBoxLayout()
        mid.setSpacing(3)
        self.name = Elide("itemName")
        self.name.set_full(job.title or job.url)
        self.meta = label(job.meta, "itemMeta")
        self.bar = ThinBar()
        self.status = label("", "status")
        mid.addWidget(self.name)
        mid.addWidget(self.meta)
        mid.addSpacing(3)
        mid.addWidget(self.bar)
        mid.addWidget(self.status)
        lay.addLayout(mid, 1)
        sz = QVBoxLayout()
        sz.setSpacing(0)
        self.size_lbl = label("", "sizeLbl")
        self.size_sub = label("", "sizeSub")
        for w in (self.size_lbl, self.size_sub):
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            sz.addWidget(w)
        lay.addLayout(sz)
        self.btns = QHBoxLayout()
        self.btns.setSpacing(2)
        lay.addLayout(self.btns)
        self._buttons: dict[str, IconButton] = {}
        for key, icon in (("folder", "folder"), ("send", "video"), ("pause", "pause"), ("resume", "play"),
                          ("retry", "retry"), ("remove", "x")):
            b = IconButton(icon, 28, 14)
            b.clicked.connect(lambda _=False, k=key: self.action.emit(self.job.id, k))
            self.btns.addWidget(b)
            self._buttons[key] = b
        self.retranslate()
        self.update_state()

    def retranslate(self):
        tips = {"folder": t("h_file"), "send": t("a_send_tip"), "pause": t("a_pause"), "resume": t("a_resume"),
                "retry": t("a_retry"), "remove": t("a_cancel")}
        for k, b in self._buttons.items():
            b.setToolTip(tips[k])

    def update_state(self):
        j = self.job
        st = j.state
        show = {
            "wait": {"remove"}, "work": {"pause", "remove"}, "pause": {"resume", "remove"},
            "done": {"folder", "remove"} | ({"send"} if self.can_send and j.opts.what == "video" else set()),
            "err": {"retry", "remove"}, "cancel": {"retry", "remove"},
        }[st]
        for k, b in self._buttons.items():
            b.setVisible(k in show)
        self._buttons["remove"].setToolTip(t("a_remove") if st in ("done", "err", "cancel") else t("a_cancel"))
        self.bar.set_state(j.frac, st == "work")
        self.bar.setVisible(st in ("work", "pause"))
        self.pic.done = st == "done"
        self.pic.update()
        self.status.setProperty("state", {"work": "work", "done": "done", "err": "error"}.get(st, ""))
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(self._status_text())
        if st == "done":
            self.size_lbl.setText(fmt_size(j.size))
            self.size_sub.setText("")
        elif j.est or j.got:
            self.size_lbl.setText(fmt_size(j.got) if st in ("work", "pause") and j.got else (fmt_size(j.est) if j.est else ""))
            self.size_sub.setText(("≈ " + fmt_size(j.est)) if st in ("work", "pause") and j.est else "")
        else:
            self.size_lbl.setText("")
            self.size_sub.setText("")

    def _status_text(self) -> str:
        j = self.job
        if j.state == "wait":
            return t("st_wait")
        if j.state == "pause":
            return t("st_pause", p=round(j.frac * 100))
        if j.state == "done":
            return t("st_done", s=os.path.basename(os.path.dirname(j.path)) or "—")
        if j.state == "cancel":
            return t("st_cancel")
        if j.state == "err":
            kind = j.err_kind or "other"
            site = t("site") if j.site == "site" else j.site
            head = t("e_" + kind, site=site)
            return head + (f" · {j.err_text[:90]}" if j.err_text and kind == "other" else "")
        stage = t("stage_" + j.stage) if j.stage else t("stage_start")
        parts = [f"<b>{stage}</b>", f"{round(j.frac * 100)}%"]
        if j.speed:
            parts.append(f"{fmt_size(j.speed)}/s")
        if j.eta:
            parts.append(t("eta", t=clock(j.eta)))
        return " · ".join(parts)


class HistRow(QFrame):
    action = Signal(str, str)            # history id, action

    def __init__(self, item: dict, gone: bool, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("hrow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(14)
        audio = item.get("kind") == "audio"
        vert = bool(item.get("vertical"))
        self.pic = Picture(32 if audio else (24 if vert else 56), 32, 7)
        self.pic.site = item.get("site", "site")
        self.pic.play = False
        self.pic.icon = "sound" if audio else ""
        self.pic.dim = gone
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addStretch()
        bl.addWidget(self.pic)
        bl.addStretch()
        box.setFixedWidth(56)
        lay.addWidget(box)
        mid = QVBoxLayout()
        mid.setSpacing(2)
        name = Elide("itemName")
        name.set_full(item.get("title", ""))
        meta = label("", "itemMeta")
        meta.setTextFormat(Qt.TextFormat.RichText)
        when = datetime.fromtimestamp(item.get("t", 0)).strftime("%H:%M")
        bits = [item.get("meta", ""), fmt_size(item.get("size", 0)), when]
        txt = " · ".join(b for b in bits if b)
        if gone:
            txt += f' · <span style="color:#d0a060">{t("h_gone")}</span>'
        meta.setText(txt)
        mid.addWidget(name)
        mid.addWidget(meta)
        lay.addLayout(mid, 1)
        for key, icon, tip in (("file", "folder", t("h_file")), ("link", "link", t("h_link")),
                               ("again", "retry", t("h_again_tip")), ("remove", "x", t("a_remove"))):
            b = IconButton(icon, 28, 14, tip)
            if key == "file" and gone:
                b.setEnabled(False)
            b.clicked.connect(lambda _=False, k=key: self.action.emit(self.item["hid"], k))
            lay.addWidget(b)


class PickRow(QAbstractButton):
    """A checkable line in a playlist / several links."""

    def __init__(self, num: int, title: str, right: str, note: str = "", parent=None):
        super().__init__(parent)
        self.num, self.right, self.note = num, right, note
        self.setText(title)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self._h = False

    def sizeHint(self):
        return QSize(300, 32)

    def enterEvent(self, e):
        self._h = True
        self.update()

    def leaveEvent(self, e):
        self._h = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self._h:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(theme.c("panel2"))
            p.drawRoundedRect(r.adjusted(2, 1, -2, -1), 9, 9)
        on = self.isChecked()
        box = QRectF(10, r.center().y() - 9, 18, 18)
        p.setPen(QPen(theme.c("ink") if on else theme.c("line2"), 1.5))
        p.setBrush(theme.c("ink") if on else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box, 6, 6)
        if on:
            pm = icon_pixmap("check", theme.c("on_ink"), 12, self.devicePixelRatioF())
            p.drawPixmap(QRectF(box.x() + 3, box.y() + 3, 12, 12), pm, QRectF(pm.rect()))
        p.setFont(font(8, QFont.Weight.Bold, mono=True))
        p.setPen(theme.c("faint"))
        p.drawText(QRectF(34, 0, 26, r.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(self.num))
        p.setFont(font(8.4, QFont.Weight.DemiBold, mono=True))
        rw = p.fontMetrics().horizontalAdvance(self.right) + 14
        p.setPen(theme.c("muted"))
        p.drawText(QRectF(r.width() - rw, 0, rw - 8, r.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   self.right)
        x = 70.0
        avail = r.width() - x - rw - 8
        f = font(9.4, QFont.Weight.DemiBold)
        p.setFont(f)
        note_w = 0.0
        if self.note:
            nf = font(8.2, QFont.Weight.Bold)
            p.setFont(nf)
            note_w = p.fontMetrics().horizontalAdvance(self.note) + 10
            p.setFont(f)
        text = p.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, int(max(30, avail - note_w)))
        p.setPen(theme.c("text") if on else mix(theme.c("text"), theme.c("muted"), 0.5))
        p.drawText(QRectF(x, 0, avail, r.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if self.note:
            tw = p.fontMetrics().horizontalAdvance(text)
            p.setFont(font(8.2, QFont.Weight.Bold))
            p.setPen(theme.c("tint"))
            p.drawText(QRectF(x + tw + 8, 0, note_w, r.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self.note)


class SiteDot(QWidget):
    def __init__(self, site: str, parent=None):
        super().__init__(parent)
        self.site = site
        self.setFixedSize(8, 8)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(site_color(self.site))
        p.drawEllipse(QRectF(self.rect()))
