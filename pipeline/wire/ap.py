"""AP Media API adapter (Associated Press), from AP's public developer guide (api.ap.org/media/v/docs).

Secret: AP_MEDIA_API_KEY (the API key from AP's Media API / AP Newsroom account).
Calls:
  GET https://api.ap.org/media/v/content/search?q=...&sort=versioncreated:desc&page_size=50&in_my_plan=true
  GET https://api.ap.org/media/v/content/{item_id}?in_my_plan=true
  GET <renditions.main.href>          (the download link from the item; AP may redirect to mapi.associatedpress.com)
The key goes only in the x-api-key header, and only to AP's two hosts.

No spend: every request carries in_my_plan=true ("only those items that do not incur any additional cost to
download"), a rendition marked "priced" is refused, and we never append a pricetag (which is how AP takes the
acknowledgement for a charged download). Only AP's own photos are used (creditline AP / ASSOCIATED PRESS):
partner content AP redistributes can carry other terms, and Reuters/Getty never.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlsplit

import requests

from .base import AGENCY_CREDIT, DENIED_CREDIT, Candidate, NotConfigured, WireAdapter, WireError

BASE = "https://api.ap.org/media/v"
ALLOWED_HOSTS = ("api.ap.org", "mapi.associatedpress.com")
KEY_ENV = "AP_MEDIA_API_KEY"
MAX_BYTES = 40 * 1024 * 1024
AP_CREDITLINES = {"AP", "ASSOCIATED PRESS", "THE ASSOCIATED PRESS"}
# usage terms / editor's notes that rule a photo out for an Instagram post
RESTRICTED = re.compile(r"\b(no (online|internet|web|digital|social)|(online|internet|social media|web) out|"
                        r"do not (use|publish)|kill(ed)?\b|withdrawn|eds?:? (this|the) (photo|image) (has been|is) "
                        r"(eliminated|withdrawn)|elimination|mandatory (out|kill))", re.I)


def ap_credit(item: dict) -> str:
    name = str((item.get("photographer") or {}).get("name") or "").strip()
    if not name:
        bylines = item.get("bylines") or []
        name = str((bylines[0] if bylines else {}).get("by") or "").strip()
    return AGENCY_CREDIT["ap"].format(photographer=name) if name else "AP Photo"


def _restricted(item: dict) -> str | None:
    terms = item.get("usageterms") or []
    terms = " ".join(terms) if isinstance(terms, list) else str(terms)
    text = " ".join([terms, str(item.get("ednote") or "")])
    m = RESTRICTED.search(text)
    return m.group(0) if m else None


def _parse_time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def check_item(item: dict) -> str | None:
    """Why this AP item can't be used, or None."""
    if item.get("type") != "picture":
        return f"type {item.get('type')!r}, not a picture"
    if item.get("pubstatus") not in (None, "usable"):
        return f"pubstatus {item.get('pubstatus')!r}"
    emb = _parse_time(item.get("embargoed"))
    if emb and emb > datetime.now(timezone.utc):
        return "embargoed"
    creditline = str(item.get("description_creditline") or "").strip().upper()
    if creditline not in AP_CREDITLINES:
        return f"not an AP photo (credit line {creditline or 'missing'})"
    who = " ".join(str(x) for x in (creditline, (item.get("photographer") or {}).get("name"),
                                    item.get("copyrightnotice")) if x)
    if DENIED_CREDIT.search(who):
        return "Reuters/Getty/other unlicensed agency"
    if why := _restricted(item):
        return f"usage restriction: {why}"
    main = (item.get("renditions") or {}).get("main") or {}
    if not main.get("href"):
        return "no main rendition"
    if main.get("priced") in (True, "true") or str(main.get("pricetag") or "Unlimited") not in ("Unlimited",):
        return f"the download is charged ({main.get('pricetag')}): never used"
    if not str(main.get("mimetype") or "image/jpeg").startswith("image/"):
        return f"main rendition is {main.get('mimetype')}"
    return None


class APAdapter(WireAdapter):
    name = "ap"
    secrets = (KEY_ENV,)

    def __init__(self, api_key: str | None = None, session=None, base: str = BASE):
        key = os.environ.get(KEY_ENV, "") if api_key is None else api_key
        self._key = key.strip() or None
        self._s = session or requests.Session()
        self.base = base.rstrip("/")
        self.hosts = tuple({urlsplit(self.base).hostname, *ALLOWED_HOSTS})

    def configured(self) -> bool:
        return bool(self._key)

    def _get(self, url: str, params: dict | None = None, stream: bool = False):
        """GET with the key in the x-api-key header, following redirects only within AP's hosts."""
        if not self._key:
            raise NotConfigured("ap", f"set the {KEY_ENV} secret (docs/SETUP-GITHUB-SECRETS.md)")
        for _ in range(6):
            host = urlsplit(url).hostname or ""
            if urlsplit(url).scheme != "https" or host not in self.hosts:
                raise WireError(f"AP sent us to {host or url!r}: not an AP host, refused")
            try:
                r = self._s.get(url, params=params, timeout=60, stream=stream, allow_redirects=False,
                                headers={"x-api-key": self._key, "Accept-Encoding": "gzip",
                                         "User-Agent": "idly-social-lane/1.0"})
            except requests.RequestException as e:
                raise WireError(f"AP network error: {type(e).__name__}", transient=True) from e
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                url, params = urljoin(url, r.headers["Location"]), None
                continue
            if r.status_code in (401, 403):
                raise WireError(f"AP refused the key (HTTP {r.status_code}): check {KEY_ENV}")
            if r.status_code == 402:
                raise WireError("AP says this download needs payment: refused (no spend)")
            if r.status_code == 429 or r.status_code >= 500:
                raise WireError(f"AP HTTP {r.status_code}", transient=True)
            if r.status_code != 200:
                raise WireError(f"AP HTTP {r.status_code}")
            return r
        raise WireError("AP: too many redirects")

    def search(self, query: str, since: datetime) -> list[Candidate]:
        hours = max(1, math.ceil((datetime.now(timezone.utc) - since).total_seconds() / 3600 - 1 / 60))
        q = f"type:picture AND ({query}) AND versioncreated:>now-{hours}h"
        r = self._get(f"{self.base}/content/search",
                      {"q": q, "sort": "versioncreated:desc", "page_size": 50, "in_my_plan": "true"})
        items = ((r.json().get("data") or {}).get("items")) or []
        out = []
        for row in items:
            item = row.get("item") or {}
            if check_item(item):
                continue
            main = item["renditions"]["main"]
            preview = (item.get("renditions") or {}).get("preview") or {}
            out.append(Candidate(
                agency="ap", id=str((item.get("altids") or {}).get("itemid") or ""),
                caption=str(item.get("description_caption") or item.get("headline") or ""),
                credit=ap_credit(item), preview_url=preview.get("href"),
                created_at=item.get("firstcreated") or item.get("versioncreated"),
                width=main.get("width"), height=main.get("height"), headline=str(item.get("headline") or "")))
        return [c for c in out if c.id]

    def download(self, id: str) -> tuple[bytes, str]:
        if not re.fullmatch(r"[0-9a-fA-F]{32}", id or ""):
            raise WireError(f"not an AP item id: {id!r}")
        data = self._get(f"{self.base}/content/{quote(id)}", {"in_my_plan": "true"}).json()
        item = (data.get("data") or {}).get("item") or {}
        if why := check_item(item):
            raise WireError(f"AP item {id}: {why}")
        r = self._get(item["renditions"]["main"]["href"], stream=True)
        body = bytearray()
        for chunk in r.iter_content(1 << 16):
            body += chunk
            if len(body) > MAX_BYTES:
                raise WireError(f"AP item {id}: the image is over {MAX_BYTES >> 20} MB")
        return bytes(body), ap_credit(item)
