"""Colors for the black/white themes and the Qt stylesheet built from them (wxwx kit).

An add-on adds its own rules with  add_qss(r"""#myThing { color: $muted; }""")  — same $palette
variables as the base stylesheet. set_font() swaps the UI font (the toolkit passes its own)."""
from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QFont

HAIR_BLACK = "#121214"
HAIR_WHITE = "#f1efea"

PALETTES = {
    "dark": dict(
        page="#09090b", win="#111113", panel="#141417", panel2="#1b1b1f", panel3="#26262c", seg_ind="#2c2c33",
        line="rgba(255,255,255,17)", line2="rgba(255,255,255,31)",
        text="#ecebef", muted="#8d8b95", faint="#5b5a63",
        ink="#f1efea", on_ink="#111113", tint="#b8a8e2", glow="rgba(184,168,226,72)",
    ),
    "light": dict(
        page="#e8e5df", win="#f7f5f1", panel="#fbfaf7", panel2="#eeebe5", panel3="#e1ddd6", seg_ind="#ffffff",
        line="rgba(20,18,24,19)", line2="rgba(20,18,24,36)",
        text="#17161a", muted="#76737d", faint="#aaa7af",
        ink="#151418", on_ink="#f7f5f1", tint="#8572bd", glow="rgba(133,114,189,56)",
    ),
}

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Cascadia Mono"


def _to_qcolor(v: str) -> QColor:
    if v.startswith("rgba("):
        r, g, b, a = (int(x) for x in v[5:-1].split(","))
        return QColor(r, g, b, a)
    return QColor(v)


class Theme:
    def __init__(self) -> None:
        self.name = "dark"

    @property
    def p(self) -> dict:
        return PALETTES[self.name]

    @property
    def dark(self) -> bool:
        return self.name == "dark"

    def c(self, key: str, alpha: int | None = None) -> QColor:
        col = QColor(_to_qcolor(self.p[key]))
        if alpha is not None:
            col.setAlpha(alpha)
        return col


theme = Theme()


def font(size: float, weight: QFont.Weight = QFont.Weight.Normal, mono: bool = False) -> QFont:
    f = QFont(MONO_FAMILY if mono else FONT_FAMILY)
    f.setPointSizeF(size)
    f.setWeight(weight)
    if mono:
        f.setStyleHint(QFont.StyleHint.Monospace)
    return f


QSS = Template(r"""
* { font-family: "$font"; }
QMainWindow, #central { background: $win; }
QWidget { color: $text; }
#header { background: $win; border-bottom: 1px solid $line; }
#appTitle { font-size: 11.5pt; font-weight: 800; }
#appSub, #faint { color: $faint; font-size: 8.5pt; }
#seam { background: $line2; }
#settings, #footer, #settingsBody { background: $panel; }
#footer { border-top: 1px solid $line; }
#h2 { font-size: 15pt; font-weight: 800; }
#muted { color: $muted; font-size: 9pt; }
#section { color: $muted; font-size: 7.5pt; font-weight: 700; }
#hint { color: $faint; font-size: 8.3pt; font-weight: 600; }
#rowLabel { color: $muted; font-size: 9.3pt; font-weight: 600; }
#rowValue { font-size: 9.8pt; font-weight: 800; }
#scaleLabel { color: $faint; font-size: 7.8pt; }
#totalLabel { color: $muted; font-size: 9.3pt; font-weight: 600; }
#totalValue { font-size: 13.5pt; font-weight: 800; }
#empty { color: $faint; font-size: 10pt; }

QPushButton#ghost, QPushButton#link, QToolButton#link {
    background: transparent; border: none; color: $muted; font-weight: 600;
    padding: 6px 11px; border-radius: 8px; font-size: 9.2pt;
}
QPushButton#link, QToolButton#link { padding: 3px 7px; font-size: 8.6pt; }
QToolButton#link::menu-indicator { subcontrol-position: right center; subcontrol-origin: padding; left: -2px; }
QToolButton#link { padding-right: 16px; }
QPushButton#ghost:hover, QPushButton#link:hover, QToolButton#link:hover { background: $panel2; color: $text; }
QPushButton#ghost:disabled { color: $faint; }

#updateBar { background: $panel; border-bottom: 1px solid $line; }
#updateText { font-size: 9.6pt; }
QPushButton#accent {
    background: $ink; color: $on_ink; border: none; border-radius: 9px;
    padding: 7px 16px; font-weight: 800; font-size: 9.2pt;
}
QPushButton#accent:hover { background: $tint; }
QPushButton#accent:disabled { background: $panel3; color: $faint; }
#block { border-bottom: 1px solid $line; }
#secTitle { font-size: 9.6pt; font-weight: 800; color: $text; }
QPushButton#secAction { background: transparent; border: none; color: $muted; font-weight: 700; font-size: 8.9pt;
    padding: 4px 8px; border-radius: 7px; }
QPushButton#secAction:hover { background: $panel2; color: $text; }
#note { color: $faint; font-size: 8.4pt; }
#rowTitle { font-size: 9.8pt; font-weight: 700; }
#rowSub { color: $faint; font-size: 8.3pt; }
#gpuText { color: $muted; font-size: 8.9pt; font-weight: 600; }
#destBox { background: $panel2; border: 1px solid $line; border-radius: 12px; }
#destPath { font-family: "$mono"; font-size: 8.9pt; font-weight: 700; color: $text; }
#destSub { color: $faint; font-size: 8.2pt; }
QPushButton#destBtn { background: transparent; border: none; color: $muted; font-weight: 700; font-size: 8.9pt;
    padding: 5px 9px; border-radius: 8px; }
QPushButton#destBtn:hover { background: $panel3; color: $text; }
#saveTo { color: $muted; font-size: 8.9pt; }
#saveToPath { color: $text; font-size: 8.9pt; font-weight: 700; }
#panelRight { background: $panel; }
#panelFooter { background: $panel; border-top: 1px solid $line; }
#item { background: $panel; border: 1px solid $line; border-radius: 14px; }
#item:hover { border: 1px solid $line2; }
#itemName { font-size: 10pt; font-weight: 700; }
#itemMeta { color: $muted; font-size: 8.5pt; }
#status { color: $faint; font-size: 8.2pt; }
#status[state="work"] { color: $tint; }
#status[state="done"] { color: $muted; }
#status[state="error"] { color: #d0606f; }
#estLbl { color: $faint; font-size: 7.6pt; font-weight: 600; }
#estSize { font-size: 11.3pt; font-weight: 800; }
#estPct { color: $tint; font-size: 8.2pt; font-weight: 700; }
QToolButton#rm { background: transparent; border: none; color: $faint; border-radius: 8px; font-size: 10pt; }
QToolButton#rm:hover { background: $panel2; color: $text; }

QPlainTextEdit#cmd {
    background: $win; border: 1px solid $line; border-radius: 10px; color: $text;
    font-family: "$mono"; font-size: 8.3pt; padding: 6px; selection-background-color: $tint;
}

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: $panel3; border-radius: 3px; min-width: 30px; }
QScrollBar::handle:vertical { background: $panel3; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $faint; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { height: 0; background: none; }

QMenu { background: $panel; border: 1px solid $line2; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; color: $text; }
QMenu::item:selected { background: $panel2; }
QToolTip { background: $ink; color: $on_ink; border: none; padding: 5px 8px; border-radius: 6px; }

QDialog, QMessageBox, QInputDialog { background: $panel; }
QLineEdit { background: $win; border: 1px solid $line2; border-radius: 8px; padding: 6px 8px; color: $text; }
QDialog QPushButton, QMessageBox QPushButton {
    background: $panel2; border: 1px solid $line2; border-radius: 8px; padding: 6px 16px; color: $text; min-width: 70px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover { border-color: $muted; }
#h1 { font-size: 16pt; font-weight: 800; }
#h3 { font-size: 13pt; font-weight: 800; }
#sub { color: $muted; font-size: 9.4pt; }
#monoPath { font-family: "$mono"; font-size: 8.8pt; font-weight: 700; color: $text; }
#faintBig { color: $faint; font-size: 12pt; }
#row { background: $panel; border: 1px solid $line; border-radius: 14px; }
""")


_EXTRA: list[Template] = []


def add_qss(rules: str) -> None:
    """Extra rules for this add-on, appended to the base stylesheet."""
    _EXTRA.append(Template(rules))


def set_font(family: str) -> None:
    global FONT_FAMILY
    if family:
        FONT_FAMILY = family


def stylesheet() -> str:
    v = dict(theme.p, font=FONT_FAMILY, mono=MONO_FAMILY)
    return QSS.substitute(v) + "".join(t.substitute(v) for t in _EXTRA)
