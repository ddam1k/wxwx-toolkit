"""Colors and the stylesheet come from the shared wxwx kit; below are the rules only Photo needs."""
from ..kit.theme import *  # noqa: F401,F403
from ..kit.theme import add_qss, set_font, stylesheet  # noqa: F401

add_qss(r"""
#photoPage, #photoSettings { background: transparent; }
#idleHint { color: $muted; font-size: 9.4pt; font-weight: 600; }
#idleTitle { color: $text; font-size: 11.4pt; font-weight: 800; }
#qValue { color: $text; font-size: 17pt; font-weight: 800; }
#qWord { color: $tint; font-size: 9pt; font-weight: 700; }
#qEnd { color: $faint; font-size: 8pt; font-weight: 600; }
QLineEdit#pxEdit { background: transparent; border: 1px solid $line; border-radius: 13px; padding: 3px 10px;
    font-size: 9pt; font-weight: 700; color: $text; min-width: 46px; max-width: 64px; }
QLineEdit#pxEdit:focus { border: 1px solid $tint; }
QLineEdit#pxEdit[on="true"] { border: 1px solid $ink; }
#warnNote { color: #e5b986; font-size: 8.6pt; }
""")
