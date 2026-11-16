"""Where things live.

The program itself may sit in Program Files (read-only without admin), so everything the
toolkit downloads at runtime — add-ons and shared tools like ffmpeg — goes to a per-user
data folder: %LOCALAPPDATA%\\wxwx-toolkit on Windows (~/.local/share/wxwx-toolkit elsewhere).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("WXWX_TOOLKIT_DATA")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "wxwx-toolkit"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "wxwx-toolkit"
    base.mkdir(parents=True, exist_ok=True)
    return base


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


NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW for subprocesses on Windows
