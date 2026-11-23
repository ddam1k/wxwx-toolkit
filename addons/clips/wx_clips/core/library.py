"""The NVIDIA clips folder: game subfolders, their clips, what is new (no Qt here)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

CLIP_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".flv", ".avi", ".m4v", ".ts"}
# "Valorant 2026.11.16 - 23.17.09.05.DVR.mp4" (NVIDIA App / ShadowPlay naming)
NV_NAME = re.compile(r"^(?P<game>.+?) (?P<y>\d{4})\.(?P<mo>\d\d)\.(?P<d>\d\d) - (?P<h>\d\d)\.(?P<mi>\d\d)\.(?P<s>\d\d)")
KNOWN_SUFFIXES = ("_wx", "_trim")
# what other tools leave at the end of a cut: «… - Trim» (Windows Photos / Clipchamp)
_OTHER_CUTS = re.compile(r" - trim$", re.I)
_COUNTER = re.compile(r"(?: \(\d+\)|_\d+|_+)$")      # « (2)» from a taken name, «_1» from segments, «_» from reserved


def recorded(name: str) -> float | None:
    """When the clip was recorded, from an NVIDIA name («Valorant 2023.03.28 - 21.15.06.02.DVR…»)."""
    m = NV_NAME.match(Path(name).stem)
    if not m:
        return None
    try:
        return datetime(int(m["y"]), int(m["mo"]), int(m["d"]), int(m["h"]), int(m["mi"]), int(m["s"])).timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def looks_cut(name: str, suffixes=()) -> bool:
    """A file named like something this add-on (or another trimmer) made from a clip."""
    stem = Path(name).stem
    for _ in range(3):                       # «…_wx_1 (2)» → «…_wx»
        new = _COUNTER.sub("", stem)
        if new == stem:
            break
        stem = new
    low = stem.lower()
    if _OTHER_CUTS.search(low):
        return True
    return any(sf and low.endswith(sf.lower()) for sf in (*KNOWN_SUFFIXES, *suffixes))


@dataclass
class ClipFile:
    path: str
    folder: str               # game folder name, "" for files in the root
    size: int
    mtime: float
    rec: float = 0.0          # recorded at: from the NVIDIA name, else the file time

    def __post_init__(self):
        if not self.rec:
            self.rec = recorded(self.path) or self.mtime

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
        return max((c.rec for c in self.clips), default=0.0)


def _clips_in(folder: Path, name: str, deep: bool) -> list[ClipFile]:
    out = []
    try:
        it = folder.rglob("*") if deep else folder.iterdir()
        for f in it:
            if any(part.startswith(".") for part in f.relative_to(folder).parts[:-1]):
                continue                              # .wxwx-trash and other hidden folders
            if f.suffix.lower() in CLIP_EXTS and f.is_file():
                st = f.stat()
                out.append(ClipFile(str(f), name, st.st_size, st.st_mtime))
    except OSError:
        pass
    out.sort(key=lambda c: c.rec, reverse=True)
    return out


def sort_clips(clips: list[ClipFile], how: str) -> list[ClipFile]:
    """new / old — by when it was recorded; big — by size; name — A→Z."""
    if how == "big":
        return sorted(clips, key=lambda c: c.size, reverse=True)
    if how == "name":
        return sorted(clips, key=lambda c: c.name.lower())
    return sorted(clips, key=lambda c: c.rec, reverse=how != "old")


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


def new_clips(folders: list[GameFolder], since: float, done: set[str], is_cut=None) -> list[ClipFile]:
    """Files that appeared since `since` — not the ones already cut, and not our own results."""
    out = [c for f in folders for c in f.clips
           if c.mtime > since and c.path not in done and not (is_cut and is_cut(c.path))]
    out.sort(key=lambda c: c.rec, reverse=True)
    return out
