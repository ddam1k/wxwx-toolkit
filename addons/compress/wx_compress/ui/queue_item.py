"""One row in the queue: thumbnail, name, meta, progress, estimate."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QToolButton, QVBoxLayout,
                               QWidget)

from ..core.ffmpeg import MediaInfo
from ..core.i18n import fmt_mb as _fmt_mb
from ..core.i18n import t
from .widgets import ThinBar, Thumb, animate


fmt_mb = _fmt_mb


def fmt_dur(s: float) -> str:
    s = int(round(s))
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_pct(new: float, old: float) -> str:
    if old <= 0:
        return ""
    d = round((1 - new / old) * 100)
    return f"−{d}%" if d >= 0 else f"+{-d}%"


class ElideLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text
        self.setMinimumWidth(40)
        self.setText(text)

    def set_full(self, t: str) -> None:
        self._full = t
        self.setToolTip(t)
        self._elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        super().setText(QFontMetrics(self.font()).elidedText(self._full, Qt.TextElideMode.ElideMiddle, self.width()))


class QueueItem(QFrame):
    remove_requested = Signal(int)
    open_requested = Signal(int)

    def __init__(self, item_id: int, name: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.setObjectName("item")
        self.setFixedHeight(84)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 8, 10)
        lay.setSpacing(14)

        self.thumb = Thumb()
        lay.addWidget(self.thumb)

        info = QVBoxLayout()
        info.setSpacing(1)
        self.name = ElideLabel()
        self.name.setObjectName("itemName")
        self.name.set_full(name)
        self.meta = QLabel("…")
        self.meta.setObjectName("itemMeta")
        self.bar = ThinBar()
        self.status = QLabel(t("st_reading"))
        self.status.setObjectName("status")
        info.addWidget(self.name)
        info.addWidget(self.meta)
        info.addSpacing(5)
        info.addWidget(self.bar)
        info.addSpacing(3)
        info.addWidget(self.status)
        lay.addLayout(info, 1)

        est = QVBoxLayout()
        est.setSpacing(0)
        self.est_lbl = QLabel(t("est_will"))
        self.est_lbl.setObjectName("estLbl")
        self.est_size = QLabel("—")
        self.est_size.setObjectName("estSize")
        self.est_pct = QLabel("")
        self.est_pct.setObjectName("estPct")
        for w in (self.est_lbl, self.est_size, self.est_pct):
            w.setAlignment(Qt.AlignmentFlag.AlignRight)
            est.addWidget(w)
        est_w = QWidget()
        est_w.setLayout(est)
        est_w.setFixedWidth(96)
        est.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(est_w)

        self.rm = QToolButton()
        self.rm.setObjectName("rm")
        self.rm.setText("✕")
        self.rm.setFixedSize(28, 28)
        self.rm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rm.setToolTip(t("rm_tip"))
        self.rm.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        lay.addWidget(self.rm)

        self.setToolTip(t("open_tip"))
        self._fade_in()

    # ---- animations ----
    def _fade_in(self):
        eff = QGraphicsOpacityEffect(self)
        eff.setOpacity(0)
        self.setGraphicsEffect(eff)
        animate(self, 0, 1, 380, eff.setOpacity, on_done=lambda: self.setGraphicsEffect(None))

    def fade_out(self, done) -> None:
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        animate(self, 1, 0, 260, eff.setOpacity, QEasingCurve.Type.InCubic, on_done=done)

    # ---- data ----
    def set_media(self, m: MediaInfo, thumb_png: bytes | None) -> None:
        self.meta.setText(f"{m.width}×{m.height} · {m.fps:g} fps · {fmt_mb(m.size_mb)}"
                          + ("" if m.acodec else " · " + t("no_audio")))
        self.thumb.duration = fmt_dur(m.duration)
        if thumb_png:
            pm = QPixmap()
            pm.loadFromData(thumb_png, "PNG")
            self.thumb.pixmap = pm
        self.thumb.update()

    def set_estimate(self, new_mb: float, old_mb: float, done: bool = False) -> None:
        self.est_lbl.setText(t("est_now") if done else t("est_will"))
        self.est_size.setText(fmt_mb(new_mb))
        self.est_pct.setText(fmt_pct(new_mb, old_mb))

    def set_state(self, state: str, text: str, progress: float = 0.0) -> None:
        if self.status.property("state") != state:
            self.status.setProperty("state", state)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.thumb.set_done(state == "done")
        self.status.setText(text)
        self.bar.set_state(progress, state == "work")
        self.rm.setEnabled(state != "work")

    def mouseDoubleClickEvent(self, e):
        self.open_requested.emit(self.item_id)
