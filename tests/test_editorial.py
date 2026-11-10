"""Unit tests for the editorial rules and the 12/14 gate.  Run: python3 -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial, publish  # noqa: E402

GOOD_CAPTION = """Jio's new ₹10,000 prepaid plan covers three years on one recharge, about ₹278 a month.

You get 2.5GB a day, unlimited calls and 100 SMS a day for 1,095 days.

Would you pay ₹10,000 up front to skip recharges for three years?

Full story on idly.news (link in bio).

#Jio #Recharge #Telecom #TechIndia #idlytech

Photo: Jane Doe / Wikimedia Commons, CC BY-SA 4.0"""

GOOD_SCORE = {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 1, "alone": 1,
              "total": 12, "notes": "original: shared photo; alone: needs the caption for dates"}

GOOD_CARD = {"tag": "TELECOM · INDIA", "stat": "₹10,000", "stat_label": "three years of Jio on one recharge",
             "headline": "Jio's new plan runs three years on one recharge",
             "bullets": ["2.5GB a day and unlimited calls", "Works out to about ₹278 a month"],
             "photo": "x.jpg", "photo_credit": "Photo: Jane Doe / Wikimedia Commons"}


def story(title, dek=""):
    return {"title": title, "dek": dek, "gist": []}


class GossipFilter(unittest.TestCase):
    def test_blocks_todays_gossip(self):
        for title in ["Alia Bhatt shares Diwali photos with Ranbir Kapoor and daughter Raha",
                      "Katrina Kaif and Vicky Kaushal share first photo of son Vihaan on Diwali",
                      "Kareena Kapoor says she is against Botox and enjoying her 40s",
                      "Actor ties the knot in a private ceremony",
                      "Star sparks dating rumours after dinner outing"]:
            self.assertEqual(editorial.screen_story(story(title))[0], "block", title)

    def test_flags_borderline_for_review(self):
        for title in ["BTS' V sends Diwali wishes in Hindi and reacts to AI kurta photos",
                      "WhatsApp lets you share photos in full HD",
                      "Minister's son arrested in land case"]:
            self.assertEqual(editorial.screen_story(story(title))[0], "review", title)

    def test_passes_news(self):
        for title in ["Delhi air turns severe after Diwali fireworks, average AQI at 376",
                      "Tesla launches Robotaxi service in San Antonio, its eighth city",
                      "Analysts are expecting a rate cut in December",
                      "Jio launches ₹10,000 prepaid plan with three-year validity"]:
            self.assertEqual(editorial.screen_story(story(title))[0], "ok", title)


class CardCopy(unittest.TestCase):
    def test_good_card(self):
        self.assertEqual(editorial.card_problems(GOOD_CARD), [])

    def test_limits(self):
        bad = {**GOOD_CARD, "tag": "Telecom", "stat": "big", "headline": " ".join(["word"] * 11),
               "bullets": ["one"], "photo_credit": ""}
        errs = " ".join(editorial.card_problems(bad))
        for needle in ("tag", "stat must", "headline", "2-3 bullets", "photo_credit"):
            self.assertIn(needle, errs)


class Caption(unittest.TestCase):
    def test_good_caption(self):
        errs, _ = editorial.post_problems(GOOD_CAPTION, GOOD_SCORE)
        self.assertEqual(errs, [])

    def test_from_n_reports_banned(self):
        errs, _ = editorial.caption_problems(GOOD_CAPTION + "\nFrom 3 reports: NDTV, BBC, DW.")
        self.assertTrue(any("From N reports" in e for e in errs))

    def test_bait_and_hype(self):
        errs, _ = editorial.caption_problems(GOOD_CAPTION.replace(
            "You get", "Tag a friend: you get") + "\nA game-changing, AI-powered plan.")
        joined = " ".join(errs)
        self.assertIn("engagement bait", joined)
        self.assertIn("hype wording", joined)

    def test_needs_link_photo_hashtags_question(self):
        errs, _ = editorial.caption_problems("Just a fact line.")
        self.assertEqual(len(errs), 4)

    def test_send_and_save_bait_banned(self):
        for line in ("Send this to the friend who forgets to recharge.", "Save this for your next recharge.",
                     "Tell us below.", "Tell us in the comments.", "Let us know below.",
                     "Let us know in the comments."):
            errs, _ = editorial.post_problems(GOOD_CAPTION.replace("You get", line + "\n\nYou get"), GOOD_SCORE)
            self.assertTrue(any("engagement bait" in e for e in errs), line)

    def test_no_idly_article_caption(self):
        cap = GOOD_CAPTION.replace("Full story on idly.news (link in bio).", "Sources: CNBC, Yahoo Finance.")
        self.assertEqual(editorial.caption_problems(cap, idly_article=False)[0], [])
        errs, _ = editorial.caption_problems(GOOD_CAPTION, idly_article=False)
        self.assertTrue(any("must not send readers" in e for e in errs))
        self.assertTrue(any("missing the line" in e for e in editorial.caption_problems(cap)[0]))

    def test_send_two_needs_no_send_line(self):
        errs, _ = editorial.post_problems(GOOD_CAPTION, GOOD_SCORE)
        self.assertEqual(errs, [])


class ScoreGate(unittest.TestCase):
    def test_twelve_passes(self):
        self.assertTrue(editorial.passes_gate(GOOD_SCORE))

    def test_eleven_fails(self):
        low = {**GOOD_SCORE, "alone": 0, "total": 11}
        self.assertFalse(editorial.passes_gate(low))
        with self.assertRaises(publish.GateRefused):
            publish.gate(low, force_below_gate=False)

    def test_wrong_total_or_missing_notes_fails(self):
        self.assertFalse(editorial.passes_gate({**GOOD_SCORE, "total": 14}))
        self.assertFalse(editorial.passes_gate({**GOOD_SCORE, "notes": ""}))
        self.assertFalse(editorial.passes_gate({**GOOD_SCORE, "hook": 3, "total": 13}))
        self.assertFalse(editorial.passes_gate(None))

    def test_publish_post_refuses_below_gate_even_in_dry_run(self):
        low = {**GOOD_SCORE, "alone": 0, "total": 11}
        with self.assertRaises(publish.GateRefused):
            publish.publish_post("idlytech", ["https://example.com/a.jpg"], GOOD_CAPTION, score=low,
                                 story_id=1, dry_run=True)


if __name__ == "__main__":
    unittest.main()


def test_images_first_rejects_text_only_cover_credit():
    base = ("Headline line.\n\nOne genuine question here?\n\nSources: A, B.\n\n#a #b #c #d\n\n")
    for credit in ("Image: idly graphic (data: BikeAdvice, Rushlane)",
                   "Image: idly design (type and a chart of the ratings; no photo used)."):
        errs, _ = editorial.caption_problems(base + credit, idly_article=False)
        assert any("images first" in e for e in errs), credit
    errs, _ = editorial.caption_problems(base + "Photo: Ultraviolette", idly_article=False)
    assert not any("images first" in e for e in errs)
