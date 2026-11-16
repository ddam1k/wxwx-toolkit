import unittest

from wx_clips.core.ffmpeg import MediaInfo
from wx_clips.core.session import Clip


def clip(dur=90.0):
    c = Clip("x.mp4")
    c.ready(MediaInfo("x.mp4", 50, 1920, 1080, 60, dur, audio_tracks=["", ""]))
    return c


class SessionTests(unittest.TestCase):
    def test_single(self):
        c = clip()
        self.assertFalse(c.trimmed())
        c.key_in(10)
        c.key_out(25)
        self.assertEqual((c.single.a, c.single.b, c.kept()), (10, 25, 15))
        c.key_out(5)                                   # can't go before the start
        self.assertAlmostEqual(c.single.b, 10.5)
        self.assertEqual(c.tracks, [True, True])

    def test_keys_create_segments(self):
        c = clip()
        c.set_mode("multi")
        self.assertEqual(c.key_in(10), "pending")
        self.assertEqual(c.key_out(20), "added")
        self.assertEqual(c.key_in(40), "pending")
        self.assertEqual(c.key_out(30 + 10.1), "too_short")
        self.assertEqual(c.key_out(50), "added")
        self.assertEqual([(s.a, s.b) for s in c.multi], [(10, 20), (40, 50)])
        self.assertEqual(c.key_in(15), "moved")         # playhead inside segment 1 -> its start moves
        self.assertEqual(c.multi[0].a, 15)
        self.assertEqual(len({s.col for s in c.multi}), 2)

    def test_add_never_overlaps_but_edit_can(self):
        c = clip()
        c.set_mode("multi")
        c.add(10, 20)
        c.add(15, 30)                                    # clipped to 20..30
        self.assertEqual([(s.a, s.b) for s in c.multi], [(10, 20), (20, 30)])
        c.toggle_edit(1)
        c.key_in(5)                                      # edit mode: may overlap, list re-sorts
        self.assertEqual([(s.a, s.b) for s in c.multi], [(5, 30), (10, 20)])
        self.assertIs(c.multi[c.sel], c.edit)
        c.toggle_edit(c.sel)
        self.assertIsNone(c.edit)

    def test_mode_switch_keeps_the_cut(self):
        c = clip()
        c.key_in(30)
        c.key_out(48)
        c.set_mode("multi")
        self.assertEqual([(s.a, s.b) for s in c.multi], [(30, 48)])
        c.add(60, 70)
        c.merge = False
        self.assertEqual(c.out_files(), 2)
        c.set_mode("single")
        self.assertEqual((c.single.a, c.single.b), (30, 70))

    def test_c_cycles(self):
        c = clip()
        c.set_mode("multi")
        for a in (1, 10, 20):
            c.add(a, a + 3)
        self.assertEqual([c.next_c() for _ in range(4)], [0, 1, 2, 0])

    def test_typed_times(self):
        c = clip()
        c.set_mode("multi")
        c.add(10, 20)
        c.add(30, 40)
        self.assertTrue(c.set_time(1, "a", 5))           # overlaps are fine, list re-sorts
        self.assertEqual([(s.a, s.b) for s in c.multi], [(5, 40), (10, 20)])
        self.assertFalse(c.set_time(0, "b", 999))        # clamped to the clip end
        self.assertEqual(c.multi[0].b, 90)
