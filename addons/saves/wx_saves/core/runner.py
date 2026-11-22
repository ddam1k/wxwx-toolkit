"""One download = one yt-dlp process (+ an ffmpeg pass when «MP4 для всех» has to re-encode).

Runs in a background thread and reports through Qt signals (queued to the GUI thread). Intermediate
files go to a per-download temp folder (-P temp:…), so pause/resume continues the .part files and a
cancel leaves nothing behind in the user's folder.
"""
from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from . import ytdlp
from .files import move_out

NO_WINDOW = 0x08000000 if os.name == "nt" else 0


@dataclass
class Tools:
    ytdlp: str | None = None
    ffmpeg: str | None = None
    ffprobe: str | None = None
    deno: str | None = None

    @property
    def ffmpeg_dir(self) -> str | None:
        return os.path.dirname(self.ffmpeg) if self.ffmpeg else None


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_text(args: list[str], timeout: float = 90) -> tuple[int, str, str]:
    """Run a tool and return (code, stdout, stderr) — for probes and «yt-dlp -U»."""
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW,
                           stdin=subprocess.DEVNULL, env=_env())
    except (OSError, subprocess.SubprocessError) as e:
        return -1, "", str(e)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def probe(tools: Tools, url: str, playlist: bool, cookies: str = "none", proxy: str = "") -> tuple[ytdlp.Info | None, str]:
    """(info, "") or (None, error text)."""
    if not tools.ytdlp:
        return None, "no-yt-dlp"
    code, out, err = run_text([tools.ytdlp, *ytdlp.probe_args(url, playlist, tools.ffmpeg_dir, tools.deno, cookies, proxy)],
                              timeout=120)
    if code == 0 and out.strip():
        try:
            return ytdlp.parse_info(out.strip().splitlines()[-1], url), ""
        except (ValueError, KeyError, TypeError) as e:
            return None, f"bad json: {e}"
    return None, err or out or f"yt-dlp exited with {code}"


def probe_via(tools: Tools, url: str, playlist: bool, cookies: str, proxies: list[str]) -> tuple:
    """probe() trying each proxy address in turn while the failure is a network one.
    (info, error, the address that answered — "" for direct)."""
    tries = proxies or [""]
    info, err = None, ""
    for i, px in enumerate(tries):
        info, err = probe(tools, url, playlist, cookies, px)
        if info is not None or ytdlp.error_kind(err) != "network" or i == len(tries) - 1:
            return info, err, px
    return info, err, tries[-1]


@dataclass
class Job:
    """What the list shows. Mutated by the worker thread, read by the GUI on `changed`."""
    id: int
    url: str
    title: str
    site: str
    opts: ytdlp.Opts
    key: str = ""                    # video id — for history and «уже качала»
    thumb: str = ""                  # url of the preview picture
    vertical: bool = False
    est: float = 0.0                 # expected bytes
    duration: float = 0.0
    recode: bool = False
    state: str = "wait"              # wait | work | pause | done | err | cancel
    stage: str = "start"
    frac: float = 0.0
    speed: float = 0.0
    eta: float | None = None
    got: float = 0.0
    path: str = ""
    size: float = 0.0
    err_kind: str = ""
    err_text: str = ""
    tmp: str = ""
    meta: str = ""
    extra: dict = field(default_factory=dict)


class Worker(QObject):
    changed = Signal(int)            # job id
    finished = Signal(int)

    def __init__(self, job: Job, tools: Tools, parent=None):
        super().__init__(parent)
        self.job = job
        self.tools = tools
        self._proc: subprocess.Popen | None = None
        self._stop = ""              # "" | "pause" | "cancel"
        self._last_emit = 0.0

    def start(self) -> None:
        self._stop = ""
        self.job.state = "work"
        self.job.err_kind = self.job.err_text = ""
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self, why: str) -> None:
        self._stop = why
        p = self._proc
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    # ------------------------------------------------------------ thread
    def _emit(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self._last_emit > 0.12:
            self._last_emit = now
            try:
                self.changed.emit(self.job.id)
            except RuntimeError:
                pass

    def _run(self) -> None:
        j = self.job
        try:
            ok = self._download()
            if ok and j.recode and j.path and not self._stop:
                ok = self._recode()
        except Exception as e:           # never leave a row spinning
            ok = False
            j.err_kind, j.err_text = "other", str(e)
        if self._stop == "pause":
            j.state, j.speed = "pause", 0.0
        elif self._stop == "cancel":
            j.state = "cancel"
            self._cleanup_tmp()
        elif ok:
            j.state, j.frac, j.speed = "done", 1.0, 0.0
            try:
                j.size = float(os.path.getsize(j.path))
            except OSError:
                pass
            self._cleanup_tmp()
        else:
            j.state = "err"
        self._emit(True)
        try:
            self.finished.emit(j.id)
        except RuntimeError:
            pass

    def _cleanup_tmp(self) -> None:
        if self.job.tmp:
            shutil.rmtree(self.job.tmp, ignore_errors=True)

    def _download(self) -> bool:
        j = self.job
        if not self.tools.ytdlp:
            j.err_kind = "tool"
            return False
        o, staged = j.opts, ""
        if o.what == "audio" and j.tmp:
            # yt-dlp would reuse a video of the same name already in the folder and delete it after
            # extracting the sound → audio is made in the job's own folder and moved out when ready
            staged = os.path.join(j.tmp, "out")
            o = dataclasses.replace(o, folder=staged)
        args = ytdlp.download_args(j.url, o, self.tools.ffmpeg_dir, self.tools.deno)
        if j.tmp:
            os.makedirs(j.tmp, exist_ok=True)
            args[-2:-2] = ["-P", f"temp:{j.tmp}"]
        tail: deque[str] = deque(maxlen=30)
        try:
            self._proc = subprocess.Popen([self.tools.ytdlp, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, env=_env(),
                                          text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            j.err_kind, j.err_text = "tool", str(e)
            return False
        dl_share = 0.5 if j.recode else 0.92
        streams = 0
        last_audio = None
        assert self._proc.stdout
        for line in self._proc.stdout:
            ev = ytdlp.parse_line(line)
            if ev is None:
                s = line.strip()
                if s:
                    tail.append(s)
                continue
            if ev["kind"] == "dl":
                if ev["audio"] != last_audio:
                    streams += 1
                    last_audio = ev["audio"]
                total = ev["total"] or j.est or 0.0
                p = min(1.0, ev["done"] / total) if total else 0.0
                if j.opts.what == "audio":
                    j.stage, j.frac = "audio", p * dl_share
                elif ev["audio"]:
                    j.stage, j.frac = "audio", 0.82 * dl_share + 0.18 * dl_share * p
                elif streams <= 1:
                    j.stage, j.frac = "video", 0.82 * dl_share * p
                else:
                    j.stage, j.frac = "dl", p * dl_share
                j.speed, j.eta, j.got = ev["speed"], ev["eta"], ev["done"]
                self._emit()
            elif ev["kind"] == "pp":
                j.stage = ytdlp.stage_of_pp(ev["pp"])
                j.frac = max(j.frac, dl_share + (0.02 if ev["status"] == "started" else 0.05))
                j.speed, j.eta = 0.0, None
                self._emit(True)
            elif ev["kind"] == "file":
                j.path = ev["path"]
        code = self._proc.wait()
        self._proc = None
        if self._stop:
            return False
        if code != 0 or not j.path:
            text = "\n".join(tail)
            j.err_kind = ytdlp.error_kind(text)
            j.err_text = ytdlp.last_error(text) or f"yt-dlp exited with {code}"
            return False
        if staged:
            try:
                j.path = move_out(j.path, staged, j.opts.folder or ".")
            except OSError as e:
                j.err_kind, j.err_text = "other", str(e)
                return False
        return True

    def _recode(self) -> bool:
        """«MP4 для всех»: the site had no H.264 at this quality → convert, NVENC first, then x264."""
        j = self.job
        if not (self.tools.ffmpeg and self.tools.ffprobe):
            return True
        code, out, _ = run_text([self.tools.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=codec_name:format=duration", "-of", "default=nw=1", j.path], timeout=30)
        vals = dict(ln.split("=", 1) for ln in out.splitlines() if "=" in ln)
        if vals.get("codec_name", "h264") == "h264":
            return True
        try:
            dur = float(vals.get("duration") or j.duration or 0)
        except ValueError:
            dur = j.duration
        j.stage = "recode"
        self._emit(True)
        tmp_out = os.path.join(j.tmp or os.path.dirname(j.path), "recode.mp4")
        for enc in (["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21"], ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19"]):
            if self._ffmpeg([self.tools.ffmpeg, "-hide_banner", "-y", "-i", j.path, *enc, "-pix_fmt", "yuv420p",
                             "-c:a", "copy", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", tmp_out], dur):
                try:
                    os.replace(tmp_out, j.path)
                    return True
                except OSError as e:
                    j.err_kind, j.err_text = "other", str(e)
                    return False
            if self._stop:
                return False
        j.err_kind, j.err_text = "other", "re-encoding to H.264 failed"
        return False

    def _ffmpeg(self, args: list[str], dur: float) -> bool:
        j = self.job
        try:
            self._proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                          creationflags=NO_WINDOW, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError:
            return False
        assert self._proc.stdout
        for line in self._proc.stdout:
            m = re.match(r"out_time_us=(\d+)", line.strip())
            if m and dur:
                j.frac = 0.5 + 0.48 * min(1.0, int(m.group(1)) / 1e6 / dur)
                self._emit()
        code = self._proc.wait()
        self._proc = None
        return code == 0 and not self._stop
