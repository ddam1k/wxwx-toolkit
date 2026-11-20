"""Copies the shared wxwx kit (addons/_shared/kit/) into every add-on that uses it (wx_<id>/kit/).

    python scripts/sync_kit.py           copy
    python scripts/sync_kit.py --check   only check that every copy is identical (CI)

An add-on uses the kit when its package has a kit/ folder — create an empty one to opt in.
"""
from __future__ import annotations

import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "addons" / "_shared" / "kit"


def kit_files() -> list[Path]:
    return sorted(p for p in KIT.rglob("*.py") if "__pycache__" not in p.parts)


def targets() -> list[Path]:
    out = []
    for m in sorted((ROOT / "addons").glob("*/manifest.json")):
        pkg = m.parent / json.loads(m.read_text("utf-8"))["entry"].split(":")[0].split(".")[0]
        if (pkg / "kit").is_dir():
            out.append(pkg / "kit")
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = []
    for dst in targets():
        want = {p.relative_to(KIT) for p in kit_files()}
        have = {p.relative_to(dst) for p in dst.rglob("*.py") if "__pycache__" not in p.parts}
        for rel in sorted(want | have):
            a, b = KIT / rel, dst / rel
            same = a.is_file() and b.is_file() and filecmp.cmp(a, b, shallow=False)
            if same:
                continue
            if check:
                bad.append(str(b.relative_to(ROOT)))
            elif a.is_file():
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(a, b)
                print("updated", b.relative_to(ROOT))
            else:
                b.unlink()
                print("removed", b.relative_to(ROOT))
    # reports go to stderr: build_addons.py runs this check and its stdout is read as «id version zip» lines
    if bad:
        print("kit copies differ from addons/_shared/kit — run: python scripts/sync_kit.py", file=sys.stderr)
        print("\n".join("  " + b for b in bad), file=sys.stderr)
        return 1
    if check:
        print("kit OK in", ", ".join(str(t.relative_to(ROOT / "addons")) for t in targets()) or "no add-ons",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
