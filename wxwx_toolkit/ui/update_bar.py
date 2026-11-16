"""Slim bar under the header: 'version X is available · Update · Later', with download progress."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ..core.i18n import t
from .widgets import Logo, ThinBar, animate

HEIGHT = 46


class UpdateBar(QFrame):
    update_clicked = Signal()
    later_clicked = Signal()
    notes_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateBar")
        self.setMaximumHeight(0)
        self.version = ""
        self.can_install = True
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 18, 0)
        lay.setSpacing(10)
        self.logo = Logo(18)
        lay.addWidget(self.logo)
        self.text = QLabel("")
        self.text.setObjectName("updateText")
        lay.addWidget(self.text)
        self.bar = ThinBar()
        self.bar.setFixedWidth(160)
        self.bar.hide()
        lay.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch()
        self.notes = QPushButton()
        self.notes.setObjectName("link")
        self.later = QPushButton()
        self.later.setObjectName("ghost")
        self.go = QPushButton()
        self.go.setObjectName("accent")
        for w, sig in ((self.notes, self.notes_clicked), (self.later, self.later_clicked), (self.go, self.update_clicked)):
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            w.clicked.connect(sig)
            lay.addWidget(w)
        self.retranslate()

    def retranslate(self):
        self.notes.setText(t("upd_notes"))
        self.later.setText(t("upd_later"))
        self.go.setText(t("upd_go") if self.can_install else t("upd_get"))
        if self.version and not self.bar.isVisible():
            self.text.setText(t("upd_available", v=self.version))

    def _set_h(self, v):
        self.setMaximumHeight(int(v))

    def slide(self, show: bool) -> None:
        animate(self, self.maximumHeight(), HEIGHT if show else 0, 380, self._set_h,
                QEasingCurve.Type.OutCubic if show else QEasingCurve.Type.InCubic)

    def show_release(self, version: str, notes: str, can_install: bool) -> None:
        self.version, self.can_install = version, can_install
        self.notes.setToolTip(notes[:1200] if notes else "")
        self.go.setEnabled(True)
        self.later.show()
        self.bar.hide()
        self.logo.set_busy(False)
        self.retranslate()
        self.slide(True)

    def set_downloading(self, done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 0
        self.text.setText(t("upd_dl", p=pct))
        self.bar.show()
        self.bar.set_state(pct / 100, True)
        self.go.setEnabled(False)
        self.later.hide()
        self.logo.set_busy(True)

    def set_installing(self) -> None:
        self.text.setText(t("upd_installing"))
        self.bar.set_state(1, False)
