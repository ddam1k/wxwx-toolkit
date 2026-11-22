"""Core of Saves without Qt: links, yt-dlp arguments, progress lines, errors, sizes, history."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from wx_saves.core import links, ytdlp
from wx_saves.core.history import History


def yt_json(**over):
    fmts = [
        {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 129, "filesize": 3_000_000},
        {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 130, "filesize": 2_900_000},
        {"format_id": "137", "ext": "mp4", "vcodec": "avc1.640028", "acodec": "none", "height": 1080, "width": 1920,
         "filesize": 40_000_000},
        {"format_id": "248", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 1080, "width": 1920,
         "filesize": 30_000_000},
        {"format_id": "136", "ext": "mp4", "vcodec": "avc1.4d401f", "acodec": "none", "height": 720, "width": 1280,
         "filesize": 20_000_000},
        {"format_id": "313", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 2160, "width": 3840,
         "filesize": 150_000_000},
        {"format_id": "401", "ext": "mp4", "vcodec": "av01.0.12M.08", "acodec": "none", "height": 2160, "width": 3840,
         "filesize": 120_000_000},
    ]
    d = {"id": "abc123", "title": "Cloth sim", "uploader": "Motion Ref", "extractor_key": "Youtube",
         "duration": 200, "view_count": 12345, "width": 3840, "height": 2160, "fps": 60, "formats": fmts,
         "subtitles": {"en": [{}], "live_chat": [{}]}, "automatic_captions": {"ru": [{}]},
         "thumbnails": [{"url": "https://i.ytimg.com/a.jpg", "width": 1280, "height": 720},
                        {"url": "https://i.ytimg.com/a.webp", "width": 1920, "height": 1080}]}
    d.update(over)
    return json.dumps(d)


class LinkTests(unittest.TestCase):
    def test_split(self):
        text = "смотри https://youtu.be/abc, и https://www.tiktok.com/@a/video/1). https://youtu.be/abc"
        self.assertEqual(links.split(text), ["https://youtu.be/abc", "https://www.tiktok.com/@a/video/1"])
        self.assertEqual(links.split("просто текст"), [])

    def test_site(self):
        self.assertEqual(links.site("https://m.youtube.com/watch?v=x"), "YouTube")
        self.assertEqual(links.site("https://www.instagram.com/reel/x/"), "Instagram")
        self.assertEqual(links.site("https://vm.tiktok.com/x"), "TikTok")
        self.assertEqual(links.site("https://notyoutube.com/x"), "site")

    def test_playlist(self):
        self.assertTrue(links.is_playlist("https://www.youtube.com/playlist?list=PL1"))
        self.assertFalse(links.is_playlist("https://www.youtube.com/watch?v=a&list=PL1"))
        self.assertFalse(links.is_playlist("https://vimeo.com/playlist?list=1"))

    def test_video_id(self):
        self.assertEqual(links.video_id("https://youtu.be/abc?t=3"), "abc")
        self.assertEqual(links.video_id("https://www.youtube.com/watch?v=xyz&t=1"), "xyz")


class ArgsTests(unittest.TestCase):
    def test_video_args(self):
        o = ytdlp.Opts(q=1080, fmt="mp4", folder="D:/dl", subs="en")
        a = ytdlp.download_args("https://youtu.be/x", o, "C:/ff", "C:/deno.exe")
        self.assertEqual(a[-2:], ["--", "https://youtu.be/x"])
        self.assertIn("--merge-output-format", a)
        self.assertEqual(a[a.index("--merge-output-format") + 1], "mp4")
        self.assertIn("deno:C:/deno.exe", a)
        self.assertIn("--write-subs", a)
        self.assertNotIn("--write-auto-subs", a)
        self.assertEqual(a[a.index("-P") + 1], "D:/dl")

    def test_orig_and_audio(self):
        a = ytdlp.download_args("u", ytdlp.Opts(fmt="orig"))
        self.assertEqual(a[a.index("--merge-output-format") + 1], "webm/mkv")
        a = ytdlp.download_args("u", ytdlp.Opts(what="audio", afmt="mp3"))
        self.assertIn("-x", a)
        self.assertEqual(a[a.index("--audio-quality") + 1], "320K")
        self.assertNotIn("--merge-output-format", a)

    def test_piece_and_subfolder(self):
        a = ytdlp.download_args("u", ytdlp.Opts(part=(62.0, 95.5), subfolder="My: list"))
        tmpl = a[a.index("-o") + 1]
        self.assertTrue(tmpl.startswith("My_ list/"), tmpl)          # «:» is not allowed in Windows folder names
        self.assertIn("(1.02–1.35)", tmpl)
        self.assertIn("*62.00-95.50", a)

    def test_cookies(self):
        a = ytdlp.probe_args("u", False, cookies="firefox")
        self.assertIn("--cookies-from-browser", a)
        self.assertNotIn("--cookies-from-browser", ytdlp.probe_args("u", False))


class ParseTests(unittest.TestCase):
    def test_info(self):
        inf = ytdlp.parse_info(yt_json(), "https://youtu.be/abc123")
        self.assertEqual(inf.site, "YouTube")
        self.assertEqual(inf.heights, [2160, 1080, 720])
        self.assertEqual(inf.subs, ["en"])
        self.assertTrue(inf.auto_subs)
        self.assertTrue(inf.thumbnail.endswith(".jpg"))
        self.assertFalse(inf.vertical)
        # 4K has no H.264 → «MP4 для всех» converts
        self.assertTrue(ytdlp.needs_recode(inf, ytdlp.Opts(fmt="mp4", q=2160)))
        self.assertFalse(ytdlp.needs_recode(inf, ytdlp.Opts(fmt="mp4", q=1080)))
        self.assertFalse(ytdlp.needs_recode(inf, ytdlp.Opts(fmt="orig", q=2160)))

    def test_estimate(self):
        inf = ytdlp.parse_info(yt_json(), "u")
        full = ytdlp.estimate(inf, ytdlp.Opts(q=1080, fmt="mp4"))
        self.assertAlmostEqual(full, 43_000_000, delta=1)
        half = ytdlp.estimate(inf, ytdlp.Opts(q=1080, fmt="mp4", part=(0, 100)))
        self.assertAlmostEqual(half, full / 2, delta=1)
        self.assertGreaterEqual(ytdlp.estimate(inf, ytdlp.Opts(what="audio", afmt="mp3")), 200 * 40_000)

    def test_vertical_and_playlist(self):
        inf = ytdlp.parse_info(yt_json(width=1080, height=1920), "u")
        self.assertTrue(inf.vertical)
        pl = ytdlp.parse_info(json.dumps({"_type": "playlist", "title": "L", "extractor_key": "YoutubeTab",
                                          "entries": [{"id": "a", "title": "A", "duration": 60, "url": "a"},
                                                      None, {"id": "b", "title": "B", "duration": 30}]}), "u")
        self.assertTrue(pl.playlist)
        self.assertEqual(len(pl.entries), 2)
        self.assertEqual(pl.duration, 90)
        self.assertEqual(pl.entries[1]["url"], "https://www.youtube.com/watch?v=b")

    def test_progress_lines(self):
        p = ytdlp.parse_line("WXP 1000/4000/NA/250.5/12/avc1")
        self.assertEqual((p["kind"], p["done"], p["total"], p["speed"], p["eta"]), ("dl", 1000, 4000, 250.5, 12))
        p = ytdlp.parse_line("WXP 10/NA/500/NA/NA/none")
        self.assertEqual(p["total"], 500)
        self.assertTrue(p["audio"])
        self.assertEqual(ytdlp.parse_line("WXQ Merger/started")["pp"], "Merger")
        self.assertEqual(ytdlp.parse_line("WXFC:\\a b.mp4")["path"], "C:\\a b.mp4")
        self.assertIsNone(ytdlp.parse_line("[download] 5%"))
        self.assertEqual(ytdlp.stage_of_pp("FFmpegExtractAudio"), "audio")

    def test_errors(self):
        k = ytdlp.error_kind
        self.assertEqual(k("ERROR: [youtube] x: Sign in to confirm you're not a bot"), "login")
        self.assertEqual(k("ERROR: [youtube] x: Private video"), "private")
        self.assertEqual(k("ERROR: HTTP Error 429: Too Many Requests"), "ratelimit")
        self.assertEqual(k("ERROR: Unsupported URL: https://x"), "unsupported")
        self.assertEqual(k("ERROR: Could not copy Chrome cookie database"), "cookies")
        self.assertEqual(k("weird"), "other")
        self.assertIn("Private video", ytdlp.last_error("[info] x\nERROR: [youtube] x: Private video\n"))


class ProxyTests(unittest.TestCase):
    def test_addresses(self):
        from wx_saves.core import proxy
        self.assertEqual(proxy.candidates("1234"), ["socks5h://127.0.0.1:1234", "http://127.0.0.1:1234"])
        self.assertEqual(proxy.candidates(" 127.0.0.1:10808 "), ["socks5h://127.0.0.1:10808", "http://127.0.0.1:10808"])
        self.assertEqual(proxy.candidates("socks5://127.0.0.1:1080"), ["socks5h://127.0.0.1:1080"])
        self.assertEqual(proxy.candidates("HTTP://u:p@localhost:8080/"), ["http://u:p@localhost:8080"])
        self.assertEqual(proxy.normalize(""), "")
        for bad in ("127.0.0.1", "ftp://1.2.3.4:21", "localhost:70000", "привет"):
            self.assertFalse(proxy.valid(bad), bad)
        self.assertTrue(proxy.valid(""))
        self.assertEqual(proxy.check(""), ("off", ""))
        self.assertEqual(proxy.check("nope")[0], "bad")

    def test_args(self):
        a = ytdlp.download_args("u", ytdlp.Opts(proxy="socks5h://127.0.0.1:1"))
        self.assertEqual(a[a.index("--proxy") + 1], "socks5h://127.0.0.1:1")
        self.assertIn("--proxy", ytdlp.probe_args("u", False, proxy="http://h:1"))
        self.assertNotIn("--proxy", ytdlp.probe_args("u", False))
        self.assertEqual(ytdlp.error_kind("ERROR: Unable to connect to proxy"), "network")


@unittest.skipUnless(__import__("shutil").which("curl"), "needs curl")
class ProxyCheckTests(unittest.TestCase):
    def test_check_through_a_real_proxy(self):
        import http.server
        import socket
        from functools import partial
        from miniproxy import MiniProxy
        from wx_saves.core import proxy
        d = tempfile.mkdtemp()
        Path(d, "generate_204").write_text("")
        Path(d, "thumb.jpg").write_bytes(b"\xff\xd8 not really a jpeg")
        web = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(http.server.SimpleHTTPRequestHandler, directory=d))
        web.handle_error = lambda *_a: None
        __import__("threading").Thread(target=web.serve_forever, daemon=True).start()
        target = f"http://127.0.0.1:{web.server_address[1]}/generate_204"
        px = MiniProxy()
        # «1234» alone: SOCKS5 fails on an HTTP port, HTTP works → the HTTP address is the one kept
        self.assertEqual(proxy.check(str(px.port), target=target), ("ok", f"http://127.0.0.1:{px.port}"))
        self.assertTrue(any("generate_204" in ln for ln in px.seen))
        self.assertEqual(proxy.check(f"socks5h://127.0.0.1:{px.port}", target=target)[0], "proto")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
        s.close()
        self.assertEqual(proxy.check(str(dead), target=target)[0], "port")
        out = Path(d, "t.bin")
        self.assertTrue(proxy.fetch(target.replace("generate_204", "thumb.jpg"), str(out), f"http://127.0.0.1:{px.port}"))
        self.assertTrue(out.read_bytes().startswith(b"\xff\xd8"))
        web.shutdown()
        px.shutdown()


class MoveOutTests(unittest.TestCase):
    def test_never_overwrites(self):
        from wx_saves.core.files import move_out
        d = Path(tempfile.mkdtemp())
        staged, out = d / "job" / "out", d / "dl"
        (staged / "List").mkdir(parents=True)
        (out / "List").mkdir(parents=True)
        (out / "List" / "Song.mp3").write_text("old")
        (staged / "List" / "Song.mp3").write_text("new")
        dest = move_out(str(staged / "List" / "Song.mp3"), str(staged), str(out))
        self.assertEqual(Path(dest), out / "List" / "Song (2).mp3")
        self.assertEqual((out / "List" / "Song.mp3").read_text(), "old")


class HistoryTests(unittest.TestCase):
    def test_add_find_prune(self):
        d = Path(tempfile.mkdtemp())
        h = History(d)
        a = h.add({"key": "abc", "title": "Cloth sim", "url": "https://youtu.be/abc", "path": str(d / "nope.mp4")})
        self.assertTrue(a["hid"])
        self.assertEqual(History(d).find(key="abc")["title"], "Cloth sim")     # saved to disk
        self.assertEqual(len(h.search("cloth")), 1)
        self.assertEqual(h.search("zzz"), [])
        self.assertTrue(History.gone(a))
        old = h.add({"key": "old", "title": "Old", "url": "u"})
        old["t"] = time.time() - 60 * 86400
        h.save()
        h.set_keep("month")
        self.assertIsNone(h.find(key="old"))
        self.assertIsNotNone(h.find(key="abc"))
        h.remove(a["hid"])
        self.assertIsNone(h.find(key="abc"))
        h.add({"key": "x", "title": "X", "url": "u"})
        self.assertEqual(h.clear(), 1)
        self.assertEqual(History(d).items, [])


if __name__ == "__main__":
    unittest.main()
