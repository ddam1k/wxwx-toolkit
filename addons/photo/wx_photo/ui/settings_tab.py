"""The Photo tab in toolkit Settings."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..core import opts
from ..core.i18n import t
from ..kit.common import label
from .theme import stylesheet
from .widgets import Chip, FlowLayout, SwitchRow


class SettingsTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("photoSettings")
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

    def _changed(self, key: str):
        if key in ("opts", "use_tk"):
            try:
                self.render()
            except RuntimeError:
                pass

    def _section(self, text: str):
        self.col.addSpacing(24)
        self.col.addWidget(label(text, "section"))
        self.col.addSpacing(10)

    def render(self):
        while self.col.count():
            it = self.col.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        o = opts.from_dict(self.host.get("opts"))
        cur = opts.matches(o)
        self._section(t("s_defaults"))
        self.col.addWidget(label(t("b_preset"), "rowLabel"))
        self.col.addSpacing(8)
        box = QWidget()
        fl = FlowLayout(box, spacing=8)
        for k in opts.PRESETS:
            c = Chip(t("p_" + k), small=True)
            c.setChecked(k == cur)
            c.clicked.connect(lambda _=False, key=k: self._preset(key))
            fl.addWidget(c)
        self.col.addWidget(box)
        self.col.addSpacing(10)
        self.col.addWidget(label(t("preset_note"), "note", wrap=True))
        self._section(t("s_dest"))
        sw = SwitchRow()
        sw.title.setText(t("tk_t"))
        sfx = self.host.suffix() if hasattr(self.host, "suffix") else "_wx"
        sw.sub.setText(t("tk_s", s=sfx))
        sw.switch.set_now(bool(self.host.get("use_tk", True)))
        sw.toggled.connect(lambda on: self.host.set("use_tk", on))
        self.col.addWidget(sw)
        self.col.addSpacing(14)
        self.col.addWidget(label(t("s_formats"), "note", wrap=True))
        self.col.addSpacing(16)
        self.col.addStretch(1)

    def _preset(self, key: str):
        self.host.set("opts", opts.PRESETS[key].to_dict())
