"""Credits everywhere: the cover's vertical credit is required, every other hype slide gets a quiet
credit/source line above the footer rule (without colliding), and captions end with the credit line.
Images are synthetic or the Commons car fixture. Run: python3 -m unittest discover tests"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cardkit import render as R  # noqa: E402
from pipeline import editorial  # noqa: E402
from tests.lane_helpers import CAR, CAR_CREDIT, chrome_available  # noqa: E402
from tests.test_editorial import GOOD_CAPTION, GOOD_SCORE  # noqa: E402

POST = {"acct": "idlytech", "slug": "t", "date": "10 Nov 2026", "sources": ["CNBC", "Yahoo Finance"]}


class CreditLineText(unittest.TestCase):
    def test_sources_on_text_slides(self):
        self.assertEqual(R.credit_line_text(POST, {"type": "detail"}), "Sources: CNBC, Yahoo Finance")

    def test_slide_override_and_image_credit(self):
        self.assertEqual(R.credit_line_text(POST, {"credit_line": "Source: SIAM"}), "Source: SIAM")
        self.assertEqual(R.credit_line_text(POST, {"photo_credit": "Image: Netflix India (official trailer)"}),
                         "Image: Netflix India (official trailer)")
        self.assertEqual(R.credit_line_text(POST, {"photo": {"credit": CAR_CREDIT}}), CAR_CREDIT)

    def test_string_sources_and_none(self):
        self.assertEqual(R.credit_line_text({**POST, "sources": "Sources: BBC, DW"}, {}), "Sources: BBC, DW")
        self.assertEqual(R.credit_line_text({**POST, "sources": "BBC"}, {}), "Sources: BBC")
        self.assertEqual(R.credit_line_text({"acct": "idlytech"}, {}), "")

    def test_detail_html_has_the_line_above_the_rule(self):
        html = R.hype_detail_html(POST, {"type": "detail", "stat": "₹10", "bullets": ["a b", "c d"]})
        self.assertIn("<div class='srcline'>Sources: CNBC, Yahoo Finance</div><div class='line'>", html)
        self.assertIn(".srcline{display:block;font:500 16px/1.25 Inter", html)
        self.assertIn("rgba(255,255,255,.45)", html)

    def test_cover_credit_required(self):
        post = {**POST, "slides": [{"type": "cover", "headline": "x", "photo": str(CAR), "photo_credit": ""}]}
        with self.assertRaises(ValueError) as cm:
            R._check_hype(post)
        self.assertIn("photo_credit", str(cm.exception))
        post["slides"][0]["photo_credit"] = CAR_CREDIT
        R._check_hype(post)


class CaptionCredit(unittest.TestCase):
    def test_must_end_with_credit(self):
        cap = GOOD_CAPTION.replace("\n\nPhoto: Jane Doe / Wikimedia Commons, CC BY-SA 4.0", "") + \
            "\n\nPhoto: Jane Doe / Wikimedia Commons, CC BY-SA 4.0\n\n#extra"
        errs, _ = editorial.caption_problems(cap)
        self.assertTrue(any("must end with the credit line" in e for e in errs))

    def test_agency_and_official_credit_forms(self):
        base = GOOD_CAPTION.rsplit("\n\n", 1)[0]
        for credit in ("Image: Netflix India (official trailer)", "Image: Maruti Suzuki", "AP Photo/Jane Doe",
                       "Photo: PTI", "ANI Photo", "Photo: IANS"):
            errs, _ = editorial.post_problems(f"{base}\n\n{credit}", GOOD_SCORE)
            self.assertEqual(errs, [], credit)

    def test_with_credit_replaces_trailing_credit(self):
        cap = editorial.with_credit(GOOD_CAPTION, "Image: Maruti Suzuki")
        self.assertTrue(cap.endswith("#idlytech\n\nImage: Maruti Suzuki"))
        self.assertNotIn("Jane Doe", cap)
        self.assertEqual(editorial.with_credit("Text.\n\n#a #b", "ANI Photo"), "Text.\n\n#a #b\n\nANI Photo")


@unittest.skipUnless(chrome_available(), "Chrome/Playwright not available")
class RenderedCreditLine(unittest.TestCase):
    """Rendered for real: the line sits between the bullets and the footer rule and touches neither."""

    def test_detail_and_custom_slides(self):
        orig_detail, orig_check = R.hype_detail_html, R._check_hype

        def custom(post, slide):          # a custom kind like the review posts': own markup, own .foot2 footer
            if slide.get("type") != "custom":
                return orig_detail(post, slide)
            logo = Path(R.LOGOS) / "tech_white.png"
            css = R._hype_css() + (".x .body{position:absolute;left:72px;right:72px;top:96px;bottom:176px;"
                                   "overflow:hidden;font:600 40px/1.2 Inter}"
                                   ".foot2{position:absolute;left:72px;right:72px;bottom:56px}"
                                   ".foot2 .line{height:2px;background:rgba(255,255,255,.18);margin-bottom:24px}"
                                   ".foot2 .r{display:flex;align-items:center}.foot2 img{height:58px}")
            body = "".join(f"<p>Row {i} of a long custom list</p>" for i in range(30))
            return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>"
                    f"<div class='s x'><div class='body'>{body}</div><div class='foot2'><div class='line'></div>"
                    f"<div class='r'><img src='file://{logo}'></div></div></div></body></html>")

        R.hype_detail_html = custom
        R._check_hype = lambda p: None
        try:
            post = {**POST, "slides": [
                {"type": "cover", "headline": "WagonR is India's best-seller", "photo": str(CAR),
                 "photo_credit": CAR_CREDIT},
                {"type": "detail", "stat": "23,747", "stat_label": "WagonR sales in October, the most of any car",
                 "bullets": ["Brezza second, just 1,311 units behind", "Nexon, Baleno and Dzire round out the top five",
                             "Maruti held six of the top ten spots"]},
                {"type": "custom"}]}
            report = []
            with tempfile.TemporaryDirectory() as d:
                R.render_cards([post], d, template="hype", report=report, verbose=False)
        finally:
            R.hype_detail_html, R._check_hype = orig_detail, orig_check
        cover, detail, cust = report
        self.assertEqual(cover["credit_line"], CAR_CREDIT)
        for r in (detail, cust):
            self.assertEqual(r["credit_line"], "Sources: CNBC, Yahoo Finance")
            self.assertEqual(r["credit_collision"], [], r)
            self.assertTrue(r["credit_inside"], r)
            x0, y0, x1, y1 = r["credit_rect"]
            self.assertGreaterEqual(x0, 48)
            self.assertLessEqual(y1, 1350 - 56 - 58 - 24)          # above the footer rule
            self.assertGreaterEqual(y0, 1350 - 190 if r is detail else 1350 - 176)   # below the body
        self.assertFalse(detail["credit_injected"])
        self.assertTrue(cust["credit_injected"])


if __name__ == "__main__":
    unittest.main()
