"""The live publish path against a local mock of graph.instagram.com (no network, nothing posted)."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import common, publish  # noqa: E402
from tests.test_editorial import GOOD_CAPTION, GOOD_SCORE  # noqa: E402

TOKEN = "FAKE-TOKEN-do-not-leak-123"


class FakeGraph(BaseHTTPRequestHandler):
    calls: list = []
    polls = 0
    fail_first_media = True

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
        FakeGraph.calls.append((method, self.path, body, self.headers.get("Authorization")))
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
        path = self.path.split("?")[0]
        if path == "/v25.0/me":
            return self._send(200, {"user_id": "1789", "username": "idlytech", "id": "app-scoped"})
        if path == "/v25.0/1789/content_publishing_limit":
            return self._send(200, {"data": [{"quota_usage": 3, "config": {"quota_total": 100}}]})
        if path == "/v25.0/1789/media" and method == "POST":
            if FakeGraph.fail_first_media:
                FakeGraph.fail_first_media = False
                return self._send(500, {"error": {"code": 2, "message": "temporary", "is_transient": True}})
            return self._send(200, {"id": "c1"})
        if path == "/v25.0/c1":
            FakeGraph.polls += 1
            return self._send(200, {"status_code": "FINISHED" if FakeGraph.polls > 1 else "IN_PROGRESS"})
        if path == "/v25.0/1789/media_publish":
            return self._send(200, {"id": "m1"})
        if path == "/v25.0/m1":
            return self._send(200, {"permalink": "https://www.instagram.com/p/FAKE/"})
        return self._send(404, {"error": {"code": 100, "message": f"unknown path {path}"}})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class PublishFlow(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeGraph)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(publish, "GRAPH", f"http://127.0.0.1:{self.server.server_port}"),
            mock.patch.object(publish, "POLL_WAITS", [0] * 5),
            mock.patch.object(publish.time, "sleep", lambda s: None),
            mock.patch.object(common, "POSTED_FILE", Path(self.tmp.name) / "posted.json"),
            mock.patch.dict(os.environ, {"IG_TOKEN_IDLYTECH": TOKEN}),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_publish_single_image(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            res = publish.publish_post("idlytech", ["https://example.com/card.jpg"], GOOD_CAPTION,
                                       score=GOOD_SCORE, story_id=1664, date="2026-11-09", slot="pm",
                                       alt_text="A card about Jio's plan")
        self.assertEqual(res["status"], "posted")
        self.assertEqual(res["permalink"], "https://www.instagram.com/p/FAKE/")
        posted = json.loads(common.POSTED_FILE.read_text())
        self.assertEqual(posted[0]["story_id"], 1664)
        self.assertEqual(posted[0]["media_id"], "m1")
        # the token went only in the header: never in a URL, body, or any output
        for method, path, body, auth in FakeGraph.calls:
            self.assertNotIn(TOKEN, path + body)
        self.assertNotIn(TOKEN, out.getvalue() + err.getvalue() + common.POSTED_FILE.read_text())
        self.assertIn("retry 1/3", err.getvalue())          # the transient 500 was retried

    def test_wrong_account_token_is_refused(self):
        with mock.patch.dict(common.ACCOUNTS["idlytech"], {"username": "someoneelse"}):
            with self.assertRaises(publish.IGError):
                publish.publish_post("idlytech", ["https://example.com/card.jpg"], GOOD_CAPTION,
                                     score=GOOD_SCORE, story_id=1, date="2026-11-09", slot="pm")


if __name__ == "__main__":
    unittest.main()
