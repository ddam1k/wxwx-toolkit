"""The Clips tab in toolkit Settings: NVIDIA folder, what counts as new, default cutting, cache."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ..core import library
from ..core.cache import Cache
from ..core.i18n import fmt_mb, t
from .common import button, label
from .theme import stylesheet
from .widgets import Segmented, SwitchRow


class SettingsTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("clipsSettings")
        self.cache = Cache(host.data_dir)
        self.col = QVBoxLayout(self)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(0)
        self.render()

    def _section(self, text: str):
        self.col.addSpacing(24)
        self.col.addWidget(label(text, "section"))
        self.col.addSpacing(10)

    def render(self):
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        h = self.host
        nv = h.get("nv_dir", "") or ""
        self._section(t("s_folder"))
        row = QFrame()
        row.setObjectName("destBox")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 12, 10, 12)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label(nv or t("s_unset"), "destPath" if nv else "rowTitle"))
        tv.addWidget(label(t("s_set_sub") if nv else t("s_unset_sub"), "destSub"))
        rl.addLayout(tv, 1)
        if not nv:
            b = button(t("s_find"), "destBtn")
            b.clicked.connect(self._find)
            rl.addWidget(b)
        b = button(t("change") if nv else t("s_pick"), "destBtn")
        b.clicked.connect(self._pick)
        rl.addWidget(b)
        if nv:
            b = button("✕", "destBtn")
            b.clicked.connect(lambda: self._set("nv_dir", ""))
            rl.addWidget(b)
        self.col.addWidget(row)
        self.col.addSpacing(8)
        n = label(t("s_note"), "note", wrap=True)
        n.setTextFormat(Qt.TextFormat.RichText)
        self.col.addWidget(n)

        self._section(t("s_new"))
        seg = Segmented([("last", t("new_last"), ""), ("day", t("new_day"), ""), ("week", t("new_week"), "")])
        seg.set_value(h.get("new_range", "last") or "last", animated=False)
        seg.changed.connect(lambda v: h.set("new_range", v))
        self.col.addWidget(seg)
        self.col.addSpacing(8)
        sw = SwitchRow()
        sw.title.setText(t("s_mark"))
        sw.sub.setText(t("s_mark_s"))
        sw.switch.set_now(bool(h.get("mark_done", True)))
        sw.toggled.connect(lambda on: h.set("mark_done", on))
        self.col.addWidget(sw)

        sw = SwitchRow()
        sw.title.setText(t("s_fprev"))
        sw.sub.setText(t("s_fprev_s"))
        sw.switch.set_now(bool(h.get("folder_previews", False)))
        sw.toggled.connect(lambda on: h.set("folder_previews", on))
        self.col.addWidget(sw)

        self._section(t("s_cut"))
        seg = Segmented([("single", t("mode_single"), t("mode_single_s")), ("multi", t("mode_multi"), t("mode_multi_s"))])
        seg.set_value(h.get("def_mode", "single") or "single", animated=False)
        seg.changed.connect(lambda v: h.set("def_mode", v))
        self.col.addWidget(seg)
        self.col.addSpacing(8)
        sw = SwitchRow()
        sw.title.setText(t("s_merge"))
        sw.sub.setText(t("s_merge_s"))
        sw.switch.set_now(bool(h.get("def_merge", True)))
        sw.toggled.connect(lambda on: h.set("def_merge", on))
        self.col.addWidget(sw)

        self._section(t("s_cache"))
        row = QFrame()
        row.setObjectName("destBox")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 12, 10, 12)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label(t("s_cache_t"), "rowTitle"))
        try:
            mb = self.cache.size_mb()
        except OSError:
            mb = 0.0
        tv.addWidget(label(t("s_cache_s", mb=fmt_mb(mb)), "destSub"))
        rl.addLayout(tv, 1)
        b = button(t("s_cache_btn"), "destBtn")
        b.clicked.connect(self._clear_cache)
        rl.addWidget(b)
        self.col.addWidget(row)
        self.apply_theme()

    def _set(self, key, value):
        self.host.set(key, value)
        self.render()

    def _find(self):
        p = library.detect()
        if p:
            self._set("nv_dir", p)
            self.host.toast(t("s_found", p=p))
        else:
            self.host.toast(t("s_notfound"))

    def _pick(self):
        start = self.host.get("nv_dir", "") or os.path.join(os.path.expanduser("~"), "Videos")
        d = QFileDialog.getExistingDirectory(self, t("s_folder").capitalize(), start)
        if d:
            self._set("nv_dir", os.path.normpath(d))

    def _clear_cache(self):
        self.cache.clear()
        self.host.toast(t("s_cache_done"))
        self.render()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
