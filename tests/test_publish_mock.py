"""The live publish path against a local mock of graph.facebook.com (no network, nothing posted).

Two ways the token reaches Meta, both covered:
- network secret (the Claude cloud setup): no token in the environment; the client sends NO credentials
  and the agent proxy adds the Authorization header. Here the mock plays the proxy + Meta.
- IG_SYSTEM_TOKEN (running anywhere else): sent only as "Authorization: Bearer", never in a URL, a body,
  any output, state/posted.json or state/accounts.json.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import common, publish  # noqa: E402
from tests.test_editorial import GOOD_CAPTION, GOOD_SCORE  # noqa: E402

TOKEN = "FAKE-SYSTEM-USER-TOKEN-do-not-leak-123"
BUSINESS = common.BUSINESS_ID
IG_IDS = {"idlynews": "1781", "idlytech": "1789", "idlyhype": "1783", "idlyautomotive": "1784", "idlynerd": "1785"}
USER_BY_ID = {v: k for k, v in IG_IDS.items()}
V = f"/{publish.API_VERSION}"


class FakeGraph(BaseHTTPRequestHandler):
    """Meta's Graph API for a system user with the five idly accounts, spread across the lookups:
    assigned_instagram_accounts has 3 (two pages), owned_instagram_accounts is refused (no permission),
    instagram_accounts has @idlyautomotive, and /me/accounts has the Page-linked @idlynerd."""
    calls: list = []
    expect_auth = None          # None: proxy mode (client must send no credentials); else the exact token
    secret_configured = True    # proxy mode only: False = no network secret, Meta sees no token
    fail_first_media = True
    polls: dict = {}
    containers: dict = {}

    def log_message(self, *a):
        pass

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        auth = self.headers.get("Authorization")
        FakeGraph.calls.append((method, self.path, body, auth))
        if FakeGraph.expect_auth is None:
            if auth is not None:                                   # the client must not send credentials
                return self._send(400, {"error": {"code": 190, "message": "client sent its own credentials"}})
            if not FakeGraph.secret_configured:
                return self._send(400, {"error": {"code": 2500, "message": "An active access token must be used "
                                                  "to query information about the current user."}})
        elif auth != f"Bearer {FakeGraph.expect_auth}":
            return self._send(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})

        url = urlsplit(self.path)
        path, q = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
        form = {k: v[0] for k, v in parse_qs(body).items()}
        seg = path[len(V) + 1:].split("/") if path.startswith(V + "/") else []

        if seg == ["me"]:
            if q.get("fields") == "client_business_id":
                return self._send(200, {"client_business_id": BUSINESS, "id": "sys1"})
            return self._send(200, {"id": "sys1", "name": "idly publisher system user"})
        if seg == ["me", "assigned_instagram_accounts"]:
            page1 = [{"id": IG_IDS["idlynews"], "username": "idlynews"},
                     {"id": IG_IDS["idlytech"], "username": "IdlyTech"}]
            if q.get("after") == "CUR1":
                return self._send(200, {"data": [{"id": IG_IDS["idlyhype"], "username": "idlyhype"}],
                                        "paging": {"cursors": {"before": "CUR1", "after": "CUR2"}}})
            return self._send(200, {"data": page1, "paging": {
                "cursors": {"before": "CUR0", "after": "CUR1"},
                "next": f"https://graph.facebook.com{V}/me/assigned_instagram_accounts?access_token=NEVER-FOLLOW"}})
        if seg == [BUSINESS, "owned_instagram_accounts"]:
            return self._send(403, {"error": {"code": 200, "message": "(#200) Requires business_management"}})
        if seg == [BUSINESS, "instagram_accounts"]:
            return self._send(200, {"data": [{"id": IG_IDS["idlyautomotive"], "username": "idlyautomotive"},
                                             {"id": "999", "username": "someoneelse"}]})
        if seg == ["me", "accounts"]:
            return self._send(200, {"data": [
                {"id": "page1", "instagram_business_account": {"id": IG_IDS["idlynerd"], "username": "idlynerd"}},
                {"id": "page2"}]})
        if len(seg) == 1 and seg[0] in USER_BY_ID and method == "GET":
            return self._send(200, {"id": seg[0], "username": USER_BY_ID[seg[0]]})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "content_publishing_limit":
            return self._send(200, {"data": [{"quota_usage": 3, "config": {"quota_total": 50,
                                                                           "quota_duration": 86400}}]})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "media" and method == "POST":
            if FakeGraph.fail_first_media:
                FakeGraph.fail_first_media = False
                return self._send(500, {"error": {"code": 2, "message": "temporary", "is_transient": True}})
            n = len(FakeGraph.containers) + 1
            if form.get("media_type") == "CAROUSEL":
                cid = "car1"
            elif form.get("is_carousel_item") == "true":
                cid = f"{'v' if form.get('media_type') == 'VIDEO' else 'i'}{n}"
            else:
                cid = "c1"
            FakeGraph.containers[cid] = form
            return self._send(200, {"id": cid})
        if len(seg) == 1 and seg[0] in FakeGraph.containers:
            FakeGraph.polls[seg[0]] = FakeGraph.polls.get(seg[0], 0) + 1
            ready = FakeGraph.polls[seg[0]] > (2 if seg[0].startswith("v") else 1)   # videos take longer
            return self._send(200, {"status_code": "FINISHED" if ready else "IN_PROGRESS"})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "media_publish":
            return self._send(200, {"id": "m1"})
        if seg == ["m1"]:
            return self._send(200, {"permalink": "https://www.instagram.com/p/FAKE/"})
        return self._send(404, {"error": {"code": 100, "message": f"unknown path {path}"}})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class MockGraphCase(unittest.TestCase):
    env_token = ""

    def setUp(self):
        FakeGraph.calls, FakeGraph.polls, FakeGraph.containers = [], {}, {}
        FakeGraph.fail_first_media, FakeGraph.secret_configured = True, True
        FakeGraph.expect_auth = self.env_token or None
        self.server = HTTPServer(("127.0.0.1", 0), FakeGraph)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(publish, "GRAPH", f"http://127.0.0.1:{self.server.server_port}"),
            mock.patch.object(publish, "POLL_WAITS", [0] * 5),
            mock.patch.object(publish.time, "sleep", lambda s: None),
            mock.patch.object(common, "POSTED_FILE", Path(self.tmp.name) / "posted.json"),
            mock.patch.object(common, "ACCOUNTS_FILE", Path(self.tmp.name) / "accounts.json"),
            mock.patch.dict(os.environ, {common.TOKEN_ENV: self.env_token}),
        ]
        for p in self.patches:
            p.start()
        self.out, self.err = io.StringIO(), io.StringIO()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def run_quiet(self, fn, *a, **kw):
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            return fn(*a, **kw)

    def publish(self, media=("https://example.com/card.jpg",), account="idlytech", **kw):
        return self.run_quiet(publish.publish_post, account, list(media), GOOD_CAPTION, score=GOOD_SCORE,
                              story_id=1664, date="2026-11-09", slot="pm", **kw)

    def assert_nothing_leaked(self, secret=TOKEN):
        for method, path, body, auth in FakeGraph.calls:
            self.assertNotIn(secret, path + body)
            self.assertNotIn("access_token", path + body)
        files = [common.POSTED_FILE, common.ACCOUNTS_FILE]
        saved = "".join(f.read_text() for f in files if f.exists())
        self.assertNotIn(secret, self.out.getvalue() + self.err.getvalue() + saved)
        self.assertFalse(any("NEVER-FOLLOW" in path for _, path, _, _ in FakeGraph.calls))


class NetworkSecretMode(MockGraphCase):
    """No token in the environment: the agent proxy supplies it."""

    def test_publish_single_image_sends_no_credentials(self):
        res = self.publish(alt_text="A card about Jio's plan", collaborators=["@IdlyNews"])
        self.assertEqual(res["status"], "posted")
        self.assertEqual(res["permalink"], "https://www.instagram.com/p/FAKE/")
        self.assertTrue(all(auth is None for *_, auth in FakeGraph.calls))      # the proxy adds it, not us
        self.assertTrue(all(p.startswith(V + "/") for _, p, _, _ in FakeGraph.calls))
        posted = json.loads(common.POSTED_FILE.read_text())
        self.assertEqual(posted[0]["story_id"], 1664)
        self.assertEqual(posted[0]["media_id"], "m1")
        self.assertEqual(set(posted[0]), {"story_id", "account", "media_id", "permalink", "posted_at", "date",
                                          "slot", "images", "score_total"})
        c1 = FakeGraph.containers["c1"]
        self.assertEqual(json.loads(c1["collaborators"]), ["idlynews"])
        self.assertEqual(c1["alt_text"], "A card about Jio's plan")
        self.assertIn("retry 1/3", self.err.getvalue())          # the transient 500 was retried
        self.assertEqual(common.load_account_ids()["idlytech"], "1789")
        self.assert_nothing_leaked()

    def test_carousel_with_video_children(self):
        res = self.publish(media=["https://example.com/card.jpg", "https://example.com/clip.mp4"],
                           collaborators=["idlynews", "idlyhype"])
        self.assertEqual(res["status"], "posted")
        kids = {k: v for k, v in FakeGraph.containers.items() if k != "car1"}
        video = next(v for k, v in kids.items() if k.startswith("v"))
        image = next(v for k, v in kids.items() if k.startswith("i"))
        self.assertEqual((video["media_type"], video["video_url"], video["is_carousel_item"]),
                         ("VIDEO", "https://example.com/clip.mp4", "true"))
        self.assertEqual((image["image_url"], image["is_carousel_item"]), ("https://example.com/card.jpg", "true"))
        self.assertNotIn("caption", video)
        parent = FakeGraph.containers["car1"]
        self.assertEqual(parent["children"], ",".join(kids))     # in the given order
        self.assertEqual(json.loads(parent["collaborators"]), ["idlynews", "idlyhype"])
        vid = next(k for k in kids if k.startswith("v"))
        self.assertEqual(FakeGraph.polls[vid], 3)                # polled until FINISHED
        self.assert_nothing_leaked()

    def test_check_finds_all_five_accounts(self):
        report = self.run_quiet(publish.check_accounts)
        self.assertTrue(report["ok"], report)
        self.assertEqual({a["account"]: a["ig_id"] for a in report["accounts"]}, IG_IDS)
        self.assertTrue(all(a["reachable"] and a["quota_used"] == 3 for a in report["accounts"]))
        attempts = {a["lookup"]: a for a in report["discovery"]["attempts"]}
        self.assertFalse(attempts[f"GET /{BUSINESS}/owned_instagram_accounts"]["ok"])
        self.assertEqual(attempts["GET /me/assigned_instagram_accounts"]["matched"], 3)   # two pages
        saved = json.loads(common.ACCOUNTS_FILE.read_text())
        self.assertEqual({k: v["id"] for k, v in saved["accounts"].items()}, IG_IDS)
        self.assertTrue(all(set(v) == {"id", "username"} for v in saved["accounts"].values()))
        text = "\n".join(publish.format_check(report))
        self.assertIn("network secret", text)
        self.assertIn("@idlynerd: ok (id 1785, 3/25 posts in 24h)", text)
        self.assert_nothing_leaked()

    def test_no_secret_configured_is_reported_clearly(self):
        FakeGraph.secret_configured = False
        report = self.run_quiet(publish.check_accounts)
        self.assertFalse(report["ok"])
        self.assertIn("network secret", report["auth_error"])
        self.assertTrue(all(a["warnings"] == ["no access: Meta got no valid access token"]
                            for a in report["accounts"]))
        self.assertIn("ACCESS PROBLEM", "\n".join(publish.format_check(report)))
        self.assertEqual(len(FakeGraph.calls), 1)                # stops after /me is refused
        with self.assertRaises(publish.IGError) as ctx:
            self.publish()
        self.assertIn("network secret", str(ctx.exception))
        self.assertFalse(common.POSTED_FILE.exists())

    def test_stale_cached_id_is_rediscovered(self):
        common.save_account_ids({"idlytech": {"id": IG_IDS["idlynews"], "username": "idlytech"}}, ["manual"])
        res = self.publish()
        self.assertEqual(res["status"], "posted")
        self.assertIn("didn't check out", self.err.getvalue())
        self.assertEqual(common.load_account_ids()["idlytech"], "1789")
        self.assertTrue(any(p.startswith(f"{V}/1789/media_publish") for _, p, _, _ in FakeGraph.calls))

    def test_wrong_account_is_refused(self):
        with mock.patch.dict(common.ACCOUNTS["idlytech"], {"username": "someoneelse2"}):
            with self.assertRaises(publish.IGError):
                self.publish()
        self.assertFalse(any(p.endswith("/media_publish") for _, p, _, _ in FakeGraph.calls))

    def test_dry_run_makes_no_calls(self):
        res = self.publish(media=["https://example.com/a.jpg", "https://example.com/b.mov"],
                           collaborators=["idlynews"], dry_run=True)
        self.assertEqual(res["status"], "dry-run")
        self.assertEqual(FakeGraph.calls, [])
        plan = self.out.getvalue()
        self.assertIn(f"{publish.GRAPH}/{publish.API_VERSION}/<ig-user-id>/media  media_type=VIDEO", plan)
        self.assertIn('collaborators=["idlynews"]', plan)


class EnvTokenMode(MockGraphCase):
    """IG_SYSTEM_TOKEN set (running outside the Claude cloud environment)."""
    env_token = TOKEN

    def test_token_only_in_the_header(self):
        res = self.publish(alt_text="A card about Jio's plan")
        self.assertEqual(res["status"], "posted")
        self.assertTrue(all(auth == f"Bearer {TOKEN}" for *_, auth in FakeGraph.calls))
        report = self.run_quiet(publish.check_accounts)
        self.assertTrue(report["ok"])
        self.run_quiet(print, "\n".join(publish.format_check(report)))
        self.assert_nothing_leaked()


class LocalChecks(unittest.TestCase):
    def test_collaborators(self):
        self.assertEqual(publish.clean_collaborators(None, "idlytech"), [])
        self.assertEqual(publish.clean_collaborators(["@IdlyNews", "idlynews"], "idlytech"), ["idlynews"])
        for bad in (["a", "b", "c", "d"], ["not a name"], ["idlytech"], "idlynews"):
            with self.assertRaises(ValueError, msg=bad):
                publish.clean_collaborators(bad, "idlytech")

    def test_single_video_is_refused(self):
        with self.assertRaises(ValueError):
            publish.publish_post("idlytech", ["https://example.com/clip.mp4"], GOOD_CAPTION, score=GOOD_SCORE,
                                 story_id=1, dry_run=True)


if __name__ == "__main__":
    unittest.main()
