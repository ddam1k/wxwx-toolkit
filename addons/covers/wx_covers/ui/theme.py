"""Colors and the stylesheet come from the shared wxwx kit; below are the rules only Covers needs."""
from ..kit.theme import *  # noqa: F401,F403
from ..kit.theme import add_qss, set_font, stylesheet  # noqa: F401

add_qss(r"""
#coversPage, #coversSettings { background: transparent; }
#listHead { font-size: 9pt; font-weight: 700; color: $muted; }
#idleHint { color: $muted; font-size: 9.4pt; font-weight: 600; }
#idleTitle { color: $text; font-size: 11.4pt; font-weight: 800; }
#cvHint { color: $muted; font-size: 8.6pt; }
QPushButton#danger { background: transparent; border: none; color: #e59a86; font-size: 9pt; font-weight: 700;
    padding: 2px 0; text-align: left; }
QPushButton#danger:hover { color: #f0b2a0; }
#fldLbl { font-size: 8pt; font-weight: 800; color: $muted; }
QLineEdit#tagEdit { background: $panel2; border: 1px solid $line; border-radius: 9px; padding: 6px 9px;
    font-size: 9.6pt; font-weight: 600; color: $text; }
QLineEdit#tagEdit:focus { border: 1px solid $tint; }
QLineEdit#tagEdit:disabled { color: $faint; background: transparent; }
#fnPrev { font-size: 8.8pt; color: $muted; background: $panel2; border-radius: 10px; padding: 8px 10px; }
#totalSub { font-size: 8.8pt; color: $tint; font-weight: 700; }
QPushButton#undo { background: transparent; border: none; color: $muted; font-size: 8.8pt; font-weight: 700; padding: 0; }
QPushButton#undo:hover { color: $text; }
""")
