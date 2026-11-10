"""Official image resolvers: allowlist/denylist, oEmbed (mocked), og:image (fixture HTML), placeholders.
Run: python3 -m unittest discover tests"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import official_image as oi  # noqa: E402
from tests.lane_helpers import (FIXTURES, FakeFetcher, flat_png, jpeg_bytes, make_spec, noise_image,  # noqa: E402
                                oembed, og_routes)

SOURCES = oi.load_sources()
VID = "AbCdEfGhIjK"
OEMBED = "https://www.youtube.com/oembed"


class Allowlist(unittest.TestCase):
    def test_denied_outlets(self):
        for url in ("https://www.123telugu.com/mnews/x.html", "https://www.cinemaexpress.com/a",
                    "https://timesofindia.indiatimes.com/x", "https://www.ndtv.com/entertainment/x",
                    "https://www.hindustantimes.com/x", "https://indianexpress.com/article/x",
                    "https://www.reuters.com/x", "https://media.gettyimages.com/x.jpg", "https://apnews.com/x"):
            self.assertIsNotNone(oi.denied(url, SOURCES), url)

    def test_official_domains_and_paths(self):
        ok = {"https://www.marutisuzuki.com/corporate/media/press-releases/x": "Maruti Suzuki",
              "https://about.netflix.com/en/news/x": "Netflix",
              "https://www.apple.com/newsroom/2026/11/x/": "Apple",
              "https://www.apple.com/in/newsroom/2026/11/x/": "Apple",
              "https://www.samsung.com/in/newsroom/x": "Samsung",
              "https://news.samsung.com/in/x": "Samsung",
              "https://blog.google/products/x/": "Google",
              "https://www.yashrajfilms.com/movies/x": "Yash Raj Films"}
        for url, org in ok.items():
            entry = oi.official_entry(url, SOURCES)
            self.assertIsNotNone(entry, url)
            self.assertEqual(entry["organisation"], org)
        for url in ("https://www.apple.com/iphone/", "https://www.samsung.com/in/smartphones/x",
                    "https://marutisuzuki.com.evil.example/x", "https://evilmarutisuzuki.com/x",
                    "https://www.ndtv.com/x", "https://en.wikipedia.org/wiki/WagonR"):
            self.assertIsNone(oi.official_entry(url, SOURCES), url)

    def test_channel_allowlist(self):
        self.assertEqual(oi.official_channel("https://www.youtube.com/@NetflixIndiaOfficial", SOURCES)["name"],
                         "Netflix India")
        self.assertEqual(oi.official_channel("http://youtube.com/@netflixindiaofficial/", SOURCES)["name"],
                         "Netflix India")             # case, scheme, host and slash variations
        self.assertEqual(oi.official_channel("https://www.youtube.com/channel/UCZSNzBgFub_WWil6TOTYwAg",
                                             SOURCES)["name"], "Netflix India")
        for lookalike in ("https://www.youtube.com/@dharmaproductions", "https://www.youtube.com/@ExcelEntertainment",
                          "https://www.youtube.com/@NetflixIndiaOfficial2", "", "https://www.youtube.com/@THINKMUSIC"):
            self.assertIsNone(oi.official_channel(lookalike, SOURCES), lookalike)

    def test_pending_review_is_not_allowlisted(self):
        allow = {c["name"] for c in SOURCES["youtube_channels"]}
        for p in SOURCES["pending_review"]:
            self.assertNotIn(p["name"], allow)

    def test_every_requested_studio_is_seeded(self):
        names = {c["name"] for c in SOURCES["youtube_channels"]} | {p["name"] for p in SOURCES["pending_review"]}
        for want in ("Netflix India", "Prime Video India", "JioHotstar", "ZEE5", "SonyLIV", "Sun TV", "T-Series",
                     "Sony Music South", "Lyca Productions", "Mythri Movie Makers", "Hombale Films",
                     "Yash Raj Films", "Dharma Productions", "Excel Entertainment", "Aha", "Saregama",
                     "Think Music", "Lahari Music"):
            self.assertIn(want, names)


class YouTubeIds(unittest.TestCase):
    def test_parse(self):
        for ref in (VID, f"https://www.youtube.com/watch?v={VID}&t=3s", f"https://youtu.be/{VID}",
                    f"https://m.youtube.com/watch?v={VID}", f"https://www.youtube.com/shorts/{VID}",
                    f"https://www.youtube.com/embed/{VID}", f"youtube.com/watch?v={VID}"):
            self.assertEqual(oi.youtube_id(ref), VID, ref)
        for ref in ("https://vimeo.com/123", "https://www.youtube.com/@NetflixIndiaOfficial", "short"):
            with self.assertRaises(oi.ResolveError):
                oi.youtube_id(ref)


def yt_routes(author_name, author_url, maxres=True, hq=True, title="Kaalam | Official Trailer | Netflix India"):
    routes = {OEMBED: oembed(author_name, author_url, title)}
    if maxres:
        routes[f"https://i.ytimg.com/vi/{VID}/maxresdefault.jpg"] = (200, "image/jpeg",
                                                                     jpeg_bytes(noise_image(1280, 720)))
    if hq:
        routes[f"https://i.ytimg.com/vi/{VID}/hqdefault.jpg"] = (200, "image/jpeg", jpeg_bytes(noise_image(480, 360)))
    return routes


class YouTubeOfficial(unittest.TestCase):
    def resolve(self, routes, ref=f"https://youtu.be/{VID}"):
        fake = FakeFetcher(routes)
        with mock.patch.object(oi, "FETCHER", fake):
            return oi.resolve({"resolver": "youtube_official", "ref": ref}, {}, SOURCES), fake

    def test_official_channel_resolves(self):
        res, fake = self.resolve(yt_routes("Netflix India", "https://www.youtube.com/@NetflixIndiaOfficial"))
        self.assertEqual(res.credit, "Image: Netflix India (official trailer)")
        self.assertEqual(res.image_url, f"https://i.ytimg.com/vi/{VID}/maxresdefault.jpg")
        self.assertEqual((res.width, res.height), (1280, 720))
        self.assertTrue(fake.calls[0].startswith(OEMBED + "?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D"))
        self.assertTrue(any("oEmbed" in line for line in res.log))

    def test_teaser_and_song_credit(self):
        res, _ = self.resolve(yt_routes("YRF", "https://www.youtube.com/@yrf", title="Alpha | Official Teaser"))
        self.assertEqual(res.credit, "Image: Yash Raj Films (official teaser)")
        res, _ = self.resolve(yt_routes("T-Series", "https://www.youtube.com/@tseries", title="Song (Lyrical)"))
        self.assertEqual(res.credit, "Image: T-Series (official video)")

    def test_unlisted_uploader_refused(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve(yt_routes("Movie Fan Club", "https://www.youtube.com/@moviefanclub"))
        self.assertIn("not on the official channel allowlist", cm.exception.reason)
        self.assertFalse(cm.exception.transient)

    def test_hq_fallback_too_small(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve(yt_routes("Netflix India", "https://www.youtube.com/@NetflixIndiaOfficial", maxres=False))
        self.assertIn("hqdefault.jpg", cm.exception.reason)
        self.assertIn("under 900px", cm.exception.reason)

    def test_private_video(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve({OEMBED: (401, "text/plain", b"Unauthorized")})
        self.assertIn("private", cm.exception.reason)

    def test_oembed_outage_is_transient(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve({OEMBED: (503, "text/plain", b"busy")})
        self.assertTrue(cm.exception.transient)


class OgImage(unittest.TestCase):
    def test_parse_fixture(self):
        html = (FIXTURES / "og_official_page.html").read_text()
        og = oi.parse_og(html, "https://www.marutisuzuki.com/press/wagonr-october")
        self.assertEqual(og["images"], [
            "https://www.marutisuzuki.com/content/dam/press/logo-maruti.png",
            "https://www.marutisuzuki.com/content/dam/press/wagonr-front.jpg",
            "https://www.marutisuzuki.com/content/dam/press/wagonr-twitter.jpg"])
        self.assertEqual(og["site_name"], "Maruti Suzuki India")

    def test_parse_twitter_only_and_attribute_order(self):
        html = ('<html><head><meta content="//cdn.example.com/a.jpg" name="twitter:image">'
                '<meta content="http://x.example.com/b.jpg" property="og:image:secure_url"></head></html>')
        og = oi.parse_og(html, "https://about.netflix.com/en/news/x")
        self.assertEqual(og["images"], ["https://x.example.com/b.jpg", "https://cdn.example.com/a.jpg"])

    def resolve(self, routes, ref="https://www.marutisuzuki.com/press/wagonr-october"):
        with mock.patch.object(oi, "FETCHER", FakeFetcher(routes)):
            return oi.resolve({"resolver": "og_image_official", "ref": ref}, {}, SOURCES)

    def test_resolves_and_skips_the_logo(self):
        res = self.resolve(og_routes())
        self.assertEqual(res.credit, "Image: Maruti Suzuki")
        self.assertTrue(res.image_url.endswith("/wagonr-front.jpg"))
        self.assertEqual((res.width, res.height), (1920, 1281))

    def test_news_outlet_refused(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve({}, "https://www.cinemaexpress.com/telugu/news/x")
        self.assertIn("news outlet", cm.exception.reason)

    def test_unlisted_domain_refused(self):
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve({}, "https://www.example-fan-site.com/kantara")
        self.assertIn("not an official domain", cm.exception.reason)

    def test_redirect_to_outlet_refused(self):
        routes = {"https://www.marutisuzuki.com/press/x": ("redirect", "https://www.ndtv.com/auto/x")}
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve(routes, "https://www.marutisuzuki.com/press/x")
        self.assertIn("ndtv.com", cm.exception.reason)

    def test_image_hosted_by_outlet_refused(self):
        page = b'<meta property="og:image" content="https://static.toiimg.com/photo/x.jpg">' \
               b'<meta property="og:image" content="https://images.indianexpress.com/x.jpg">'
        routes = {"https://www.tatamotors.com/press/x": (200, "text/html", page)}
        with self.assertRaises(oi.ResolveError) as cm:
            self.resolve(routes, "https://www.tatamotors.com/press/x")
        self.assertIn("indianexpress.com", cm.exception.reason)

    def test_http_page_refused(self):
        with self.assertRaises(oi.ResolveError):
            self.resolve({}, "http://www.marutisuzuki.com/press/x")


class ImageChecks(unittest.TestCase):
    def test_placeholders(self):
        from PIL import Image
        flat = Image.new("RGB", (1200, 800), (128, 128, 128))
        self.assertIn("flat", oi.placeholder_reason(flat))
        self.assertIn("tiny", oi.placeholder_reason(noise_image(150, 150)))
        self.assertIn("colours", oi.placeholder_reason(Image.open(__import__("io").BytesIO(flat_png())).convert("RGB")))
        self.assertIn("placeholder", oi.placeholder_reason(noise_image(1200, 800), "https://x.com/img/placeholder.jpg"))
        self.assertIn("logo", oi.placeholder_reason(noise_image(1200, 800), "https://x.com/assets/logo.png"))
        self.assertIsNone(oi.placeholder_reason(noise_image(1200, 800), "https://x.com/press/wagonr.jpg"))

    def test_size_rule(self):
        with self.assertRaises(oi.ResolveError) as cm:
            oi.check_image(jpeg_bytes(noise_image(880, 700)), "https://x.com/a.jpg")
        self.assertIn("under 900px", cm.exception.reason)
        self.assertEqual(oi.check_image(jpeg_bytes(noise_image(900, 700)), "https://x.com/a.jpg").width, 900)

    def test_not_an_image(self):
        with self.assertRaises(oi.ResolveError):
            oi.check_image(b"<html>nope</html>", "https://x.com/a.jpg")


class AttemptOrder(unittest.TestCase):
    def test_licensed_wire_goes_first(self):
        image = {"resolver": "og_image_official", "ref": "https://about.netflix.com/en/news/x",
                 "fallback": [{"resolver": "youtube_official", "ref": VID},
                              {"resolver": "licensed_wire", "query": "Kaalam premiere Mumbai"}]}
        self.assertEqual([a["resolver"] for a in oi.attempts_of(image)],
                         ["licensed_wire", "og_image_official", "youtube_official"])

    def test_resolve_first_falls_through(self):
        spec = make_spec(image={"resolver": "youtube_official", "ref": VID,
                                "fallback": [{"resolver": "og_image_official",
                                              "ref": "https://www.marutisuzuki.com/press/wagonr-october"}]})
        routes = {**og_routes(), **yt_routes("Fan Edits", "https://www.youtube.com/@fanedits")}
        with mock.patch.object(oi, "FETCHER", FakeFetcher(routes)):
            res, tried = oi.resolve_first(spec["image"], spec, SOURCES)
        self.assertEqual(res.resolver, "og_image_official")
        self.assertEqual([t["ok"] for t in tried], [False, True])
        self.assertIn("allowlist", tried[0]["reason"])


if __name__ == "__main__":
    unittest.main()
