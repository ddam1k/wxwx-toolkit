"""Store (add-ons + shared components), settings and the add-on error page."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..core.addons import CatalogEntry, Manifest
from ..core.components import COMPONENTS
from ..core.i18n import fmt_size, lang, t
from ..core.paths import data_dir
from .shell import IconTile, LangCard, SwitchRow
from .widgets import FlowLayout, ProgressButton, animate


def label(text: str, name: str, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, name: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class Page(QWidget):
    """Scrollable page with a padded column."""

    def __init__(self, max_width: int | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.col = QVBoxLayout(body)
        self.col.setContentsMargins(28, 24, 28, 24)
        self.col.setSpacing(0)
        if max_width:
            body.setMaximumWidth(max_width + 56)
        scroll.setWidget(body)
        outer.addWidget(scroll)

    def fade_in(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        animate(self, 0, 1, 260, eff.setOpacity, on_done=lambda: self.setGraphicsEffect(None))


# ---------------------------------------------------------------- store
@dataclass
class CardModel:
    id: str
    entry: CatalogEntry | None
    manifest: Manifest | None
    is_new: bool = False

    def title(self) -> str:
        src = self.manifest or self.entry
        return src.title(lang()) if src else self.id

    def desc(self) -> str:
        src = self.manifest or self.entry
        return src.desc(lang()) if src else ""

    @property
    def icon(self) -> str:
        return (self.manifest or self.entry).icon

    @property
    def needs(self) -> list:
        return (self.entry or self.manifest).needs


class AddonCard(QFrame):
    def __init__(self, model: CardModel, store: "StorePage"):
        super().__init__()
        self.model = model
        self.setObjectName("card")
        self.setFixedWidth(300)
        self.setMinimumHeight(206)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(13)
        top.addWidget(IconTile(model.icon))
        tv = QVBoxLayout()
        tv.setSpacing(1)
        tv.addStretch()
        tv.addWidget(label(model.title(), "cardTitle"))
        m, e = model.manifest, model.entry
        size = fmt_size(e.asset_size / 1048576) if e and e.asset_size else ""
        sub = " · ".join(x for x in (t("addon"), size) if x)
        if model.is_new:
            sub += f" · <b style='color:{store.tint()}'>{t('new')}</b>"
        s = label(sub, "cardSub")
        s.setTextFormat(Qt.TextFormat.RichText)
        tv.addWidget(s)
        tv.addStretch()
        top.addLayout(tv, 1)
        lay.addLayout(top)
        lay.addWidget(label(model.desc(), "cardDesc", wrap=True))
        if model.needs:
            row = QHBoxLayout()
            row.setSpacing(6)
            for n in model.needs:
                c = COMPONENTS.get(n)
                ok = bool(c and c.available)
                txt = f"✓ {n}" if ok else f"↓ {n} · {c.size_mb} {t('mb')}" if c else n
                row.addWidget(label(txt, "pill"))
            row.addStretch()
            lay.addLayout(row)
        lay.addStretch()

        bottom = QHBoxLayout()
        self.btn = None
        if m and e and e.latest and store.needs_update(e, m):
            info, act, sig = f"{m.version} → <b style='color:{store.tint()}'>{e.latest}</b>", t("update"), store.update_clicked
        elif m:
            info = t("installed_v", v=m.version) if e else t("local")
            act, sig = None, None
        elif e and e.latest and not store.compatible(e):
            info, act, sig = t("needs_toolkit", v=e.min_toolkit), None, None
        elif e and e.latest:
            info, act, sig = f"v{e.latest}", t("install"), store.install_clicked
        else:
            info, act, sig = "—", None, None
        il = label(info, "cardInfo")
        il.setTextFormat(Qt.TextFormat.RichText)
        bottom.addWidget(il)
        bottom.addStretch()
        if m:
            rm = button(t("remove"), "link")
            rm.clicked.connect(lambda: store.remove_clicked.emit(model.id))
            bottom.addWidget(rm)
        if act:
            self.btn = ProgressButton(act, height=38, font_size=9.4, radius=10)
            self.btn.clicked.connect(lambda: sig.emit(model.id))
            bottom.addWidget(self.btn)
        elif m:
            op = button(t("open"), "soft")
            op.clicked.connect(lambda: store.open_clicked.emit(model.id))
            bottom.addWidget(op)
        lay.addLayout(bottom)

    def set_progress(self, frac: float, text: str) -> None:
        if self.btn:
            self.btn.setEnabled(False)
            self.btn.set_progress(frac)
            self.btn.setText(text)


class ComponentRow(QFrame):
    def __init__(self, cid: str, users: list[str], store: "StorePage"):
        super().__init__()
        self.setObjectName("row")
        c = COMPONENTS[cid]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)
        ci = label(cid[:2], "ci")
        ci.setFixedSize(40, 40)
        ci.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ci)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label(c.title, "rowTitle"))
        tv.addWidget(label(f"{t('needed_for')}: {', '.join(users) if users else t('nobody')}", "rowSub"))
        lay.addLayout(tv, 1)
        self.btn = None
        ver = store.component_versions.get(cid)
        if c.available:
            lay.addWidget(label(t("comp_ok", v=ver or "?"), "rowStatus"))
        else:
            lay.addWidget(label(t("comp_missing", mb=c.size_mb), "rowStatusFaint"))
            self.btn = ProgressButton(t("download"), height=34, font_size=9, radius=9)
            self.btn.clicked.connect(lambda: store.component_clicked.emit(cid))
            lay.addWidget(self.btn)

    def set_progress(self, frac: float, text: str) -> None:
        if self.btn:
            self.btn.setEnabled(False)
            self.btn.set_progress(frac)
            self.btn.setText(text)


class StorePage(Page):
    install_clicked = Signal(str)
    update_clicked = Signal(str)
    remove_clicked = Signal(str)
    open_clicked = Signal(str)
    component_clicked = Signal(str)
    install_file_clicked = Signal()
    retry_clicked = Signal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx                      # MainWindow: catalog, installed, helpers
        self.cards: dict[str, AddonCard] = {}
        self.rows: dict[str, ComponentRow] = {}
        self.component_versions: dict[str, str | None] = {}
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(3)
        self.h1 = label("", "h1")
        self.sub = label("", "sub")
        tv.addWidget(self.h1)
        tv.addWidget(self.sub)
        head.addLayout(tv, 1)
        self.from_file = button("", "ghost")
        self.from_file.clicked.connect(self.install_file_clicked)
        head.addWidget(self.from_file, 0, Qt.AlignmentFlag.AlignTop)
        self.col.addLayout(head)
        self.col.addSpacing(26)
        self.sec_avail = label("", "section")
        self.col.addWidget(self.sec_avail)
        self.col.addSpacing(12)
        self.status = label("", "empty", wrap=True)
        self.retry = button("", "soft")
        self.retry.clicked.connect(self.retry_clicked)
        srow = QHBoxLayout()
        srow.addWidget(self.status, 1)
        srow.addWidget(self.retry)
        self.col.addLayout(srow)
        self.cards_box = QWidget()
        self.flow = FlowLayout(self.cards_box, 12)
        self.col.addWidget(self.cards_box)
        self.col.addSpacing(26)
        self.sec_comp = label("", "section")
        self.col.addWidget(self.sec_comp)
        self.col.addSpacing(12)
        self.comp_box = QVBoxLayout()
        self.comp_box.setSpacing(8)
        self.col.addLayout(self.comp_box)
        self.col.addStretch()

    # helpers used by cards
    def tint(self) -> str:
        return self.ctx.tint_hex()

    def needs_update(self, e, m) -> bool:
        return self.ctx.needs_update(e, m)

    def compatible(self, e) -> bool:
        return self.ctx.entry_compatible(e)

    def refresh(self) -> None:
        self.h1.setText(t("addons"))
        self.sub.setText(t("store_sub"))
        self.from_file.setText(t("from_file"))
        self.sec_avail.setText(t("available"))
        self.sec_comp.setText(t("shared"))
        self.retry.setText(t("retry"))
        models = self.ctx.card_models()
        state = self.ctx.catalog_state            # loading | ok | error
        self.status.setVisible(state != "ok" or not models)
        self.retry.setVisible(state == "error")
        self.status.setText(t("catalog_loading") if state == "loading" else
                            t("catalog_error") if state == "error" else t("catalog_empty"))
        self.flow.clear()
        self.cards = {}
        for m in models:
            card = AddonCard(m, self)
            self.flow.addWidget(card)
            self.cards[m.id] = card
        self.cards_box.setVisible(bool(models))
        while self.comp_box.count():
            w = self.comp_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.rows = {}
        for cid in COMPONENTS:
            users = [m.title() for m in models if cid in m.needs]
            row = ComponentRow(cid, users, self)
            self.comp_box.addWidget(row)
            self.rows[cid] = row
        for cid, (frac, text) in self.ctx.busy_components.items():
            if cid in self.rows:
                self.rows[cid].set_progress(frac, text)
        for aid, (frac, text) in self.ctx.busy_addons.items():
            if aid in self.cards:
                self.cards[aid].set_progress(frac, text)


# ---------------------------------------------------------------- settings
class SettingsPage(Page):
    lang_chosen = Signal(str)
    option_changed = Signal(str, bool)

    OPTIONS = ("au_addons", "au_new", "au_ask")

    def __init__(self, ctx):
        super().__init__(max_width=640)
        self.ctx = ctx
        self.h1 = label("", "h1")
        self.sub = label("", "sub")
        self.col.addWidget(self.h1)
        self.col.addSpacing(3)
        self.col.addWidget(self.sub)
        self.sec_lang = self._section()
        row = QHBoxLayout()
        row.setSpacing(8)
        self.lang_cards = {"ru": LangCard("RU", "Русский"), "en": LangCard("EN", "English")}
        for code, card in self.lang_cards.items():
            card.clicked.connect(lambda _=False, c=code: self.lang_chosen.emit(c))
            row.addWidget(card)
        self.col.addLayout(row)
        self.sec_upd = self._section()
        self.rows = {}
        for key in self.OPTIONS:
            r = SwitchRow()
            r.toggled.connect(lambda on, k=key: self.option_changed.emit(k, on))
            self.col.addWidget(r)
            self.rows[key] = r
        self.sec_data = self._section()
        data_row = QFrame()
        data_row.setObjectName("row")
        dl = QHBoxLayout(data_row)
        dl.setContentsMargins(14, 12, 14, 12)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        self.data_title = label("", "rowTitle")
        tv.addWidget(self.data_title)
        path = label(str(data_dir()), "rowSub")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tv.addWidget(path)
        dl.addLayout(tv, 1)
        self.open_btn = button("", "soft")
        self.open_btn.clicked.connect(self.ctx.open_data_folder)
        dl.addWidget(self.open_btn)
        self.col.addWidget(data_row)
        self.col.addStretch()

    def _section(self) -> QLabel:
        self.col.addSpacing(26)
        lb = label("", "section")
        self.col.addWidget(lb)
        self.col.addSpacing(12)
        return lb

    def refresh(self) -> None:
        self.h1.setText(t("settings"))
        self.sub.setText(t("settings_sub"))
        self.sec_lang.setText(t("language"))
        self.sec_upd.setText(t("updates"))
        self.sec_data.setText(t("data"))
        self.data_title.setText(t("data_folder"))
        self.open_btn.setText(t("open_folder"))
        self.lang_cards["ru"].sub = t("ru_sub")
        self.lang_cards["en"].sub = t("en_sub")
        for code, card in self.lang_cards.items():
            card.setChecked(code == lang())
            card.update()
        for key, r in self.rows.items():
            r.set_texts(t(key), t(key + "_s"))
            r.switch.set_now(self.ctx.option(key))


# ---------------------------------------------------------------- add-on failed to load
class ErrorPage(Page):
    def __init__(self, title: str, error: str):
        super().__init__(max_width=760)
        self.title = label("", "h1")
        self.sub = label("", "sub")
        self.col.addWidget(self.title)
        self.col.addSpacing(3)
        self.col.addWidget(self.sub)
        self.col.addSpacing(16)
        box = QPlainTextEdit(error)
        box.setObjectName("error")
        box.setReadOnly(True)
        box.setMinimumHeight(260)
        self.col.addWidget(box)
        self.col.addSpacing(10)
        copy = button("", "soft")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(error))
        self.copy = copy
        row = QHBoxLayout()
        row.addWidget(copy)
        row.addStretch()
        self.col.addLayout(row)
        self.col.addStretch()
        self.addon_title = title
        self.refresh()

    def refresh(self) -> None:
        self.title.setText(t("addon_failed", n=self.addon_title))
        self.sub.setText(t("addon_failed_sub"))
        self.copy.setText("Copy" if lang() == "en" else "Скопировать")
