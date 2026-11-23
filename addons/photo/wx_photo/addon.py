"""wxwx toolkit add-on entry: create(host) -> QWidget, settings(host) -> QWidget.

Shipped as `wx_photo`; manifest entry "wx_photo.addon:create"."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from .core import i18n
from .ui import theme as theme_mod
from .ui import widgets as widgets_mod


def _prepare(host):
    i18n.set_lang(host.lang)
    theme_mod.theme.name = host.theme
    app = QApplication.instance()
    if app is not None:
        theme_mod.set_font(app.font().family())
    widgets_mod.set_hints(getattr(host, "hints", True))


def create(host):
    from .ui.page import PhotoPage
    _prepare(host)
    page = PhotoPage(host)

    def on_lang(lang):
        i18n.set_lang(lang)
        page.retranslate()

    def on_theme(name):
        theme_mod.theme.name = name
        page.apply_theme()

    host.lang_changed.connect(on_lang)
    host.theme_changed.connect(on_theme)
    if hasattr(host, "hints_changed"):
        host.hints_changed.connect(lambda on: widgets_mod.set_hints(on, page))
    if hasattr(host, "files_received"):
        host.files_received.connect(page.files_received)
    return page


def settings(host):
    from .ui.settings_tab import SettingsTab
    _prepare(host)
    tab = SettingsTab(host)

    def on_lang(lang):
        i18n.set_lang(lang)
        tab.render()

    def on_theme(name):
        theme_mod.theme.name = name
        tab.apply_theme()

    host.lang_changed.connect(on_lang)
    host.theme_changed.connect(on_theme)
    if hasattr(host, "hints_changed"):
        host.hints_changed.connect(lambda on: widgets_mod.set_hints(on, tab))
    return tab
