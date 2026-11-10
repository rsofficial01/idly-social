"""The live publish path against a local mock of graph.facebook.com and graph.instagram.com
(no network, nothing posted). URLs under /ig/ play graph.instagram.com.

Every way a token can reach Meta is covered:
- shared, network secret (the Claude cloud setup): no token in the environment; the client sends NO
  credentials and the agent proxy adds the Authorization header (the mock plays the proxy + Meta).
- shared, IG_SYSTEM_TOKEN (running anywhere else).
- per account, IG_TOKEN_<ACCOUNT>: host auto-detected (graph.instagram.com first, then graph.facebook.com).
In every mode a token travels only as "Authorization: Bearer": never in a URL, a body, any output,
check.json, state/posted.json or state/accounts.json.
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

from PIL import Image  # noqa: E402

from pipeline import common, publish  # noqa: E402
from tests.test_editorial import GOOD_CAPTION, GOOD_SCORE  # noqa: E402

TOKEN = "FAKE-SYSTEM-USER-TOKEN-do-not-leak-123"
IG_TOKENS = {f"IGAA-FAKE-{a}-do-not-leak": a for a in ("idlytech", "idlynerd", "idlyhype", "idlynews")}
TOKEN_OF = {a: t for t, a in IG_TOKENS.items()}
FB_ACCOUNT_TOKEN = "EAA-FAKE-idlyautomotive-do-not-leak"      # a per-account token that works on facebook
NEW_TOKEN = "IGAA-NEW-FROM-REFRESH-do-not-leak"               # what a refresh may hand back
ALL_SECRETS = [TOKEN, FB_ACCOUNT_TOKEN, NEW_TOKEN, *IG_TOKENS]
BUSINESS = common.BUSINESS_ID
IG_IDS = {"idlynews": "1781", "idlytech": "1789", "idlyhype": "1783", "idlyautomotive": "1784", "idlynerd": "1785"}
USER_BY_ID = {v: k for k, v in IG_IDS.items()}
V = f"/{publish.API_VERSION}"


class FakeGraph(BaseHTTPRequestHandler):
    """Meta for the five idly accounts. Shared system user: assigned_instagram_accounts has 3 (two pages),
    owned_instagram_accounts is refused (no permission), instagram_accounts has @idlyautomotive and
    /me/accounts the Page-linked @idlynerd. Per-account tokens see only their own account."""
    calls: list = []
    shared_token = None         # None: network-secret mode (no header = the proxy added the secret)
    secret_configured = True    # network-secret mode only: False = no secret, Meta sees no token
    fb_tokens = {FB_ACCOUNT_TOKEN: "idlyautomotive"}
    refresh = {}                # token -> ("same" | "new", expires_in seconds)
    fail_first_media = True
    polls: dict = {}
    containers: dict = {}
    quota_usage = 3

    def log_message(self, *a):
        pass

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _err(self, code, message, http=400):
        return self._send(http, {"error": {"code": code, "message": message}})

    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        auth = self.headers.get("Authorization")
        FakeGraph.calls.append((method, self.path, body, auth))
        token = auth[len("Bearer "):] if auth and auth.startswith("Bearer ") else None
        url = urlsplit(self.path)
        path, q = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
        form = {k: v[0] for k, v in parse_qs(body).items()}
        on_ig = path.startswith("/ig/")
        path = path[3:] if on_ig else path

        if on_ig:                                                  # graph.instagram.com
            who = IG_TOKENS.get(token)
            if not who:
                return self._err(190, "Invalid OAuth access token - Cannot parse access token")
            if path == "/refresh_access_token" and q.get("grant_type") == "ig_refresh_token":
                kind, secs = FakeGraph.refresh.get(token, ("same", 60 * 86400))
                return self._send(200, {"access_token": token if kind == "same" else NEW_TOKEN,
                                        "token_type": "bearer", "expires_in": secs})
            allowed = {IG_IDS[who]}
        else:                                                      # graph.facebook.com
            if token is None:
                if not FakeGraph.secret_configured:
                    return self._err(2500, "An active access token must be used to query information "
                                           "about the current user.")
                who = "shared"
            elif token == FakeGraph.shared_token:
                who = "shared"
            elif token in FakeGraph.fb_tokens:
                who = FakeGraph.fb_tokens[token]
            else:
                return self._err(190, "Invalid OAuth access token - Cannot parse access token")
            allowed = set(IG_IDS.values()) if who == "shared" else {IG_IDS[who]}
        seg = path[len(V) + 1:].split("/") if path.startswith(V + "/") else []

        if seg == ["me"]:
            if on_ig:
                return self._send(200, {"user_id": IG_IDS[who], "username": who, "id": f"app-{who}"})
            if who != "shared":
                return self._send(200, {"id": f"fbuser-{who}", "name": f"{who} owner"})
            if q.get("fields") == "client_business_id":
                return self._send(200, {"client_business_id": BUSINESS, "id": "sys1"})
            return self._send(200, {"id": "sys1", "name": "idly publisher system user"})
        if not on_ig and who == "shared":
            if seg == ["me", "assigned_instagram_accounts"]:
                if q.get("after") == "CUR1":
                    return self._send(200, {"data": [{"id": IG_IDS["idlyhype"], "username": "idlyhype"}],
                                            "paging": {"cursors": {"before": "CUR1", "after": "CUR2"}}})
                return self._send(200, {"data": [{"id": IG_IDS["idlynews"], "username": "idlynews"},
                                                 {"id": IG_IDS["idlytech"], "username": "IdlyTech"}],
                                        "paging": {"cursors": {"before": "CUR0", "after": "CUR1"},
                                                   "next": f"https://graph.facebook.com{V}/me/assigned_"
                                                           f"instagram_accounts?access_token=NEVER-FOLLOW"}})
            if seg == [BUSINESS, "owned_instagram_accounts"]:
                return self._err(200, "(#200) Requires business_management", http=403)
            if seg == [BUSINESS, "instagram_accounts"]:
                return self._send(200, {"data": [{"id": IG_IDS["idlyautomotive"], "username": "idlyautomotive"},
                                                 {"id": "999", "username": "someoneelse"}]})
            if seg == ["me", "accounts"]:
                return self._send(200, {"data": [
                    {"id": "page1", "instagram_business_account": {"id": IG_IDS["idlynerd"], "username": "idlynerd"}},
                    {"id": "page2"}]})
        if seg and seg[0] in USER_BY_ID and seg[0] not in allowed:
            return self._err(100, f"Unsupported get request. Object with ID '{seg[0]}' does not exist")
        if len(seg) == 1 and seg[0] in USER_BY_ID and method == "GET":
            return self._send(200, {"id": seg[0], "username": USER_BY_ID[seg[0]]})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "content_publishing_limit":
            return self._send(200, {"data": [{"quota_usage": FakeGraph.quota_usage,
                                              "config": {"quota_total": 50, "quota_duration": 86400}}]})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "media" and method == "POST":
            if FakeGraph.fail_first_media:
                FakeGraph.fail_first_media = False
                return self._send(500, {"error": {"code": 2, "message": "temporary", "is_transient": True}})
            n = len(FakeGraph.containers) + 1
            if form.get("media_type") == "CAROUSEL":
                cid = "car1"
            elif form.get("media_type") == "STORIES":
                cid = "st1"
            elif form.get("is_carousel_item") == "true":
                cid = f"{'v' if form.get('media_type') == 'VIDEO' else 'i'}{n}"
            else:
                cid = "c1"
            FakeGraph.containers[cid] = {**form, "_host": "ig" if on_ig else "fb", "_ig": seg[0]}
            return self._send(200, {"id": cid})
        if len(seg) == 1 and seg[0] in FakeGraph.containers:
            FakeGraph.polls[seg[0]] = FakeGraph.polls.get(seg[0], 0) + 1
            ready = FakeGraph.polls[seg[0]] > (2 if seg[0].startswith("v") else 1)   # videos take longer
            return self._send(200, {"status_code": "FINISHED" if ready else "IN_PROGRESS"})
        if len(seg) == 2 and seg[0] in USER_BY_ID and seg[1] == "media_publish":
            return self._send(200, {"id": "m1"})
        if seg == ["m1"]:
            return self._send(200, {"permalink": "https://www.instagram.com/p/FAKE/"})
        return self._err(100, f"unknown path {path}", http=404)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class MockGraphCase(unittest.TestCase):
    env_token = ""

    def setUp(self):
        FakeGraph.calls, FakeGraph.polls, FakeGraph.containers, FakeGraph.refresh = [], {}, {}, {}
        FakeGraph.quota_usage = 3
        FakeGraph.fail_first_media, FakeGraph.secret_configured = True, True
        FakeGraph.shared_token = self.env_token or None
        self.server = HTTPServer(("127.0.0.1", 0), FakeGraph)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        root = f"http://127.0.0.1:{self.server.server_port}"
        no_account_tokens = {common.token_env(a): "" for a in common.ACCOUNTS}   # ignore any real ones
        self.patches = [
            mock.patch.object(publish, "GRAPH", root),
            mock.patch.object(publish, "GRAPH_IG", root + "/ig"),
            mock.patch.object(publish, "POLL_WAITS", [0] * 5),
            mock.patch.object(publish.time, "sleep", lambda s: None),
            mock.patch.object(common, "POSTED_FILE", Path(self.tmp.name) / "posted.json"),
            mock.patch.object(common, "ACCOUNTS_FILE", Path(self.tmp.name) / "accounts.json"),
            mock.patch.dict(os.environ, {common.TOKEN_ENV: self.env_token, **no_account_tokens}),
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

    def own_tokens(self, **tokens):
        os.environ.update({common.token_env(a): t for a, t in tokens.items()})   # undone by patch.dict

    def run_quiet(self, fn, *a, **kw):
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            return fn(*a, **kw)

    def publish(self, media=("https://example.com/card.jpg",), account="idlytech", **kw):
        return self.run_quiet(publish.publish_post, account, list(media), GOOD_CAPTION, score=GOOD_SCORE,
                              story_id=1664, date="2026-11-09", slot="pm", **kw)

    def check(self, **kw):
        report = self.run_quiet(publish.check_accounts, **kw)
        self.run_quiet(print, json.dumps(report), "\n".join(publish.format_check(report)))
        return report

    def calls_to(self, host):
        return [c for c in FakeGraph.calls if c[1].startswith("/ig/") == (host == publish.IG_HOST)]

    def assert_nothing_leaked(self):
        files = [common.POSTED_FILE, common.ACCOUNTS_FILE]
        saved = "".join(f.read_text() for f in files if f.exists())
        for secret in ALL_SECRETS:
            for method, path, body, auth in FakeGraph.calls:
                self.assertNotIn(secret, path + body)
            self.assertNotIn(secret, self.out.getvalue() + self.err.getvalue() + saved)
        for method, path, body, auth in FakeGraph.calls:
            self.assertNotIn("access_token=", path + body)
            self.assertNotIn("NEVER-FOLLOW", path)


class NetworkSecretMode(MockGraphCase):
    """No token in the environment: the agent proxy supplies the shared one."""

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
        report = self.check()
        self.assertTrue(report["ok"], report)
        self.assertEqual({a["account"]: a["ig_id"] for a in report["accounts"]}, IG_IDS)
        self.assertTrue(all(a["reachable"] and a["quota_used"] == 3 for a in report["accounts"]))
        attempts = {a["lookup"]: a for a in report["discovery"]["attempts"]}
        self.assertFalse(attempts[f"GET /{BUSINESS}/owned_instagram_accounts"]["ok"])
        self.assertEqual(attempts["GET /me/assigned_instagram_accounts"]["matched"], 3)   # two pages
        saved = json.loads(common.ACCOUNTS_FILE.read_text())
        self.assertEqual({k: v["id"] for k, v in saved["accounts"].items()}, IG_IDS)
        self.assertTrue(all(set(v) <= set(common.ACCOUNT_FIELDS) for v in saved["accounts"].values()))
        text = "\n".join(publish.format_check(report))
        self.assertIn("network secret", text)
        self.assertIn("@idlynerd (shared token on graph.facebook.com): ok (id 1785, 3/25 posts in 24h)", text)
        self.assert_nothing_leaked()

    def test_no_secret_configured_is_reported_clearly(self):
        FakeGraph.secret_configured = False
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertIn("network secret", report["auth_error"])
        self.assertTrue(all("no access: set IG_TOKEN_" in a["warnings"][0] for a in report["accounts"]))
        self.assertIn("ACCESS PROBLEM (shared token)", "\n".join(publish.format_check(report)))
        self.assertEqual(len(FakeGraph.calls), 1)                # stops after /me is refused
        with self.assertRaises(publish.IGError) as ctx:
            self.publish()
        self.assertIn("network secret", str(ctx.exception))
        self.assertFalse(common.POSTED_FILE.exists())

    def test_stale_cached_id_is_rediscovered(self):
        common.update_accounts({"idlytech": {"id": IG_IDS["idlynews"]}}, ["manual"])
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


class Stories(MockGraphCase):
    """publish_story: STORIES container -> FINISHED -> media_publish, recorded as type "story"."""

    def story(self, image="https://example.com/story.jpg", **kw):
        kw.setdefault("wait", False)
        return self.run_quiet(publish.publish_story, "idlytech", image, **kw)

    def test_story_published_and_recorded(self):
        res = self.story(story_of="17900000000000001", date="2026-11-10", slot="pm")
        self.assertEqual(res["status"], "posted")
        st = FakeGraph.containers["st1"]
        self.assertEqual((st["media_type"], st["image_url"]), ("STORIES", "https://example.com/story.jpg"))
        self.assertNotIn("caption", st)
        self.assertTrue(any(p.endswith("/media_publish") and "creation_id=st1" in b for _, p, b, _ in FakeGraph.calls))
        entry = json.loads(common.POSTED_FILE.read_text())[-1]
        self.assertEqual((entry["type"], entry["story_of"], entry["media_id"]), ("story", "17900000000000001", "m1"))
        self.assertEqual(common.posted_story_ids("idlytech"), set())           # a story is not a feed post
        self.assertIsNone(common.slot_already_posted("idlytech", "2026-11-10", "pm"))
        self.assert_nothing_leaked()

    def test_story_links_to_the_feed_post_in_its_folder(self):
        folder = "posts/2026-11-10/idlyautomotive-1427-six-airbags"
        common.append_posted({"story_id": None, "account": "idlyautomotive", "media_id": "17909514279669792",
                              "slot": "pm", "images": [common.public_url(f"{folder}/01.jpg")]})
        feed = publish.linked_feed_post("idlyautomotive", common.REPO / folder / "01.jpg")
        self.assertEqual(feed["media_id"], "17909514279669792")
        self.assertIsNone(publish.linked_feed_post("idlytech", common.REPO / folder / "01.jpg"))

    def test_story_keeps_headroom_for_feed_posts(self):
        FakeGraph.quota_usage = publish.LOCAL_DAILY_CAP - publish.STORY_HEADROOM
        with self.assertRaises(publish.IGError) as ctx:
            self.story()
        self.assertIn("feed posts keep", str(ctx.exception))
        self.assertFalse(any(m == "POST" for m, *_ in FakeGraph.calls))
        self.assertFalse(common.POSTED_FILE.exists())

    def test_story_dry_run_and_cli(self):
        code = self.run_quiet(publish.main, ["story", "--account", "idlytech", "--image",
                                             "https://example.com/story.jpg", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(FakeGraph.calls, [])
        self.assertIn("media_type=STORIES, image_url=https://example.com/story.jpg", self.out.getvalue())

    def test_story_image_checks(self):
        tmp = Path(self.tmp.name)
        Image.new("RGB", (1080, 1350)).save(tmp / "feed.jpg", "JPEG")
        Image.new("RGB", (1080, 1920)).save(tmp / "story.png", "PNG")
        Image.new("RGB", (1080, 1920)).save(tmp / "story.jpg", "JPEG")
        with self.assertRaises(ValueError):
            publish.check_story_jpeg(tmp / "feed.jpg")
        with self.assertRaises(ValueError):
            publish.check_story_jpeg(tmp / "story.png")
        publish.check_story_jpeg(tmp / "story.jpg")
        with self.assertRaises(ValueError):                                     # outside posts/: not public
            publish.publish_story("idlytech", str(tmp / "story.jpg"), dry_run=True)

    def test_published_container_found_on_the_stories_edge(self):
        client = publish.IGClient(host=publish.FB_HOST)
        with mock.patch.object(client, "call", side_effect=[
                publish.IGError("timeout", transient=True), {"status_code": "PUBLISHED"},
                {"data": [{"id": "old", "timestamp": "2026-11-10T01:00:00+0000"},
                          {"id": "new", "timestamp": "2026-11-10T09:00:05+0000"}]}]):
            since = common.parse_time("2026-11-10T09:00:00+00:00")
            media_id = client.publish("1789", "st1", "", finder=lambda: client.find_recent_story("1789", since))
        self.assertEqual(media_id, "new")


class EnvTokenMode(MockGraphCase):
    """IG_SYSTEM_TOKEN set (running outside the Claude cloud environment)."""
    env_token = TOKEN

    def test_token_only_in_the_header(self):
        res = self.publish(alt_text="A card about Jio's plan")
        self.assertEqual(res["status"], "posted")
        self.assertTrue(all(auth == f"Bearer {TOKEN}" for *_, auth in FakeGraph.calls))
        report = self.check()
        self.assertTrue(report["ok"])
        self.assert_nothing_leaked()


class AccountTokenMode(MockGraphCase):
    """IG_TOKEN_<ACCOUNT> from the Meta dashboard; no shared token anywhere."""

    def setUp(self):
        super().setUp()
        FakeGraph.secret_configured = False

    def test_own_token_on_instagram_host(self):
        self.own_tokens(idlytech=TOKEN_OF["idlytech"])
        res = self.publish(collaborators=["idlynews"])
        self.assertEqual(res["status"], "posted")
        self.assertEqual(self.calls_to(publish.FB_HOST), [])     # all on graph.instagram.com
        self.assertTrue(all(auth == f"Bearer {TOKEN_OF['idlytech']}" for *_, auth in FakeGraph.calls))
        self.assertEqual(FakeGraph.containers["c1"]["_host"], "ig")
        self.assertEqual(json.loads(FakeGraph.containers["c1"]["collaborators"]), ["idlynews"])
        saved = json.loads(common.ACCOUNTS_FILE.read_text())["accounts"]["idlytech"]
        self.assertEqual(saved, {"id": "1789", "username": "idlytech", "host": "graph.instagram.com"})
        self.assert_nothing_leaked()

    def test_own_token_falls_back_to_facebook_host_and_remembers_it(self):
        common.update_accounts({"idlyautomotive": {"id": IG_IDS["idlyautomotive"]}}, ["seed"])
        self.own_tokens(idlyautomotive=FB_ACCOUNT_TOKEN)
        self.assertEqual(self.publish(account="idlyautomotive")["status"], "posted")
        self.assertEqual(len(self.calls_to(publish.IG_HOST)), 1)  # tried graph.instagram.com/me once
        self.assertEqual(FakeGraph.containers["c1"]["_host"], "fb")
        self.assertEqual(common.load_accounts()["idlyautomotive"]["host"], "graph.facebook.com")
        FakeGraph.calls.clear()
        self.check(expiry=True)
        self.assertEqual(self.calls_to(publish.IG_HOST), [])      # cached host: straight to facebook
        self.assert_nothing_leaked()

    def test_check_mixed_modes_with_expiry(self):
        common.update_accounts({"idlyautomotive": {"id": IG_IDS["idlyautomotive"]}}, ["seed"])
        self.own_tokens(idlytech=TOKEN_OF["idlytech"], idlynerd=TOKEN_OF["idlynerd"],
                        idlyhype=TOKEN_OF["idlyhype"], idlyautomotive=FB_ACCOUNT_TOKEN)
        FakeGraph.refresh = {TOKEN_OF["idlynerd"]: ("same", 5 * 86400 + 60),
                             TOKEN_OF["idlyhype"]: ("new", 60 * 86400)}
        FakeGraph.secret_configured = True                        # @idlynews still uses the shared one
        report = self.check()
        st = {a["account"]: a for a in report["accounts"]}
        self.assertEqual(st["idlytech"]["days_left"], 60)
        self.assertEqual(st["idlynerd"]["days_left"], 5)
        self.assertIn("expires in 5 days", st["idlynerd"]["warnings"][0])
        self.assertNotIn("days_left", st["idlyhype"])
        self.assertIn("new token", st["idlyhype"]["notes"][0])
        self.assertEqual((st["idlyautomotive"]["host"], st["idlyautomotive"]["reachable"]),
                         ("graph.facebook.com", True))
        self.assertEqual((st["idlynews"]["mode"], st["idlynews"]["reachable"]), ("shared", True))
        self.assertEqual(report["shared_accounts"], ["idlynews"])
        self.assertFalse(report["ok"])                            # idlynerd's token is about to expire
        refreshes = [c for c in FakeGraph.calls if c[1].startswith("/ig/refresh_access_token")]
        self.assertEqual(len(refreshes), 3)                       # instagram-host tokens only
        self.assert_nothing_leaked()                              # incl. the token the refresh handed back
        FakeGraph.calls.clear()
        self.check(expiry=False)
        self.assertFalse(any("refresh_access_token" in c[1] for c in FakeGraph.calls))

    def test_token_for_another_account_is_refused(self):
        self.own_tokens(idlytech=TOKEN_OF["idlynews"])
        with self.assertRaises(publish.WrongAccount):
            self.publish()
        self.assertEqual(self.calls_to(publish.FB_HOST), [])      # no fallback with a wrong-account token
        self.assertFalse(common.POSTED_FILE.exists())
        self.assert_nothing_leaked()

    def test_bad_token_is_reported(self):
        self.own_tokens(idlyhype="garbage-do-not-leak")
        report = self.check()
        st = next(a for a in report["accounts"] if a["account"] == "idlyhype")
        self.assertIn("works on neither host", st["warnings"][0])
        self.assertIn("Meta dashboard", st["warnings"][0])
        sent = "".join(path + body for _, path, body, _ in FakeGraph.calls)
        self.assertNotIn("garbage-do-not-leak", self.out.getvalue() + self.err.getvalue() + sent)

    def test_dry_run_shows_the_host_without_calls(self):
        self.own_tokens(idlytech=TOKEN_OF["idlytech"])
        self.publish(dry_run=True)
        self.assertEqual(FakeGraph.calls, [])
        self.assertIn(f"{publish.GRAPH_IG}/{publish.API_VERSION}/me?fields=user_id,username", self.out.getvalue())
        self.assertIn("IG_TOKEN_IDLYTECH is set", self.out.getvalue())
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

    def test_seeded_account_ids(self):
        doc = json.loads((common.REPO / "state" / "accounts.json").read_text())
        self.assertEqual(set(doc["accounts"]), set(common.ACCOUNTS))
        for acct, entry in doc["accounts"].items():
            self.assertTrue(set(entry) <= set(common.ACCOUNT_FIELDS), entry)
            self.assertEqual(entry["username"], acct)
            self.assertRegex(entry["id"], r"^17841\d{10,}$")


if __name__ == "__main__":
    unittest.main()
