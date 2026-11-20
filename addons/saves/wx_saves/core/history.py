"""What was saved, from where and when — history.json in the add-on's data folder (no Qt here)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

KEEP_DAYS = {"month": 31, "year": 366, "all": None}
MAX_ITEMS = 3000


class History:
    def __init__(self, folder: Path):
        self.file = Path(folder) / "history.json"
        self.items: list[dict] = []
        self.keep = "year"
        self.load()

    # ---- storage
    def load(self) -> None:
        try:
            data = json.loads(self.file.read_text("utf-8"))
            self.items = [i for i in data.get("items", []) if isinstance(i, dict) and i.get("title")]
        except (OSError, ValueError):
            self.items = []
        self.prune()

    def save(self) -> None:
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"v": 1, "items": self.items}, ensure_ascii=False), "utf-8")
            os.replace(tmp, self.file)
        except OSError:
            pass

    def prune(self) -> int:
        days = KEEP_DAYS.get(self.keep)
        before = len(self.items)
        if days:
            edge = time.time() - days * 86400
            self.items = [i for i in self.items if i.get("t", 0) >= edge]
        self.items = self.items[:MAX_ITEMS]
        return before - len(self.items)

    # ---- edits
    def add(self, item: dict) -> dict:
        item = dict(item)
        item.setdefault("t", time.time())
        item.setdefault("hid", f"h{int(item['t'] * 1000)}{len(self.items)}")
        self.items.insert(0, item)
        self.prune()
        self.save()
        return item

    def remove(self, hid: str) -> None:
        self.items = [i for i in self.items if i.get("hid") != hid]
        self.save()

    def clear(self) -> int:
        n = len(self.items)
        self.items = []
        self.save()
        return n

    def set_keep(self, keep: str) -> None:
        self.keep = keep if keep in KEEP_DAYS else "year"
        if self.prune():
            self.save()

    # ---- questions
    def find(self, key: str | None = None, url: str | None = None, title: str | None = None) -> dict | None:
        for i in self.items:
            if key and i.get("key") == key:
                return i
            if url and i.get("url") == url:
                return i
            if title and i.get("title") == title:
                return i
        return None

    def search(self, text: str) -> list[dict]:
        q = (text or "").strip().lower()
        if not q:
            return list(self.items)
        return [i for i in self.items
                if q in (str(i.get("title", "")) + " " + str(i.get("meta", "")) + " " + str(i.get("site", ""))).lower()]

    @staticmethod
    def gone(item: dict) -> bool:
        p = item.get("path")
        return not p or not os.path.exists(p)
