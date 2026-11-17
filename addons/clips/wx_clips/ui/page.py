"""ClipsPage: the add-on's widget. Holds the state (library, session, preferences) and switches
between the gallery (HomeView) and the cutting screen (EditorView)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QStackedWidget, QVBoxLayout, QWidget

from ..core import ffmpeg as ff
from ..core import library
from ..core.cache import Cache
from ..core.encode import out_folder
from ..core.i18n import fmt_mb, t
from ..core.session import Clip
from ..core.settings import BUILTIN_PRESETS, GPU_ENCODERS, EncodeSettings
from .common import Loader, fade_change
from .common import since as since_ts
from .editor import EditorView
from .gallery import HomeView
from .theme import stylesheet
from .widgets import DropOverlay

VIDEO_EXTS = library.CLIP_EXTS | {".mts", ".m2ts", ".mpg", ".mpeg", ".wmv", ".3gp", ".ogv"}


def _check_gpu():
    ok, _err = ff.encoder_check("h264_nvenc")
    return ok, (ff.gpu_name() or "") if ok else ""


class ClipsPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("clipsPage")
        self.setAcceptDrops(True)
        self.cache = Cache(host.data_dir)
        self.loader = Loader(3, self)
        self.loader.done.connect(self._loaded)
        self._info: dict = {}
        self._thumb: dict = {}
        self._frames: dict = {}
        self.picks: set[str] = set()
        self.done: set[str] = set(host.get("done", []) or [])
        self.folders: list = []
        self.new_list: list = []
        self.new_set: set[str] = set()
        self.state = "unset"
        self.fsort = ("date", -1)
        self.clips: list[Clip] = []
        self.cur = 0
        self.busy = False
        self.gpu = None
        prev = host.get("last_launch")
        self.last_launch = float(prev) if prev else time.time() - 2 * 86400
        host.set("last_launch", time.time())
        self.read_prefs()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.home = self._make_home()
        self.editor = self._make_editor()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.editor)
        self.overlay = DropOverlay(self)
        self.overlay.text = t("dropv")
        self.apply_theme()
        if hasattr(host, "settings_changed"):
            host.settings_changed.connect(self._setting)
        self.loader.submit("gpu", _check_gpu)
        self._timer = QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(lambda: self.rescan() if self.isVisible() else None)
        self._timer.start()
        self.rescan()

    # ------------------------------------------------ preferences
    def read_prefs(self):
        g = self.host.get
        self.nv_dir = g("nv_dir", "") or ""
        self.new_range = g("new_range", "last") or "last"
        self.mark = bool(g("mark_done", True))
        self.def_mode = g("def_mode", "single") or "single"
        self.def_merge = bool(g("def_merge", True))
        self.preset_id = g("preset", "discord") or "discord"
        self.encoder = g("encoder", "gpu") or "gpu"
        self.use_tk = bool(g("use_tk", True)) and hasattr(self.host, "folder")
        self.own_mode = g("own_mode", "beside") or "beside"
        self.own_dir = g("own_dir", "") or ""
        self.folder_previews = bool(g("folder_previews", False))
        self.del_orig = bool(g("del_orig", False))

    def _setting(self, key: str):
        old = self.nv_dir, self.new_range, self.mark, self.folder_previews
        self.read_prefs()
        if (self.nv_dir, self.new_range, self.mark) != old[:3]:
            if self.nv_dir != old[0]:
                self.home.folder = None
            self._sig = None
            self.rescan()
        elif self.folder_previews != old[3]:
            self.home.repaint_cards()

    def set_del_orig(self, on: bool):
        self.del_orig = on
        self.host.set("del_orig", on)

    def trash_originals(self, paths: list[str]) -> int:
        from ..core.trash import send_to_trash
        n = sum(1 for p in paths if send_to_trash(p))
        if n:
            self._sig = None
            self.rescan()
        return n

    def set_folder_previews(self, on: bool):
        self.host.set("folder_previews", on)
        self.folder_previews = on
        self.home.repaint_cards()

    # ------------------------------------------------ views
    def _make_home(self) -> HomeView:
        h = HomeView(self)
        h.open_paths.connect(self.open_paths)
        h.resume.connect(lambda: self.show_editor())
        h.pick_files.connect(self.pick_files)
        h.open_settings.connect(self._open_settings)
        return h

    def _make_editor(self) -> EditorView:
        e = EditorView(self)
        e.go_home.connect(self.show_home)
        return e

    def _open_settings(self):
        if hasattr(self.host, "open_settings"):
            self.host.open_settings()

    def show_home(self):
        self.editor.player.pause()

        def go():
            self.home.render()
            self.stack.setCurrentWidget(self.home)
        fade_change(self, go, 380, 60)

    def show_editor(self):
        if not self.clips:
            return

        def go():
            self.stack.setCurrentWidget(self.editor)
            self.editor.load_current()
            self.editor.enter()
        fade_change(self, go, 380, -60)

    # ------------------------------------------------ library
    def rescan(self):
        if not self.nv_dir:
            self.state = "unset"
            self.folders, self.new_list, self.new_set = [], [], set()
            self._refresh_home()
            return
        if not Path(self.nv_dir).is_dir():
            self.state = "missing"
            self.folders = []
            self._refresh_home()
            return
        if not self.folders:
            self.state = "scanning"
            self._refresh_home()
        self.loader.submit("scan", library.scan, self.nv_dir)

    def _compute_new(self):
        done = self.done if self.mark else set()
        self.new_list = library.new_clips(self.folders, since_ts(self.new_range, self.last_launch), done)
        self.new_set = {c.path for c in self.new_list}

    def _refresh_home(self):
        if self.stack.currentWidget() is self.home:
            self.home.render()

    # ------------------------------------------------ async results
    def info(self, path: str):
        m = self._info.get(path)
        if m is None:
            self.loader.submit("meta:" + path, self.cache.meta, path)
        return m

    def thumb(self, path: str | None):
        if not path:
            return None
        tp = self._thumb.get(path)
        if tp is None:
            m = self.info(path)
            if m is not None:
                self.loader.submit("thumb:" + path, self.cache.thumb, path, m.duration)
        return tp

    def frames(self, path: str) -> list:
        fr = self._frames.get(path)
        if fr is None:
            m = self.info(path)
            if m is not None:
                self.loader.submit("frames:" + path, self.cache.frames, path, m.duration)
            return []
        return fr

    def mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    def game(self, path: str) -> str:
        m = library.NV_NAME.match(Path(path).stem)
        return m.group("game") if m else Path(path).stem

    def _loaded(self, key: str, value):
        kind, _, path = key.partition(":")
        if kind == "scan":
            folders = value or []
            sig = tuple((f.name, f.count, f.size, f.last) for f in folders)
            same = sig == getattr(self, "_sig", None) and self.state == "ok"
            self._sig = sig
            self.folders = folders
            self.state = "ok"
            self._compute_new()
            if not same:                       # nothing new on disk: don't rebuild (keeps tab switches smooth)
                self._refresh_home()
            return
        if kind == "gpu":
            self.gpu = value if value else (False, "")
            if self.editor.step == 2:
                self.editor.render_step2()
            return
        if kind == "meta":
            if value is None:
                return
            self._info[path] = value
            self.thumb(path)
            for c in self.clips:
                if c.path == path and c.info is None:
                    self._clip_ready(c, value)
            self.home.repaint_cards()
        elif kind == "thumb":
            self._thumb[path] = value
            for c in self.clips:
                if c.path == path:
                    c.thumb = value
            self.home.repaint_cards()
            self.editor.render_strip() if self.stack.currentWidget() is self.editor else None
        elif kind == "frames":
            self._frames[path] = value or []
            for c in self.clips:
                if c.path == path:
                    c.frames = value or []
                    self.editor.timeline.update()
            self.home.repaint_cards()

    def _clip_ready(self, c: Clip, m):
        c.ready(m)
        c.thumb = c.thumb or self._thumb.get(c.path)
        c.frames = c.frames or self._frames.get(c.path) or []
        c.mode = self.def_mode
        c.merge = self.def_merge
        self.frames(c.path)
        self.thumb(c.path)
        if self.stack.currentWidget() is self.editor:
            if self.clip_index(c) == self.cur:
                self.editor.load_current()
            else:
                self.editor.render()

    def clip_index(self, c: Clip) -> int:
        try:
            return self.clips.index(c)
        except ValueError:
            return -1

    # ------------------------------------------------ session
    def session_paths(self) -> list[str]:
        return [c.path for c in self.clips]

    def open_paths(self, paths: list[str]):
        paths = [p for p in paths if Path(p).suffix.lower() in VIDEO_EXTS and os.path.isfile(p)]
        if not paths:
            return
        first = -1
        for p in paths:
            i = next((k for k, c in enumerate(self.clips) if c.path == p), -1)
            if i < 0:
                c = Clip(p)
                m = self._info.get(p)
                self.clips.append(c)
                if m:
                    self._clip_ready(c, m)
                else:
                    self.info(p)
                i = len(self.clips) - 1
            if first < 0:
                first = i
        self.picks.clear()
        self.cur = first

        def go():
            self.editor.step = 1
            self.editor.go_step(1, animated=False)
            self.stack.setCurrentWidget(self.editor)
            self.editor.load_current()
            self.editor.enter()
        fade_change(self, go, 380, -60)
        self.toast(t("added_clips"))

    def pick_files(self):
        start = self.nv_dir or str(Path.home() / "Videos")
        files, _ = QFileDialog.getOpenFileNames(self, t("pick_files"), start,
                                                f"{t('video_files')} (" + " ".join("*" + e for e in sorted(VIDEO_EXTS)) + ")")
        if files:
            self.open_paths(files)

    def remove_clip(self, i: int):
        if 0 <= i < len(self.clips):
            del self.clips[i]
            self.cur = max(0, min(self.cur if self.cur < i else self.cur - 1, len(self.clips) - 1))

    def clear_clips(self):
        self.clips.clear()
        self.cur = 0

    def open_set(self) -> set:
        return {c.path for c in self.clips}

    def mark_done(self, paths: list[str]):
        if not self.mark or not paths:
            return
        self.done |= set(paths)
        self.host.set("done", sorted(self.done)[-3000:])
        self._compute_new()

    def set_busy(self, on: bool):
        self.busy = on

    def toast(self, text: str):
        self.host.toast(text)

    # ------------------------------------------------ presets / output
    def presets(self) -> list[tuple[str, str, dict | None, bool]]:
        out = [(p.id, t("p_" + p.id), p.values, False) for p in BUILTIN_PRESETS]
        try:
            own = self.host.get("presets", [], addon="compress") or []
        except TypeError:                      # toolkit < 1.2
            own = []
        for d in own:
            try:
                out.append((f"own:{d['id']}", d["title"], dict(d.get("values", {})), True))
            except (KeyError, TypeError):
                continue
        out.append(("none", t("no_comp"), None, False))
        return out

    def _preset(self):
        ps = self.presets()
        return next((p for p in ps if p[0] == self.preset_id), ps[0])

    def set_preset(self, pid: str):
        self.preset_id = pid
        self.host.set("preset", pid)

    def set_encoder(self, v: str):
        self.encoder = v
        self.host.set("encoder", v)

    def encode_settings(self) -> EncodeSettings | None:
        pid, _title, values, _own = self._preset()
        if values is None:
            return None
        s = EncodeSettings.from_dict(values)
        gpu_ok = bool(self.gpu and self.gpu[0])
        s.encoder = "gpu" if gpu_ok and self.encoder == "gpu" and s.codec in GPU_ENCODERS else "cpu"
        return s

    def preset_desc(self) -> str:
        pid, _title, values, own = self._preset()
        if values is None:
            return t("no_comp_d")
        s = EncodeSettings.from_dict(values)
        parts = [s.format.upper()]
        if not s.is_gif:
            parts.append({"h264": "H.264", "h265": "H.265", "av1": "AV1", "vp9": "VP9"}.get(s.codec, s.codec))
            parts.append(t("d_q", q=s.quality) if s.mode == "quality" else
                         t("d_size", mb=fmt_mb(s.size_mb)) if s.mode == "size" else t("d_ratio", r=f"{s.ratio:g}"))
        else:
            parts.append(t("d_colors", n=s.colors))
        parts.append(f"{s.res}p" if s.res else t("d_src_res"))
        if s.fps_target:
            parts.append(t("d_fps", f=s.fps_target))
        if s.audio == "none" and not s.is_gif:
            parts.append(t("d_noaudio"))
        if own:
            parts.append(t("own_preset"))
        return " · ".join(parts) + "\n" + t("presets_note")

    def set_dest(self, use_tk: bool | None = None, own_mode: str | None = None, own_dir: str | None = None):
        if use_tk is not None:
            self.use_tk = use_tk
            self.host.set("use_tk", use_tk)
        if own_mode is not None:
            self.own_mode = own_mode
            self.host.set("own_mode", own_mode)
        if own_dir is not None:
            self.own_dir = own_dir
            self.host.set("own_dir", own_dir)

    def dest_dir(self) -> str:
        if self.use_tk and hasattr(self.host, "folder"):
            return self.host.folder("output")
        return self.own_dir if self.own_mode == "custom" else ""

    def folder_for(self, path: str) -> str:
        if self.use_tk and hasattr(self.host, "folder"):
            return self.host.folder("output")
        if self.own_mode == "custom" and self.own_dir:
            return self.own_dir
        return str(out_folder(path, self.own_mode if self.own_mode != "custom" else "beside", None))

    # ------------------------------------------------ toolkit hooks
    def is_busy(self) -> bool:
        return self.editor.running

    def shutdown(self):
        self._timer.stop()
        self.editor.shutdown()
        self.loader.shutdown()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        for w in self.findChildren(QWidget):
            w.update()

    def retranslate(self):
        self.overlay.text = t("dropv")
        if not self.editor.running:
            idx_editor = self.stack.currentWidget() is self.editor
            old = self.editor
            old.player.shutdown()
            self.stack.removeWidget(old)
            old.deleteLater()
            self.editor = self._make_editor()
            self.stack.addWidget(self.editor)
            if idx_editor:
                self.stack.setCurrentWidget(self.editor)
                self.editor.load_current()
        self.home.render()

    # ------------------------------------------------ drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.overlay.setGeometry(self.rect())
            self.overlay.show_overlay(True)

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.overlay.show_overlay(False)

    def dropEvent(self, e):
        self.overlay.show_overlay(False)
        paths = ff.collect_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        if paths:
            self.open_paths(paths)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.rect())

    def showEvent(self, e):
        super().showEvent(e)
        if self.state == "ok":                 # after the toolkit's page switch has settled
            QTimer.singleShot(700, self.rescan)
