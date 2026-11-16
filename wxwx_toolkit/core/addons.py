"""Add-ons: catalog from GitHub, install/uninstall from zip, loading into the toolkit (no Qt here).

An add-on is a zip with this layout (see docs/ADDONS.md):

    manifest.json
    wx_<id>/__init__.py      exposes  create(host) -> QWidget

manifest.json:
    {
      "id": "compress",                       lowercase letters, digits, dashes
      "version": "1.0.0",
      "entry": "wx_compress:create",          module:function
      "name": {"ru": "Видео", "en": "Video"},
      "description": {"ru": "...", "en": "..."},
      "icon": "video",                        one of the toolkit icons (video, photo, dl, music, …)
      "needs": ["ffmpeg"],                    shared components, see components.py
      "min_toolkit": "1.0.0"
    }

The catalog (addons.json in the toolkit repo) lists add-ons and the GitHub repo each one is
released from; the zip is the release asset named  wxwx-addon-<id>-<version>.zip
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .. import REPO, __version__
from . import net
from .paths import addons_dir, downloads_tmp
from .updater import is_newer, parse_version

CATALOG_URL = f"https://raw.githubusercontent.com/{REPO}/main/addons.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


@dataclass
class Manifest:
    id: str
    version: str
    entry: str
    name: dict
    description: dict = field(default_factory=dict)
    icon: str = "addon"
    needs: list = field(default_factory=list)
    min_toolkit: str = "1.0.0"
    path: Path | None = None

    @classmethod
    def from_dict(cls, d: dict, path: Path | None = None) -> "Manifest":
        if not ID_RE.match(str(d.get("id", ""))):
            raise ValueError(f"bad add-on id: {d.get('id')!r}")
        if ":" not in str(d.get("entry", "")):
            raise ValueError("entry must look like 'module:function'")
        name = d.get("name") or {}
        if isinstance(name, str):
            name = {"en": name, "ru": name}
        desc = d.get("description") or {}
        if isinstance(desc, str):
            desc = {"en": desc, "ru": desc}
        return cls(id=d["id"], version=str(d.get("version", "0.0.0")), entry=d["entry"], name=name,
                   description=desc, icon=d.get("icon", "addon"), needs=list(d.get("needs", [])),
                   min_toolkit=str(d.get("min_toolkit", "1.0.0")), path=path)

    def title(self, lang: str) -> str:
        return self.name.get(lang) or self.name.get("en") or self.id

    def desc(self, lang: str) -> str:
        return self.description.get(lang) or self.description.get("en") or ""

    @property
    def compatible(self) -> bool:
        return not is_newer(self.min_toolkit, __version__)


@dataclass
class CatalogEntry:
    """What the store shows for an add-on that may or may not be installed."""
    id: str
    repo: str
    name: dict
    description: dict
    icon: str
    needs: list
    latest: str | None = None
    asset_url: str | None = None
    asset_size: int = 0
    min_toolkit: str = "1.0.0"

    def title(self, lang: str) -> str:
        return self.name.get(lang) or self.name.get("en") or self.id

    def desc(self, lang: str) -> str:
        return self.description.get(lang) or self.description.get("en") or ""


# ---------------------------------------------------------------- installed add-ons
def installed() -> dict[str, Manifest]:
    out: dict[str, Manifest] = {}
    for d in sorted(addons_dir().iterdir()):
        mf = d / "manifest.json"
        if d.is_dir() and not d.name.startswith(".") and mf.is_file():
            try:
                m = Manifest.from_dict(json.loads(mf.read_text("utf-8")), d)
                if m.id == d.name:
                    out[m.id] = m
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
    return out


def _manifest_root(extracted: Path) -> Path:
    if (extracted / "manifest.json").is_file():
        return extracted
    subs = [p for p in extracted.iterdir() if p.is_dir()]
    if len(subs) == 1 and (subs[0] / "manifest.json").is_file():
        return subs[0]
    raise ValueError("manifest.json not found in the zip")


def install_zip(zip_path: str) -> Manifest:
    """Validates and installs (or replaces) an add-on from a zip. Returns its manifest."""
    with tempfile.TemporaryDirectory(dir=addons_dir(), prefix=".tmp-") as tmp:
        tmpp = Path(tmp)
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():  # no absolute paths / .. tricks
                target = (tmpp / name).resolve()
                if not str(target).startswith(str(tmpp.resolve())):
                    raise ValueError(f"unsafe path in zip: {name}")
            z.extractall(tmpp)
        root = _manifest_root(tmpp)
        m = Manifest.from_dict(json.loads((root / "manifest.json").read_text("utf-8")))
        module = m.entry.split(":")[0].split(".")[0]
        if not (root / module).is_dir() and not (root / f"{module}.py").is_file():
            raise ValueError(f"entry module '{module}' is missing")
        dest = addons_dir() / m.id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(root), str(dest))
    m.path = dest
    return m


def uninstall(addon_id: str) -> None:
    d = addons_dir() / addon_id
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def load(m: Manifest, host):
    """Imports the add-on and calls its entry with the host API; returns its QWidget."""
    path = str(m.path)
    if path not in sys.path:
        sys.path.insert(0, path)
    module_name, func_name = m.entry.split(":", 1)
    top = module_name.split(".")[0]
    for name in list(sys.modules):  # fresh import after an update in the same session
        if name == top or name.startswith(top + "."):
            del sys.modules[name]
    module = importlib.import_module(module_name)
    return getattr(module, func_name)(host)


# ---------------------------------------------------------------- catalog
def parse_catalog(data: dict) -> list[CatalogEntry]:
    out = []
    for a in data.get("addons", []):
        if not ID_RE.match(str(a.get("id", ""))) or "/" not in str(a.get("repo", "")):
            continue
        name = a.get("name") or {"en": a["id"]}
        out.append(CatalogEntry(id=a["id"], repo=a["repo"], name=name, description=a.get("description", {}),
                                icon=a.get("icon", "addon"), needs=list(a.get("needs", [])),
                                min_toolkit=str(a.get("min_toolkit", "1.0.0"))))
    return out


def resolve_release(entry: CatalogEntry, release: dict) -> CatalogEntry:
    prefix = f"wxwx-addon-{entry.id}-"
    asset = next((a for a in release.get("assets", [])
                  if a.get("name", "").startswith(prefix) and a.get("name", "").endswith(".zip")), None)
    if asset:
        entry.latest = asset["name"][len(prefix):-4] or (release.get("tag_name") or "").lstrip("v")
        entry.asset_url = asset.get("browser_download_url")
        entry.asset_size = int(asset.get("size") or 0)
    return entry


def fetch_catalog() -> list[CatalogEntry]:
    """Catalog + latest release of each add-on. Network errors for one add-on don't hide the rest."""
    entries = parse_catalog(net.get_json(CATALOG_URL))
    for e in entries:
        try:
            resolve_release(e, net.latest_release(e.repo))
        except Exception:
            pass
    return entries


def download_and_install(entry: CatalogEntry, progress=None) -> Manifest:
    if not entry.asset_url:
        raise RuntimeError("the add-on has no release yet")
    path = net.download(entry.asset_url, str(downloads_tmp() / f"{entry.id}.zip"), progress,
                        expected_size=entry.asset_size)
    try:
        return install_zip(path)
    finally:
        Path(path).unlink(missing_ok=True)


def needs_update(entry: CatalogEntry, have: Manifest | None) -> bool:
    return bool(have and entry.latest and parse_version(entry.latest) > parse_version(have.version))
