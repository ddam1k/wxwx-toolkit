"""What to do with the pictures: presets, format, quality, size, privacy, names (no Qt here)."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass

# what Qt reads itself; HEIC / AVIF / others go through ffmpeg first
QT_READ = (".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff")
FF_READ = (".heic", ".heif", ".avif", ".jxl", ".tga", ".dds", ".psd")
IMAGE_EXT = QT_READ + FF_READ
FORMATS = ("orig", "jpg", "webp", "avif", "png")
SIZES = (0, 3840, 2560, 1920, 1280)
Q_MIN, Q_MAX = 40, 100
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
EXT_FMT = {".jpg": "jpg", ".jpeg": "jpg", ".jfif": "jpg", ".png": "png", ".webp": "webp", ".avif": "avif"}


@dataclass
class Opts:
    preset: str = "web"
    fmt: str = "webp"          # orig | jpg | webp | avif | png
    q: int = 80
    long: int = 1920           # longest side; 0 = keep
    strip: bool = True         # drop camera / place data

    def key(self) -> tuple:
        return (self.fmt, self.q, self.long, self.strip)

    def to_dict(self) -> dict:
        return asdict(self)


PRESETS = {
    "web": Opts("web", "webp", 80, 1920, True),
    "tg": Opts("tg", "jpg", 85, 2560, True),
    "light": Opts("light", "webp", 70, 1280, True),
    "loss": Opts("loss", "orig", 100, 0, False),
}


def from_dict(d: dict | None) -> Opts:
    o = Opts()
    for k, v in (d or {}).items():
        if hasattr(o, k):
            setattr(o, k, v)
    o.fmt = o.fmt if o.fmt in FORMATS else "webp"
    o.q = max(Q_MIN, min(Q_MAX, int(o.q or 80)))
    o.long = max(0, int(o.long or 0))
    return o


def is_image(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXT)


def needs_ffmpeg(path: str) -> bool:
    return path.lower().endswith(FF_READ)


def src_fmt(path: str) -> str:
    """What a file is now, as one of our formats (BMP/TIFF/HEIC… become «jpg» for «Исходный»)."""
    return EXT_FMT.get(os.path.splitext(path)[1].lower(), "jpg")


def out_fmt(path: str, o: Opts, alpha: bool = False) -> str:
    if o.fmt != "orig":
        return o.fmt
    f = src_fmt(path)
    if f == "jpg" and alpha:
        return "png"           # a transparent GIF/TIFF kept «as is» must not lose its transparency
    return f


def lossless(path: str, o: Opts) -> bool:
    return out_fmt(path, o) == "png"


def dims(w: int, h: int, long: int) -> tuple[int, int]:
    """Downsize to the longest side; never upscale."""
    if not long or max(w, h) <= long:
        return w, h
    k = long / max(w, h)
    return max(1, round(w * k)), max(1, round(h * k))


def quality_word(q: int) -> str:
    return "q95" if q >= 95 else "q85" if q >= 85 else "q75" if q >= 75 else "q60" if q >= 60 else "q40"


def matches(o: Opts) -> str:
    """Which preset these settings are, or «own»."""
    for k, p in PRESETS.items():
        if p.key() == o.key():
            return k
    return "own"


# ------------------------------------------------------------------ names
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def out_name(path: str, fmt: str, suffix: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return _BAD.sub("_", f"{stem}{suffix}") + "." + fmt


def free_name(path: str, taken: set[str] | None = None) -> str:
    taken = taken if taken is not None else set()
    stem, ext = os.path.splitext(path)
    cand, n = path, 2
    while os.path.exists(cand) or os.path.normcase(cand) in taken:
        cand = f"{stem} ({n}){ext}"
        n += 1
    taken.add(os.path.normcase(cand))
    return cand


# ------------------------------------------------------------------ ffmpeg (AVIF out, HEIC & co in)
def avif_crf(q: int) -> int:
    """q 40…100 → libaom crf 48…14 (lower = better)."""
    q = max(Q_MIN, min(Q_MAX, q))
    return round(48 - (q - Q_MIN) * (34 / (Q_MAX - Q_MIN)))


def avif_args(ffmpeg: str, src_png: str, dest: str, q: int) -> list[str]:
    return [ffmpeg, "-y", "-v", "error", "-i", src_png, "-frames:v", "1", "-c:v", "libaom-av1",
            "-still-picture", "1", "-cpu-used", "6", "-row-mt", "1", "-crf", str(avif_crf(q)),
            "-pix_fmt", "yuv420p", dest]


def decode_args(ffmpeg: str, src: str, dest_png: str) -> list[str]:
    return [ffmpeg, "-y", "-v", "error", "-i", src, "-frames:v", "1", "-map", "0:v:0", dest_png]


def run(args: list[str], timeout: float = 180) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=_NO_WINDOW)


def ff_error(r: subprocess.CompletedProcess) -> str:
    return r.stderr.decode("utf-8", "replace").strip()[-300:] or f"ffmpeg exited with {r.returncode}"
