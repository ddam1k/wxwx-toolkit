"""Tiny HTTP helpers on top of urllib (no extra dependencies)."""
from __future__ import annotations

import json
import os
import urllib.request

UA = {"User-Agent": "wxwx-toolkit", "Accept": "application/vnd.github+json"}


def get_json(url: str, timeout: float = 10, accept: str | None = None):
    headers = dict(UA, Accept=accept) if accept else UA
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):     # CI: no 60/h rate limit
        headers = dict(headers, Authorization=f"Bearer {os.environ['GITHUB_TOKEN']}")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dest: str, progress=None, cancelled=lambda: False, expected_size: int = 0) -> str:
    """Streams url to dest (via dest.part). progress(done, total)."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    part = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "wxwx-toolkit"})
    with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or expected_size or 0)
        done = 0
        while True:
            if cancelled():
                raise RuntimeError("cancelled")
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if total and done < total:
        raise RuntimeError("download interrupted")
    os.replace(part, dest)
    return dest


def latest_release(repo: str) -> dict:
    return get_json(f"https://api.github.com/repos/{repo}/releases/latest")
