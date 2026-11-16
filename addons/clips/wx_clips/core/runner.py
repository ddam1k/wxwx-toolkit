"""Runs a Plan (several ffmpeg steps) in a background thread, reporting overall progress via Qt signals."""
from __future__ import annotations

import os
import subprocess
import threading
from collections import deque

from PySide6.QtCore import QObject, Signal

from . import ffmpeg as ff
from .encode import Plan
from .ffmpeg import NO_WINDOW


class ClipJob(QObject):
    progress = Signal(float)            # 0..1 for the whole plan
    finished = Signal(bool, str)        # ok, error text

    def __init__(self, plan: Plan, parent=None):
        super().__init__(parent)
        self.plan = plan
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
        total = self.plan.duration
        done_before = 0.0
        err = ""
        ok = True
        for step in self.plan.steps:
            if self._stopped:
                ok, err = False, "stopped"
                break
            step_ok, step_err = self._run_step(step, done_before, total)
            if not step_ok:
                ok, err = False, step_err
                break
            done_before += step.duration
        for t in self.plan.temps:
            try:
                os.remove(t)
            except OSError:
                pass
        if not ok:
            for o in self.plan.outputs:
                try:
                    if os.path.isfile(o):
                        os.remove(o)
                except OSError:
                    pass
        else:
            self.progress.emit(1.0)
        self.finished.emit(ok, err)

    def _run_step(self, step, before: float, total: float) -> tuple[bool, str]:
        tail: deque[str] = deque(maxlen=12)
        try:
            os.makedirs(os.path.dirname(step.out) or ".", exist_ok=True)
            self._proc = subprocess.Popen([ff.FFMPEG, *step.args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, text=True,
                                          encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            return False, f"ffmpeg: {e}"
        assert self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            key, sep, val = line.partition("=")
            if not sep or " " in key:
                if line:
                    tail.append(line)
                continue
            if key in ("out_time_us", "out_time_ms"):
                try:
                    t = min(step.duration, max(0.0, int(val) / 1_000_000))
                    self.progress.emit(min(0.999, (before + t) / max(total, 0.1)))
                except ValueError:
                    pass
        code = self._proc.wait()
        self._proc.stdout.close()
        if self._stopped:
            return False, "stopped"
        if code != 0 or not os.path.isfile(step.out):
            return False, "\n".join(tail) or f"ffmpeg exit code {code}"
        return True, ""
