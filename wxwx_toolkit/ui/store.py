"""The toolkit's settings file: data\\settings.ini next to the program (1.3+).

Before 1.3 settings lived in the registry (HKCU\\Software\\wxwx\\toolkit). The first time the new
file is created everything is copied over from there, so nothing is lost on update.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

from ..core.paths import settings_file

_store: QSettings | None = None


def _copy_from_registry(dst: QSettings) -> int:
    src = QSettings("wxwx", "toolkit")
    keys = src.allKeys()
    for k in keys:
        dst.setValue(k, src.value(k))
    return len(keys)


def store() -> QSettings:
    """One shared QSettings for the toolkit and every add-on host."""
    global _store
    if _store is None:
        path = settings_file()
        fresh = not path.exists()
        _store = QSettings(str(path), QSettings.Format.IniFormat)
        if fresh:
            _copy_from_registry(_store)
            _store.setValue("meta/created_by", "1.3")
            _store.sync()
    return _store


def reset_for_tests() -> None:
    global _store
    _store = None
