"""Resolve an official image for a lane spec, under strict source rules (config/official_sources.json).

    res = official_image.resolve({"resolver": "youtube_official", "ref": "https://youtu.be/<id>"}, spec)
    res.data, res.credit, res.source_url, res.image_url, res.log

Resolvers, in the order the lane tries them (licensed_wire always first):

licensed_wire       a licensed agency photo (AP; PTI, ANI, IANS once their APIs are set up), through the
                    agency's official API only (pipeline/wire/). Picks the newest photo relevant to the query and
                    the story that is big enough and passes face framing. Credit: the agency's own format,
                    e.g. "AP Photo/<Photographer>", "Photo: PTI", "ANI Photo", "Photo: IANS".
youtube_official    an official trailer/teaser: the uploader, from YouTube's keyless oEmbed endpoint
                    (author_url), must be on the allowlist. Image: the video thumbnail (maxresdefault, then
                    hqdefault). Credit: "Image: <channel> (official trailer)".
og_image_official   a company newsroom / press release / studio or streamer page on an allowlisted domain:
                    its og:image (or twitter:image). Credit: "Image: <organisation>".

Always refused: news outlets and photo agencies' websites (denied_domains, checked for the page, every redirect
and the image URL), placeholders (logos, blanks, tiny or flat images), and anything under 900 px wide
(1080 px at <= 1.2x upscale; the framing step checks the exact upscale of the composition it picks).
Errors are ResolveError(reason, transient): transient means "try again next run" (network, 5xx, 429).
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from PIL import Image, ImageOps, ImageStat

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import framing, wire
from pipeline.common import REPO, log

SOURCES_FILE = REPO / "config" / "official_sources.json"
RESOLVERS = ("licensed_wire", "youtube_official", "og_image_official")    # priority order
MIN_WIDTH = 900                       # sources stay high-res; the 4:5 crop may then be enlarged up to 2x
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_HTML_BYTES = 3 * 1024 * 1024
UA = "Mozilla/5.0 (compatible; idly-social-lane/1.0; +https://idly.news)"
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be",
            "www.youtube-nocookie.com", "youtube-nocookie.com")
PLACEHOLDER_URL = re.compile(r"(placeholder|default[-_]?(og|share|social|image|thumb)|no[-_]?(image|photo)|"
                             r"blank|spacer|1x1|pixel\.|favicon|sprite|/logos?[/._-]|[-_/]logo[-_.]|"
                             r"apple-touch-icon)", re.I)
WIRE_MAX_DOWNLOADS = 3
WIRE_DEFAULT_HOURS = 72
STOPWORDS = set("""a an and are as at be by for from has have in into is it its of on or that the this to was were
will with after before over new says said its their his her they them who what when where why how about than
more most out up down off just also not no yes our your you we he she official first""".split())


class ResolveError(Exception):
    def __init__(self, reason: str, transient: bool = False):
        super().__init__(reason)
        self.reason, self.transient = reason, transient


@dataclass
class Resolved:
    resolver: str
    ref: str
    source_url: str              # the page, video or agency item the image comes from
    image_url: str               # where the bytes came from
    credit: str                  # exact credit line, e.g. "Image: Netflix India (official trailer)"
    organisation: str
    data: bytes
    width: int
    height: int
    log: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {"resolver": self.resolver, "ref": self.ref, "source_url": self.source_url,
                "image_url": self.image_url, "credit": self.credit, "organisation": self.organisation,
                "image_size": [self.width, self.height], "log": self.log,
                **{k: v for k, v in self.extra.items() if k != "plan"}}


# ---- the allowlist ----------------------------------------------------------------------------------

def load_sources(path: Path | None = None) -> dict:
    return json.loads(Path(path or SOURCES_FILE).read_text(encoding="utf-8"))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def host_matches(host: str, domain: str) -> bool:
    domain = domain.lower().strip(".")
    return host == domain or host.endswith("." + domain)


def denied(url: str, sources: dict) -> str | None:
    """The denylisted domain this URL is on, if any."""
    host = host_of(url)
    return next((d for d in sources.get("denied_domains", []) if host_matches(host, d)), None)


def official_entry(url: str, sources: dict) -> dict | None:
    """The official_domains entry that allows this page URL (host, and path prefix where set)."""
    host, path = host_of(url), urlsplit(url).path or "/"
    for entry in sources.get("official_domains", []):
        if not host_matches(host, entry["domain"]):
            continue
        prefixes = entry.get("path_prefixes")
        if not prefixes or any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes):
            return entry
    return None


def normalise_author_url(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = re.sub(r"^http://", "https://", u)
    return re.sub(r"^https://(m\.|music\.)?youtube\.com", "https://www.youtube.com", u)


def official_channel(author_url: str, sources: dict) -> dict | None:
    """The allowlisted channel whose handle URL (or /channel/<id> URL) is this oEmbed author_url."""
    got = normalise_author_url(author_url)
    if not got:
        return None
    for ch in sources.get("youtube_channels", []):
        keys = {normalise_author_url(ch["author_url"])}
        if ch.get("channel_id"):
            keys.add(normalise_author_url(f"https://www.youtube.com/channel/{ch['channel_id']}"))
        if got in keys:
            return ch
    return None


# ---- fetching -------------------------------------------------------------------------------------

@dataclass
class Fetched:
    url: str                     # final URL after redirects
    status: int
    content_type: str
    content: bytes


class Fetcher:
    """HTTPS GET with a byte cap and redirects followed by hand, so every hop can be checked."""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})

    def get(self, url: str, *, max_bytes: int, hop_check=None, params: dict | None = None,
            accept: str = "*/*") -> Fetched:
        for _ in range(6):
            if urlsplit(url).scheme != "https":
                raise ResolveError(f"not https: {url}")
            if hop_check:
                hop_check(url)
            try:
                r = self.s.get(url, params=params, timeout=30, stream=True, allow_redirects=False,
                               headers={"Accept": accept})
            except requests.RequestException as e:
                raise ResolveError(f"network error for {host_of(url)}: {type(e).__name__}", transient=True) from e
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                url, params = urljoin(r.url, r.headers["Location"]), None
                r.close()
                continue
            body = bytearray()
            if r.status_code == 200:
                for chunk in r.iter_content(1 << 16):
                    body += chunk
                    if len(body) > max_bytes:
                        r.close()
                        raise ResolveError(f"{url} is over {max_bytes >> 20} MB")
            r.close()
            return Fetched(r.url, r.status_code, r.headers.get("Content-Type", ""), bytes(body))
        raise ResolveError(f"too many redirects from {url}")


FETCHER = Fetcher()      # tests swap this for a fake


def _http_error(what: str, f: Fetched) -> ResolveError:
    transient = f.status == 429 or f.status >= 500
    return ResolveError(f"{what}: HTTP {f.status}", transient=transient)


# ---- image checks ---------------------------------------------------------------------------------

def open_image(data: bytes) -> Image.Image:
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:  # noqa: BLE001 - any decode failure means "not a usable image"
        raise ResolveError(f"not a readable image ({type(e).__name__})") from e
    if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
        raise ResolveError("animated image")
    if im.format not in ("JPEG", "PNG", "WEBP"):
        raise ResolveError(f"unsupported image format {im.format}")
    return ImageOps.exif_transpose(im).convert("RGB")


def placeholder_reason(im: Image.Image, url: str = "") -> str | None:
    """Why this looks like a placeholder, logo or blank, or None."""
    if url and PLACEHOLDER_URL.search(urlsplit(url).path):
        return f"looks like a placeholder or logo ({urlsplit(url).path.rsplit('/', 1)[-1]})"
    w, h = im.size
    if w < 200 or h < 200:
        return f"tiny image ({w}x{h})"
    if not 0.33 <= w / h <= 3.0:
        return f"banner-shaped image ({w}x{h})"
    small = im.resize((64, 64))
    if ImageStat.Stat(small.convert("L")).stddev[0] < 6:
        return "flat, single-colour image"
    import numpy as np
    colours = len(np.unique((np.asarray(small.convert("RGB")) >> 3).reshape(-1, 3), axis=0))
    if colours < 12:
        return f"only {colours} colours: a logo or graphic, not a photo"
    return None


def check_image(data: bytes, url: str) -> Image.Image:
    im = open_image(data)
    if why := placeholder_reason(im, url):
        raise ResolveError(why)
    if im.width < MIN_WIDTH:
        raise ResolveError(f"image is {im.width}x{im.height}: under {MIN_WIDTH}px wide, so 1080px would need "
                           f"more than {framing.MAX_UPSCALE}x upscale")
    return im


# ---- youtube_official ---------------------------------------------------------------------------------

def youtube_id(ref: str) -> str:
    ref = (ref or "").strip()
    if YT_ID.match(ref):
        return ref
    u = urlsplit(ref if "://" in ref else "https://" + ref)
    host = (u.hostname or "").lower()
    if host not in YT_HOSTS:
        raise ResolveError(f"not a YouTube URL: {ref}")
    if host == "youtu.be":
        cand = u.path.strip("/").split("/")[0]
    elif u.path == "/watch":
        cand = (parse_qs(u.query).get("v") or [""])[0]
    else:
        parts = [p for p in u.path.split("/") if p]
        cand = parts[1] if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v") else ""
    if not YT_ID.match(cand or ""):
        raise ResolveError(f"no video id in {ref}")
    return cand


def video_kind(title: str) -> str:
    t = (title or "").lower()
    if "teaser" in t:
        return "official teaser"
    if re.search(r"\b(trailer|glimpse|first look|promo|sneak peek|motion poster)\b", t):
        return "official trailer"
    return "official video"


def resolve_youtube(attempt: dict, sources: dict) -> Resolved:
    vid = youtube_id(attempt.get("ref", ""))
    watch = f"https://www.youtube.com/watch?v={vid}"
    f = FETCHER.get("https://www.youtube.com/oembed", params={"url": watch, "format": "json"},
                    max_bytes=256 * 1024, accept="application/json")
    if f.status in (401, 403, 404):
        raise ResolveError(f"YouTube oEmbed HTTP {f.status}: the video is private, removed or not embeddable")
    if f.status != 200:
        raise _http_error("YouTube oEmbed", f)
    try:
        meta = json.loads(f.content.decode("utf-8"))
    except ValueError as e:
        raise ResolveError("YouTube oEmbed returned no JSON", transient=True) from e
    author_url, author = meta.get("author_url", ""), meta.get("author_name", "")
    channel = official_channel(author_url, sources)
    lines = [f"oEmbed {watch}: author {author!r} {author_url}, title {meta.get('title', '')!r}"]
    if not channel:
        raise ResolveError(f"uploader {author!r} ({author_url or 'no author_url'}) is not on the official "
                           f"channel allowlist (config/official_sources.json)")
    errors = []
    for name in ("maxresdefault.jpg", "hqdefault.jpg"):
        url = f"https://i.ytimg.com/vi/{vid}/{name}"
        img = FETCHER.get(url, max_bytes=MAX_IMAGE_BYTES, accept="image/*")
        if img.status != 200:
            errors.append(f"{name}: HTTP {img.status}")
            if img.status == 429 or img.status >= 500:
                raise _http_error(f"thumbnail {name}", img)
            continue
        try:
            im = check_image(img.content, url)
        except ResolveError as e:
            errors.append(f"{name}: {e.reason}")
            continue
        lines.append(f"thumbnail {url} ({im.width}x{im.height})")
        kind = video_kind(meta.get("title", ""))
        return Resolved("youtube_official", attempt.get("ref", ""), watch, url,
                        f"Image: {channel['name']} ({kind})", channel["name"], img.content, im.width, im.height,
                        lines, {"channel": channel["author_url"], "video_title": meta.get("title", "")})
    raise ResolveError("no usable thumbnail: " + "; ".join(errors))


# ---- og_image_official ------------------------------------------------------------------------------

class _MetaParser(HTMLParser):
    KEYS = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src",
            "og:site_name", "og:title")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.base: str | None = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "base" and a.get("href") and self.base is None:
            self.base = a["href"]
        if tag != "meta":
            return
        key = (a.get("property") or a.get("name") or "").strip().lower()
        if key in self.KEYS and a.get("content", "").strip():
            self.meta.setdefault(key, []).append(a["content"].strip())


def parse_og(html_text: str, page_url: str) -> dict:
    """{"images": [absolute URLs in preference order], "site_name": str, "title": str}."""
    p = _MetaParser()
    try:
        p.feed(html_text)
    except Exception:  # noqa: BLE001 - malformed HTML: keep whatever was parsed
        pass
    base = urljoin(page_url, p.base) if p.base else page_url
    images = []
    for key in ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src"):
        for v in p.meta.get(key, []):
            url = urljoin(base, v)
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            if url not in images:
                images.append(url)
    first = lambda k: (p.meta.get(k) or [""])[0]  # noqa: E731
    return {"images": images, "site_name": first("og:site_name"), "title": first("og:title")}


def resolve_og(attempt: dict, sources: dict) -> Resolved:
    page = (attempt.get("ref") or "").strip()
    if not page.startswith("https://"):
        raise ResolveError(f"og_image_official needs an https URL: {page!r}")

    def page_hop(url):
        if d := denied(url, sources):
            raise ResolveError(f"{host_of(url)} is a news outlet / agency site ({d}): never used")
        if not official_entry(url, sources):
            raise ResolveError(f"{host_of(url)}{urlsplit(url).path} is not an official domain on the allowlist")

    page_hop(page)
    f = FETCHER.get(page, max_bytes=MAX_HTML_BYTES, hop_check=page_hop, accept="text/html,*/*;q=0.5")
    if f.status != 200:
        raise _http_error(f"official page {page}", f)
    entry = official_entry(f.url, sources)
    og = parse_og(f.content.decode("utf-8", errors="replace"), f.url)
    lines = [f"page {f.url} ({entry['organisation']}): og:title {og['title']!r}, {len(og['images'])} image(s)"]
    if not og["images"]:
        raise ResolveError(f"{f.url} has no og:image or twitter:image")

    def image_hop(url):
        if d := denied(url, sources):
            raise ResolveError(f"image host {host_of(url)} is a news outlet / agency ({d}): never used")

    errors = []
    for url in og["images"][:4]:
        try:
            image_hop(url)
            img = FETCHER.get(url, max_bytes=MAX_IMAGE_BYTES, hop_check=image_hop, accept="image/*")
            if img.status != 200:
                raise _http_error(f"image {url}", img)
            im = check_image(img.content, img.url)
        except ResolveError as e:
            if e.transient:
                raise
            errors.append(f"{url}: {e.reason}")
            continue
        lines.append(f"image {img.url} ({im.width}x{im.height})")
        return Resolved("og_image_official", page, f.url, img.url, f"Image: {entry['organisation']}",
                        entry["organisation"], img.content, im.width, im.height, lines,
                        {"og_title": og["title"]})
    raise ResolveError("no usable og:image: " + "; ".join(errors))


# ---- licensed_wire ------------------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in STOPWORDS]


def relevance(candidate_text: str, query: str, story_text: str = "") -> float:
    """Share of the query's words found in the photo's caption (story words add a small bonus)."""
    have = set(_tokens(candidate_text))
    q = list(dict.fromkeys(_tokens(query)))
    if not q:
        return 0.0
    score = sum(t in have for t in q) / len(q)
    story = [t for t in dict.fromkeys(_tokens(story_text)) if t not in q]
    if story:
        score += 0.25 * sum(t in have for t in story) / len(story)
    return score


def _created(c) -> datetime:
    try:
        return datetime.fromisoformat(str(c.created_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def resolve_wire(attempt: dict, spec: dict, sources: dict) -> Resolved:
    query = (attempt.get("query") or "").strip()
    hours = int(attempt.get("since_hours") or WIRE_DEFAULT_HOURS)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    story = " ".join(str(spec.get(k) or "") for k in ("headline", "title", "caption"))
    names = attempt.get("agencies") or list(wire.ORDER)
    denied_agencies = [a.lower() for a in sources.get("denied_agencies", [])]
    lines, errors, transient = [], [], False
    candidates = []
    for name in names:
        if any(d in name.lower() for d in denied_agencies):
            errors.append(f"{name}: no licence, never used")
            continue
        try:
            adapter = wire.get_adapter(name)
            if not adapter.configured():
                raise wire.NotConfigured(name, f"not configured (secrets {', '.join(adapter.secrets)})")
            found = adapter.search(query, since)
        except wire.NotConfigured as e:
            errors.append(str(e))
            continue
        except wire.WireError as e:
            transient |= e.transient
            errors.append(f"{name}: {e}")
            continue
        lines.append(f"{name}: {len(found)} photo(s) for {query!r} since {since:%d %b %H:%M} UTC")
        for c in found:
            if wire.DENIED_CREDIT.search(c.credit or ""):
                continue
            if c.width and c.width < MIN_WIDTH:
                continue
            rel = relevance(" ".join([c.caption, c.headline]), query, story)
            if rel >= 0.6:
                candidates.append((rel, c, adapter))
    if not candidates:
        raise ResolveError("licensed_wire: no relevant, big-enough photo (" + ("; ".join(errors) or
                           "searched, nothing matched") + ")", transient=transient)
    candidates.sort(key=lambda t: (_created(t[1]), t[0]), reverse=True)     # newest first
    for rel, c, adapter in candidates[:WIRE_MAX_DOWNLOADS]:
        try:
            data, credit = adapter.download(c.id)
            im = check_image(data, "")
            plan = framing.plan_image(im)
        except wire.WireError as e:
            transient |= e.transient
            errors.append(f"{c.agency} {c.id}: {e}")
            continue
        except (ResolveError, framing.FramingError) as e:
            errors.append(f"{c.agency} {c.id}: {e}")
            continue
        lines.append(f"picked {c.agency} {c.id} ({im.width}x{im.height}, relevance {rel:.2f}, {c.created_at}): "
                     f"{c.caption[:120]!r}")
        return Resolved("licensed_wire", query, f"{c.agency}:{c.id}", c.preview_url or f"{c.agency}:{c.id}",
                        credit, wire.AGENCY_NAMES.get(c.agency, c.agency), data, im.width, im.height, lines,
                        {"agency": c.agency, "item_id": c.id, "wire_caption": c.caption, "plan": plan})
    raise ResolveError("licensed_wire: no candidate passed: " + "; ".join(errors), transient=transient)


# ---- entry point ------------------------------------------------------------------------------------

def attempts_of(image: dict) -> list[dict]:
    """The spec's image attempts (main + fallbacks), licensed_wire first, otherwise in the spec's order."""
    main = {k: v for k, v in image.items() if k != "fallback"}
    items = [main] + list(image.get("fallback") or [])
    return sorted(items, key=lambda a: a.get("resolver") != "licensed_wire")      # stable: spec order otherwise


def resolve(attempt: dict, spec: dict | None = None, sources: dict | None = None) -> Resolved:
    sources = sources or load_sources()
    kind = attempt.get("resolver")
    if kind == "youtube_official":
        res = resolve_youtube(attempt, sources)
    elif kind == "og_image_official":
        res = resolve_og(attempt, sources)
    elif kind == "licensed_wire":
        res = resolve_wire(attempt, spec or {}, sources)
    else:
        raise ResolveError(f"unknown resolver {kind!r}")
    log(f"  resolver={res.resolver} source={res.source_url} image={res.image_url} credit={res.credit!r}")
    return res


def resolve_first(image: dict, spec: dict, sources: dict | None = None) -> tuple[Resolved, list[dict]]:
    """Try each attempt in order; returns the first success and the log of every attempt.
    Raises ResolveError (transient if any failure was transient) when none works."""
    sources = sources or load_sources()
    tried, transient = [], False
    for attempt in attempts_of(image):
        ref = attempt.get("ref") or attempt.get("query")
        try:
            res = resolve(attempt, spec, sources)
            tried.append({"resolver": attempt["resolver"], "ref": ref, "ok": True})
            return res, tried
        except ResolveError as e:
            transient |= e.transient
            tried.append({"resolver": attempt.get("resolver"), "ref": ref, "ok": False, "reason": e.reason,
                          "transient": e.transient})
            log(f"  resolver={attempt.get('resolver')} ref={ref}: {e.reason}")
    raise ResolveError("no image: " + " | ".join(f"{t['resolver']}: {t['reason']}" for t in tried),
                       transient=transient)
