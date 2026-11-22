"""Covers page: tracks on the left (pick one or many), what to change on the right, «Сохранить» writes the files."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ..core import audio, model
from ..core.i18n import files, t, tracks, tracks_of
from ..core.model import Item
from ..kit.common import Loader, SmoothScroll, button, label
from .art import CheckAll, TrackRow
from .panel import CoverPanel
from .theme import stylesheet
from .widgets import Chip, DropOverlay


class _Bridge(QObject):
    step = Signal(int, int, str, str)       # done, total, item id, error ("" = ok)
    over = Signal(int, int)                 # saved, failed


class CoversPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("coversPage")
        self.setAcceptDrops(True)
        self.items: list[Item] = []
        self.rows: dict[int, TrackRow] = {}
        self._uid = 0
        self._last: int | None = None
        self._only_no = False
        self._pm: dict[str, QPixmap] = {}
        self._busy = False
        self.work = Path(host.data_dir) / "work"
        self.loader = Loader(3, self)
        self.loader.done.connect(self._loaded)
        self.bridge = _Bridge(self)
        self.bridge.step.connect(self._saved_one)
        self.bridge.over.connect(self._saved_all)
        self._build()
        self.retranslate()
        self.apply_theme()
        sc = QShortcut(QKeySequence(QKeySequence.StandardKey.Paste), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.paste)
        sa = QShortcut(QKeySequence(QKeySequence.StandardKey.SelectAll), self)
        sa.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sa.activated.connect(self._select_all_key)
        if hasattr(host, "settings_changed"):
            host.settings_changed.connect(lambda _k: self.panel.refresh())
        if hasattr(host, "folders_changed"):
            host.folders_changed.connect(lambda _k: self.panel.totals())

    # ======================================================== tools
    def comp(self, exe: str) -> str | None:
        try:
            return self.host.component("ffmpeg", exe) if exe != "ffmpeg" else self.host.component("ffmpeg")
        except Exception:
            return None

    # ======================================================== build
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        left = QWidget()
        self.left = left
        v = QVBoxLayout(left)
        v.setContentsMargins(22, 20, 22, 14)
        v.setSpacing(0)
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        self.h_title = label("", "h2")
        self.h_sub = label("", "muted")
        tv.addWidget(self.h_title)
        tv.addWidget(self.h_sub)
        head.addLayout(tv, 1)
        self.add_btn = button("", "accent")
        self.add_btn.clicked.connect(self.ask_files)
        self.clear_btn = button("", "ghost")
        self.clear_btn.clicked.connect(self.clear)
        head.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(head)
        v.addSpacing(16)

        lh = QHBoxLayout()
        lh.setContentsMargins(11, 0, 4, 0)
        lh.setSpacing(10)
        self.ck_all = CheckAll()
        self.ck_all.clicked.connect(self._toggle_all)
        lh.addWidget(self.ck_all)
        self.list_lbl = label("", "listHead")
        self.list_lbl.setTextFormat(Qt.TextFormat.RichText)
        lh.addWidget(self.list_lbl, 1)
        self.only_no = Chip("", small=True)
        self.only_no.toggled.connect(self._only_no_toggled)
        lh.addWidget(self.only_no)
        self.list_head = QWidget()
        self.list_head.setLayout(lh)
        v.addWidget(self.list_head)
        v.addSpacing(6)

        self.scroll = SmoothScroll()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.list_lay = QVBoxLayout(inner)
        self.list_lay.setContentsMargins(0, 0, 4, 0)
        self.list_lay.setSpacing(2)
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch()
        self.empty_t = label("", "idleTitle")
        self.empty_s = label("", "idleHint", wrap=True)
        for w in (self.empty_t, self.empty_s):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            el.addWidget(w)
        el.addStretch()
        self.empty.setMinimumHeight(260)
        self.list_lay.addWidget(self.empty)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(inner)
        v.addWidget(self.scroll, 1)
        root.addWidget(left, 1)
        self.overlay = DropOverlay(left)

        seam = QFrame()
        seam.setObjectName("seam")
        seam.setFixedWidth(1)
        root.addWidget(seam)
        self.panel = CoverPanel(self.host, self.look)
        self.panel.changed.connect(self._repaint_rows)
        self.panel.go.connect(self.save)
        self.panel.undo.connect(self.undo)
        self.panel.pick_image.connect(self.ask_image)
        self.panel.image_dropped.connect(lambda p: self.set_image(p))
        root.addWidget(self.panel)

    # ======================================================== language / theme
    def retranslate(self):
        self.h_title.setText(t("title"))
        self.h_sub.setText(t("sub"))
        self.add_btn.setText(t("add"))
        self.clear_btn.setText(t("clear_list"))
        self.clear_btn.setToolTip(t("clear_tip"))
        self.only_no.setText(t("only_no"))
        self.empty_t.setText(t("empty_t"))
        self.empty_s.setText(t("empty_s"))
        self.panel.retranslate()
        self._head()
        self._repaint_rows()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        self.panel.recolor()
        self.update()

    # ======================================================== pictures for rows / preview
    def _pixmap(self, path: str) -> QPixmap | None:
        if not path:
            return None
        pm = self._pm.get(path)
        if pm is None:
            img = QImage(path)
            if img.isNull():
                return None
            if max(img.width(), img.height()) > 640:     # a 4000 px photo doesn't need to live in memory whole
                img = img.scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pm = QPixmap.fromImage(img)
            self._pm[path] = pm
        return pm

    def look(self, it: Item):
        """(pixmap, fit, pad) of how the cover will be after saving."""
        if it.new_cover:
            return self._pixmap(it.cover), it.fit, it.pad
        if it.cover == audio.KEEP and it.thumb:
            return self._pixmap(it.thumb), "crop", "blur"
        return None, "crop", "blur"

    # ======================================================== adding tracks
    def ask_files(self):
        start = self.host.get("last_dir", "") or str(Path.home() / "Music")
        paths, _ = QFileDialog.getOpenFileNames(self, t("add"), start, "Audio (*.mp3 *.m4a *.flac)")
        if paths:
            self.host.set("last_dir", os.path.dirname(paths[0]))
            self.add_paths(paths)

    def add_paths(self, paths: list, source: str = ""):
        found: list[str] = []
        for p in paths:
            p = str(p)
            if os.path.isdir(p):
                for root, _d, fs in os.walk(p):
                    found += [os.path.join(root, f) for f in sorted(fs) if audio.is_audio(f)]
            elif audio.is_audio(p):
                found.append(p)
        if not found:
            self.host.toast(t("not_audio"))
            return
        have = {os.path.normcase(os.path.abspath(i.path)) for i in self.items}
        new = [p for p in found if os.path.normcase(os.path.abspath(p)) not in have]
        ffprobe, ffmpeg = self.comp("ffprobe"), self.comp("ffmpeg")
        for p in new:
            self._uid += 1
            it = Item(audio.Track(path=p, fmt=os.path.splitext(p)[1][1:].lower(), size=_size(p)), id=self._uid,
                      source=source)
            self.items.append(it)
            self._add_row(it)
            if ffprobe:
                self.loader.submit(f"read:{it.id}", _read, p, ffprobe, ffmpeg, str(Path(self.host.data_dir) / "thumbs"))
        skipped = len(found) - len(new)
        if new:
            self.host.toast(t("added_skip", n=tracks(len(new)), k=skipped) if skipped else t("added", n=tracks(len(new))))
        elif skipped:
            self.host.toast(t("added_skip", n=tracks(0), k=skipped))
        if source and new:                       # sent from Saves: pick them, ready for a cover
            for i in self.items:
                i.sel = i.path in new
            self._selection_changed()
        else:
            self._head()

    def files_received(self, paths: list):
        self.add_paths(paths, source=t("src_saves"))

    def _loaded(self, key: str, value):
        if not key.startswith("read:"):
            return
        iid = int(key[5:])
        it = next((i for i in self.items if i.id == iid), None)
        if it is None or value is None:
            return
        track, thumb = value
        untouched = not it.dirty
        it.track = track
        it.thumb = thumb or ""
        if untouched:
            it.tags = track.tags()
        row = self.rows.get(iid)
        if row:
            row.update()
        if it.sel:
            self.panel.refresh()
        self._head()

    def _add_row(self, it: Item):
        row = TrackRow(it, self.look)
        row.clicked.connect(self._row_clicked)
        row.box_clicked.connect(self._box_clicked)
        self.rows[it.id] = row
        self.list_lay.insertWidget(self.list_lay.count() - 1, row)
        row.setVisible(self._visible(it))

    def clear(self):
        if self._busy or not self.items:
            return
        n = len(self.items)
        for row in self.rows.values():
            row.setParent(None)
            row.deleteLater()
        self.rows.clear()
        self.items.clear()
        self._selection_changed()
        self.host.toast(t("cleared", n=tracks(n)))

    # ======================================================== selection
    def picked(self) -> list[Item]:
        return [i for i in self.items if i.sel]

    def _row_clicked(self, iid: int, mods):
        it = next(i for i in self.items if i.id == iid)
        if mods & Qt.KeyboardModifier.ControlModifier:
            it.sel = not it.sel
        elif mods & Qt.KeyboardModifier.ShiftModifier and self._last is not None:
            ids = [i.id for i in self.items if self._visible(i)]
            if self._last in ids and iid in ids:
                a, b = sorted((ids.index(self._last), ids.index(iid)))
                for i in self.items:
                    if i.id in ids[a:b + 1]:
                        i.sel = True
        else:
            only = it.sel and len(self.picked()) == 1
            for i in self.items:
                i.sel = False
            it.sel = not only
        self._last = iid
        self._selection_changed()

    def _box_clicked(self, iid: int):
        it = next(i for i in self.items if i.id == iid)
        it.sel = not it.sel
        self._last = iid
        self._selection_changed()

    def _toggle_all(self):
        vis = [i for i in self.items if self._visible(i)]
        on = not all(i.sel for i in vis) if vis else False
        for i in vis:
            i.sel = on
        self._selection_changed()

    def _select_all_key(self):
        if not self.focusWidget() or self.focusWidget().metaObject().className() != "QLineEdit":
            for i in self.items:
                i.sel = self._visible(i)
            self._selection_changed()

    def _only_no_toggled(self, on: bool):
        self._only_no = on
        for it in self.items:
            self.rows[it.id].setVisible(self._visible(it))
        self._head()

    def _visible(self, it: Item) -> bool:
        return not self._only_no or not it.has_cover or it.sel

    def _selection_changed(self):
        self.panel.set_items(self.picked(), self.items)
        self._repaint_rows()
        self._head()

    def _repaint_rows(self):
        for r in self.rows.values():
            r.update()
        self.panel.totals()
        self._head()

    def _head(self):
        n, m = len(self.picked()), len(self.items)
        no = sum(1 for i in self.items if not i.has_cover)
        self.empty.setVisible(not self.items)
        self.list_head.setVisible(bool(self.items))
        self.clear_btn.setVisible(bool(self.items))
        self.ck_all.set_state(0 if not n else (1 if n == m else 2))
        if n:
            self.list_lbl.setText(t("picked", n=n, m=m))
        else:
            extra = f' · <span style="color:#b8a8e2">{t("no_cover_n", n=no)}</span>' if no else ""
            self.list_lbl.setText(tracks(m) + extra)
        self.only_no.setVisible(bool(no) or self._only_no)

    # ======================================================== pictures
    def ask_image(self):
        if not self.picked():
            self.host.toast(t("pick_first"))
            return
        start = self.host.get("img_dir", "") or str(Path.home() / "Pictures")
        path, _ = QFileDialog.getOpenFileName(self, t("pick_img"), start,
                                              "Images (" + " ".join("*" + e for e in audio.IMAGE_EXT) + ")")
        if path:
            self.host.set("img_dir", os.path.dirname(path))
            self.set_image(path)

    def set_image(self, path: str, targets: list[Item] | None = None, quiet: bool = False) -> bool:
        targets = targets if targets is not None else self.picked()
        if not targets:
            self.host.toast(t("pick_first"))
            return False
        img = QImage(path)
        if img.isNull():
            self.host.toast(t("bad_image"))
            return False
        model.set_cover(targets, path, (img.width(), img.height()))
        self.panel.refresh()
        self._repaint_rows()
        if not quiet:
            self.host.toast(t("cover_for", n=tracks_of(len(targets))))
        return True

    def paste(self):
        if self.focusWidget() is not None and self.focusWidget().metaObject().className() == "QLineEdit":
            self.focusWidget().paste()
            return
        md = QGuiApplication.clipboard().mimeData()
        paths = [u.toLocalFile() for u in md.urls()] if md.hasUrls() else []
        if any(audio.is_audio(p) for p in paths):
            self.add_paths(paths)
            return
        img_path = next((p for p in paths if audio.is_image(p)), "")
        if not img_path and md.hasImage():
            img = QGuiApplication.clipboard().image()
            if not img.isNull():
                data = img.bits().tobytes() if hasattr(img.bits(), "tobytes") else bytes(img.constBits())
                h = hashlib.sha1(data[:200000]).hexdigest()[:12]
                img_path = str(Path(self.host.data_dir) / "pasted" / f"paste-{h}.png")
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                img.save(img_path)
        if not img_path:
            return
        if not self.picked():
            self.host.toast(t("paste_pick"))
            return
        if self.set_image(img_path, quiet=True):
            self.host.toast(t("pasted"))

    # ======================================================== drag & drop
    def _urls(self, e) -> list[str]:
        return [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]

    def _row_at(self, e) -> TrackRow | None:
        w = self.childAt(e.position().toPoint())
        while w is not None and not isinstance(w, TrackRow):
            w = w.parentWidget()
        return w

    def dragEnterEvent(self, e):
        paths = self._urls(e)
        if any(audio.is_audio(p) or os.path.isdir(p) for p in paths):
            e.acceptProposedAction()
            self.overlay.text = t("drop")
            self.overlay.show_overlay(True)
        elif any(audio.is_image(p) for p in paths):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        paths = self._urls(e)
        if any(audio.is_image(p) for p in paths) and not any(audio.is_audio(p) for p in paths):
            row = self._row_at(e)
            for r in self.rows.values():
                if r.drop != (r is row):
                    r.drop = r is row
                    r.update()
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.overlay.show_overlay(False)
        for r in self.rows.values():
            if r.drop:
                r.drop = False
                r.update()

    def dropEvent(self, e):
        paths = self._urls(e)
        row = self._row_at(e)
        self.dragLeaveEvent(e)
        if any(audio.is_audio(p) or os.path.isdir(p) for p in paths):
            self.add_paths(paths)
            return
        img = next((p for p in paths if audio.is_image(p)), "")
        if not img:
            return
        if row is not None:
            if not row.item.sel:
                for i in self.items:
                    i.sel = i is row.item
                self._selection_changed()
        self.set_image(img)

    # ======================================================== save / undo
    def undo(self):
        d = [i for i in self.items if i.dirty]
        for i in d:
            i.reset()
        self.panel.refresh()
        self._repaint_rows()
        if d:
            self.host.toast(t("undone", n=tracks(len(d))))

    def save(self):
        d = [i for i in self.items if i.dirty and not i.track.error]
        if not d or self._busy:
            return
        ffmpeg, ffprobe = self.comp("ffmpeg"), self.comp("ffprobe")
        if not ffmpeg or not ffprobe:
            self.host.toast(t("no_ffmpeg"))
            return
        size = str(self.host.get("size", "1000") or "1000")
        rename = bool(self.host.get("rename", False))
        copies = self.host.folder("output") if self.host.get("copies", False) and hasattr(self.host, "folder") else ""
        jobs = [(i.id, i.change(), dict(i.tags)) for i in d]
        self._busy = True
        self._copies = bool(copies)
        self.panel.set_busy(True, 0.0, t("saving", i=1, n=len(jobs)))
        work = str(self.work)

        def run():
            os.makedirs(work, exist_ok=True)
            tmp = tempfile.mkdtemp(dir=work)
            cache: dict = {}
            ok = bad = 0
            try:
                for k, (iid, ch, full) in enumerate(jobs):
                    try:
                        new = audio.save(ch, ffmpeg, ffprobe, tmp, size, rename, copies, full, cache)
                        ok += 1
                        self.bridge.step.emit(k + 1, len(jobs), str(iid) + "\n" + new, "")
                    except Exception as ex:          # one bad file doesn't stop the rest
                        bad += 1
                        self.bridge.step.emit(k + 1, len(jobs), str(iid), str(ex) or "error")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
                self.bridge.over.emit(ok, bad)
        threading.Thread(target=run, daemon=True).start()

    def _saved_one(self, done: int, total: int, ref: str, err: str):
        iid_s, _, new = ref.partition("\n")
        it = next((i for i in self.items if i.id == int(iid_s)), None)
        self.panel.set_busy(True, done / total, t("saving", i=min(done + 1, total), n=total))
        if it is None:
            return
        if err:
            it.err = err.splitlines()[-1][:200]
        else:
            it.err = ""
            if not self._copies:         # the list follows the file; copies leave the original as it was
                ffprobe, ffmpeg = self.comp("ffprobe"), self.comp("ffmpeg")
                track, thumb = _read(new, ffprobe, ffmpeg, str(Path(self.host.data_dir) / "thumbs"))
                it.track, it.thumb = track, thumb or ""
            it.reset()
            it.saved = True
        row = self.rows.get(it.id)
        if row:
            row.update()

    def _saved_all(self, ok: int, bad: int):
        self._busy = False
        self.panel.set_busy(False)
        self.panel.refresh()
        self._repaint_rows()
        if bad:
            self.host.toast(t("done_err", n=tracks(ok), k=bad))
        else:
            self.host.toast(t("done_copies" if self._copies else "done", n=files(ok)))

    # ======================================================== toolkit hooks
    def is_busy(self) -> bool:
        return self._busy

    def shutdown(self):
        self.loader.shutdown()


def _size(p: str) -> int:
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def _read(path: str, ffprobe: str, ffmpeg: str | None, thumbs: str):
    """Worker: tags + a small copy of the embedded picture for the list."""
    track = audio.read(path, ffprobe)
    thumb = ""
    if track.cover and ffmpeg:
        try:
            st = os.stat(path)
            key = hashlib.sha1(f"{os.path.abspath(path)}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:16]
            dest = os.path.join(thumbs, key + ".jpg")
            os.makedirs(thumbs, exist_ok=True)
            if os.path.isfile(dest) or audio.extract_cover(path, ffmpeg, dest):
                thumb = dest
        except OSError:
            pass
    return track, thumb

