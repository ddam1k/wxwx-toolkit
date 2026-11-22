"""The Saves tab in toolkit Settings: engine, login, defaults, file name, conveniences, history."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from ..core import proxy, ytdlp
from ..core.history import History
from ..core.i18n import t
from ..core.runner import run_text
from ..kit.common import button, label
from .theme import stylesheet
from .widgets import Segmented, SwitchRow


class _Bridge(QObject):
    done = Signal(str, str)          # what, result


class SettingsTab(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("savesSettings")
        self.bridge = _Bridge(self)
        self.bridge.done.connect(self._bg_done)
        self.versions = {"yt-dlp": None, "deno": None}
        self.px = ""                  # "" | checking | ok/port/proto/site/bad/nocurl/off/saved
        self.px_addr = ""
        self.updating = False
        self.col = QVBoxLayout(self)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(0)
        self.setStyleSheet(stylesheet())
        self.render()
        self._read_versions()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        self.update()

    # ------------------------------------------------------------ helpers
    def opt(self, key, default):
        v = self.host.get(key, default)
        return default if v is None else v

    def _section(self, text: str):
        self.col.addSpacing(24)
        self.col.addWidget(label(text, "section"))
        self.col.addSpacing(10)

    def _switch(self, key: str, default: bool, title: str, sub: str, invert: bool = False):
        sw = SwitchRow()
        sw.title.setText(title)
        sw.sub.setText(sub)
        sw.switch.set_now(bool(self.opt(key, default)) != invert)
        sw.toggled.connect(lambda on, k=key: self.host.set(k, on != invert))
        self.col.addWidget(sw)
        return sw

    def _seg(self, key: str, default: str, options: list[tuple[str, str, str]], cb=None):
        seg = Segmented(options)
        seg.set_value(str(self.opt(key, default)), animated=False)

        def changed(v, k=key):
            self.host.set(k, v)
            if cb:
                cb(v)
        seg.changed.connect(changed)
        self.col.addWidget(seg)
        return seg

    def _comp_row(self, title: str, sub: str, btn: str | None = None, cb=None):
        row = QFrame()
        row.setObjectName("destBox")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 12, 10, 12)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tl = label(title, "rowTitle")
        sl = label(sub, "destSub")
        tv.addWidget(tl)
        tv.addWidget(sl)
        rl.addLayout(tv, 1)
        b = None
        if btn:
            b = button(btn, "destBtn")
            b.clicked.connect(cb)
            rl.addWidget(b)
        self.col.addWidget(row)
        self.col.addSpacing(8)
        return tl, sl, b

    # ------------------------------------------------------------ build
    def render(self):
        while self.col.count():
            it = self.col.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        h = self.host
        y, d = self.versions["yt-dlp"], self.versions["deno"]

        self._section(t("s_engine"))
        title = t("s_updating") if self.updating else (t("s_ytdlp", v=y) if y else t("s_ytdlp_none"))
        _tl, _sl, self.upd_btn = self._comp_row(title, t("s_ytdlp_s"), t("s_update"), self._update)
        if self.upd_btn is not None:
            self.upd_btn.setEnabled(not self.updating and bool(self._exe("yt-dlp")))
        self._comp_row(t("s_deno", v=d) if d else t("s_deno_none"), t("s_deno_s"))
        self._switch("auto_upd", True, t("s_autoupd"), t("s_autoupd_s"))

        self._section(t("s_proxy"))
        self._proxy_block()

        self._section(t("s_login"))
        self._seg("cookies", "none", [("none", t("c_none"), ""), ("firefox", "Firefox", ""), ("chrome", "Chrome", ""),
                                      ("edge", "Edge", "")])
        self.col.addSpacing(10)
        n = label(t("s_login_note"), "note", wrap=True)
        n.setTextFormat(Qt.TextFormat.RichText)
        self.col.addWidget(n)

        self._section(t("s_defaults"))
        self._seg("def_q", "best", [("best", t("q_best"), t("dq_best_s")), ("1080", "1080p", t("dq_1080_s")),
                                    ("720", "720p", t("dq_720_s"))])
        self.col.addSpacing(8)
        self._seg("def_fmt", "mp4o", [(f, t("f_" + f), t(f"f_{f}_s")) for f in ytdlp.FMTS])

        self._section(t("s_naming"))
        self._seg("naming", "title", [("title", t("n_title"), ""), ("author", t("n_author"), ""),
                                      ("date", t("n_date"), "")], cb=lambda _v: self._name_prev())
        self.col.addSpacing(10)
        self.fn_prev = label("", "fnPrev")
        self.fn_prev.setTextFormat(Qt.TextFormat.RichText)
        self.col.addWidget(self.fn_prev)
        self._name_prev()
        self.col.addSpacing(10)
        ns = label(t("s_nosfx"), "noSfx", wrap=True)
        ns.setProperty("hint", True)
        self.col.addWidget(ns)

        self._section(t("s_comfort"))
        self._switch("watch_clip", True, t("s_clip"), t("s_clip_s"))
        self._switch("no_dupes", True, t("s_dupes"), t("s_dupes_s"))
        sw = SwitchRow()
        sw.title.setText(t("s_par3"))
        sw.sub.setText(t("s_par3_s"))
        sw.switch.set_now(self.opt("parallel", 2) == 3)
        sw.toggled.connect(lambda on: h.set("parallel", 3 if on else 2))
        self.col.addWidget(sw)

        self._section(t("s_after"))
        self._seg("after", "none", [("none", t("af_none"), ""), ("folder", t("af_folder"), "")])

        self._section(t("s_hist"))
        self._switch("history", True, t("s_hist_t"), t("s_hist_s"))
        self.col.addSpacing(6)
        self.col.addWidget(label(t("s_keep"), "rowLabel"))
        self.col.addSpacing(6)
        self._seg("keep", "year", [("month", t("k_month"), ""), ("year", t("k_year"), ""), ("all", t("k_all"), "")])
        self.col.addSpacing(10)
        row = QHBoxLayout()
        b = button(t("s_hist_clear"), "ghost")
        b.clicked.connect(self._clear_history)
        row.addWidget(b)
        n = len(History(h.data_dir).items)
        word = t("records")[0 if n % 10 == 1 and n % 100 != 11 else (1 if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 2)]
        row.addWidget(label(t("s_hist_n", n=f"{n} {word}"), "destSub"))
        row.addStretch()
        w = QWidget()
        w.setLayout(row)
        self.col.addWidget(w)
        self.col.addSpacing(16)

    # ------------------------------------------------------------ proxy
    def _proxy_block(self):
        row = QHBoxLayout()
        row.setSpacing(8)
        self.px_edit = QLineEdit(str(self.opt("proxy", "") or ""))
        self.px_edit.setObjectName("tEdit")
        self.px_edit.setPlaceholderText(t("s_proxy_ph"))
        self.px_edit.setClearButtonEnabled(True)
        self.px_edit.editingFinished.connect(self._proxy_typed)
        self.px_edit.returnPressed.connect(self._proxy_check)
        row.addWidget(self.px_edit, 1)
        b = button(t("s_proxy_checking") if self.px == "checking" else t("s_proxy_check"), "destBtn")
        b.setEnabled(self.px != "checking")
        b.clicked.connect(self._proxy_check)
        row.addWidget(b)
        w = QWidget()
        w.setLayout(row)
        self.col.addWidget(w)
        if self.px and self.px != "checking":
            st = label(t("px_" + self.px, u=self.px_addr), "pxOk" if self.px in ("ok", "off", "saved") else "pxErr",
                       wrap=True)
            self.col.addSpacing(8)
            self.col.addWidget(st)
        self.col.addSpacing(10)
        n = label(t("s_proxy_note"), "note", wrap=True)
        self.col.addWidget(n)

    def _proxy_typed(self):
        """Save quietly on focus-out (re-rendering here would swallow a click on «Проверить»)."""
        text = self.px_edit.text().strip()
        if proxy.valid(text) and text != str(self.opt("proxy", "") or ""):
            self.host.set("proxy", text)
            if text and len(proxy.candidates(text)) > 1:      # no type given → find out which one it is
                self._proxy_check()

    def _proxy_check(self):
        if self.px == "checking":
            return
        text = self.px_edit.text().strip()
        if not proxy.valid(text):
            self.px, self.px_addr = "bad", ""
            self.render()
            return
        self.px = "checking"
        self.render()

        def run():
            res, addr = proxy.check(text)
            self.bridge.done.emit("proxy", f"{res}|{addr}|{text}")
        threading.Thread(target=run, daemon=True).start()

    def _name_prev(self):
        sample = {"title": ("", "Cloth simulation breakdown.mp4"),
                  "author": ("Motion Ref Library — ", "Cloth simulation breakdown.mp4"),
                  "date": ("2026-11-18 · Motion Ref Library — ", "Cloth simulation breakdown.mp4")}
        a, b = sample.get(self.opt("naming", "title"), sample["title"])
        try:
            self.fn_prev.setText(f'<span style="color:#8d8b95">{a}</span><b>{b}</b>')
        except RuntimeError:
            pass

    # ------------------------------------------------------------ versions / update
    def _exe(self, name: str):
        try:
            return self.host.component(name)
        except Exception:
            return None

    def _read_versions(self):
        def run():
            for name in ("yt-dlp", "deno"):
                exe = self._exe(name)
                if not exe:
                    continue
                code, out, _ = run_text([exe, "--version"], timeout=20)
                if code == 0 and out.strip():
                    v = out.strip().splitlines()[0]
                    if name == "deno":
                        v = v.split()[1] if len(v.split()) > 1 else v
                    self.bridge.done.emit("ver:" + name, v)
        threading.Thread(target=run, daemon=True).start()

    def _update(self):
        exe = self._exe("yt-dlp")
        if not exe or self.updating:
            return
        self.updating = True
        self.render()
        old = self.versions["yt-dlp"]

        def run():
            run_text([exe, "-U"], timeout=240)
            code, out, _ = run_text([exe, "--version"], timeout=20)
            self.bridge.done.emit("updated", out.strip() if code == 0 else "")
        self._old = old
        threading.Thread(target=run, daemon=True).start()

    def _bg_done(self, what: str, value: str):
        if what == "proxy":
            res, addr, typed = value.split("|", 2)
            self.px, self.px_addr = res, addr
            # keep what works: «1234» that turned out to be HTTP is saved as «http://127.0.0.1:1234»
            self.host.set("proxy", addr if res == "ok" else typed)
        elif what.startswith("ver:"):
            self.versions[what[4:]] = value
        elif what == "updated":
            self.updating = False
            if not value:
                self.host.toast(t("s_update_fail"))
            elif value != getattr(self, "_old", None):
                self.versions["yt-dlp"] = value
                self.host.toast(t("s_updated", v=value))
            else:
                self.host.toast(t("s_uptodate"))
        try:
            self.render()
        except RuntimeError:
            pass

    def _clear_history(self):
        hist = History(self.host.data_dir)
        hist.clear()
        self.host.set("history_cleared", time.time())
        self.host.toast(t("s_hist_cleared"))
        self.render()

