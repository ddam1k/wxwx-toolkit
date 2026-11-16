"""wxwx toolkit add-on entry: create(host) -> QWidget.

Inside the add-on zip this package is shipped as `wx_compress`, so the manifest entry is
"wx_compress.addon:create". Relative imports keep it working under either name.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .core import ffmpeg as ff
from .core import i18n
from .ui import theme as theme_mod
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


def _sync_tools(host):
    ff.set_tools(host.component("ffmpeg"), host.component("ffmpeg", "ffprobe"))


def create(host):
    i18n.set_lang(host.lang)
    theme_mod.theme.name = host.theme
    app = QApplication.instance()
    if app is not None:
        theme_mod.FONT_FAMILY = app.font().family()
    _sync_tools(host)

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
    return panel
