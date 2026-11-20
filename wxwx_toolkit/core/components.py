"""Shared command-line tools that add-ons need (ffmpeg, yt-dlp, deno, …), downloaded once into
<data>\\components\\<name>\\ and shared by every add-on (no Qt here)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import net
from .paths import NO_WINDOW, components_dir, downloads_tmp

EXE = ".exe" if os.name == "nt" else ""


@dataclass
class Component:
    id: str
    title: str
    files: list[str]           # executables that must end up in the component folder
    version_args: list[str]
    size_mb: int               # rough download size for the UI

    def folder(self) -> Path:
        return components_dir() / self.id

    def exe(self, name: str | None = None) -> str | None:
        """Path to an executable of this component: our copy first, then PATH."""
        name = name or self.files[0]
        local = self.folder() / (name + EXE)
        if local.is_file():
            return str(local)
        return shutil.which(name)

    @property
    def installed_locally(self) -> bool:
        return all((self.folder() / (f + EXE)).is_file() for f in self.files)

    @property
    def available(self) -> bool:
        return all(self.exe(f) for f in self.files)

    def version(self) -> str | None:
        cache = self.folder() / "version.json"
        exe = self.folder() / (self.files[0] + EXE)
        fresh = cache.is_file() and exe.is_file() and cache.stat().st_mtime >= exe.stat().st_mtime - 2
        if self.installed_locally and fresh:      # the tool may update itself (yt-dlp -U) → then ask it
            try:
                return json.loads(cache.read_text("utf-8")).get("version")
            except (OSError, ValueError):
                pass
        exe = self.exe()
        if not exe:
            return None
        try:
            r = subprocess.run([exe, *self.version_args], capture_output=True, timeout=15,
                               creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
            line = r.stdout.decode("utf-8", "replace").strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            return None
        m = re.search(r"version\s+n?([\w.\-]+)", line) or re.search(r"([\d]{4}\.[\d.]+|\d+\.\d+(\.\d+)?)", line)
        return m.group(1) if m else line[:20]


COMPONENTS: dict[str, Component] = {
    "ffmpeg": Component("ffmpeg", "ffmpeg", ["ffmpeg", "ffprobe"], ["-hide_banner", "-version"], 200),
    "yt-dlp": Component("yt-dlp", "yt-dlp", ["yt-dlp"], ["--version"], 18),
    # yt-dlp needs a JavaScript runtime for YouTube since 2025.11 — deno is the recommended one
    "deno": Component("deno", "Deno", ["deno"], ["--version"], 45),
}

DENO_ASSET = "deno-x86_64-pc-windows-msvc.zip"


# ---------------------------------------------------------------- download sources
BTBN = "BtbN/FFmpeg-Builds"
# a stable branch first: master builds need a very new NVIDIA driver for NVENC
FFMPEG_PATTERNS = [r"^ffmpeg-n7\.1-latest-win64-gpl-7\.1\.zip$", r"^ffmpeg-n8\.0-latest-win64-gpl-8\.0\.zip$",
                   r"^ffmpeg-n\d+\.\d+-latest-win64-gpl-\d+\.\d+\.zip$", r"^ffmpeg-master-latest-win64-gpl\.zip$"]


def pick_ffmpeg_asset(assets: list[dict]) -> dict | None:
    for pat in FFMPEG_PATTERNS:
        hits = sorted((a for a in assets if re.match(pat, a.get("name", ""))), key=lambda a: a["name"])
        if hits:
            return hits[0]
    return None


def _write_version(c: Component, version: str) -> None:
    (c.folder() / "version.json").write_text(json.dumps({"version": version}), "utf-8")


def install(cid: str, progress=None) -> str:
    """Downloads a component; returns its version string. Windows builds only."""
    c = COMPONENTS[cid]
    c.folder().mkdir(parents=True, exist_ok=True)
    tmp = downloads_tmp()
    if cid == "ffmpeg":
        rel = net.get_json(f"https://api.github.com/repos/{BTBN}/releases/tags/latest")
        asset = pick_ffmpeg_asset(rel.get("assets", []))
        if not asset:
            raise RuntimeError("no ffmpeg build found")
        zpath = net.download(asset["browser_download_url"], str(tmp / asset["name"]), progress,
                             expected_size=int(asset.get("size") or 0))
        try:
            with zipfile.ZipFile(zpath) as z:
                for member in z.namelist():
                    base = member.rsplit("/", 1)[-1]
                    if base in ("ffmpeg.exe", "ffprobe.exe"):
                        with z.open(member) as src, open(c.folder() / base, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        finally:
            Path(zpath).unlink(missing_ok=True)
        m = re.search(r"-n(\d+\.\d+)", asset["name"])
        version = m.group(1) if m else "master"
    elif cid == "yt-dlp":
        rel = net.latest_release("yt-dlp/yt-dlp")
        asset = next(a for a in rel["assets"] if a["name"] == "yt-dlp.exe")
        net.download(asset["browser_download_url"], str(c.folder() / "yt-dlp.exe"), progress,
                     expected_size=int(asset.get("size") or 0))
        version = rel.get("tag_name", "")
    elif cid == "deno":
        rel = net.latest_release("denoland/deno")
        asset = next(a for a in rel["assets"] if a["name"] == DENO_ASSET)
        zpath = net.download(asset["browser_download_url"], str(tmp / asset["name"]), progress,
                             expected_size=int(asset.get("size") or 0))
        try:
            with zipfile.ZipFile(zpath) as z:
                member = next(m for m in z.namelist() if m.rsplit("/", 1)[-1] == "deno.exe")
                with z.open(member) as src, open(c.folder() / "deno.exe", "wb") as dst:
                    shutil.copyfileobj(src, dst)
        finally:
            Path(zpath).unlink(missing_ok=True)
        version = rel.get("tag_name", "").lstrip("v")
    else:
        raise KeyError(cid)
    _write_version(c, version)
    return version


def remove(cid: str) -> None:
    shutil.rmtree(COMPONENTS[cid].folder(), ignore_errors=True)
