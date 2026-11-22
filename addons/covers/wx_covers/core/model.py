"""What the user changed in each track, before anything is written."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import audio
from .audio import KEEP, REMOVE, TAGS


@dataclass
class Item:
    track: audio.Track
    id: int = 0
    cover: str = KEEP              # KEEP | REMOVE | path of a chosen picture
    cover_dims: tuple[int, int] = (0, 0)
    fit: str = "crop"
    pad: str = "blur"
    tags: dict = field(default_factory=dict)       # current values of all TAGS
    sel: bool = False
    saved: bool = False
    err: str = ""
    source: str = ""               # «Сохранёнки» when another add-on sent it
    thumb: str = ""                # extracted picture of the file, for the list

    def __post_init__(self):
        if not self.tags:
            self.tags = self.track.tags()

    @property
    def path(self) -> str:
        return self.track.path

    @property
    def new_cover(self) -> bool:
        return self.cover not in (KEEP, REMOVE)

    @property
    def has_cover(self) -> bool:
        """After the changes."""
        return self.new_cover or (self.cover == KEEP and self.track.cover)

    @property
    def wide(self) -> bool:
        w, h = self.cover_dims
        return self.new_cover and w > 0 and not audio.is_square(w, h)

    def changed_tags(self) -> dict:
        old = self.track.tags()
        return {k: v for k, v in self.tags.items() if (v or "") != (old.get(k) or "")}

    @property
    def dirty(self) -> bool:
        return self.cover != KEEP or bool(self.changed_tags())

    def change(self) -> audio.Change:
        return audio.Change(self.path, self.cover, self.fit, self.pad, self.changed_tags(), self.track.cover)

    def reset(self) -> None:
        self.cover, self.cover_dims, self.fit, self.pad = KEEP, (0, 0), "crop", "blur"
        self.tags = self.track.tags()

    def display_name(self) -> str:
        return self.tags.get("title") or os.path.splitext(self.track.name)[0]

    def planned_name(self) -> str:
        return audio.planned_name(self.tags, self.track.fmt) or self.track.name


def same(items: list[Item], key) -> object:
    """The shared value of the picked tracks, or None when they differ."""
    vals = {key(i) for i in items}
    return vals.pop() if len(vals) == 1 else None


def guess_tags(items: list[Item]) -> int:
    """Fills artist/title from «Artist - Title.mp3» where the title is empty. Returns how many changed."""
    n = 0
    for it in items:
        if it.tags.get("title"):
            continue
        g = audio.guess(it.track.name)
        if g:
            it.tags["artist"] = it.tags.get("artist") or g[0]
            it.tags["title"] = g[1]
            it.saved = False
            n += 1
    return n


def can_guess(items: list[Item]) -> bool:
    return any(not it.tags.get("title") and audio.guess(it.track.name) for it in items)


def set_tag(items: list[Item], key: str, value: str) -> None:
    if key not in TAGS:
        raise KeyError(key)
    for it in items:
        it.tags[key] = value.strip()
        it.saved = False


def set_cover(items: list[Item], path: str, dims: tuple[int, int]) -> None:
    for it in items:
        it.cover, it.cover_dims, it.saved = path, dims, False


def remove_cover(items: list[Item]) -> None:
    for it in items:
        it.cover = REMOVE if it.track.cover else KEEP
        it.cover_dims, it.saved = (0, 0), False


def added_kb(items: list[Item], size: str) -> int:
    return sum(audio.COVER_KB[size] for i in items if i.dirty and i.new_cover and not i.track.cover)
