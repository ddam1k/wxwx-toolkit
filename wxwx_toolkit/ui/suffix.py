"""Suffix pickers: the toolkit-wide one (Settings → General) and the per-add-on block that add-ons
get from  host.suffix_widget()  for their own settings tab (toolkit 1.3+)."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..core import naming
from ..core.i18n import t
from .hints import mark as mark_hint
from .shell import SwitchRow
from .theme import theme
from .widgets import Segmented


def _label(name: str, wrap: bool = False) -> QLabel:
    lb = QLabel()
    lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def preview_html(sample: str, suffix: str | None) -> str:
    s = html.escape(sample)
    if suffix is None:
        return f'<span style="color:{theme.p["faint"]}">{s}</span> → <span style="color:#d0806a">{html.escape(t("sfx_fix"))}</span>'
    stem, dot, ext = sample.rpartition(".")
    if not dot:
        stem, ext = sample, ""
    out = (f'{html.escape(stem)}<span style="color:{theme.p["tint"]}">{html.escape(suffix)}</span>'
           + (f".{html.escape(ext)}" if ext else ""))
    return f'<span style="color:{theme.p["faint"]}">{s}</span> → <b>{out}</b>'


class SuffixPicker(QWidget):
    """_wx / _trim / Свой + a text field, the error line and a live example."""
    changed = Signal(str, str)          # kind, custom text

    def __init__(self, sample: str = "Ranked_2026-11-20.mp4", parent=None):
        super().__init__(parent)
        self.sample = sample
        self.kind, self.custom = naming.DEFAULT, ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.seg = Segmented([("wx", "_wx", "x"), ("trim", "_trim", "x"), ("custom", "", "x")])
        self.seg.changed.connect(self._on_kind)
        lay.addWidget(self.seg)
        self.box = QFrame()
        self.box.setObjectName("sfxBox")
        self.box.setMaximumWidth(280)
        bl = QHBoxLayout(self.box)
        bl.setContentsMargins(12, 0, 8, 0)
        bl.setSpacing(1)
        us = _label("sfxUnder")
        us.setText("_")
        bl.addWidget(us)
        self.edit = QLineEdit()
        self.edit.setObjectName("sfxEdit")
        self.edit.setMaxLength(24)
        self.edit.textEdited.connect(self._on_text)
        bl.addWidget(self.edit, 1)
        self.box.setFixedHeight(38)
        lay.addWidget(self.box)
        self.err = _label("sfxErr", wrap=True)
        lay.addWidget(self.err)
        self.prev = _label("sfxPrev")
        self.prev.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.prev)
        self.refresh()

    # ---- state
    def set_values(self, kind: str, custom: str) -> None:
        self.kind = kind if kind in naming.KINDS else naming.DEFAULT
        self.custom = custom or ""
        self.seg.set_value(self.kind, animated=False)
        if self.edit.text() != self.custom:
            self.edit.setText(self.custom)
        self._sync()

    def suffix(self) -> str | None:
        """"_xxx", or None while the custom text is broken."""
        if self.kind == "custom" and naming.error(self.custom):
            return None
        return naming.resolve(self.kind, self.custom)

    def refresh(self) -> None:
        self.seg.options = [("wx", "_wx", t("sfx_wx_s")), ("trim", "_trim", t("sfx_trim_s")),
                            ("custom", t("sfx_custom"), t("sfx_custom_s"))]
        self.seg.update()
        self.edit.setPlaceholderText(t("sfx_ph"))
        self._sync()

    def _sync(self) -> None:
        custom = self.kind == "custom"
        self.box.setVisible(custom)
        e = naming.error(self.custom) if custom else None
        self.err.setVisible(bool(e))
        self.err.setText(t("sfx_err_" + e, n=naming.MAX_LEN) if e else "")
        self.box.setProperty("bad", bool(e))
        self.box.style().unpolish(self.box)
        self.box.style().polish(self.box)
        self.prev.setText(preview_html(self.sample, self.suffix()))

    def _on_kind(self, kind: str) -> None:
        self.kind = kind
        self._sync()
        if kind == "custom":
            self.edit.setFocus()
        self.changed.emit(self.kind, self.custom)

    def _on_text(self, text: str) -> None:
        self.custom = text
        self._sync()
        self.changed.emit(self.kind, self.custom)


class AddonSuffixBlock(QWidget):
    """«Как в настройках тулкита» or the add-on's own suffix. Stored in the add-on's settings:
    suffix_own (bool), suffix (kind), suffix_custom (text)."""

    def __init__(self, host, sample: str, parent=None):
        super().__init__(parent)
        self.host, self.sample = host, sample
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.same = SwitchRow()
        self.same.toggled.connect(self._on_same)
        lay.addWidget(self.same)
        self.picker = SuffixPicker(sample)
        self.picker.changed.connect(self._on_pick)
        lay.addWidget(self.picker)
        self.prev = _label("sfxPrev")
        self.prev.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.prev)
        host.suffix_changed.connect(self._changed)
        host.lang_changed.connect(self._changed)
        host.theme_changed.connect(self._changed)
        self.refresh()

    def _changed(self, _v=None) -> None:
        self.refresh()

    def refresh(self) -> None:
        try:
            own = bool(self.host.get("suffix_own", False))
            self.same.set_texts(t("sfx_same"), t("sfx_same_s", s=self.host.toolkit_suffix()))
            self.same.switch.set_now(not own)
            self.picker.refresh()
            self.picker.set_values(self.host.get("suffix", naming.DEFAULT), self.host.get("suffix_custom", ""))
            self.picker.setVisible(own)
            self.prev.setVisible(not own)
            self.prev.setText(preview_html(self.sample, self.host.suffix()))
        except RuntimeError:
            pass

    def _on_same(self, same: bool) -> None:
        self.host.set_suffix(own=not same)

    def _on_pick(self, kind: str, custom: str) -> None:
        self.host.set_suffix(kind=kind, custom=custom)


mark = mark_hint
