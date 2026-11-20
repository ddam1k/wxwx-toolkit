"""The right panel of Saves: what to save, quality, file, a piece, extras, where — and the «Скачать» footer."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                               QVBoxLayout, QWidget)

from ..core import ytdlp
from ..core.i18n import fmt_size, t
from ..kit.common import SmoothScroll, button, label
from .art import Elide, ModeCard
from .widgets import Chip, FlowLayout, IconBadge, ProgressButton, SectionHeader, Segmented, SwitchRow


def tcode(sec: float) -> str:
    sec = max(0, int(round(sec)))
    h, m, s = sec // 3600, sec // 60 % 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_t(text: str) -> float | None:
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    total = 0.0
    try:
        for part in text.split(":"):
            total = total * 60 + float(part or 0)
    except ValueError:
        return None
    return total


class OptionsPanel(QWidget):
    changed = Signal()              # options changed → page re-counts the total
    go = Signal()
    pick_dir = Signal()

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.setObjectName("panelRight")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self.info: ytdlp.Info | None = None
        self.kind = "none"              # none | video | playlist | batch
        self.o = ytdlp.Opts()
        self.quality_chips: dict[int, Chip] = {}
        self._build()
        self.retranslate()
        self.set_target(None, "none")

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
        self.fade = QGraphicsOpacityEffect(body)
        body.setGraphicsEffect(self.fade)
        self.body = body

        # what
        self.b_what, self.h_what, lay = self._block("import")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.m_video, self.m_audio = ModeCard("video"), ModeCard("audio")
        self.m_video.setChecked(True)
        self.m_video.clicked.connect(lambda: self._set_what("video"))
        self.m_audio.clicked.connect(lambda: self._set_what("audio"))
        row.addWidget(self.m_video)
        row.addWidget(self.m_audio)
        lay.addLayout(row)

        # quality
        self.b_q, self.h_q, lay = self._block("gauge")
        qw = QWidget()
        self.q_flow = FlowLayout(qw, spacing=8)
        lay.addWidget(qw)
        self.q_note = label("", "note", wrap=True)
        lay.addWidget(self.q_note)

        # file
        self.b_file, self.h_file, lay = self._block("format")
        self.seg_fmt = Segmented([("mp4o", "", "x"), ("mp4", "", "x"), ("orig", "", "x")])
        self.seg_fmt.changed.connect(self._set_fmt)
        lay.addWidget(self.seg_fmt)
        self.fmt_note = label("", "note", wrap=True)
        lay.addWidget(self.fmt_note)

        # audio format
        self.b_audio, self.h_audio, lay = self._block("sound")
        self.seg_afmt = Segmented([("mp3", "", "x"), ("m4a", "", "x"), ("opus", "", "x")])
        self.seg_afmt.changed.connect(self._set_afmt)
        lay.addWidget(self.seg_afmt)
        self.afmt_note = label("", "note", wrap=True)
        lay.addWidget(self.afmt_note)

        # a piece
        self.b_part, self.h_part, lay = self._block("frame")
        self.sw_part = SwitchRow()
        self.sw_part.toggled.connect(self._set_part)
        lay.addWidget(self.sw_part)
        self.times = QWidget()
        tl = QHBoxLayout(self.times)
        tl.setContentsMargins(0, 2, 0, 0)
        tl.setSpacing(8)
        self.t_from, self.t_to = QLineEdit(), QLineEdit()
        self.t_len = QLabel()
        self.t_lbls = []
        for edit in (self.t_from, self.t_to):
            box = QVBoxLayout()
            box.setSpacing(3)
            lb = label("", "tLbl")
            self.t_lbls.append(lb)
            box.addWidget(lb)
            edit.setObjectName("tEdit")
            edit.editingFinished.connect(self._times_edited)
            box.addWidget(edit)
            tl.addLayout(box, 1)
        box = QVBoxLayout()
        box.setSpacing(3)
        lb = label("", "tLbl")
        self.t_lbls.append(lb)
        box.addWidget(lb)
        self.t_len.setObjectName("tEdit")
        box.addWidget(self.t_len)
        tl.addLayout(box, 1)
        lay.addWidget(self.times)

        # extras
        self.b_extra, self.h_extra, lay = self._block("chip")
        self.sw_subs = SwitchRow()
        self.sw_subs.toggled.connect(self._set_subs)
        lay.addWidget(self.sw_subs)
        self.subs_w = QWidget()
        self.subs_flow = FlowLayout(self.subs_w, spacing=6)
        lay.addWidget(self.subs_w)
        self.sw_thumb = SwitchRow()
        self.sw_thumb.toggled.connect(self._set_thumb)
        lay.addWidget(self.sw_thumb)

        # destination
        self.b_dest, self.h_dest, lay = self._block("folder")
        self.sw_tk = SwitchRow()
        self.sw_tk.toggled.connect(self._set_tk)
        lay.addWidget(self.sw_tk)
        dest = QFrame()
        dest.setObjectName("destBox")
        dl = QHBoxLayout(dest)
        dl.setContentsMargins(12, 10, 8, 10)
        dl.setSpacing(11)
        dl.addWidget(IconBadge("folder", 22, 20, plain=True, tint=True))
        dv = QVBoxLayout()
        dv.setSpacing(2)
        self.dest_path = Elide("destPath", Qt.TextElideMode.ElideMiddle)
        self.dest_sub = label("", "destSub")
        dv.addWidget(self.dest_path)
        dv.addWidget(self.dest_sub)
        dl.addLayout(dv, 1)
        self.dest_btn = button("", "destBtn")
        self.dest_btn.clicked.connect(self.pick_dir)
        dl.addWidget(self.dest_btn)
        self.dest = dest
        lay.addWidget(dest)
        self.form.addStretch(1)

        # idle overlay text
        self.idle = QWidget(self)
        il = QVBoxLayout(self.idle)
        il.setContentsMargins(24, 0, 24, 0)
        il.setSpacing(4)
        il.addStretch(1)
        self.idle_t = label("", "idleTitle")
        self.idle_s = label("", "idleHint", wrap=True)
        for w in (self.idle_t, self.idle_s):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            il.addWidget(w)
        il.addStretch(2)
        self.idle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

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
        self.l_saveto = label("", "saveTo")
        st.addWidget(self.l_saveto)
        self.saveto = Elide("saveToPath", Qt.TextElideMode.ElideMiddle)
        st.addWidget(self.saveto, 1)
        fv.addLayout(st)
        outer.addWidget(footer)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.idle.setGeometry(0, 0, self.width(), self.scroll.height())

    # ------------------------------------------------------------ texts
    def retranslate(self):
        self.h_what.title.setText(t("b_what"))
        self.m_video.set_texts(t("m_video"), t("m_video_s"))
        self.m_audio.set_texts(t("m_audio"), t("m_audio_s"))
        self.h_q.title.setText(t("b_quality"))
        self.h_file.title.setText(t("b_file"))
        self.seg_fmt.set_options([(f, t("f_" + f), t(f"f_{f}_s")) for f in ytdlp.FMTS])
        self.h_audio.title.setText(t("b_audio"))
        self.seg_afmt.set_options([(a, t("a_" + a), t(f"a_{a}_s")) for a in ytdlp.AFMTS])
        self.h_part.title.setText(t("b_part"))
        self.sw_part.title.setText(t("part_t"))
        self.sw_part.sub.setText(t("part_s"))
        for lb, k in zip(self.t_lbls, ("from", "to", "len")):
            lb.setText(t(k).upper())
        self.h_extra.title.setText(t("b_extra"))
        self.sw_subs.title.setText(t("subs_t"))
        self.sw_subs.sub.setText(t("subs_s"))
        self.h_dest.title.setText(t("b_dest"))
        self.sw_tk.title.setText(t("tk_t"))
        self.sw_tk.sub.setText(t("tk_s"))
        self.dest_btn.setText(t("change"))
        self.l_total.setText(t("total"))
        self.l_saveto.setText(t("saveto"))
        self.idle_t.setText(t("idle_t"))
        self.idle_s.setText(t("idle_s"))
        self.refresh()

    # ------------------------------------------------------------ state from the page
    def set_defaults(self, q: int, fmt: str):
        self._def_q, self._def_fmt = q, fmt

    def set_target(self, info: ytdlp.Info | None, kind: str, error: bool = False):
        """kind: none | video | playlist | batch"""
        self.info, self.kind = info, kind
        q, fmt = getattr(self, "_def_q", 0), getattr(self, "_def_fmt", "mp4o")
        self.o.q = q if (info is None or not info.heights or q <= info.max_h) else 0
        self.o.fmt = fmt
        self.o.part = None
        self.o.subs = None
        self.o.what = "audio" if kind == "playlist" else "video"
        self.sw_part.switch.set_now(False)
        self.sw_subs.switch.set_now(False)
        live = kind != "none"
        self.fade.setOpacity(1.0 if live else 0.16)
        self.body.setEnabled(live)
        self.idle.setVisible(not live)
        self.idle_t.setText(t("err_idle_t") if error else t("idle_t"))
        self.idle_s.setText(t("err_idle_s") if error else t("idle_s"))
        self.go_btn.setEnabled(live)
        self.refresh()

    def set_dest(self, use_tk: bool, path: str, sub: str):
        self.sw_tk.switch.set_now(use_tk)
        self.dest_path.set_full(path)
        self.dest_sub.setText(sub)
        self.dest_btn.setVisible(not use_tk)
        self.dest.setEnabled(not use_tk)
        self.saveto.set_full(path)

    def refresh(self):
        """Show the blocks that make sense for the current link and options."""
        o, inf = self.o, self.info
        video = o.what == "video"
        self.m_video.setChecked(video)
        self.m_audio.setChecked(not video)
        self.b_q.setVisible(video)
        self.b_file.setVisible(video)
        self.b_audio.setVisible(not video)
        self.b_part.setVisible(self.kind == "video" and bool(inf and inf.duration))
        self.times.setVisible(o.part is not None)
        self.seg_fmt.set_value(o.fmt, animated=False)
        self.seg_afmt.set_value(o.afmt, animated=False)
        self._fill_quality()
        self._fill_subs()
        self.fmt_note.setText(self._fmt_note())
        self.afmt_note.setText(t("n_" + o.afmt))
        self.sw_thumb.title.setText(t("cover_t") if not video else t("thumb_t"))
        self.sw_thumb.sub.setText(t("cover_s") if not video else t("thumb_s"))
        self.sw_thumb.switch.set_now(o.thumb)
        if o.part is not None:
            self.t_from.setText(tcode(o.part[0]))
            self.t_to.setText(tcode(o.part[1]))
            self.t_len.setText(tcode(o.part[1] - o.part[0]))

    def _heights(self) -> list[int]:
        inf = self.info
        if inf and inf.heights:
            return inf.heights
        return [2160, 1080, 720, 480]

    def _fill_quality(self):
        self.q_flow.clear()
        for c in self.quality_chips.values():
            c.deleteLater()
        self.quality_chips = {}
        hs = self._heights()
        inf = self.info
        opts = [0] + [h for h in hs if h != hs[0]]
        for h in opts:
            text = f"{t('q_best')} · {ytdlp.label(hs[0])}" if h == 0 else ytdlp.label(h)
            sub = ""
            if inf and inf.heights:
                probe = ytdlp.Opts(what="video", q=h, fmt=self.o.fmt, part=self.o.part)
                size = ytdlp.estimate(inf, probe)
                sub = "≈ " + fmt_size(size) if size else ""
            c = Chip(text, sub)
            c.setChecked(h == self.o.q)
            c.clicked.connect(lambda _=False, v=h: self._set_q(v))
            self.q_flow.addWidget(c)
            self.quality_chips[h] = c
        self.q_note.setVisible(bool(inf and inf.vertical))
        self.q_note.setText(t("vert_note"))

    def _fill_subs(self):
        inf = self.info
        langs = []
        if inf and self.kind == "video":
            pref = [l for l in ("ru", "en") if l in inf.subs] + [l for l in inf.subs if l not in ("ru", "en")][:3]
            langs = pref + (["auto"] if inf.auto_subs and not pref else [])
        has = bool(langs) and self.o.what == "video"
        self.sw_subs.setVisible(has)
        self.subs_w.setVisible(has and self.o.subs is not None)
        self.subs_flow.clear()
        for lang in langs:
            c = Chip(t("subs_auto") if lang == "auto" else lang.upper(), small=True)
            c.setChecked(self.o.subs == lang)
            c.clicked.connect(lambda _=False, v=lang: self._pick_sub(v))
            self.subs_flow.addWidget(c)
        self._langs = langs

    def _fmt_note(self) -> str:
        inf, o = self.info, self.o
        hi = bool(inf and inf.site == "YouTube" and (o.q or inf.max_h) > 1080)
        if o.fmt == "orig":
            return t("n_orig")
        if o.fmt == "mp4o":
            return t("n_mp4o_hi") if hi else t("n_mp4o")
        if inf and ytdlp.needs_recode(inf, o):
            return t("n_mp4_hi")
        return t("n_mp4_hi") if hi else t("n_mp4")

    # ------------------------------------------------------------ edits
    def _set_what(self, what: str):
        self.o.what = what
        self.refresh()
        self.changed.emit()

    def _set_q(self, h: int):
        self.o.q = h
        for v, c in self.quality_chips.items():
            c.setChecked(v == h)
        self.fmt_note.setText(self._fmt_note())
        self.changed.emit()

    def _set_fmt(self, fmt: str):
        self.o.fmt = fmt
        self.fmt_note.setText(self._fmt_note())
        self._fill_quality()
        self.changed.emit()

    def _set_afmt(self, a: str):
        self.o.afmt = a
        self.afmt_note.setText(t("n_" + a))
        self.changed.emit()

    def _set_part(self, on: bool):
        dur = self.info.duration if self.info else 0
        self.o.part = (0.0, dur) if on and dur else None
        self.refresh()
        self.changed.emit()

    def _times_edited(self):
        if self.o.part is None or not self.info:
            return
        a, b = parse_t(self.t_from.text()), parse_t(self.t_to.text())
        s, e = self.o.part
        dur = self.info.duration
        if a is not None:
            s = max(0.0, min(a, e - 1))
        if b is not None:
            e = min(dur, max(b, s + 1))
        self.o.part = (s, e)
        self.refresh()
        self.changed.emit()

    def _set_subs(self, on: bool):
        self.o.subs = (self._langs[0] if self._langs else None) if on else None
        self._fill_subs()
        self.changed.emit()

    def _pick_sub(self, lang: str):
        self.o.subs = lang
        self._fill_subs()

    def _set_thumb(self, on: bool):
        self.o.thumb = on

    def _set_tk(self, on: bool):
        self.host.set("use_tk", on)

    # ------------------------------------------------------------ footer
    def set_total(self, html: str, go_text: str, can_go: bool):
        self.total.setText(html)
        self.go_btn.setText(go_text)
        self.go_btn.setEnabled(can_go)

    def ask_dir(self, start: str) -> str:
        return QFileDialog.getExistingDirectory(self, t("b_dest").capitalize(), start)
