"""The API an add-on receives in create(host). Keep it small and stable — add-ons depend on it.

    host.api_version        int, bumped only on breaking changes
    host.lang               "ru" | "en"
    host.theme              "dark" | "light"
    host.colors             dict of the current palette (hex / rgba strings)
    host.lang_changed       Signal(str)
    host.theme_changed      Signal(str)
    host.component(name, exe=None) -> str | None     path to e.g. ffmpeg / ffprobe / yt-dlp
    host.toast(text)
    host.folder("output" | "downloads") -> str   the toolkit-wide folders from Settings  (toolkit 1.1+)
    host.folders_changed    Signal(str kind)                                       (toolkit 1.1+)
    host.preset_received    Signal(dict)   a .wtp for this add-on was opened (double-click / drop)  (1.1+)
    host.get(key, default=None) / host.set(key, value)   per-add-on settings (JSON-able values)
    host.data_dir           Path for the add-on's own files
    host.toolkit_version    str
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, QSettings, Signal

from .. import __version__
from ..core import i18n
from ..core.components import COMPONENTS
from ..core.paths import data_dir
from .theme import theme

API_VERSION = 1


class Host(QObject):
    lang_changed = Signal(str)
    theme_changed = Signal(str)
    folders_changed = Signal(str)
    preset_received = Signal(dict)

    def __init__(self, addon_id: str, toast_fn, folder_fn, parent=None):
        super().__init__(parent)
        self.addon_id = addon_id
        self._toast = toast_fn
        self._folder = folder_fn
        self._store = QSettings("wxwx", "toolkit")
        self.api_version = API_VERSION
        self.toolkit_version = __version__

    @property
    def lang(self) -> str:
        return i18n.lang()

    @property
    def theme(self) -> str:
        return theme.name

    @property
    def colors(self) -> dict:
        return dict(theme.p)

    @property
    def data_dir(self):
        d = data_dir() / "addon-data" / self.addon_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def component(self, name: str, exe: str | None = None) -> str | None:
        c = COMPONENTS.get(name)
        return c.exe(exe) if c else None

    def toast(self, text: str) -> None:
        self._toast(text)

    def folder(self, kind: str = "output") -> str:
        return self._folder(kind)

    def get(self, key: str, default=None):
        v = self._store.value(f"addon/{self.addon_id}/{key}")
        if v is None:
            return default
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._store.setValue(f"addon/{self.addon_id}/{key}", json.dumps(value))
