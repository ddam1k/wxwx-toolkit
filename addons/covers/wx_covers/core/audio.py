"""Covers engine, all through ffmpeg / ffprobe (no Qt here, so it is tested anywhere).

read()          → what a file has: tags, duration, the embedded picture
render_cover()  → the picture as it will be stored: square (cropped, or whole with padding), sized, JPEG
write()         → a new file with that picture and those tags; the sound is copied untouched (-c copy)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field

AUDIO_EXT = (".mp3", ".m4a", ".flac")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".avif", ".jfif")
TAGS = ("title", "artist", "album", "year")
SIZES = ("600", "1000", "orig")
FITS = ("crop", "fit")
PADS = ("blur", "black", "white")
PAD_COLORS = {"black": "0x0b0b0c", "white": "0xf3f1ec"}
SQUARE_TOLERANCE = 4               # px: 1000×998 is a square, no question to ask
# what one cover adds to a file, roughly (JPEG q2): for the «+180 КБ» in the footer
COVER_KB = {"600": 70, "1000": 180, "orig": 420}
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DASH = re.compile(r"\s+[-—–]\s+")


@dataclass
class Track:
    path: str
    fmt: str = ""                    # mp3 / m4a / flac
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    duration: float = 0.0
    size: int = 0
    cover: bool = False              # has an embedded picture
    cover_w: int = 0
    cover_h: int = 0
    error: str = ""

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def tags(self) -> dict:
        return {k: getattr(self, k) for k in TAGS}


def is_audio(path: str) -> bool:
    return path.lower().endswith(AUDIO_EXT)


def is_image(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXT)


def run(args: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL,
                          creationflags=_NO_WINDOW)


def _tag(tags: dict, *names: str) -> str:
    low = {k.lower(): v for k, v in (tags or {}).items()}
    for n in names:
        v = low.get(n)
        if v:
            return str(v).strip()
    return ""


def parse_probe(path: str, data: dict) -> Track:
    fmt = data.get("format", {})
    tags = dict(fmt.get("tags") or {})
    t = Track(path=path, fmt=os.path.splitext(path)[1][1:].lower())
    pic = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "audio":
            tags = {**(s.get("tags") or {}), **tags}          # FLAC/OGG keep tags on the stream
        elif s.get("codec_type") == "video" and (s.get("disposition") or {}).get("attached_pic") and pic is None:
            pic = s
    t.title = _tag(tags, "title")
    t.artist = _tag(tags, "artist", "album_artist", "albumartist")
    t.album = _tag(tags, "album")
    y = _tag(tags, "date", "year", "tdrc", "tyer")
    t.year = y[:4] if re.match(r"^\d{4}", y) else y
    try:
        t.duration = float(fmt.get("duration") or 0)
    except ValueError:
        t.duration = 0.0
    try:
        t.size = int(fmt.get("size") or 0) or os.path.getsize(path)
    except (OSError, ValueError):
        t.size = 0
    if pic:
        t.cover, t.cover_w, t.cover_h = True, int(pic.get("width") or 0), int(pic.get("height") or 0)
    return t


def read(path: str, ffprobe: str) -> Track:
    try:
        r = run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", path], timeout=30)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[-300:] or "ffprobe failed")
        return parse_probe(path, json.loads(r.stdout.decode("utf-8", "replace") or "{}"))
    except Exception as e:                                # unreadable file still shows up in the list, with the reason
        t = Track(path=path, fmt=os.path.splitext(path)[1][1:].lower(), error=str(e))
        try:
            t.size = os.path.getsize(path)
        except OSError:
            pass
        return t


def image_size(path: str, ffprobe: str) -> tuple[int, int]:
    r = run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "json", path], timeout=20)
    try:
        s = json.loads(r.stdout.decode("utf-8", "replace"))["streams"][0]
        return int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError):
        raise RuntimeError("not an image") from None


def extract_cover(path: str, ffmpeg: str, dest: str) -> bool:
    """The embedded picture → dest (JPEG/PNG by dest's extension), for showing it in the list."""
    r = run([ffmpeg, "-y", "-v", "error", "-i", path, "-an", "-map", "0:v:0", "-frames:v", "1",
             "-vf", "scale='min(iw,512)':-2", dest], timeout=30)
    return r.returncode == 0 and os.path.isfile(dest) and os.path.getsize(dest) > 0


# ------------------------------------------------------------------ names
def guess(filename: str) -> tuple[str, str] | None:
    """«Artist - Title.mp3» → (artist, title)."""
    base = os.path.splitext(os.path.basename(filename))[0].strip()
    parts = _DASH.split(base)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        return None
    return parts[0].strip(), " - ".join(p.strip() for p in parts[1:])


def safe(text: str) -> str:
    s = _BAD.sub("_", text).strip().rstrip(". ")
    return s[:150]


def planned_name(tags: dict, fmt: str) -> str | None:
    a, n = (tags.get("artist") or "").strip(), (tags.get("title") or "").strip()
    if not a or not n:
        return None
    return f"{safe(a)} — {safe(n)}.{fmt}"


def free_name(path: str) -> str:
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


# ------------------------------------------------------------------ the picture
def is_square(w: int, h: int) -> bool:
    return abs(w - h) < SQUARE_TOLERANCE


def cover_graph(w: int, h: int, fit: str = "crop", pad: str = "blur", size: str = "1000") -> tuple[str, int]:
    """ffmpeg filter graph [0:v] → [out] and the side of the square it makes."""
    if fit != "fit" or is_square(w, h):
        s = min(w, h)
        g, side = f"[0:v]crop={s}:{s}:{(w - s) // 2}:{(h - s) // 2}", s
    elif pad in PAD_COLORS:
        m = max(w, h)
        g, side = f"[0:v]pad={m}:{m}:{(m - w) // 2}:{(m - h) // 2}:color={PAD_COLORS[pad]}", m
    else:
        m = max(w, h)
        # shrink → blur → stretch back: a soft, even background for any picture size, and cheap
        g = (f"[0:v]split[a][b];[a]scale=72:72:force_original_aspect_ratio=increase,crop=72:72,"
             f"boxblur=luma_radius=8:luma_power=2,scale={m}:{m}:flags=bicubic,eq=brightness=-0.06:saturation=1.15[bg];"
             f"[bg][b]overlay={(m - w) // 2}:{(m - h) // 2}")
        side = m
    final = side if size == "orig" else min(side, int(size))
    if final != side:
        g += f",scale={final}:{final}:flags=lanczos"
    return g + ",format=yuvj420p[out]", final


def render_cover(image: str, ffmpeg: str, ffprobe: str, dest: str, fit="crop", pad="blur", size="1000",
                 dims: tuple[int, int] | None = None) -> tuple[str, int]:
    w, h = dims or image_size(image, ffprobe)
    graph, side = cover_graph(w, h, fit, pad, size)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    r = run([ffmpeg, "-y", "-v", "error", "-i", image, "-filter_complex", graph, "-map", "[out]",
             "-frames:v", "1", "-q:v", "2", dest], timeout=60)
    if r.returncode != 0 or not os.path.isfile(dest):
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[-300:] or "could not make the cover")
    return dest, side


# ------------------------------------------------------------------ writing
KEEP = "keep"          # cover argument: leave the picture the file has
REMOVE = "remove"      # … or take it out


def write_args(src: str, dest: str, ffmpeg: str, cover: str, tags: dict | None, had_cover: bool) -> list[str]:
    """cover: KEEP | REMOVE | path to a ready JPEG. tags: only the ones to change («» clears one)."""
    fmt = os.path.splitext(dest)[1][1:].lower()
    a = [ffmpeg, "-y", "-v", "error", "-i", src]
    new = cover not in (KEEP, REMOVE)
    if new:
        a += ["-i", cover]
    a += ["-map", "0:a"]
    if new:
        a += ["-map", "1:0"]
    elif cover == KEEP and had_cover:
        a += ["-map", "0:v:0"]
    a += ["-c", "copy", "-map_metadata", "0"]
    for k, v in (tags or {}).items():
        a += ["-metadata", f"{'date' if k == 'year' else k}={v}"]
    if new or (cover == KEEP and had_cover):
        a += ["-disposition:v:0", "attached_pic"]
        if new:
            a += ["-metadata:s:v:0", "title=Album cover", "-metadata:s:v:0", "comment=Cover (front)"]
    if fmt == "mp3":
        a += ["-id3v2_version", "3"]
    a += [dest]
    return a


def write(src: str, dest: str, ffmpeg: str, cover: str = KEEP, tags: dict | None = None,
          had_cover: bool = False) -> str:
    """Writes into a temp file next to dest, then puts it in place: a failure never leaves half a file."""
    stem, ext = os.path.splitext(dest)
    tmp = f"{stem}.wxwx-tmp{ext}"
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    r = run(write_args(src, tmp, ffmpeg, cover, tags, had_cover), timeout=300)
    if r.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[-400:] or "ffmpeg failed")
    os.replace(tmp, dest)
    return dest


@dataclass
class Change:
    """What to do with one file."""
    path: str
    cover: str = KEEP                 # KEEP | REMOVE | path of the chosen image
    fit: str = "crop"
    pad: str = "blur"
    tags: dict = field(default_factory=dict)        # only changed ones
    had_cover: bool = False


def save(ch: Change, ffmpeg: str, ffprobe: str, work: str, size="1000", rename=False, copies_to: str = "",
         full_tags: dict | None = None, cache: dict | None = None) -> str:
    """Applies a Change; returns where the file is now. cache: rendered covers shared by tracks in one save."""
    cover = ch.cover
    if cover not in (KEEP, REMOVE):
        key = (cover, ch.fit, ch.pad, size)
        if cache is not None and key in cache:
            cover = cache[key]
        else:
            dest = os.path.join(work, f"cover-{abs(hash(key)) % 10**10}.jpg")
            cover = render_cover(ch.cover, ffmpeg, ffprobe, dest, ch.fit, ch.pad, size)[0]
            if cache is not None:
                cache[key] = cover
    fmt = os.path.splitext(ch.path)[1][1:].lower()
    name = os.path.basename(ch.path)
    if rename:
        name = planned_name(full_tags or ch.tags, fmt) or name
    if copies_to:
        dest = free_name(os.path.join(copies_to, name))
        return write(ch.path, dest, ffmpeg, cover, ch.tags, ch.had_cover)
    write(ch.path, ch.path, ffmpeg, cover, ch.tags, ch.had_cover)
    target = os.path.join(os.path.dirname(ch.path), name)
    if os.path.normcase(os.path.abspath(target)) == os.path.normcase(os.path.abspath(ch.path)):
        return ch.path
    if os.path.exists(target) and not os.path.samefile(target, ch.path):     # case-only renames are the same file
        target = free_name(target)
    os.replace(ch.path, target)
    return target
