"""Main window: header, sidebar with tools, pages (store, settings, add-ons) and all the controller logic."""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QLocale, QObject, QPointF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)
from qframelesswindow import FramelessMainWindow

from .. import APP_NAME, __version__
from pathlib import Path

from ..core import addons, components, i18n, naming, presets, updater
from ..core.addons import CatalogEntry, Manifest
from ..core.i18n import t
from ..core.paths import data_dir, install_lang
from .hints import hints
from .host import Host
from .pages import AddonSettingsPage, CardModel, ErrorPage, SettingsHub, SettingsPage, StorePage
from .shell import NavButton, Sidebar
from .store import store
from .theme import stylesheet, theme
from .titlebar import HEIGHT as HEADER_H, HeaderBar
from .update_bar import UpdateBar
from .widgets import RevealOverlay, Toast

OPTION_DEFAULTS = {"au_addons": True, "au_new": False, "au_ask": True, "hints": True}


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


class MainWindow(FramelessMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.store = store()
        theme.name = "light" if self.store.value("theme", "dark") == "light" else "dark"
        i18n.set_lang(self._first_lang())
        hints.on = self.option("hints")
        hints.install()
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
        self.catalog_checked: str | None = None
        self._catalog_manual = False
        self.pending_updates: set[str] = set()
        self._pending_timer = QTimer(self)
        self._pending_timer.setInterval(15_000)
        self._pending_timer.timeout.connect(self._retry_pending)
        self._recheck = QTimer(self)
        self._recheck.setInterval(30 * 60_000)          # look for add-on updates every 30 min
        self._recheck.timeout.connect(lambda: self.load_catalog())

        self._build()
        self.setAcceptDrops(True)
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
        self._recheck.start()
        self.pool.submit(self._read_component_versions)
        if self.option("au_ask"):
            QTimer.singleShot(2500, lambda: self.check_updates(manual=False))

    # ======================================================== settings
    def option(self, key: str) -> bool:
        v = self.store.value(f"opt/{key}")
        return OPTION_DEFAULTS[key] if v is None else str(v).lower() in ("true", "1")

    def set_option(self, key: str, on: bool) -> None:
        self.store.setValue(f"opt/{key}", on)

    def _first_lang(self) -> str:
        """Saved choice → language picked in the installer → Windows language (Russian or English)."""
        v = self.store.value("lang")
        if v in i18n.LANGS:
            return str(v)
        lang = install_lang() or ("ru" if QLocale.system().language() == QLocale.Language.Russian else "en")
        self.store.setValue("lang", lang)
        return lang

    def tr_migrated(self) -> str:
        return t("migrated")

    # ---- «Меньше подсказок»
    def set_hints(self, on: bool) -> None:
        self.set_option("hints", on)
        hints.set(on)
        self.toast.show_text(t("hints_on") if on else t("hints_off"))

    # ---- suffix of finished files
    def toolkit_suffix_values(self) -> tuple[str, str]:
        kind = str(self.store.value("file/suffix", naming.DEFAULT) or naming.DEFAULT)
        return (kind if kind in naming.KINDS else naming.DEFAULT), str(self.store.value("file/suffix_custom", "") or "")

    def toolkit_suffix(self) -> str:
        return naming.resolve(*self.toolkit_suffix_values())

    def set_toolkit_suffix(self, kind: str, custom: str) -> None:
        self.store.setValue("file/suffix", kind)
        self.store.setValue("file/suffix_custom", custom)
        for h in self.hosts.values():
            h.suffix_changed.emit(h.suffix())

    # ======================================================== layout
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        self.central = central
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # one combined title bar (drawn by us, overlays the top of the window)
        self.header = HeaderBar(self, APP_NAME)
        self.setTitleBar(self.header)
        self.toggle = self.header.toggle
        self.toggle.clicked.connect(self.on_theme)
        root.addSpacing(HEADER_H)

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
        sp.retry_clicked.connect(lambda: self.load_catalog(manual=True))
        self.settings_page = SettingsPage(self)
        self.settings_page.lang_chosen.connect(self.set_lang)
        self.settings_page.option_changed.connect(self.set_option)
        self.settings_page.folder_change.connect(self.change_folder)
        self.settings_page.hints_toggled.connect(self.set_hints)
        self.settings_page.suffix_set.connect(self.set_toolkit_suffix)
        self.settings_hub = SettingsHub(self.settings_page)
        self.pages["store"] = self.store_page
        self.pages["settings"] = self.settings_hub
        self.stack.addWidget(self.store_page)
        self.stack.addWidget(self.settings_hub)

        self.toast = Toast(central)
        self.titleBar.raise_()

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

    DEFAULT_FOLDERS = {"output": Path.home() / "Videos" / "wxwx", "downloads": Path.home() / "Downloads" / "wxwx"}

    def folder(self, kind: str = "output") -> str:
        v = self.store.value(f"folder/{kind}")
        return str(v) if v else str(self.DEFAULT_FOLDERS.get(kind, self.DEFAULT_FOLDERS["output"]))

    def change_folder(self, kind: str):
        d = QFileDialog.getExistingDirectory(self, t("choose_folder"), self.folder(kind))
        if not d:
            return
        self.store.setValue(f"folder/{kind}", os.path.normpath(d))
        self.settings_page.refresh()
        for h in self.hosts.values():
            h.folders_changed.emit(kind)

    # ---------------------------------------------------- .wtp presets
    def handle_paths(self, paths: list[str]):
        for p in paths:
            if p.lower().endswith(presets.EXT):
                self.open_wtp(p)

    def open_wtp(self, path: str) -> bool:
        try:
            data = presets.read(path)
        except presets.PresetError:
            self.toast.show_text(t("wtp_bad"))
            return False
        aid = data["addon"]
        if aid not in self.hosts or aid not in self.installed:
            self.toast.show_text(t("wtp_missing", n=data.get("addon_name") or aid), 4500)
            self.go("store")
            return False
        self.go(aid)
        self.hosts[aid].preset_received.emit(data)
        return True

    def send_files(self, aid: str, paths: list) -> bool:
        """An add-on hands files to another one (e.g. Saves → Video)."""
        if aid not in self.hosts or aid not in self.installed:
            return False
        self.go(aid)
        self.hosts[aid].files_received.emit(list(paths))
        return True

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith(presets.EXT) for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.handle_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

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
        was_current = self.current == m.id
        self._unload_addon(m.id)
        host = Host(m.id, self.toast.show_text, self.folder, self,
                    installed_fn=lambda a: a in self.installed, open_settings_fn=self.open_addon_settings,
                    toolkit_suffix_fn=self.toolkit_suffix, send_fn=self.send_files)
        title = m.title(i18n.lang())
        settings_widget = None
        if not m.compatible:
            widget = ErrorPage(title, t("needs_toolkit", v=m.min_toolkit))
        else:
            try:
                widget = addons.load(m, host)
                settings_widget = addons.load_settings(m, host)
            except Exception:
                widget = ErrorPage(title, traceback.format_exc())
                if self._smoke:
                    self.smoke_errors.append(traceback.format_exc())
        self.hosts[m.id] = host
        self.pages[m.id] = widget
        self.stack.addWidget(widget)
        if settings_widget is not None:
            page = AddonSettingsPage(m.icon, settings_widget)
            page.set_texts(title, t("addon_v", v=m.version))
            self.settings_hub.set_addon(m.id, m.icon, page)
            self._retitle_settings()
        self._rebuild_tool_nav()
        if not hints.on:
            hints.apply()
        if was_current:                       # hot update while the page was open: show the new one
            self.go(m.id)

    def _unload_addon(self, aid: str):
        w = self.pages.pop(aid, None)
        if w is not None:
            if hasattr(w, "shutdown"):
                try:
                    w.shutdown()
                except Exception:
                    traceback.print_exc()
            self.stack.removeWidget(w)
            w.deleteLater()
        if aid in self.settings_hub.pages:
            self.settings_hub.set_addon(aid, "", None)
        h = self.hosts.pop(aid, None)
        if h is not None:
            h.deleteLater()

    def addon_busy(self, aid: str) -> bool:
        w = self.pages.get(aid)
        try:
            return bool(w is not None and hasattr(w, "is_busy") and w.is_busy())
        except Exception:
            return False

    def _retry_pending(self):
        for aid in list(self.pending_updates):
            if not self.addon_busy(aid):
                self.pending_updates.discard(aid)
                self.install_addon(aid, quiet=True)
        if not self.pending_updates:
            self._pending_timer.stop()

    def open_addon_settings(self, aid: str):
        self.go("settings")
        self.settings_hub.open(aid)

    def _retitle_settings(self):
        titles = {"general": t("s_general")}
        titles.update({aid: m.title(i18n.lang()) for aid, m in self.installed.items()})
        self.settings_hub.set_titles(titles)
        for aid, page in self.settings_hub.pages.items():
            if isinstance(page, AddonSettingsPage) and aid in self.installed:
                page.set_texts(self.installed[aid].title(i18n.lang()), t("addon_v", v=self.installed[aid].version))

    # ======================================================== catalog
    def load_catalog(self, manual: bool = False):
        if self.catalog_state == "loading" and self.catalog:
            return
        self._catalog_manual = manual
        self.catalog_state = "loading"
        self.store_page.refresh()

        def task():
            try:
                self.bridge.catalog_loaded.emit(addons.fetch_catalog())
            except Exception as e:
                self.bridge.catalog_failed.emit(str(e))
        self.pool.submit(task)

    def _on_catalog(self, entries):
        from datetime import datetime
        self.catalog = entries
        self.catalog_state = "ok"
        self.catalog_checked = datetime.now().strftime("%H:%M")
        if self._catalog_manual:
            n = sum(1 for e in entries if addons.needs_update(e, self.installed.get(e.id)))
            self.toast.show_text(t("found_upd", n=n) if n else t("all_fresh"))
            self._catalog_manual = False
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
        if self._catalog_manual:
            self.toast.show_text(t("catalog_error"), 4000)
            self._catalog_manual = False
        self.store_page.status.setToolTip(err)
        self.store_page.refresh()

    # ======================================================== install / update / remove
    def _entry(self, aid: str) -> CatalogEntry | None:
        return next((e for e in self.catalog if e.id == aid), None)

    def install_addon(self, aid: str, quiet: bool = False):
        e = self._entry(aid)
        if not e or aid in self.busy_addons:
            return
        if self.addon_busy(aid):
            title = self.installed[aid].title(i18n.lang()) if aid in self.installed else aid
            if quiet:                          # never kill a running job for a silent update
                if aid not in self.pending_updates:
                    self.pending_updates.add(aid)
                    self._pending_timer.start()
                    self.toast.show_text(t("upd_postponed", n=title), 4000)
                return
            if QMessageBox.question(self, APP_NAME, t("busy_update", n=title)) != QMessageBox.StandardButton.Yes:
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
        self.settings_hub.h1.setText(t("settings"))
        self.settings_hub.sub.setText(t("settings_sub"))
        self.settings_hub.sep.setText(t("s_addons"))
        self._retitle_settings()
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
        snap = self.grab()
        center = QPointF(self.toggle.mapTo(self, self.toggle.rect().center()))
        theme.name = "light" if theme.dark else "dark"
        self.toggle.set_light(not theme.dark)
        self.apply_theme()
        self.store_page.refresh()
        RevealOverlay(self, snap, center)
        self.store.setValue("theme", theme.name)
        for h in self.hosts.values():
            h.theme_changed.emit(theme.name)

    def apply_theme(self):
        QApplication.instance().setStyleSheet(stylesheet())
        self.header.apply_theme()
        for w in self.findChildren(QWidget):
            w.update()

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
    def smoke(self, shot: str, addon_zips: list[str] | None = None, media: str | None = None):
        """Clicks through the UI and saves screenshots: <shot>, <shot>_addon_<id>, …  Exit code 1 on errors."""
        self._smoke = shot
        addon_zips = list(addon_zips or [])
        root, ext = os.path.splitext(shot)
        QTimer.singleShot(180_000, lambda: QApplication.exit(3))
        steps = []
        loaded: list[str] = []

        def snap(suffix):
            return lambda: self.grab().save(root + suffix + ext)

        def wait_catalog():
            if self.catalog_state == "loading":
                QTimer.singleShot(300, wait_catalog)
            else:
                run()

        frames: list = []
        if media:
            def media_start():
                from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
                self._mp, self._sink = QMediaPlayer(self), QVideoSink(self)
                self._mp.setVideoSink(self._sink)
                self._sink.videoFrameChanged.connect(lambda f: frames.append((f.width(), f.height())))
                self._mp.errorOccurred.connect(lambda _e, msg: self.smoke_errors.append(f"media: {msg}"))
                self._mp.setSource(QUrl.fromLocalFile(media))
                self._mp.play()
            steps.append(media_start)

        steps.append(snap(""))
        for z in addon_zips:
            def add(z=z):
                m = self.install_zip(z)
                if not m:
                    self.smoke_errors.append(f"install_zip failed: {z}")
                    return
                loaded.append(m.id)
                self.go(m.id)
                if isinstance(self.pages.get(m.id), ErrorPage):
                    self.smoke_errors.append(f"{m.id} shows the error page")
            steps += [add, lambda: snap(f"_addon_{loaded[-1]}")() if loaded else None]
        if addon_zips:
            def wtp():
                import tempfile
                aid = loaded[-1]
                f = Path(tempfile.gettempdir()) / "smoke-preset.wtp"
                presets.write(f, presets.make(aid, "Smoke preset", {"x": 1}, aid, "1.0.0", "ci"))
                if not self.open_wtp(str(f)):
                    self.smoke_errors.append("open_wtp failed")

            def hot_update():                     # reinstall the first add-on while its page is open
                aid = loaded[0]
                self.go(aid)
                before = self.pages.get(aid)
                m = self.install_zip(addon_zips[0])
                after = self.pages.get(aid)
                if not m or after is None or after is before or isinstance(after, ErrorPage) or self.current != aid:
                    self.smoke_errors.append("hot update did not reload the add-on page")
                else:
                    print("hot update OK:", aid)
            steps += [wtp, snap("_wtp"), hot_update, snap("_hot_update")]
        steps += [lambda: self.go("settings"), lambda: self.set_lang("en"), snap("_settings_en")]
        for z in addon_zips:
            def tab(i=addon_zips.index(z)):
                aid = loaded[i] if i < len(loaded) else None
                if aid and aid in self.settings_hub.pages:
                    self.open_addon_settings(aid)
            steps += [tab, (lambda i=addon_zips.index(z): snap(f"_settings_{loaded[i]}")()
                            if i < len(loaded) and loaded[i] in self.settings_hub.pages else None)]
        def nohints():                        # 1.3: «Меньше подсказок» + a broken custom suffix
            self.set_lang("ru")
            self.go("settings")
            self.settings_hub.open("general")
            self.set_hints(False)
            self.set_toolkit_suffix("custom", "sm*")
            self.settings_page.refresh()
            if self.toolkit_suffix() != "_wx":
                self.smoke_errors.append(f"broken custom suffix must fall back to _wx, got {self.toolkit_suffix()}")

        def hints_back():
            hidden = [w for w in QApplication.allWidgets() if w.property("hint") and w.isVisible()]
            if hidden:
                self.smoke_errors.append(f"{len(hidden)} hint widgets still visible in «less hints» mode")
            self.set_toolkit_suffix("trim", "")
            self.settings_page.refresh()
            for aid, h in self.hosts.items():
                if h.suffix() != "_trim" and not h.get("suffix_own", False):
                    self.smoke_errors.append(f"{aid}: host.suffix() = {h.suffix()}, expected _trim")
        steps += [nohints, snap("_settings_nohints"), hints_back, snap("_settings_trim")]
        for z in addon_zips:
            def tab2(i=addon_zips.index(z)):
                aid = loaded[i] if i < len(loaded) else None
                if aid and aid in self.settings_hub.pages:
                    self.open_addon_settings(aid)
            steps += [tab2, (lambda i=addon_zips.index(z): snap(f"_settings_{loaded[i]}_nohints")()
                             if i < len(loaded) and loaded[i] in self.settings_hub.pages else None)]
        steps += [lambda: self.set_hints(True), lambda: self.set_toolkit_suffix("wx", "")]
        steps += [lambda: self.go("store"), lambda: self.load_catalog(manual=True), self.on_theme, snap("_light")]
        if addon_zips:
            steps += [lambda: self.go(loaded[0]), snap("_addon_en_light")]
        if media:
            def media_verify():
                print("media frames:", len(frames), frames[:1])
                if not frames:
                    self.smoke_errors.append("QtMultimedia: no video frame decoded")
                self._mp.stop()
            steps.append(media_verify)

        def run():
            if not steps:
                for e in self.smoke_errors:
                    print("SMOKE ERROR:", e)
                QApplication.exit(1 if self.smoke_errors else 0)
                return
            try:
                steps.pop(0)()
            except Exception:
                self.smoke_errors.append(traceback.format_exc())
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
