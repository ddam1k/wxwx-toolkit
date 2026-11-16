"""Runs one ffmpeg job in a background thread and reports progress through Qt signals."""
from __future__ import annotations

import os
import subprocess
import threading
from collections import deque

from PySide6.QtCore import QObject, Signal

from . import ffmpeg as ff
from .ffmpeg import NO_WINDOW


class EncodeJob(QObject):
    progress = Signal(float, float)   # fraction 0..1, speed (x realtime)
    finished = Signal(bool, str)      # ok, error text

    def __init__(self, args: list[str], duration: float, out_path: str, parent=None):
        super().__init__(parent)
        self.args = args
        self.duration = max(duration, 0.1)
        self.out_path = out_path
        self._proc: subprocess.Popen | None = None
        self._stopped = False

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass

    def _run(self) -> None:
        tail: deque[str] = deque(maxlen=12)
        try:
            os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
            self._proc = subprocess.Popen(
                [ff.FFMPEG, *self.args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as e:
            self.finished.emit(False, f"не удалось запустить ffmpeg: {e}")
            return

        speed = 0.0
        assert self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            key, sep, val = line.partition("=")
            if not sep or " " in key:
                if line:
                    tail.append(line)
                continue
            if key in ("out_time_us", "out_time_ms"):        # both are microseconds in ffmpeg
                try:
                    t = int(val) / 1_000_000
                    self.progress.emit(max(0.0, min(1.0, t / self.duration)), speed)
                except ValueError:
                    pass
            elif key == "speed":
                try:
                    speed = float(val.rstrip("x"))
                except ValueError:
                    pass
            elif key == "progress" and val == "end":
                self.progress.emit(1.0, speed)

        code = self._proc.wait()
        ok = code == 0 and not self._stopped and os.path.isfile(self.out_path)
        if not ok:
            try:
                if os.path.isfile(self.out_path):
                    os.remove(self.out_path)
            except OSError:
                pass
        err = "остановлено" if self._stopped else ("\n".join(tail) or f"ffmpeg завершился с кодом {code}")
        self.finished.emit(ok, "" if ok else err)
