"""Entry point.

    python run.py                                   normal start
    python run.py --smoke out.png [--addon a.zip]   CI check: screenshots of the main screens, then exit
"""
from __future__ import annotations

import getpass
import json
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
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


SERVER = f"wxwx-toolkit-{getpass.getuser()}"


def _file_args(argv: list[str]) -> list[str]:
    return [os.path.abspath(a) for a in argv[1:] if not a.startswith("--") and os.path.isfile(a)]


def _send_to_running(paths: list[str]) -> bool:
    """If the toolkit is already open, hand it the files and let this process exit."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(json.dumps(paths).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def _listen(win) -> QLocalServer:
    server = QLocalServer(win)
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def on_conn():
        conn = server.nextPendingConnection()

        def read():
            try:
                paths = json.loads(bytes(conn.readAll()).decode("utf-8") or "[]")
            except ValueError:
                paths = []
            win.bring_to_front()
            win.handle_paths(paths)
        conn.readyRead.connect(read)
    server.newConnection.connect(on_conn)
    return server


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wxwx.toolkit")
        except Exception:
            pass

    app = QApplication(argv)
    smoke = "--smoke" in argv
    files = _file_args(argv)
    if not smoke and _send_to_running(files):
        return 0
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
    if not smoke:
        win._server = _listen(win)
        if files:
            QTimer.singleShot(600, lambda: win.handle_paths(files))
    if "--smoke" in argv:
        i = argv.index("--smoke")
        zips = [argv[k + 1] for k, x in enumerate(argv[:-1]) if x == "--addon"]
        media = argv[argv.index("--media") + 1] if "--media" in argv else None

        def hook(*exc):
            import traceback
            win.smoke_errors.append("".join(traceback.format_exception(*exc)))
            sys.__excepthook__(*exc)
        sys.excepthook = hook
        win.smoke(argv[i + 1], zips, media)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
