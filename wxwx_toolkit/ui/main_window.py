"""Main window: header, sidebar with tools, pages (store, settings, add-ons) and all the controller logic."""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QPointF, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core import addons, components, i18n, updater
from ..core.addons import CatalogEntry, Manifest
from ..core.i18n import t
from ..core.paths import data_dir
from .host import Host
from .pages import CardModel, ErrorPage, SettingsPage, StorePage
from .shell import NavButton, Sidebar
from .theme import stylesheet, theme
from .update_bar import UpdateBar
from .widgets import Logo, RevealOverlay, ThemeToggle, Toast

OPTION_DEFAULTS = {"au_addons": True, "au_new": False, "au_ask": True}


class Bridge(QObject):
    catalog_loaded = Signal(object)
    catalog_failed = Signal(str)
    op_progress = Signal(str, str, float, str)     # kind (addon|comp), id, fraction, text
    op_done = Signal(str, str, object)
    op_failed = Signal(str, str, str)
    comp_versions = Signal(object)
    update_found = Signal(object, bool)
    update_failed = Signal(str, bool)
    update_progress = Signal(int, int)
    update_ready = Signal(str)


def _label(text: str, name: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(name)
    return lb


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.store = QSettings("wxwx", "toolkit")
        theme.name = "light" if self.store.value("theme", "dark") == "light" else "dark"
        i18n.set_lang(str(self.store.value("lang", "ru")))
        self.seen = set(filter(None, str(self.store.value("seen_addons", "") or "").split(",")))

        self.pool = ThreadPoolExecutor(max_workers=3)
        self.bridge = Bridge()
        b = self.bridge
        b.catalog_loaded.connect(self._on_catalog)
        b.catalog_failed.connect(self._on_catalog_failed)
        b.op_progress.connect(self._on_op_progress)
        b.op_done.connect(self._on_op_done)
        b.op_failed.connect(self._on_op_failed)
        b.comp_versions.connect(self._on_comp_versions)
        b.update_found.connect(self._on_update_found)
        b.update_failed.connect(self._on_update_failed)
        b.update_progress.connect(lambda d, tot: self.update_bar.set_downloading(d, tot))
        b.update_ready.connect(self._on_update_ready)

        self.installed: dict[str, Manifest] = addons.installed()
        self.catalog: list[CatalogEntry] = []
        self.catalog_state = "loading"
        self.busy_addons: dict[str, tuple[float, str]] = {}
        self.busy_components: dict[str, tuple[float, str]] = {}
        self.pages: dict[str, QWidget] = {}
        self.hosts: dict[str, Host] = {}
        self.nav: dict[str, NavButton] = {}
        self.current = "store"
        self.release: updater.Release | None = None
        self._update_busy = False
        self._smoke: str | None = None
        self.smoke_errors: list[str] = []

        self._build()
        self.resize(1180, 760)
        self.setMinimumSize(940, 620)
        geo = self.store.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        self.apply_theme()
        self.toggle.set_light(theme.name == "light", animated=False)

        for m in self.installed.values():
            self._load_addon(m)
        self.retranslate()
        self.go("store")
        self.load_catalog()
        self.pool.submit(self._read_component_versions)
        if self.option("au_ask"):
            QTimer.singleShot(2500, lambda: self.check_updates(manual=False))

    # ======================================================== settings
    def option(self, key: str) -> bool:
        v = self.store.value(f"opt/{key}")
        return OPTION_DEFAULTS[key] if v is None else str(v).lower() in ("true", "1")

    def set_option(self, key: str, on: bool) -> None:
        self.store.setValue(f"opt/{key}", on)

    # ======================================================== layout
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        self.central = central
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(54)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 0, 16, 0)
        hl.setSpacing(11)
        self.logo = Logo(28)
        hl.addWidget(self.logo)
        tl = QVBoxLayout()
        tl.setSpacing(0)
        tl.addStretch()
        tl.addWidget(_label(APP_NAME, "appTitle"))
        tl.addWidget(_label("by yuyu", "appBy"))
        tl.addStretch()
        hl.addLayout(tl)
        hl.addStretch()
        self.toggle = ThemeToggle()
        self.toggle.clicked.connect(self.on_theme)
        hl.addWidget(self.toggle)
        root.addWidget(header)

        self.update_bar = UpdateBar()
        self.update_bar.update_clicked.connect(self.install_update)
        self.update_bar.later_clicked.connect(lambda: self.update_bar.slide(False))
        self.update_bar.notes_clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.release.page_url if self.release else updater.RELEASES_PAGE)))
        root.addWidget(self.update_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        self.sidebar = Sidebar()
        sl = self.sidebar.lay
        self.lbl_tools = _label("", "sideSection")
        self.lbl_tools.setContentsMargins(12, 8, 0, 6)
        sl.addWidget(self.lbl_tools)
        self.tools_box = QVBoxLayout()
        self.tools_box.setSpacing(2)
        sl.addLayout(self.tools_box)
        self.nav_empty = _label("", "faint")
        self.nav_empty.setContentsMargins(12, 4, 0, 0)
        sl.addWidget(self.nav_empty)
        sl.addStretch(1)
        self.lbl_toolkit = _label("", "sideSection")
        self.lbl_toolkit.setContentsMargins(12, 8, 0, 6)
        sl.addWidget(self.lbl_toolkit)
        for key, icon in (("store", "store"), ("settings", "settings")):
            btn = NavButton(icon, "")
            btn.clicked.connect(lambda _=False, k=key: self.go(k))
            sl.addWidget(btn)
            self.nav[key] = btn
        sl.addSpacing(10)
        self.ver_btn = QPushButton(f"wxwx toolkit  {__version__}")
        self.ver_btn.setObjectName("verLink")
        self.ver_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ver_btn.clicked.connect(lambda: self.check_updates(manual=True))
        vrow = QHBoxLayout()
        vrow.setContentsMargins(7, 0, 0, 0)
        vrow.addWidget(self.ver_btn)
        vrow.addStretch()
        sl.addLayout(vrow)
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self.store_page = StorePage(self)
        sp = self.store_page
        sp.install_clicked.connect(self.install_addon)
        sp.update_clicked.connect(self.install_addon)
        sp.remove_clicked.connect(self.remove_addon)
        sp.open_clicked.connect(self.go)
        sp.component_clicked.connect(self.install_component)
        sp.install_file_clicked.connect(self.install_from_file)
        sp.retry_clicked.connect(self.load_catalog)
        self.settings_page = SettingsPage(self)
        self.settings_page.lang_chosen.connect(self.set_lang)
        self.settings_page.option_changed.connect(self.set_option)
        self.pages["store"] = self.store_page
        self.pages["settings"] = self.settings_page
        self.stack.addWidget(self.store_page)
        self.stack.addWidget(self.settings_page)

        self.toast = Toast(central)

    # ======================================================== helpers for pages
    def tint_hex(self) -> str:
        return theme.p["tint"]

    def needs_update(self, e: CatalogEntry, m: Manifest) -> bool:
        return addons.needs_update(e, m)

    def entry_compatible(self, e: CatalogEntry) -> bool:
        return not updater.is_newer(e.min_toolkit, __version__)

    def card_models(self) -> list[CardModel]:
        out = []
        for e in self.catalog:
            out.append(CardModel(e.id, e, self.installed.get(e.id), is_new=e.id not in self.seen and e.id not in self.installed))
        known = {e.id for e in self.catalog}
        out += [CardModel(aid, None, m) for aid, m in self.installed.items() if aid not in known]
        return out

    def open_data_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    # ======================================================== navigation
    def go(self, key: str):
        if key not in self.pages:
            return
        self.current = key
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        if hasattr(page, "fade_in"):
            page.fade_in()
        for k, btn in self.nav.items():
            btn.setChecked(k == key)
            btn.update()
        QTimer.singleShot(0, lambda: self.sidebar.point_bar_at(self.nav.get(key)))
        if key == "store" and self.catalog_state == "ok":
            new = {e.id for e in self.catalog} - self.seen
            if new:
                QTimer.singleShot(1500, lambda: self._mark_seen(new))

    def _mark_seen(self, ids):
        self.seen |= set(ids)
        self.store.setValue("seen_addons", ",".join(sorted(self.seen)))
        self._update_badges()

    def _update_badges(self):
        upd = any(addons.needs_update(e, self.installed.get(e.id)) for e in self.catalog)
        new = any(e.id not in self.seen and e.id not in self.installed for e in self.catalog)
        self.nav["store"].set_dot(upd or new)
        for e in self.catalog:
            if e.id in self.nav:
                self.nav[e.id].set_dot(addons.needs_update(e, self.installed.get(e.id)))

    def _rebuild_tool_nav(self):
        for aid in list(self.nav):
            if aid not in ("store", "settings") and aid not in self.installed:
                btn = self.nav.pop(aid)
                self.tools_box.removeWidget(btn)
                btn.deleteLater()
        for aid, m in self.installed.items():
            if aid not in self.nav:
                btn = NavButton(m.icon, m.title(i18n.lang()))
                btn.clicked.connect(lambda _=False, k=aid: self.go(k))
                self.tools_box.addWidget(btn)
                self.nav[aid] = btn
            self.nav[aid].setText(m.title(i18n.lang()))
        self.nav_empty.setVisible(not self.installed)
        QTimer.singleShot(0, lambda: self.sidebar.point_bar_at(self.nav.get(self.current)))

    # ======================================================== add-on pages
    def _load_addon(self, m: Manifest):
        self._unload_addon(m.id)
        host = Host(m.id, self.toast.show_text, self)
        title = m.title(i18n.lang())
        if not m.compatible:
            widget = ErrorPage(title, t("needs_toolkit", v=m.min_toolkit))
        else:
            try:
                widget = addons.load(m, host)
            except Exception:
                widget = ErrorPage(title, traceback.format_exc())
                if self._smoke:
                    self.smoke_errors.append(traceback.format_exc())
        self.hosts[m.id] = host
        self.pages[m.id] = widget
        self.stack.addWidget(widget)
        self._rebuild_tool_nav()

    def _unload_addon(self, aid: str):
        w = self.pages.pop(aid, None)
        if w is not None:
            self.stack.removeWidget(w)
            w.deleteLater()
        h = self.hosts.pop(aid, None)
        if h is not None:
            h.deleteLater()

    # ======================================================== catalog
    def load_catalog(self):
        self.catalog_state = "loading"
        self.store_page.refresh()

        def task():
            try:
                self.bridge.catalog_loaded.emit(addons.fetch_catalog())
            except Exception as e:
                self.bridge.catalog_failed.emit(str(e))
        self.pool.submit(task)

    def _on_catalog(self, entries):
        self.catalog = entries
        self.catalog_state = "ok"
        self.store_page.refresh()
        self._update_badges()
        for e in entries:
            have = self.installed.get(e.id)
            if have and addons.needs_update(e, have) and self.option("au_addons") and self.entry_compatible(e):
                self.install_addon(e.id, quiet=True)
            elif not have and self.option("au_new") and e.latest and self.entry_compatible(e):
                self.install_addon(e.id)
        if self.current == "store":
            self.go("store")

    def _on_catalog_failed(self, err: str):
        self.catalog_state = "error"
        self.store_page.status.setToolTip(err)
        self.store_page.refresh()

    # ======================================================== install / update / remove
    def _entry(self, aid: str) -> CatalogEntry | None:
        return next((e for e in self.catalog if e.id == aid), None)

    def install_addon(self, aid: str, quiet: bool = False):
        e = self._entry(aid)
        if not e or aid in self.busy_addons:
            return
        missing = [n for n in e.needs if n in components.COMPONENTS and not components.COMPONENTS[n].available]
        self.busy_addons[aid] = (0.0, "…")
        self.store_page.refresh()

        def task():
            try:
                for cid in missing:
                    components.install(cid, lambda d, tot, c=cid: self.bridge.op_progress.emit(
                        "addon", aid, d / tot if tot else 0, f"{c} · {int(d * 100 / tot) if tot else 0}%"))
                m = addons.download_and_install(e, lambda d, tot: self.bridge.op_progress.emit(
                    "addon", aid, d / tot if tot else 0, f"{int(d * 100 / tot) if tot else 0}%"))
                self.bridge.op_done.emit("addon", aid, (m, quiet))
            except Exception as ex:
                self.bridge.op_failed.emit("addon", aid, str(ex))
        self.pool.submit(task)

    def install_component(self, cid: str):
        if cid in self.busy_components:
            return
        self.busy_components[cid] = (0.0, "…")
        self.store_page.refresh()

        def task():
            try:
                v = components.install(cid, lambda d, tot: self.bridge.op_progress.emit(
                    "comp", cid, d / tot if tot else 0, f"{int(d * 100 / tot) if tot else 0}%"))
                self.bridge.op_done.emit("comp", cid, v)
            except Exception as ex:
                self.bridge.op_failed.emit("comp", cid, str(ex))
        self.pool.submit(task)

    def _on_op_progress(self, kind: str, oid: str, frac: float, text: str):
        if kind == "addon":
            self.busy_addons[oid] = (frac, text)
            card = self.store_page.cards.get(oid)
        else:
            self.busy_components[oid] = (frac, text)
            card = self.store_page.rows.get(oid)
        if card:
            card.set_progress(frac, text)

    def _on_op_done(self, kind: str, oid: str, result):
        if kind == "addon":
            self.busy_addons.pop(oid, None)
            m, quiet = result
            was = oid in self.installed
            self.installed[oid] = m
            self._load_addon(m)
            if not quiet:
                self.toast.show_text(t("t_updated", n=m.title(i18n.lang()), v=m.version) if was
                                     else t("t_installed", n=m.title(i18n.lang())))
        else:
            self.busy_components.pop(oid, None)
            self.toast.show_text(t("t_comp", n=oid))
        self.pool.submit(self._read_component_versions)
        self.store_page.refresh()
        self._update_badges()
        self.retranslate_hosts()

    def _on_op_failed(self, kind: str, oid: str, err: str):
        (self.busy_addons if kind == "addon" else self.busy_components).pop(oid, None)
        self.toast.show_text(t("t_failed", e=err[:120]), 4500)
        self.store_page.refresh()

    def remove_addon(self, aid: str):
        m = self.installed.get(aid)
        if not m:
            return
        title = m.title(i18n.lang())
        if QMessageBox.question(self, APP_NAME, f"{t('remove')} «{title}»?") != QMessageBox.StandardButton.Yes:
            return
        self._unload_addon(aid)
        addons.uninstall(aid)
        self.installed.pop(aid, None)
        self._rebuild_tool_nav()
        if self.current == aid:
            self.go("store")
        self.store_page.refresh()
        self._update_badges()
        self.toast.show_text(t("t_removed", n=title))

    def install_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, t("choose_zip"), "", t("addon_zip"))
        if path:
            self.install_zip(path)

    def install_zip(self, path: str) -> Manifest | None:
        try:
            m = addons.install_zip(path)
        except Exception as e:
            self.toast.show_text(t("t_bad_zip", e=str(e)[:100]), 4500)
            return None
        was = m.id in self.installed
        self.installed[m.id] = m
        self._load_addon(m)
        self.store_page.refresh()
        self.toast.show_text(t("t_updated", n=m.title(i18n.lang()), v=m.version) if was
                             else t("t_installed", n=m.title(i18n.lang())))
        return m

    def _read_component_versions(self):
        self.bridge.comp_versions.emit({cid: c.version() for cid, c in components.COMPONENTS.items()})

    def _on_comp_versions(self, versions):
        self.store_page.component_versions = versions
        self.store_page.refresh()

    # ======================================================== language + theme
    def set_lang(self, lang: str):
        if lang == i18n.lang():
            return
        i18n.set_lang(lang)
        self.store.setValue("lang", lang)
        self.retranslate()
        page = self.pages.get(self.current)
        if hasattr(page, "fade_in"):
            page.fade_in()
        self.toast.show_text(t("lang_set"))

    def retranslate(self):
        self.lbl_tools.setText(t("tools"))
        self.lbl_toolkit.setText(t("toolkit"))
        self.nav_empty.setText(t("nav_empty"))
        self.nav["store"].setText(t("addons"))
        self.nav["settings"].setText(t("settings"))
        self.ver_btn.setToolTip(t("check_upd"))
        self._rebuild_tool_nav()
        self.store_page.refresh()
        self.settings_page.refresh()
        self.update_bar.retranslate()
        for w in self.pages.values():
            if isinstance(w, ErrorPage):
                w.refresh()
        self.retranslate_hosts()
        for b in self.nav.values():
            b.update()

    def retranslate_hosts(self):
        for h in self.hosts.values():
            h.lang_changed.emit(i18n.lang())

    def on_theme(self):
        snap = self.central.grab()
        center = QPointF(self.toggle.mapTo(self.central, self.toggle.rect().center()))
        theme.name = "light" if theme.dark else "dark"
        self.toggle.set_light(not theme.dark)
        self.apply_theme()
        self.store_page.refresh()
        RevealOverlay(self.central, snap, center)
        self.store.setValue("theme", theme.name)
        for h in self.hosts.values():
            h.theme_changed.emit(theme.name)

    def apply_theme(self):
        QApplication.instance().setStyleSheet(stylesheet())
        for w in self.central.findChildren(QWidget):
            w.update()
        self._style_titlebar()

    def _style_titlebar(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = ctypes.c_void_p(int(self.winId()))
            dwm = ctypes.windll.dwmapi
            dark = ctypes.c_int(1 if theme.dark else 0)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            for attr, key in ((35, "win"), (36, "text")):
                col = QColor(theme.p[key])
                ref = ctypes.c_uint(col.red() | col.green() << 8 | col.blue() << 16)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ref), ctypes.sizeof(ref))
        except Exception:
            pass

    def showEvent(self, e):
        super().showEvent(e)
        self._style_titlebar()

    # ======================================================== toolkit self-update
    def check_updates(self, manual: bool):
        if self._update_busy or self._smoke:
            return
        self._update_busy = True
        if manual:
            self.ver_btn.setText(t("upd_checking"))

        def task():
            try:
                self.bridge.update_found.emit(updater.check(__version__), manual)
            except Exception as e:
                self.bridge.update_failed.emit(str(e), manual)
        self.pool.submit(task)

    def _on_update_found(self, rel, manual: bool):
        self._update_busy = False
        self.ver_btn.setText(f"wxwx toolkit  {__version__}")
        if rel is None:
            if manual:
                self.toast.show_text(t("upd_latest"))
            return
        self.release = rel
        self.update_bar.show_release(rel.version, rel.notes, updater.is_installed() and bool(rel.asset_url))

    def _on_update_failed(self, err: str, manual: bool):
        self._update_busy = False
        self.ver_btn.setText(f"wxwx toolkit  {__version__}")
        if manual:
            self.toast.show_text(t("upd_fail"))
            self.ver_btn.setToolTip(f"{t('check_upd')}\n\n{err}")

    def install_update(self):
        rel = self.release
        if not rel:
            return
        if not updater.is_installed() or not rel.asset_url:
            QDesktopServices.openUrl(QUrl(rel.page_url))
            self.toast.show_text(t("upd_page"))
            return
        self._update_busy = True
        self.update_bar.set_downloading(0, rel.asset_size)
        last = [-1]

        def progress(done, total):
            pct = int(done * 100 / total) if total else 0
            if pct != last[0]:
                last[0] = pct
                self.bridge.update_progress.emit(done, total)

        def task():
            try:
                self.bridge.update_ready.emit(updater.download(rel, progress))
            except Exception as e:
                self.bridge.update_failed.emit(str(e), True)
                QTimer.singleShot(0, lambda: self.update_bar.show_release(rel.version, rel.notes, True))
        self.pool.submit(task)

    def _on_update_ready(self, path: str):
        self._update_busy = False
        self.update_bar.set_installing()
        self.store.setValue("geometry", self.saveGeometry())
        try:
            updater.launch_installer(path)
        except OSError as e:
            cancelled = getattr(e, "winerror", None) == 1223
            self.toast.show_text(t("upd_cancelled") if cancelled else str(e))
            self.update_bar.show_release(self.release.version, self.release.notes, True)
            return
        QTimer.singleShot(400, QApplication.quit)

    # ======================================================== smoke test (CI)
    def smoke(self, shot: str, addon_zip: str | None):
        self._smoke = shot
        root, ext = os.path.splitext(shot)
        QTimer.singleShot(120_000, lambda: QApplication.exit(3))
        steps = []

        def snap(suffix):
            return lambda: self.grab().save(root + suffix + ext)

        def wait_catalog():
            if self.catalog_state == "loading":
                QTimer.singleShot(300, wait_catalog)
            else:
                run()

        steps.append(snap(""))
        if addon_zip:
            def add():
                m = self.install_zip(addon_zip)
                if not m:
                    self.smoke_errors.append("install_zip failed")
                    return
                self.go(m.id)
            steps += [add, snap("_addon")]
        steps += [lambda: self.go("settings"), lambda: self.set_lang("en"), snap("_settings_en"),
                  lambda: self.go("store"), self.on_theme, snap("_light")]

        def run():
            if not steps:
                QApplication.exit(1 if self.smoke_errors else 0)
                return
            steps.pop(0)()
            QTimer.singleShot(1300, run)

        QTimer.singleShot(1200, wait_catalog)

    # ======================================================== window events
    def closeEvent(self, e):
        self.store.setValue("geometry", self.saveGeometry())
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(e)


def reveal_in_explorer(path: str) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
