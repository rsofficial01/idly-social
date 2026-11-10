"""cardkit.reel: the motion reel's timeline, count-ups, charts, encoder settings and Instagram's file checks. The full
render needs Chrome and ffmpeg and uses only non-person images (tests/fixtures/commons_wagonr.jpg, a car).
Run: python3 -m pytest -q tests"""
import json
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
from tests.lane_helpers import CAR, CAR_CREDIT, chrome_available, mp4_bytes  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
TOP5 = [["WagonR", 23747], ["Brezza", 22436], ["Tata Nexon", 21966], ["Baleno", 20919], ["Dzire", 20649]]


def post(details=2, chart=False):
    slides = [{"type": "cover", "headline": "WagonR Stays India's Best-Selling Car in October", "photo": str(CAR),
               "photo_credit": CAR_CREDIT, "focal": (0.5, 0.5), "zoom": 1.0}]
    slides += [{"type": "detail", "stat": s, "stat_label": "WagonR Sales in October",
                "bullets": ["Brezza Second, 1,311 Units Behind", "Top Five: WagonR, Brezza, Nexon"]}
               for s in ("23,747", "+86%", "7 of 10")[:details]]
    if chart:
        slides[-1] = {"type": "detail", "stat_label": "October's Top 5", "chart": TOP5, "chart_unit": "Units sold"}
    return {"acct": "idlyautomotive", "slug": "t", "date": "10 Nov 2026", "sources": ["Autocar India", "Rushlane"],
            "slides": slides}


class Timeline(unittest.TestCase):
    def test_ten_to_fourteen_seconds_no_scene_over_3_5(self):
        for n in (1, 2):
            segs = R.timeline(n)
            total = sum(f for _, f in segs) / R.FPS
            self.assertTrue(10.0 <= total <= R.REEL_MAX_S, (n, total))
            self.assertTrue(all(f / R.FPS <= R.SCENE_MAX_S for _, f in segs), segs)
            self.assertEqual((segs[0][0], segs[-1][0]), ("cover", "end"))
        self.assertEqual([(s, round(f / R.FPS, 2)) for s, f in R.timeline(2)],
                         [("cover", 3.2), ("detail1", 3.4), ("detail2", 3.5), ("end", 2.0)])
        with self.assertRaises(ValueError):
            R.timeline(0)                                             # a cover alone can't carry 10 s

    def test_transitions_push_or_cut_never_crossfade(self):
        self.assertEqual([R._enter(s) for s, _ in R.timeline(2)], ["open", "push", "push", "cut"])
        self.assertFalse(hasattr(R, "XFADE"))

    def test_pick_details(self):
        p = post(3)
        self.assertEqual([s["stat"] for s in R.pick_details(p)], ["23,747", "+86%"])
        self.assertEqual([s["stat"] for s in R.pick_details(p, [3, 1])], ["7 of 10", "23,747"])
        with self.assertRaises(ValueError):
            R.pick_details(p, [4])
        with self.assertRaises(ValueError):
            R.pick_details(p, [1, 2, 3])
        self.assertEqual(R.pick_details(post(0)), [])

    def test_every_reveal_finishes_well_inside_its_scene(self):
        infos = {"cover": {"head_lines": 3, "kick_chars": 16},
                 "detail1": {"stat": True, "stat_spec": R.count_spec("23,747"), "label_lines": 2, "rule": True,
                             "bullets": 3},
                 "detail2": {"label_lines": 1, "rule": True, "unit": True,
                             "rows": [{"frac": 1, "spec": None}] * R.CHART_MAX_ROWS},
                 "end": {}}
        for name, frames in R.timeline(2):
            cues = R._cues(name, infos[name], frames / R.FPS, R.PUSH_S)
            self.assertLess(R._settled(cues), frames / R.FPS - 0.25, name)
            kinds = {c["k"] for c in cues}
            self.assertIn("drift" if name != "cover" else "zoom", kinds, name)   # holds keep moving
            for c in cues:
                if c["k"] == "lines":
                    self.assertEqual(c["stagger"], 0.12)                  # lines rise 120 ms apart
        cover = R._cues("cover", infos["cover"], 3.2, R.PUSH_S)
        zoom = next(c for c in cover if c["k"] == "zoom")
        self.assertGreater(zoom["z1"], 1.05)
        drifts = sorted(c["y1"] for c in cover if c["k"] == "drift")
        self.assertNotEqual(drifts[0], drifts[1])                         # text and chrome at different speeds
        self.assertNotEqual(zoom["dy"], drifts[0])                        # ... and the photo at a third (parallax)


class CountUps(unittest.TestCase):
    def test_formats(self):
        cases = {
            "23,747": ("", 23747, 0, "indian", ""),
            "2,24,000": ("", 224000, 0, "indian", ""),
            "224,000": ("", 224000, 0, "western", ""),
            "+86%": ("+", 86, 0, "none", "%"),
            "−4.27%": ("−", 4.27, 2, "none", "%"),
            "₹2.69 lakh": ("₹", 2.69, 2, "none", " lakh"),
            "₹2,000 crore": ("₹", 2000, 0, "indian", " crore"),
            "$192B": ("$", 192, 0, "none", "B"),
            "7 of 10": ("", 7, 0, "none", " of 10"),
        }
        for text, (pre, value, dec, group, suf) in cases.items():
            sp = R.count_spec(text)
            self.assertEqual((sp["pre"], sp["value"], sp["dec"], sp["group"], sp["suf"]), (pre, value, dec, group, suf),
                             text)
            self.assertEqual(R.count_text(sp, 1.0), text)                 # the last frame is the exact stat
        for text in ("2026", "Nov 17", "2-1", "1:30", "Q3", "0%", "", "No. 1"):
            self.assertIsNone(R.count_spec(text), text)                   # these never count

    def test_never_zero_monotonic_and_in_format(self):
        for text in ("23,747", "2,24,000", "+86%", "−4.27%", "₹2.69 lakh", "$192B", "−0.4%"):
            sp = R.count_spec(text)
            seq = [R.count_text(sp, e / 200) for e in range(0, 201)]
            vals = [R.count_spec(t)["value"] if R.count_spec(t) else None for t in seq]
            self.assertTrue(all(v and v > 0 for v in vals), (text, seq[:3]))
            self.assertEqual(vals, sorted(vals), text)
            self.assertEqual(seq[-1], text)
            self.assertTrue(all(t.startswith(sp["pre"]) and t.endswith(sp["suf"]) for t in seq), text)
            if sp["dec"]:
                self.assertTrue(all(len(t.split(".")[1].rstrip(sp["suf"])) == sp["dec"] for t in seq), text)
        sp = R.count_spec("2,24,000")
        self.assertEqual(R.count_text(sp, 0.5512), "1,23,469")            # Indian grouping on the way up
        self.assertEqual(R.count_text(R.count_spec("224,000"), 0.5512), "123,469")
        self.assertEqual(R.count_text(R.count_spec("₹2.69 lakh"), 0.5), "₹1.84 lakh")   # 1 + 1.69 x 0.5 = 1.84499...
        self.assertEqual(R.count_text(R.count_spec("+86%"), 0.5), "+44%")          # 43.5: a tie rounds up, as in JS
        for text, first in (("₹2.69 lakh", "₹1.0"), ("−4.27%", "−1.0"), ("23,747", "1")):
            self.assertTrue(R.count_text(R.count_spec(text), 0.0).startswith(first), text)     # counts from 1
        self.assertEqual(R.count_text(R.count_spec("0.4%"), 0.0), "0.1%")         # under 1: from one step

    def test_count_texts_frame_by_frame(self):
        sp = R.count_spec("23,747")
        texts = R.count_texts(sp, R.STAT_AT, R.STAT_COUNT_S, 115)
        self.assertEqual(texts[-1], "23,747")
        self.assertNotIn("0", texts)
        self.assertGreater(len(texts), 30)                                # it really counts, frame by frame


class Charts(unittest.TestCase):
    def test_rows(self):
        rows, unit = R.chart_rows({"chart": TOP5, "chart_unit": "Units sold"})
        self.assertEqual(unit, "Units sold")
        self.assertEqual([r["text"] for r in rows], ["23,747", "22,436", "21,966", "20,919", "20,649"])
        self.assertEqual(rows[0]["frac"], 1.0)
        self.assertAlmostEqual(rows[4]["frac"], 20649 / 23747)            # bars start at zero
        self.assertEqual([r["lead"] for r in rows], [True, False, False, False, False])
        rows, unit = R.chart_rows({"chart": {"rows": [["A", 224000], ["B", "1,10,500"]], "unit": "units"}})
        self.assertEqual(([r["text"] for r in rows], unit), (["2,24,000", "1,10,500"], "units"))
        rows, _ = R.chart_rows({"chart": [["Nexon", "₹8.0 lakh"], ["Brezza", "₹8.69 lakh"]]})
        self.assertEqual([r["lead"] for r in rows], [False, True])
        self.assertIsNone(R.chart_rows({"stat": "1"}))

    def test_bad_charts(self):
        for chart in ([["Only", 1]], [["A", 1]] * 9, [["A", "lots"], ["B", 2]], [["A", 1, 2], ["B", 2]],
                      [["A", "₹1 lakh"], ["B", "$2B"]], [["A", 0], ["B", 0]], [["", 1], ["B", 2]],
                      [["A", True], ["B", 2]]):
            with self.assertRaises(ValueError, msg=chart):
                R.chart_rows({"chart": chart})

    def test_reel_accepts_a_chart_only_slide_the_feed_does_not(self):
        from cardkit.render import _check_hype
        p = post(2, chart=True)
        _check_hype(p, reel=True)
        with self.assertRaisesRegex(ValueError, "chart alone is for reels"):
            _check_hype(p)


class Encoder(unittest.TestCase):
    def test_encoder_settings(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg not installed")
        cmd = " ".join(R.ffmpeg_cmd(12.1, "out.mp4"))
        for want in ("-f image2pipe -c:v mjpeg -framerate 30 -i pipe:0", "-preset veryfast", "-c:v libx264",
                     "-pix_fmt yuv420p", "-r 30", "anullsrc=channel_layout=stereo:sample_rate=48000", "-c:a aac",
                     "-movflags +faststart", "-use_editlist 0", "open-gop=0", f"scale={V.VW}:{V.VH}",
                     "out_color_matrix=bt709"):
            self.assertIn(want, cmd)
        self.assertNotIn("-i music", cmd)

    def test_mp4_boxes(self):
        d = Path(tempfile.mkdtemp())
        for name, data, faststart, elst in (("ok", mp4_bytes(), True, False),
                                            ("late", mp4_bytes(faststart=False), False, False),
                                            ("elst", mp4_bytes(elst=True), True, True)):
            (d / f"{name}.mp4").write_bytes(data)
            info = R.mp4_boxes(str(d / f"{name}.mp4"))
            self.assertEqual((info["faststart"], info["elst"]), (faststart, elst), name)


@unittest.skipUnless(chrome_available() and FFMPEG, "needs Chrome/Playwright and ffmpeg")
class RenderReel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp())
        cls.rows = []
        cls.res = R.render_reel(post(2, chart=True), str(cls.out), report=cls.rows, verbose=False)

    def test_reel_meets_instagrams_spec(self):
        self.assertEqual(self.res["problems"], [])
        probe = next(r for r in self.rows if r["type"] == "reel")
        self.assertEqual((probe["video_codec"], probe["width"], probe["height"], probe["pix_fmt"], probe["fps"]),
                         ("h264", 1080, 1920, "yuv420p", 30.0))
        self.assertEqual((probe["audio_codec"], probe["sample_rate"], probe["channels"]), ("aac", 48000, 2))
        self.assertTrue(probe["faststart"])
        self.assertFalse(probe["elst"])
        self.assertAlmostEqual(probe["duration"], 12.1, delta=0.1)
        self.assertIn(b"rc_lookahead=10", (self.out / "reel.mp4").read_bytes()[:200000])   # x264's veryfast
        vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(self.out / "reel.mp4"), "-af", "volumedetect",
                              "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
        self.assertLess(float(vol.split("max_volume:")[1].split("dB")[0]), -80)   # silent: no one else's audio
        for name in ("reel_cover.jpg", "preview_00.5s.jpg", "preview_04.0s.jpg", "preview_07.0s.jpg",
                     "preview_last.jpg"):
            self.assertEqual(Image.open(self.out / name).size, (1080, 1920), name)
        self.assertLess(self.res["render_s"], 180)

    def test_every_scene_inside_the_reel_safe_zone(self):
        pages = [r for r in self.rows if r["type"] != "reel"]
        self.assertEqual([r["type"] for r in pages], ["cover", "detail", "detail", "end"])
        zone = V.REEL_SAFE_ZONE
        for r in pages:
            self.assertEqual(V.vertical_problems([r]), [], r["page"])
            self.assertGreaterEqual(r["min_font_px"], 30, r["page"])
            self.assertEqual(r["zone"], "reel")
            for name, (x0, y0, x1, y1) in r["boxes"].items():          # Instagram's Reels UI zones
                self.assertTrue(zone.top <= y0 and y1 <= zone.bottom, (r["page"], name, y0, y1))
                if y1 > zone.right_from:
                    self.assertLessEqual(x1, zone.right, (r["page"], name, "under the Reels buttons"))
            if r["type"] in ("cover", "detail"):
                self.assertEqual(len(set(r["left_edges"].values())), 1, r["left_edges"])   # one left edge
        stat, chart = pages[1], pages[2]
        self.assertLessEqual(stat["max_band"], V.MAX_EMPTY_BAND)
        self.assertGreaterEqual(stat["label"], 52)
        self.assertGreaterEqual(stat["bullet"], 40)
        self.assertGreater(stat["stat"], 250)
        self.assertEqual((chart["chart"], chart["counts"]), (5, False))
        self.assertLessEqual(chart["max_band"], V.MAX_EMPTY_BAND)
        self.assertEqual(sum(1 for k in chart["boxes"] if k.startswith("row")), 5)
        cover = pages[0]
        self.assertLessEqual(cover["boxes"]["date"][3], zone.bottom)       # headline and footer sit above y 1380
        self.assertGreater(cover["boxes"]["headline"][3], zone.bottom - 120)
        self.assertLess(cover["fade_start"], 700)
        self.assertIn("credit", cover["boxes"])                            # the vertical credit stays
        end = pages[3]["boxes"]
        mid = (min(b[1] for b in end.values()) + max(b[3] for b in end.values())) / 2
        self.assertAlmostEqual(mid, (zone.top + zone.bottom) / 2, delta=30)

    def test_counters_never_show_zero_and_end_exact(self):
        reel = next(r for r in self.rows if r["type"] == "reel")
        finals = {c["id"]: c for c in reel["counters"]}
        self.assertEqual(finals["detail1.stat"]["last"], "23,747")
        self.assertEqual([finals[f"detail2.bar.{i}"]["last"] for i in range(5)],
                         ["23,747", "22,436", "21,966", "20,919", "20,649"])
        for c in reel["counters"]:
            self.assertGreater(R.count_spec(c["first"])["value"], 0, c)
            self.assertEqual(c["last"], c["final"], c)
        self.assertLessEqual(reel["longest_still_frames"], R.STILL_MAX_S * R.FPS)   # nothing sits still

    def test_frames_move_and_cut_where_planned(self):
        video = str(self.out / "reel.mp4")
        f = {n: np.asarray(R.video_frame(video, n), dtype=float) for n in (60, 61, 165, 166, 302, 303)}
        for a in (60, 165):                              # holds: still moving, but gently
            d = np.abs(f[a + 1] - f[a]).mean()
            self.assertTrue(0.02 < d < 4, (a, d))
        cut = np.abs(f[303] - f[302]).mean()             # the hard cut to the end card
        self.assertGreater(cut, 5)
        self.assertGreater(f[303].max(), 60)             # ... lands on the logo, not on an empty frame
        # the cover still is a real frame of the reel (same headline and footer)
        cover = np.asarray(Image.open(self.out / "reel_cover.jpg").convert("RGB"), dtype=float)
        start = next(r for r in self.rows if r["type"] == "cover")["settled_at"]
        frame = np.asarray(R.video_frame(video, round((start + 0.05) * R.FPS)), dtype=float)
        self.assertLess(np.abs(cover[1150:1400] - frame[1150:1400]).mean(), 6)

    def test_js_formatter_matches_python(self):
        import asyncio

        from playwright.async_api import async_playwright

        from cardkit.render import _chrome
        specs = [R.count_spec(t) for t in ("23,747", "2,24,000", "224,000", "₹2.69 lakh", "−4.27%", "+86%")]
        es = [0, 0.001, 0.05, 0.33, 0.5512, 0.9, 0.999, 1]

        async def run():
            async with async_playwright() as pw:
                b = await pw.chromium.launch(executable_path=_chrome(), args=["--no-sandbox"])
                pg = await b.new_page()
                await pg.add_script_tag(content=R.REEL_JS)
                out = await pg.evaluate("([S, E]) => S.map(s => E.map(e => fmt(s, e)))", [specs, es])
                await b.close()
                return out
        got = asyncio.run(run())
        self.assertEqual(got, [[R.count_text(s, e) for e in es] for s in specs])

    def test_one_detail_and_cli(self):
        d = Path(tempfile.mkdtemp())
        (d / "post.json").write_text(json.dumps(post(1)))
        res = R.render_reel(post(1), str(d / "out"), previews=(), verbose=False)
        self.assertAlmostEqual(res["duration"], 10.0)
        self.assertEqual((res["previews"], res["problems"]), ([], []))
        code = subprocess.run([sys.executable, "-m", "cardkit.reel", str(d / "post.json"), str(d / "cli"),
                               "--sheet", str(d / "sheet.jpg")],
                              cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
        self.assertEqual(code.returncode, 0, code.stderr)
        self.assertTrue(json.loads(code.stdout)["ok"])
        self.assertEqual(Image.open(d / "sheet.jpg").size[0] > 1000, True)
        with self.assertRaisesRegex(ValueError, "at least one detail slide"):
            R.render_reel(post(0), str(d / "none"), verbose=False)


if __name__ == "__main__":
    unittest.main()
