"""ffmpeg plans for one clip: cut segments (frame-accurate), mix audio tracks, compress — or just copy.

A plan is a list of steps (ffmpeg argument lists run one after another) plus the files it produces.
No Qt here, so it is unit-tested with real ffmpeg.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from .ffmpeg import MediaInfo
from .settings import CPU_ENCODERS, EFFICIENCY, GPU_ENCODERS, EncodeSettings

SUFFIX = "_wx"
HEAD = ["-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]


@dataclass
class Step:
    args: list[str]
    duration: float           # seconds of output this step writes (for progress)
    out: str


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    temps: list[str] = field(default_factory=list)
    est_mb: float = 0.0

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.steps) or 0.1


# ---------------------------------------------------------------- shared with the Video add-on
def equivalent_crf(quality: int) -> float:
    return 34 - quality * 0.16


def quality_value(s: EncodeSettings) -> int:
    q = s.quality
    if s.encoder == "gpu":
        return round(36 - q * 0.17)
    if s.codec in ("av1", "vp9"):
        return round(52 - q * 0.30)
    return round(equivalent_crf(q))


def encoder_name(s: EncodeSettings) -> str:
    return GPU_ENCODERS[s.codec] if s.encoder == "gpu" else CPU_ENCODERS[s.codec]


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


def audio_codec(s: EncodeSettings) -> tuple[list[str], float]:
    """Audio is always re-encoded here (it goes through trim/mix filters)."""
    if s.is_gif or s.audio == "none":
        return ["-an"], 0.0
    hi = s.audio == "keep"
    if s.format == "mp4":
        return ["-c:a", "aac", "-b:a", "192k" if hi else "128k"], 192.0 if hi else 128.0
    return ["-c:a", "libopus", "-b:a", "160k" if hi else "96k"], 160.0 if hi else 96.0


def video_codec_args(s: EncodeSettings, m: MediaInfo, audio_k: float) -> list[str]:
    enc = encoder_name(s)
    a = ["-c:v", enc, "-pix_fmt", "yuv420p"]
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
        kb = target_video_kbps(s, m, audio_k)
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
    return a


def target_total_mb(s: EncodeSettings, m: MediaInfo) -> float:
    mb = s.size_mb if s.mode == "size" else m.size_mb / s.ratio
    return min(mb, m.size_mb)


def target_video_kbps(s: EncodeSettings, m: MediaInfo, audio_k: float) -> int:
    total_k = target_total_mb(s, m) * 1048576 * 8 / 1000 / max(m.duration, 0.1)
    return max(50, int(total_k * 0.96 - audio_k))


def estimate_mb(s: EncodeSettings, m: MediaInfo, has_audio: bool = True) -> float:
    w, h = out_size(s, m)
    fps = out_fps(s, m)
    if s.is_gif:
        colors = 0.35 + 0.65 * s.colors / 256
        return max(0.05, w * h * fps * m.duration * 0.11 * colors / 1048576)
    _, audio_k = audio_codec(s)
    if not has_audio:
        audio_k = 0
    if s.mode != "quality":
        return target_total_mb(s, m)
    crf = equivalent_crf(s.quality)
    bpp = 0.08 * math.pow(2, (23 - crf) / 6) * EFFICIENCY[s.codec] * (1.15 if s.encoder == "gpu" else 1.0)
    video_k = min(w * h * fps * bpp / 1000, max(50.0, m.total_kbps) * 1.05)
    return max(0.05, (video_k + audio_k) * 1000 / 8 * m.duration / 1048576)


# ---------------------------------------------------------------- paths
def unique(path: Path) -> Path:
    n, cand = 2, path
    while cand.exists():
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return cand


def out_folder(src: str, mode: str, custom: str | None) -> Path:
    """mode: beside | subfolder | custom | toolkit (custom/toolkit use the given folder)."""
    sp = Path(src)
    if mode == "subfolder":
        return sp.parent / "clips"
    if mode in ("custom", "toolkit") and custom:
        return Path(custom)
    return sp.parent


def _sub(m: MediaInfo, length: float) -> MediaInfo:
    """The clip as if it were only `length` seconds long (bitrate targets, estimates)."""
    k = max(0.01, min(1.0, length / max(m.duration, 0.1)))
    return replace(m, duration=max(length, 0.1), size_mb=m.size_mb * k)


def estimate(m: MediaInfo, segs: list[tuple[float, float]], tracks: list[int], s: EncodeSettings | None,
             merge: bool) -> float:
    """Expected output size in MB (no files touched)."""
    segs = [(a, b) for a, b in (segs or [(0.0, m.duration)]) if b - a > 0.05] or [(0.0, m.duration)]
    groups = [segs] if (merge or len(segs) == 1) else [[sg] for sg in segs]
    total = 0.0
    for g in groups:
        length = sum(b - a for a, b in g)
        total += m.size_mb * length / max(m.duration, 0.1) if s is None else estimate_mb(s, _sub(m, length), bool(tracks))
    return total


# ---------------------------------------------------------------- the plan
def plan_clip(m: MediaInfo, segs: list[tuple[float, float]], tracks: list[int], s: EncodeSettings | None,
              merge: bool, folder: Path, tmp_dir: Path, reserved: set[str] | None = None,
              suffix: str = SUFFIX) -> Plan:
    """segs: (start, end) seconds, sorted; empty = the whole clip. tracks: audio stream indexes to keep
    (mixed into one when re-encoding). s=None: no re-encode (stream copy, cuts land on keyframes)."""
    reserved = reserved if reserved is not None else set()
    segs = [(max(0.0, a), min(m.duration, b)) for a, b in (segs or [(0.0, m.duration)]) if b - a > 0.05]
    segs = segs or [(0.0, m.duration)]
    tracks = [t for t in tracks if 0 <= t < len(m.audio_tracks)]
    stem = Path(m.path).stem + (suffix or SUFFIX)
    ext = ("." + s.format) if s else (Path(m.path).suffix.lower() or ".mp4")
    groups = [segs] if (merge or len(segs) == 1) else [[sg] for sg in segs]

    def name(i: int) -> str:
        base = folder / (f"{stem}{ext}" if len(groups) == 1 else f"{stem}_{i + 1}{ext}")
        p = unique(base)
        while str(p) in reserved:
            base = base.with_name(base.stem + "_" + base.suffix)
            p = unique(base)
        reserved.add(str(p))
        return str(p)

    plan = Plan()
    for gi, group in enumerate(groups):
        out = name(gi)
        plan.outputs.append(out)
        length = sum(b - a for a, b in group)
        if s is None:
            _copy_steps(plan, m, group, tracks, out, tmp_dir, gi)
            plan.est_mb += m.size_mb * length / max(m.duration, 0.1)
        else:
            sub = _sub(m, length)
            plan.steps.append(Step(_encode_args(m, sub, group, tracks, s, out), length, out))
            plan.est_mb += estimate_mb(s, sub, bool(tracks))
    return plan


def _encode_args(m: MediaInfo, sub: MediaInfo, group, tracks, s: EncodeSettings, out: str) -> list[str]:
    a = list(HEAD)
    for st, en in group:
        a += ["-ss", f"{st:.3f}", "-t", f"{en - st:.3f}", "-i", m.path]
    use_audio = bool(tracks) and not s.is_gif and s.audio != "none"
    fc, cat = [], []
    for k in range(len(group)):
        fc.append(f"[{k}:v:0]setpts=PTS-STARTPTS[v{k}]")
        cat.append(f"[v{k}]")
        if use_audio:
            ins = "".join(f"[{k}:a:{t}]" for t in tracks)
            mix = f"amix=inputs={len(tracks)}:duration=longest:normalize=0," if len(tracks) > 1 else ""
            fc.append(f"{ins}{mix}aresample=async=1,asetpts=PTS-STARTPTS[a{k}]")
            cat.append(f"[a{k}]")
    if len(group) > 1:
        fc.append("".join(cat) + f"concat=n={len(group)}:v=1:a={1 if use_audio else 0}[vc]" + ("[ac]" if use_audio else ""))
        v, au = "[vc]", "[ac]"
    else:
        v, au = "[v0]", "[a0]"
    w, h = out_size(s, m)
    fps = out_fps(s, m)
    post = []
    if abs(fps - m.fps) > 0.01:
        post.append(f"fps={fps:g}")
    if (w, h) != (m.width, m.height):
        post.append(f"scale={w}:{h}:flags=lanczos")
    if s.is_gif:
        post.append(f"split[ga][gb];[ga]palettegen=max_colors={s.colors}:stats_mode=diff[gp];"
                    f"[gb][gp]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    fc.append(f"{v}{','.join(post) if post else 'null'}[vo]")
    a += ["-filter_complex", ";".join(fc), "-map", "[vo]"]
    if s.is_gif:
        return a + ["-loop", "0", out]
    acodec, audio_k = audio_codec(s) if use_audio else (["-an"], 0.0)
    if use_audio:
        a += ["-map", au]
    a += video_codec_args(s, sub, audio_k) + acodec
    if s.format == "mp4":
        a += ["-movflags", "+faststart"]
    return a + [out]


def _copy_steps(plan: Plan, m: MediaInfo, group, tracks, out: str, tmp_dir: Path, gi: int) -> None:
    maps = ["-map", "0:v:0"] + [x for t in tracks for x in ("-map", f"0:a:{t}")]
    if len(group) == 1:
        st, en = group[0]
        plan.steps.append(Step(HEAD + ["-ss", f"{st:.3f}", "-i", m.path, "-t", f"{en - st:.3f}", *maps,
                                       "-c", "copy", "-avoid_negative_ts", "make_zero", out], en - st, out))
        return
    parts = []
    for k, (st, en) in enumerate(group):
        part = str(tmp_dir / f"part-{os.getpid()}-{gi}-{k}{Path(out).suffix}")
        parts.append(part)
        plan.temps.append(part)
        plan.steps.append(Step(HEAD + ["-ss", f"{st:.3f}", "-i", m.path, "-t", f"{en - st:.3f}", *maps,
                                       "-c", "copy", "-avoid_negative_ts", "make_zero", part], en - st, part))
    lst = tmp_dir / f"list-{os.getpid()}-{gi}.txt"
    lst.write_text("".join(f"file '{p.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for p in parts),
                   "utf-8")
    plan.temps.append(str(lst))
    plan.steps.append(Step(HEAD + ["-f", "concat", "-safe", "0", "-i", str(lst), "-map", "0", "-c", "copy", out],
                           sum(b - a for a, b in group), out))
