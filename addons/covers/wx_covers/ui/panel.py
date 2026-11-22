"""The right panel of Covers: cover, non-square choice, size, tags, files — and the «Сохранить» footer."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from ..core import audio, model
from ..core.i18n import files, fmt_size, t, tracks
from ..core.model import Item
from ..kit.common import SmoothScroll, button, label
from .art import BigCover
from .widgets import Chip, IconBadge, ProgressButton, SectionHeader, Segmented, SwitchRow


class CoverPanel(QWidget):
    changed = Signal()              # something about the picked tracks changed → rows repaint
    go = Signal()
    undo = Signal()
    pick_image = Signal()
    image_dropped = Signal(str)

    def __init__(self, host, pixmaps, parent=None):
        super().__init__(parent)
        self.host = host
        self.pixmaps = pixmaps
        self.setObjectName("panelRight")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self.items: list[Item] = []          # picked
        self.all: list[Item] = []
        self._busy = False
        self._build()
        self.retranslate()
        self.set_items([], [])

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

        # cover
        self.b_cover, self.h_cover, lay = self._block("cover")
        row = QHBoxLayout()
        row.setSpacing(14)
        self.big = BigCover(self.pixmaps)
        self.big.clicked.connect(self.pick_image)
        self.big.setAcceptDrops(True)
        self.big.dragEnterEvent = self._big_drag
        self.big.dragMoveEvent = self._big_drag
        self.big.dragLeaveEvent = self._big_leave
        self.big.dropEvent = self._big_drop
        row.addWidget(self.big)
        col = QVBoxLayout()
        col.setSpacing(8)
        self.pick_btn = button("", "destBtn")
        self.pick_btn.clicked.connect(self.pick_image)
        col.addWidget(self.pick_btn)
        self.cv_hint = label("", "cvHint", wrap=True)
        self.cv_hint.setProperty("hint", True)
        col.addWidget(self.cv_hint)
        col.addStretch()
        self.rm_btn = QPushButton()
        self.rm_btn.setObjectName("danger")
        self.rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rm_btn.clicked.connect(self._remove)
        col.addWidget(self.rm_btn)
        row.addLayout(col, 1)
        lay.addLayout(row)

        # not square
        self.b_wide, self.h_wide, lay = self._block("crop")
        self.seg_fit = Segmented([("crop", "", "x"), ("fit", "", "x")])
        self.seg_fit.changed.connect(self._set_fit)
        lay.addWidget(self.seg_fit)
        self.pads = QWidget()
        pl = QHBoxLayout(self.pads)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(8)
        self.pad_chips: dict[str, Chip] = {}
        for k in audio.PADS:
            c = Chip("", small=True)
            c.clicked.connect(lambda _=False, key=k: self._set_pad(key))
            pl.addWidget(c)
            self.pad_chips[k] = c
        pl.addStretch()
        lay.addWidget(self.pads)
        self.wide_note = label("", "note", wrap=True)
        lay.addWidget(self.wide_note)

        # size
        self.b_size, self.h_size, lay = self._block("size")
        self.seg_size = Segmented([(s, "", "x") for s in audio.SIZES])
        self.seg_size.changed.connect(lambda v: self.host.set("size", v))
        lay.addWidget(self.seg_size)
        self.size_note = label("", "note", wrap=True)
        lay.addWidget(self.size_note)

        # tags
        self.b_tags, self.h_tags, lay = self._block("tag")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.edits: dict[str, QLineEdit] = {}
        self.edit_lbls: dict[str, QWidget] = {}
        for i, k in enumerate(audio.TAGS):
            box = QVBoxLayout()
            box.setSpacing(4)
            lb = label("", "fldLbl")
            self.edit_lbls[k] = lb
            box.addWidget(lb)
            e = QLineEdit()
            e.setObjectName("tagEdit")
            e.textEdited.connect(lambda v, key=k: self._tag_edited(key, v))
            if k == "year":
                e.setMaxLength(10)
            box.addWidget(e)
            self.edits[k] = e
            span = 2 if k == "title" else 1
            r, c = {"title": (0, 0), "artist": (1, 0), "album": (1, 1), "year": (2, 0)}[k]
            grid.addLayout(box, r, c, 1, span)
        lay.addLayout(grid)
        self.guess_btn = button("", "destBtn")
        self.guess_btn.clicked.connect(self._guess)
        lay.addWidget(self.guess_btn)
        self.guess_note = label("", "note", wrap=True)
        lay.addWidget(self.guess_note)

        # files
        self.b_files, self.h_files, lay = self._block("file")
        self.sw_rename = SwitchRow()
        self.sw_rename.toggled.connect(lambda on: self._switch("rename", on))
        lay.addWidget(self.sw_rename)
        self.fn_prev = label("", "fnPrev", wrap=True)
        self.fn_prev.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.fn_prev)
        self.sw_copies = SwitchRow()
        self.sw_copies.toggled.connect(lambda on: self._switch("copies", on))
        lay.addWidget(self.sw_copies)
        self.form.addStretch(1)

        # idle overlay
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
        self.undo_btn = QPushButton()
        self.undo_btn.setObjectName("undo")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(self.undo)
        tot.addWidget(self.undo_btn)
        tot.addSpacing(10)
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
        self.saveto_icon = IconBadge("file", 16, 15, plain=True, tint=True)
        st.addWidget(self.saveto_icon)
        self.saveto = label("", "saveTo", wrap=True)
        self.saveto.setTextFormat(Qt.TextFormat.RichText)
        st.addWidget(self.saveto, 1)
        fv.addLayout(st)
        outer.addWidget(footer)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.idle.setGeometry(0, 0, self.width(), self.scroll.height())

    # ------------------------------------------------------------ drop a picture on the preview
    def _big_drag(self, e):
        if any(audio.is_image(u.toLocalFile()) for u in e.mimeData().urls()) or e.mimeData().hasImage():
            e.acceptProposedAction()
            self.big.over = True
            self.big.update()

    def _big_leave(self, _e):
        self.big.over = False
        self.big.update()

    def _big_drop(self, e):
        self.big.over = False
        self.big.update()
        for u in e.mimeData().urls():
            if audio.is_image(u.toLocalFile()):
                e.acceptProposedAction()
                self.image_dropped.emit(u.toLocalFile())
                return

    # ------------------------------------------------------------ texts
    def retranslate(self):
        self.h_cover.title.setText(t("b_cover"))
        self.pick_btn.setText(t("pick_img"))
        self.cv_hint.setText(t("cv_hint"))
        self.rm_btn.setText(t("rm_cover"))
        self.h_wide.title.setText(t("b_wide"))
        self.seg_fit.set_options([(f, t("fit_" + f), t(f"fit_{f}_s")) for f in audio.FITS])
        for k, c in self.pad_chips.items():
            c.setText(t("pad_" + k))
        self.wide_note.setText(t("wide_note"))
        self.h_size.title.setText(t("b_size"))
        self.seg_size.set_options([(s, t("sz_" + s), t(f"sz_{s}_s")) for s in audio.SIZES])
        self.size_note.setText(t("size_note"))
        self.h_tags.title.setText(t("b_tags"))
        for k, lb in self.edit_lbls.items():
            lb.setText(t("tg_" + k).upper())
        self.guess_btn.setText("✦  " + t("guess"))
        self.guess_note.setText(t("guess_note"))
        self.h_files.title.setText(t("b_files"))
        self.sw_rename.title.setText(t("rename_t"))
        self.sw_rename.sub.setText(t("rename_s"))
        self.sw_copies.title.setText(t("copies_t"))
        self.sw_copies.sub.setText(t("copies_s"))
        self.idle_t.setText(t("idle_t"))
        self.idle_s.setText(t("idle_s"))
        self.undo_btn.setText("↶ " + t("undo"))
        self.refresh()

    # ------------------------------------------------------------ state
    def opt(self, key, default):
        v = self.host.get(key, default)
        return default if v is None else v

    def set_items(self, picked: list[Item], all_items: list[Item]):
        self.items, self.all = picked, all_items
        self.refresh()

    def refresh(self):
        s = self.items
        on = bool(s)
        self.fade.setOpacity(1.0 if on else 0.28)
        self.body.setEnabled(on)
        self.idle.setVisible(not on)
        self.big.set_items(s)
        self.rm_btn.setVisible(any(i.has_cover for i in s))
        wide = [i for i in s if i.wide]
        self.b_wide.setVisible(bool(wide))
        if wide:
            fit = model.same(wide, lambda i: i.fit)
            self.seg_fit.set_value(fit or "crop", animated=False)
            pad = model.same(wide, lambda i: i.pad)
            self.pads.setVisible(fit == "fit")
            for k, c in self.pad_chips.items():
                c.blockSignals(True)
                c.setChecked(k == pad)
                c.blockSignals(False)
        self.seg_size.set_value(str(self.opt("size", "1000")), animated=False)
        many = len(s) > 1
        for k, e in self.edits.items():
            v = model.same(s, lambda i, key=k: i.tags.get(key) or "") if s else ""
            each = k == "title" and many
            e.setEnabled(not each)
            if not e.hasFocus():
                e.setText("" if each or v is None else v)
            e.setPlaceholderText(t("ph_each") if each else (t("ph_mixed") if v is None else t("ph_" + k)))
        g = model.can_guess(s)
        self.guess_btn.setVisible(g)
        self.guess_note.setVisible(g)
        rename = bool(self.opt("rename", False))
        for sw, key in ((self.sw_rename, "rename"), (self.sw_copies, "copies")):
            sw.switch.blockSignals(True)
            sw.switch.set_now(bool(self.opt(key, False)))
            sw.switch.blockSignals(False)
        self.fn_prev.setVisible(rename and on)
        if rename and s:
            rows = []
            for it in s[:3]:
                n = it.planned_name()
                old = html.escape(it.track.name)
                rows.append(f'{old} <i style="color:#5b5a63">— {t("fn_keep")}</i>' if n == it.track.name
                            else f'{old} → <b style="color:#ecebef">{html.escape(n)}</b>')
            if len(s) > 3:
                rows.append(f'<i>{t("fn_more", n=len(s) - 3)}</i>')
            self.fn_prev.setText("<br>".join(rows))
        self.totals()

    def totals(self):
        d = [i for i in self.all if i.dirty]
        self.undo_btn.setVisible(bool(d) and not self._busy)
        if self._busy:
            return
        self.l_total.setText(t("changed") if d else t("total"))
        if d:
            add = model.added_kb(self.all, str(self.opt("size", "1000")))
            extra = f'&nbsp;&nbsp;<span style="color:#b8a8e2;font-size:8.6pt">+{fmt_size(add * 1024)}</span>' if add else ""
            self.total.setText(tracks(len(d)) + extra)
            self.go_btn.setText(t("save_n", n=files(len(d))))
        else:
            self.total.setText("—")
            self.go_btn.setText(t("save"))
        self.go_btn.setEnabled(bool(d))
        if self.opt("copies", False):
            folder = self.host.folder("output") if hasattr(self.host, "folder") else ""
            self.saveto_icon.icon = "folder"
            self.saveto.setText(f'{t("saveto_copies")} <b>{html.escape(folder)}</b>')
        else:
            self.saveto_icon.icon = "file"
            self.saveto.setText(t("saveto_inplace"))
        self.saveto_icon.update()

    def set_busy(self, on: bool, frac: float = 0.0, text: str = ""):
        self._busy = on
        self.go_btn.set_progress(frac if on else 0.0)
        if on:
            self.go_btn.setText(text)
        self.go_btn.setEnabled(not on and any(i.dirty for i in self.all))
        self.body.setEnabled(not on and bool(self.items))
        self.undo_btn.setVisible(not on and any(i.dirty for i in self.all))
        if not on:
            self.totals()

    # ------------------------------------------------------------ edits
    def _tag_edited(self, key: str, value: str):
        model.set_tag(self.items, key, value)
        self.changed.emit()
        if key in ("artist", "title"):
            self.refresh()
        else:
            self.totals()

    def _set_fit(self, v: str):
        for i in self.items:
            if i.wide:
                i.fit, i.saved = v, False
        self.changed.emit()
        self.refresh()

    def _set_pad(self, v: str):
        for i in self.items:
            if i.wide:
                i.pad, i.saved = v, False
        self.changed.emit()
        self.refresh()

    def _remove(self):
        model.remove_cover(self.items)
        self.changed.emit()
        self.refresh()

    def _guess(self):
        n = model.guess_tags(self.items)
        self.host.toast(t("guessed", n=tracks(n)) if n else t("guess_none"))
        self.changed.emit()
        self.refresh()

    def _switch(self, key: str, on: bool):
        self.host.set(key, on)
        self.refresh()

