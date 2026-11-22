"""Covers engine without Qt: real ffmpeg on generated MP3 / M4A / FLAC files."""
import os
import shutil
import subprocess
import tempfile
import unittest

from wx_covers.core import audio, model
from wx_covers.core.audio import KEEP, REMOVE

FF = os.environ.get("WX_FFMPEG") or shutil.which("ffmpeg")
FP = os.environ.get("WX_FFPROBE") or shutil.which("ffprobe")


class NameTests(unittest.TestCase):
    def test_guess(self):
        self.assertEqual(audio.guess("Kaito Mirai - Glass Garden.mp3"), ("Kaito Mirai", "Glass Garden"))
        self.assertEqual(audio.guess("C:/x/a — b – c.flac"), ("a", "b - c"))
        self.assertIsNone(audio.guess("track07.mp3"))
        self.assertIsNone(audio.guess("well-known.mp3"))

    def test_planned(self):
        self.assertEqual(audio.planned_name({"artist": "AC/DC", "title": "T.N.T."}, "mp3"), "AC_DC — T.N.T.mp3")
        self.assertIsNone(audio.planned_name({"artist": "", "title": "x"}, "mp3"))

    def test_graph(self):
        g, side = audio.cover_graph(1280, 720, "crop", "blur", "1000")
        self.assertEqual(side, 720)                     # never upscaled
        self.assertIn("crop=720:720:280:0", g)
        g, side = audio.cover_graph(1280, 720, "fit", "white", "1000")
        self.assertEqual(side, 1000)
        self.assertIn("pad=1280:1280:0:280", g)
        g, side = audio.cover_graph(1000, 998, "fit", "blur", "orig")      # «square enough» → no padding
        self.assertIn("crop=998:998", g)

    def test_probe_parse(self):
        t = audio.parse_probe("x.flac", {"format": {"duration": "12.5", "size": "100", "tags": {"ALBUM": "A"}},
                                         "streams": [{"codec_type": "audio", "tags": {"TITLE": "T", "DATE": "2024-05-01"}},
                                                     {"codec_type": "video", "width": 500, "height": 500,
                                                      "disposition": {"attached_pic": 1}}]})
        self.assertEqual((t.title, t.album, t.year, t.cover, t.cover_w), ("T", "A", "2024", True, 500))


class ModelTests(unittest.TestCase):
    def item(self, name="a - b.mp3", **tags):
        return model.Item(audio.Track(path=name, fmt="mp3", **tags))

    def test_dirty_and_reset(self):
        it = self.item(title="x")
        self.assertFalse(it.dirty)
        model.set_tag([it], "album", " A ")
        self.assertEqual(it.changed_tags(), {"album": "A"})
        model.set_cover([it], "c.png", (1280, 720))
        self.assertTrue(it.wide)
        self.assertEqual(it.change().cover, "c.png")
        it.reset()
        self.assertFalse(it.dirty)
        model.remove_cover([it])                      # nothing to remove → still clean
        self.assertFalse(it.dirty)

    def test_guess_and_same(self):
        a, b, c = self.item("Kaito - Glass.mp3"), self.item("track07.mp3"), self.item("X - Y.mp3", title="Kept")
        self.assertTrue(model.can_guess([a, b]))
        self.assertEqual(model.guess_tags([a, b, c]), 1)
        self.assertEqual((a.tags["artist"], a.tags["title"]), ("Kaito", "Glass"))
        self.assertEqual(c.tags["title"], "Kept")
        self.assertIsNone(model.same([a, b], lambda i: i.tags["title"]))
        self.assertEqual(model.same([a], lambda i: i.tags["artist"]), "Kaito")
        self.assertEqual(a.planned_name(), "Kaito — Glass.mp3")
        self.assertEqual(b.planned_name(), "track07.mp3")


@unittest.skipUnless(FF and FP, "needs ffmpeg")
class EngineTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def mk(self, name, *extra):
        p = os.path.join(self.d, name)
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=2", *extra, p], check=True)
        return p

    def img(self, w, h):
        p = os.path.join(self.d, f"img{w}x{h}.png")
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}", "-frames:v", "1", p],
                       check=True)
        return p

    def test_every_format(self):
        files = [self.mk("Kaito Mirai - Glass Garden.mp3", "-c:a", "libmp3lame"),
                 self.mk("low orbit.m4a", "-c:a", "aac", "-metadata", "title=Low Orbit", "-metadata", "artist=VS"),
                 self.mk("demo.flac", "-metadata", "title=wxwx theme")]
        pic = self.img(1280, 720)
        cache = {}
        for p in files:
            before = audio.read(p, FP)
            it = model.Item(before)
            model.guess_tags([it])
            model.set_tag([it], "album", "Greenhouse")
            model.set_cover([it], pic, (1280, 720))
            it.fit = "fit"
            new = audio.save(it.change(), FF, FP, self.d, "1000", rename=True, full_tags=it.tags, cache=cache)
            t = audio.read(new, FP)
            self.assertEqual(t.album, "Greenhouse", new)
            self.assertTrue(t.cover, new)
            self.assertEqual((t.cover_w, t.cover_h), (1000, 1000), new)
            self.assertAlmostEqual(t.duration, before.duration, delta=0.1)
            self.assertEqual(t.title, it.tags["title"])
        self.assertEqual(len(cache), 1)                 # one picture rendered for all three
        names = sorted(f for f in os.listdir(self.d) if audio.is_audio(f))
        self.assertEqual(names, ["Kaito Mirai — Glass Garden.mp3", "VS — Low Orbit.m4a", "demo.flac"])
        self.assertFalse([f for f in os.listdir(self.d) if "wxwx-tmp" in f])

    def test_remove_keep_and_copies(self):
        p = self.mk("song.mp3", "-c:a", "libmp3lame")
        pic = self.img(600, 600)
        audio.save(audio.Change(p, pic), FF, FP, self.d)
        self.assertTrue(audio.read(p, FP).cover)
        audio.save(audio.Change(p, KEEP, tags={"title": "Only tags"}, had_cover=True), FF, FP, self.d)
        t = audio.read(p, FP)
        self.assertTrue(t.cover)                         # tags changed, the picture stayed
        self.assertEqual(t.title, "Only tags")
        out = os.path.join(self.d, "copies")
        c = audio.save(audio.Change(p, REMOVE, had_cover=True), FF, FP, self.d, copies_to=out)
        self.assertFalse(audio.read(c, FP).cover)
        self.assertTrue(audio.read(p, FP).cover)         # the original is untouched
        c2 = audio.save(audio.Change(p, KEEP, had_cover=True), FF, FP, self.d, copies_to=out)
        self.assertTrue(c2.endswith("song (2).mp3"))
        thumb = os.path.join(self.d, "t.jpg")
        self.assertTrue(audio.extract_cover(p, FF, thumb))

    def test_rename_never_overwrites(self):
        a = self.mk("one.mp3", "-c:a", "libmp3lame")
        self.mk("A — B.mp3", "-c:a", "libmp3lame")
        new = audio.save(audio.Change(a, KEEP, tags={"artist": "A", "title": "B"}), FF, FP, self.d, rename=True,
                         full_tags={"artist": "A", "title": "B"})
        self.assertTrue(new.endswith("A — B (2).mp3"), new)

    def test_broken_file(self):
        p = os.path.join(self.d, "broken.mp3")
        with open(p, "wb") as f:
            f.write(b"not audio at all")
        t = audio.read(p, FP)
        self.assertTrue(t.error)
        with self.assertRaises(RuntimeError):
            audio.save(audio.Change(p, KEEP, tags={"title": "x"}), FF, FP, self.d)
        with open(p, "rb") as f:
            self.assertEqual(f.read(), b"not audio at all")      # a failure leaves the file as it was


if __name__ == "__main__":
    unittest.main()
