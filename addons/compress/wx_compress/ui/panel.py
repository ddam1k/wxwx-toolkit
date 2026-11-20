"""The compressor itself: queue on the left, settings on the right.

One widget for both worlds:
  * the standalone app puts it into its own window (ui/main_window.py)
  * the toolkit add-on returns it from create(host) (addon.py)
Everything outside the panel (persistence, toasts, the toolkit's folder) comes through an Env.
"""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu, QPlainTextEdit,
                               QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..core import ffmpeg as ff
from ..core import presets as wtp
from ..core.command import SUFFIX, build_args, estimate_mb, output_path, preview, quality_value, quality_word
from ..core.i18n import files_word, fmt_mb, lang, t
from ..core.runner import EncodeJob
from ..core.settings import (BUILTIN_PRESETS, CODECS, CPU_ENCODERS, FPS_STEPS, GPU_ENCODERS, RESOLUTIONS,
                             EncodeSettings, Preset, apply_preset)
from .queue_item import ElideLabel, QueueItem, fmt_pct
from .theme import stylesheet, theme
from .widgets import (Chip, DropOverlay, DropZone, FlowLayout, IconBadge, Led, ProgressButton, SectionHeader,
                      Segmented, SplitSlider, SwitchRow)

ADDON_ID = "compress"
OWN_MODES = ("beside", "subfolder", "custom")
CODEC_SUB_EN = {"везде": "everywhere", "браузеры": "browsers", "палитра": "palette"}


class Env:
    """Standalone defaults; the add-on overrides these with the toolkit host."""
    is_addon = False

    def get(self, key: str, default=None):
        return default

    def set(self, key: str, value) -> None:
        pass

    def toast(self, text: str, ms: int = 2600) -> None:
        pass

    def toolkit_folder(self) -> str | None:
        return None

    def suffix(self) -> str:
        return SUFFIX


@dataclass
class Item:
    id: int
    path: str
    media: ff.MediaInfo | None = None
    thumb: bytes | None = None
    status: str = "probing"          # probing | queued | work | done | error
    progress: float = 0.0
    out_path: str | None = None
    out_mb: float | None = None
    widget: QueueItem | None = None


class Bridge(QObject):
    probed = Signal(int, object, object)
    caps = Signal(object, object, object, object)     # encoders, gpu ok per codec, errors, gpu name


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    if name == "note":
        lbl.setProperty("hint", True)    # hidden in «Меньше подсказок» mode (toolkit 1.3+)
    return lbl


def _btn(text: str, name: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class CompressorPanel(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, env: Env, parent=None):
        super().__init__(parent)
        self.setObjectName("panelRoot")
        self.env = env
        saved = env.get("settings")
        self._first_run = saved is None
        self.s = EncodeSettings.from_dict(saved or {})
        self.preset_id = env.get("preset", "telegram")
        self.custom = [Preset.from_dict(d) for d in env.get("presets", []) or []]
        self.use_tk = bool(env.get("use_tk", True)) and env.is_addon
        self.own_mode = env.get("own_mode", "beside")
        if self.own_mode not in OWN_MODES:
            self.own_mode = "beside"
        self.out_dir = env.get("out_dir", "") or ""
        self.last_dir = env.get("last_dir", "") or ""
        self.share_dir = env.get("share_dir", "") or ""

        self.items: list[Item] = []
        self._next_id = 0
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.bridge = Bridge()
        self.bridge.probed.connect(self._on_probed)
        self.bridge.caps.connect(self._on_caps)
        self.encoders: set[str] | None = None
        self.gpu: dict[str, bool] = {}
        self.gpu_errors: dict[str, str] = {}
        self.gpu_label: str | None = None

        self.running = False
        self.stop_requested = False
        self.job: EncodeJob | None = None
        self.run_settings: EncodeSettings | None = None
        self.run_ids: list[int] = []
        self._smoke_done = None
        self._preset_sig = None
        self._codec_fmt = None
        self.preset_chips: dict[str, Chip] = {}
        self.codec_chips: dict[str, Chip] = {}

        self._build()
        self.setAcceptDrops(True)
        self.apply_theme()
        self.retranslate()
        self.pool.submit(self._detect_caps)

    # ======================================================== persistence
    def _save(self):
        e = self.env
        e.set("settings", self.s.to_dict())
        e.set("preset", self.preset_id)
        e.set("presets", [p.to_dict() for p in self.custom])
        e.set("use_tk", self.use_tk)
        e.set("own_mode", self.own_mode)
        e.set("out_dir", self.out_dir)
        e.set("last_dir", self.last_dir)
        e.set("share_dir", self.share_dir)

    # ======================================================== layout
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_queue(), 1)
        seam = QFrame()
        seam.setObjectName("seam")
        seam.setFixedWidth(1)
        root.addWidget(seam)
        root.addWidget(self._build_settings())
        self.overlay = DropOverlay(self)

    def _build_queue(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(0)
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        self.h_title = _label("", "h2")
        self.q_meta = _label("", "muted")
        tv.addWidget(self.h_title)
        tv.addWidget(self.q_meta)
        head.addLayout(tv)
        head.addStretch()
        self.add_btn = _btn("", "ghost")
        self.add_btn.clicked.connect(self.add_dialog)
        self.clear_btn = _btn("", "ghost")
        self.clear_btn.clicked.connect(self.clear_queue)
        head.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(head)
        v.addSpacing(14)
        self.drop = DropZone()
        self.drop.clicked.connect(self.add_dialog)
        v.addWidget(self.drop)
        v.addSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.list_lay = QVBoxLayout(inner)
        self.list_lay.setContentsMargins(0, 0, 6, 0)
        self.list_lay.setSpacing(8)
        self.empty = _label("", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setMinimumHeight(220)
        self.list_lay.addWidget(self.empty)
        self.list_lay.addStretch(1)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)
        return w

    def _block(self, icon: str) -> tuple[QWidget, SectionHeader, QVBoxLayout]:
        w = QWidget()
        w.setObjectName("block")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 16, 0, 18)
        lay.setSpacing(10)
        hdr = SectionHeader(icon)
        lay.addWidget(hdr)
        self.form.addWidget(w)
        return w, hdr, lay

    def _value_row(self) -> tuple[QHBoxLayout, QLabel, QLabel]:
        row = QHBoxLayout()
        name = _label("", "rowLabel")
        val = _label("", "rowValue")
        val.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(name)
        row.addStretch()
        row.addWidget(val)
        return row, name, val

    def _scale_row(self) -> tuple[QHBoxLayout, QLabel, QLabel]:
        row = QHBoxLayout()
        a, b = _label("", "scaleLabel"), _label("", "scaleLabel")
        row.addWidget(a)
        row.addStretch()
        row.addWidget(b)
        return row, a, b

    def _build_settings(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panelRight")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setFixedWidth(392)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.form = QVBoxLayout(body)
        self.form.setContentsMargins(20, 2, 16, 8)
        self.form.setSpacing(0)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.settings_scroll = scroll

        # ---- presets
        _, self.h_preset, lay = self._block("preset")
        self.save_btn = self.h_preset.add_action()
        self.save_btn.clicked.connect(self.save_preset)
        self.import_btn = self.h_preset.add_action()
        self.import_btn.clicked.connect(self.import_dialog)
        box = QWidget()
        self.preset_flow = FlowLayout(box, 6)
        lay.addWidget(box)
        self.preset_note = _label("", "note", wrap=True)
        lay.addWidget(self.preset_note)

        # ---- format
        _, self.h_format, lay = self._block("format")
        self.seg_format = Segmented([("mp4", "MP4", ""), ("webm", "WebM", ""), ("gif", "GIF", "")])
        self.seg_format.changed.connect(self.on_format)
        lay.addWidget(self.seg_format)
        box = QWidget()
        self.codec_flow = FlowLayout(box, 6)
        lay.addWidget(box)

        # ---- encoder
        _, self.h_enc, lay = self._block("chip")
        self.seg_enc = Segmented([("cpu", "", "x"), ("gpu", "", "x")])
        self.seg_enc.changed.connect(lambda v: self.change(encoder=v))
        lay.addWidget(self.seg_enc)
        grow = QHBoxLayout()
        grow.setSpacing(8)
        self.gpu_led = Led()
        self.gpu_text = _label("", "gpuText", wrap=True)
        grow.addWidget(self.gpu_led, 0, Qt.AlignmentFlag.AlignTop)
        grow.addWidget(self.gpu_text, 1)
        lay.addLayout(grow)

        # ---- compression mode
        self.g_mode, self.h_mode, lay = self._block("gauge")
        self.seg_mode = Segmented([("quality", "", ""), ("size", "", ""), ("ratio", "", "")])
        self.seg_mode.changed.connect(lambda v: self.change(mode=v))
        lay.addWidget(self.seg_mode)
        self.mode_stack = QStackedWidget()
        self.mode_stack.setFixedHeight(92)
        lay.addWidget(self.mode_stack)

        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(2)
        row, self.l_quality, self.q_val = self._value_row()
        self.sl_quality = SplitSlider(0, 100)
        self.sl_quality.valueChanged.connect(lambda v: self.change(quality=v))
        srow, self.l_smaller, self.l_better = self._scale_row()
        pl.addLayout(row)
        pl.addWidget(self.sl_quality)
        pl.addLayout(srow)
        pl.addStretch()
        self.mode_stack.addWidget(page)

        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(2)
        row, self.l_fit, self.s_val = self._value_row()
        self.sl_size = SplitSlider(1, 200)
        self.sl_size.valueChanged.connect(lambda v: self.change(size_mb=v))
        box = QWidget()
        fl = FlowLayout(box, 5)
        self.size_quick = {}
        for v in (8, 10, 25, 50, 100):
            c = Chip(f"{v}", small=True)
            c.clicked.connect(lambda _=False, v=v: self.change(size_mb=v))
            fl.addWidget(c)
            self.size_quick[v] = c
        pl.addLayout(row)
        pl.addWidget(self.sl_size)
        pl.addSpacing(6)
        pl.addWidget(box)
        pl.addStretch()
        self.mode_stack.addWidget(page)

        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(2)
        row, self.l_shrink, self.r_val = self._value_row()
        self.sl_ratio = SplitSlider(3, 20)
        self.sl_ratio.valueChanged.connect(lambda v: self.change(ratio=v / 2))
        box = QWidget()
        fl = FlowLayout(box, 5)
        self.ratio_quick = {}
        for v in (2, 3, 5, 10):
            c = Chip(f"×{v}", small=True)
            c.clicked.connect(lambda _=False, v=v: self.change(ratio=float(v)))
            fl.addWidget(c)
            self.ratio_quick[v] = c
        pl.addLayout(row)
        pl.addWidget(self.sl_ratio)
        pl.addSpacing(6)
        pl.addWidget(box)
        pl.addStretch()
        self.mode_stack.addWidget(page)

        # ---- gif palette
        self.g_colors, self.h_colors, lay = self._block("palette")
        row, self.l_colors, self.c_val = self._value_row()
        self.sl_colors = SplitSlider(1, 16)
        self.sl_colors.valueChanged.connect(lambda v: self.change(colors=v * 16))
        srow, self.l_lighter, self.l_smoother = self._scale_row()
        lay.addLayout(row)
        lay.addWidget(self.sl_colors)
        lay.addLayout(srow)

        # ---- size & fps
        _, self.h_size, lay = self._block("frame")
        box = QWidget()
        fl = FlowLayout(box, 6)
        self.res_chips = {}
        for value, title in RESOLUTIONS:
            c = Chip(title)
            c.clicked.connect(lambda _=False, v=value: self.change(res=v))
            fl.addWidget(c)
            self.res_chips[value] = c
        lay.addWidget(box)
        row, self.l_fps, self.fps_val = self._value_row()
        self.sl_fps = SplitSlider(0, len(FPS_STEPS) - 1)
        self.sl_fps.valueChanged.connect(lambda v: self.change(fps_idx=v))
        lay.addSpacing(4)
        lay.addLayout(row)
        lay.addWidget(self.sl_fps)

        # ---- audio
        self.g_audio, self.h_audio, lay = self._block("sound")
        self.seg_audio = Segmented([("keep", "", ""), ("compress", "", "128k"), ("none", "", "")])
        self.seg_audio.changed.connect(lambda v: self.change(audio=v))
        lay.addWidget(self.seg_audio)

        # ---- destination
        _, self.h_dest, lay = self._block("folder")
        self.tk_row = SwitchRow()
        self.tk_row.toggled.connect(self.set_use_tk)
        self.tk_row.setVisible(self.env.is_addon)
        lay.addWidget(self.tk_row)
        self.seg_out = Segmented([("beside", "", "x"), ("subfolder", "", "x"), ("custom", "", "x")])
        self.seg_out.changed.connect(self.set_own_mode)
        lay.addWidget(self.seg_out)
        dest = QFrame()
        self.dest_box = dest
        dest.setObjectName("destBox")
        dl = QHBoxLayout(dest)
        dl.setContentsMargins(12, 10, 8, 10)
        dl.setSpacing(11)
        dl.addWidget(IconBadge("folder", 22, 20, plain=True, tint=True))
        dv = QVBoxLayout()
        dv.setSpacing(2)
        self.dest_path = ElideLabel()
        self.dest_path.setObjectName("destPath")
        self.dest_sub = ElideLabel()
        self.dest_sub.setObjectName("destSub")
        dv.addWidget(self.dest_path)
        dv.addWidget(self.dest_sub)
        dl.addLayout(dv, 1)
        self.dest_change = _btn("", "destBtn")
        self.dest_change.clicked.connect(self.pick_out_dir)
        self.dest_open = _btn("", "destBtn")
        self.dest_open.clicked.connect(self.open_out_dir)
        dl.addWidget(self.dest_change)
        dl.addWidget(self.dest_open)
        lay.addWidget(dest)

        # ---- ffmpeg command
        w = QWidget()
        cl = QVBoxLayout(w)
        cl.setContentsMargins(0, 14, 0, 14)
        cl.setSpacing(6)
        row = QHBoxLayout()
        self.cmd_toggle = _btn("", "link")
        self.cmd_toggle.clicked.connect(self.toggle_cmd)
        self.copy_btn = _btn("", "link")
        self.copy_btn.clicked.connect(self.copy_cmd)
        row.addWidget(self.cmd_toggle)
        row.addStretch()
        row.addWidget(self.copy_btn)
        cl.addLayout(row)
        self.cmd = QPlainTextEdit()
        self.cmd.setObjectName("cmd")
        self.cmd.setReadOnly(True)
        self.cmd.setFixedHeight(104)
        self.cmd.hide()
        cl.addWidget(self.cmd)
        self.form.addWidget(w)
        self.form.addStretch(1)

        # ---- footer
        footer = QWidget()
        footer.setObjectName("panelFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fv = QVBoxLayout(footer)
        fv.setContentsMargins(20, 14, 20, 14)
        fv.setSpacing(0)
        tot = QHBoxLayout()
        self.l_total = _label("", "totalLabel")
        tot.addWidget(self.l_total)
        tot.addStretch()
        self.total = _label("—", "totalValue")
        self.total.setTextFormat(Qt.TextFormat.RichText)
        tot.addWidget(self.total)
        fv.addLayout(tot)
        fv.addSpacing(12)
        self.go = ProgressButton("")
        self.go.clicked.connect(self.on_go)
        fv.addWidget(self.go)
        fv.addSpacing(10)
        st = QHBoxLayout()
        st.setSpacing(7)
        st.addStretch()
        st.addWidget(IconBadge("folder", 16, 15, plain=True, tint=True))
        self.l_saveto = _label("", "saveTo")
        st.addWidget(self.l_saveto)
        self.saveto = ElideLabel()
        self.saveto.setObjectName("saveToPath")
        self.saveto.setMaximumWidth(250)
        st.addWidget(self.saveto)
        st.addStretch()
        fv.addLayout(st)
        outer.addWidget(footer)
        return panel

    # ======================================================== language / theme
    def retranslate(self):
        self.h_title.setText(t("title") if self.env.is_addon else t("queue"))
        self.add_btn.setText(t("add"))
        self.clear_btn.setText(t("clear"))
        self.empty.setText(t("empty"))
        self.drop.texts = (t("drop_b"), t("drop_or"), t("drop_s"))
        self.drop.update()
        self.overlay.text = t("drop_overlay")
        for hdr, key in ((self.h_preset, "sec_preset"), (self.h_format, "sec_format"), (self.h_enc, "sec_enc"),
                         (self.h_mode, "sec_mode"), (self.h_colors, "sec_colors"), (self.h_size, "sec_size"),
                         (self.h_audio, "sec_audio"), (self.h_dest, "sec_dest")):
            hdr.title.setText(t(key))
        self.save_btn.setText(t("p_save"))
        self.import_btn.setText("⤓ " + t("p_import"))
        self.preset_note.setText(t("p_note"))
        self.seg_enc.set_options([("cpu", t("cpu"), t("cpu_s")), ("gpu", t("gpu"), t("gpu_s"))])
        self.seg_mode.set_options([("quality", t("mode_quality"), ""), ("size", t("mode_size"), ""),
                                   ("ratio", t("mode_ratio"), "")])
        self.seg_audio.set_options([("keep", t("a_keep"), ""), ("compress", t("a_compress"), "128k"),
                                    ("none", t("a_none"), "")])
        self.seg_out.set_options([("beside", t("o_beside"), t("o_beside_s")), ("subfolder", t("o_sub"), t("o_sub_s")),
                                  ("custom", t("o_custom"), t("o_custom_s"))])
        self.l_quality.setText(t("quality"))
        self.l_smaller.setText(t("smaller"))
        self.l_better.setText(t("better"))
        self.l_fit.setText(t("fit_in"))
        self.l_shrink.setText(t("shrink_by"))
        self.l_colors.setText(t("colors"))
        self.l_lighter.setText(t("lighter"))
        self.l_smoother.setText(t("smoother"))
        self.l_fps.setText(t("fps"))
        for v, c in self.size_quick.items():
            c.setText(f"{v} {t('mb')}" if v == 8 else str(v))
            c.updateGeometry()
        self.res_chips[None].setText(t("res_src"))
        self.res_chips[None].updateGeometry()
        self.tk_row.title.setText(t("use_tk"))
        self.tk_row.sub.setText(t("use_tk_s"))
        self.dest_change.setText(t("d_change"))
        self.dest_open.setText(t("d_open"))
        self.copy_btn.setText(t("copy"))
        self.cmd_toggle.setText(t("cmd") + ("  ⌃" if self.cmd.isVisible() else "  ⌄"))
        self.l_total.setText(t("total"))
        self.l_saveto.setText(t("save_to"))
        self.go.setText(t("stop") if self.running else t("go"))
        self._preset_sig = None
        self._codec_fmt = None
        for it in self.items:
            if it.media and it.widget:
                it.widget.set_media(it.media, it.thumb)
                self._refresh_item_status(it)
        self.render()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        for w in self.findChildren(QWidget):
            w.update()
        self.update()

    # ======================================================== capabilities
    def _detect_caps(self):
        enc = ff.list_encoders()
        gpu = {c: False for c in GPU_ENCODERS}
        errors = {}
        if GPU_ENCODERS["h264"] in enc:
            gpu["h264"], errors["h264"] = ff.encoder_check(GPU_ENCODERS["h264"])
            if gpu["h264"]:
                for c in ("h265", "av1"):
                    if GPU_ENCODERS[c] in enc:
                        gpu[c], errors[c] = ff.encoder_check(GPU_ENCODERS[c])
        name = ff.gpu_name()
        self.bridge.caps.emit(enc, gpu, errors, name)

    def _on_caps(self, enc, gpu, errors, name):
        self.encoders, self.gpu, self.gpu_errors, self.gpu_label = enc, gpu, errors, name
        if self._first_run and gpu.get("h264"):
            self.s.encoder = "gpu"
        self._fix_encoder()
        self.render()

    def _gpu_ok(self, codec: str) -> bool:
        if codec not in GPU_ENCODERS:
            return False
        if self.encoders is None:
            return True
        return self.gpu.get(codec, False)

    def _cpu_ok(self, codec: str) -> bool:
        if codec == "gif" or self.encoders is None:
            return True
        return CPU_ENCODERS[codec] in self.encoders

    def _fix_encoder(self):
        if self.s.encoder == "gpu" and not self._gpu_ok(self.s.codec):
            self.s.encoder = "cpu"
        if self.s.encoder == "cpu" and not self._cpu_ok(self.s.codec) and self._gpu_ok(self.s.codec):
            self.s.encoder = "gpu"

    def _gpu_status(self) -> tuple[str, str, str]:
        """text, led colour, tooltip"""
        green, amber, grey = "#6fcf97", "#d0a060", theme.p["faint"]
        s = self.s
        if self.encoders is None:
            return t("gpu_checking"), grey, ""
        if s.is_gif:
            return t("gif_cpu"), grey, ""
        if s.codec == "vp9":
            return t("vp9_cpu"), grey, ""
        err = self.gpu_errors.get("h264", "")
        if not any(self.gpu.values()):
            low = err.lower()
            if "api version" in low or "driver does not support" in low:
                return t("gpu_driver"), amber, err
            if self.gpu_label:
                return t("gpu_fail"), amber, err
            return t("gpu_none"), amber, err
        name = self.gpu_label or t("nvidia")
        if s.codec == "av1" and not self.gpu.get("av1"):
            return t("av1_old", n=name), amber, self.gpu_errors.get("av1", "")
        return t("gpu_ready", n=name, av1="AV1 " if s.codec == "av1" else ""), green, ""

    # ======================================================== settings changes
    def change(self, **kw):
        for k, v in kw.items():
            setattr(self.s, k, v)
        self.s.normalize()
        self._fix_encoder()
        self.preset_id = "custom"
        self.render()
        self._save()

    def on_format(self, fmt: str):
        ids = [c[0] for c in CODECS[fmt]]
        self.change(format=fmt, codec=self.s.codec if self.s.codec in ids else ids[0])

    # ======================================================== presets
    def all_presets(self) -> list[Preset]:
        return BUILTIN_PRESETS + self.custom

    def preset_title(self, p: Preset) -> str:
        return t("p_" + p.id) if any(b.id == p.id for b in BUILTIN_PRESETS) else p.title

    def preset_values(self) -> dict:
        d = self.s.to_dict()
        d.pop("encoder", None)      # depends on the PC, not on the preset
        return d

    def choose_preset(self, pid: str):
        p = next((x for x in self.all_presets() if x.id == pid), None)
        if p:
            enc = self.s.encoder
            self.s = apply_preset(self.s, p)
            self.s.encoder = enc
            self._fix_encoder()
        self.preset_id = pid
        self.render()
        self._save()

    def _unique_name(self, name: str) -> str:
        names = {self.preset_title(p) for p in self.all_presets()}
        out, n = name, 2
        while out in names:
            out = f"{name} ({n})"
            n += 1
        return out

    def _add_custom(self, name: str, values: dict) -> Preset:
        p = Preset(f"my{len(self.custom)}_{abs(hash((name, len(self.custom)))) % 100000}", name, values)
        self.custom.append(p)
        return p

    def save_preset(self):
        name, ok = QInputDialog.getText(self, t("p_new_title"), t("p_name"), text=t("p_mine", n=len(self.custom) + 1))
        if not ok or not name.strip():
            return
        p = self._add_custom(self._unique_name(name.strip()), self.preset_values())
        self.preset_id = p.id
        self.render()
        self._save()
        self.env.toast(t("t_saved_preset", n=p.title))

    def preset_menu(self, pid: str, pos):
        if pid == "custom":
            p = Preset("custom", t("p_own"), self.preset_values())
        else:
            p = next((x for x in self.all_presets() if x.id == pid), None)
            if not p:
                return
        mine = p in self.custom
        menu = QMenu(self)
        title = QAction(self.preset_title(p), menu)
        title.setEnabled(False)
        menu.addAction(title)
        menu.addSeparator()
        menu.addAction(t("m_share"), lambda: self.export_preset(p))
        menu.addAction(t("m_dup"), lambda: self.duplicate_preset(p))
        if mine:
            menu.addAction(t("m_rename"), lambda: self.rename_preset(p))
            menu.addSeparator()
            menu.addAction(t("m_delete"), lambda: self.delete_preset(p))
        menu.exec(pos)

    def export_preset(self, p: Preset):
        name = self.preset_title(p)
        values = self.preset_values() if p.id == "custom" else {k: v for k, v in
                                                                  apply_preset(EncodeSettings(), p).to_dict().items()
                                                                  if k != "encoder"}
        start = Path(self.share_dir or Path.home() / "Documents") / (wtp.safe_filename(name) + wtp.EXT)
        path, _ = QFileDialog.getSaveFileName(self, t("share_title"), str(start), t("wtp_filter"))
        if not path:
            return
        out = wtp.write(path, wtp.make(ADDON_ID, name, values, t("title"), __version__))
        self.share_dir = str(out.parent)
        self._save()
        self.env.toast(t("t_exported", f=out.name), 3500)

    def duplicate_preset(self, p: Preset):
        values = self.preset_values() if p.id == "custom" else dict(apply_preset(EncodeSettings(), p).to_dict())
        values.pop("encoder", None)
        c = self._add_custom(self._unique_name(t("p_copy", n=self.preset_title(p))), values)
        self.choose_preset(c.id)
        self.env.toast(t("t_dup"))

    def rename_preset(self, p: Preset):
        name, ok = QInputDialog.getText(self, t("p_rename_title"), t("p_name"), text=p.title)
        if ok and name.strip():
            p.title = name.strip()
            self._preset_sig = None
            self.render()
            self._save()

    def delete_preset(self, p: Preset):
        self.custom.remove(p)
        if self.preset_id == p.id:
            self.preset_id = "custom"
        self._preset_sig = None
        self.render()
        self._save()
        self.env.toast(t("t_deleted", n=p.title))

    def import_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, t("import_title"), self.share_dir or str(Path.home() / "Downloads"),
                                              t("wtp_filter"))
        if path:
            self.import_file(path)

    def import_file(self, path: str):
        try:
            data = wtp.read(path)
        except wtp.PresetError:
            self.env.toast(t("t_bad_wtp"))
            return
        self.import_preset(data)

    def import_preset(self, data: dict):
        """Also called by the toolkit when a .wtp is double-clicked."""
        try:
            data = wtp.parse(data)
        except wtp.PresetError:
            self.env.toast(t("t_bad_wtp"))
            return
        if data["addon"] != ADDON_ID:
            self.env.toast(t("t_wrong_addon", n=data.get("addon_name") or data["addon"]), 4000)
            return
        values = {k: v for k, v in data["settings"].items() if k != "encoder"}
        name = self._unique_name(str(data.get("name") or "preset"))
        p = self._add_custom(name, values)
        self.choose_preset(p.id)
        author = data.get("author")
        self.env.toast(t("t_imported_from", n=name, a=author) if author else t("t_imported", n=name), 3500)

    # ======================================================== destination
    def set_use_tk(self, on: bool):
        self.use_tk = on
        self.render()
        self._save()

    def set_own_mode(self, mode: str):
        if mode == "custom" and not os.path.isdir(self.out_dir):
            if not self.pick_out_dir():
                self.seg_out.set_value(self.own_mode)
                return
        self.own_mode = mode
        self.render()
        self._save()

    def pick_out_dir(self) -> bool:
        d = QFileDialog.getExistingDirectory(self, t("d_pick"), self.out_dir or self.last_dir)
        if not d:
            return False
        self.out_dir = os.path.normpath(d)
        self.own_mode = "custom"
        self.render()
        self._save()
        return True

    def effective_dest(self) -> tuple[str, str | None]:
        if self.env.is_addon and self.use_tk:
            return "toolkit", self.env.toolkit_folder()
        return self.own_mode, (self.out_dir if self.own_mode == "custom" else None)

    def open_out_dir(self):
        mode, d = self.effective_dest()
        if d:
            os.makedirs(d, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def _render_dest(self):
        mode, d = self.effective_dest()
        self.tk_row.switch.set_now(self.use_tk)
        own = not (self.env.is_addon and self.use_tk)
        self.seg_out.setVisible(own)
        self.seg_out.set_value(self.own_mode)
        it = next((i for i in self.items if i.media), None)
        sample = it.media.path if it else str(Path.home() / "Videos" / "clip.mp4")
        ex = output_path(sample, self.s.format, "beside" if mode == "toolkit" else mode, d, self.env.suffix())
        if mode == "toolkit":
            big, small, short = d or "—", t("d_tk_s"), d or "—"
        elif mode == "beside":
            big, small, short = t("d_beside"), t("d_example", p=ex), t("beside_short")
        elif mode == "subfolder":
            big, small, short = "…" + os.sep + "compressed" + os.sep, t("d_example", p=ex), t("sub_short")
        else:
            big, small, short = d or "—", t("d_custom_s"), d or "—"
        self.dest_path.set_full(big)
        self.dest_sub.set_full(small)
        self.dest_change.setVisible(mode == "custom")
        self.dest_open.setVisible(mode in ("toolkit", "custom"))
        self.saveto.set_full(short)

    # ======================================================== command preview
    def toggle_cmd(self):
        self.cmd.setVisible(not self.cmd.isVisible())
        self.cmd_toggle.setText(t("cmd") + ("  ⌃" if self.cmd.isVisible() else "  ⌄"))

    def copy_cmd(self):
        QGuiApplication.clipboard().setText(self.cmd.toPlainText())
        self.env.toast(t("t_cmd_copied"))

    # ======================================================== render
    def _sample_media(self) -> ff.MediaInfo:
        it = next((i for i in self.items if i.media), None)
        if it:
            return it.media
        return ff.MediaInfo("input.mp4", 250, 1920, 1080, 60, 120, "h264", "aac", 160)

    def render(self):
        s = self.s
        sig = tuple((p.id, self.preset_title(p)) for p in self.all_presets())
        if sig != self._preset_sig:
            self._preset_sig = sig
            self.preset_flow.clear()
            self.preset_chips = {}
            for p in self.all_presets():
                c = Chip(self.preset_title(p))
                c.clicked.connect(lambda _=False, pid=p.id: self.choose_preset(pid))
                self.preset_flow.addWidget(c)
                self.preset_chips[p.id] = c
            c = Chip(t("p_own"), dot=True)
            c.clicked.connect(lambda: self.choose_preset("custom"))
            self.preset_flow.addWidget(c)
            self.preset_chips["custom"] = c
            for pid, c in self.preset_chips.items():
                c.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                c.customContextMenuRequested.connect(
                    lambda pos, pid=pid, c=c: self.preset_menu(pid, c.mapToGlobal(pos)))
        if self.preset_id not in self.preset_chips:
            self.preset_id = "custom"
        for pid, c in self.preset_chips.items():
            c.setChecked(pid == self.preset_id)

        if self._codec_fmt != s.format:
            self._codec_fmt = s.format
            self.codec_flow.clear()
            self.codec_chips = {}
            for cid, title, sub in CODECS[s.format]:
                c = Chip(title, CODEC_SUB_EN.get(sub, sub) if lang() == "en" else sub)
                c.clicked.connect(lambda _=False, cid=cid: self.change(codec=cid))
                self.codec_flow.addWidget(c)
                self.codec_chips[cid] = c
        for cid, c in self.codec_chips.items():
            c.setChecked(cid == s.codec)
            c.setEnabled(self._cpu_ok(cid) or self._gpu_ok(cid))

        self.seg_format.set_value(s.format)
        self.seg_enc.set_disabled("gpu", not self._gpu_ok(s.codec))
        self.seg_enc.set_disabled("cpu", not self._cpu_ok(s.codec))
        self.seg_enc.set_value(s.encoder)
        self.seg_mode.set_value(s.mode)
        self.seg_audio.set_value(s.audio)
        text, color, tip = self._gpu_status()
        self.gpu_text.setText(text)
        self.gpu_text.setToolTip(tip)
        self.gpu_led.set_color(color)
        self.gpu_led.setToolTip(tip)

        self.g_mode.setVisible(not s.is_gif)
        self.g_audio.setVisible(not s.is_gif)
        self.g_colors.setVisible(s.is_gif)
        self.mode_stack.setCurrentIndex({"quality": 0, "size": 1, "ratio": 2}[s.mode])
        for sl, v in ((self.sl_quality, s.quality), (self.sl_size, min(s.size_mb, 200)),
                      (self.sl_ratio, round(s.ratio * 2)), (self.sl_colors, s.colors // 16),
                      (self.sl_fps, s.fps_idx)):
            sl.blockSignals(True)
            sl.setValue(v)
            sl.blockSignals(False)
            sl.update()
        muted = theme.p["muted"]
        self.q_val.setText(f"{'CQ' if s.encoder == 'gpu' else 'CRF'} {quality_value(s)}"
                           f"&nbsp;&nbsp;<span style='color:{muted}; font-weight:600'>{quality_word(s.quality)}</span>")
        self.s_val.setText(f"{s.size_mb} {t('mb')}")
        self.r_val.setText(f"×{s.ratio:g}".replace(".", t("dec")))
        self.c_val.setText(str(s.colors))
        f = s.fps_target
        self.fps_val.setText(t("fps_src") if f is None else str(f))
        for v, c in self.size_quick.items():
            c.setChecked(v == s.size_mb)
        for v, c in self.ratio_quick.items():
            c.setChecked(abs(v - s.ratio) < 0.01)
        for v, c in self.res_chips.items():
            c.setChecked(v == s.res)

        orig = new = 0.0
        for it in self.items:
            if not it.media or not it.widget:
                continue
            orig += it.media.size_mb
            if it.status == "done" and it.out_mb is not None:
                new += it.out_mb
            else:
                e = estimate_mb(s, it.media)
                new += e
                it.widget.set_estimate(e, it.media.size_mb)
        n = len(self.items)
        self.q_meta.setText(f"{files_word(n)} · {fmt_mb(orig)}" if n else t("no_files"))
        self.empty.setVisible(n == 0)
        tint = theme.p["tint"]
        self.total.setText(f"{fmt_mb(orig)} → {fmt_mb(new)}&nbsp;<span style='color:{tint}; font-size:9pt'>"
                           f"{fmt_pct(new, orig)}</span>" if orig else "—")
        self._render_dest()
        m = self._sample_media()
        mode, d = self.effective_dest()
        out = output_path(m.path, s.format, mode, d, self.env.suffix()) if self.items else f"input{self.env.suffix()}.{s.format}"
        self.cmd.setPlainText(preview(build_args(s, m, out)))
        self.go.setEnabled(self.running or any(i.media for i in self.items))
        self.clear_btn.setEnabled(bool(self.items))

    # ======================================================== queue
    def add_dialog(self):
        exts = " ".join(f"*{e}" for e in sorted(ff.VIDEO_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, t("pick_videos"), self.last_dir,
                                                f"{t('video_filter')} ({exts});;{t('all_files')} (*)")
        if files:
            self.last_dir = os.path.dirname(files[0])
            self._save()
            self.add_paths(files)

    def add_paths(self, paths: list[str]) -> int:
        for p in paths:
            if p.lower().endswith(wtp.EXT):
                self.import_file(p)
        paths = [p for p in paths if not p.lower().endswith(wtp.EXT)]
        files = ff.collect_paths(paths)
        known = {os.path.normcase(i.path) for i in self.items}
        added = 0
        for p in files:
            if os.path.normcase(p) in known:
                continue
            known.add(os.path.normcase(p))
            self._next_id += 1
            it = Item(self._next_id, p)
            w = QueueItem(it.id, os.path.basename(p))
            w.remove_requested.connect(self.remove_item)
            w.open_requested.connect(self.reveal_item)
            w.set_state("probing", t("st_reading"))
            it.widget = w
            self.items.append(it)
            self.list_lay.insertWidget(self.list_lay.count() - 1, w)
            self.pool.submit(self._probe_task, it.id, p)
            added += 1
        if paths and not files:
            self.env.toast(t("t_no_videos"))
        self.render()
        return added

    def _probe_task(self, item_id: int, path: str):
        m = ff.probe(path)
        th = ff.thumbnail(path, m.duration) if m else None
        self.bridge.probed.emit(item_id, m, th)

    def _find(self, item_id: int) -> Item | None:
        return next((i for i in self.items if i.id == item_id), None)

    def _refresh_item_status(self, it: Item):
        w = it.widget
        if it.status == "queued":
            w.set_state("queued", t("st_queued"))
        elif it.status == "done" and it.out_mb is not None:
            w.set_state("done", t("st_done", a=fmt_mb(it.media.size_mb), b=fmt_mb(it.out_mb)), 1)
            w.set_estimate(it.out_mb, it.media.size_mb, done=True)

    def _on_probed(self, item_id: int, media, thumb):
        it = self._find(item_id)
        if not it:
            return
        it.media, it.thumb = media, thumb
        if media is None:
            it.status = "error"
            it.widget.set_state("error", t("st_bad"))
            it.widget.meta.setText("—")
        else:
            it.status = "queued"
            it.widget.set_media(media, thumb)
            it.widget.set_state("queued", t("st_queued"))
        self.render()
        if self._smoke_done and not self.running and all(i.status != "probing" for i in self.items):
            QTimer.singleShot(300, self.on_go)

    def remove_item(self, item_id: int):
        it = self._find(item_id)
        if not it or it.status == "work":
            return
        self.items.remove(it)
        w = it.widget
        w.fade_out(w.deleteLater)
        self.render()

    def clear_queue(self):
        for it in list(self.items):
            if it.status != "work":
                self.remove_item(it.id)

    def reveal_item(self, item_id: int):
        it = self._find(item_id)
        path = it.out_path if it and it.status == "done" else (it.path if it else None)
        if not path or not os.path.exists(path):
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    # ======================================================== encoding
    def on_go(self):
        if self.running:
            self.stop_requested = True
            if self.job:
                self.job.stop()
            return
        if not ff.FFMPEG:
            self.env.toast(t("no_ffmpeg"), 5000)
            return
        todo = [i for i in self.items if i.media and i.status in ("queued", "error")]
        if not todo:
            todo = [i for i in self.items if i.media and i.status == "done"]
        if not todo:
            self.env.toast(t("t_nothing"))
            return
        mode, d = self.effective_dest()
        if mode in ("custom", "toolkit") and not d:
            if not self.pick_out_dir():
                return
        for it in todo:
            it.status = "queued"
            it.progress = 0
            it.widget.set_state("queued", t("st_queued"))
        self.run_ids = [i.id for i in todo]
        self.run_settings = self.s.copy()
        self.running = True
        self.stop_requested = False
        self.busy_changed.emit(True)
        self.go.setText(t("stop"))
        self.render()
        self._run_next()

    def _run_next(self):
        if self.stop_requested:
            return self._finish(stopped=True)
        it = next((self._find(i) for i in self.run_ids if self._find(i) and self._find(i).status == "queued"), None)
        if it is None:
            return self._finish()
        mode, d = self.effective_dest()
        out = output_path(it.media.path, self.run_settings.format, mode, d, self.env.suffix())
        it.status = "work"
        it.out_path = out
        it.widget.set_state("work", t("st_start"), 0)
        job = EncodeJob(build_args(self.run_settings, it.media, out), it.media.duration, out, self)
        job.progress.connect(lambda f, sp, it=it: self._on_progress(it, f, sp))
        job.finished.connect(lambda ok, err, it=it: self._on_job_done(it, ok, err))
        self.job = job
        job.start()

    def _overall(self) -> float:
        ids = [i for i in self.run_ids if self._find(i)]
        if not ids:
            return 0.0
        total = 0.0
        for i in ids:
            it = self._find(i)
            total += 1.0 if it.status == "done" else (it.progress if it.status == "work" else 0.0)
        return total / len(ids)

    def _on_progress(self, it: Item, frac: float, speed: float):
        if it.status != "work":
            return
        it.progress = frac
        text = t("st_work", p=round(frac * 100))
        if speed > 0:
            text += f" · {speed:.1f}×".replace(".", t("dec"))
        it.widget.set_state("work", text, frac)
        self.go.set_progress(self._overall())

    def _on_job_done(self, it: Item, ok: bool, err: str):
        self.job = None
        if ok:
            it.status = "done"
            it.progress = 1
            it.out_mb = os.path.getsize(it.out_path) / 1048576
            self._refresh_item_status(it)
        elif self.stop_requested:
            it.status = "queued"
            it.progress = 0
            it.widget.set_state("queued", t("st_queued"))
        else:
            it.status = "error"
            first = err.strip().splitlines()[-1] if err.strip() else "?"
            it.widget.set_state("error", t("st_error", e=first[:90]))
            it.widget.status.setToolTip(err)
        self.go.set_progress(self._overall())
        self.render()
        QTimer.singleShot(0, self._run_next)

    def _finish(self, stopped: bool = False):
        self.running = False
        self.stop_requested = False
        self.busy_changed.emit(False)
        self.go.setText(t("go"))
        self.go.set_progress(0)
        self.render()
        run = [self._find(i) for i in self.run_ids if self._find(i)]
        done = [i for i in run if i.status == "done"]
        failed = [i for i in run if i.status == "error"]
        if stopped:
            self.env.toast(t("t_stopped"))
        elif done:
            saved = sum(i.media.size_mb - i.out_mb for i in done)
            msg = t("t_done", s=fmt_mb(max(saved, 0)), d=self.saveto._full)
            if failed:
                msg += t("t_errors", n=len(failed))
            self.env.toast(msg, 4500)
            if self.window():
                from PySide6.QtWidgets import QApplication
                QApplication.alert(self.window())
        elif failed:
            self.env.toast(t("t_failed", n=len(failed)), 4500)
        if self._smoke_done:
            cb, self._smoke_done = self._smoke_done, None
            QTimer.singleShot(600, lambda: cb(bool(done) and not failed))

    def stop(self):
        self.stop_requested = True
        if self.job:
            self.job.stop()

    # ======================================================== smoke test (CI)
    def smoke(self, files: list[str], on_done) -> bool:
        self._smoke_done = on_done
        return bool(self.add_paths(files))

    # ======================================================== drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.overlay.show_overlay(True)

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.overlay.show_overlay(False)

    def dropEvent(self, e):
        self.overlay.show_overlay(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.add_paths(paths)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.rect())

    def is_busy(self) -> bool:
        """toolkit 1.2+: a quiet add-on update waits while this is True."""
        return bool(self.running)

    def shutdown(self):
        self.stop()
        self.pool.shutdown(wait=False, cancel_futures=True)
