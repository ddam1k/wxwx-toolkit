"""Clicks through the real Clips UI with a fake host and real ffmpeg; saves screenshots.
Runs only with WX_UI_SMOKE=1 (CI on Windows). Screenshots go to $WX_SHOTS as smoke_clips_*.png."""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

RUN = os.environ.get("WX_UI_SMOKE") == "1"


@unittest.skipUnless(RUN, "set WX_UI_SMOKE=1")
class ClipsUiSmoke(unittest.TestCase):
    def test_flow(self):
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

        from wx_clips.core import ffmpeg as ff

        app = QApplication.instance() or QApplication([])
        shots = Path(os.environ.get("WX_SHOTS", "."))
        tmp = Path(tempfile.mkdtemp(prefix="wx-clips-ui-"))
        nv = tmp / "NVIDIA"
        out = tmp / "out"

        def make(game, stamp, dur, color, old=False):
            d = nv / game
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{game} {stamp}.DVR.mp4"
            subprocess.run([ff.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=60:d={dur}",
                            "-f", "lavfi", "-i", f"sine=f=440:d={dur}", "-f", "lavfi", "-i", f"sine=f=660:d={dur}",
                            "-vf", f"drawbox=x=0:y=0:w=1280:h=90:color={color}@0.8:t=fill", "-map", "0", "-map", "1",
                            "-map", "2", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(p)], check=True)
            if old:
                ts = time.time() - 30 * 86400
                os.utime(p, (ts, ts))
            return str(p)

        a = make("Valorant", "2026.11.16 - 23.17.09.05", 12, "red")
        b = make("Valorant", "2026.11.16 - 21.40.11.02", 8, "purple")
        c = make("Grand Theft Auto V", "2026.11.16 - 22.59.30.01", 10, "orange")
        jre = make("Jre-1.8", "2026.10.25 - 11.52.00.01", 6, "green", old=True)

        class Host(QObject):
            lang_changed = Signal(str)
            theme_changed = Signal(str)
            folders_changed = Signal(str)
            preset_received = Signal(dict)
            settings_changed = Signal(str)
            lang, theme, api_version, toolkit_version = "ru", "dark", 1, "1.2.0"

            def __init__(self):
                super().__init__()
                self.store = {("clips", "nv_dir"): str(nv), ("clips", "last_launch"): time.time() - 86400,
                              ("clips", "del_orig"): True,
                              ("compress", "presets"): [{"id": "u1", "title": "Клипы 1080p60",
                                                         "values": {"format": "mp4", "codec": "h264", "quality": 70,
                                                                    "res": 1080, "fps_idx": 0, "mode": "quality"}}]}
                self.data_dir = tmp / "data"
                self.data_dir.mkdir()
                self.toasts = []

            def component(self, name, exe=None):
                return ff.FFPROBE if exe == "ffprobe" else ff.FFMPEG

            def toast(self, text):
                self.toasts.append(text)
                print("toast:", text)

            def folder(self, kind="output"):
                return str(out)

            def get(self, key, default=None, addon=None):
                return self.store.get((addon or "clips", key), default)

            def set(self, key, value):
                self.store[("clips", key)] = value
                self.settings_changed.emit(key)

            def installed(self, aid):
                return True

            def open_settings(self):
                pass

        host = Host()
        from wx_clips import addon
        page = addon.create(host)
        win = QWidget()
        win.setObjectName("testWin")
        win.setStyleSheet("#testWin{background:#111113}")
        QVBoxLayout(win).addWidget(page)
        win.layout().setContentsMargins(0, 0, 0, 0)
        win.resize(1180, 760)
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
            spin(0.6)
            win.grab().save(str(shots / f"smoke_clips_{name}.png"))

        self.assertTrue(spin(20, lambda: page.state == "ok"), "scan never finished")
        self.assertEqual(len(page.new_list), 3)
        spin(8, lambda: all(page._thumb.get(p) for p in (a, b, c)))
        shot("1_home")
        page.home.tabs.select("folders", emit=True)
        spin(4, lambda: all(page._thumb.get(f.clips[0].path) for f in page.folders))
        shot("2_folders")
        page.home._open_folder(next(f for f in page.folders if f.name == "Valorant"))
        shot("3_folder")

        page.picks |= {a, b, c}
        page.home._open_picked()
        ed = page.editor
        self.assertTrue(spin(20, lambda: all(k.info for k in page.clips) and page.clips[0].frames), "clips did not load")
        spin(5, lambda: ed.view.img is not None)
        self.assertIsNotNone(ed.view.img, "player shows no frame")
        clip = page.clips[page.cur]
        ed.player.play()
        spin(0.5)
        ed._scrub_start(True)
        ed.player.seek(5.0)
        ed._scrub_end("seek")
        self.assertTrue(spin(2, lambda: ed.player.playing), "clicking the timeline must keep playing")
        ed.player.pause()
        clip.single.a, clip.single.b = 2.0, 7.5
        ed.player.seek(4.0)
        ed.changed()
        shot("4_single")

        ed.set_mode("multi")
        clip.add(8.0, 10.5)
        clip.toggle_edit(0)
        ed.changed()
        ed.play_cut(1)
        spin(1.0)
        shot("5_multi_edit")
        ed._toggle_edit(None)
        ed.player.pause()

        page.cur = 1
        ed.load_current()
        page.clips[1].set_mode("multi")
        page.clips[1].add(1, 3)
        page.clips[1].add(4, 6)
        page.clips[1].merge = False
        ed.changed()
        ed.go_step(2)
        shot("6_step2")

        ed.export()
        self.assertTrue(spin(180, lambda: not ed.running), "export did not finish")
        files = sorted(p.name for p in out.glob("*"))
        print("outputs:", files)
        self.assertEqual(len(files), 4, files)          # 1 merged + 2 separate + 1 whole
        self.assertTrue(all(k.status == "done" for k in page.clips), [k.error for k in page.clips])
        shot("7_done")

        self.assertTrue(spin(5, lambda: not any(os.path.exists(x) for x in (a, b, c))), "originals not trashed")
        page.show_home()
        shot("8_home_after")
        self.assertTrue(spin(10, lambda: len(page.new_list) == 0))   # processed (and trashed) clips are gone

        # "+ Add" from the strip -> gallery -> pick another clip -> it joins the session
        n0 = len(page.clips)
        page.picks.add(jre)
        page.home._open_picked()
        spin(2)
        self.assertEqual(len(page.clips), n0 + 1, "picked clip was not added")
        self.assertIs(page.stack.currentWidget(), ed)
        self.assertEqual(ed.clip.path, jre)
        shot("8b_added")

        # Clear, then Gallery: must not crash, must end on the gallery with an empty session
        ed._clear()
        spin(1)
        self.assertEqual(page.clips, [])
        self.assertIs(page.stack.currentWidget(), page.home)
        page.show_editor()
        page.show_home()
        spin(0.6)
        shot("8c_cleared")

        tab = addon.settings(host)
        tab.resize(640, 640)
        tab.setStyleSheet(tab.styleSheet() + "#clipsSettings{background:#111113}")
        tab.setContentsMargins(24, 0, 24, 24)
        tab.setAttribute(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.WidgetAttribute.WA_StyledBackground, True)
        tab.show()
        spin(0.6)
        tab.grab().save(str(shots / "smoke_clips_9_settings.png"))

        host.lang = "en"
        host.lang_changed.emit("en")
        spin(0.5)
        page.shutdown()
