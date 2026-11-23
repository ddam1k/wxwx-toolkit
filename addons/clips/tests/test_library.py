"""Clip library without Qt: recording dates, cut detection, sorting, delete with undo."""
import os
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

from wx_clips.core import library, trash


class LibraryTests(unittest.TestCase):
    def test_recorded(self):
        ts = library.recorded("Valorant 2023.03.28 - 21.15.06.02.DVR - Trim.mp4")
        self.assertEqual(datetime.fromtimestamp(ts), datetime(2023, 3, 28, 21, 15, 6))
        self.assertIsNone(library.recorded("my clip.mp4"))
        self.assertIsNone(library.recorded("Game 2023.13.40 - 25.00.00.DVR.mp4"))

    def test_looks_cut(self):
        yes = ["Valorant 2023.03.28 - 21.15.06.02.DVR - Trim.mp4", "Valorant 2026.11.22 - 19.45.00.01.DVR_wx.mp4",
               "Apex 2026.11.22 - 19.45.00.01.DVR_wx_2.mp4", "x_trim (2).mp4", "x_wx_1 (3).webm", "x_wx_.mp4",
               "x_mine.mp4"]
        no = ["Valorant 2026.11.22 - 19.45.00.01.DVR.mp4", "wxwx.mp4", "trimmer.mp4", "clip_1.mp4"]
        for n in yes:
            self.assertTrue(library.looks_cut(n, ("_mine",)), n)
        for n in no:
            self.assertFalse(library.looks_cut(n, ("_mine",)), n)

    def test_sort_and_new(self):
        d = Path(tempfile.mkdtemp())
        (d / "Valorant").mkdir()
        names = {"Valorant 2023.03.28 - 21.15.06.02.DVR_wx.mp4": 1000, "Valorant 2024.01.02 - 10.00.00.00.DVR.mp4": 50,
                 "Valorant 2022.06.01 - 08.00.00.00.DVR.mp4": 70, "no date.mp4": 10}
        for n, size in names.items():
            (d / "Valorant" / n).write_bytes(b"x" * size)
        hidden = d / "Valorant" / trash.STASH
        hidden.mkdir()
        (hidden / "deleted.mp4").write_bytes(b"x")
        f = library.scan(str(d))[0]
        self.assertEqual(f.count, 4)                       # the stash folder is not a clip
        byname = [c.name[:20] for c in library.sort_clips(f.clips, "name")]
        self.assertEqual(byname[0], "no date.mp4")
        new = library.sort_clips(f.clips, "new")
        self.assertEqual(new[0].name, "no date.mp4")         # no date in the name → file time (now)
        self.assertEqual([c.name[9:19] for c in new[1:]], ["2024.01.02", "2023.03.28", "2022.06.01"])
        self.assertEqual(library.sort_clips(f.clips, "old")[0].name[9:19], "2022.06.01")
        self.assertEqual(library.sort_clips(f.clips, "big")[0].size, 1000)
        fresh = library.new_clips([f], time.time() - 3600, set(), lambda p: library.looks_cut(p))
        self.assertEqual(len(fresh), 3)                      # the cut is not «new»

    def test_stash_restore_flush(self):
        d = Path(tempfile.mkdtemp())
        p = d / "clip.mp4"
        p.write_bytes(b"data")
        s = trash.stash(str(p))
        self.assertFalse(p.exists())
        self.assertTrue(os.path.exists(s))
        self.assertEqual(trash.restore(s, str(p)), str(p))
        self.assertTrue(p.exists())
        self.assertFalse((d / trash.STASH).exists())
        s = trash.stash(str(p))
        self.assertTrue(trash.flush(s, str(p)))              # off Windows: deleted for real
        self.assertFalse(p.exists())
        self.assertFalse((d / trash.STASH).exists())
        q = d / "left.mp4"
        q.write_bytes(b"x")
        trash.stash(str(q))
        self.assertEqual(trash.flush_left(str(d)), 1)
        self.assertFalse((d / trash.STASH).exists())


if __name__ == "__main__":
    unittest.main()
