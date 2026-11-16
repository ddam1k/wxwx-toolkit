"""Self-update of the toolkit through GitHub Releases (no Qt here).

Release assets (built by CI):
    wxwx-toolkit-setup-X.Y.Z.exe       installer, also used for updates (installs over the old one)
    wxwx-toolkit-X.Y.Z-portable.zip
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .. import REPO
from . import net
from .paths import app_dir, downloads_tmp

RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
SETUP_PREFIX = "wxwx-toolkit-setup-"
INSTALLER_ARGS = "/SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS"


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", (v or "").split("-")[0])[:3]
    return tuple(int(n) for n in nums) + (0,) * (3 - len(nums))


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


@dataclass
class Release:
    version: str
    notes: str
    page_url: str
    asset_name: str | None
    asset_url: str | None
    asset_size: int


def is_installed() -> bool:
    """True when running from the Inno Setup install (portable / source can't self-update)."""
    return (app_dir() / "unins000.exe").is_file()


def release_from_json(data: dict, current: str) -> Release | None:
    tag = data.get("tag_name") or ""
    if not tag or data.get("draft") or data.get("prerelease") or not is_newer(tag, current):
        return None
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").startswith(SETUP_PREFIX) and a.get("name", "").endswith(".exe")), None)
    return Release(
        version=tag.lstrip("v"), notes=(data.get("body") or "").strip(),
        page_url=data.get("html_url") or RELEASES_PAGE,
        asset_name=asset.get("name") if asset else None,
        asset_url=asset.get("browser_download_url") if asset else None,
        asset_size=int(asset.get("size") or 0) if asset else 0,
    )


def check(current: str) -> Release | None:
    return release_from_json(net.latest_release(REPO), current)


def download(rel: Release, progress=None) -> str:
    if not rel.asset_url:
        raise RuntimeError("no installer in the release")
    return net.download(rel.asset_url, str(downloads_tmp() / rel.asset_name), progress,
                        expected_size=rel.asset_size)


def launch_installer(path: str) -> None:
    """ShellExecute so Windows can show the UAC prompt (Program Files needs admin)."""
    os.startfile(path, arguments=INSTALLER_ARGS)  # type: ignore[attr-defined]
