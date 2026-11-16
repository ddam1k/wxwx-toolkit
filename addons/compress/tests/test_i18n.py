import json
import tempfile
import unittest
from pathlib import Path

from wx_compress.core import i18n, presets


class I18nTests(unittest.TestCase):
    def test_same_keys(self):
        self.assertEqual(set(i18n.STR["ru"]), set(i18n.STR["en"]))
        self.assertEqual(len(i18n.STR["ru"]["q_words"]), len(i18n.STR["en"]["q_words"]))

    def test_formatting(self):
        i18n.set_lang("ru")
        self.assertEqual(i18n.files_word(3), "3 файла")
        self.assertEqual(i18n.fmt_mb(2.5), "2,5 МБ")
        i18n.set_lang("en")
        self.assertEqual(i18n.fmt_mb(2048), "2.00 GB")
        self.assertIn("50", i18n.t("st_work", p=50))
        i18n.set_lang("ru")


class WtpTests(unittest.TestCase):
    def test_roundtrip_matches_toolkit_format(self):
        d = Path(tempfile.mkdtemp())
        p = presets.write(d / "x", presets.make("compress", "Discord", {"format": "mp4"}, "Видео", "1.1.0"))
        raw = json.loads(p.read_text("utf-8"))
        self.assertEqual((p.suffix, raw["wtp"], raw["addon"]), (".wtp", 1, "compress"))
        self.assertEqual(presets.read(p)["settings"], {"format": "mp4"})


if __name__ == "__main__":
    unittest.main()
