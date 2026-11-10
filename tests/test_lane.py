"""The official image lane: spec schema, queue moves, render-pending, approve/reject, publish-approved, the git
merge helpers, and an end-to-end dry run with a non-person image (a Wikimedia Commons photo of a car, served
by a fake fetcher as if it were an official newsroom's og:image). Nothing touches the network or Instagram.
Run: python3 -m unittest discover tests"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import framing, gitsync, lane, official_image, publish  # noqa: E402
from pipeline.common import now_utc  # noqa: E402
from tests.lane_helpers import (CAR, CAR_CREDIT, CAPTION, GOOD_SCORE, REEL_CALLS, REVIEWER_SCORE,  # noqa: E402
                                FakeFetcher, chrome_available, formats_file, make_spec, og_routes,
                                stub_reel_renderer, stub_renderer, stub_story_renderer)


class LaneCase(unittest.TestCase):
    """A private queue and reports folder per test; fake web; stub renderer and face detector."""
    real_renderer = False
    real_detector = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(lane, "QUEUE", root / "queue"),
                        mock.patch.object(lane, "REPORTS", root / "reports"),
                        mock.patch.object(official_image, "FETCHER", FakeFetcher(og_routes())),
                        # the real state/posted.json must not leak into tests (30-minute gap per account)
                        mock.patch("pipeline.common.POSTED_FILE", root / "state" / "posted.json"),
                        # stories and reels on for these tests (config/formats.json itself keeps them paused)
                        mock.patch.object(publish, "FORMATS_FILE", formats_file(root))]
        if not self.real_renderer:
            self.patches.append(mock.patch.object(lane, "RENDERER", stub_renderer))
            self.patches.append(mock.patch.object(lane, "STORY_RENDERER", stub_story_renderer))
            self.patches.append(mock.patch.object(lane, "REEL_RENDERER", stub_reel_renderer))
        if not self.real_detector:
            self.patches.append(mock.patch.object(framing, "DETECTOR", lambda im: []))
        for p in self.patches:
            p.start()
        self.q = root / "queue"
        self.reports = root / "reports"

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def write_spec(self, slug, spec):
        path = self.q / "pending" / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lane.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def reasons(self, slug):
        return json.loads((self.q / "rejected" / slug / "reasons.json").read_text())["reasons"]


class SpecSchema(LaneCase):
    def test_good_spec(self):
        self.assertEqual(lane.validate_spec(make_spec(), "wagonr-oct"), [])

    def test_wire_spec_and_fallbacks(self):
        spec = make_spec(image={"resolver": "licensed_wire", "query": "WagonR launch Delhi", "agencies": ["ap", "pti"],
                                "fallback": [{"resolver": "og_image_official",
                                              "ref": "https://www.marutisuzuki.com/press/x"}]})
        self.assertEqual(lane.validate_spec(spec, "wagonr-oct"), [])

    def test_bad_specs(self):
        cases = {
            "unknown account": make_spec(account="idlysports"),
            "missing ref": make_spec(image={"resolver": "youtube_official"}),
            "wire needs a query": make_spec(image={"resolver": "licensed_wire", "ref": "x" * 20}),
            "reuters agency": make_spec(image={"resolver": "licensed_wire", "query": "x y z", "agencies": ["reuters"]}),
            "detail needs sources": {k: v for k, v in make_spec().items() if k != "sources"},
            "below gate": make_spec(scores={"self": {**GOOD_SCORE, "alone": 0, "total": 11}}),
            "wrong total": make_spec(scores={"self": {**GOOD_SCORE, "total": 14}}),
            "extra field": make_spec(colour="red"),
            "article needs id": make_spec(story_id=None),
            "future": make_spec(created_at=(now_utc() + timedelta(hours=2)).isoformat()),
            "own collaborator": make_spec(collaborators=["idlyautomotive"]),
        }
        for name, spec in cases.items():
            self.assertTrue(lane.validate_spec(spec, "wagonr-oct"), name)
        self.assertTrue(lane.validate_spec(make_spec(), "Bad Slug!"))
        self.assertTrue(lane.validate_spec(make_spec(slug="other"), "wagonr-oct"))

    def test_no_article_spec(self):
        cap = make_spec()["caption"].replace("Full story on idly.news (link in bio).", "Sources: SIAM, Autocar India.")
        self.assertEqual(lane.validate_spec(make_spec(story_id=None, idly_article=False, caption=cap), "x-y-z"), [])

    def test_validate_cli(self):
        good = self.write_spec("good-one", make_spec())
        bad = self.write_spec("bad-one", make_spec(account="nope"))
        code, out, _ = self.run_cli("validate", str(good), str(bad))
        self.assertEqual(code, 1)
        self.assertIn("good-one.json: ok", out)
        self.assertIn("bad-one.json: PROBLEMS", out)


class RenderPending(LaneCase):
    def test_renders_and_moves(self):
        self.write_spec("wagonr-oct", make_spec())
        code, _, err = self.run_cli("render-pending")
        self.assertEqual(code, 0, err)
        rdir = self.q / "rendered" / "wagonr-oct"
        self.assertEqual(sorted(p.name for p in rdir.iterdir()),
                         ["01.jpg", "02.jpg", "render_report.json", "spec.json", "story.jpg"])
        self.assertFalse((self.q / "pending" / "wagonr-oct.json").exists())
        spec = json.loads((rdir / "spec.json").read_text())
        self.assertTrue(spec["caption_final"].endswith("\n\nImage: Maruti Suzuki"))
        self.assertEqual(spec["image_credit"], "Image: Maruti Suzuki")
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertEqual(rep["resolver"], "og_image_official")
        self.assertEqual(rep["source"]["source_url"], "https://www.marutisuzuki.com/press/wagonr-october")
        self.assertTrue(rep["source"]["image_url"].endswith("/wagonr-front.jpg"))
        self.assertEqual(rep["framing"]["mode"], "cover")
        self.assertLessEqual(rep["upscale"], 1.2)
        self.assertEqual(rep["faces"], [])
        self.assertIn("checks", rep)
        log = next(self.reports.glob("lane-*.md")).read_text()
        self.assertIn("rendered · @idlyautomotive wagonr-oct", log)

    def test_idempotent(self):
        spec = make_spec()
        self.write_spec("wagonr-oct", spec)
        self.run_cli("render-pending")
        first = (self.q / "rendered" / "wagonr-oct" / "spec.json").read_text()
        self.write_spec("wagonr-oct", spec)            # e.g. a crash left the pending file behind
        code, _, err = self.run_cli("render-pending")
        self.assertEqual(code, 0)
        self.assertIn("skipped: already rendered", err)
        self.assertFalse((self.q / "pending" / "wagonr-oct.json").exists())
        self.assertEqual((self.q / "rendered" / "wagonr-oct" / "spec.json").read_text(), first)
        self.assertEqual(self.run_cli("render-pending")[0], 0)    # empty queue: nothing to do

    def test_slug_reuse_with_new_content_rejected(self):
        self.write_spec("wagonr-oct", make_spec())
        self.run_cli("render-pending")
        self.write_spec("wagonr-oct", make_spec(headline="A different headline for the same slug"))
        self.run_cli("render-pending")
        self.assertIn("already used", self.reasons("wagonr-oct")[0])
        self.assertTrue((self.q / "rendered" / "wagonr-oct" / "01.jpg").exists())

    def test_invalid_and_stale_rejected(self):
        self.write_spec("bad-spec", make_spec(account="nope"))
        self.write_spec("old-news", make_spec(created_at=(now_utc() - timedelta(hours=9)).isoformat()))
        self.write_spec("old-ok", make_spec(created_at=(now_utc() - timedelta(hours=30)).isoformat(),
                                            evergreen=True))
        (self.q / "pending" / "broken.json").write_text("{not json")
        self.run_cli("render-pending")
        self.assertIn("account", self.reasons("bad-spec")[0])
        self.assertIn("stale", self.reasons("old-news")[0])
        self.assertIn("not valid JSON", self.reasons("broken")[0])
        self.assertTrue((self.q / "rendered" / "old-ok").exists())
        self.assertTrue((self.q / "rejected" / "old-news" / "spec.json").exists())

    def test_resolver_failure_rejected_with_reasons(self):
        self.write_spec("fan-site", make_spec(image={"resolver": "og_image_official",
                                                     "ref": "https://www.pinkvilla.com/entertainment/x"}))
        self.run_cli("render-pending")
        self.assertIn("news outlet", self.reasons("fan-site")[0])

    def test_transient_failure_stays_pending(self):
        routes = {"https://www.marutisuzuki.com/press/wagonr-october": (503, "text/html", b"busy")}
        with mock.patch.object(official_image, "FETCHER", FakeFetcher(routes)):
            self.write_spec("wagonr-oct", make_spec())
            code, _, _ = self.run_cli("render-pending")
        self.assertEqual(code, 0)
        self.assertTrue((self.q / "pending" / "wagonr-oct.json").exists())

    def test_framing_failure_rejected(self):
        with mock.patch.object(framing, "DETECTOR", lambda im: [framing.Face(900, 3, 120, 140),
                                                                framing.Face(900, 1130, 120, 140)]):
            self.write_spec("wagonr-oct", make_spec())
            self.run_cli("render-pending")
        self.assertTrue(any("framing" in r for r in self.reasons("wagonr-oct")))

    def test_caption_credit_replaced_and_checked(self):
        cap = make_spec()["caption"] + "\n\nPhoto: something the session guessed"
        self.write_spec("wagonr-oct", make_spec(caption=cap))
        self.run_cli("render-pending")
        spec = json.loads((self.q / "rendered" / "wagonr-oct" / "spec.json").read_text())
        self.assertNotIn("guessed", spec["caption_final"])
        self.assertTrue(spec["caption_final"].endswith("Image: Maruti Suzuki"))

    def test_caption_problems_rejected(self):
        self.write_spec("baity", make_spec(caption=make_spec()["caption"].replace(
            "Which car", "Tag a friend! Which car")))
        self.run_cli("render-pending")
        self.assertIn("engagement bait", " ".join(self.reasons("baity")))

    def test_lock_held(self):
        self.write_spec("wagonr-oct", make_spec())
        with lane.queue_lock() as got:
            self.assertTrue(got)
            code, _, err = self.run_cli("render-pending")
        self.assertEqual(code, 0)
        self.assertIn("holds the queue lock", err)
        self.assertTrue((self.q / "pending" / "wagonr-oct.json").exists())


class Review(LaneCase):
    def render(self, slug="wagonr-oct", **over):
        self.write_spec(slug, make_spec(**over))
        self.run_cli("render-pending")
        return self.q / "rendered" / slug

    def score_file(self, score):
        p = Path(self.tmp.name) / "score.json"
        p.write_text(json.dumps(score))
        return str(p)

    def test_show_is_blind(self):
        self.render()
        code, out, _ = self.run_cli("show", "wagonr-oct")
        self.assertEqual(code, 0)
        packet = json.loads(out)
        self.assertNotIn("scores", packet)
        self.assertNotIn('"self"', out)
        self.assertEqual(packet["image"]["credit"], "Image: Maruti Suzuki")

    def test_approve(self):
        self.render()
        code, out, _ = self.run_cli("approve", "wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        self.assertEqual(code, 0)
        doc = json.loads((self.q / "approved" / "wagonr-oct.json").read_text())
        self.assertEqual(doc["reviewer"]["total"], 13)
        self.assertIn("12/14", out)                  # the lower of self 12 and reviewer 13

    def test_approve_below_gate_rejects(self):
        self.render()
        low = {**REVIEWER_SCORE, "send": 0, "total": 11}
        self.run_cli("approve", "wagonr-oct", "--score-file", self.score_file(low))
        self.assertFalse((self.q / "approved" / "wagonr-oct.json").exists())
        self.assertFalse((self.q / "rendered" / "wagonr-oct").exists())
        self.assertIn("below the 12 gate", self.reasons("wagonr-oct")[0])

    def test_approve_bad_score(self):
        self.render()
        code, _, err = self.run_cli("approve", "wagonr-oct", "--score-file",
                                    self.score_file({**REVIEWER_SCORE, "total": 9}))
        self.assertEqual(code, 2)
        self.assertIn("total", err)

    def test_reject(self):
        self.render()
        self.run_cli("approve", "wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        self.run_cli("reject", "wagonr-oct", "--reason", "headline runs into the car's grille")
        self.assertFalse((self.q / "approved" / "wagonr-oct.json").exists())
        self.assertFalse((self.q / "rendered" / "wagonr-oct").exists())
        self.assertEqual(self.reasons("wagonr-oct"), ["headline runs into the car's grille"])
        self.assertTrue((self.q / "rejected" / "wagonr-oct" / "render_report.json").exists())


class PublishApproved(Review):
    def approve(self, slug="wagonr-oct", **over):
        self.render(slug, **over)
        self.run_cli("approve", slug, "--score-file", self.score_file(REVIEWER_SCORE))

    def no_tokens(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("IG_TOKEN_") and k != "IG_SYSTEM_TOKEN"}
        return mock.patch.dict(os.environ, env, clear=True)

    def test_dry_run_posts_nothing(self):
        self.approve()
        with mock.patch.object(publish, "append_posted") as ap, mock.patch.object(publish, "connect") as conn:
            code, out, err = self.run_cli("publish-approved", "--dry-run")
        self.assertEqual(code, 0, err)
        ap.assert_not_called()
        conn.assert_not_called()
        self.assertIn("[dry-run] @idlyautomotive", out)
        self.assertIn("queue/rendered/wagonr-oct/01.jpg", out)
        self.assertIn("queue/rendered/wagonr-oct/02.jpg", out)
        self.assertTrue((self.q / "approved" / "wagonr-oct.json").exists())   # still waiting for the real run

    def test_missing_token_skips_with_report_line(self):
        self.approve()
        with self.no_tokens():
            code, _, _ = self.run_cli("publish-approved")
        self.assertEqual(code, 0)
        self.assertTrue((self.q / "approved" / "wagonr-oct.json").exists())
        log = next(self.reports.glob("lane-*.md")).read_text()
        self.assertIn("IG_TOKEN_IDLYAUTOMOTIVE secret is not set", log)

    def test_stale_at_publish_rejected(self):
        self.approve(created_at=(now_utc() - timedelta(hours=7, minutes=59)).isoformat())
        spec_path = self.q / "rendered" / "wagonr-oct" / "spec.json"
        spec = json.loads(spec_path.read_text())
        spec["created_at"] = (now_utc() - timedelta(hours=8, minutes=5)).isoformat()
        spec_path.write_text(json.dumps(spec))
        self.run_cli("publish-approved", "--dry-run")
        self.assertIn("stale", self.reasons("wagonr-oct")[0])

    def test_publishes_and_moves(self):
        self.approve()
        self.approve("brezza-oct", headline="Brezza jumps 86% to finish second in October", story_id=990002)
        self.approve("nexon-oct", account="idlytech", story_id=990003,
                     caption=make_spec()["caption"].replace("#idlyautomotive", "#idlytech"))
        posted = []

        def fake_publish(account, media, caption, **kw):
            posted.append((account, media, caption, kw))
            return {"status": "posted", "permalink": f"https://www.instagram.com/p/{len(posted)}/", "media_id": "1"}

        client = mock.Mock()
        client.find_recent.return_value = None
        env = {"IG_TOKEN_IDLYAUTOMOTIVE": "x", "IG_TOKEN_IDLYTECH": "y"}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(publish, "publish_post", fake_publish), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            code, _, err = self.run_cli("publish-approved")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(a for a, *_ in posted), ["idlyautomotive", "idlytech"])   # one per account per run
        account, media, caption, kw = next(p for p in posted if p[0] == "idlyautomotive")
        self.assertTrue(all(u.startswith("https://raw.githubusercontent.com/rsofficial01/idly-social/main/queue/rendered/")
                            for u in media))
        self.assertEqual(kw["slot"], "lane")
        self.assertEqual(kw["score"]["total"], 12)                    # the lower score goes to the gate
        self.assertEqual(kw["record_extra"]["lane"], "official-image")
        self.assertTrue(caption.endswith("Image: Maruti Suzuki"))
        self.assertEqual(len(list((self.q / "posted").iterdir())), 2)
        self.assertEqual(len(list((self.q / "approved").glob("*.json"))), 1)       # the second automotive waits
        done = next((self.q / "posted").iterdir())
        self.assertTrue({"01.jpg", "02.jpg", "spec.json", "render_report.json", "approved.json",
                         "result.json"} <= {p.name for p in done.iterdir()})

    def test_duplicate_guard(self):
        self.approve()
        client = mock.Mock()
        client.find_recent.return_value = "17999"
        client.permalink.return_value = "https://www.instagram.com/p/already/"
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post") as pp, \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            self.run_cli("publish-approved")
        pp.assert_not_called()
        result = json.loads((self.q / "posted" / "wagonr-oct" / "result.json").read_text())
        self.assertTrue(result["recovered"])

    def test_waits_for_public_images(self):
        self.approve()
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post") as pp, \
                mock.patch("pipeline.run_day.url_ready", return_value=(False, "HTTP 404")):
            code, _, err = self.run_cli("publish-approved")
        self.assertEqual(code, 0)
        pp.assert_not_called()
        self.assertIn("waiting", err)
        self.assertTrue((self.q / "approved" / "wagonr-oct.json").exists())


class LaneStories(PublishApproved):
    """story.jpg: rendered with the post, posted right after it, and never able to hold up or change the feed post."""

    def test_story_rendered_with_the_post(self):
        rdir = self.render()
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertEqual(rep["story"]["status"], "rendered")
        self.assertEqual(rep["story"]["framing"]["frame"], "vertical")
        publish.check_story_jpeg(rdir / "story.jpg")
        _, out, _ = self.run_cli("show", "wagonr-oct")
        self.assertTrue(json.loads(out)["story"].endswith("queue/rendered/wagonr-oct/story.jpg"))

    def test_story_off(self):
        rdir = self.render(story=False)
        self.assertFalse((rdir / "story.jpg").exists())
        self.assertEqual(json.loads((rdir / "render_report.json").read_text())["story"]["status"], "off")

    def test_story_framing_failure_keeps_the_post(self):
        real = framing.plan_image

        def plan(im, faces=None, use_saliency=True, frame=framing.COVER):
            if frame is framing.VERTICAL:
                raise framing.FramingError(["vertical: no crop keeps every face inside y 380-880"])
            return real(im, faces, use_saliency, frame)

        with mock.patch.object(framing, "plan_image", plan):
            rdir = self.render()
        self.assertTrue((rdir / "01.jpg").exists())
        self.assertFalse((rdir / "story.jpg").exists())
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertIn("380-880", rep["story"]["reasons"][0])
        self.assertIn("no story", next(self.reports.glob("lane-*.md")).read_text())

    def test_story_layout_problem_keeps_the_post(self):
        def bad(post, out, report):
            stub_story_renderer(post, out, report)
            report[-1]["collisions"] = [["credit", "site"]]
            return str(out)

        with mock.patch.object(lane, "STORY_RENDERER", bad):
            rdir = self.render()
        self.assertTrue((rdir / "02.jpg").exists())
        self.assertFalse((rdir / "story.jpg").exists())
        self.assertIn("credit collides with site", json.loads((rdir / "render_report.json").read_text())
                      ["story"]["reasons"][0])

    def publish_run(self, story_effect=None, **approve_kw):
        self.approve(**approve_kw)
        client = mock.Mock()
        client.find_recent.return_value = None
        feed = {"status": "posted", "permalink": "https://www.instagram.com/p/F/", "media_id": "1790"}
        story = mock.Mock(side_effect=story_effect, return_value={"status": "posted", "media_id": "1791",
                                                                  "permalink": ""})
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post", return_value=feed), \
                mock.patch.object(publish, "publish_story", story), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            code, _, err = self.run_cli("publish-approved")
        self.assertEqual(code, 0, err)
        return story, json.loads((self.q / "posted" / "wagonr-oct" / "result.json").read_text())

    def test_story_posted_after_the_feed_post(self):
        story, result = self.publish_run()
        args, kw = story.call_args
        self.assertEqual(args[0], "idlyautomotive")
        self.assertTrue(args[1].endswith("/queue/rendered/wagonr-oct/story.jpg"))   # still public at that moment
        self.assertEqual((kw["story_of"], kw["slot"]), ("1790", "lane"))
        self.assertEqual(result["status"], "posted")
        self.assertEqual(result["story"]["media_id"], "1791")
        self.assertIn("story · @idlyautomotive wagonr-oct", next(self.reports.glob("lane-*.md")).read_text())

    def test_story_failure_never_touches_the_feed_post(self):
        _, result = self.publish_run(story_effect=publish.IGError("container st1 is ERROR: bad image"))
        self.assertEqual(result["status"], "posted")
        self.assertEqual(result["permalink"], "https://www.instagram.com/p/F/")
        self.assertEqual(result["story"]["status"], "failed")
        self.assertIn("story failed", next(self.reports.glob("lane-*.md")).read_text())

    def test_reviewer_can_drop_the_story(self):
        self.render()
        self.run_cli("approve", "wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE), "--no-story")
        story = mock.Mock()
        client = mock.Mock()
        client.find_recent.return_value = None
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post", return_value={"status": "posted", "media_id": "1"}), \
                mock.patch.object(publish, "publish_story", story), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            self.run_cli("publish-approved")
        story.assert_not_called()

    def test_dry_run_shows_the_story_call(self):
        self.approve()
        with mock.patch.object(publish, "append_posted") as ap, mock.patch.object(publish, "connect") as conn:
            code, out, err = self.run_cli("publish-approved", "--dry-run")
        self.assertEqual(code, 0, err)
        ap.assert_not_called()
        conn.assert_not_called()
        self.assertIn("media_type=STORIES", out)
        self.assertIn("queue/rendered/wagonr-oct/story.jpg", out)

    def test_stories_paused_by_the_switch(self):
        formats_file(self.tmp.name, stories=False)
        story, result = self.publish_run()
        story.assert_not_called()
        self.assertEqual(result["status"], "posted")                    # the feed post goes out as usual
        self.assertEqual(result["story"]["status"], "paused")
        self.assertIn("stories paused (config/formats.json)", next(self.reports.glob("lane-*.md")).read_text())

    def test_missing_switch_file_means_paused(self):
        Path(publish.FORMATS_FILE).unlink()
        self.assertEqual(publish.formats(), {"stories": False, "reels": False})
        Path(publish.FORMATS_FILE).write_text("{not json")
        self.assertEqual(publish.formats(), {"stories": False, "reels": False})
        Path(publish.FORMATS_FILE).write_text('{"stories": "yes", "reels": 1}')
        self.assertEqual(publish.formats(), {"stories": False, "reels": False})

    def test_stories_do_not_count_as_posts(self):
        from pipeline import common
        recent = (now_utc() - timedelta(minutes=5)).isoformat(timespec="seconds")
        common.append_posted({"type": "story", "account": "idlyautomotive", "media_id": "9", "story_id": 990001,
                              "posted_at": recent, "slot": "lane", "date": "2026-11-10"})
        self.assertEqual(common.posted_story_ids("idlyautomotive"), set())
        story, result = self.publish_run()                    # not "waiting" for a 30-minute gap, not a duplicate
        self.assertEqual(result["status"], "posted")


class LaneReels(PublishApproved):
    """Reels: request-reel -> render-reels (stub renderer) -> blind review -> publish-approved (mocked publisher)."""

    def setUp(self):
        super().setUp()
        REEL_CALLS.clear()
        root = Path(self.tmp.name)
        self.repo = root / "repo"                       # a stand-in repo for posts/ sources
        p = mock.patch.object(lane, "REPO", self.repo)
        p.start()
        self.patches.append(p)
        (root / "reel-caption.txt").write_text(CAPTION.replace("#idlyautomotive", "#Reels #idlyautomotive"))
        (root / "reel-score.json").write_text(json.dumps(GOOD_SCORE))
        self.cap, self.score = str(root / "reel-caption.txt"), str(root / "reel-score.json")

    def reel_reasons(self, slug):
        return json.loads((self.q / "reels" / "rejected" / slug / "reasons.json").read_text())["reasons"]

    def post_lane_item(self):
        """wagonr-oct goes all the way to queue/posted/ (the feed post's media id is 1790)."""
        self.approve()
        client = mock.Mock()
        client.find_recent.return_value = None
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post", return_value={"status": "posted", "media_id": "1790",
                                                                         "permalink": "https://www.instagram.com/p/F/"}), \
                mock.patch.object(publish, "publish_story", return_value={"status": "posted", "media_id": "1791"}), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            self.run_cli("publish-approved")
        self.assertTrue((self.q / "posted" / "wagonr-oct").exists())

    def request(self, source="lane:wagonr-oct", *extra):
        return self.run_cli("request-reel", "--source", source, "--caption-file", self.cap, "--score-file",
                            self.score, *extra)

    def rendered_reel(self, source="lane:wagonr-oct", slug="reel-wagonr-oct"):
        self.post_lane_item() if source.startswith("lane:") else None
        code, out, err = self.request(source)
        self.assertEqual(code, 0, out + err)
        code, _, err = self.run_cli("render-reels")
        self.assertEqual(code, 0, err)
        return self.q / "reels" / "rendered" / slug

    def test_request_reel_writes_a_valid_request(self):
        self.post_lane_item()
        code, out, _ = self.request()
        self.assertEqual(code, 0, out)
        req = json.loads((self.q / "reels" / "pending" / "reel-wagonr-oct.json").read_text())
        self.assertEqual((req["source"], req["account"], req["story_id"], req["idly_article"]),
                         ("lane:wagonr-oct", "idlyautomotive", 990001, True))
        self.assertEqual(req["scores"]["self"]["total"], 12)
        self.assertEqual(lane.validate_reel_request(req, "reel-wagonr-oct"), [])
        self.assertIn("git push", out)

    def test_request_problems(self):
        code, _, err = self.request("lane:not-posted-yet")
        self.assertEqual(code, 2)
        self.assertIn("no posted lane item", err)
        self.post_lane_item()
        Path(self.cap).write_text(CAPTION.replace("Which car", "Tag a friend! Which car"))
        code, out, _ = self.request()
        self.assertEqual(code, 1)
        self.assertIn("engagement bait", out)
        bad = {"source": "lane:wagonr-oct", "account": "idlytech", "idly_article": True, "caption": CAPTION,
               "scores": {"self": GOOD_SCORE}, "created_at": now_utc().isoformat(), "details": [3]}
        errs = " | ".join(lane.validate_reel_request(bad, "reel-x1"))
        self.assertIn("not @idlytech's", errs)
        self.assertIn("has 1 detail slide", errs)
        self.assertTrue(lane.validate_reel_request(dict(bad, account="idlyautomotive", details=[1]), "no-prefix"))

    def test_render_reels_from_a_lane_post(self):
        rdir = self.rendered_reel()
        self.assertEqual(sorted(p.name for p in rdir.iterdir()),
                         ["preview_00.5s.jpg", "preview_04.0s.jpg", "preview_07.0s.jpg", "preview_last.jpg",
                          "reel.mp4", "reel_cover.jpg", "render_report.json", "request.json"])
        req = json.loads((rdir / "request.json").read_text())
        self.assertTrue(req["caption_final"].endswith("\n\nImage: Maruti Suzuki"))
        self.assertEqual((req["reel_of"], req["image_credit"]), ("1790", "Image: Maruti Suzuki"))
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertEqual(rep["framing"]["frame"], "reel")                   # framing.REEL: faces above the reel's fade
        self.assertTrue(rep["image_url"].endswith("/wagonr-front.jpg"))      # the very image the feed post used
        post = REEL_CALLS[-1]["post"]
        self.assertEqual(post["slides"][0]["vertical"]["photo_h"], rep["framing"]["out_h"])
        self.assertEqual(post["slides"][0]["photo_credit"], "Image: Maruti Suzuki")
        self.assertIn("rendered · reel @idlyautomotive reel-wagonr-oct", next(self.reports.glob("lane-*.md")).read_text())

    def test_changed_official_image_is_rejected(self):
        self.post_lane_item()
        spec_path = self.q / "posted" / "wagonr-oct" / "spec.json"
        spec = json.loads(spec_path.read_text())
        spec["lane"]["image_url"] = "https://www.marutisuzuki.com/content/dam/press/another.jpg"
        spec_path.write_text(json.dumps(spec))
        self.request()
        self.run_cli("render-reels")
        self.assertIn("changed since the feed post", self.reel_reasons("reel-wagonr-oct")[0])

    def write_posts_folder(self, posted=True):
        folder = "posts/2026-11-10/idlyautomotive-1600-wagonr"
        d = self.repo / folder
        d.mkdir(parents=True)
        (d / "photo.jpg").write_bytes(CAR.read_bytes())
        (d / "caption.txt").write_text(CAPTION + "\n\n" + CAR_CREDIT)
        (d / "post.json").write_text(json.dumps({
            "acct": "idlyautomotive", "slug": "x", "date": "10 Nov 2026", "sources": ["Autocar India"],
            "slides": [{"type": "cover", "headline": "WagonR Stays India's Best-Selling Car", "photo": f"{folder}/photo.jpg",
                        "photo_credit": CAR_CREDIT, "focal": [0.5, 0.5], "zoom": 1.0},
                       {"type": "detail", "stat": "23,747", "stat_label": "WagonR sales in October",
                        "bullets": ["Brezza second", "Top five: WagonR, Brezza, Nexon"]}]}))
        if posted:
            from pipeline import common
            common.append_posted({"story_id": 1601, "account": "idlyautomotive", "media_id": "1801", "slot": "pm",
                                  "images": [common.public_url(f"{folder}/01.jpg")]})
        return folder

    def test_render_reels_from_a_posts_folder(self):
        folder = self.write_posts_folder()
        rdir = self.rendered_reel(folder, "reel-idlyautomotive-1600-wagonr")
        req = json.loads((rdir / "request.json").read_text())
        self.assertEqual((req["reel_of"], req["story_id"]), ("1801", 1601))
        self.assertTrue(req["caption_final"].endswith(CAR_CREDIT))
        self.assertEqual(REEL_CALLS[-1]["post"]["slides"][0]["vertical"]["photo_h"], 1350)

    def test_posts_folder_must_be_posted_and_have_post_json(self):
        folder = self.write_posts_folder(posted=False)
        code, _, err = self.request(folder)
        self.assertEqual(code, 2)
        self.assertIn("no feed post", err)
        code, _, err = self.request("posts/2026-11-10/nothing-here")
        self.assertEqual(code, 2)
        self.assertIn("post.json is missing", err)

    def test_review_and_publish(self):
        rdir = self.rendered_reel()
        code, out, _ = self.run_cli("show", "reel-wagonr-oct")
        self.assertEqual(code, 0)
        packet = json.loads(out)
        self.assertNotIn("scores", packet)
        self.assertTrue(any(f.endswith("preview_04.0s.jpg") for f in packet["files"]))
        self.run_cli("approve", "reel-wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        self.assertTrue((self.q / "reels" / "approved" / "reel-wagonr-oct.json").exists())
        client = mock.Mock()
        client.find_recent_reel.return_value = None
        reel = mock.Mock(return_value={"status": "posted", "type": "reel", "media_id": "1802", "video_host": "raw",
                                       "permalink": "https://www.instagram.com/reel/R/"})
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_reel", reel), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch.object(lane, "MIN_GAP", timedelta(0)), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")) as ready:
            code, _, err = self.run_cli("publish-approved")
        self.assertEqual(code, 0, err)
        args, kw = reel.call_args
        self.assertEqual(args[0], "idlyautomotive")
        self.assertTrue(args[1].endswith("/queue/reels/rendered/reel-wagonr-oct/reel.mp4"))
        self.assertEqual(args[2], json.loads((self.q / "reels" / "posted" / "reel-wagonr-oct" / "request.json")
                                             .read_text())["caption_final"])
        self.assertEqual(kw["score"]["total"], 12)                               # the lower score goes to the gate
        self.assertEqual((kw["record_extra"]["reel_slug"], kw["record_extra"]["reel_source"],
                          kw["record_extra"]["reel_of"]), ("reel-wagonr-oct", "lane:wagonr-oct", "1790"))
        self.assertTrue(kw["cover"].endswith("reel_cover.jpg"))
        self.assertIn(publish.VIDEO_TYPES, [c.kwargs.get("content_types") for c in ready.call_args_list])
        self.assertFalse(rdir.exists())
        self.assertEqual(json.loads((self.q / "reels" / "posted" / "reel-wagonr-oct" / "result.json").read_text())
                         ["media_id"], "1802")
        self.assertIn("posted reel · @idlyautomotive reel-wagonr-oct", next(self.reports.glob("lane-*.md")).read_text())

    def test_reels_paused_by_the_switch(self):
        self.rendered_reel()
        self.run_cli("approve", "reel-wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        formats_file(self.tmp.name, reels=False)
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_reel") as reel, mock.patch.object(lane, "MIN_GAP", timedelta(0)):
            code, _, err = self.run_cli("publish-approved")
        self.assertEqual(code, 0, err)
        reel.assert_not_called()
        self.assertTrue((self.q / "reels" / "approved" / "reel-wagonr-oct.json").exists())   # waits, not rejected
        self.assertIn("reels paused (config/formats.json)", next(self.reports.glob("lane-*.md")).read_text())

    def test_reel_waits_for_the_gap_after_the_feed_post(self):
        self.rendered_reel()
        from pipeline import common
        common.append_posted({"account": "idlyautomotive", "media_id": "1", "story_id": 5,
                              "posted_at": now_utc().isoformat(timespec="seconds")})
        self.run_cli("approve", "reel-wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_reel") as reel:
            code, _, err = self.run_cli("publish-approved")
        reel.assert_not_called()
        self.assertIn("min gap", err)

    def test_below_the_gate_is_rejected(self):
        self.rendered_reel()
        low = {**REVIEWER_SCORE, "send": 0, "total": 11}
        self.run_cli("approve", "reel-wagonr-oct", "--score-file", self.score_file(low))
        self.assertFalse((self.q / "reels" / "approved" / "reel-wagonr-oct.json").exists())
        self.assertIn("below the 12 gate", self.reel_reasons("reel-wagonr-oct")[0])

    def test_dry_run_prints_the_reel_calls(self):
        self.rendered_reel()
        self.run_cli("approve", "reel-wagonr-oct", "--score-file", self.score_file(REVIEWER_SCORE))
        with mock.patch.object(publish, "append_posted") as ap, mock.patch.object(publish, "connect") as conn, \
                mock.patch.object(lane, "MIN_GAP", timedelta(0)):
            code, out, err = self.run_cli("publish-approved", "--dry-run")
        self.assertEqual(code, 0, err)
        ap.assert_not_called()
        conn.assert_not_called()
        self.assertIn("media_type=REELS", out)
        self.assertIn("reels/rendered/reel-wagonr-oct/reel.mp4", out)
        self.assertTrue((self.q / "reels" / "approved" / "reel-wagonr-oct.json").exists())

    def test_one_reel_per_source(self):
        self.rendered_reel()
        from pipeline import common
        common.append_posted({"type": "reel", "account": "idlyautomotive", "media_id": "1802",
                              "reel_source": "lane:wagonr-oct", "reel_slug": "reel-wagonr-oct"})
        code, out, _ = self.request("lane:wagonr-oct", "--slug", "reel-wagonr-oct-again")
        self.assertEqual(code, 1)
        self.assertIn("already has a reel", out)

    def test_status_lists_reels(self):
        self.rendered_reel()
        _, out, _ = self.run_cli("status")
        self.assertIn("reels/rendered: 1", out)
        self.assertIn("reel-wagonr-oct", out)


class GitMerges(unittest.TestCase):
    def test_posted_union(self):
        up = json.dumps([{"account": "a", "media_id": "1"}, {"account": "b", "media_id": "2"}])
        me = json.dumps([{"account": "a", "media_id": "1"}, {"account": "c", "media_id": "3", "lane_slug": "x"}])
        merged = json.loads(gitsync.merge_posted(up, me))
        self.assertEqual([e["media_id"] for e in merged], ["1", "2", "3"])

    def test_accounts_keep_both_sides(self):
        base = json.dumps({"accounts": {"a": {"id": "1"}, "b": {"id": "2"}}})
        up = json.dumps({"accounts": {"a": {"id": "1", "host": "graph.facebook.com"}, "b": {"id": "2"}}})
        me = json.dumps({"accounts": {"a": {"id": "1"}, "b": {"id": "2", "host": "graph.instagram.com"}}})
        merged = json.loads(gitsync.merge_accounts(base, up, me))["accounts"]
        self.assertEqual(merged["a"]["host"], "graph.facebook.com")
        self.assertEqual(merged["b"]["host"], "graph.instagram.com")

    def test_report_lines(self):
        self.assertEqual(gitsync.merge_lines("# t\n- a\n", "# t\n- b\n"), "# t\n- a\n- b\n")


@unittest.skipUnless(chrome_available(), "Chrome/Playwright not available: cardkit can't render here")
class EndToEndDryRun(LaneCase):
    """spec -> og_image_official (fixture page + Commons car photo) -> real YuNet -> real cardkit -> approve ->
    publish-approved --dry-run. Nothing leaves the machine."""
    real_renderer = True
    real_detector = True

    def setUp(self):
        super().setUp()
        try:
            framing.ensure_model()
        except Exception as e:  # noqa: BLE001
            self.patches.append(mock.patch.object(framing, "DETECTOR", lambda im: []))
            self.patches[-1].start()
            print(f"(YuNet unavailable, using no faces: {e})")

    def test_full_flow(self):
        self.write_spec("wagonr-oct-e2e", make_spec())
        code, _, err = self.run_cli("render-pending")
        self.assertEqual(code, 0, err)
        rdir = self.q / "rendered" / "wagonr-oct-e2e"
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertEqual(rep["faces"], [])
        self.assertEqual([s["type"] for s in rep["slides"]], ["cover", "detail"])
        self.assertEqual(rep["slides"][0]["credit_line"], "Image: Maruti Suzuki")
        self.assertEqual(rep["slides"][1]["credit_line"], "Sources: Autocar India, Rushlane")
        self.assertEqual(rep["slides"][1]["credit_collision"], [])
        for f in ("01.jpg", "02.jpg"):
            publish.check_jpeg(rdir / f)
        score = Path(self.tmp.name) / "r.json"
        score.write_text(json.dumps(REVIEWER_SCORE))
        self.assertEqual(self.run_cli("approve", "wagonr-oct-e2e", "--score-file", str(score))[0], 0)
        with mock.patch.object(publish, "append_posted") as ap:
            code, out, err = self.run_cli("publish-approved", "--dry-run")
        self.assertEqual(code, 0, err)
        ap.assert_not_called()
        self.assertIn("POST", out)
        self.assertIn("media_type=CAROUSEL", out)
        self.assertIn("media_type=STORIES", out)
        rep = json.loads((self.q / "rendered" / "wagonr-oct-e2e" / "render_report.json").read_text())
        self.assertEqual(rep["story"]["status"], "rendered", rep["story"])
        publish.check_story_jpeg(self.q / "rendered" / "wagonr-oct-e2e" / "story.jpg")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
    def test_reel_flow(self):
        """posted lane item -> request-reel -> render-reels (real cardkit.reel + ffmpeg) -> approve -> dry run."""
        self.write_spec("wagonr-oct-e2e", make_spec())
        self.assertEqual(self.run_cli("render-pending")[0], 0)
        score = Path(self.tmp.name) / "r.json"
        score.write_text(json.dumps(REVIEWER_SCORE))
        self.run_cli("approve", "wagonr-oct-e2e", "--score-file", str(score))
        client = mock.Mock()
        client.find_recent.return_value = None
        with mock.patch.dict(os.environ, {"IG_TOKEN_IDLYAUTOMOTIVE": "x"}), \
                mock.patch.object(publish, "publish_post", return_value={"status": "posted", "media_id": "1790"}), \
                mock.patch.object(publish, "publish_story", return_value={"status": "posted", "media_id": "1791"}), \
                mock.patch.object(publish, "connect", return_value=(client, "1784")), \
                mock.patch("pipeline.run_day.url_ready", return_value=(True, "ok")):
            self.run_cli("publish-approved")
        cap = Path(self.tmp.name) / "cap.txt"
        cap.write_text(make_spec()["caption"])
        code, out, err = self.run_cli("request-reel", "--source", "lane:wagonr-oct-e2e", "--caption-file", str(cap),
                                      "--score-file", str(score), "--details", "1")
        self.assertEqual(code, 0, out + err)
        code, _, err = self.run_cli("render-reels")
        self.assertEqual(code, 0, err)
        rdir = self.q / "reels" / "rendered" / "reel-wagonr-oct-e2e"
        rep = json.loads((rdir / "render_report.json").read_text())
        self.assertAlmostEqual(rep["duration"], 10.0)                  # cover 3.5 s, the detail 3.5 s, end card 3 s
        self.assertEqual(rep["video"]["problems"], [])
        self.assertEqual([p["type"] for p in rep["pages"]], ["cover", "detail", "end"])
        publish.check_reel_mp4(rdir / "reel.mp4")
        self.assertEqual(self.run_cli("approve", "reel-wagonr-oct-e2e", "--score-file", str(score))[0], 0)
        with mock.patch.object(publish, "append_posted") as ap, mock.patch.object(lane, "MIN_GAP", timedelta(0)):
            code, out, err = self.run_cli("publish-approved", "--dry-run")
        self.assertEqual(code, 0, err)
        ap.assert_not_called()
        self.assertIn("media_type=REELS", out)


if __name__ == "__main__":
    unittest.main()
