"""Photo page: pictures on the left with their real future size, settings on the right, «Сжать» writes them."""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ..core import engine, opts
from ..core.i18n import files, fmt_size, pics, t
from ..kit.common import Loader, SmoothScroll, button, label
from .art import CompareView, Item, PhotoRow
from .panel import OptionsPanel
from .theme import stylesheet
from .widgets import DropOverlay


def _scan(path: str, ffmpeg: str | None):
    """Worker: what the picture is + a small thumbnail (QImage — QPixmap only on the GUI thread)."""
    src = engine.info(path, ffmpeg)
    thumb = None
    if not src.error:
        img = engine.load(path, ffmpeg)
        if not img.isNull():
            thumb = img.scaled(144, 144, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
    return src, thumb


class _Bridge(QObject):
    step = Signal(int, int, str, str)     # done, total, item id, «path|size|desc» or error
    over = Signal(int, int)


class PhotoPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("photoPage")
        self.setAcceptDrops(True)
        self.items: list[Item] = []
        self.rows: dict[int, PhotoRow] = {}
        self._uid = 0
        self._gen = 0
        self._busy = False
        self.loader = Loader(2, self)
        self.loader.done.connect(self._loaded)
        self.bridge = _Bridge(self)
        self.bridge.step.connect(self._saved_one)
        self.bridge.over.connect(self._saved_all)
        self._est_timer = QTimer(self)
        self._est_timer.setSingleShot(True)
        self._est_timer.setInterval(120)
        self._est_timer.timeout.connect(self._estimate_all)
        self._build()
        self.retranslate()
        self.apply_theme()
        if hasattr(host, "settings_changed"):
            host.settings_changed.connect(self._setting)
        if hasattr(host, "folders_changed"):
            host.folders_changed.connect(lambda _k: self.panel.refresh())

    def ffmpeg(self) -> str | None:
        try:
            return self.host.component("ffmpeg")
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
        self.clear_btn = button("", "ghost")
        self.clear_btn.clicked.connect(self.clear)
        self.add_btn = button("", "accent")
        self.add_btn.clicked.connect(self.ask_files)
        head.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(head)
        v.addSpacing(16)
        self.scroll = SmoothScroll()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.list_lay = QVBoxLayout(inner)
        self.list_lay.setContentsMargins(0, 0, 4, 0)
        self.list_lay.setSpacing(4)
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch()
        self.empty_t = label("", "idleTitle")
        self.empty_s = label("", "idleHint", wrap=True)
        for w in (self.empty_t, self.empty_s):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            el.addWidget(w)
        el.addStretch()
        self.empty.setMinimumHeight(300)
        self.list_lay.addWidget(self.empty)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(inner)
        v.addWidget(self.scroll, 1)
        root.addWidget(left, 1)
        self.overlay = DropOverlay(left)
        self.cmp = CompareView(left)
        self.cmp.closed.connect(lambda: self.scroll.setFocus())

        seam = QFrame()
        seam.setObjectName("seam")
        seam.setFixedWidth(1)
        root.addWidget(seam)
        self.panel = OptionsPanel(self.host)
        self.panel.changed.connect(self._opts_changed)
        self.panel.go.connect(self.save)
        root.addWidget(self.panel)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.cmp.isVisible():
            self.cmp.setGeometry(self.left.rect())

    # ======================================================== language / theme / settings
    def retranslate(self):
        self.h_title.setText(t("title"))
        self.add_btn.setText(t("add"))
        self.clear_btn.setText(t("clear_list"))
        self.clear_btn.setToolTip(t("clear_tip"))
        self.empty_t.setText(t("empty_t"))
        self.empty_s.setText(t("empty_s"))
        self.overlay.text = t("drop")
        self.panel.retranslate()
        self._head()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        self.update()

    def _setting(self, key: str):
        if key in ("use_tk",):
            self.panel.refresh()
            self._totals()

    # ======================================================== adding
    def ask_files(self):
        start = self.host.get("last_dir", "") or str(Path.home() / "Pictures")
        flt = "Images (" + " ".join("*" + e for e in opts.IMAGE_EXT) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, t("add"), start, flt)
        if paths:
            self.host.set("last_dir", os.path.dirname(paths[0]))
            self.add_paths(paths)

    def add_paths(self, paths: list):
        found: list[str] = []
        for p in map(str, paths):
            if os.path.isdir(p):
                for root, _d, fs in os.walk(p):
                    found += [os.path.join(root, f) for f in sorted(fs) if opts.is_image(f)]
            elif opts.is_image(p):
                found.append(p)
        if not found:
            self.host.toast(t("not_img"))
            return
        have = {os.path.normcase(os.path.abspath(i.src.path)) for i in self.items}
        new = [p for p in found if os.path.normcase(os.path.abspath(p)) not in have]
        if any(opts.needs_ffmpeg(p) for p in new) and not self.ffmpeg():
            self.host.toast(t("no_ffmpeg"))
        ff = self.ffmpeg()
        for p in new:
            self._uid += 1
            it = Item(self._uid, engine.Source(p, size=_size(p)))
            self.items.append(it)
            row = PhotoRow(it, lambda: self.panel.o)
            row.compare.connect(self.open_compare)
            row.remove.connect(self.remove)
            self.rows[it.id] = row
            self.list_lay.insertWidget(self.list_lay.count() - 1, row)
            self.loader.submit(f"scan:{it.id}", _scan, p, ff)
        skipped = len(found) - len(new)
        if new:
            self.host.toast(t("added_skip", n=pics(len(new)), k=skipped) if skipped else t("added", n=pics(len(new))))
        self._head()

    def files_received(self, paths: list):
        self.add_paths(paths)

    def remove(self, iid: int):
        it = self._item(iid)
        if it is None or it.st == "work":
            return
        self.items.remove(it)
        row = self.rows.pop(iid, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        if self.cmp.item_id == iid:
            self.cmp.close_view()
        self._head()

    def clear(self):
        if self._busy or not self.items:
            return
        for iid in [i.id for i in self.items]:
            self.remove(iid)
        self.host.toast(t("cleared"))

    def _item(self, iid: int) -> Item | None:
        return next((i for i in self.items if i.id == iid), None)

    # ======================================================== results from workers
    def _loaded(self, key: str, value):
        kind, _, rest = key.partition(":")
        if kind == "scan":
            it = self._item(int(rest))
            if it is None or value is None:
                return
            src, thumb = value
            it.src = src
            it.thumb = QPixmap.fromImage(thumb) if thumb is not None else None
            self.panel.alpha = any(i.src.alpha for i in self.items)
            self.panel.refresh()
            self._estimate(it)
            self._row(it)
            self._head()
        elif kind == "est":
            gen, iid = rest.split(":")
            it = self._item(int(iid))
            if it is None or int(gen) != self._gen:
                return                              # settings moved on since this was started
            if isinstance(value, engine.Result):
                it.res, it.res_key = value, self.panel.o.key()
                if self.cmp.item_id == it.id:
                    self._compare_after(it)
            else:                                   # this picture can't be made with these settings
                it.res, it.res_key = None, ()
                it.st, it.err = "err", str(value or "error")
            self._row(it)
            self._totals()
        elif kind == "full":
            if self.cmp.item_id == int(rest):
                self.cmp.set_before(value)
        elif kind == "after":
            iid, _, k = rest.partition(":")
            it = self._item(int(iid))
            if it is not None and self.cmp.item_id == it.id and it.res is not None and str(hash(it.res_key)) == k:
                self.cmp.set_after(value, self._after_txt(it))

    def _row(self, it: Item):
        r = self.rows.get(it.id)
        if r is not None:
            r.update()

    # ======================================================== estimates
    def _opts_changed(self):
        self._gen += 1
        for it in self.items:
            if it.st in ("done", "err"):
                it.st, it.err = "wait", ""            # new settings → it can be made again
            it.res, it.res_key = None, ()
            self._row(it)
        self._totals()
        self._est_timer.start()

    def _estimate_all(self):
        for it in self.items:
            self._estimate(it)

    def _estimate(self, it: Item):
        if it.src.error or not it.src.w or it.st == "done":
            return
        o = opts.Opts(**self.panel.o.to_dict())
        self.loader.submit(f"est:{self._gen}:{it.id}", _encode, it.src, o, self.ffmpeg())

    def _totals(self):
        ok = [i for i in self.items if not i.src.error]
        before = sum(i.src.size for i in ok)
        key = self.panel.o.key()
        after = 0
        ready = True
        for i in ok:
            if i.st == "done":
                after += i.done_size
            elif i.res is not None and i.res_key == key:
                after += len(i.res.data)
            else:
                ready = False
        todo = sum(1 for i in ok if i.st in ("wait", "err"))
        self.panel.set_totals(before, after if ok else None, todo, ready)

    def _head(self):
        n = len(self.items)
        total = sum(i.src.size for i in self.items)
        self.h_sub.setText(t("files_sum", f=files(n), s=fmt_size(total)) if n else t("no_files"))
        self.empty.setVisible(not n)
        self.clear_btn.setVisible(bool(n))
        self._totals()

    # ======================================================== compare
    def open_compare(self, iid: int):
        it = self._item(iid)
        if it is None:
            return
        s = it.src
        left = f"{opts.src_fmt(s.path).upper()} · {fmt_size(s.size)} · {s.w}×{s.h}"
        self.cmp.open(iid, os.path.basename(s.path), None, left)
        self.loader.submit(f"full:{iid}", engine.load, s.path, self.ffmpeg())
        if it.res is not None and it.res_key == self.panel.o.key():
            self._compare_after(it)
        else:
            self._estimate(it)

    def _compare_after(self, it: Item):
        self.cmp.set_after(None, "…")
        self.loader.submit(f"after:{it.id}:{hash(it.res_key)}", engine.decode, it.res, self.ffmpeg())

    def _after_txt(self, it: Item) -> str:
        r = it.res
        q = "" if r.fmt == "png" else f" {self.panel.o.q}"
        return f"{r.fmt.upper()}{q} · {fmt_size(len(r.data))} · {r.w}×{r.h}"

    def keyPressEvent(self, e):
        if self.cmp.isVisible():
            self.cmp.keyPressEvent(e)
        else:
            super().keyPressEvent(e)

    # ======================================================== saving
    def out_dir(self, it: Item) -> str:
        if self.panel.use_tk():
            return self.host.folder("output")
        return os.path.dirname(it.src.path)

    def save(self):
        todo = [i for i in self.items if i.st in ("wait", "err") and not i.src.error and i.src.w]
        if not todo or self._busy:
            return
        o = opts.Opts(**self.panel.o.to_dict())
        sfx = self.panel.suffix()
        ff = self.ffmpeg()
        key = o.key()
        jobs = []
        for it in todo:
            res = it.res if it.res_key == key else None
            jobs.append((it.id, it.src, res, self.out_dir(it)))
            it.st, it.progress, it.err = "work", 0.0, ""
            self._row(it)
        self._busy = True
        self.panel.set_busy(True, 0.0, t("saving", i=1, n=len(jobs)))

        def run():
            ok = bad = 0
            taken: set[str] = set()
            for k, (iid, src, res, folder) in enumerate(jobs):
                try:
                    r = res or engine.encode(src, o, ff)
                    os.makedirs(folder, exist_ok=True)
                    dest = opts.free_name(os.path.join(folder, opts.out_name(src.path, r.fmt, sfx)), taken)
                    tmp = dest + ".wxwx-tmp"
                    with open(tmp, "wb") as f:
                        f.write(r.data)
                    os.replace(tmp, dest)
                    ok += 1
                    self.bridge.step.emit(k + 1, len(jobs), str(iid), f"ok|{dest}|{len(r.data)}|{r.w}×{r.h} {r.fmt.upper()}")
                except Exception as ex:
                    bad += 1
                    self.bridge.step.emit(k + 1, len(jobs), str(iid), "err|" + (str(ex) or "error"))
            self.bridge.over.emit(ok, bad)
        threading.Thread(target=run, daemon=True).start()

    def _saved_one(self, done: int, total: int, iid: str, msg: str):
        self.panel.set_busy(True, done / total, t("saving", i=min(done + 1, total), n=total))
        it = self._item(int(iid))
        if it is None:
            return
        kind, _, rest = msg.partition("|")
        if kind == "ok":
            path, size, desc = rest.split("|", 2)
            it.st, it.out, it.done_size, it.done_desc, it.progress = "done", path, int(size), desc, 1.0
        else:
            it.st, it.err = "err", rest.splitlines()[-1][:160] if rest else "error"
        self._row(it)
        self._totals()

    def _saved_all(self, ok: int, bad: int):
        self._busy = False
        self.panel.set_busy(False)
        self._totals()
        self.host.toast(t("done_err", n=files(ok), k=bad) if bad else t("done", n=files(ok)))

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
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    # ======================================================== toolkit hooks
    def is_busy(self) -> bool:
        return self._busy

    def shutdown(self):
        self.loader.shutdown()


def _encode(src, o, ffmpeg):
    try:
        return engine.encode(src, o, ffmpeg)
    except Exception as e:
        return str(e)


def _size(p: str) -> int:
    try:
        return os.path.getsize(p)
    except OSError:
        return 0
