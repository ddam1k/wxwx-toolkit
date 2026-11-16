""".wtp — wxwx toolkit preset. A small JSON file any add-on can export and import.

    {
      "wtp": 1,
      "addon": "compress",            id of the add-on the preset belongs to
      "addon_name": "Видео",          shown when the preset is opened in the wrong place
      "addon_version": "1.1.0",
      "name": "Discord 10 МБ",
      "author": "yuyu",
      "created": "2026-11-16",
      "settings": { ... }             add-on specific
    }
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

WTP_VERSION = 1
EXT = ".wtp"


class PresetError(ValueError):
    pass


def make(addon: str, name: str, settings: dict, addon_name: str = "", addon_version: str = "",
         author: str = "") -> dict:
    return {"wtp": WTP_VERSION, "addon": addon, "addon_name": addon_name or addon, "addon_version": addon_version,
            "name": name, "author": author, "created": datetime.date.today().isoformat(), "settings": settings}


def parse(data) -> dict:
    if not isinstance(data, dict) or data.get("wtp") != WTP_VERSION:
        raise PresetError("not a .wtp preset")
    if not isinstance(data.get("settings"), dict) or not data.get("addon"):
        raise PresetError("preset has no add-on or settings")
    data.setdefault("name", "preset")
    return data


def read(path: str | Path) -> dict:
    try:
        return parse(json.loads(Path(path).read_text("utf-8-sig")))
    except (OSError, json.JSONDecodeError) as e:
        raise PresetError(str(e)) from e


def write(path: str | Path, data: dict) -> Path:
    p = Path(path)
    if p.suffix.lower() != EXT:
        p = p.with_suffix(EXT)
    p.write_text(json.dumps(parse(dict(data)), ensure_ascii=False, indent=2), "utf-8")
    return p


def safe_filename(name: str) -> str:
    bad = '\\/:*?"<>|'
    return "".join("_" if c in bad else c for c in name).strip() or "preset"
