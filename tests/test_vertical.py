"""cardkit.vertical (9:16 Story cards) and pipeline.framing's VERTICAL frame. No real person anywhere: synthetic
noise images, synthetic face boxes, and tests/fixtures/commons_wagonr.jpg (a car). Chrome-only tests are skipped
when Playwright/Chrome isn't installed. Run: python3 -m pytest -q tests"""
import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from cardkit import vertical as V  # noqa: E402
from pipeline import framing as F  # noqa: E402
from pipeline.framing import Face  # noqa: E402
from tests.lane_helpers import CAR, CAR_CREDIT, chrome_available, noise_image  # noqa: E402


def push_map(box, z, origin=V.PUSH_ORIGIN):
    """Where a box in the zoom-1 photo window lands at push-in zoom z (the reel's cover)."""
    ox, oy = origin
    x0, y0, x1, y1 = box
    return [ox + (x0 - ox) * z, oy + (y0 - oy) * z, ox + (x1 - ox) * z, oy + (y1 - oy) * z]


class Geometry(unittest.TestCase):
    def test_crop_matches_framing_pixel_for_pixel(self):
        rng = random.Random(7)
        for _ in range(400):
            w, h = rng.randint(600, 6000), rng.randint(600, 6000)
            focal = (rng.random(), rng.random())
            zoom = rng.choice([1.0, 1.0, rng.uniform(1.0, 2.5)])
            box, out_h = V.vertical_crop_box(w, h, focal, zoom)
            l, t, cw, ch, fh = F.frame_crop(w, h, focal, zoom, F.VERTICAL)
            self.assertEqual(box, (l, t, l + cw, t + ch), (w, h, focal, zoom))
            self.assertEqual(out_h, fh)
            self.assertTrue(0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h)

    def test_same_width_as_the_cover_crop(self):
        for w, h, zoom in [(1920, 1281, 1.0), (1920, 1281, 1.3), (1920, 2560, 1.0), (3000, 3000, 1.1)]:
            cover = F.cardkit_crop(w, h, (0.5, 0.5), zoom)
            box, _ = V.vertical_crop_box(w, h, (0.5, 0.5), zoom)
            self.assertAlmostEqual(box[2] - box[0], cover[2], delta=1)

    def test_taller_only_when_the_source_allows(self):
        self.assertEqual(V.vertical_crop_box(1920, 1281)[1], 1350)          # landscape: the cover's own 4:5
        self.assertEqual(V.vertical_crop_box(1920, 2560)[1], 1440)          # 3:4 portrait: taller
        self.assertEqual(V.vertical_crop_box(2000, 2400)[1], 1350)          # 5:6: the 4:5 crop already uses it all
        self.assertEqual(V.vertical_crop_box(1920, 1281, zoom=1.1)[1], 1440)  # zoomed in: room above and below

    def test_window_and_push_in_always_fill_the_frame(self):
        path = Path(tempfile.mkdtemp()) / "white.png"
        Image.new("RGB", (1600, 2000), (255, 255, 255)).save(path)
        win = V.PhotoWindow(str(path))
        for z in (1.0, 1.03, 1.06):
            im = win.at(z)
            self.assertEqual(im.size, (1080, win.h))
            self.assertGreater(np.asarray(im).min(), 250, f"edge showing at zoom {z}")

    def test_window_at_zoom_1_is_the_planned_crop(self):
        win = V.PhotoWindow(str(CAR), (0.5, 0.5), 1.0)
        box, h = V.vertical_crop_box(1920, 1281)
        ref = Image.open(CAR).convert("RGB").crop(box).resize((1080, h), Image.LANCZOS)
        diff = np.abs(np.asarray(win.at(1.0), dtype=int) - np.asarray(ref, dtype=int)).mean()
        self.assertLess(diff, 3.0)


class VerticalFraming(unittest.TestCase):
    def check(self, plan, w, h, faces):
        for f in faces:
            out = F.map_cover(F.padded(f, w, h), plan.crop, plan.out_h)
            self.assertTrue(F.face_ok(out, F.VERTICAL), out)
            for z in (1.0, 1.06):                                   # the reel's push-in keeps it clear too
                x0, y0, x1, y1 = push_map(out, z)
                self.assertGreaterEqual(y0, V.LOGO_TOP + V.LOGO_H + 20, f"face under the logo at zoom {z}")
                self.assertLessEqual(y1, 1000, f"face runs into the text block at zoom {z}")
                self.assertTrue(0 <= x0 and x1 <= 1080, f"face cut by the edge at zoom {z}")

    def test_face_in_a_portrait_lands_in_the_band(self):
        w, h = 2400, 3200
        faces = [Face(1100, 1400, 260, 300)]
        plan, why = F.plan_cover(w, h, faces, frame=F.VERTICAL)
        self.assertIsNotNone(plan, why)
        self.assertEqual((plan.frame, plan.out_h), ("vertical", 1440))
        self.check(plan, w, h, faces)

    def test_face_high_in_a_landscape_zooms(self):
        w, h = 3000, 2000
        faces = [Face(1400, 260, 160, 180)]
        plan, why = F.plan_cover(w, h, faces, frame=F.VERTICAL)
        self.assertIsNotNone(plan, why)
        self.assertGreater(plan.zoom, 1.0)
        self.check(plan, w, h, faces)

    def test_impossible_face_fails_with_the_vertical_band(self):
        plan, why = F.plan_cover(1500, 1000, [Face(700, 4, 120, 150)], frame=F.VERTICAL)
        self.assertIsNone(plan)
        self.assertIn("380-880", why)

    def test_edge_margin_is_wider_than_the_cover(self):
        self.assertGreater(F.VERTICAL.edge_margin, F.COVER.edge_margin)

    def test_plan_image_and_render_input(self):
        img = noise_image(700, 900)                                 # small: needs > 1.15x, so it is pre-enlarged
        plan = F.plan_image(img, faces=[], use_saliency=False, frame=F.VERTICAL)
        self.assertEqual(plan.frame, "vertical")
        path, focal, zoom = F.render_input(img, plan, Path(tempfile.mkdtemp()))
        self.assertEqual(Image.open(path).size, (1080, plan.out_h))
        self.assertEqual((tuple(focal), zoom), ((0.5, 0.5), 1.0))
        self.assertEqual(path.name, "vertical_source.png")
        # the pre-enlarged window is exactly what cardkit then shows
        box, h = V.vertical_crop_box(1080, plan.out_h, focal, zoom, plan.out_h)
        self.assertEqual((box, h), ((0, 0, 1080, plan.out_h), plan.out_h))

    def test_car_has_no_faces_and_frames(self):
        plan = F.plan_image(Image.open(CAR).convert("RGB"), faces=[], frame=F.VERTICAL)
        self.assertEqual(plan.faces_out, [])
        self.assertLessEqual(plan.upscale, F.MAX_UPSCALE)

    def test_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(F, "DETECTOR", lambda im: []):
            code = F._cli([str(CAR), tempfile.mkdtemp(), "--vertical"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["photo_h"], 1350)


class Problems(unittest.TestCase):
    def test_vertical_problems(self):
        clean = {"page": "cover", "type": "cover", "collisions": [], "ui_zone": [], "outside": [], "truncated": [],
                 "left_edges": {"kicker": 64, "headline": 64, "date": 64}, "min_font_px": 30, "scale": 1.0}
        self.assertEqual(V.vertical_problems([clean]), [])
        bad = dict(clean, overflow=True, collisions=[["credit", "site"]], ui_zone=["date y 1590-1620"],
                   left_edges={"kicker": 64, "headline": 70}, min_font_px=21, scale=2.4, truncated=["sources"])
        text = " | ".join(V.vertical_problems([bad]))
        for want in ("does not fit", "credit collides with site", "UI zone", "left edge", "21px", "2.40x",
                     "cut short"):
            self.assertIn(want, text)


def post_for(photo, credit=CAR_CREDIT, headline="WagonR Stays India's Best-Selling Car in October", **kw):
    return {"acct": kw.pop("acct", "idlyautomotive"), "slug": "t", "date": "10 Nov 2026",
            "sources": ["Autocar India", "Rushlane"],
            "slides": [{"type": "cover", "headline": headline, "photo": str(photo), "photo_credit": credit,
                        "focal": (0.5, 0.5), "zoom": 1.0, **kw},
                       {"type": "detail", "stat": "23,747", "stat_label": "WagonR sales in October",
                        "bullets": ["Brezza second, 1,311 units behind", "Top five: WagonR, Brezza, Nexon"]}]}


@unittest.skipUnless(chrome_available(), "Chrome/Playwright not available: cardkit can't render here")
class StoryCard(unittest.TestCase):
    def render(self, post):
        out = Path(tempfile.mkdtemp()) / "story.jpg"
        rows = []
        V.render_story(post, str(out), report=rows, verbose=False)
        return Image.open(out), rows[0]

    def test_layout_rules(self):
        im, row = self.render(post_for(CAR))
        self.assertEqual((im.size, im.format), ((1080, 1920), "JPEG"))
        self.assertEqual(V.vertical_problems([row]), [])
        self.assertEqual(set(row["left_edges"].values()), {V.VSIDE})          # kicker, headline, date
        self.assertGreaterEqual(row["min_font_px"], 30)
        for name, (x0, y0, x1, y1) in row["boxes"].items():
            self.assertGreaterEqual(y0, V.SAFE_TOP, name)
            self.assertLessEqual(y1, V.SAFE_BOTTOM, name)
        lx0, ly0, lx1, _ = row["boxes"]["logo"]
        self.assertAlmostEqual((lx0 + lx1) / 2, 540, delta=2)                  # logo top-centre
        self.assertEqual(row["photo_h"], 1350)
        arr = np.asarray(im.convert("RGB"), dtype=int)
        self.assertTrue(np.all(np.abs(arr[1640:1900] - 10) <= 4))             # bottom UI zone: brand background
        self.assertGreater(arr[0:200].std(), 20)                               # the photo runs to the very top
        self.assertLess(abs(row["solid_from"] - row["text_top"] - V.SOLID_BELOW_TEXT_TOP), 2)

    def test_full_bleed_no_side_fill(self):
        """Never a boxed photo on a blurred copy: the photo's own detail reaches both side edges."""
        path = Path(tempfile.mkdtemp()) / "noise.jpg"
        noise_image(2400, 1600, seed=3).save(path, quality=92)
        im, row = self.render(post_for(path, credit="Photo: test"))
        arr = np.asarray(im.convert("L"), dtype=float)
        for x in (0, 1, 1078, 1079):
            col = arr[320:900, x]
            self.assertGreater(np.abs(np.diff(col)).mean(), 4, f"column {x} looks blurred or flat")

    def test_portrait_source_is_taller(self):
        path = Path(tempfile.mkdtemp()) / "tall.jpg"
        noise_image(1500, 2000, seed=5).save(path, quality=92)
        _, row = self.render(post_for(path, credit="Photo: test"))
        self.assertEqual(row["photo_h"], 1440)
        self.assertEqual(V.vertical_problems([row]), [])

    def test_vertical_plan_overrides_cover_crop(self):
        path = Path(tempfile.mkdtemp()) / "noise.jpg"
        noise_image(2400, 1600, seed=4).save(path, quality=92)
        _, row = self.render(post_for(path, credit="Photo: test",
                                      vertical={"focal": [0.2, 0.5], "zoom": 1.25}))
        box, h = V.vertical_crop_box(2400, 1600, (0.2, 0.5), 1.25)
        self.assertEqual((row["crop"], row["photo_h"]), (list(box), h))

    def test_long_headline_overflows_and_is_reported(self):
        _, row = self.render(post_for(CAR, headline=" ".join(["Extraordinarily"] * 12)))
        self.assertTrue(row["overflow"])
        self.assertTrue(any("does not fit" in p for p in V.vertical_problems([row])))

    def test_long_credit_moves_down_and_still_clears_the_zones(self):
        credit = "Photo: Jane Doe-Somebody Longname / Wikimedia Commons, CC BY-SA 4.0 (cropped)"
        _, row = self.render(post_for(CAR, credit=credit))
        self.assertGreater(row["credit_bottom"], V.CREDIT_Y)
        self.assertEqual(V.vertical_problems([row]), [])

    def test_absurd_credit_is_reported(self):
        _, row = self.render(post_for(CAR, credit="Photo: " + "Very Long Credit " * 12))
        self.assertTrue(V.vertical_problems([row]))

    def test_every_account_logo(self):
        for acct in ("idlynews", "idlytech", "idlyhype", "idlynerd"):
            _, row = self.render(post_for(CAR, acct=acct))
            self.assertEqual(V.vertical_problems([row]), [], acct)

    def test_cli(self):
        d = Path(tempfile.mkdtemp())
        (d / "post.json").write_text(json.dumps(post_for(CAR)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = V.main(["story", str(d / "post.json"), str(d / "story.jpg")])
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(json.loads(out.getvalue())["ok"])
        self.assertEqual(Image.open(d / "story.jpg").size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
