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
    host.get(key, default, addon="compress")   read (only) another add-on's setting, e.g. its presets  (1.2+)
    host.installed(addon_id) -> bool          is that add-on installed                                 (1.2+)
    host.open_settings()                      switch to this add-on's tab in Settings                  (1.2+)
    host.settings_changed   Signal(str key)   emitted after set() — keeps the page and its settings tab in sync (1.2+)
    host.data_dir           Path for the add-on's own files
    host.toolkit_version    str

    «Меньше подсказок» (toolkit 1.3+):
    host.hints              bool, True = show explanations (the default)
    host.hints_changed      Signal(bool)
    host.hint(*widgets)     mark labels as hints — the toolkit hides them in "less hints" mode
                            (same as widget.setProperty("hint", True))

    Suffix of finished files (toolkit 1.3+):
    host.suffix() -> str            e.g. "_wx": the toolkit's suffix or this add-on's own one
    host.suffix_changed     Signal(str)
    host.suffix_widget(sample) -> QWidget   ready block for the add-on's settings tab:
                            «Как в настройках тулкита» or its own _wx / _trim / custom

    Hand files to another add-on (toolkit 1.3.1+):
    host.send_to(addon_id, [paths]) -> bool   opens that add-on and gives it the files
    host.files_received     Signal(list)      files another add-on sent to this one

The add-on's page may also define (toolkit 1.2+ calls them before a hot update / removal):
    is_busy() -> bool       True while it works; the toolkit then postpones a quiet auto-update
    shutdown()              stop workers / child processes — the old page is about to be destroyed
"""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal

from .. import __version__
from ..core import i18n, naming
from ..core.components import COMPONENTS
from ..core.paths import data_dir
from .hints import hints as _hints
from .hints import mark as _mark
from .store import store
from .theme import theme

API_VERSION = 1


class Host(QObject):
    lang_changed = Signal(str)
    theme_changed = Signal(str)
    folders_changed = Signal(str)
    preset_received = Signal(dict)
    settings_changed = Signal(str)
    hints_changed = Signal(bool)
    suffix_changed = Signal(str)
    files_received = Signal(list)

    def __init__(self, addon_id: str, toast_fn, folder_fn, parent=None, installed_fn=None, open_settings_fn=None,
                 toolkit_suffix_fn=None, send_fn=None):
        super().__init__(parent)
        self.addon_id = addon_id
        self._toast = toast_fn
        self._folder = folder_fn
        self._installed = installed_fn or (lambda _aid: False)
        self._open_settings = open_settings_fn or (lambda _aid: None)
        self._store = store()
        self._toolkit_suffix = toolkit_suffix_fn or (lambda: "_" + naming.DEFAULT)
        self._send = send_fn
        self.api_version = API_VERSION
        self.toolkit_version = __version__
        _hints.changed.connect(self.hints_changed)

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

    def installed(self, addon_id: str) -> bool:
        return bool(self._installed(addon_id))

    def open_settings(self) -> None:
        self._open_settings(self.addon_id)

    def get(self, key: str, default=None, addon: str | None = None):
        v = self._store.value(f"addon/{addon or self.addon_id}/{key}")
        if v is None:
            return default
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._store.setValue(f"addon/{self.addon_id}/{key}", json.dumps(value))
        self.settings_changed.emit(key)

    # ---- «Меньше подсказок» (1.3+)
    @property
    def hints(self) -> bool:
        return _hints.on

    def hint(self, *widgets) -> None:
        _mark(*widgets)

    # ---- suffix (1.3+)
    def toolkit_suffix(self) -> str:
        return self._toolkit_suffix()

    def suffix(self) -> str:
        if self.get("suffix_own", False):
            return naming.resolve(self.get("suffix", naming.DEFAULT), self.get("suffix_custom", ""))
        return self.toolkit_suffix()

    def set_suffix(self, own: bool | None = None, kind: str | None = None, custom: str | None = None) -> None:
        if own is not None:
            self._store.setValue(f"addon/{self.addon_id}/suffix_own", json.dumps(bool(own)))
        if kind is not None:
            self._store.setValue(f"addon/{self.addon_id}/suffix", json.dumps(kind))
        if custom is not None:
            self._store.setValue(f"addon/{self.addon_id}/suffix_custom", json.dumps(custom))
        self.suffix_changed.emit(self.suffix())

    def suffix_widget(self, sample: str = "video.mp4"):
        from .suffix import AddonSuffixBlock
        return AddonSuffixBlock(self, sample)

    # ---- hand files to another add-on (1.3.1+)
    def send_to(self, addon_id: str, paths: list) -> bool:
        return bool(self._send and self._send(addon_id, [str(p) for p in paths]))
