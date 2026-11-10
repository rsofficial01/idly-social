"""Face-aware framing: geometry with SYNTHETIC face boxes (no real faces anywhere).
Run: python3 -m unittest discover tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from pipeline import framing as F  # noqa: E402
from pipeline.framing import Face  # noqa: E402
from tests.lane_helpers import CAR, noise_image  # noqa: E402


def check_plan(test, plan, w, h, faces):
    """Every padded face, mapped the way cardkit really crops, is inside the band and clear of the edges."""
    test.assertLessEqual(plan.upscale, F.MAX_UPSCALE + 1e-9)
    for f in faces:
        box = F.padded(f, w, h)
        if plan.mode == "cover":
            crop = F.cardkit_crop(w, h, plan.focal, plan.zoom)
            out = F.map_cover(box, crop)
        else:
            s = plan.upscale
            out = [round(box[0] * s), round(box[1] * s) + plan.band_top, round(box[2] * s),
                   round(box[3] * s) + plan.band_top]
        test.assertTrue(F.face_ok(out), f"{plan.mode}: face {out} outside y {F.FACE_TOP}-{F.FACE_BOTTOM}")
        test.assertGreaterEqual(out[1], F.LOGO_BOX[3], "a face sits under the logo")


class CoverGeometry(unittest.TestCase):
    def test_no_faces_centre_crop(self):
        plan = F.plan_cover(1920, 1281, [])[0]
        self.assertEqual(plan.mode, "cover")
        self.assertEqual(plan.zoom, 1.0)
        self.assertAlmostEqual(plan.focal[0], 0.5, places=2)
        self.assertAlmostEqual(plan.upscale, 1080 / 1025, places=2)

    def test_face_in_the_middle_moves_into_the_band(self):
        w, h = 2400, 3000                                 # 4:5 portrait: the crop can move vertically
        faces = [Face(1100, 1500, 220, 260)]
        plan, why = F.plan_cover(w, h, faces)
        self.assertIsNotNone(plan, why)
        check_plan(self, plan, w, h, faces)

    def test_face_at_the_very_top_needs_zoom(self):
        w, h = 3000, 2000                                 # wide: zoom 1 can't move up, so it zooms in
        faces = [Face(1400, 200, 160, 180)]
        plan, why = F.plan_cover(w, h, faces)
        self.assertIsNotNone(plan, why)
        self.assertGreater(plan.zoom, 1.0)
        check_plan(self, plan, w, h, faces)

    def test_two_faces_side_by_side(self):
        w, h = 3200, 2400
        faces = [Face(1100, 700, 200, 240), Face(1700, 760, 200, 240)]
        plan, why = F.plan_cover(w, h, faces)
        self.assertIsNotNone(plan, why)
        check_plan(self, plan, w, h, faces)

    def test_faces_too_far_apart_vertically(self):
        w, h = 2000, 2500
        faces = [Face(900, 200, 200, 240), Face(900, 2100, 200, 240)]
        plan, why = F.plan_cover(w, h, faces)
        self.assertIsNone(plan)
        self.assertIn("190-702", why)

    def test_face_cut_by_source_edge(self):
        plan, why = F.plan_cover(2400, 3000, [Face(-20, 900, 200, 240)])
        self.assertIsNone(plan)
        self.assertIn("cut off", why)

    def test_too_small_for_cover(self):
        plan, why = F.plan_cover(1280, 720, [])          # 576px crop: 1.875x
        self.assertIsNone(plan)
        self.assertIn("upscale", why)

    def test_zoom_never_exceeds_upscale_limit(self):
        plan, why = F.plan_cover(1300, 1625, [Face(600, 40, 100, 120)])   # needs zoom, little headroom
        if plan:
            self.assertLessEqual(plan.upscale, F.MAX_UPSCALE + 1e-9)
        else:
            self.assertTrue(why)

    def test_matches_cardkit_crop_pixel_for_pixel(self):
        """Put a marker where a synthetic face is; cardkit's own crop must land it where the plan says."""
        from cardkit.render import _hype_crop
        w, h = 3000, 2000
        face = Face(1400, 200, 160, 180)
        plan = F.plan_cover(w, h, [face])[0]
        im = Image.new("RGB", (w, h), (0, 0, 0))
        cx, cy = round(face.x + face.w / 2), round(face.y + face.h / 2)
        im.paste((255, 0, 0), (cx - 6, cy - 6, cx + 6, cy + 6))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.png"
            im.save(p)
            out, scale = _hype_crop(str(p), plan.focal, plan.zoom)
        arr = np.asarray(out)
        ys, xs = np.where((arr[:, :, 0] > 180) & (arr[:, :, 1] < 80))
        crop = F.cardkit_crop(w, h, plan.focal, plan.zoom)
        ex, ey = F.map_cover((cx, cy, cx, cy), crop)[:2]
        self.assertLess(abs(xs.mean() - ex), 4)
        self.assertLess(abs(ys.mean() - ey), 4)
        self.assertTrue(F.FACE_TOP <= ys.mean() <= F.FACE_BOTTOM)


class LetterboxGeometry(unittest.TestCase):
    def test_trailer_still(self):
        w, h = 1280, 720                                   # YouTube maxresdefault
        faces = [Face(560, 180, 140, 170)]
        plan, why = F.plan_letterbox(w, h, faces)
        self.assertIsNotNone(plan, why)
        self.assertGreaterEqual(plan.band_top, F.LOGO_CLEAR)
        self.assertEqual(plan.band_height, 608)
        check_plan(self, plan, w, h, faces)

    def test_face_low_in_frame_moves_band_up_but_not_under_logo(self):
        w, h = 1280, 720
        faces = [Face(600, 470, 120, 140)]
        plan, why = F.plan_letterbox(w, h, faces)
        self.assertIsNotNone(plan, why)
        self.assertGreaterEqual(plan.band_top, F.LOGO_CLEAR)
        check_plan(self, plan, w, h, faces)

    def test_face_at_bottom_edge_fails(self):
        plan, why = F.plan_letterbox(1280, 720, [Face(600, 600, 100, 110)])
        self.assertIsNone(plan)

    def test_face_at_side_edge_fails(self):
        plan, why = F.plan_letterbox(1280, 720, [Face(2, 200, 120, 140)])
        self.assertIsNone(plan)

    def test_too_narrow(self):
        plan, why = F.plan_letterbox(880, 495, [])
        self.assertIsNone(plan)
        self.assertIn("upscale", why)

    def test_compose(self):
        src = noise_image(1280, 720, seed=3)
        plan = F.plan_letterbox(1280, 720, [])[0]
        out = F.compose_letterbox(src, plan)
        self.assertEqual(out.size, (1080, 1350))
        band = np.asarray(out.crop((0, plan.band_top, 1080, plan.band_top + plan.band_height))).astype(int)
        ref = np.asarray(src.resize((1080, plan.band_height), Image.LANCZOS)).astype(int)
        self.assertLess(np.abs(band - ref).mean(), 2)
        top = np.asarray(out.crop(F.LOGO_BOX).convert("L"))   # blurred, darkened: calm under the logo
        self.assertLess(top.std(), 25)


class PlanImage(unittest.TestCase):
    def test_falls_back_to_letterbox_then_fails(self):
        img = noise_image(1280, 720)
        self.assertEqual(F.plan_image(img, []).mode, "letterbox")
        with self.assertRaises(F.FramingError) as cm:
            F.plan_image(img, [Face(600, 20, 100, 110), Face(600, 590, 100, 110)])
        self.assertEqual(len(cm.exception.reasons), 2)

    def test_too_small(self):
        with self.assertRaises(F.FramingError):
            F.plan_image(noise_image(800, 600), [])

    def test_salient_block_under_the_logo_is_avoided(self):
        """Busy text-like block at top centre, calm elsewhere: the crop must not put the logo on it."""
        w, h = 1500, 2600
        arr = np.full((h, w, 3), 90, np.uint8)
        rng = np.random.default_rng(7)
        arr[0:420, 450:1050] = rng.integers(0, 255, (420, 600, 3), dtype=np.uint8)   # 'title text'
        img = Image.fromarray(arr)
        plan = F.plan_image(img, [])
        if plan.mode == "cover":
            self.assertLessEqual(plan.logo_saliency, F.SALIENT_LOGO)
            crop = F.cardkit_crop(w, h, plan.focal, plan.zoom)
            self.assertGreater(crop[1], 300, "the crop should move down, off the busy block")

    def test_detector_stub_is_used(self):
        calls = []
        old = F.DETECTOR
        F.DETECTOR = lambda im: calls.append(im.size) or [Face(900, 400, 150, 180)]
        try:
            plan = F.plan_image(noise_image(1920, 1281))
        finally:
            F.DETECTOR = old
        self.assertEqual(calls, [(1920, 1281)])
        self.assertEqual(len(plan.faces_src), 1)
        check_plan(self, plan, 1920, 1281, [Face(900, 400, 150, 180)])


class YuNet(unittest.TestCase):
    """The real detector, on a photo of a car (no person): it must find no face."""

    def setUp(self):
        try:
            F.ensure_model()
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"YuNet model not available offline: {e}")

    def test_car_has_no_faces(self):
        img = Image.open(CAR).convert("RGB")
        self.assertEqual(F.detect_faces(img), [])
        plan = F.plan_image(img)
        self.assertEqual(plan.mode, "cover")


if __name__ == "__main__":
    unittest.main()
