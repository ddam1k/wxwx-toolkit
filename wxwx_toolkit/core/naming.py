"""The suffix added to a finished file's name so it never lands on top of the original (no Qt here).

    Ranked_2026-11-20.mp4  →  Ranked_2026-11-20_wx.mp4

One suffix is set for the whole toolkit; every add-on can keep it or pick its own.
"""
from __future__ import annotations

import re

KINDS = ("wx", "trim", "custom")
DEFAULT = "wx"
MAX_LEN = 16
_ALLOWED = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_-]+$")


def clean(text: str) -> str:
    """What the user typed → the bare suffix: no spaces, no leading underscores / dashes."""
    return (text or "").strip().lstrip("_-").strip()


def error(text: str) -> str | None:
    """None if the custom suffix is fine, else "empty" | "chars" | "long"."""
    s = clean(text)
    if not s:
        return "empty"
    if not _ALLOWED.match(s):
        return "chars"
    if len(s) > MAX_LEN:
        return "long"
    return None


def resolve(kind: str, custom: str = "") -> str:
    """The suffix with its underscore, e.g. "_wx". A broken custom value falls back to the default."""
    if kind == "custom":
        return "_" + clean(custom) if error(custom) is None else "_" + DEFAULT
    return "_" + (kind if kind in KINDS else DEFAULT)


def apply(name: str, suffix: str) -> str:
    """"clip.mp4", "_wx" → "clip_wx.mp4" (only the last extension is kept apart)."""
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        return name + suffix
    return f"{stem}{suffix}.{ext}"
