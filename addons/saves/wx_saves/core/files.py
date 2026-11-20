"""Putting finished files into the user's folder (no Qt here)."""
from __future__ import annotations

import os
import shutil


def free_name(path: str) -> str:
    """path, or «name (2).ext», «name (3).ext»… — never on top of an existing file."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


def move_out(path: str, staged: str, folder: str) -> str:
    """Move a finished file from the job folder into the user's folder, keeping a playlist subfolder."""
    rel = os.path.relpath(path, staged)
    if rel.startswith(".."):
        rel = os.path.basename(path)
    dest = free_name(os.path.join(folder, rel))
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    shutil.move(path, dest)
    return dest
