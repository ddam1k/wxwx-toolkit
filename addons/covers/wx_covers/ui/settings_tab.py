"""The Covers tab in toolkit Settings: what a new session starts with."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..core import audio
from ..core.i18n import t
from ..kit.common import label
from .theme import stylesheet
from .widgets import Segmented, SwitchRow


class SettingsTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("coversSettings")
        self.col = QVBoxLayout(self)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(0)
        self.setStyleSheet(stylesheet())
        self.render()
        if hasattr(host, "settings_changed"):
            host.settings_changed.connect(self._changed)

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        self.update()

    def opt(self, key, default):
        v = self.host.get(key, default)
        return default if v is None else v

    def _changed(self, key: str):
        if key in ("size", "rename", "copies"):          # the page changed it → show the same here
            try:
                self.render()
            except RuntimeError:
                pass

    def _section(self, text: str):
        self.col.addSpacing(24)
        self.col.addWidget(label(text, "section"))
        self.col.addSpacing(10)

    def _switch(self, key: str, title: str, sub: str):
        sw = SwitchRow()
        sw.title.setText(title)
        sw.sub.setText(sub)
        sw.switch.set_now(bool(self.opt(key, False)))
        sw.toggled.connect(lambda on, k=key: self.host.set(k, on))
        self.col.addWidget(sw)

    def render(self):
        while self.col.count():
            it = self.col.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._section(t("s_defaults"))
        self.col.addWidget(label(t("b_size"), "rowLabel"))
        self.col.addSpacing(6)
        seg = Segmented([(s, t("sz_" + s), t(f"sz_{s}_s")) for s in audio.SIZES])
        seg.set_value(str(self.opt("size", "1000")), animated=False)
        seg.changed.connect(lambda v: self.host.set("size", v))
        self.col.addWidget(seg)
        self.col.addSpacing(10)
        self._switch("rename", t("rename_t"), t("s_rename_s"))
        self._switch("copies", t("copies_t"), t("s_copies_s"))
        self.col.addSpacing(10)
        n = label(t("s_formats"), "note", wrap=True)
        self.col.addWidget(n)
        self._section(t("s_from"))
        self.col.addWidget(label(t("s_from_note"), "note", wrap=True))
        self.col.addSpacing(16)
