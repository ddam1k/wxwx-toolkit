# PyInstaller spec: one-folder build
#   pyinstaller --noconfirm wxwx-toolkit.spec
# Add-ons are plain Python run inside this exe, so modules they may need must be bundled here:
# everything from PySide6-Essentials that is useful for tools (widgets, svg, multimedia-free), plus stdlib.

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6.QtSvg", "PySide6.QtNetwork", "PySide6.QtConcurrent", "PySide6.QtXml",
        "qframelesswindow", "qframelesswindow.windows", "win32gui", "win32api", "win32con",
        "json", "zipfile", "sqlite3", "csv", "hashlib", "urllib.request", "urllib.parse",
        "concurrent.futures", "subprocess", "shutil", "tempfile", "uuid", "dataclasses",
    ],
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtOpenGL", "PySide6.QtTest", "PySide6.QtDBus"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="wxwx-toolkit",
    console=False,
    icon="assets/icon.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="wxwx-toolkit", upx=False)
