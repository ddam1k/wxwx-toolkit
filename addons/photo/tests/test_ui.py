"""Clicks through the real Photo UI with a fake host: real encodes in every format, compare view, saving.
Runs only with WX_UI_SMOKE=1 (CI on Windows). Screenshots go to $WX_SHOTS as smoke_photo_*.png."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

RUN = os.environ.get("WX_UI_SMOKE") == "1"


@unittest.skipUnless(RUN, "set WX_UI_SMOKE=1")
class PhotoUiSmoke(unittest.TestCase):
    def test_flow(self):
        from PySide6.QtCore import QObject, Qt, Signal
        from PySide6.QtGui import QImageReader, QImageWriter
        from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

        from test_core import tiff
        from wx_photo.core import exif

        app = QApplication.instance() or QApplication([])
        print("Qt writes:", sorted(bytes(f).decode() for f in QImageWriter.supportedImageFormats()))
        shots = Path(os.environ.get("WX_SHOTS", "."))
        tmp = Path(tempfile.mkdtemp(prefix="wx-photo-ui-"))
        pics, out = tmp / "pics", tmp / "out"
        pics.mkdir()
        ff = shutil.which("ffmpeg")

        def mk(name, src, *extra):
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", src, "-frames:v", "1", *extra, str(pics / name)],
                           check=True)
            return str(pics / name)

        # a phone photo lying on its side (EXIF orientation 6) with a GPS tag
        photo = mk("IMG_4021.jpg", "gradients=s=4032x3024:c0=0x8fb4d9:c1=0x3d4a3a:n=4,noise=alls=18:allf=t", "-q:v", "2")
        with open(photo, "rb") as f:
            data = f.read()
        with open(photo, "wb") as f:
            f.write(exif.put_exif(data, tiff(6, True)))
        # put_exif resets orientation to 1 — set it back to 6 by hand for the test
        with open(photo, "rb") as f:
            raw = bytearray(f.read())
        t0 = exif.jpeg_exif(bytes(raw))
        pos = bytes(raw).find(t0)
        p_or = exif.tags(t0)[exif.ORIENTATION][0]
        raw[pos + p_or + 8:pos + p_or + 10] = (6).to_bytes(2, "little")
        with open(photo, "wb") as f:
            f.write(bytes(raw))
        shot_png = mk("screenshot_2026-11-19.png", "testsrc2=s=2560x1440")
        logo = mk("logo_wx.png", "color=c=black@0.0:s=1024x1024,format=rgba,drawbox=x=212:y=212:w=600:h=600:color=0xb8a8e2@1:t=fill",
                  "-pix_fmt", "rgba")
        pose = mk("pose_ref_03.webp", "gradients=s=1200x1600:c0=0xe9d3c4:c1=0x4a2f3d", "-c:v", "libwebp", "-quality", "90")
        avif_in = mk("render.avif", "testsrc2=s=1600x900", "-c:v", "libaom-av1", "-still-picture", "1", "-cpu-used", "8",
                     "-pix_fmt", "yuv420p")

        class Host(QObject):
            lang_changed = Signal(str)
            theme_changed = Signal(str)
            folders_changed = Signal(str)
            settings_changed = Signal(str)
            hints_changed = Signal(bool)
            files_received = Signal(list)
            lang, theme, hints, api_version, toolkit_version = "ru", "dark", True, 1, "1.3.2"

            def __init__(self):
                super().__init__()
                self.store = {}
                self.data_dir = tmp / "data"
                self.data_dir.mkdir()
                self.toasts = []

            def component(self, name, exe=None):
                return shutil.which(exe or name)

            def toast(self, text):
                self.toasts.append(text)
                print("toast:", text)

            def folder(self, kind="output"):
                return str(out)

            def suffix(self):
                return "_wx"

            def get(self, key, default=None, addon=None):
                return self.store.get(key, default)

            def set(self, key, value):
                self.store[key] = value
                self.settings_changed.emit(key)

        host = Host()
        from wx_photo import addon
        page = addon.create(host)
        win = QWidget()
        win.setObjectName("testWin")
        win.setStyleSheet("#testWin{background:#111113}")
        QVBoxLayout(win).addWidget(page)
        win.layout().setContentsMargins(0, 0, 0, 0)
        win.resize(1180, 780)
        win.show()

        def spin(sec, until=None):
            end = time.time() + sec
            while time.time() < end:
                app.processEvents()
                time.sleep(0.02)
                if until and until():
                    return True
            return bool(until and until())

        def shot(name):
            spin(0.5)
            win.grab().save(str(shots / f"smoke_photo_{name}.png"))

        def estimated():
            key = page.panel.o.key()
            return all(i.src.error or (i.res is not None and i.res_key == key) for i in page.items)

        shot("1_empty")
        page.add_paths([str(pics)])
        self.assertEqual(len(page.items), 5)
        self.assertTrue(spin(60, lambda: all(i.src.w for i in page.items)), [i.src for i in page.items])
        by = {os.path.basename(i.src.path): i for i in page.items}
        ph = by["IMG_4021.jpg"].src
        self.assertEqual((ph.w, ph.h), (3024, 4032))             # turned upright by EXIF
        self.assertTrue(ph.gps)
        self.assertTrue(by["logo_wx.png"].src.alpha)
        self.assertFalse(by["screenshot_2026-11-19.png"].src.alpha)
        self.assertEqual(by["render.avif"].src.w, 1600)          # read through ffmpeg
        self.assertTrue(spin(120, estimated), "estimates (web preset) never finished")
        r = by["IMG_4021.jpg"].res
        self.assertEqual((r.fmt, r.w, r.h), ("webp", 1440, 1920))
        self.assertLess(len(r.data), ph.size)
        shot("2_list_web")

        page.open_compare(by["IMG_4021.jpg"].id)
        self.assertTrue(spin(20, lambda: page.cmp.before is not None and page.cmp.after is not None), "compare empty")
        page.cmp.cut = 0.42
        shot("3_compare")
        page.cmp.zoom = True
        page.cmp.focus_pt = page.cmp.focus_pt.__class__(0.3, 0.6)
        shot("4_compare_zoom")
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        page.cmp.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        spin(0.5)
        self.assertEqual(page.cmp.item_id, -1)

        # Telegram preset, then «own» by moving the quality; transparency warning for JPG
        page.panel._preset("tg")
        self.assertIn("белым", page.panel.fmt_note.text())
        page.panel.slider.setValue(62)
        self.assertEqual(page.panel.o.preset, "own")
        self.assertTrue(spin(120, estimated), "estimates (jpg 62) never finished")
        jr = by["IMG_4021.jpg"].res
        self.assertEqual(jr.fmt, "jpg")
        self.assertIsNone(exif.jpeg_exif(jr.data))               # privacy on: no camera data
        shot("5_own_jpg")

        page.panel._fmt("avif")
        self.assertTrue(spin(240, estimated), "AVIF estimates never finished")
        self.assertEqual(by["logo_wx.png"].res.fmt, "avif")
        shot("6_avif")

        # save (toolkit folder + _wx)
        page.panel._fmt("webp")
        self.assertTrue(spin(120, estimated))
        page.save()
        self.assertTrue(spin(120, lambda: not page._busy), "save never finished")
        names = sorted(os.listdir(out))
        print("out:", names)
        self.assertEqual(names, ["IMG_4021_wx.webp", "logo_wx_wx.webp", "pose_ref_03_wx.webp", "render_wx.webp",
                                 "screenshot_2026-11-19_wx.webp"])
        rd = QImageReader(str(out / "logo_wx_wx.webp"))
        img = rd.read()
        self.assertTrue(img.hasAlphaChannel(), "WebP lost the transparency")
        self.assertTrue(all(i.st == "done" for i in page.items))
        shot("7_saved")

        # «Без потерь» next to the originals: the JPG is the same picture, camera data kept
        page.panel._dest(False)
        page.panel._preset("loss")
        self.assertTrue(spin(120, estimated))
        page.save()
        self.assertTrue(spin(120, lambda: not page._busy))
        same = pics / "IMG_4021_wx.jpg"
        self.assertTrue(same.exists(), sorted(os.listdir(pics)))
        with open(same, "rb") as f:
            kept = f.read()
        self.assertEqual(kept, raw)                               # byte for byte
        self.assertTrue(exif.has_gps(kept))
        self.assertTrue((pics / "screenshot_2026-11-19_wx.png").exists())

        host.lang = "en"
        host.lang_changed.emit("en")
        shot("8_en")
        host.lang_changed.emit("ru")

        tab = addon.settings(host)
        holder = QWidget()
        holder.setObjectName("testWin")
        holder.setStyleSheet("#testWin{background:#111113}")
        QVBoxLayout(holder).addWidget(tab)
        holder.resize(720, 460)
        holder.show()
        spin(0.5)
        holder.grab().save(str(shots / "smoke_photo_9_settings.png"))
        page.shutdown()
        print("toasts:", host.toasts)


if __name__ == "__main__":
    unittest.main()
