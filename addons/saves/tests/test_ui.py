"""Clicks through the real Saves UI with a fake host; real yt-dlp downloads from a local web server.
Runs only with WX_UI_SMOKE=1 (CI on Windows). Screenshots go to $WX_SHOTS as smoke_saves_*.png."""
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from functools import partial
from pathlib import Path

RUN = os.environ.get("WX_UI_SMOKE") == "1"


@unittest.skipUnless(RUN, "set WX_UI_SMOKE=1")
class SavesUiSmoke(unittest.TestCase):
    def test_flow(self):
        from PySide6.QtCore import QObject, Signal
        from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

        from test_core import yt_json
        from wx_saves.core import ytdlp

        app = QApplication.instance() or QApplication([])
        shots = Path(os.environ.get("WX_SHOTS", "."))
        tmp = Path(tempfile.mkdtemp(prefix="wx-saves-ui-"))
        www, out = tmp / "www", tmp / "out"
        www.mkdir()
        ffmpeg = shutil.which("ffmpeg")
        ffdir = os.path.dirname(ffmpeg)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=8",
                        "-f", "lavfi", "-i", "sine=f=440:d=8", "-c:v", "libx264", "-preset", "ultrafast",
                        "-c:a", "aac", "-shortest", str(www / "Cloth sim breakdown.mp4")], check=True)
        subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360", "-frames:v", "1",
                        str(www / "thumb.jpg")], check=True)
        srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(http.server.SimpleHTTPRequestHandler, directory=str(www)))
        srv.handle_error = lambda *_a: None          # yt-dlp closes the probe request early — that's fine
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        class Host(QObject):
            lang_changed = Signal(str)
            theme_changed = Signal(str)
            folders_changed = Signal(str)
            settings_changed = Signal(str)
            hints_changed = Signal(bool)
            files_received = Signal(list)
            lang, theme, hints, api_version, toolkit_version = "ru", "dark", True, 1, "1.3.1"

            def __init__(self):
                super().__init__()
                self.store = {"watch_clip": False, "auto_upd": False}
                self.data_dir = tmp / "data"
                self.data_dir.mkdir()
                self.toasts, self.sent = [], []

            def component(self, name, exe=None):
                if name == "ffmpeg":
                    return shutil.which(exe or "ffmpeg")
                return os.environ.get({"yt-dlp": "WX_YTDLP", "deno": "WX_DENO"}[name])

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
                return aid == "compress"

            def send_to(self, aid, paths):
                self.sent.append((aid, paths))
                return True

            def open_settings(self):
                pass

        host = Host()
        from wx_saves import addon
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
            spin(0.6)
            (w or win).grab().save(str(shots / f"smoke_saves_{name}.png"))

        shot("1_empty")

        # a YouTube video as yt-dlp would describe it (no network in the preview states)
        url = "https://www.youtube.com/watch?v=abc123"
        info = json.loads(yt_json())
        info["thumbnails"] = [{"url": f"{base}/thumb.jpg", "width": 640, "height": 360}]
        page.url.blockSignals(True)
        page.url.setText(url)
        page.url.blockSignals(False)
        page._site_tag()
        page.cur_url = url
        page._loaded("probe:" + url, (ytdlp.parse_info(json.dumps(info), url), ""))
        self.assertEqual(page.state, "video")
        spin(3, lambda: any(f.suffix == ".jpg" for f in (host.data_dir / "thumbs").glob("*")) if (host.data_dir / "thumbs").exists() else False)
        shot("2_video")
        page.panel._set_what("audio")
        shot("3_audio")
        page.panel._set_what("video")

        page._loaded("probe:" + url, (None, "ERROR: [youtube] abc123: Sign in to confirm you're not a bot"))
        self.assertEqual(page.state, "error")
        self.assertEqual(page.err[0], "login")
        shot("4_error")

        pl_url = "https://www.youtube.com/playlist?list=PL1"
        page.cur_url = pl_url
        pl = {"_type": "playlist", "id": "PL1", "title": "Референсы ткани", "uploader": "Motion Ref",
              "extractor_key": "YoutubeTab",
              "entries": [{"id": f"v{i}", "title": f"Cloth test #{i}", "duration": 60 + i * 17} for i in range(7)]}
        page._loaded("probe:" + pl_url, (ytdlp.parse_info(json.dumps(pl), pl_url), ""))
        self.assertEqual(page.state, "playlist")
        page._pick(2, False)
        shot("5_playlist")

        # real download: direct file from the local server through yt-dlp's generic extractor
        page.clear_url()
        spin(0.5)
        page.url.setText(f"{base}/Cloth%20sim%20breakdown.mp4")
        self.assertTrue(spin(60, lambda: page.state in ("video", "error")), "probe never finished")
        self.assertEqual(page.state, "video", page.err)
        shot("6_probed")
        page.start()
        self.assertTrue(spin(5, lambda: page.jobs and page.jobs[0].state == "work"))
        shot("7_working")
        self.assertTrue(spin(120, lambda: page.jobs[0].state in ("done", "err")), "download never finished")
        j = page.jobs[0]
        self.assertEqual(j.state, "done", (j.err_kind, j.err_text))
        self.assertTrue(os.path.isfile(j.path), j.path)
        print("saved:", j.path, j.size)

        # the same link as MP3 — the MP4 already in the folder must stay; this one goes through a proxy
        from miniproxy import MiniProxy
        px = MiniProxy()
        host.set("proxy", str(px.port))          # just the port, as people type it
        page.url.setText(f"{base}/Cloth%20sim%20breakdown.mp4")
        self.assertTrue(spin(60, lambda: page.state == "video"))
        page.panel._set_what("audio")
        page.start()
        self.assertTrue(spin(120, lambda: page.jobs[0].state in ("done", "err")), "mp3 never finished")
        self.assertEqual(page.jobs[0].state, "done", (page.jobs[0].err_kind, page.jobs[0].err_text))
        self.assertTrue(page.jobs[0].path.endswith(".mp3"), page.jobs[0].path)
        print("through proxy:", px.seen[:4])
        self.assertEqual(host.store["proxy"], f"http://127.0.0.1:{px.port}")   # SOCKS guess failed → HTTP kept
        self.assertTrue(any("Cloth" in ln for ln in px.seen), "yt-dlp did not use the proxy")
        files = sorted(p.name for p in out.rglob("*") if p.is_file())
        print("outputs:", files)
        self.assertEqual(len(files), 2, files)
        shot("8_done")

        page._row_action(page.jobs[1].id, "send")
        self.assertEqual(host.sent and host.sent[0][0], "compress")

        page.tabs.select("hist", emit=True)
        self.assertEqual(len(page.hist.items), 2)
        shot("9_history")
        page.search.setText("zzz")
        spin(0.3)
        page.search.setText("")
        host.lang = "en"
        host.lang_changed.emit("en")
        shot("10_history_en")
        host.lang_changed.emit("ru")

        host.hints = False
        host.hints_changed.emit(False)
        page.tabs.select("now", emit=True)
        shot("11_no_hints")

        tab = addon.settings(host)
        holder = QWidget()
        holder.setObjectName("testWin")
        holder.setStyleSheet("#testWin{background:#111113}")
        QVBoxLayout(holder).addWidget(tab)
        holder.resize(720, 1300)
        holder.show()
        spin(8, lambda: tab.versions["yt-dlp"] is not None)
        shot("12_settings", holder)
        tab._proxy_check()                       # the test proxy forwards to the real youtube.com
        self.assertTrue(spin(40, lambda: tab.px not in ("", "checking")), "proxy check hung")
        print("proxy check:", tab.px, tab.px_addr)
        self.assertEqual(tab.px, "ok")
        self.assertEqual(host.store["proxy"], f"http://127.0.0.1:{px.port}")
        shot("13_proxy_ok", holder)
        tab.px_edit.setText("1")
        tab._proxy_check()
        self.assertTrue(spin(30, lambda: tab.px not in ("", "checking")))
        self.assertEqual(tab.px, "port")
        shot("14_proxy_dead", holder)
        tab._clear_history()
        self.assertTrue(spin(2, lambda: not page.hist.items), "page history not cleared from settings")

        page.shutdown()
        srv.shutdown()
        px.shutdown()
        print("toasts:", host.toasts)


if __name__ == "__main__":
    unittest.main()
