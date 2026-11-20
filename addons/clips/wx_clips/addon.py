"""wxwx toolkit entry points: create(host) -> the page, settings(host) -> its tab in Settings."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .core import ffmpeg as ff
from .core import i18n
from .ui import theme as theme_mod
from .ui import widgets as widgets_mod


def _prepare(host):
    i18n.set_lang(host.lang)
    theme_mod.theme.name = host.theme
    app = QApplication.instance()
    if app is not None:
        theme_mod.set_font(app.font().family())
    ff.set_tools(host.component("ffmpeg"), host.component("ffmpeg", "ffprobe"))
    widgets_mod.set_hints(getattr(host, "hints", True))


def create(host):
    from .ui.page import ClipsPage
    _prepare(host)
    page = ClipsPage(host)

    def on_lang(lang):
        i18n.set_lang(lang)
        ff.set_tools(host.component("ffmpeg"), host.component("ffmpeg", "ffprobe"))
        page.retranslate()

    def on_theme(name):
        theme_mod.theme.name = name
        page.apply_theme()

    host.lang_changed.connect(on_lang)
    host.theme_changed.connect(on_theme)
    if hasattr(host, "hints_changed"):                 # toolkit 1.3+
        host.hints_changed.connect(lambda on: widgets_mod.set_hints(on, page))
    return page


def settings(host):
    from .ui.settings_tab import SettingsTab
    _prepare(host)
    tab = SettingsTab(host)
    host.lang_changed.connect(lambda _l: tab.render())
    host.theme_changed.connect(lambda _n: tab.apply_theme())
    if hasattr(host, "hints_changed"):
        host.hints_changed.connect(lambda on: widgets_mod.set_hints(on, tab))
    return tab
