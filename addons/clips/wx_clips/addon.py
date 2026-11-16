"""wxwx toolkit entry points: create(host) -> the page, settings(host) -> its tab in Settings."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .core import ffmpeg as ff
from .core import i18n
from .ui import theme as theme_mod


def _prepare(host):
    i18n.set_lang(host.lang)
    theme_mod.theme.name = host.theme
    app = QApplication.instance()
    if app is not None:
        theme_mod.FONT_FAMILY = app.font().family()
    ff.set_tools(host.component("ffmpeg"), host.component("ffmpeg", "ffprobe"))


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
    return page


def settings(host):
    from .ui.settings_tab import SettingsTab
    _prepare(host)
    tab = SettingsTab(host)
    host.lang_changed.connect(lambda _l: tab.render())
    host.theme_changed.connect(lambda _n: tab.apply_theme())
    return tab
