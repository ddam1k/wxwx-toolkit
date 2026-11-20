"""Colors and the stylesheet come from the shared wxwx kit (addons/_shared/kit in the toolkit repo);
below are the rules only Clips needs."""
from ..kit.theme import *  # noqa: F401,F403
from ..kit.theme import add_qss, set_font, stylesheet  # noqa: F401

add_qss(r"""
#tc { font-family: "$mono"; font-size: 8.8pt; color: $muted; }
#stepper { border-bottom: 1px solid $line; }
#timeBox { background: $panel2; border: 1px solid $line; border-radius: 11px; }
#tbTitle { color: $faint; font-size: 7.2pt; font-weight: 800; }
QLineEdit#tbEdit, QLineEdit#tbEditRo { background: transparent; border: none; padding: 0; font-family: "$mono";
    font-size: 9.6pt; font-weight: 700; color: $text; }
QLineEdit#tbEditRo { color: $tint; }
QLineEdit#segTime { background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 1px 4px;
    font-family: "$mono"; font-size: 8.8pt; font-weight: 700; color: $text; }
QLineEdit#segTime:hover { border: 1px solid $line2; }
QLineEdit#segTime:focus { border: 1px solid $tint; background: $win; }
#segNum { font-size: 7.8pt; font-weight: 800; }
#segSub { color: $faint; font-size: 7.8pt; font-weight: 600; padding-left: 14px; }
#segTotal { font-family: "$mono"; font-size: 9.6pt; font-weight: 800; }
#segEmpty { color: $faint; font-size: 8.6pt; border: 1px dashed $line2; border-radius: 12px; padding: 14px; }
#clipsPage, #clipsSettings { background: transparent; }
""")
