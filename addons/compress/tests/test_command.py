"""Runs the generated ffmpeg commands for real on a short synthetic clip.

    python -m unittest discover -s tests -v
"""
import os
import subprocess
import tempfile
import unittest

from wx_compress.core import ffmpeg as ff
from wx_compress.core.command import build_args, estimate_mb, output_path, preview
from wx_compress.core.settings import BUILTIN_PRESETS, EncodeSettings, apply_preset


@unittest.skipUnless(ff.FFMPEG and ff.FFPROBE, "ffmpeg/ffprobe not found")
class EncodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="wxwx-test-")
        cls.src = os.path.join(cls.tmp, "sample clip.mp4")
        subprocess.run([ff.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=6",
                        "-f", "lavfi", "-i", "sine=f=440:d=6",
                        "-c:v", "libx264", "-crf", "16", "-c:a", "aac", "-shortest", cls.src],
                       check=True, creationflags=ff.NO_WINDOW)
        cls.media = ff.probe(cls.src)
        cls.encoders = ff.list_encoders()

    def encode(self, s: EncodeSettings) -> tuple[str, float]:
        out = output_path(self.src, s.format, "custom", self.tmp)
        r = subprocess.run([ff.FFMPEG, *build_args(s, self.media, out)], capture_output=True, text=True,
                           creationflags=ff.NO_WINDOW)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + preview(build_args(s, self.media, out)))
        self.assertIn("progress=end", r.stdout)
        return out, os.path.getsize(out) / 1048576

    def test_probe(self):
        m = self.media
        self.assertEqual((m.width, m.height), (1280, 720))
        self.assertAlmostEqual(m.fps, 30, places=1)
        self.assertAlmostEqual(m.duration, 6, delta=0.2)
        self.assertEqual(m.acodec, "aac")
        self.assertTrue(ff.thumbnail(self.src, m.duration))

    def test_all_presets(self):
        for p in BUILTIN_PRESETS:
            with self.subTest(preset=p.id):
                s = apply_preset(EncodeSettings(), p)
                out, mb = self.encode(s)
                info = ff.probe(out)
                self.assertIsNotNone(info)
                if s.res:
                    self.assertLessEqual(info.short_side, s.res)
                self.assertGreater(mb, 0)
                self.assertGreater(estimate_mb(s, self.media), 0)

    def test_size_mode_hits_target(self):
        for codec in ("h264", "h265"):
            with self.subTest(codec=codec):
                s = EncodeSettings(format="mp4", codec=codec, mode="size", size_mb=1, res=None)
                _, mb = self.encode(s)
                self.assertLessEqual(mb, 1.12)
                self.assertGreater(mb, 0.5)

    def test_ratio_and_codecs(self):
        combos = [("mp4", "av1", "libsvtav1"), ("webm", "vp9", "libvpx-vp9"), ("webm", "av1", "libsvtav1")]
        for fmt, codec, need in combos:
            if need not in self.encoders:
                continue
            with self.subTest(fmt=fmt, codec=codec):
                s = EncodeSettings(format=fmt, codec=codec, mode="ratio", ratio=4, res=480, fps_idx=6)
                out, mb = self.encode(s)
                info = ff.probe(out)
                self.assertEqual(info.short_side, 480)
                self.assertAlmostEqual(info.fps, 15, delta=0.5)
                self.assertLess(mb, self.media.size_mb / 3)

    def test_audio_modes(self):
        for audio in ("keep", "none"):
            with self.subTest(audio=audio):
                out, _ = self.encode(EncodeSettings(audio=audio, quality=30, res=360))
                info = ff.probe(out)
                self.assertEqual(info.acodec is None, audio == "none")

    def test_output_path_suffix(self):
        out = output_path(self.src, "mp4", "custom", self.tmp, "_trim")
        self.assertIn("sample clip_trim", os.path.basename(out))
        self.assertIn("sample clip_wx", os.path.basename(output_path(self.src, "mp4", "custom", self.tmp)))

    def test_output_path_never_overwrites_source(self):
        p = output_path(self.src, "mp4")
        self.assertNotEqual(os.path.abspath(p), os.path.abspath(self.src))
        self.assertIn("_wx", p)


class SettingsTests(unittest.TestCase):
    def test_normalize(self):
        s = EncodeSettings.from_dict({"format": "webm", "codec": "h264", "encoder": "gpu", "junk": 1})
        self.assertEqual(s.codec, "vp9")
        self.assertEqual(s.encoder, "cpu")
        s = EncodeSettings.from_dict({"format": "gif"})
        self.assertEqual(s.codec, "gif")


if __name__ == "__main__":
    unittest.main()
