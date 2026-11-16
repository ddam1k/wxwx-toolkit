"""The NVIDIA clips folder: game subfolders, their clips, what is new (no Qt here)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

CLIP_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".flv", ".avi", ".m4v", ".ts"}
# "Valorant 2026.11.16 - 23.17.09.05.DVR.mp4" (NVIDIA App / ShadowPlay naming)
NV_NAME = re.compile(r"^(?P<game>.+?) (?P<y>\d{4})\.(?P<mo>\d\d)\.(?P<d>\d\d) - (?P<h>\d\d)\.(?P<mi>\d\d)\.(?P<s>\d\d)")


@dataclass
class ClipFile:
    path: str
    folder: str               # game folder name, "" for files in the root
    size: int
    mtime: float

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def game(self) -> str:
        m = NV_NAME.match(Path(self.path).stem)
        return m.group("game") if m else (self.folder or Path(self.path).stem)


@dataclass
class GameFolder:
    name: str
    path: str
    root: bool = False
    clips: list[ClipFile] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.clips)

    @property
    def size(self) -> int:
        return sum(c.size for c in self.clips)

    @property
    def last(self) -> float:
        return max((c.mtime for c in self.clips), default=0.0)


def _clips_in(folder: Path, name: str, deep: bool) -> list[ClipFile]:
    out = []
    try:
        it = folder.rglob("*") if deep else folder.iterdir()
        for f in it:
            if f.suffix.lower() in CLIP_EXTS and f.is_file():
                st = f.stat()
                out.append(ClipFile(str(f), name, st.st_size, st.st_mtime))
    except OSError:
        pass
    out.sort(key=lambda c: c.mtime, reverse=True)
    return out


def scan(root: str) -> list[GameFolder]:
    """Every subfolder with clips (searched recursively) + files lying in the root itself."""
    base = Path(root)
    if not root or not base.is_dir():
        return []
    folders = []
    try:
        subs = sorted((p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())
    except OSError:
        subs = []
    for d in subs:
        clips = _clips_in(d, d.name, deep=True)
        if clips:
            folders.append(GameFolder(d.name, str(d), False, clips))
    loose = _clips_in(base, "", deep=False)
    if loose:
        folders.append(GameFolder("", str(base), True, loose))
    return folders


def looks_like_clips(folder: Path) -> bool:
    try:
        for d in folder.iterdir():
            if d.is_dir():
                for f in d.iterdir():
                    if f.suffix.lower() in CLIP_EXTS and NV_NAME.match(f.stem):
                        return True
    except OSError:
        pass
    return False


def detect() -> str | None:
    """Where NVIDIA keeps clips: NVIDIA App uses Videos\\NVIDIA\\<Game>, old ShadowPlay Videos\\<Game>."""
    home = Path.home()
    vids = [home / "Videos"]
    od = os.environ.get("OneDrive")
    if od:
        vids.append(Path(od) / "Videos")
    for v in vids:
        for cand in (v / "NVIDIA", v / "Captures", v):
            if cand.is_dir() and looks_like_clips(cand):
                return str(cand)
    return None


def new_clips(folders: list[GameFolder], since: float, done: set[str]) -> list[ClipFile]:
    out = [c for f in folders for c in f.clips if c.mtime > since and c.path not in done]
    out.sort(key=lambda c: c.mtime, reverse=True)
    return out
