"""Turning EncodeSettings + MediaInfo into ffmpeg arguments, size estimates and output paths."""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

from .ffmpeg import MediaInfo
from .settings import CPU_ENCODERS, EFFICIENCY, GPU_ENCODERS, EncodeSettings

MP4_COPYABLE_AUDIO = {"aac", "mp3", "ac3", "eac3", "alac", "opus", "flac"}
WEBM_COPYABLE_AUDIO = {"opus", "vorbis"}
SUFFIX = "_wx"


# ---------- quality ----------
def equivalent_crf(quality: int) -> float:
    """Slider 0..100 → x264-like CRF 34..18 (codec independent scale used for estimates)."""
    return 34 - quality * 0.16


def quality_value(s: EncodeSettings) -> int:
    q = s.quality
    if s.encoder == "gpu":
        return round(36 - q * 0.17)            # NVENC -cq
    if s.codec in ("av1", "vp9"):
        return round(52 - q * 0.30)            # 0..63 scale
    return round(equivalent_crf(q))            # x264 / x265


def quality_word(q: int) -> str:
    from .i18n import t
    words = t("q_words")
    return words[0 if q >= 85 else 1 if q >= 65 else 2 if q >= 45 else 3 if q >= 25 else 4]


# ---------- geometry ----------
def out_size(s: EncodeSettings, m: MediaInfo) -> tuple[int, int]:
    w, h = m.width, m.height
    if s.res and m.short_side > s.res:
        k = s.res / m.short_side
        w, h = w * k, h * k
    if s.is_gif:
        return max(2, round(w)), max(2, round(h))
    return max(2, round(w / 2) * 2), max(2, round(h / 2) * 2)


def out_fps(s: EncodeSettings, m: MediaInfo) -> float:
    t = s.fps_target
    fps = m.fps if (t is None or m.fps <= t + 0.5) else float(t)
    return min(fps, 50.0) if s.is_gif else fps


def _scale_needed(s: EncodeSettings, m: MediaInfo) -> bool:
    return out_size(s, m) != (m.width, m.height)


# ---------- audio ----------
def audio_plan(s: EncodeSettings, m: MediaInfo) -> tuple[list[str], float]:
    if s.is_gif or s.audio == "none" or not m.acodec:
        return ["-an"], 0.0
    mp4 = s.format == "mp4"
    if s.audio == "keep":
        ok = MP4_COPYABLE_AUDIO if mp4 else WEBM_COPYABLE_AUDIO
        if m.acodec in ok:
            return ["-c:a", "copy"], m.abitrate_k or 160.0
        return (["-c:a", "aac", "-b:a", "192k"], 192.0) if mp4 else (["-c:a", "libopus", "-b:a", "160k"], 160.0)
    return (["-c:a", "aac", "-b:a", "128k"], 128.0) if mp4 else (["-c:a", "libopus", "-b:a", "96k"], 96.0)


# ---------- bitrate targets ----------
def target_total_mb(s: EncodeSettings, m: MediaInfo) -> float:
    mb = s.size_mb if s.mode == "size" else m.size_mb / s.ratio
    return min(mb, m.size_mb)


def target_video_kbps(s: EncodeSettings, m: MediaInfo) -> int:
    _, audio_k = audio_plan(s, m)
    total_k = target_total_mb(s, m) * 1048576 * 8 / 1000 / max(m.duration, 0.1)
    return max(50, int(total_k * 0.96 - audio_k))   # 4 % container/overshoot headroom


# ---------- arguments ----------
def encoder_name(s: EncodeSettings) -> str:
    return GPU_ENCODERS[s.codec] if s.encoder == "gpu" else CPU_ENCODERS[s.codec]


def build_args(s: EncodeSettings, m: MediaInfo, out_path: str) -> list[str]:
    """Arguments for ffmpeg (without the executable). Progress goes to stdout as key=value."""
    a = ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
         "-i", m.path]
    w, h = out_size(s, m)
    fps = out_fps(s, m)
    fps_changed = abs(fps - m.fps) > 0.01

    if s.is_gif:
        chain = []
        if fps_changed:
            chain.append(f"fps={fps:g}")
        if _scale_needed(s, m):
            chain.append(f"scale={w}:{h}:flags=lanczos")
        chain.append(f"split[a][b];[a]palettegen=max_colors={s.colors}:stats_mode=diff[p];"
                     f"[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
        return a + ["-vf", ",".join(chain), "-loop", "0", out_path]

    vf = []
    if _scale_needed(s, m):
        vf.append(f"scale={w}:{h}:flags=lanczos")
    if fps_changed:
        vf.append(f"fps={fps:g}")
    if vf:
        a += ["-vf", ",".join(vf)]

    audio_args, _ = audio_plan(s, m)
    a += ["-map", "0:v:0"]
    if audio_args != ["-an"]:
        a += ["-map", "0:a:0?"]

    enc = encoder_name(s)
    a += ["-c:v", enc, "-pix_fmt", "yuv420p"]
    gpu = s.encoder == "gpu"

    if s.mode == "quality":
        q = str(quality_value(s))
        if gpu:
            a += ["-rc", "vbr", "-cq", q, "-b:v", "0", "-preset", "p5"]
        elif enc == "libsvtav1":
            a += ["-crf", q, "-preset", "7"]
        elif enc == "libvpx-vp9":
            a += ["-crf", q, "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "3"]
        else:
            a += ["-crf", q, "-preset", "medium"]
    else:
        kb = target_video_kbps(s, m)
        a += ["-b:v", f"{kb}k"]
        if gpu:
            a += ["-rc", "vbr", "-maxrate", f"{int(kb * 1.3)}k", "-bufsize", f"{kb * 2}k", "-preset", "p5"]
        elif enc == "libsvtav1":
            a += ["-preset", "7"]
        elif enc == "libvpx-vp9":
            a += ["-maxrate", f"{int(kb * 1.3)}k", "-bufsize", f"{kb * 2}k",
                  "-row-mt", "1", "-deadline", "good", "-cpu-used", "3"]
        else:
            a += ["-maxrate", f"{int(kb * 1.3)}k", "-bufsize", f"{kb * 2}k", "-preset", "medium"]

    if enc == "libx265":
        a += ["-x265-params", "log-level=error"]
    if s.format == "mp4" and s.codec == "h265":
        a += ["-tag:v", "hvc1"]
    a += audio_args
    if s.format == "mp4":
        a += ["-movflags", "+faststart"]
    return a + [out_path]


def preview(ffmpeg_args: list[str]) -> str:
    """Readable command for the UI (without progress plumbing)."""
    skip_next = False
    parts = ["ffmpeg"]
    for i, arg in enumerate(ffmpeg_args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-progress", "-loglevel"):
            skip_next = True
            continue
        if arg in ("-hide_banner", "-nostdin", "-nostats", "-y"):
            continue
        if i == len(ffmpeg_args) - 1 or (i > 0 and ffmpeg_args[i - 1] == "-i"):
            arg = os.path.basename(arg)
        parts.append(subprocess.list2cmdline([arg]) if any(c in arg for c in ' ;[]"') else arg)
    return " ".join(parts)


# ---------- estimate ----------
def estimate_mb(s: EncodeSettings, m: MediaInfo) -> float:
    w, h = out_size(s, m)
    fps = out_fps(s, m)
    if s.is_gif:
        colors = 0.35 + 0.65 * s.colors / 256
        return max(0.05, w * h * fps * m.duration * 0.11 * colors / 1048576)
    _, audio_k = audio_plan(s, m)
    if s.mode != "quality":
        return target_total_mb(s, m)
    crf = equivalent_crf(s.quality)
    bpp = 0.08 * math.pow(2, (23 - crf) / 6) * EFFICIENCY[s.codec] * (1.15 if s.encoder == "gpu" else 1.0)
    video_k = w * h * fps * bpp / 1000
    src_video_k = max(50.0, m.total_kbps - (m.abitrate_k or 0))
    video_k = min(video_k, src_video_k * 1.05)
    return max(0.05, (video_k + audio_k) * 1000 / 8 * m.duration / 1048576)


# ---------- output path ----------
def output_path(src: str, fmt: str, out_mode: str = "beside", out_dir: str | None = None,
                suffix: str = SUFFIX) -> str:
    sp = Path(src)
    if out_mode == "subfolder":
        folder = sp.parent / "compressed"
    elif out_mode in ("custom", "toolkit") and out_dir:
        folder = Path(out_dir)
    else:
        folder = sp.parent
    stem = sp.stem + (suffix or SUFFIX)
    cand = folder / f"{stem}.{fmt}"
    n = 2
    while cand.exists() or cand.resolve() == sp.resolve():
        cand = folder / f"{stem} ({n}).{fmt}"
        n += 1
    return str(cand)
