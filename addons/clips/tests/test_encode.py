"""Real ffmpeg runs of the cut/mix/compress plans.  python -m unittest discover -s tests -v"""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from wx_clips.core import ffmpeg as ff
from wx_clips.core import library
from wx_clips.core.cache import Cache
from wx_clips.core.encode import plan_clip
from wx_clips.core.settings import BUILTIN_PRESETS, EncodeSettings, apply_preset


def run_plan(plan):
    for st in plan.steps:
        r = subprocess.run([ff.FFMPEG, *st.args], capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(r.stdout[-2000:] + r.stderr[-2000:])
    for t in plan.temps:
        os.remove(t)


def info(path):
    r = subprocess.run([ff.FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                       capture_output=True, text=True)
    d = json.loads(r.stdout)
    return float(d["format"]["duration"]), [s["codec_type"] for s in d["streams"]]


@unittest.skipUnless(ff.FFMPEG and ff.FFPROBE, "ffmpeg not found")
class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="wx-clips-"))
        game = cls.tmp / "nv" / "Valorant"
        game.mkdir(parents=True)
        cls.src = str(game / "Valorant 2026.11.16 - 23.17.09.05.DVR.mp4")
        # like an NVIDIA clip: video + two audio tracks (game, mic)
        subprocess.run([ff.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=60:d=12",
                        "-f", "lavfi", "-i", "sine=f=440:d=12", "-f", "lavfi", "-i", "sine=f=880:d=12",
                        "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx264", "-g", "120", "-c:a", "aac",
                        "-metadata:s:a:0", "handler_name=Game", "-metadata:s:a:1", "handler_name=Mic", cls.src], check=True)
        cls.m = ff.probe(cls.src)
        cls.out = cls.tmp / "out"
        cls.out.mkdir()

    def s(self, pid, **kw):
        p = next(x for x in BUILTIN_PRESETS if x.id == pid)
        s = apply_preset(EncodeSettings(), p)
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_probe_tracks(self):
        self.assertEqual(self.m.audio_tracks, ["Game", "Mic"])
        self.assertAlmostEqual(self.m.duration, 12, delta=0.2)

    def test_merge_two_segments_mixed_audio(self):
        p = plan_clip(self.m, [(1, 3), (6, 8.5)], [0, 1], self.s("telegram"), True, self.out, self.tmp)
        self.assertEqual(len(p.outputs), 1)
        run_plan(p)
        d, kinds = info(p.outputs[0])
        self.assertAlmostEqual(d, 4.5, delta=0.25)
        self.assertEqual(kinds, ["video", "audio"])
        self.assertIn("_wx", p.outputs[0])

    def test_separate_files_one_track(self):
        p = plan_clip(self.m, [(0.5, 2), (4, 5)], [1], self.s("web"), False, self.out, self.tmp)
        self.assertEqual(len(p.outputs), 2)
        run_plan(p)
        self.assertAlmostEqual(info(p.outputs[0])[0], 1.5, delta=0.25)
        self.assertAlmostEqual(info(p.outputs[1])[0], 1.0, delta=0.25)
        self.assertTrue(p.outputs[1].endswith("_wx_2.webm"))

    def test_size_target_and_no_audio(self):
        p = plan_clip(self.m, [(2, 10)], [], self.s("discord", size_mb=1), True, self.out, self.tmp)
        run_plan(p)
        d, kinds = info(p.outputs[0])
        self.assertEqual(kinds, ["video"])
        self.assertLess(os.path.getsize(p.outputs[0]) / 1048576, 1.3)
        self.assertAlmostEqual(p.est_mb, 1.0, delta=0.01)

    def test_copy_mode_merge_keeps_tracks(self):
        p = plan_clip(self.m, [(0, 4), (6, 10)], [0, 1], None, True, self.out, self.tmp)
        self.assertEqual(len(p.steps), 3)
        run_plan(p)
        d, kinds = info(p.outputs[0])
        self.assertEqual(kinds, ["video", "audio", "audio"])
        self.assertAlmostEqual(d, 8, delta=2.2)       # keyframe cuts

    def test_gif(self):
        p = plan_clip(self.m, [(1, 2)], [0], self.s("gif"), True, self.out, self.tmp)
        run_plan(p)
        self.assertTrue(p.outputs[0].endswith(".gif"))

    def test_suffix(self):
        p = plan_clip(self.m, [(0.5, 2), (4, 5)], [0], self.s("web"), False, self.out, self.tmp, suffix="_trim")
        self.assertTrue(all("_trim_" in Path(o).stem for o in p.outputs), p.outputs)
        q = plan_clip(self.m, [], [0], self.s("web"), True, self.out, self.tmp, suffix="_small")
        self.assertTrue(Path(q.outputs[0]).stem.endswith("_small"), q.outputs)

    def test_names_never_clash(self):
        a = plan_clip(self.m, [], [0], self.s("telegram"), True, self.out, self.tmp, reserved := set())
        b = plan_clip(self.m, [], [0], self.s("telegram"), True, self.out, self.tmp, reserved)
        self.assertNotEqual(a.outputs[0], b.outputs[0])

    def test_library_and_cache(self):
        folders = library.scan(str(self.tmp / "nv"))
        self.assertEqual([f.name for f in folders], ["Valorant"])
        self.assertEqual(folders[0].clips[0].game, "Valorant")
        self.assertTrue(library.looks_like_clips(self.tmp / "nv"))
        self.assertEqual(len(library.new_clips(folders, time.time() - 3600, set())), 1)
        self.assertEqual(library.new_clips(folders, time.time() - 3600, {self.src}), [])
        c = Cache(self.tmp / "data")
        m = c.meta(self.src)
        self.assertEqual(m.audio_tracks, ["Game", "Mic"])
        self.assertEqual(c.meta(self.src).duration, m.duration)          # from the cache file
        self.assertTrue(Path(c.thumb(self.src, m.duration)).is_file())
        self.assertEqual(len(c.frames(self.src, m.duration, 6)), 6)
