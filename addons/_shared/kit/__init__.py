"""wxwx kit — the widgets, theme and helpers every wxwx add-on draws with.

The one true copy lives in the toolkit repo at addons/_shared/kit/. scripts/sync_kit.py copies it
into each add-on package as  wx_<id>/kit/  (CI fails if a copy drifts), so an add-on zip stays
self-contained and works on any toolkit version. Edit the shared copy, then run:

    python scripts/sync_kit.py
"""
KIT_VERSION = "1.0.0"

_LANG = {"lang": "ru"}


def set_lang(lang: str) -> None:
    _LANG["lang"] = "en" if lang == "en" else "ru"


def lang() -> str:
    return _LANG["lang"]
