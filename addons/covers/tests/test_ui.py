"""Clicks through the real Covers UI with a fake host and real ffmpeg.
Runs only with WX_UI_SMOKE=1 (CI on Windows). Screenshots go to $WX_SHOTS as smoke_covers_*.png."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

RUN = os.environ.get("WX_UI_SMOKE") == "1"


@unittest.skipUnless(RUN, "set WX_UI_SMOKE=1")
class CoversUiSmoke(unittest.TestCase):
    def test_flow(self):
        from PySide6.QtCore import QObject, Qt, Signal
        from PySide6.QtGui import QGuiApplication, QImage
        from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

        from wx_covers.core import audio

        app = QApplication.instance() or QApplication([])
        shots = Path(os.environ.get("WX_SHOTS", "."))
        tmp = Path(tempfile.mkdtemp(prefix="wx-covers-ui-"))
        music, out = tmp / "music", tmp / "out"
        music.mkdir()
        ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")

        def mk(name, *extra):
            p = music / name
            subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=330:d=4", *extra, str(p)], check=True)
            return str(p)

        wide = str(tmp / "sunset wide.png")
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "gradients=s=1280x720:c0=0xffcf9f:c1=0x5b3a73:x0=0:y0=0:x1=1280:y1=720", "-frames:v", "1", wide],
                       check=True)
        square = str(tmp / "moon.png")
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i",
                        "gradients=s=800x800:c0=0x1b1a2e:c1=0xd6b4e8", "-frames:v", "1", square], check=True)
        a = mk("Kaito Mirai - Glass Garden.mp3", "-c:a", "libmp3lame")
        b = mk("track07.mp3", "-c:a", "libmp3lame")
        c = mk("Low Orbit.m4a", "-c:a", "aac", "-metadata", "title=Low Orbit", "-metadata", "artist=Velvet Static")
        d0 = mk("demo.flac", "-metadata", "title=wxwx theme (demo)", "-metadata", "artist=yuyu")
        d = str(music / "demo with cover.flac")
        audio.save(audio.Change(d0, square), ff, fp, str(tmp))        # one file already has a picture
        os.replace(d0, d)

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

            def get(self, key, default=None, addon=None):
                return self.store.get(key, default)

            def set(self, key, value):
                self.store[key] = value
                self.settings_changed.emit(key)

            def installed(self, aid):
                return True

        host = Host()
        from wx_covers import addon
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

        def shot(name, w=None):
            spin(0.5)
            (w or win).grab().save(str(shots / f"smoke_covers_{name}.png"))

        shot("1_empty")
        page.add_paths([str(music)])
        self.assertEqual(len(page.items), 4)
        self.assertTrue(spin(20, lambda: all(i.track.duration > 0 for i in page.items)), "tags never read")
        self.assertTrue(spin(10, lambda: any(i.thumb for i in page.items)), "existing cover not shown")
        by = {os.path.basename(i.path): i for i in page.items}
        self.assertTrue(by["demo with cover.flac"].track.cover)
        self.assertEqual(by["Low Orbit.m4a"].tags["artist"], "Velvet Static")
        shot("2_list")

        # one track: a wide picture, whole on white, tags from the file name
        page._row_clicked(by["Kaito Mirai - Glass Garden.mp3"].id, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(len(page.picked()), 1)
        self.assertTrue(page.set_image(wide))
        self.assertTrue(page.panel.b_wide.isVisibleTo(page.panel))
        page.panel._set_fit("fit")
        page.panel._set_pad("white")
        page.panel._guess()
        self.assertEqual(by["Kaito Mirai - Glass Garden.mp3"].tags["artist"], "Kaito Mirai")
        page.panel._tag_edited("album", "Greenhouse")
        shot("3_one")

        # ctrl-click a second one, paste a picture from the clipboard
        page._row_clicked(by["track07.mp3"].id, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(page.picked()), 2)
        page._row_clicked(by["Kaito Mirai - Glass Garden.mp3"].id, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual([os.path.basename(i.path) for i in page.picked()], ["track07.mp3"])
        QGuiApplication.clipboard().setImage(QImage(square))
        spin(0.3)
        page.paste()
        self.assertTrue(by["track07.mp3"].new_cover, host.toasts[-1:])
        page._row_clicked(by["Kaito Mirai - Glass Garden.mp3"].id, Qt.KeyboardModifier.ControlModifier)
        shot("4_two_mixed")

        # all: tags differ → titles are left alone, a shared year goes to everyone
        page._toggle_all()
        self.assertEqual(len(page.picked()), 4)
        self.assertFalse(page.panel.edits["title"].isEnabled())
        page.panel._tag_edited("year", "2026")
        host.set("rename", True)
        shot("5_all")

        # undo everything, then do it again and save
        page.undo()
        self.assertFalse(any(i.dirty for i in page.items))
        page._row_clicked(by["Kaito Mirai - Glass Garden.mp3"].id, Qt.KeyboardModifier.NoModifier)
        page.set_image(wide)
        page.panel._set_fit("fit")
        page.panel._guess()
        page._row_clicked(by["demo with cover.flac"].id, Qt.KeyboardModifier.NoModifier)
        page.panel._remove()
        page.panel._tag_edited("album", "Demos")
        self.assertEqual(sum(i.dirty for i in page.items), 2)
        page.save()
        self.assertTrue(spin(60, lambda: not page._busy), "save never finished")
        names = sorted(os.listdir(music))
        print("music:", names)
        self.assertIn("Kaito Mirai — Glass Garden.mp3", names)            # renamed by tags
        self.assertIn("yuyu — wxwx theme (demo).flac", names)
        kaito = audio.read(str(music / "Kaito Mirai — Glass Garden.mp3"), fp)
        self.assertEqual((kaito.cover, kaito.cover_w, kaito.title), (True, 1000, "Glass Garden"))
        flac = audio.read(str(music / "yuyu — wxwx theme (demo).flac"), fp)
        self.assertEqual((flac.cover, flac.album), (False, "Demos"))
        self.assertTrue(all(i.saved for i in page.items if "Kaito" in i.path or "yuyu" in i.path))
        self.assertFalse([n for n in names if "wxwx-tmp" in n])
        shot("6_saved")

        # copies: the original stays as it was
        host.set("copies", True)
        host.set("rename", False)
        page._row_clicked(by["Low Orbit.m4a"].id, Qt.KeyboardModifier.NoModifier)
        page.set_image(square)
        page.save()
        self.assertTrue(spin(60, lambda: not page._busy))
        self.assertTrue(audio.read(str(out / "Low Orbit.m4a"), fp).cover)
        self.assertFalse(audio.read(str(music / "Low Orbit.m4a"), fp).cover)
        host.set("copies", False)

        # Saves hands over a download
        host.files_received.emit([b])                 # already in the list → not doubled
        sent = mk("rainy window study.mp3", "-c:a", "libmp3lame")
        host.files_received.emit([sent])
        self.assertEqual(len(page.items), 5)
        self.assertEqual(page.items[-1].source, "Сохранёнок")
        self.assertEqual([i.path for i in page.picked()], [sent])
        spin(3, lambda: page.items[-1].track.duration > 0)
        page.only_no.setChecked(True)
        shot("7_from_saves")
        page.only_no.setChecked(False)

        host.lang = "en"
        host.lang_changed.emit("en")
        page._toggle_all()
        shot("8_en")
        host.lang_changed.emit("ru")

        tab = addon.settings(host)
        holder = QWidget()
        holder.setObjectName("testWin")
        holder.setStyleSheet("#testWin{background:#111113}")
        QVBoxLayout(holder).addWidget(tab)
        holder.resize(720, 560)
        holder.show()
        shot("9_settings", holder)
        page.shutdown()
        print("toasts:", host.toasts)


if __name__ == "__main__":
    unittest.main()
