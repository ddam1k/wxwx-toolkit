"""wxwx toolkit add-on entry: create(host) -> QWidget.

Inside the add-on zip this package is shipped as `wx_compress`, so the manifest entry is
"wx_compress.addon:create". Relative imports keep it working under either name.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .core import ffmpeg as ff
from .core import i18n
from .ui import theme as theme_mod
from .ui import widgets as widgets_mod
from .ui.panel import CompressorPanel, Env


class HostEnv(Env):
    is_addon = True

    def __init__(self, host):
        self.host = host

    def get(self, key, default=None):
        return self.host.get(key, default)

    def set(self, key, value):
        self.host.set(key, value)

    def toast(self, text, ms=2600):
        self.host.toast(text)

    def toolkit_folder(self):
        if hasattr(self.host, "folder"):           # toolkit 1.1+
            return self.host.folder("output")
        return None

    def suffix(self):
        if hasattr(self.host, "suffix"):           # toolkit 1.3+: shared or own suffix
            try:
                return self.host.suffix()
            except Exception:
                pass
        return super().suffix()


def _sync_tools(host):
    ff.set_tools(host.component("ffmpeg"), host.component("ffmpeg", "ffprobe"))


def create(host):
    i18n.set_lang(host.lang)
    theme_mod.theme.name = host.theme
    app = QApplication.instance()
    if app is not None:
        theme_mod.FONT_FAMILY = app.font().family()
    _sync_tools(host)
    widgets_mod.set_hints(getattr(host, "hints", True))

    panel = CompressorPanel(HostEnv(host))

    def on_lang(lang):
        i18n.set_lang(lang)
        _sync_tools(host)          # a component may have just been downloaded
        panel.retranslate()

    def on_theme(name):
        theme_mod.theme.name = name
        panel.apply_theme()
        panel.render()

    host.lang_changed.connect(on_lang)
    host.theme_changed.connect(on_theme)
    if hasattr(host, "folders_changed"):
        host.folders_changed.connect(lambda _kind: panel.render())
    if hasattr(host, "preset_received"):
        host.preset_received.connect(panel.import_preset)
    if hasattr(host, "hints_changed"):                 # toolkit 1.3+
        host.hints_changed.connect(lambda on: widgets_mod.set_hints(on, panel))
    if hasattr(host, "suffix_changed"):
        host.suffix_changed.connect(lambda _s: panel.render())
    return panel


def settings(host):
    """Settings tab (toolkit 1.3+): the suffix of finished files. Older toolkits get no tab."""
    if not hasattr(host, "suffix_widget"):
        return None
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    i18n.set_lang(host.lang)
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addSpacing(24)
    sec = QLabel(i18n.t("s_naming"))
    sec.setObjectName("section")
    lay.addWidget(sec)
    lay.addSpacing(10)
    lay.addWidget(host.suffix_widget("gameplay_2026-11-12.mp4"))
    host.lang_changed.connect(lambda _l: sec.setText(i18n.t("s_naming")))
    return w
