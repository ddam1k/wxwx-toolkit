"""yt-dlp: command lines, reading its JSON and progress lines, naming errors (no Qt here).

Quality is the smaller side of the picture ("1080p" of a vertical Short is 1080×1920), so formats are
chosen with yt-dlp's sort  -S res:<H>  rather than a height filter.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

STEPS = (2160, 1440, 1080, 720, 480, 360)
FMTS = ("mp4o", "mp4", "orig")          # MP4 as the site gives it · MP4 that opens everywhere (H.264) · WebM/MKV
AFMTS = ("mp3", "m4a", "opus")
NAMING = {
    "title": "%(title).150B.%(ext)s",
    "author": "%(uploader,channel,creator|Unknown).60B — %(title).120B.%(ext)s",
    "date": "%(upload_date>%Y-%m-%d|)s · %(uploader,channel,creator|Unknown).60B — %(title).110B.%(ext)s",
}
COOKIES = ("none", "firefox", "chrome", "edge")
SITE_OF = {"youtube": "YouTube", "youtubetab": "YouTube", "instagram": "Instagram", "tiktok": "TikTok"}


def label(h: int) -> str:
    return "4K" if h >= 2160 else f"{h}p"


@dataclass
class Opts:
    what: str = "video"              # "video" | "audio"
    q: int = 0                       # 0 = best
    fmt: str = "mp4o"
    afmt: str = "mp3"
    part: tuple[float, float] | None = None
    subs: str | None = None          # language code, "auto" → automatic captions
    thumb: bool = False              # the cover as .jpg next to the file
    cookies: str = "none"
    proxy: str = ""                  # full address from core.proxy.normalize, "" = direct
    naming: str = "title"
    folder: str = ""
    subfolder: str = ""              # e.g. the playlist's name


@dataclass
class Info:
    url: str
    id: str = ""
    title: str = ""
    uploader: str = ""
    site: str = "site"
    duration: float = 0.0
    thumbnail: str = ""
    views: int = 0
    vertical: bool = False
    fps: float = 0.0
    heights: list[int] = field(default_factory=list)        # available qualities (STEPS), best first
    sizes: dict[str, float] = field(default_factory=dict)   # "<fmt>:<h>" / "audio" → bytes (estimate)
    subs: list[str] = field(default_factory=list)           # languages of real subtitles
    auto_subs: bool = False
    playlist: bool = False
    entries: list[dict] = field(default_factory=list)       # {id, title, duration, url}

    @property
    def max_h(self) -> int:
        return self.heights[0] if self.heights else 0


# ---------------------------------------------------------------- command lines
def _common(ffmpeg_dir: str | None, deno: str | None, cookies: str, proxy: str = "") -> list[str]:
    a = ["--color", "never", "--ignore-config", "--windows-filenames"]
    if ffmpeg_dir:
        a += ["--ffmpeg-location", ffmpeg_dir]
    if deno:
        a += ["--js-runtimes", f"deno:{deno}"]
    if cookies in COOKIES and cookies != "none":
        a += ["--cookies-from-browser", cookies]
    if proxy:
        a += ["--proxy", proxy]
    return a


def probe_args(url: str, playlist: bool, ffmpeg_dir=None, deno=None, cookies="none", proxy="") -> list[str]:
    a = _common(ffmpeg_dir, deno, cookies, proxy) + ["-J", "--skip-download"]
    a += ["--flat-playlist", "--yes-playlist"] if playlist else ["--no-playlist"]
    return a + ["--", url]


def sort_for(o: Opts) -> str:
    res = f"res:{o.q}" if o.q else "res"
    if o.fmt == "mp4":
        return f"{res},vcodec:h264,acodec:m4a"
    if o.fmt == "mp4o":
        return f"{res},ext:mp4:m4a"
    return res


def download_args(url: str, o: Opts, ffmpeg_dir=None, deno=None) -> list[str]:
    a = _common(ffmpeg_dir, deno, o.cookies, o.proxy)
    a += ["--no-playlist", "--newline", "--progress", "--no-mtime", "--continue", "--no-overwrites",
          "--progress-template",
          "download:WXP %(progress.downloaded_bytes)s/%(progress.total_bytes)s/%(progress.total_bytes_estimate)s/"
          "%(progress.speed)s/%(progress.eta)s/%(info.vcodec)s",
          "--progress-template", "postprocess:WXQ %(progress.postprocessor)s/%(progress.status)s",
          "--print", "after_move:WXF%(filepath)s",
          "--embed-metadata"]
    tmpl = NAMING.get(o.naming, NAMING["title"])
    if o.part:                                    # a piece never lands on top of the whole video
        tmpl = tmpl.replace(".%(ext)s", f" ({clock(o.part[0])}–{clock(o.part[1])}).%(ext)s")
    if o.subfolder:
        tmpl = safe_name(o.subfolder) + "/" + tmpl
    a += ["-P", o.folder or ".", "-o", tmpl]
    if o.what == "audio":
        a += ["-f", "ba[ext=m4a]/ba/b" if o.afmt == "m4a" else "ba/b", "-x", "--audio-format", o.afmt,
              "--embed-thumbnail"]
        if o.afmt == "mp3":
            a += ["--audio-quality", "320K"]
    else:
        a += ["-f", "bv*+ba/b", "-S", sort_for(o),
              "--merge-output-format", "webm/mkv" if o.fmt == "orig" else "mp4"]
        if o.subs:
            a += ["--write-subs", "--convert-subs", "srt",
                  "--sub-langs", "ru.*,en.*,-live_chat" if o.subs == "auto" else f"{o.subs}.*,{o.subs}"]
            if o.subs == "auto":
                a += ["--write-auto-subs"]
    if o.part:
        s, e = o.part
        a += ["--download-sections", f"*{s:.2f}-{e:.2f}", "--force-keyframes-at-cuts"]
    if o.thumb:
        a += ["--write-thumbnail", "--convert-thumbnails", "jpg"]
    return a + ["--", url]


def clock(sec: float) -> str:
    """For file names: 754 → "12.34", 3754 → "1.02.34" (no colons on Windows)."""
    sec = int(sec)
    h, m, s = sec // 3600, sec // 60 % 60, sec % 60
    return f"{h}.{m:02d}.{s:02d}" if h else f"{m}.{s:02d}"


def safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")
    return s[:80] or "playlist"


# ---------------------------------------------------------------- reading the JSON
def _res(f: dict) -> int:
    w, h = f.get("width") or 0, f.get("height") or 0
    return min(w, h) if w and h else (h or 0)


def _step(r: int) -> int:
    """1080 → 1080, 1072 → 1080 (odd encodes), 2026 → 2160."""
    for s in sorted(STEPS):
        if r <= s * 1.04:
            return s
    return STEPS[0]


def _size(f: dict, duration: float) -> float:
    if f.get("filesize"):
        return float(f["filesize"])
    if f.get("filesize_approx"):
        return float(f["filesize_approx"])
    tbr = f.get("tbr") or ((f.get("vbr") or 0) + (f.get("abr") or 0))
    return float(tbr) * 125 * duration if tbr and duration else 0.0


def _is_video(f):
    return (f.get("vcodec") or "none") != "none"


def _is_audio_only(f):
    return (f.get("acodec") or "none") != "none" and not _is_video(f)


def _pick_video(formats: list[dict], h: int, fmt: str) -> dict | None:
    """Roughly what -S would choose: biggest res ≤ h, then the codec/container the format wants, then bitrate."""
    vids = [f for f in formats if _is_video(f) and _res(f) and _step(_res(f)) <= h]
    if not vids:
        return None

    def key(f):
        vc = (f.get("vcodec") or "")
        pref = 0
        if fmt == "mp4" and vc.startswith(("avc", "h264")):
            pref = 1
        elif fmt == "mp4o" and f.get("ext") == "mp4":
            pref = 1
        return (_step(_res(f)), pref, f.get("tbr") or 0)
    return max(vids, key=key)


def _pick_audio(formats: list[dict], prefer_m4a: bool) -> dict | None:
    auds = [f for f in formats if _is_audio_only(f)]
    if not auds:
        return None
    return max(auds, key=lambda f: ((f.get("ext") == "m4a") if prefer_m4a else 0, f.get("abr") or f.get("tbr") or 0))


def parse_info(raw: str | dict, url: str) -> Info:
    d = json.loads(raw) if isinstance(raw, str) else raw
    site = SITE_OF.get(str(d.get("extractor_key") or d.get("ie_key") or "").lower(), None)
    if site is None:
        from .links import site as site_of
        site = site_of(url)
    inf = Info(url=url, id=str(d.get("id") or ""), title=str(d.get("title") or ""),
               uploader=str(d.get("uploader") or d.get("channel") or d.get("creator") or ""),
               site=site, thumbnail=_best_thumb(d), views=int(d.get("view_count") or 0))
    if d.get("_type") == "playlist" or d.get("entries") is not None:
        inf.playlist = True
        for e in d.get("entries") or []:
            if not e:
                continue
            eu = e.get("url") or e.get("webpage_url") or ""
            if not eu.startswith("http") and e.get("id") and site == "YouTube":
                eu = f"https://www.youtube.com/watch?v={e['id']}"
            inf.entries.append({"id": str(e.get("id") or ""), "title": str(e.get("title") or "—"),
                                "duration": float(e.get("duration") or 0), "url": eu})
        inf.duration = sum(e["duration"] for e in inf.entries)
        inf.uploader = inf.uploader or str(d.get("channel") or d.get("uploader_id") or "")
        return inf
    inf.duration = float(d.get("duration") or 0)
    formats = d.get("formats") or [d]
    w, h = d.get("width") or 0, d.get("height") or 0
    inf.vertical = bool(w and h and h > w)
    inf.fps = float(d.get("fps") or 0)
    steps = sorted({_step(_res(f)) for f in formats if _is_video(f) and _res(f)}, reverse=True)
    inf.heights = steps
    aud = _pick_audio(formats, True)
    a_size = _size(aud, inf.duration) if aud else 0.0
    for fmt in FMTS:
        for s in steps:
            v = _pick_video(formats, s, fmt)
            if v is None:
                continue
            has_audio = (v.get("acodec") or "none") != "none"
            inf.sizes[f"{fmt}:{s}"] = _size(v, inf.duration) + (0.0 if has_audio else a_size)
            if fmt == "mp4" and not (v.get("vcodec") or "").startswith(("avc", "h264")):
                inf.sizes[f"recode:{s}"] = 1
    inf.sizes["audio"] = a_size or inf.duration * 16_000
    inf.subs = sorted(k for k in (d.get("subtitles") or {}) if k != "live_chat")
    inf.auto_subs = bool(d.get("automatic_captions"))
    return inf


def _best_thumb(d: dict) -> str:
    th = d.get("thumbnails") or []
    good = [t for t in th if t.get("url") and not str(t.get("url")).endswith(".webp")]
    pool = good or [t for t in th if t.get("url")]
    if pool:
        best = max(pool, key=lambda t: ((t.get("width") or 0) * (t.get("height") or 0), t.get("preference") or 0))
        return str(best["url"])
    return str(d.get("thumbnail") or "")


def estimate(inf: Info, o: Opts) -> float:
    """Bytes for these options (0 when unknown)."""
    if o.what == "audio":
        size = inf.sizes.get("audio", 0.0)
        if o.afmt == "mp3":
            size = max(size, inf.duration * 40_000)       # 320 kbit/s
    else:
        h = o.q or inf.max_h
        size = inf.sizes.get(f"{o.fmt}:{h}") or 0.0
        if not size and inf.heights:
            lower = [s for s in inf.heights if s <= h] or inf.heights[-1:]
            size = inf.sizes.get(f"{o.fmt}:{lower[0]}", 0.0)
    if o.part and inf.duration:
        size *= max(0.0, min(1.0, (o.part[1] - o.part[0]) / inf.duration))
    return size


def needs_recode(inf: Info, o: Opts) -> bool:
    """«MP4 для всех» when the site has no H.264 at this quality (YouTube above 1080p) → we convert after."""
    if o.what != "video" or o.fmt != "mp4" or not inf.heights:
        return False
    return bool(inf.sizes.get(f"recode:{o.q or inf.max_h}"))


# ---------------------------------------------------------------- progress lines
def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_line(line: str) -> dict | None:
    """One stdout line → {"kind": "dl"|"pp"|"file", …} or None."""
    line = line.strip()
    if line.startswith("WXP "):
        parts = line[4:].split("/")
        if len(parts) < 6:
            return None
        done, total, est, speed, eta = (_num(p) for p in parts[:5])
        total = total or est
        return {"kind": "dl", "done": done or 0.0, "total": total or 0.0, "speed": speed or 0.0,
                "eta": eta, "audio": parts[5] == "none"}
    if line.startswith("WXQ "):
        pp, _, status = line[4:].partition("/")
        return {"kind": "pp", "pp": pp, "status": status}
    if line.startswith("WXF"):
        return {"kind": "file", "path": line[3:].strip()}
    return None


STAGE_OF_PP = {"Merger": "merge", "FFmpegMerger": "merge", "ExtractAudio": "audio", "FFmpegExtractAudio": "audio",
               "VideoConvertor": "convert", "FFmpegVideoConvertor": "convert", "EmbedThumbnail": "finish",
               "FFmpegMetadata": "finish", "Metadata": "finish", "SubtitlesConvertor": "finish",
               "FFmpegSubtitlesConvertor": "finish", "ThumbnailsConvertor": "finish", "FixupM3u8": "finish",
               "FFmpegFixupM3u8": "finish", "FixupM4a": "finish", "FFmpegFixupM4a": "finish"}


def stage_of_pp(name: str) -> str:
    return STAGE_OF_PP.get(name, "finish")


# ---------------------------------------------------------------- errors
_ERR = [
    ("login", ("login required", "sign in to confirm", "use --cookies", "cookies-from-browser", "requested content is not available",
               "rate-limit reached or login", "confirm your age", "age-restricted", "inappropriate for some users",
               "this account is private", "log in")),
    ("private", ("private video", "video is private")),
    ("cookies", ("could not copy chrome cookie", "failed to decrypt", "could not find firefox", "cookie database",
                 "permission denied", "dpapi")),
    ("unavailable", ("video unavailable", "has been removed", "is not available", "no video formats", "there's no video",
                     "does not exist", "not found", "http error 404")),
    ("geo", ("not available in your country", "geo restriction", "geo-restricted")),
    ("unsupported", ("unsupported url",)),
    ("network", ("unable to download", "getaddrinfo", "timed out", "connection", "http error 5", "ssl", "proxy",
                 "socks", "name resolution", "nodename nor servname")),
    ("ratelimit", ("http error 429", "too many requests")),
]


def error_kind(text: str) -> str:
    low = (text or "").lower()
    if "http error 429" in low or "too many requests" in low:
        return "ratelimit"
    for kind, needles in _ERR:
        if any(n in low for n in needles):
            return kind
    return "other"


def last_error(text: str) -> str:
    """The last «ERROR: …» line, shortened — shown under «подробнее»."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    errs = [ln for ln in lines if ln.startswith("ERROR")]
    msg = (errs or lines or [""])[-1]
    msg = re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?([\w-]+:\s*)?", "", msg)
    return msg[:300]
