"""cardkit.reel: the reel timeline, frames, encoder settings and Instagram's file checks. The full render needs
Chrome and ffmpeg and uses only non-person images (tests/fixtures/commons_wagonr.jpg, a car; synthetic noise).
Run: python3 -m pytest -q tests"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from cardkit import reel as R  # noqa: E402
from cardkit import vertical as V  # noqa: E402
from tests.lane_helpers import CAR, CAR_CREDIT, chrome_available, mp4_bytes, noise_image  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def post(details=2):
    slides = [{"type": "cover", "headline": "WagonR Stays India's Best-Selling Car in October", "photo": str(CAR),
               "photo_credit": CAR_CREDIT, "focal": (0.5, 0.5), "zoom": 1.0}]
    slides += [{"type": "detail", "stat": s, "stat_label": "WagonR sales in October",
                "bullets": ["Brezza second, 1,311 units behind", "Top five: WagonR, Brezza, Nexon"]}
               for s in ("23,747", "+86%", "7 of 10")[:details]]
    return {"acct": "idlyautomotive", "slug": "t", "date": "10 Nov 2026", "sources": ["Autocar India"],
            "slides": slides}


class Timeline(unittest.TestCase):
    def test_always_9_to_14_seconds(self):
        for n in (0, 1, 2):
            segs = R.timeline(n)
            total = sum(f for _, f in segs) / R.FPS
            self.assertTrue(R.REEL_MIN_S <= total <= R.REEL_MAX_S, (n, total))
            self.assertTrue(all(f > 2 * R.XFADE for _, f in segs))
            self.assertEqual((segs[0][0], segs[-1][0]), ("cover", "end"))
        self.assertEqual([(s, f / R.FPS) for s, f in R.timeline(2)],
                         [("cover", 3.5), ("detail1", 3.0), ("detail2", 3.0), ("end", 1.5)])

    def test_pick_details(self):
        p = post(3)
        self.assertEqual([s["stat"] for s in R.pick_details(p)], ["23,747", "+86%"])
        self.assertEqual([s["stat"] for s in R.pick_details(p, [3, 1])], ["7 of 10", "23,747"])
        with self.assertRaises(ValueError):
            R.pick_details(p, [4])
        with self.assertRaises(ValueError):
            R.pick_details(p, [1, 2, 3])
        self.assertEqual(R.pick_details(post(0)), [])

    def test_encoder_settings(self):
        cmd = " ".join(R.ffmpeg_cmd(11.0, "out.mp4")) if shutil.which("ffmpeg") else ""
        if not cmd:
            self.skipTest("ffmpeg not installed")
        for want in ("-preset veryfast", "-c:v libx264", "-pix_fmt yuv420p", "-framerate 30",
                     "anullsrc=channel_layout=stereo:sample_rate=48000", "-c:a aac", "-movflags +faststart",
                     "-use_editlist 0", "open-gop=0", f"-s {V.VW}x{V.VH}"):
            self.assertIn(want, cmd)
        self.assertNotIn("-i music", cmd)


class Boxes(unittest.TestCase):
    def test_mp4_boxes(self):
        d = Path(tempfile.mkdtemp())
        for name, data, faststart, elst in (("ok", mp4_bytes(), True, False),
                                            ("late", mp4_bytes(faststart=False), False, False),
                                            ("elst", mp4_bytes(elst=True), True, True)):
            (d / f"{name}.mp4").write_bytes(data)
            info = R.mp4_boxes(str(d / f"{name}.mp4"))
            self.assertEqual((info["faststart"], info["elst"]), (faststart, elst), name)


class Frames(unittest.TestCase):
    """The frame logic on synthetic pages (no Chrome): push-in, text fade-in, crossfades, held slides."""

    def setUp(self):
        path = Path(tempfile.mkdtemp()) / "noise.jpg"
        noise_image(2000, 1500).save(path, quality=92)
        overlay = Image.new("RGBA", (V.VW, V.VH), (0, 0, 0, 0))
        text = Image.new("RGBA", (V.VW, V.VH), (0, 0, 0, 0))
        text.paste((255, 255, 255, 255), (64, 1300, 900, 1500))
        pages = {"window": V.PhotoWindow(str(path)), "overlay": overlay, "text": text,
                 "details": [Image.new("RGB", (V.VW, V.VH), (200, 0, 0)), Image.new("RGB", (V.VW, V.VH), (0, 200, 0))],
                 "end": Image.new("RGB", (V.VW, V.VH), (0, 0, 200))}
        self.frames = R.ReelFrames(pages, 2)

    def px(self, f, xy):
        return self.frames.frame(f).getpixel(xy)

    def test_text_slides_in_after_0_4_s(self):
        win_h = self.frames.win.h
        self.assertNotEqual(self.px(0, (400, 1450)), (255, 255, 255))           # 0.0 s: no headline yet
        self.assertNotEqual(self.px(12, (400, 1450)), (255, 255, 255))          # 0.4 s: not yet
        self.assertEqual(self.px(45, (400, 1450)), (255, 255, 255))             # 1.5 s: in place, fully opaque
        a, b = np.asarray(self.frames.frame(20)), np.asarray(self.frames.frame(45))
        self.assertFalse(np.array_equal(a[1300:1500], b[1300:1500]))            # still moving at 0.67 s
        self.assertGreater(win_h, 0)

    def test_push_in_moves_the_photo(self):
        a = np.asarray(self.frames.frame(0))[:900].astype(int)
        b = np.asarray(self.frames.frame(96))[:900].astype(int)
        self.assertGreater(np.abs(a - b).mean(), 2)

    def test_crossfades_and_held_slides(self):
        cover_end = 105
        self.assertEqual(self.px(cover_end, (10, 10)), (200, 0, 0))             # detail 1 held
        mid = self.px(cover_end + 90 - R.XFADE // 2, (10, 10))                  # detail 1 -> 2 crossfade
        self.assertTrue(0 < mid[0] < 200 and 0 < mid[1] < 200, mid)
        self.assertEqual(self.px(self.frames.total - 1, (10, 10)), (0, 0, 200))  # the end card is last
        self.assertIs(self.frames.frame(150), self.frames.frame(160))            # held slides are not re-made


@unittest.skipUnless(chrome_available() and FFMPEG, "needs Chrome/Playwright and ffmpeg")
class RenderReel(unittest.TestCase):
    def test_reel_meets_instagrams_spec(self):
        out = Path(tempfile.mkdtemp())
        rows = []
        res = R.render_reel(post(2), str(out), report=rows, verbose=False)
        self.assertEqual(res["problems"], [])
        probe = next(r for r in rows if r["type"] == "reel")
        self.assertEqual((probe["video_codec"], probe["width"], probe["height"], probe["pix_fmt"], probe["fps"]),
                         ("h264", 1080, 1920, "yuv420p", 30.0))
        self.assertEqual((probe["audio_codec"], probe["sample_rate"], probe["channels"]), ("aac", 48000, 2))
        self.assertTrue(probe["faststart"])
        self.assertFalse(probe["elst"])
        self.assertAlmostEqual(probe["duration"], 11.0, delta=0.1)
        self.assertIn(b"rc_lookahead=10", (out / "reel.mp4").read_bytes()[:200000])   # x264's veryfast preset
        vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out / "reel.mp4"), "-af", "volumedetect",
                              "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
        max_db = float(vol.split("max_volume:")[1].split("dB")[0])
        self.assertLess(max_db, -80)                                              # silent: no one else's audio
        for name in ("reel_cover.jpg", "preview_00.5s.jpg", "preview_04.0s.jpg", "preview_07.0s.jpg",
                     "preview_last.jpg"):
            self.assertEqual(Image.open(out / name).size, (1080, 1920), name)
        pages = [r for r in rows if r["type"] != "reel"]
        self.assertEqual([r["type"] for r in pages], ["cover", "detail", "detail", "end"])
        for r in pages:
            self.assertEqual(V.vertical_problems([r]), [], r["page"])
            self.assertGreaterEqual(r["min_font_px"], 30, r["page"])
        # the layers composite back to the story card (photo + overlay + text at rest)
        cover = np.asarray(Image.open(out / "reel_cover.jpg").convert("RGB"), dtype=int)
        last_cover_frame = np.asarray(R.video_frame(str(out / "reel.mp4"), 96), dtype=int)
        self.assertLess(np.abs(cover[1150:1600] - last_cover_frame[1150:1600]).mean(), 6)

    def test_one_detail_and_cli(self):
        import json
        d = Path(tempfile.mkdtemp())
        (d / "post.json").write_text(json.dumps(post(1)))
        res = R.render_reel(post(1), str(d / "out"), previews=(), verbose=False)
        self.assertAlmostEqual(res["duration"], 9.5)
        self.assertEqual(res["previews"], [])
        code = subprocess.run([sys.executable, "-m", "cardkit.reel", str(d / "post.json"), str(d / "cli")],
                              cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
        self.assertEqual(code.returncode, 0, code.stderr)
        self.assertTrue(json.loads(code.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
