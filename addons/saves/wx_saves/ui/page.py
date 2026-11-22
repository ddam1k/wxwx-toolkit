"""Saves page: paste a link → see what it is → pick quality/format on the right → «Скачать».
Below: «Сейчас» (downloads in progress / done) and «История» (everything saved, searchable)."""
from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..core import links, proxy, ytdlp
from ..core.history import History
from ..core.i18n import files, fmt_size, lang, t
from ..core.runner import Job, Tools, Worker, probe
from ..kit.common import IconButton, Loader, SmoothScroll, TabRow, button, label, pixmap
from .art import Picture, Shimmer, site_html
from .panel import OptionsPanel
from .rows import DlRow, HistRow, PickRow, clock, meta_of
from .theme import stylesheet

# bytes per second, for playlists and lists of links where we don't know the formats yet
RATE = {2160: 2_400_000, 1440: 1_100_000, 1080: 520_000, 720: 260_000, 480: 130_000, 360: 80_000}
ARATE = {"mp3": 40_000, "m4a": 16_500, "opus": 16_000}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def fetch(url: str, dest: str, via: str = "") -> str | None:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return dest
    if via:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        return dest if proxy.fetch(url, dest, via) else None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(6_000_000)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return dest
    except Exception:
        return None


def reveal(path: str) -> None:
    if os.name == "nt" and path and os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)], creationflags=0x08000000)
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class SavesPage(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.setObjectName("savesPage")
        self.loader = Loader(4, self)
        self.loader.done.connect(self._loaded)
        self.hist = History(host.data_dir)
        self.hist.set_keep(host.get("keep", "year") or "year")
        self.jobs: list[Job] = []
        self.workers: dict[int, Worker] = {}
        self.rows: dict[int, DlRow] = {}
        self._uid = 0
        self.state = "none"             # none | loading | video | playlist | batch | error | notlink
        self.info: ytdlp.Info | None = None
        self.cur_url = ""
        self.err = ("", "")
        self.batch: list[dict] = []
        self.sel: set[int] = set()
        self.picks: list[PickRow] = []
        self._last_offered = ""
        self._session_done = 0
        self._thumb_paths: dict[str, str] = {}
        self._pill_url = ""
        self._build()
        self.retranslate()
        self.apply_theme()
        self._render_preview()
        self._render_list()
        self._paste = QShortcut(QKeySequence(QKeySequence.StandardKey.Paste), self)
        self._paste.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._paste.activated.connect(self.paste_clipboard)
        app = QGuiApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._app_state)
        if hasattr(host, "settings_changed"):
            host.settings_changed.connect(self._setting_changed)
        if hasattr(host, "folders_changed"):
            host.folders_changed.connect(self._folders_changed)
        QTimer.singleShot(1500, self._auto_update)

    # ======================================================== tools & settings
    def tools(self) -> Tools:
        def comp(name, exe=None):
            try:
                return self.host.component(name, exe) if exe else self.host.component(name)
            except Exception:
                return None
        return Tools(comp("yt-dlp"), comp("ffmpeg"), comp("ffmpeg", "ffprobe"), comp("deno"))

    def opt(self, key: str, default):
        v = self.host.get(key, default)
        return default if v is None else v

    def via(self) -> str:
        """The proxy address for yt-dlp and thumbnails, "" = direct."""
        return proxy.normalize(self.opt("proxy", "") or "")

    def folder(self) -> str:
        tk = self.host.folder("downloads") if hasattr(self.host, "folder") else ""
        if self.opt("use_tk", True) or not self.opt("own_dir", ""):
            return tk or str(Path.home() / "Downloads")
        return self.opt("own_dir", "")

    # ======================================================== build
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        left = QWidget()
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
        self.open_btn = button("", "ghost")
        self.open_btn.clicked.connect(lambda: reveal(self.folder()))
        self.clear_btn = button("", "ghost")
        self.clear_btn.clicked.connect(self.clear_done)
        head.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignBottom)
        head.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(head)
        v.addSpacing(14)

        bar = QFrame()
        bar.setObjectName("urlBar")
        bar.setFixedHeight(52)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 8, 0)
        bl.setSpacing(10)
        self.site_tag = label("", "siteTag")
        self.site_tag.setTextFormat(Qt.TextFormat.RichText)
        bl.addWidget(self.site_tag)
        self.url = QLineEdit()
        self.url.setObjectName("urlEdit")
        self.url.textChanged.connect(self._url_typed)
        self.url.returnPressed.connect(self.start)
        self.url.installEventFilter(self)
        bl.addWidget(self.url, 1)
        self.url_x = IconButton("x", 28, 13)
        self.url_x.clicked.connect(self.clear_url)
        bl.addWidget(self.url_x)
        self.paste_btn = button("", "ghost")
        self.paste_btn.clicked.connect(self.paste_clipboard)
        bl.addWidget(self.paste_btn)
        self.urlbar = bar
        v.addWidget(bar)
        self._url_timer = QTimer(self)
        self._url_timer.setSingleShot(True)
        self._url_timer.setInterval(380)
        self._url_timer.timeout.connect(self._url_settled)

        pill = QFrame()
        pill.setObjectName("clipPill")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(12, 6, 6, 6)
        pl.setSpacing(10)
        self.pill_text = label("", "clipText")
        self.pill_text.setTextFormat(Qt.TextFormat.RichText)
        self.pill_text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        pl.addWidget(self.pill_text, 1)
        self.pill_go = button("", "accent")
        self.pill_go.clicked.connect(self._pill_paste)
        pl.addWidget(self.pill_go)
        px = IconButton("x", 26, 12)
        px.clicked.connect(lambda: self.pill.hide())
        pl.addWidget(px)
        self.pill = pill
        pill.hide()
        v.addSpacing(10)
        v.addWidget(pill)

        self.pv_host = QWidget()
        self.pv_lay = QVBoxLayout(self.pv_host)
        self.pv_lay.setContentsMargins(0, 4, 0, 0)
        self.pv_lay.setSpacing(10)
        v.addWidget(self.pv_host)
        v.addSpacing(12)

        lh = QHBoxLayout()
        lh.setSpacing(10)
        self.tabs = TabRow()
        self.tab_now = self.tabs.add("now", "")
        self.tab_hist = self.tabs.add("hist", "")
        self.tabs.select("now", animated=False)
        self.tabs.changed.connect(self._tab)
        lh.addWidget(self.tabs, 1)
        self.speed = label("", "speed")
        lh.addWidget(self.speed, 0, Qt.AlignmentFlag.AlignVCenter)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(lambda _s: self._render_history())
        self.search.hide()
        lh.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(lh)
        v.addSpacing(8)

        self.stack = QStackedWidget()
        self.now_scroll = SmoothScroll()
        self.now_scroll.setWidgetResizable(True)
        self.now_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.now_lay = QVBoxLayout(inner)
        self.now_lay.setContentsMargins(0, 0, 4, 0)
        self.now_lay.setSpacing(8)
        self.empty = QWidget()
        el = QVBoxLayout(self.empty)
        el.addStretch()
        self.empty_t = label("", "idleTitle")
        self.empty_s = label("", "idleHint", wrap=True)
        for w in (self.empty_t, self.empty_s):
            w.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            el.addWidget(w)
        el.addStretch()
        self.empty.setMinimumHeight(150)
        self.now_lay.addWidget(self.empty)
        self.now_lay.addStretch(1)
        self.now_scroll.setWidget(inner)
        self.stack.addWidget(self.now_scroll)
        self.hist_scroll = SmoothScroll()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hin = QWidget()
        self.hist_lay = QVBoxLayout(hin)
        self.hist_lay.setContentsMargins(0, 0, 4, 0)
        self.hist_lay.setSpacing(2)
        self.hist_scroll.setWidget(hin)
        self.stack.addWidget(self.hist_scroll)
        v.addWidget(self.stack, 1)
        root.addWidget(left, 1)

        seam = QFrame()
        seam.setObjectName("seam")
        seam.setFixedWidth(1)
        root.addWidget(seam)
        self.panel = OptionsPanel(self.host)
        self.panel.changed.connect(self._totals)
        self.panel.go.connect(self.start)
        self.panel.pick_dir.connect(self._pick_dir)
        root.addWidget(self.panel)
        self._apply_defaults()
        self._update_dest()

    def eventFilter(self, obj, ev):
        if obj is self.url and ev.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.urlbar.setProperty("focus", ev.type() == QEvent.Type.FocusIn)
            self.urlbar.style().unpolish(self.urlbar)
            self.urlbar.style().polish(self.urlbar)
        return False

    # ======================================================== language / theme
    def retranslate(self):
        self.h_title.setText(t("title"))
        self.h_sub.setText(t("sub"))
        self.open_btn.setText(t("open_dir"))
        self.clear_btn.setText(t("clear_list"))
        self.clear_btn.setToolTip(t("clear_tip"))
        self.url.setPlaceholderText(t("url_ph"))
        self.paste_btn.setText(t("paste"))
        self.pill_go.setText(t("clip_paste"))
        self.search.setPlaceholderText(t("search"))
        self.empty_t.setText(t("empty_t"))
        self.empty_s.setText(t("empty_s"))
        self.url_x.setToolTip("✕")
        self.panel.retranslate()
        for r in self.rows.values():
            r.retranslate()
            r.update_state()
        self._site_tag()
        self._update_dest()
        self._counts()
        self._render_preview()
        self._render_history()

    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        self.update()

    def _setting_changed(self, key: str):
        if key in ("use_tk", "own_dir"):
            self._update_dest()
        elif key in ("def_q", "def_fmt"):
            self._apply_defaults()
        elif key in ("history", "keep"):
            self.hist.set_keep(self.opt("keep", "year"))
            self._render_history()
            self._counts()
        elif key == "parallel":
            self._pump()
        elif key == "history_cleared":
            self.hist.load()
            self._render_history()
            self._counts()

    def _apply_defaults(self):
        q = self.opt("def_q", "best")
        self.panel.set_defaults(0 if q == "best" else int(q), self.opt("def_fmt", "mp4o"))

    def _folders_changed(self, _kind: str):
        self._update_dest()

    def _update_dest(self):
        use_tk = bool(self.opt("use_tk", True))
        self.panel.set_dest(use_tk, self.folder(), t("tk_dir_s") if use_tk else t("own_dir_s"))

    def _pick_dir(self):
        d = self.panel.ask_dir(self.folder())
        if d:
            self.host.set("own_dir", d)
            self._update_dest()

    # ======================================================== link input
    def paste_clipboard(self):
        text = QGuiApplication.clipboard().text()
        if links.split(text):
            self.url.setText(text.strip())
            self.url.setFocus()
            self.pill.hide()
        else:
            self.host.toast(t("pasted_none"))

    def clear_url(self):
        self.url.clear()
        self.url.setFocus()

    def _url_typed(self, _text):
        self.url_x.setVisible(bool(self.url.text()))
        self._site_tag()
        self._url_timer.start()

    def _site_tag(self):
        ls = links.split(self.url.text())
        if not self.url.text().strip():
            self.site_tag.setText(f'<span style="color:#5b5a63">●</span>&nbsp;{t("link")}')
        elif not ls:
            self.site_tag.setText(f'<span style="color:#d0806a">●</span>&nbsp;{t("not_link")}')
        elif len(ls) > 1:
            self.site_tag.setText(site_html("site", t("links_n", n=len(ls))))
        else:
            s = links.site(ls[0])
            self.site_tag.setText(site_html(s, t("site") if s == "site" else s))

    def _url_settled(self):
        text = self.url.text().strip()
        ls = links.split(text)
        if not text:
            self._set_state("none")
        elif not ls:
            self._set_state("notlink")
        elif len(ls) == 1:
            if ls[0] != self.cur_url or self.state in ("none", "notlink"):
                self._probe(ls[0])
        else:
            self._start_batch(ls)

    def _probe(self, url: str):
        self.cur_url = url
        self.info = None
        self._set_state("loading")
        pl = links.is_playlist(url)
        self.loader.submit("probe:" + url, probe, self.tools(), url, pl, self.opt("cookies", "none"), self.via())

    def _start_batch(self, ls: list[str]):
        self.cur_url = " ".join(ls)
        self.batch = [{"url": u, "site": links.site(u), "title": "", "duration": 0.0, "info": None} for u in ls]
        self.sel = set(range(len(ls)))
        self._set_state("batch")
        tools = self.tools()
        for i, u in enumerate(ls):
            self.loader.submit(f"bprobe:{i}:{u}", probe, tools, u, False, self.opt("cookies", "none"), self.via())

    def _loaded(self, key: str, value):
        try:
            self._loaded_safe(key, value)
        except RuntimeError:
            pass

    def _loaded_safe(self, key: str, value):
        if key.startswith("probe:"):
            url = key[6:]
            if url != self.cur_url:
                return
            info, err = value if value else (None, "error")
            if info is None:
                kind = "tool" if err == "no-yt-dlp" else ytdlp.error_kind(err)
                self.err = (kind, ytdlp.last_error(err))
                self._set_state("error")
                return
            self.info = info
            if info.playlist:
                have = {h.get("key") for h in self.hist.items}
                skip = bool(self.opt("no_dupes", True))
                self.sel = {i for i, e in enumerate(info.entries) if not (skip and e["id"] and e["id"] in have)}
                self._set_state("playlist")
            else:
                self._set_state("video")
            self._load_thumb(info.thumbnail, info.id or str(abs(hash(info.url))))
        elif key.startswith("bprobe:"):
            _, i, url = key.split(":", 2)
            i = int(i)
            if self.state != "batch" or i >= len(self.batch) or self.batch[i]["url"] != url:
                return
            info, _err = value if value else (None, "")
            if info is not None:
                self.batch[i].update(title=info.title, duration=info.duration, info=info, site=info.site)
                if info.thumbnail and i == 0:
                    self._load_thumb(info.thumbnail, info.id or str(abs(hash(url))))
            else:
                self.batch[i]["title"] = self.batch[i]["title"] or url
            self._render_preview()
            self._totals()
        elif key.startswith("thumb:"):
            if value:
                pm = pixmap(value)
                for pic in self.findChildren(Picture):
                    if getattr(pic, "thumb_key", "") == key[6:]:
                        pic.set_pixmap(pm)
                self._thumb_paths[key[6:]] = value


    def _thumb_file(self, k: str) -> str:
        return str(Path(self.host.data_dir) / "thumbs" / (k.replace("/", "_")[:80] + ".jpg"))

    def _load_thumb(self, url: str, k: str):
        if not url:
            return
        self.loader.submit("thumb:" + k, fetch, url, self._thumb_file(k), self.via())

    # ======================================================== clipboard watch
    def _app_state(self, st):
        if st == Qt.ApplicationState.ApplicationActive and self.isVisible():
            QTimer.singleShot(150, self._check_clipboard)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(250, self._check_clipboard)

    def _check_clipboard(self):
        if not self.opt("watch_clip", True) or not self.isVisible():
            return
        ls = links.split(QGuiApplication.clipboard().text())
        if not ls:
            return
        u = ls[0]
        if u == self._last_offered or u in self.url.text():
            return
        self._last_offered = u
        self._pill_url = u
        s = links.site(u)
        self.pill_text.setText(t("clip_found", site=site_html(s, t("site") if s == "site" else s)))
        self.pill.show()

    def _pill_paste(self):
        self.pill.hide()
        self.url.setText(self._pill_url)

    # ======================================================== preview
    def _set_state(self, state: str):
        self.state = state
        if state in ("video", "playlist"):
            kind = state
        elif state == "batch":
            kind = "batch"
        else:
            kind = "none"
        self.panel.set_target(self.info if state in ("video", "playlist") else None, kind, error=state == "error")
        if state in ("video", "playlist"):
            self._restore_opts()
        self._render_preview()
        self._totals()

    def _restore_opts(self):
        o = self.panel.o
        o.afmt = self.opt("afmt", "mp3")
        o.thumb = False
        self.panel.refresh()

    def _clear_preview(self):
        while self.pv_lay.count():
            it = self.pv_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _card(self, err: bool = False) -> tuple[QFrame, QHBoxLayout]:
        card = QFrame()
        card.setObjectName("pv")
        card.setProperty("err", err)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(16)
        self.pv_lay.addWidget(card)
        return card, lay

    def _x_button(self, lay: QHBoxLayout):
        x = IconButton("x", 26, 12, "")
        x.clicked.connect(self.clear_url)
        lay.addWidget(x, 0, Qt.AlignmentFlag.AlignTop)

    def _render_preview(self):
        self._clear_preview()
        st = self.state
        self.pv_host.setVisible(st != "none")
        if st == "loading":
            sh = Shimmer()
            sh.text = t("probing")
            self.pv_lay.addWidget(sh)
        elif st == "notlink":
            _c, lay = self._card(True)
            col = QVBoxLayout()
            col.addWidget(label(t("not_link_t"), "pvTitle"))
            col.addWidget(label(t("not_link_s"), "pvErr", wrap=True))
            lay.addLayout(col, 1)
        elif st == "error":
            self._render_error()
        elif st == "video" and self.info:
            self._render_video(self.info)
        elif st == "playlist" and self.info:
            self._render_list_card(self.info.title, self.info.uploader, self.info.site,
                                   [(e["title"], e["duration"], e["id"]) for e in self.info.entries],
                                   self.info.thumbnail, self.info.id)
        elif st == "batch":
            n = len(self.batch)
            self._render_list_card(t("links_n", n=n) if n > 1 else "", "", "site",
                                   [(b["title"] or b["url"], b["duration"], (b["info"].id if b["info"] else ""))
                                    for b in self.batch], "", "batch", sites=[b["site"] for b in self.batch])
        self._counts()

    def _picture(self, w: int, h: int, site: str, k: str, badge: str = "") -> Picture:
        pic = Picture(w, h)
        pic.site = site
        pic.badge = badge
        pic.thumb_key = k
        path = self._thumb_paths.get(k) or (self._thumb_file(k) if os.path.isfile(self._thumb_file(k)) else None)
        if path:
            pic.set_pixmap(pixmap(path))
        return pic

    def _render_error(self):
        kind, text = self.err
        _c, lay = self._card(True)
        site = links.site(self.cur_url)
        lay.addWidget(self._picture(74, 100, site, ""))
        col = QVBoxLayout()
        col.setSpacing(5)
        tag = label(site_html(site, t("site") if site == "site" else site), "siteTag")
        tag.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(tag)
        col.addWidget(label(t("e_" + kind, site=t("site") if site == "site" else site), "pvTitle"))
        sub = label(t("e_network_px_s" if kind == "network" and self.via() else f"e_{kind}_s"), "pvErr", wrap=True)
        sub.setToolTip(text)
        col.addWidget(sub)
        row = QHBoxLayout()
        row.setSpacing(8)
        if kind in ("login", "cookies") or (kind == "network" and not self.via()):
            b = button(t("e_login_btn") if kind != "network" else t("e_proxy_btn"), "accent")
            b.clicked.connect(self._open_settings)
            row.addWidget(b)
        r = button(t("retry"), "ghost")
        r.clicked.connect(lambda: self._probe(self.cur_url))
        row.addWidget(r)
        if text:
            d = button(t("details"), "link")
            d.setToolTip(text)
            d.clicked.connect(lambda: self.host.toast(text[:220]))
            row.addWidget(d)
        row.addStretch()
        col.addLayout(row)
        lay.addLayout(col, 1)
        self._x_button(lay)

    def _open_settings(self):
        if hasattr(self.host, "open_settings"):
            self.host.open_settings()

    def _render_video(self, inf: ytdlp.Info):
        _c, lay = self._card()
        k = inf.id or str(abs(hash(inf.url)))
        dur = clock(inf.duration) if inf.duration else ""
        pic = self._picture(74, 131, inf.site, k, dur) if inf.vertical else self._picture(208, 117, inf.site, k, dur)
        pic.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(inf.url)))
        lay.addWidget(pic)
        col = QVBoxLayout()
        col.setSpacing(5)
        tag = label(site_html(inf.site, t("site") if inf.site == "site" else inf.site), "siteTag")
        tag.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(tag)
        title = label(inf.title, "pvTitle", wrap=True)
        title.setMaximumHeight(46)
        col.addWidget(title)
        meta = inf.uploader + (f" · {t('views', n=self._num(inf.views))}" if inf.views else "")
        col.addWidget(label(meta, "pvMeta"))
        col.addStretch()
        tags = QHBoxLayout()
        tags.setSpacing(6)
        was = self.hist.find(key=inf.id) if inf.id else self.hist.find(url=inf.url)
        if was:
            b = QPushButton(t("was", when=self._when(was["t"])))
            b.setObjectName("tagWas")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda: self._jump_history(was["hid"]))
            tags.addWidget(b)
        bits = []
        if inf.heights:
            bits.append(ytdlp.label(inf.max_h) + (f" · {round(inf.fps)} fps" if inf.fps > 30 else ""))
        if inf.vertical:
            bits.append(t("vertical"))
        if inf.subs:
            bits.append(t("subs_tag", l=", ".join(s.upper() for s in inf.subs[:3])))
        for b in bits:
            tags.addWidget(label(b, "tag"))
        tags.addStretch()
        col.addLayout(tags)
        lay.addLayout(col, 1)
        self._x_button(lay)

    def _render_list_card(self, title: str, who: str, site: str, rows: list, thumb: str, k: str, sites=None):
        _c, lay = self._card()
        total = sum(r[1] for r in rows)
        lay.addWidget(self._picture(160, 90, site, k, clock(total) if total else ""))
        col = QVBoxLayout()
        col.setSpacing(5)
        if site != "site":
            tag = label(site_html(site, site), "siteTag")
            tag.setTextFormat(Qt.TextFormat.RichText)
            col.addWidget(tag)
        col.addWidget(label(title or t("links_n", n=len(rows)), "pvTitle", wrap=True))
        if who:
            col.addWidget(label(who, "pvMeta"))
        col.addStretch()
        tags = QHBoxLayout()
        tags.addWidget(label(t("playlist_n", n=len(rows)) if sites is None else t("links_n", n=len(rows)), "tag"))
        tags.addStretch()
        col.addLayout(tags)
        lay.addLayout(col, 1)
        self._x_button(lay)
        # picks
        box = QFrame()
        box.setObjectName("picks")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(6, 6, 6, 6)
        bl.setSpacing(0)
        hh = QHBoxLayout()
        hh.setContentsMargins(8, 2, 4, 6)
        self.picks_lbl = label("", "picksHead")
        hh.addWidget(self.picks_lbl, 1)
        self.picks_all = button("", "link")
        self.picks_all.clicked.connect(self._toggle_all)
        hh.addWidget(self.picks_all)
        bl.addLayout(hh)
        sc = SmoothScroll()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(0)
        self.picks = []
        have = {h.get("key") for h in self.hist.items}
        for i, (name, dur, vid) in enumerate(rows):
            note = t("have") if vid and vid in have else (sites[i] if sites and sites[i] != "site" else "")
            r = PickRow(i + 1, name, clock(dur) if dur else "…", note)
            r.setChecked(i in self.sel)
            r.toggled.connect(lambda on, idx=i: self._pick(idx, on))
            il.addWidget(r)
            self.picks.append(r)
        il.addStretch()
        sc.setWidget(inner)
        sc.setFixedHeight(min(176, 32 * len(rows) + 4))
        bl.addWidget(sc)
        self.pv_lay.addWidget(box)
        self._picks_head()

    def _picks_head(self):
        n = len(self.picks)
        if not hasattr(self, "picks_lbl"):
            return
        try:
            self.picks_lbl.setText(t("picked", n=len(self.sel), m=n))
            self.picks_all.setText(t("pick_none") if len(self.sel) == n else t("pick_all"))
        except RuntimeError:
            pass

    def _pick(self, i: int, on: bool):
        (self.sel.add if on else self.sel.discard)(i)
        self._picks_head()
        self._totals()

    def _toggle_all(self):
        n = len(self.picks)
        on = len(self.sel) != n
        self.sel = set(range(n)) if on else set()
        for r in self.picks:
            r.blockSignals(True)
            r.setChecked(on)
            r.blockSignals(False)
            r.update()
        self._picks_head()
        self._totals()

    @staticmethod
    def _num(n: int) -> str:
        ru = lang() == "ru"
        if n >= 1_000_000:
            v = f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".")
            return (v.replace(".", ",") + " млн") if ru else (v + "M")
        if n >= 1000:
            return f"{n // 1000}" + (" тыс." if ru else "K")
        return str(n)

    @staticmethod
    def _when(ts: float) -> str:
        d = datetime.fromtimestamp(ts).date()
        days = (datetime.now().date() - d).days
        if days == 0:
            return t("today_h").lower()
        if days == 1:
            return t("yesterday_h").lower()
        return f"{d.day} {t('months')[d.month - 1]}"

    # ======================================================== totals
    def _rate(self, o: ytdlp.Opts) -> float:
        if o.what == "audio":
            return ARATE[o.afmt]
        return RATE.get(o.q or 1080, 520_000)

    def _totals(self):
        o = self.panel.o
        st = self.state
        if st == "video" and self.info:
            est = ytdlp.estimate(self.info, o)
            h = o.q or self.info.max_h
            desc = o.afmt.upper() if o.what == "audio" else f"{ytdlp.label(h) if h else ''} · {'MP4' if o.fmt != 'orig' else 'WebM'}"
            was = self.hist.find(key=self.info.id) if self.info.id else None
            go = t("go_part") if o.part else (t("go_again") if was else t("go"))
            self.panel.set_total(self._total_html(est, desc), go, True)
        elif st in ("playlist", "batch"):
            durs = ([e["duration"] for e in self.info.entries] if st == "playlist" and self.info
                    else [b["duration"] for b in self.batch])
            n = len(self.sel)
            secs = sum(durs[i] for i in self.sel if i < len(durs))
            est = secs * self._rate(o)
            desc = o.afmt.upper() if o.what == "audio" else f"{ytdlp.label(o.q) if o.q else t('q_best')} · {'MP4' if o.fmt != 'orig' else 'WebM'}"
            self.panel.set_total(self._total_html(est, desc), t("go_n", n=files(n)), n > 0)
        else:
            self.panel.set_total("—", t("go"), False)

    @staticmethod
    def _total_html(b: float, desc: str) -> str:
        size = ("≈ " + fmt_size(b)) if b else "—"
        return f'{size}&nbsp;&nbsp;<span style="color:#b8a8e2;font-size:8.6pt">{desc}</span>'

    # ======================================================== downloading
    def start(self):
        st = self.state
        if st not in ("video", "playlist", "batch"):
            if st == "none" and self.url.text().strip():
                self._url_settled()
            return
        o = self.panel.o
        base = dataclasses.replace(o, folder=self.folder(), cookies=self.opt("cookies", "none"), proxy=self.via(),
                                   naming=self.opt("naming", "title"), subfolder="")
        new: list[Job] = []
        if st == "video" and self.info:
            inf = self.info
            j = self._job(inf.url, inf.title, inf.site, base, inf.id, inf.vertical, ytdlp.estimate(inf, base), inf.duration,
                          ytdlp.needs_recode(inf, base), o.q or inf.max_h, inf.thumbnail)
            new.append(j)
        elif st == "playlist" and self.info:
            inf = self.info
            sub = dataclasses.replace(base, subfolder=ytdlp.safe_name(inf.title or "playlist"), part=None)
            for i in sorted(self.sel):
                e = inf.entries[i]
                if not e["url"]:
                    continue
                new.append(self._job(e["url"], e["title"], inf.site, sub, e["id"], False, e["duration"] * self._rate(sub),
                                     e["duration"], sub.what == "video" and sub.fmt == "mp4", sub.q, ""))
        elif st == "batch":
            for i in sorted(self.sel):
                b = self.batch[i]
                inf = b["info"]
                bo = dataclasses.replace(base, part=None, subs=None)
                if inf is not None:
                    est = ytdlp.estimate(inf, bo)
                    new.append(self._job(b["url"], inf.title, inf.site, bo, inf.id, inf.vertical, est, inf.duration,
                                         ytdlp.needs_recode(inf, bo), bo.q or inf.max_h, inf.thumbnail))
                else:
                    new.append(self._job(b["url"], b["url"], b["site"], bo, "", False, 0.0, 0.0,
                                         bo.what == "video" and bo.fmt == "mp4", bo.q, ""))
        if not new:
            return
        self.host.set("afmt", o.afmt)
        for j in new:
            self.jobs.insert(0, j)
            self._add_row(j)
        self.host.toast(t("queued", n=files(len(new))) if len(new) > 1 else t("started"))
        self.url.clear()
        self.cur_url = ""
        self.info = None
        self._set_state("none")
        if self.tabs.current != "now":
            self.tabs.select("now", emit=True)
        self._pump()

    def _job(self, url, title, site, o, key, vertical, est, dur, recode, height, thumb) -> Job:
        self._uid += 1
        tmp = str(Path(self.host.data_dir) / "tmp" / f"job-{int(time.time())}-{self._uid}")
        j = Job(id=self._uid, url=url, title=title or url, site=site, opts=o, key=key or "", thumb=thumb or "",
                vertical=vertical, est=est, duration=dur, recode=bool(recode), tmp=tmp,
                meta=meta_of(site, o, height))
        return j

    def _add_row(self, j: Job):
        can_send = bool(hasattr(self.host, "send_to") and hasattr(self.host, "installed") and self.host.installed("compress"))
        row = DlRow(j, can_send)
        row.action.connect(self._row_action)
        if j.thumb:
            k = j.key or str(abs(hash(j.url)))
            row.pic.thumb_key = k
            path = self._thumb_paths.get(k) or (self._thumb_file(k) if os.path.isfile(self._thumb_file(k)) else None)
            if path:
                row.pic.set_pixmap(pixmap(path))
            else:
                self._load_thumb(j.thumb, k)
        self.rows[j.id] = row
        self.now_lay.insertWidget(0, row)
        self._render_list()

    def _parallel(self) -> int:
        return 3 if self.opt("parallel", 2) == 3 else 2

    def _pump(self):
        busy = sum(1 for j in self.jobs if j.state == "work")
        tools = self.tools()
        for j in reversed(self.jobs):
            if busy >= self._parallel():
                break
            if j.state == "wait":
                w = self.workers.get(j.id)
                if w is None:
                    w = Worker(j, tools, self)
                    w.changed.connect(self._job_changed)
                    w.finished.connect(self._job_finished)
                    self.workers[j.id] = w
                w.tools = tools
                w.start()
                self._job_changed(j.id)            # «В очереди» → «Начинаю…» right away
                busy += 1
        self._counts()

    def _job_changed(self, jid: int):
        row = self.rows.get(jid)
        if row is not None:
            try:
                row.update_state()
            except RuntimeError:
                pass
        sp = sum(j.speed for j in self.jobs if j.state == "work")
        self.speed.setText(f"↓ {fmt_size(sp)}/s" if sp else "")

    def _job_finished(self, jid: int):
        j = next((x for x in self.jobs if x.id == jid), None)
        if j is None:
            return
        self._job_changed(jid)
        if j.state == "done":
            self._session_done += 1
            if self.opt("history", True):
                k = j.key or str(abs(hash(j.url)))
                thumb = self._thumb_paths.get(k) or (self._thumb_file(k) if os.path.isfile(self._thumb_file(k)) else "")
                self.hist.add({"key": j.key, "title": j.title, "site": j.site, "meta": j.meta, "url": j.url,
                               "path": j.path, "size": j.size, "kind": j.opts.what, "vertical": j.vertical,
                               "thumb": thumb})
                if self.tabs.current == "hist":
                    self._render_history()
        self._pump()
        if not any(x.state in ("work", "wait") for x in self.jobs) and self._session_done:
            if self.opt("after", "none") == "folder":
                reveal(j.path or self.folder())
                self.host.toast(t("all_done_dir"))
            else:
                self.host.toast(t("all_done"))
            self._session_done = 0
        self._counts()

    def _row_action(self, jid: int, action: str):
        j = next((x for x in self.jobs if x.id == jid), None)
        if j is None:
            return
        w = self.workers.get(jid)
        if action == "folder":
            reveal(j.path or self.folder())
        elif action == "send":
            if j.path and self.host.send_to("compress", [j.path]):
                self.host.toast(t("sent"))
        elif action == "pause" and w:
            w.stop("pause")
        elif action == "resume":
            j.state = "wait"
            self._job_changed(jid)
            self._pump()
        elif action == "retry":
            j.state, j.frac, j.err_kind, j.err_text, j.stage = "wait", 0.0, "", "", "start"
            self._job_changed(jid)
            self._pump()
        elif action == "remove":
            if j.state in ("work",) and w:
                w.stop("cancel")
            elif j.state in ("pause", "wait", "err") and j.tmp:
                threading.Thread(target=shutil.rmtree, args=(j.tmp, True), daemon=True).start()
            self._drop(jid)

    def _drop(self, jid: int):
        self.jobs = [x for x in self.jobs if x.id != jid]
        self.workers.pop(jid, None)
        row = self.rows.pop(jid, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self._render_list()
        self._pump()

    def clear_done(self):
        done = [j.id for j in self.jobs if j.state in ("done", "cancel")]
        if not done:
            self.host.toast(t("nothing_done"))
            return
        for jid in done:
            self._drop(jid)
        self.host.toast(t("removed_n", n=len(done)))

    def _render_list(self):
        self.empty.setVisible(not self.rows)
        self._counts()

    def _counts(self):
        busy = sum(1 for j in self.jobs if j.state in ("work", "wait"))
        self.tab_now.setText(t("tab_now"))
        self.tab_hist.setText(t("tab_hist"))
        self.tab_now.set_count(busy or len(self.jobs), tint=bool(busy))
        self.tab_hist.set_count(len(self.hist.items) if self.opt("history", True) else 0, tint=False)
        self.clear_btn.setVisible(any(j.state in ("done", "cancel") for j in self.jobs))
        self.tabs.select(self.tabs.current, animated=False)

    # ======================================================== history
    def _tab(self, key: str):
        self.stack.setCurrentIndex(1 if key == "hist" else 0)
        self.search.setVisible(key == "hist")
        self.speed.setVisible(key == "now")
        if key == "hist":
            self._render_history()

    def _jump_history(self, hid: str):
        self.tabs.select("hist", emit=True)

    def _render_history(self):
        lay = self.hist_lay
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        if not self.opt("history", True):
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.addStretch()
            for txt, name in ((t("h_off_t"), "idleTitle"), (t("h_off_s"), "idleHint")):
                lb = label(txt, name, wrap=True)
                lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                bl.addWidget(lb)
            b = button(t("h_off_btn"), "link")
            b.clicked.connect(self._open_settings)
            bl.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
            bl.addStretch()
            box.setMinimumHeight(170)
            lay.addWidget(box)
            lay.addStretch(1)
            return
        items = self.hist.search(self.search.text())
        if not items:
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.addStretch()
            none = bool(self.hist.items)
            for txt, name in ((t("h_none_t") if none else t("h_empty_t"), "idleTitle"),
                              (t("h_none_s") if none else t("h_empty_s"), "idleHint")):
                lb = label(txt, name, wrap=True)
                lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                bl.addWidget(lb)
            bl.addStretch()
            box.setMinimumHeight(170)
            lay.addWidget(box)
            lay.addStretch(1)
            return
        last = ""
        for item in items[:400]:
            day = self._day(item.get("t", 0))
            if day != last:
                lay.addWidget(label(day, "dayLbl"))
                last = day
            row = HistRow(item, History.gone(item))
            if item.get("thumb") and os.path.isfile(item["thumb"]):
                row.pic.set_pixmap(pixmap(item["thumb"]))
            row.action.connect(self._hist_action)
            lay.addWidget(row)
        lay.addStretch(1)

    @staticmethod
    def _day(ts: float) -> str:
        d = datetime.fromtimestamp(ts).date()
        days = (datetime.now().date() - d).days
        if days == 0:
            return t("today_h")
        if days == 1:
            return t("yesterday_h")
        return f"{d.day} {t('months')[d.month - 1]}" + (f" {d.year}" if d.year != datetime.now().year else "")

    def _hist_action(self, hid: str, action: str):
        item = next((i for i in self.hist.items if i.get("hid") == hid), None)
        if item is None:
            return
        if action == "file":
            reveal(item.get("path", ""))
        elif action == "link":
            QDesktopServices.openUrl(QUrl(item.get("url", "")))
        elif action == "again":
            self.url.setText(item.get("url", ""))
            self.host.toast(t("again_hint"))
        elif action == "remove":
            self.hist.remove(hid)
            self._render_history()
            self._counts()

    # ======================================================== yt-dlp self-update
    def _auto_update(self):
        if not self.opt("auto_upd", True):
            return
        last = float(self.opt("upd_at", 0) or 0)
        if time.time() - last < 86400:
            return
        exe = self.tools().ytdlp
        if not exe:
            return
        self.host.set("upd_at", time.time())

        def run():
            from ..core.runner import run_text
            run_text([exe, "-U"], timeout=180)
        threading.Thread(target=run, daemon=True).start()

    # ======================================================== toolkit hooks
    def is_busy(self) -> bool:
        return any(j.state in ("work", "wait") for j in self.jobs)

    def shutdown(self):
        for w in list(self.workers.values()):
            w.stop("pause")
        self.loader.shutdown()
