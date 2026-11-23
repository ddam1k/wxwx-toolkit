"""The right panel of Photo: preset, format, quality, size, privacy, where to save — and the footer."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from ..core import opts
from ..core.i18n import files, fmt_size, t
from ..core.opts import Opts
from ..kit.common import SmoothScroll, label
from .widgets import Chip, FlowLayout, IconBadge, ProgressButton, SectionHeader, Segmented, SplitSlider, SwitchRow


class OptionsPanel(QWidget):
    changed = Signal()               # the picture settings changed → new estimates
    go = Signal()

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.setObjectName("panelRight")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self.o = opts.from_dict(host.get("opts"))
        self.alpha = False                    # any picture in the list is transparent
        self._busy = False
        self._quiet = False
        self._build()
        self.retranslate()

    # ------------------------------------------------------------ build
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

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = SmoothScroll()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.form = QVBoxLayout(body)
        self.form.setContentsMargins(20, 2, 16, 8)
        self.form.setSpacing(0)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, 1)

        # preset
        _w, self.h_preset, lay = self._block("preset")
        box = QWidget()
        fl = FlowLayout(box, spacing=8)
        self.preset_chips: dict[str, Chip] = {}
        for k in (*opts.PRESETS, "own"):
            c = Chip("", small=True)
            c.clicked.connect(lambda _=False, key=k: self._preset(key))
            fl.addWidget(c)
            self.preset_chips[k] = c
        lay.addWidget(box)
        self.preset_note = label("", "note", wrap=True)
        lay.addWidget(self.preset_note)

        # format
        _w, self.h_fmt, lay = self._block("format")
        self.seg_fmt = Segmented([(f, f, "") for f in opts.FORMATS])
        self.seg_fmt.changed.connect(self._fmt)
        lay.addWidget(self.seg_fmt)
        self.fmt_note = label("", "note", wrap=True)
        self.fmt_note.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.fmt_note)

        # quality
        self.b_q, self.h_q, lay = self._block("gauge")
        qh = QHBoxLayout()
        qh.setSpacing(10)
        self.q_value = label("", "qValue")
        self.q_word = label("", "qWord")
        qh.addWidget(self.q_value)
        qh.addWidget(self.q_word, 1, Qt.AlignmentFlag.AlignVCenter)
        self.q_wrap = QWidget()
        qv = QVBoxLayout(self.q_wrap)
        qv.setContentsMargins(0, 0, 0, 0)
        qv.setSpacing(4)
        qv.addLayout(qh)
        self.slider = SplitSlider(opts.Q_MIN, opts.Q_MAX)
        self.slider.valueChanged.connect(self._q)
        qv.addWidget(self.slider)
        ends = QHBoxLayout()
        self.q_l, self.q_r = label("", "qEnd"), label("", "qEnd")
        ends.addWidget(self.q_l)
        ends.addStretch()
        ends.addWidget(self.q_r)
        qv.addLayout(ends)
        lay.addWidget(self.q_wrap)
        self.q_note = label("", "note", wrap=True)
        self.q_note.setProperty("hint", True)
        lay.addWidget(self.q_note)
        self.q_png = label("", "note", wrap=True)
        lay.addWidget(self.q_png)
        self._q_timer = QTimer(self)
        self._q_timer.setSingleShot(True)
        self._q_timer.setInterval(260)
        self._q_timer.timeout.connect(self.changed)

        # size
        _w, self.h_size, lay = self._block("size")
        sb = QWidget()
        sl = FlowLayout(sb, spacing=8)
        self.size_chips: dict[int, Chip] = {}
        for v in opts.SIZES:
            c = Chip(str(v) if v else "", small=True)
            c.clicked.connect(lambda _=False, val=v: self._size(val))
            sl.addWidget(c)
            self.size_chips[v] = c
        self.px = QLineEdit()
        self.px.setObjectName("pxEdit")
        self.px.setMaxLength(5)
        self.px.editingFinished.connect(self._px)
        sl.addWidget(self.px)
        lay.addWidget(sb)
        self.size_note = label("", "note", wrap=True)
        lay.addWidget(self.size_note)

        # privacy
        _w, self.h_priv, lay = self._block("shield")
        self.sw_strip = SwitchRow()
        self.sw_strip.toggled.connect(self._strip)
        lay.addWidget(self.sw_strip)
        self.strip_note = label("", "note", wrap=True)
        lay.addWidget(self.strip_note)

        # destination
        _w, self.h_dest, lay = self._block("folder")
        self.sw_tk = SwitchRow()
        self.sw_tk.toggled.connect(lambda on: self._dest(on))
        lay.addWidget(self.sw_tk)
        self.dest = QWidget()
        self.dest.setObjectName("destBox")
        self.dest.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        dl = QHBoxLayout(self.dest)
        dl.setContentsMargins(12, 10, 12, 10)
        dl.setSpacing(10)
        dl.addWidget(IconBadge("folder", 18, 16, plain=True, tint=True))
        dv = QVBoxLayout()
        dv.setSpacing(2)
        self.dest_path = label("", "destPath", wrap=True)
        self.dest_sub = label("", "destSub")
        dv.addWidget(self.dest_path)
        dv.addWidget(self.dest_sub)
        dl.addLayout(dv, 1)
        lay.addWidget(self.dest)
        self.form.addStretch(1)

        # footer
        footer = QWidget()
        footer.setObjectName("panelFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fv = QVBoxLayout(footer)
        fv.setContentsMargins(20, 14, 20, 14)
        fv.setSpacing(0)
        tot = QHBoxLayout()
        self.l_total = label("", "totalLabel")
        tot.addWidget(self.l_total)
        tot.addStretch()
        self.total = label("—", "totalValue")
        self.total.setTextFormat(Qt.TextFormat.RichText)
        tot.addWidget(self.total)
        fv.addLayout(tot)
        fv.addSpacing(12)
        self.go_btn = ProgressButton("")
        self.go_btn.clicked.connect(self.go)
        fv.addWidget(self.go_btn)
        fv.addSpacing(10)
        st = QHBoxLayout()
        st.setSpacing(7)
        st.addWidget(IconBadge("folder", 16, 15, plain=True, tint=True))
        self.saveto = label("", "saveTo", wrap=True)
        self.saveto.setTextFormat(Qt.TextFormat.RichText)
        st.addWidget(self.saveto, 1)
        fv.addLayout(st)
        outer.addWidget(footer)

    # ------------------------------------------------------------ texts & state
    def retranslate(self):
        self.h_preset.title.setText(t("b_preset"))
        for k, c in self.preset_chips.items():
            c.setText(t("p_" + k))
        self.preset_note.setText(t("preset_note"))
        self.h_fmt.title.setText(t("b_format"))
        self.seg_fmt.set_options([(f, t("f_" + f), "") for f in opts.FORMATS])
        self.h_q.title.setText(t("b_quality"))
        self.q_l.setText(t("q_light"))
        self.q_r.setText(t("q_orig"))
        self.q_note.setText(t("q_note"))
        self.q_png.setText(t("q_png"))
        self.h_size.title.setText(t("b_size"))
        self.size_chips[0].setText(t("sz_0"))
        self.px.setPlaceholderText(t("sz_own"))
        self.size_note.setText(t("size_note"))
        self.h_priv.title.setText(t("b_privacy"))
        self.sw_strip.title.setText(t("strip_t"))
        self.sw_strip.sub.setText(t("strip_s"))
        self.strip_note.setText(t("strip_note"))
        self.h_dest.title.setText(t("b_dest"))
        self.sw_tk.title.setText(t("tk_t"))
        self.l_total.setText(t("total"))
        self.refresh()

    def suffix(self) -> str:
        try:
            return self.host.suffix() if hasattr(self.host, "suffix") else "_wx"
        except Exception:
            return "_wx"

    def use_tk(self) -> bool:
        return bool(self.host.get("use_tk", True)) and hasattr(self.host, "folder")

    def refresh(self):
        o = self.o
        self._quiet = True
        cur = opts.matches(o)
        for k, c in self.preset_chips.items():
            if c.isChecked() != (k == cur):
                c.setChecked(k == cur)
        self.seg_fmt.set_value(o.fmt, animated=False)
        note = t("n_" + o.fmt)
        if self.alpha and o.fmt in ("jpg", "avif"):
            note += f' <b>{t("n_" + o.fmt + "_alpha")}</b>'
        self.fmt_note.setText(note)
        png = o.fmt == "png"
        self.q_wrap.setVisible(not png)
        self.q_note.setVisible(not png)
        self.q_png.setVisible(png)
        if self.slider.value() != o.q:
            self.slider.setValue(o.q)
        self.q_value.setText(str(o.q))
        self.q_word.setText(t(opts.quality_word(o.q)))
        own = o.long not in opts.SIZES
        for v, c in self.size_chips.items():
            if c.isChecked() != (v == o.long):
                c.setChecked(v == o.long)
        self.px.setProperty("on", own)
        self.px.style().unpolish(self.px)
        self.px.style().polish(self.px)
        if own and not self.px.hasFocus():
            self.px.setText(str(o.long))
        elif not own and not self.px.hasFocus():
            self.px.clear()
        self.sw_strip.switch.blockSignals(True)
        self.sw_strip.switch.set_now(o.strip)
        self.sw_strip.switch.blockSignals(False)
        self.strip_note.setVisible(not o.strip and o.fmt not in ("jpg", "orig"))
        tk = self.use_tk()
        self.sw_tk.switch.blockSignals(True)
        self.sw_tk.switch.set_now(tk)
        self.sw_tk.switch.blockSignals(False)
        sfx = self.suffix()
        self.sw_tk.sub.setText(t("tk_s", s=sfx))
        folder = self.host.folder("output") if tk else t("beside")
        self.dest_path.setText(folder)
        ext = "jpg" if o.fmt == "orig" else o.fmt
        self.dest_sub.setText(t("example", n=f"IMG_4021{sfx}.{ext}"))
        self.dest.setEnabled(not tk)
        self._quiet = False

    def set_totals(self, before: int, after: int | None, n_todo: int, ready: bool):
        if not before:
            self.total.setText("—")
        elif after is None or not ready:
            self.total.setText(f"{fmt_size(before)} → …")
        else:
            d = round((1 - after / before) * 100)
            col = "#8fd19e" if d >= 0 else "#e59a86"
            self.total.setText(f'{fmt_size(before)} → {fmt_size(after)}&nbsp;&nbsp;'
                               f'<span style="color:{col};font-size:9pt">{"−" + str(d) if d >= 0 else "+" + str(-d)}%</span>')
        if not self._busy:
            self.go_btn.setText(t("go_n", n=files(n_todo)) if n_todo else t("go"))
            self.go_btn.setEnabled(n_todo > 0)
        folder = html.escape(self.host.folder("output") if self.use_tk() else t("beside"))
        self.saveto.setText(f'{t("saveto")} <b>{folder}</b>')

    def set_busy(self, on: bool, frac: float = 0.0, text: str = ""):
        self._busy = on
        self.go_btn.set_progress(frac if on else 0.0)
        if on:
            self.go_btn.setText(text)
            self.go_btn.setEnabled(False)
        self.scroll.widget().setEnabled(not on)

    # ------------------------------------------------------------ edits
    def _commit(self, rerender: bool = True):
        self.o.preset = opts.matches(self.o)
        self.host.set("opts", self.o.to_dict())
        self.refresh()
        if rerender:
            self.changed.emit()

    def _preset(self, key: str):
        if key == "own":
            self.refresh()                   # «Свой» is what you get by changing something
            return
        p = opts.PRESETS[key]
        self.o = opts.Opts(**p.to_dict())
        self._commit()

    def _fmt(self, v: str):
        if self._quiet or v == self.o.fmt:
            return
        self.o.fmt = v
        self._commit()

    def _q(self, v: int):
        if self._quiet or v == self.o.q:
            return
        self.o.q = int(v)
        self.o.preset = opts.matches(self.o)
        self.host.set("opts", self.o.to_dict())
        self.q_value.setText(str(v))
        self.q_word.setText(t(opts.quality_word(v)))
        cur = opts.matches(self.o)
        for k, c in self.preset_chips.items():
            if c.isChecked() != (k == cur):
                c.setChecked(k == cur)
        self._q_timer.start()                 # while dragging: wait for the hand to stop

    def _size(self, v: int):
        self.o.long = v
        self._commit()

    def _px(self):
        txt = self.px.text().strip()
        if not txt:
            return
        try:
            v = int(txt)
        except ValueError:
            v = -1
        if not 64 <= v <= 16384:
            self.px.clear()
            self.host.toast(t("size_bad"))
            return
        if v != self.o.long:
            self.o.long = v
            self._commit()

    def _strip(self, on: bool):
        if self._quiet:
            return
        self.o.strip = on
        self._commit()

    def _dest(self, on: bool):
        if self._quiet:
            return
        self.host.set("use_tk", on)
        self.refresh()
        self.changed.emit()
