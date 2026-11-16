"""Cached probe results, thumbnails and timeline frames in the add-on's data folder (no Qt here)."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict
from pathlib import Path

from . import ffmpeg as ff
from .ffmpeg import MediaInfo

FRAMES = 14
_lock = threading.Lock()


class Cache:
    def __init__(self, folder: Path):
        self.dir = Path(folder) / "cache"
        self.dir.mkdir(parents=True, exist_ok=True)

    def key(self, path: str) -> str:
        try:
            st = os.stat(path)
            raw = f"{os.path.normcase(os.path.abspath(path))}|{st.st_size}|{int(st.st_mtime)}"
        except OSError:
            raw = path
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def meta(self, path: str) -> MediaInfo | None:
        k = self.key(path)
        f = self.dir / f"{k}.json"
        if f.is_file():
            try:
                d = json.loads(f.read_text("utf-8"))
                d["path"] = path
                return MediaInfo(**d)
            except (ValueError, TypeError):
                pass
        m = ff.probe(path)
        if m:
            with _lock:
                f.write_text(json.dumps(asdict(m)), "utf-8")
        return m

    def thumb(self, path: str, duration: float) -> str | None:
        f = self.dir / f"{self.key(path)}-t.jpg"
        if not f.is_file():
            data = ff.frame(path, min(duration * 0.35, max(0.0, duration - 0.5)), 360)
            if not data:
                return None
            f.write_bytes(data)
        return str(f)

    def frames(self, path: str, duration: float, n: int = FRAMES, width: int = 192) -> list[str]:
        k = self.key(path)
        out = []
        for i in range(n):
            f = self.dir / f"{k}-f{n}-{i}.jpg"
            if not f.is_file():
                data = ff.frame(path, duration * (i + 0.5) / n, width)
                if not data:
                    break
                f.write_bytes(data)
            out.append(str(f))
        return out

    def size_mb(self) -> float:
        return sum(f.stat().st_size for f in self.dir.iterdir() if f.is_file()) / 1048576

    def clear(self) -> None:
        for f in self.dir.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
