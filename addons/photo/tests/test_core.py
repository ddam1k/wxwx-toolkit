"""Photo core without Qt: options, names, EXIF surgery, ffmpeg AVIF."""
import os
import shutil
import struct
import subprocess
import tempfile
import unittest

from wx_photo.core import exif, opts
from wx_photo.core.opts import Opts

FF = os.environ.get("WX_FFMPEG") or shutil.which("ffmpeg")


def tiff(orientation=6, gps=True, endian="<"):
    """A tiny IFD0: Orientation (+ GPS pointer)."""
    entries = [(0x0112, 3, 1, orientation)] + ([(0x8825, 4, 1, 0)] if gps else [])
    body = b"II*\x00" if endian == "<" else b"MM\x00*"
    body += struct.pack(endian + "I", 8) + struct.pack(endian + "H", len(entries))
    for tag, typ, cnt, val in entries:
        v = struct.pack(endian + "HH", val, 0) if typ == 3 else struct.pack(endian + "I", val)
        body += struct.pack(endian + "HHI", tag, typ, cnt) + v
    return body + b"\x00\x00\x00\x00"


def jpeg_with(tf: bytes) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    app1 = b"Exif\x00\x00" + tf
    app1 = b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    com = b"\xff\xfe" + struct.pack(">H", 7) + b"hello"
    return b"\xff\xd8" + app0 + app1 + com + b"\xff\xda\x00\x02SCANDATA\xff\xd9"


class OptsTests(unittest.TestCase):
    def test_presets_and_own(self):
        self.assertEqual(opts.matches(Opts("x", "webp", 80, 1920, True)), "web")
        self.assertEqual(opts.matches(Opts("x", "webp", 81, 1920, True)), "own")
        o = opts.from_dict({"fmt": "nope", "q": 7, "long": -5, "junk": 1})
        self.assertEqual((o.fmt, o.q, o.long), ("webp", 40, 0))

    def test_formats(self):
        o = Opts(fmt="orig")
        self.assertEqual(opts.out_fmt("a.JPEG", o), "jpg")
        self.assertEqual(opts.out_fmt("a.png", o), "png")
        self.assertEqual(opts.out_fmt("a.gif", o, alpha=True), "png")      # transparency is kept
        self.assertEqual(opts.out_fmt("a.heic", o), "jpg")
        self.assertEqual(opts.out_fmt("a.png", Opts(fmt="avif")), "avif")
        self.assertTrue(opts.needs_ffmpeg("IMG_1.HEIC"))
        self.assertFalse(opts.needs_ffmpeg("a.webp"))

    def test_dims_and_names(self):
        self.assertEqual(opts.dims(4032, 3024, 1920), (1920, 1440))
        self.assertEqual(opts.dims(1200, 1600, 1920), (1200, 1600))         # never upscaled
        self.assertEqual(opts.dims(3000, 3000, 0), (3000, 3000))
        self.assertEqual(opts.out_name("C:/p/IMG 4021.JPG", "webp", "_wx"), "IMG 4021_wx.webp")
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a_wx.jpg"), "w").close()
        taken = set()
        self.assertTrue(opts.free_name(os.path.join(d, "a_wx.jpg"), taken).endswith("a_wx (2).jpg"))
        self.assertTrue(opts.free_name(os.path.join(d, "a_wx.jpg"), taken).endswith("a_wx (3).jpg"))

    def test_avif_crf(self):
        self.assertEqual(opts.avif_crf(100), 14)
        self.assertEqual(opts.avif_crf(40), 48)
        self.assertLess(opts.avif_crf(90), opts.avif_crf(60))


class ExifTests(unittest.TestCase):
    def test_read_gps_orientation(self):
        for e in ("<", ">"):
            data = jpeg_with(tiff(6, True, e))
            t = exif.jpeg_exif(data)
            self.assertTrue(exif.has_gps(data))
            self.assertEqual(exif.tags(t)[exif.ORIENTATION][1], 6)
            self.assertEqual(exif.tags(exif.upright(t))[exif.ORIENTATION][1], 1)
        self.assertFalse(exif.has_gps(jpeg_with(tiff(1, False))))
        self.assertIsNone(exif.jpeg_exif(b"not a jpeg"))

    def test_strip_and_put(self):
        data = jpeg_with(tiff())
        clean = exif.strip_jpeg(data)
        self.assertIsNone(exif.jpeg_exif(clean))
        self.assertNotIn(b"hello", clean)                  # comments go too
        self.assertIn(b"JFIF", clean)                      # JFIF header stays
        self.assertTrue(clean.endswith(b"SCANDATA\xff\xd9"))
        back = exif.put_exif(clean, tiff(8))
        self.assertEqual(back[2:4], b"\xff\xe0")           # JFIF still first
        t = exif.jpeg_exif(back)
        self.assertEqual(exif.tags(t)[exif.ORIENTATION][1], 1)
        self.assertTrue(exif.has_gps(back))


@unittest.skipUnless(FF, "needs ffmpeg")
class FfmpegTests(unittest.TestCase):
    def test_avif_and_decode(self):
        d = tempfile.mkdtemp()
        png, avif, back = (os.path.join(d, n) for n in ("a.png", "a.avif", "b.png"))
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=800x600", "-frames:v", "1", png],
                       check=True)
        sizes = []
        for q in (50, 90):
            r = opts.run(opts.avif_args(FF, png, avif, q))
            self.assertEqual(r.returncode, 0, opts.ff_error(r))
            sizes.append(os.path.getsize(avif))
        self.assertLess(sizes[0], sizes[1])
        r = opts.run(opts.decode_args(FF, avif, back))
        self.assertEqual(r.returncode, 0, opts.ff_error(r))
        self.assertGreater(os.path.getsize(back), 0)


if __name__ == "__main__":
    unittest.main()
