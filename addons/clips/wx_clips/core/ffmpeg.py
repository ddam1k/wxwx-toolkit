"""Locating ffmpeg/ffprobe, probing media, thumbnails and capability checks (no Qt here)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: no console flashes on Windows

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".gif",
              ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp", ".ogv"}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def find_tool(name: str) -> str | None:
    exe = name + (".exe" if os.name == "nt" else "")
    for d in (app_dir() / "bin", app_dir()):
        p = d / exe
        if p.is_file():
            return str(p)
    return shutil.which(name)


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


def set_tools(ffmpeg: str | None, ffprobe: str | None) -> None:
    """Use other ffmpeg/ffprobe binaries (the toolkit passes its shared copies)."""
    global FFMPEG, FFPROBE
    if ffmpeg:
        FFMPEG = ffmpeg
    if ffprobe:
        FFPROBE = ffprobe


def gpu_name() -> str | None:
    """Name of the NVIDIA card via nvidia-smi (ships with the driver), None if there is none."""
    exe = shutil.which("nvidia-smi")
    if not exe and os.name == "nt":
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        exe = str(cand) if cand.is_file() else None
    if not exe:
        return None
    try:
        r = run([exe, "--query-gpu=name", "--format=csv,noheader"], 10)
        name = r.stdout.decode("utf-8", "replace").strip().splitlines()[0].strip()
        return name or None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


@dataclass
class MediaInfo:
    path: str
    size_mb: float
    width: int
    height: int
    fps: float
    duration: float
    vcodec: str = ""
    acodec: str | None = None
    abitrate_k: float | None = None
    audio_tracks: list = field(default_factory=list)   # one title per audio stream ("" if none)
    mtime: float = 0.0

    @property
    def short_side(self) -> int:
        return max(1, min(self.width, self.height))

    @property
    def vertical(self) -> bool:
        return self.height > self.width

    @property
    def total_kbps(self) -> float:
        return self.size_mb * 1048576 * 8 / 1000 / max(self.duration, 0.1)


def run(args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)


def _ratio(value: str | None) -> float:
    try:
        num, _, den = (value or "").partition("/")
        n, d = float(num), float(den or 1)
        return n / d if d else 0.0
    except ValueError:
        return 0.0


def _rotation(stream: dict) -> int:
    try:
        rot = int(float(stream.get("tags", {}).get("rotate", 0)))
    except ValueError:
        rot = 0
    for sd in stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                rot = int(float(sd["rotation"]))
            except (TypeError, ValueError):
                pass
    return rot


def probe(path: str) -> MediaInfo | None:
    if not FFPROBE:
        return None
    try:
        r = run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], 30)
        data = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if not video:
        return None
    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    if not w or not h:
        return None
    if abs(_rotation(video)) % 180 == 90:
        w, h = h, w
    fps = _ratio(video.get("avg_frame_rate"))
    if not 0 < fps <= 240:
        fps = _ratio(video.get("r_frame_rate"))
    if not 0 < fps <= 240:
        fps = 30.0
    try:
        duration = float(fmt.get("duration") or video.get("duration") or 0)
    except ValueError:
        duration = 0.0
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    abr = None
    if audio and audio.get("bit_rate"):
        try:
            abr = int(audio["bit_rate"]) / 1000
        except ValueError:
            pass
    tracks = [str((s.get("tags") or {}).get("title") or (s.get("tags") or {}).get("handler_name") or "").strip()
              for s in streams if s.get("codec_type") == "audio"]
    tracks = ["" if t.lower() in ("soundhandler", "sound handler", "") else t for t in tracks]
    return MediaInfo(
        path=path, size_mb=os.path.getsize(path) / 1048576, width=w, height=h, fps=round(fps, 3),
        duration=max(duration, 0.1), vcodec=video.get("codec_name", ""),
        acodec=audio.get("codec_name") if audio else None, abitrate_k=abr,
        audio_tracks=tracks, mtime=os.path.getmtime(path),
    )


def frame(path: str, t: float, width: int = 320) -> bytes | None:
    """One JPEG frame at t seconds (fast keyframe seek)."""
    if not FFMPEG:
        return None
    try:
        r = run([FFMPEG, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1",
                 "-vf", f"scale={width}:-2", "-q:v", "5", "-f", "image2pipe", "-c:v", "mjpeg", "-"], 20)
        return r.stdout if r.returncode == 0 and r.stdout else None
    except (OSError, subprocess.SubprocessError):
        return None


def thumbnail(path: str, duration: float, width: int = 168) -> bytes | None:
    if not FFMPEG:
        return None
    t = min(1.0, duration / 3)
    base = ["-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe", "-c:v", "png", "-"]
    for pre in (["-ss", f"{t:.2f}"], []):
        try:
            r = run([FFMPEG, "-v", "error", *pre, "-i", path, *base], 20)
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def list_encoders() -> set[str]:
    if not FFMPEG:
        return set()
    try:
        out = run([FFMPEG, "-hide_banner", "-encoders"], 20).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return set()
    return set(re.findall(r"^\s*V\S*\s+(\S+)", out, re.M))


def encoder_check(name: str) -> tuple[bool, str]:
    """Actually try to encode a few frames: NVENC is listed even without an NVIDIA GPU.
    Returns (works, ffmpeg error text)."""
    if not FFMPEG:
        return False, "ffmpeg не найден"
    try:
        r = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                 "color=black:s=640x360:r=30:d=0.5", "-pix_fmt", "yuv420p", "-c:v", name, "-f", "null", "-"], 30)
        return r.returncode == 0, r.stderr.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def encoder_works(name: str) -> bool:
    return encoder_check(name)[0]


def nvenc_hint(error: str) -> str:
    """Short human hint for a failed NVENC check."""
    e = error.lower()
    if "api version" in e or "driver does not support" in e or "nvenc api" in e:
        return "обнови драйвер NVIDIA"
    if "cannot load" in e or "nvcuda" in e or "no nvenc capable devices" in e or "no capable devices" in e:
        return "NVIDIA не найдена"
    return "NVENC не запустился"


def collect_paths(paths: list[str]) -> list[str]:
    """Expand dropped folders into video files, keep order, drop non-video."""
    out: list[str] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            out += sorted(str(f) for f in pp.rglob("*") if f.suffix.lower() in VIDEO_EXTS and f.is_file())
        elif pp.is_file() and pp.suffix.lower() in VIDEO_EXTS:
            out.append(str(pp))
    return out
