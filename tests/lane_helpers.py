"""Shared fakes for the official image lane tests. No network, and no image of a real person anywhere:
test images are synthetic noise/gradients, or tests/fixtures/commons_wagonr.jpg (a car, Wikimedia Commons,
"2020 Maruti Suzuki Wagon R VXi (O) (India) front view" by Riding Hub, CC BY 3.0). Faces are synthetic boxes."""
from __future__ import annotations

import io
import json
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from pipeline import official_image  # noqa: E402
from pipeline.common import now_utc  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CAR = FIXTURES / "commons_wagonr.jpg"
CAR_CREDIT = "Photo: Riding Hub / Wikimedia Commons (CC BY 3.0)"


def noise_image(w: int, h: int, seed: int = 1) -> Image.Image:
    """A busy synthetic 'photo': smooth colour gradients plus noise (many colours, no faces)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:h, 0:w]
    base = np.stack([(x / w) * 200, (y / h) * 180, ((x + y) / (w + h)) * 220], axis=-1)
    arr = np.clip(base + rng.normal(0, 18, (h, w, 3)), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def jpeg_bytes(im: Image.Image, quality: int = 88) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def flat_png(w: int = 1200, h: int = 630, colour=(200, 30, 40)) -> bytes:
    """A logo-like placeholder: two flat colours plus a little text."""
    im = Image.new("RGB", (w, h), colour)
    ImageDraw.Draw(im).rectangle((w // 2, 0, w, h), fill=(255, 255, 255))
    ImageDraw.Draw(im).text((40, 40), "LOGO", fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


class FakeFetcher:
    """Plays the web for official_image.Fetcher.get: routes map URL (or URL prefix) to
    (status, content_type, body) or ("redirect", location). Every hop goes through hop_check."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def _route(self, url: str):
        if url in self.routes:
            return self.routes[url]
        base = url.split("?")[0]
        if base in self.routes:
            return self.routes[base]
        return (404, "text/html", b"not found")

    def get(self, url, *, max_bytes, hop_check=None, params=None, accept="*/*"):
        if params:
            url = f"{url}?{urlencode(params)}"
        for _ in range(6):
            if urlsplit(url).scheme != "https":
                raise official_image.ResolveError(f"not https: {url}")
            if hop_check:
                hop_check(url)
            self.calls.append(url)
            route = self._route(url)
            if route[0] == "redirect":
                url = urljoin(url, route[1])
                continue
            status, ctype, body = route
            if len(body) > max_bytes:
                raise official_image.ResolveError(f"{url} is over the limit")
            return official_image.Fetched(url, status, ctype, body)
        raise official_image.ResolveError("too many redirects")


def oembed(author_name: str, author_url: str, title: str = "Kaalam | Official Trailer | Netflix India") -> tuple:
    return (200, "application/json", json.dumps({
        "title": title, "author_name": author_name, "author_url": author_url, "type": "video",
        "provider_name": "YouTube", "thumbnail_url": "https://i.ytimg.com/vi/x/hqdefault.jpg"}).encode())


GOOD_SCORE = {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 1, "alone": 1, "total": 12,
              "notes": "original: official image; alone: needs the caption for the date"}
REVIEWER_SCORE = {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 2, "alone": 1, "total": 13,
                  "notes": "alone: needs the caption for the date"}

CAPTION = """The 2026 WagonR was India's best-selling car in October, with 23,747 units sold.

The Brezza finished second, just 1,311 units behind, after an 86% jump.

Which car would you pick for city driving?

Full story on idly.news (link in bio).

#WagonR #Maruti #CarSales #idlyautomotive"""


def make_spec(**over) -> dict:
    spec = {
        "account": "idlyautomotive", "story_id": 990001, "idly_article": True,
        "title": "WagonR stays India's best-selling car in October",
        "headline": "WagonR stays India's best-selling car in October",
        "caption": CAPTION,
        "alt_text": "A white Maruti Suzuki WagonR in a showroom, with the headline on the card.",
        "sources": ["Autocar India", "Rushlane"],
        "detail_slides": [{"stat": "23,747", "stat_label": "WagonR sales in October",
                           "bullets": ["Brezza second, 1,311 units behind", "Top five: WagonR, Brezza, Nexon"]}],
        "image": {"resolver": "og_image_official", "ref": "https://www.marutisuzuki.com/press/wagonr-october"},
        "scores": {"self": dict(GOOD_SCORE)},
        "created_at": (now_utc() - timedelta(minutes=20)).isoformat(timespec="seconds"),
    }
    spec.update(over)
    return spec


def og_routes(image_bytes: bytes | None = None) -> dict:
    page = (FIXTURES / "og_official_page.html").read_bytes()
    img = image_bytes if image_bytes is not None else CAR.read_bytes()
    return {
        "https://www.marutisuzuki.com/press/wagonr-october": (200, "text/html", page),
        "https://www.marutisuzuki.com/content/dam/press/logo-maruti.png": (200, "image/png", flat_png()),
        "https://www.marutisuzuki.com/content/dam/press/wagonr-front.jpg": (200, "image/jpeg", img),
    }


def stub_renderer(posts, out_dir, png_dir, report):
    """Stand-in for cardkit (no Chrome needed): one 1080x1350 JPEG per slide, plus cardkit-style report rows."""
    out = []
    for p in posts:
        d = Path(out_dir) / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        for i, s in enumerate(p["slides"], 1):
            if s["type"] == "cover":
                im = Image.open(s["photo"]).convert("RGB").resize((1080, 1350))
            else:
                im = Image.new("RGB", (1080, 1350), (14, 14, 16))
            path = d / f"{i:02d}.jpg"
            im.save(path, "JPEG", quality=85)
            out.append(str(path))
            report.append({"slug": p["slug"], "slide": i, "type": s["type"], "overflow": False,
                           "scale": 1.0 if s["type"] == "cover" else None, "jpg": str(path),
                           "credit_line": s.get("photo_credit") if s["type"] == "cover" else "Sources: stub",
                           "credit_collision": [], "credit_inside": True})
    return out


def stub_story_renderer(post, out_jpg, report):
    """Stand-in for cardkit.vertical.render_story (no Chrome): a 1080x1920 JPEG and a clean report row."""
    slide = post["slides"][0]
    v = slide.get("vertical") or {}
    im = Image.open(v.get("photo") or slide["photo"]).convert("RGB").resize((1080, v.get("photo_h") or 1350))
    card = Image.new("RGB", (1080, 1920), (10, 10, 10))
    card.paste(im, (0, 0))
    card.save(out_jpg, "JPEG", quality=85)
    report.append({"page": "cover", "type": "cover", "overflow": False, "collisions": [], "ui_zone": [],
                   "outside": [], "truncated": [], "left_edges": {"kicker": 64, "headline": 64, "date": 64},
                   "min_font_px": 30, "scale": 1.0, "photo_h": v.get("photo_h") or 1350})
    return str(out_jpg)


def chrome_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    from cardkit.render import _chrome
    if _chrome():
        return True
    return any(Path.home().joinpath(".cache", "ms-playwright").glob("chromium*"))
