"""Send files to the Recycle Bin (Windows); they can be restored from there."""
from __future__ import annotations

import os


def send_to_trash(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, os.path.abspath(path) + "\0", None,
                         FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI, False, None, None)
    try:
        r = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    except OSError:
        return False
    return r == 0 and not op.fAnyOperationsAborted and not os.path.exists(path)


# ---------------------------------------------------------------- delete with «Вернуть»
# A deleted clip first only steps aside into a hidden «.wxwx-trash» folder next to it (a rename: instant even
# for a 5-minute clip). «Вернуть» moves it back. A few seconds later — or when the add-on closes — it goes back
# to its own place and on into the Recycle Bin, so «Восстановить» in the Bin puts it where it was.
STASH = ".wxwx-trash"


def stash(path: str) -> str:
    folder = os.path.join(os.path.dirname(path), STASH)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, os.path.basename(path))
    n = 2
    while os.path.exists(dest):
        stem, ext = os.path.splitext(os.path.basename(path))
        dest = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    os.replace(path, dest)                   # raises if the file is open somewhere
    return dest


def restore(stashed: str, original: str) -> str:
    target = original
    if os.path.exists(target):
        stem, ext = os.path.splitext(original)
        target = f"{stem} (restored){ext}"
    os.replace(stashed, target)
    _drop_empty(os.path.dirname(stashed))
    return target


def flush(stashed: str, original: str) -> bool:
    """Into the Recycle Bin from the clip's own folder. Elsewhere than Windows: deleted."""
    if not os.path.exists(stashed):
        return False
    src = stashed
    if not os.path.exists(original):
        try:
            os.replace(stashed, original)
            src = original
        except OSError:
            pass
    ok = send_to_trash(src)
    if not ok and os.name != "nt":
        try:
            os.remove(src)
            ok = True
        except OSError:
            ok = False
    _drop_empty(os.path.dirname(stashed))
    return ok


def flush_left(root: str) -> int:
    """Clips left aside when the app was closed mid-countdown: finish their way to the Bin."""
    n = 0
    if not root or not os.path.isdir(root):
        return 0
    for base, dirs, _files in os.walk(root):
        if STASH in dirs:
            st = os.path.join(base, STASH)
            for f in os.listdir(st):
                if flush(os.path.join(st, f), os.path.join(base, f)):
                    n += 1
            dirs.remove(STASH)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
    return n


def _drop_empty(folder: str) -> None:
    if os.path.basename(folder) == STASH:
        try:
            os.rmdir(folder)
        except OSError:
            pass
