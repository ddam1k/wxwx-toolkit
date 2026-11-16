"""python -m unittest discover -s tests -v   (no network, no Qt)"""
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["WXWX_TOOLKIT_DATA"] = tempfile.mkdtemp(prefix="wxwx-data-")

from wxwx_toolkit.core import addons, components, i18n, updater  # noqa: E402


def make_zip(src: Path, dest: Path, nested: bool = False) -> Path:
    with zipfile.ZipFile(dest, "w") as z:
        for f in src.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                arc = f.relative_to(src)
                z.write(f, (Path("hello-addon") / arc) if nested else arc)
    return dest


class AddonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        addons.uninstall("hello")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_and_list(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                z = make_zip(ROOT / "examples" / "hello-addon", self.tmp / f"h{nested}.zip", nested)
                m = addons.install_zip(str(z))
                self.assertEqual((m.id, m.version, m.icon), ("hello", "1.0.0", "addon"))
                self.assertIn("hello", addons.installed())
                self.assertTrue((addons.installed()["hello"].path / "wx_hello" / "__init__.py").is_file())
                self.assertEqual(m.title("ru"), "Привет")
                self.assertTrue(m.compatible)

    def test_reinstall_replaces(self):
        z = make_zip(ROOT / "examples" / "hello-addon", self.tmp / "h.zip")
        addons.install_zip(str(z))
        (addons.installed()["hello"].path / "stale.txt").write_text("x")
        addons.install_zip(str(z))
        self.assertFalse((addons.installed()["hello"].path / "stale.txt").exists())
        addons.uninstall("hello")
        self.assertNotIn("hello", addons.installed())

    def test_rejects_bad_zips(self):
        bad = self.tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("readme.txt", "no manifest")
        with self.assertRaises(ValueError):
            addons.install_zip(str(bad))
        evil = self.tmp / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../escape.txt", "x")
            z.writestr("manifest.json", "{}")
        with self.assertRaises(ValueError):
            addons.install_zip(str(evil))
        nomod = self.tmp / "nomod.zip"
        with zipfile.ZipFile(nomod, "w") as z:
            z.writestr("manifest.json", json.dumps({"id": "x", "entry": "wx_x:create", "name": "X"}))
        with self.assertRaises(ValueError):
            addons.install_zip(str(nomod))
        for bad_id in ("Bad", "../x", ""):
            with self.assertRaises(ValueError):
                addons.Manifest.from_dict({"id": bad_id, "entry": "a:b"})

    def test_min_toolkit(self):
        m = addons.Manifest.from_dict({"id": "x", "entry": "a:b", "min_toolkit": "99.0.0"})
        self.assertFalse(m.compatible)

    def test_catalog(self):
        data = {"addons": [
            {"id": "compress", "repo": "ddam1k/wxwx-compress", "name": {"ru": "Видео", "en": "Video"},
             "needs": ["ffmpeg"], "icon": "video"},
            {"id": "BAD", "repo": "x/y"}, {"id": "norepo"},
        ]}
        cat = addons.parse_catalog(data)
        self.assertEqual([c.id for c in cat], ["compress"])
        rel = {"tag_name": "v1.2.0", "assets": [
            {"name": "wxwx-compress-setup-1.2.0.exe", "browser_download_url": "u/exe"},
            {"name": "wxwx-addon-compress-1.2.0.zip", "browser_download_url": "u/zip", "size": 5}]}
        e = addons.resolve_release(cat[0], rel)
        self.assertEqual((e.latest, e.asset_url, e.asset_size), ("1.2.0", "u/zip", 5))
        have = addons.Manifest.from_dict({"id": "compress", "entry": "a:b", "version": "1.1.0"})
        self.assertTrue(addons.needs_update(e, have))
        have.version = "1.2.0"
        self.assertFalse(addons.needs_update(e, have))

    def test_catalog_file_is_valid(self):
        data = json.loads((ROOT / "addons.json").read_text("utf-8"))
        self.assertIn("addons", data)
        self.assertEqual(len(addons.parse_catalog(data)), len(data["addons"]))


class MiscTests(unittest.TestCase):
    def test_updater(self):
        data = {"tag_name": "v1.1.0", "assets": [{"name": "wxwx-toolkit-setup-1.1.0.exe", "browser_download_url": "u",
                                                   "size": 3}]}
        r = updater.release_from_json(data, "1.0.0")
        self.assertEqual((r.version, r.asset_url), ("1.1.0", "u"))
        self.assertIsNone(updater.release_from_json(data, "1.1.0"))
        self.assertTrue(updater.is_newer("v1.10.0", "1.9.9"))

    def test_ffmpeg_asset_pick(self):
        names = ["ffmpeg-master-latest-win64-gpl.zip", "ffmpeg-n8.1-latest-win64-gpl-8.1.zip",
                 "ffmpeg-n8.1-latest-win64-lgpl-8.1.zip", "ffmpeg-n8.1-latest-win64-gpl-shared-8.1.zip"]
        self.assertEqual(components.pick_ffmpeg_asset([{"name": n} for n in names])["name"],
                         "ffmpeg-n8.1-latest-win64-gpl-8.1.zip")
        self.assertEqual(components.pick_ffmpeg_asset([{"name": names[0]}])["name"], names[0])

    def test_i18n(self):
        for lang in i18n.LANGS:
            i18n.set_lang(lang)
            self.assertEqual(set(i18n.STR["ru"]), set(i18n.STR["en"]))
            self.assertTrue(i18n.fmt_size(2.5))
        i18n.set_lang("ru")
        self.assertEqual(i18n.fmt_size(2.5), "2,5 МБ")
        self.assertEqual(i18n.plural_files(3), "3 файла")
        i18n.set_lang("en")
        self.assertEqual(i18n.fmt_size(2048), "2.00 GB")


if __name__ == "__main__":
    unittest.main()
