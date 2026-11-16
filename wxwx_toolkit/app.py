"""Entry point.

    python run.py                                   normal start
    python run.py --smoke out.png [--addon a.zip]   CI check: screenshots of the main screens, then exit
"""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, __version__
from .ui import theme as theme_mod
from .ui.main_window import MainWindow
from .ui.widgets import logo_pixmap


def _pick_fonts() -> None:
    families = set(QFontDatabase.families())
    for name in ("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"):
        if name in families:
            theme_mod.FONT_FAMILY = name
            break
    for name in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"):
        if name in families:
            theme_mod.MONO_FAMILY = name
            break


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wxwx.toolkit")
        except Exception:
            pass

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("wxwx")
    _pick_fonts()
    app.setFont(QFont(theme_mod.FONT_FAMILY, 10))
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(s))
    app.setWindowIcon(icon)

    win = MainWindow()
    win.show()
    if "--smoke" in argv:
        i = argv.index("--smoke")
        addon = argv[argv.index("--addon") + 1] if "--addon" in argv else None

        def hook(*exc):
            import traceback
            win.smoke_errors.append("".join(traceback.format_exception(*exc)))
            sys.__excepthook__(*exc)
        sys.excepthook = hook
        win.smoke(argv[i + 1], addon)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
