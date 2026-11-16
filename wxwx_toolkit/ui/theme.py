"""Colors for the black/white themes and the Qt stylesheet built from them.
Add-ons get the same stylesheet automatically, so objectNames below (h1, sub, accent, chip…)
can be used inside add-ons too."""
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
        cy="rgba(255,255,255,13)", cyt="rgba(184,168,226,82)", scan="rgba(255,255,255,3)",
    ),
    "light": dict(
        page="#e8e5df", win="#f7f5f1", panel="#fbfaf7", panel2="#eeebe5", panel3="#e1ddd6", seg_ind="#ffffff",
        line="rgba(20,18,24,19)", line2="rgba(20,18,24,36)",
        text="#17161a", muted="#76737d", faint="#aaa7af",
        ink="#151418", on_ink="#f7f5f1", tint="#8572bd", glow="rgba(133,114,189,56)",
        cy="rgba(20,18,24,14)", cyt="rgba(133,114,189,77)", scan="rgba(20,18,24,3)",
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
QMainWindow, #central, #page { background: $win; }
QWidget { color: $text; }
#header { background: $win; border-bottom: 1px solid $line; }
#appTitle { font-size: 11.5pt; font-weight: 800; }
#appBy { color: $faint; font-size: 7.4pt; font-weight: 600; }
#h1 { font-size: 16pt; font-weight: 800; }
#sub { color: $muted; font-size: 9.6pt; }
#section { color: $muted; font-size: 7.6pt; font-weight: 700; }
#sideSection { color: $faint; font-size: 7.6pt; font-weight: 700; }
#tabSep { color: $faint; font-size: 7.2pt; font-weight: 700; padding: 0 6px 4px 14px; border-left: 1px solid $line2; margin: 10px 2px 12px 8px; }
#faint { color: $faint; font-size: 8.5pt; }
#empty { color: $faint; font-size: 10pt; }

QPushButton#ghost, QPushButton#link, QToolButton#link {
    background: transparent; border: none; color: $muted; font-weight: 600;
    padding: 6px 11px; border-radius: 8px; font-size: 9.2pt;
}
QPushButton#link, QToolButton#link { padding: 3px 7px; font-size: 8.6pt; }
QPushButton#ghost:hover, QPushButton#link:hover, QToolButton#link:hover { background: $panel2; color: $text; }
QPushButton#verLink { background: transparent; border: none; color: $faint; font-size: 7.8pt; padding: 2px 5px;
    border-radius: 6px; text-align: left; }
QPushButton#verLink:hover { background: $panel2; color: $text; }
QPushButton#accent {
    background: $ink; color: $on_ink; border: none; border-radius: 10px;
    padding: 8px 18px; font-weight: 800; font-size: 9.4pt;
}
QPushButton#accent:hover { background: $tint; }
QPushButton#accent:disabled { background: $panel3; color: $faint; }
QPushButton#soft {
    background: $panel2; color: $text; border: none; border-radius: 10px;
    padding: 8px 16px; font-weight: 700; font-size: 9.2pt;
}
QPushButton#soft:hover { background: $panel3; }

#card { background: $panel; border: 1px solid $line; border-radius: 16px; }
#card:hover { border: 1px solid $line2; }
#cardTitle { font-size: 11.3pt; font-weight: 800; }
#cardSub { color: $faint; font-size: 8.4pt; font-weight: 600; }
#cardDesc { color: $muted; font-size: 9.2pt; }
#cardInfo { color: $faint; font-size: 8.6pt; }
#pill { background: $panel2; color: $muted; border-radius: 7px; padding: 3px 8px; font-size: 8.2pt; font-weight: 700; }
#row { background: $panel; border: 1px solid $line; border-radius: 14px; }
#rowTitle { font-size: 10pt; font-weight: 700; }
#rowSub { color: $muted; font-size: 8.6pt; }
#rowStatus { color: $tint; font-size: 9pt; font-weight: 700; }
#rowStatusFaint { color: $faint; font-size: 9pt; font-weight: 600; }
#ci { background: $panel2; color: $muted; border-radius: 11px; font-family: "$mono"; font-size: 8.4pt; font-weight: 700; }

#updateBar { background: $panel; border-bottom: 1px solid $line; }
#updateText { font-size: 9.6pt; }

QPlainTextEdit#error {
    background: $panel; border: 1px solid $line; border-radius: 10px; color: $text;
    font-family: "$mono"; font-size: 8.4pt; padding: 8px; selection-background-color: $tint;
}

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
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
""")


def stylesheet() -> str:
    return QSS.substitute(theme.p, font=FONT_FAMILY, mono=MONO_FAMILY)
