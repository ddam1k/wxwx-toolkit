"""«Меньше подсказок» — one switch that hides the explanations under settings everywhere.

Any widget with the dynamic property  hint=True  is a hint: in "less hints" mode the toolkit hides
it (and keeps it hidden even if its page shows it again later). Add-ons just mark their labels:

    label.setProperty("hint", True)

Custom-painted controls (segmented buttons and chips with a second line) read  hints.on  and the
host's  hints_changed  signal to drop their small print.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QWidget

_HIDDEN = "_hintHidden"


class Hints(QObject):
    changed = Signal(bool)          # True = hints are shown

    def __init__(self):
        super().__init__()
        self.on = True
        self._installed = False

    def install(self) -> None:
        app = QApplication.instance()
        if app is not None and not self._installed:
            app.installEventFilter(self)
            self._installed = True

    def set(self, on: bool) -> None:
        on = bool(on)
        if on == self.on:
            return
        self.on = on
        self.apply()
        self.changed.emit(on)

    def apply(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        for w in app.allWidgets():
            if w.property("hint"):
                self._fix(w)

    def _fix(self, w: QWidget) -> None:
        if not self.on:
            if not w.isHidden():
                w.setProperty(_HIDDEN, True)
                w.hide()
        elif w.property(_HIDDEN):
            w.setProperty(_HIDDEN, False)
            w.show()

    def eventFilter(self, obj, ev):
        # a page showed a hint label again while hints are off → hide it right after
        if not self.on and ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.property("hint"):
            QTimer.singleShot(0, lambda w=obj: self._safe_fix(w))
        return False

    def _safe_fix(self, w: QWidget) -> None:
        try:
            self._fix(w)
        except RuntimeError:         # deleted meanwhile
            pass


hints = Hints()


def mark(*widgets: QWidget) -> None:
    for w in widgets:
        w.setProperty("hint", True)
        if not hints.on:
            hints._fix(w)
