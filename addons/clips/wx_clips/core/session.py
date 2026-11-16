"""What the user is cutting: clips, their single cut or segments, keys, edit mode (no Qt here)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .ffmpeg import MediaInfo

N_COLORS = 6
MIN_LEN = 0.5


@dataclass(eq=False)
class Seg:
    a: float
    b: float
    col: int = 0

    @property
    def length(self) -> float:
        return self.b - self.a


@dataclass(eq=False)
class Clip:
    path: str
    info: MediaInfo | None = None
    thumb: str | None = None
    frames: list = field(default_factory=list)
    mode: str = "single"                 # single | multi
    single: Seg | None = None
    multi: list = field(default_factory=list)
    sel: int = 0
    pend: float | None = None            # start key waiting for its end key (multi)
    edit: Seg | None = None              # segment whose edges I / O move (multi)
    merge: bool = True
    tracks: list = field(default_factory=list)   # bool per audio track
    status: str = ""                     # "" | queued | work | done | error
    progress: float = 0.0
    error: str = ""
    c_idx: int | None = None             # which segment C plays next

    # ------------------------------------------------ basics
    @property
    def dur(self) -> float:
        return self.info.duration if self.info else 0.0

    @property
    def fps(self) -> float:
        return self.info.fps if self.info else 60.0

    def ready(self, info: MediaInfo) -> None:
        self.info = info
        if self.single is None or self.single.b <= 0:
            self.single = Seg(0.0, info.duration)
        if len(self.tracks) != len(info.audio_tracks):
            self.tracks = [True] * len(info.audio_tracks)

    def segs(self) -> list[Seg]:
        if self.mode == "single":
            return [self.single] if self.single else []
        return self.multi

    def kept(self) -> float:
        s = self.segs()
        return sum(x.length for x in s) if s else self.dur

    def trimmed(self) -> bool:
        if self.mode == "multi":
            return bool(self.multi)
        return bool(self.single) and (self.single.a > 0.05 or self.single.b < self.dur - 0.05)

    def out_files(self) -> int:
        return max(1, len(self.multi)) if self.mode == "multi" and not self.merge else 1

    def ranges(self) -> list[tuple[float, float]]:
        return [(s.a, s.b) for s in self.segs()]

    def track_indexes(self) -> list[int]:
        return [i for i, on in enumerate(self.tracks) if on]

    # ------------------------------------------------ mode
    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        if mode == "multi" and not self.multi and self.trimmed():
            self.multi = [Seg(self.single.a, self.single.b, 0)]
        if mode == "single" and self.multi:
            self.single = Seg(self.multi[0].a, max(s.b for s in self.multi))
        self.mode, self.sel, self.pend, self.edit = mode, 0, None, None

    # ------------------------------------------------ keys
    def seg_at(self, t: float) -> int:
        return next((i for i, s in enumerate(self.multi) if s.a - 1e-3 <= t <= s.b + 1e-3), -1)

    def _resort(self, s: Seg) -> None:
        self.multi.sort(key=lambda x: x.a)
        self.sel = self.multi.index(s)

    def key_in(self, t: float) -> str:
        """I. Returns what happened: moved | pending."""
        if self.mode == "single":
            self.single.a = max(0.0, min(t, self.single.b - MIN_LEN))
            return "moved"
        if self.edit is not None:
            self.edit.a = max(0.0, min(t, self.edit.b - MIN_LEN))
            self._resort(self.edit)
            return "moved"
        i = self.seg_at(t)
        if i >= 0:
            s = self.multi[i]
            s.a = min(t, s.b - MIN_LEN)
            self.sel = i
            return "moved"
        self.pend = t
        return "pending"

    def key_out(self, t: float) -> str:
        """O. Returns: moved | added | too_short | no_room."""
        if self.mode == "single":
            self.single.b = min(self.dur, max(t, self.single.a + MIN_LEN))
            return "moved"
        if self.edit is not None:
            self.edit.b = min(self.dur, max(t, self.edit.a + MIN_LEN))
            self._resort(self.edit)
            return "moved"
        if self.pend is not None:
            if t <= self.pend + 0.3:
                return "too_short"
            a, self.pend = self.pend, None
            return self.add(a, t)
        i = self.seg_at(t)
        if i >= 0:
            s = self.multi[i]
            s.b = max(t, s.a + MIN_LEN)
            self.sel = i
            return "moved"
        prev = max((s.b for s in self.multi if s.b <= t), default=0.0)
        return self.add(max(prev, t - 5), t)

    def add(self, a: float, b: float) -> str:
        for s in self.multi:                       # new segments never overlap old ones
            if s.a < b and s.b > a:
                if s.a <= a:
                    a = s.b
                else:
                    b = s.a
        if b - a < 0.3:
            return "no_room"
        used = {s.col for s in self.multi}
        col = next((k for k in range(N_COLORS) if k not in used), len(self.multi) % N_COLORS)
        s = Seg(a, b, col)
        self.multi.append(s)
        self._resort(s)
        return "added"

    def delete(self, i: int) -> None:
        if 0 <= i < len(self.multi):
            if self.edit is self.multi[i]:
                self.edit = None
            del self.multi[i]
            self.sel = max(0, min(self.sel, len(self.multi) - 1))

    def set_time(self, i: int, which: str, t: float) -> bool:
        """Typed time for segment i (overlaps allowed). False if it had to be clamped."""
        s = self.segs()[i]
        if which == "a":
            v = max(0.0, min(t, s.b - MIN_LEN))
        else:
            v = min(self.dur, max(t, s.a + MIN_LEN))
        setattr(s, which, v)
        if self.mode == "multi":
            self._resort(s)
        return abs(v - t) < 0.01

    def toggle_edit(self, i: int) -> None:
        s = self.multi[i] if 0 <= i < len(self.multi) else None
        self.edit = None if self.edit is s else s
        self.pend = None
        if self.edit is not None:
            self.sel = i

    def next_c(self) -> int:
        n = len(self.multi)
        self.c_idx = 0 if self.c_idx is None or n == 0 else (self.c_idx + 1) % n
        return self.c_idx
