"""Where things live.

Since 1.3 everything the toolkit keeps — settings, add-ons, shared tools like ffmpeg, add-on data —
sits next to the program in `<program folder>\\data`. The installer puts the program into a
per-user folder (no admin needed) or wherever the user chooses, so that folder is writable.

If the program folder is read-only (an old install in Program Files, a locked-down PC) the toolkit
falls back to the per-user folder it used before 1.3: %LOCALAPPDATA%\\wxwx-toolkit
(~/.local/share/wxwx-toolkit elsewhere). Running from source also uses that folder.
"""
from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

MIGRATED_MARK = ".migrated"          # in the new data folder once the old one was moved over
MOVE_ITEMS = ("addons", "components", "addon-data", "presets", "settings.ini")


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def legacy_data_dir() -> Path:
    """The pre-1.3 per-user folder (also the fallback when the program folder is read-only)."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "wxwx-toolkit"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "wxwx-toolkit"


def writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


@lru_cache(maxsize=1)
def _resolve() -> tuple[Path, bool]:
    """(data folder, True if it is next to the program)."""
    override = os.environ.get("WXWX_TOOLKIT_DATA")
    if override:
        return Path(override), False
    if getattr(sys, "frozen", False):
        local = app_dir() / "data"
        if writable(local):
            return local, True
    return legacy_data_dir(), False


def data_dir() -> Path:
    base, _ = _resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def is_local() -> bool:
    """True when data lives next to the program (1.3+ install or portable build)."""
    return _resolve()[1]


def migrate_legacy(new: Path | None = None, old: Path | None = None) -> list[str]:
    """Move add-ons, components, add-on data and settings from the old per-user folder into the
    folder next to the program. Runs once; anything already present in the new folder wins.
    Returns the names that were moved."""
    if new is None:
        if not is_local():
            return []
        new = data_dir()
    old = old or legacy_data_dir()
    mark = new / MIGRATED_MARK
    if mark.exists() or not old.is_dir() or old.resolve() == new.resolve():
        return []
    moved = []
    for name in MOVE_ITEMS:
        src, dst = old / name, new / name
        if not src.exists() or dst.exists():
            continue
        try:
            shutil.move(str(src), str(dst))
            moved.append(name)
        except OSError:
            pass                          # leave it — the add-on/tool will simply be downloaded again
    try:
        new.mkdir(parents=True, exist_ok=True)
        mark.write_text(str(old), encoding="utf-8")
    except OSError:
        pass
    return moved


def addons_dir() -> Path:
    d = data_dir() / "addons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def components_dir() -> Path:
    d = data_dir() / "components"
    d.mkdir(parents=True, exist_ok=True)
    return d


def downloads_tmp() -> Path:
    d = data_dir() / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_file() -> Path:
    return data_dir() / "settings.ini"


def install_lang() -> str | None:
    """Language picked in the installer (written to install.ini next to the program)."""
    f = app_dir() / "install.ini"
    try:
        for line in f.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            k, _, v = line.partition("=")
            if k.strip().lower() == "lang" and v.strip() in ("ru", "en"):
                return v.strip()
    except OSError:
        pass
    return None


NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW for subprocesses on Windows
