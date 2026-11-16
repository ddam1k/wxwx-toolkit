"""Builds a zip for every add-on in addons/<id>/  ->  dist/addons/wxwx-addon-<id>-<version>.zip

    python scripts/build_addons.py            all add-ons
    python scripts/build_addons.py compress   just one

An add-on folder holds manifest.json + its package (wx_<something>/); tests/ and caches are left out.
If the package has __version__, it must match manifest.json (the add-on shows it in its .wtp presets).
Prints one line per zip: <id> <version> <path>
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"__pycache__", "tests", ".pytest_cache"}


def build(folder: Path, out_dir: Path) -> tuple[str, str, Path]:
    m = json.loads((folder / "manifest.json").read_text("utf-8"))
    aid, ver = m["id"], m["version"]
    if aid != folder.name:
        raise SystemExit(f"{folder}: manifest id {aid!r} must equal the folder name")
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        raise SystemExit(f"{aid}: version {ver!r} must look like 1.2.3")
    pkg = folder / m["entry"].split(":")[0].split(".")[0]
    init = pkg / "__init__.py"
    if init.is_file():
        found = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text("utf-8"))
        if found and found.group(1) != ver:
            raise SystemExit(f"{aid}: __version__ {found.group(1)} != manifest version {ver}")
    out = out_dir / f"wxwx-addon-{aid}-{ver}.zip"
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            rel = f.relative_to(folder)
            if f.is_file() and not SKIP_DIRS & set(rel.parts) and f.suffix != ".pyc":
                z.write(f, rel)
    return aid, ver, out


def main(argv: list[str]) -> int:
    out_dir = ROOT / "dist" / "addons"
    folders = sorted(p for p in (ROOT / "addons").iterdir() if (p / "manifest.json").is_file())
    if argv:
        folders = [f for f in folders if f.name in argv]
    for f in folders:
        aid, ver, out = build(f, out_dir)
        print(aid, ver, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
