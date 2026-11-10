"""Licensed wire adapters: AP Media API against a mock (no network); PTI/ANI/IANS stubs; the licensed_wire
resolver's choice. Images are synthetic; faces are synthetic boxes. Run: python3 -m unittest discover tests"""
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import framing, official_image, wire  # noqa: E402
from pipeline.wire import ap  # noqa: E402
from tests.lane_helpers import jpeg_bytes, make_spec, noise_image  # noqa: E402

KEY = "FAKE-AP-KEY-do-not-leak"
NOW = datetime.now(timezone.utc)


def ap_item(itemid, caption, *, creditline="AP", photographer="Jane Doe", hours_ago=2, w=3000, h=2000,
            priced=False, usageterms=None, typ="picture"):
    return {"type": typ, "pubstatus": "usable", "altids": {"itemid": itemid},
            "headline": caption[:40], "description_caption": caption,
            "firstcreated": (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z"),
            "versioncreated": (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z"),
            "photographer": {"name": photographer, "title": "STAFF"}, "description_creditline": creditline,
            "usageterms": usageterms or ["This content is intended for editorial use only."],
            "renditions": {"main": {"href": f"https://api.ap.org/media/v/content/{itemid}/download?role=main&t=1",
                                    "width": w, "height": h, "mimetype": "image/jpeg",
                                    **({"priced": True, "pricetag": "USD:15.00"} if priced else {})},
                           "preview": {"href": f"https://api.ap.org/media/v/content/{itemid}/download?role=preview"}}}


class Resp:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        return json.loads(self._body)

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i:i + n]


class FakeAP:
    """Plays api.ap.org (search, item, download with a redirect to mapi.associatedpress.com)."""

    def __init__(self, items, image=b"", redirect_to="https://mapi.associatedpress.com/dl/abc.jpg"):
        self.items = {i["altids"]["itemid"]: i for i in items}
        self.order = items
        self.image = image or jpeg_bytes(noise_image(3000, 2000))
        self.redirect_to = redirect_to
        self.calls = []

    def get(self, url, params=None, timeout=None, stream=False, allow_redirects=True, headers=None):
        self.calls.append((url, params, dict(headers or {})))
        u = urlsplit(url)
        if headers.get("x-api-key") != KEY:
            return Resp(401, b"{}")
        if u.path.endswith("/content/search"):
            return Resp(200, json.dumps({"data": {"items": [{"item": i} for i in self.order]}}).encode())
        if "/download" in u.path:
            return Resp(302, b"", {"Location": self.redirect_to})
        if u.hostname == "mapi.associatedpress.com":
            return Resp(200, self.image)
        itemid = u.path.rsplit("/", 1)[-1]
        if itemid in self.items:
            return Resp(200, json.dumps({"data": {"item": self.items[itemid]}}).encode())
        return Resp(404, b"{}")


ID1, ID2, ID3, ID4, ID5, ID6 = (f"{i:032x}" for i in range(1, 7))


class APAdapter(unittest.TestCase):
    def items(self):
        return [
            ap_item(ID1, "India's Virat Kohli bats during the first Test against Australia in Perth", hours_ago=1),
            ap_item(ID2, "Kohli celebrates his century in Perth", creditline="REUTERS", hours_ago=1),
            ap_item(ID3, "Kohli in Perth, a priced photo", priced=True),
            ap_item(ID4, "Kohli at Perth nets", usageterms=["NO ONLINE USE"]),
            ap_item(ID5, "Kohli graphic", typ="graphic"),
            ap_item(ID6, "Kohli and Rohit at Perth airport", creditline="Getty Images via AP"),
        ]

    def test_search_query_headers_and_filters(self):
        fake = FakeAP(self.items())
        a = ap.APAdapter(api_key=KEY, session=fake)
        # the window is measured from the clock at call time (NOW is fixed at import, which a long suite outruns)
        found = a.search("Kohli Perth", datetime.now(timezone.utc) - timedelta(hours=48))
        self.assertEqual([c.id for c in found], [ID1])          # Reuters, priced, restricted, graphic, Getty out
        c = found[0]
        self.assertEqual(c.credit, "AP Photo/Jane Doe")
        self.assertEqual((c.width, c.height), (3000, 2000))
        url, params, headers = fake.calls[0]
        self.assertEqual(url, "https://api.ap.org/media/v/content/search")
        self.assertEqual(params["in_my_plan"], "true")             # no spend
        self.assertEqual(params["sort"], "versioncreated:desc")
        self.assertIn("type:picture AND (Kohli Perth) AND versioncreated:>now-48h", params["q"])
        self.assertEqual(headers["x-api-key"], KEY)
        self.assertNotIn(KEY, url + json.dumps(params))           # the key only ever travels in the header

    def test_download_follows_ap_redirect_only(self):
        fake = FakeAP(self.items())
        data, credit = ap.APAdapter(api_key=KEY, session=fake).download(ID1)
        self.assertEqual(credit, "AP Photo/Jane Doe")
        self.assertGreater(len(data), 1000)
        hosts = [urlsplit(u).hostname for u, _, _ in fake.calls]
        self.assertEqual(hosts, ["api.ap.org", "api.ap.org", "mapi.associatedpress.com"])
        self.assertEqual(fake.calls[0][1], {"in_my_plan": "true"})

    def test_redirect_off_ap_refused(self):
        fake = FakeAP(self.items(), redirect_to="https://evil.example.com/x.jpg")
        with self.assertRaises(wire.WireError):
            ap.APAdapter(api_key=KEY, session=fake).download(ID1)
        self.assertFalse(any("evil" in u for u, _, _ in fake.calls))

    def test_priced_item_never_downloaded(self):
        fake = FakeAP(self.items())
        with self.assertRaises(wire.WireError) as cm:
            ap.APAdapter(api_key=KEY, session=fake).download(ID3)
        self.assertIn("charged", str(cm.exception))
        self.assertFalse(any("/download" in u for u, _, _ in fake.calls))

    def test_bad_key(self):
        with self.assertRaises(wire.WireError) as cm:
            ap.APAdapter(api_key="wrong", session=FakeAP(self.items())).search("Kohli", NOW)
        self.assertIn("refused the key", str(cm.exception))

    def test_not_configured(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            a = ap.APAdapter()
            self.assertFalse(a.configured())
            with self.assertRaises(wire.NotConfigured):
                a.search("Kohli", NOW)

    def test_credit_without_photographer(self):
        item = ap_item(ID1, "x", photographer="")
        self.assertEqual(ap.ap_credit(item), "AP Photo")


class Stubs(unittest.TestCase):
    def test_pti_ani_ians_are_not_configured(self):
        for name, secret in (("pti", "PTI_API_KEY"), ("ani", "ANI_API_KEY"), ("ians", "IANS_API_KEY")):
            a = wire.get_adapter(name)
            self.assertFalse(a.configured())
            self.assertIn(secret, a.secrets)
            with self.assertRaises(wire.NotConfigured):
                a.search("x", NOW)
            with self.assertRaises(wire.NotConfigured):
                a.download("x")

    def test_reuters_and_getty_never(self):
        for name in ("reuters", "Reuters Connect", "getty", "gettyimages"):
            with self.assertRaises(wire.NotConfigured):
                wire.get_adapter(name)

    def test_credit_formats(self):
        self.assertEqual(wire.AGENCY_CREDIT, {"ap": "AP Photo/{photographer}", "pti": "Photo: PTI",
                                              "ani": "ANI Photo", "ians": "Photo: IANS"})


class FakeAdapter(wire.WireAdapter):
    def __init__(self, name, candidates, images):
        self.name, self.cands, self.images, self.downloads = name, candidates, images, []

    def configured(self):
        return True

    def search(self, query, since):
        return list(self.cands)

    def download(self, id):
        self.downloads.append(id)
        return self.images[id], next(c.credit for c in self.cands if c.id == id)


def cand(id, caption, hours_ago, credit="Photo: PTI", w=3000):
    return wire.Candidate("pti", id, caption, credit, None,
                          (NOW - timedelta(hours=hours_ago)).isoformat(), w, 2000)


class LicensedWireResolver(unittest.TestCase):
    def run_resolver(self, cands, images, faces=None, attempt=None):
        fake = FakeAdapter("pti", cands, images)
        attempt = attempt or {"resolver": "licensed_wire", "query": "Kohli Perth Test", "agencies": ["pti"]}
        old = framing.DETECTOR
        framing.DETECTOR = (lambda im: faces(im)) if faces else (lambda im: [])
        try:
            with mock.patch.object(wire, "get_adapter", lambda name: fake):
                res = official_image.resolve(attempt, make_spec(headline="Kohli hits a century in Perth"))
        finally:
            framing.DETECTOR = old
        return res, fake

    def test_picks_newest_relevant(self):
        cands = [cand("old", "Virat Kohli bats in the Perth Test", 30),
                 cand("new", "Kohli celebrates a hundred in the Perth Test", 2),
                 cand("offtopic", "Farmers protest in Delhi", 1),
                 cand("small", "Kohli Perth Test close-up", 1, w=700),
                 cand("reuters", "Kohli Perth Test", 1, credit="REUTERS/Jane Doe")]
        imgs = {k: jpeg_bytes(noise_image(3000, 2000)) for k in ("old", "new", "offtopic", "small", "reuters")}
        res, fake = self.run_resolver(cands, imgs)
        self.assertEqual(fake.downloads, ["new"])
        self.assertEqual(res.credit, "Photo: PTI")
        self.assertEqual(res.extra["item_id"], "new")
        self.assertIn("plan", res.extra)

    def test_skips_one_that_fails_framing(self):
        cands = [cand("bad", "Kohli in the Perth Test", 1), cand("good", "Kohli in the Perth Test", 3)]
        imgs = {"bad": jpeg_bytes(noise_image(3000, 2000, seed=5)), "good": jpeg_bytes(noise_image(3000, 2000))}
        seen = []

        def faces(im):
            seen.append(1)          # first download: faces at the very top and bottom -> no framing fits
            return [framing.Face(1400, 5, 150, 170), framing.Face(1400, 1820, 150, 170)] if len(seen) == 1 else []
        res, fake = self.run_resolver(cands, imgs, faces)
        self.assertEqual(fake.downloads, ["bad", "good"])
        self.assertEqual(res.extra["item_id"], "good")

    def test_nothing_configured(self):
        attempt = {"resolver": "licensed_wire", "query": "Kohli Perth", "agencies": ["ani", "ians"]}
        with self.assertRaises(official_image.ResolveError) as cm:
            official_image.resolve(attempt, make_spec())
        self.assertIn("ani", cm.exception.reason)
        self.assertFalse(cm.exception.transient)

    def test_relevance(self):
        self.assertGreaterEqual(official_image.relevance("Virat Kohli in Perth", "Kohli Perth"), 1.0)
        self.assertLess(official_image.relevance("Farmers protest in Delhi", "Kohli Perth"), 0.6)


if __name__ == "__main__":
    unittest.main()
