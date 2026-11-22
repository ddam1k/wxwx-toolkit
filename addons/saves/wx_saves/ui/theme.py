"""Colors and the stylesheet come from the shared wxwx kit; below are the rules only Saves needs."""
from ..kit.theme import *  # noqa: F401,F403
from ..kit.theme import add_qss, set_font, stylesheet  # noqa: F401

add_qss(r"""
#savesPage, #savesSettings { background: transparent; }
#urlBar { background: $panel; border: 1px solid $line2; border-radius: 14px; }
#urlBar[focus="true"] { border: 1px solid $tint; }
QLineEdit#urlEdit { background: transparent; border: none; padding: 0; font-size: 10.6pt; font-weight: 600; color: $text; }
#siteTag { font-size: 8.4pt; font-weight: 800; color: $muted; padding: 0 2px; }
#clipPill { background: $panel2; border: 1px solid $line2; border-radius: 12px; }
#clipText { font-size: 9pt; font-weight: 600; color: $text; }
#pv { background: $panel; border: 1px solid $line; border-radius: 16px; }
#pv[err="true"] { border: 1px solid rgba(208,160,96,110); }
#pvTitle { font-size: 11.6pt; font-weight: 800; color: $text; }
#pvMeta { font-size: 9pt; color: $muted; }
#pvErr { font-size: 9pt; color: $muted; }
#tag { font-size: 8.2pt; font-weight: 700; color: $muted; background: $panel2; border-radius: 7px; padding: 3px 8px; }
QPushButton#tagWas { font-size: 8.2pt; font-weight: 700; color: $tint; background: rgba(184,168,226,40); border: none;
    border-radius: 7px; padding: 3px 8px; }
#picks { background: $panel; border: 1px solid $line; border-radius: 14px; }
#picksHead { font-size: 9pt; font-weight: 700; color: $muted; }
#hrow { background: transparent; border-radius: 12px; }
#hrow:hover { background: $panel; }
#dayLbl { font-size: 8.4pt; font-weight: 700; color: $faint; padding: 10px 2px 2px 2px; }
QLineEdit#search { background: $panel; border: 1px solid $line; border-radius: 9px; padding: 4px 10px; font-size: 9.2pt;
    color: $text; }
QLineEdit#search:focus { border: 1px solid $tint; }
#idleHint { color: $muted; font-size: 9.4pt; font-weight: 600; }
#idleTitle { color: $text; font-size: 11.4pt; font-weight: 800; }
#speed { color: $muted; font-size: 8.6pt; font-weight: 700; }
#sizeLbl { font-size: 10pt; font-weight: 800; color: $text; }
#sizeSub { font-size: 7.8pt; color: $faint; }
#gone { color: #d0a060; }
QLineEdit#tEdit { background: $panel2; border: 1px solid transparent; border-radius: 10px; padding: 6px 10px;
    font-family: "$mono"; font-size: 9.6pt; font-weight: 700; color: $text; }
#pxOk { color: #8fd19e; font-size: 9pt; }
#pxErr { color: #e59a86; font-size: 9pt; }
QLineEdit#tEdit:focus { border: 1px solid $tint; }
#tLbl { color: $faint; font-size: 7.4pt; font-weight: 800; }
#fnPrev { background: $panel2; border-radius: 10px; padding: 9px 11px; font-family: "$mono"; font-size: 8.6pt; color: $muted; }
#noSfx { background: $panel; border: 1px dashed $line2; border-radius: 12px; padding: 12px 14px; color: $muted; font-size: 9pt; }
""")
