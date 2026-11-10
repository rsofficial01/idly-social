"""Publish to Instagram with Meta's official Instagram API (graph.instagram.com / graph.facebook.com).

    # one image (repo-relative path -> public raw.githubusercontent.com URL, or a full https URL)
    python3 pipeline/publish.py post --account idlytech --image posts/2026-11-09/pm-idlytech-1691.jpg \
        --caption-file caption.txt --score-file score.json --story-id 1691 [--collaborator idlynews] [--dry-run]
    # carousel: repeat --image / --video (2-10 items, in order). .mp4/.mov items are carousel videos.
    python3 pipeline/publish.py check [--offline] [--no-refresh]   # every account: token, id, host, quota, expiry

Access, per account (first match wins):
1. IG_TOKEN_<ACCOUNT>: that account's own token from the Meta dashboard ("Generate token"). Its host is
   auto-detected: GET graph.instagram.com/me?fields=user_id,username, then graph.facebook.com/me?fields=id,name.
   The working host and the account id are remembered in state/accounts.json (never the token).
2. Shared: ONE system-user access token for all accounts, on graph.facebook.com. In the Claude cloud it is a
   network secret: the agent proxy adds "Authorization: Bearer ..." and this code sends no credentials.
   Anywhere else, IG_SYSTEM_TOKEN.
Tokens are sent only as the Authorization: Bearer header: never in a URL or a request body, never printed,
logged or saved. Nothing is published unless the post's 7-check score is >= 12/14.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial
from pipeline.common import (ACCOUNTS, BUSINESS_ID, REPO, TOKEN_ENV, append_posted, default_date,
                             default_slot, load_account_ids, load_accounts, log, now_utc, public_url,
                             repo_path, token_env, update_accounts)

GRAPH = "https://graph.facebook.com"        # Facebook Login (the shared system-user token)
GRAPH_IG = "https://graph.instagram.com"    # Instagram User tokens
FB_HOST, IG_HOST = "graph.facebook.com", "graph.instagram.com"
HOSTS = (IG_HOST, FB_HOST)                  # detection order for an account's own token
API_VERSION = "v27.0"            # latest Graph API version in Meta's docs (v27.0, released 4 Nov 2026)
LOCAL_DAILY_CAP = 25             # our own cap; Meta's quota (config.quota_total) is also respected
EXPIRY_WARN_DAYS = 10
MAX_JPEG_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 10                   # carousel items (Meta allows more; we keep 10)
MAX_COLLABORATORS = 3            # Meta: "a list of up to 3 instagram usernames"
VIDEO_EXT = (".mp4", ".mov")
POLL_WAITS = [3, 5, 10, 20, 30, 60, 60, 60, 60]   # ~5 minutes in total, per Meta's guidance
# Meta error codes worth retrying: temporary, throttling, "media not ready", "could not fetch media"
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613, 9004, 9007}
AUTH_CODES = {102, 190, 2500}    # no access token, or an invalid / revoked one
PERMISSION_CODES = {3, 10, 200}
USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")

AUTH_HINT = ("Meta got no valid shared access token. In the Claude cloud environment, add the network secret "
             "for graph.facebook.com (RUNBOOK.md, 'Meta access'); elsewhere set IG_SYSTEM_TOKEN")
PERMISSION_HINT = ("check the login configuration's permissions and that the Instagram account is an asset "
                   "of the token's user (RUNBOOK.md, 'Meta access')")


class GateRefused(Exception):
    pass


class IGError(Exception):
    def __init__(self, message: str, code=None, transient=False, hint: str = ""):
        super().__init__(message + (f" [{hint}]" if hint else ""))
        self.message, self.code, self.transient = message, code, transient


class WrongAccount(IGError):
    """The token works, but for a different Instagram account: never post with it."""


def base_url(host: str) -> str:
    return GRAPH_IG if host == IG_HOST else GRAPH      # read at call time (tests point these at a mock)


def account_token(account: str) -> str | None:
    """This account's own token (IG_TOKEN_<ACCOUNT>), or None to use the shared token."""
    return os.environ.get(token_env(account), "").strip() or None


def auth_mode() -> str:
    """'env' when IG_SYSTEM_TOKEN is set, else 'network-secret' (the agent proxy adds the header)."""
    return "env" if os.environ.get(TOKEN_ENV, "").strip() else "network-secret"


def describe_auth(mode: str | None = None) -> str:
    """The shared token."""
    if (mode or auth_mode()) == "env":
        return f"{TOKEN_ENV} is set: sent only as the Authorization: Bearer header (never printed)"
    return (f"{TOKEN_ENV} not set: no credentials sent; the network secret for graph.facebook.com "
            f"adds the Authorization header at the agent proxy")


def describe_account_auth(account: str, host: str | None = None) -> str:
    if account_token(account) is None:
        return f"shared token: {describe_auth()}"
    where = host or "host auto-detected (graph.instagram.com, then graph.facebook.com)"
    return f"{token_env(account)} is set: Authorization: Bearer header only (never printed); {where}"


class IGClient:
    """Tiny Graph API client. Credentials, if any, live only in the session's Authorization header.

    token=None: the shared token (IG_SYSTEM_TOKEN if set, else no credentials: the network secret adds
    them). label: the env var a per-account token came from, used in error hints."""

    def __init__(self, token: str | None = None, host: str = FB_HOST, label: str | None = None):
        token = os.environ.get(TOKEN_ENV, "") if token is None else token
        self._token = token.strip() or None
        self.host = host
        self.hint = (f"{label} was refused: generate a new token for this account in the Meta dashboard"
                     if label else AUTH_HINT)
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "idly-social/2.0"
        if self._token:
            self._s.headers["Authorization"] = f"Bearer {self._token}"

    def _clean(self, text: str) -> str:
        text = str(text)
        return text.replace(self._token, "***") if self._token else text

    def call(self, method: str, path: str, params=None, data=None, attempts: int = 4,
             versioned: bool = True) -> dict:
        root = base_url(self.host)
        url = f"{root}/{API_VERSION}/{path}" if versioned else f"{root}/{path}"
        for attempt in range(1, attempts + 1):
            try:
                r = self._s.request(method, url, params=params, data=data, timeout=60, allow_redirects=False)
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                if r.ok and "error" not in body:
                    return body
                e = body.get("error") or {}
                code = e.get("code")
                hint = (self.hint if code in AUTH_CODES else PERMISSION_HINT if code in PERMISSION_CODES else "")
                err = IGError(self._clean(f"{method} {self.host}/{path} -> HTTP {r.status_code}, code {code}"
                                          f"/{e.get('error_subcode')}: {e.get('message') or r.reason}"),
                              code=code, hint=hint,
                              transient=bool(e.get("is_transient")) or code in TRANSIENT_CODES
                              or r.status_code == 429 or r.status_code >= 500)
            except requests.RequestException as ex:
                err = IGError(self._clean(f"{method} {self.host}/{path} -> network error: {type(ex).__name__}"),
                              transient=True)
            if not err.transient or attempt == attempts:
                raise err
            wait = min(60, 2 ** attempt) + random.uniform(0, 1)
            log(f"    retry {attempt}/{attempts - 1} in {wait:.0f}s ({err})")
            time.sleep(wait)

    # -- endpoints --------------------------------------------------------
    def me(self, fields: str = "id,name") -> dict:
        return self.call("GET", "me", params={"fields": fields}, attempts=2)

    def ig_user(self, ig_id: str) -> dict:
        return self.call("GET", ig_id, params={"fields": "id,username"})

    def ig_me(self) -> dict:
        """graph.instagram.com only: the Instagram account the token belongs to (user_id, username)."""
        return self.call("GET", "me", params={"fields": "user_id,username"}, attempts=2)

    def token_expiry(self) -> tuple[int | None, str]:
        """graph.instagram.com tokens only: GET /refresh_access_token (token in the header, as always).
        Meta answers with a token and expires_in. If it is the very token we hold, expires_in is its
        remaining life (the call also extended it). If Meta hands back a different token, it is dropped
        right here, never saved or printed, and the expiry of ours stays unknown."""
        data = self.call("GET", "refresh_access_token", params={"grant_type": "ig_refresh_token"},
                         attempts=1, versioned=False)
        same = bool(self._token) and data.pop("access_token", None) == self._token
        expires_in = data.get("expires_in")
        data.clear()
        if not same:
            return None, "expiry unknown: Meta returned a new token on refresh (not saved, not used)"
        try:
            return int(expires_in) // 86400, ""
        except (TypeError, ValueError):
            return None, "expiry unknown: refresh gave no expires_in"

    def list_edge(self, path: str, fields: str, max_pages: int = 5) -> list[dict]:
        """Read a list edge with cursors. Never follows Meta's paging.next URL (it can carry a token)."""
        rows, after = [], None
        for _ in range(max_pages):
            params = {"fields": fields, "limit": 100, **({"after": after} if after else {})}
            data = self.call("GET", path, params=params, attempts=2)
            rows += data.get("data") or []
            paging = data.get("paging") or {}
            after = (paging.get("cursors") or {}).get("after")
            if not after or not paging.get("next"):
                break
        return rows

    def quota(self, ig_id: str) -> tuple[int, int]:
        data = self.call("GET", f"{ig_id}/content_publishing_limit", params={"fields": "quota_usage,config"})
        row = (data.get("data") or [{}])[0]
        return int(row.get("quota_usage", 0)), int((row.get("config") or {}).get("quota_total", LOCAL_DAILY_CAP))

    def create_container(self, ig_id: str, **fields) -> str:
        return self.call("POST", f"{ig_id}/media", data=fields)["id"]

    def wait_finished(self, container_id: str) -> None:
        for wait in POLL_WAITS:
            status = self.call("GET", container_id, params={"fields": "status_code,status"})
            code = status.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED", "PUBLISHED"):
                raise IGError(f"container {container_id} is {code}: {status.get('status', '')}")
            time.sleep(wait)
        raise IGError(f"container {container_id} not FINISHED after ~5 minutes")

    def publish(self, ig_id: str, container_id: str, caption: str) -> str:
        """media_publish is not idempotent: before any retry, check the container wasn't already published."""
        for attempt in range(1, 4):
            try:
                return self.call("POST", f"{ig_id}/media_publish", data={"creation_id": container_id},
                                 attempts=1)["id"]
            except IGError as err:
                status = self.call("GET", container_id, params={"fields": "status_code"}).get("status_code")
                if status == "PUBLISHED":
                    media_id = self.find_recent(ig_id, caption)
                    if media_id:
                        return media_id
                    raise IGError("container is PUBLISHED but its media id was not found: check the "
                                  "account before retrying") from err
                if not err.transient or attempt == 3:
                    raise
                log(f"    media_publish failed ({err}); retrying in {10 * attempt}s")
                time.sleep(10 * attempt)

    def find_recent(self, ig_id: str, caption: str) -> str | None:
        data = self.call("GET", f"{ig_id}/media", params={"fields": "id,caption", "limit": 5})
        for m in data.get("data") or []:
            if (m.get("caption") or "")[:120] == caption[:120]:
                return m["id"]
        return None

    def permalink(self, media_id: str) -> str:
        return self.call("GET", media_id, params={"fields": "permalink"}).get("permalink", "")


# ---- account discovery ----------------------------------------------------------------

def discover(client: IGClient, business_id: str = BUSINESS_ID, stop_when_complete: bool = True,
             only: list[str] | None = None) -> dict:
    """Find the Instagram professional account id of each idly username. Lookups, in order:

      1. GET /me?fields=id,name                       who the token is (the system user); also, optionally,
                                                      client_business_id (the portfolio that granted access)
      2. GET /me/assigned_instagram_accounts          Instagram accounts assigned to the system user
      3. GET /{business-id}/owned_instagram_accounts  Instagram accounts owned by the business portfolio
         GET /{business-id}/instagram_accounts
      4. GET /me/accounts?fields=instagram_business_account{id,username}    Page-linked accounts

    Returns {"found": {account: {"id", "username"}}, "attempts": [...], "via": [...], "auth_error": str|None}.
    Only ids and usernames are kept; response bodies are never printed.
    """
    wanted = {v["username"]: k for k, v in ACCOUNTS.items()}
    out = {"found": {}, "attempts": [], "via": [], "auth_error": None}

    def complete() -> bool:
        return stop_when_complete and all(a in out["found"] for a in (only or ACCOUNTS))

    def attempt(label: str, fetch) -> bool:
        """Run one lookup; returns False when the token itself was rejected (no point going on)."""
        try:
            rows = fetch()
        except IGError as e:
            out["attempts"].append({"lookup": label, "ok": False, "error": str(e)})
            if e.code in AUTH_CODES:
                out["auth_error"] = str(e)
                return False
            return True
        new = 0
        for row in rows:
            acct = wanted.get(str(row.get("username") or "").lower())
            if acct and row.get("id") and acct not in out["found"]:
                out["found"][acct] = {"id": str(row["id"]), "username": ACCOUNTS[acct]["username"]}
                new += 1
        out["attempts"].append({"lookup": label, "ok": True, "rows": len(rows), "matched": new})
        if new:
            out["via"].append(label)
        return True

    try:
        me = client.me()
        out["attempts"].append({"lookup": "GET /me?fields=id,name", "ok": True,
                                "id": me.get("id"), "name": me.get("name")})
    except IGError as e:
        out["attempts"].append({"lookup": "GET /me?fields=id,name", "ok": False, "error": str(e)})
        if e.code in AUTH_CODES:
            out["auth_error"] = str(e)
            return out
    business_ids = [business_id]
    try:          # only system-user tokens from Facebook Login for Business have this field
        client_bid = str(client.me("client_business_id").get("client_business_id") or "")
        if client_bid and client_bid not in business_ids:
            business_ids.append(client_bid)
    except IGError:
        pass

    lookups = [("GET /me/assigned_instagram_accounts",
                lambda: client.list_edge("me/assigned_instagram_accounts", "id,username"))]
    for bid in business_ids:
        lookups += [(f"GET /{bid}/owned_instagram_accounts",
                     lambda bid=bid: client.list_edge(f"{bid}/owned_instagram_accounts", "id,username")),
                    (f"GET /{bid}/instagram_accounts",
                     lambda bid=bid: client.list_edge(f"{bid}/instagram_accounts", "id,username"))]
    lookups.append(("GET /me/accounts (Page-linked)",
                    lambda: [p["instagram_business_account"] for p in
                             client.list_edge("me/accounts", "instagram_business_account{id,username}")
                             if p.get("instagram_business_account")]))
    for label, fetch in lookups:
        if complete() or not attempt(label, fetch):
            break
    return out


def verify_account(client: IGClient, account: str, ig_id: str) -> dict:
    """GET /{ig-user-id}?fields=id,username and make sure it is the account we mean to post to."""
    info = client.ig_user(ig_id)
    username, expected = str(info.get("username") or "").lower(), ACCOUNTS[account]["username"]
    if username != expected:
        raise IGError(f"account id {ig_id} is @{username or '?'}, expected @{expected}: not using it")
    return info


def summarize_attempts(attempts: list[dict]) -> str:
    return "; ".join(f"{a['lookup']}: " + (f"{a.get('matched', 0)} matched" if a["ok"] else "failed")
                     for a in attempts if "matched" in a or not a["ok"])


def resolve_account(client: IGClient, account: str) -> str:
    """graph.facebook.com: cached id (state/accounts.json) -> verified; on a miss or a mismatch, run
    discovery once."""
    cached = load_account_ids().get(account)
    if cached:
        try:
            verify_account(client, account, cached)
            return cached
        except IGError as e:
            if e.code in AUTH_CODES or e.transient:
                raise
            log(f"  cached id for @{account} didn't check out ({e}); running discovery")
    disc = discover(client, only=[account])
    if disc["auth_error"]:
        raise IGError(disc["auth_error"], code=190)
    if disc["found"]:
        update_accounts(disc["found"], disc["via"])
    hit = disc["found"].get(account)
    if not hit:
        raise IGError(f"@{ACCOUNTS[account]['username']} not found by discovery "
                      f"({summarize_attempts(disc['attempts'])}); run `publish.py check`")
    verify_account(client, account, hit["id"])
    return hit["id"]


def identify(client: IGClient, account: str, cached_id: str | None) -> str:
    """Prove this account's own token works on client.host and belongs to the account; return its id."""
    expected = ACCOUNTS[account]["username"]
    if client.host == IG_HOST:
        me = client.ig_me()                                   # GET /me?fields=user_id,username
        username = str(me.get("username") or "").lower()
        if username != expected or not me.get("user_id"):
            raise WrongAccount(f"{token_env(account)} belongs to @{username or '?'}, expected @{expected}: "
                               f"not posting with it")
        return str(me["user_id"])
    client.me()                                               # GET /me?fields=id,name: the token works here
    if not cached_id:
        disc = discover(client, only=[account])
        if account not in disc["found"]:
            raise IGError(f"@{expected} not found with {token_env(account)} "
                          f"({summarize_attempts(disc['attempts'])})")
        cached_id = disc["found"][account]["id"]
    try:
        verify_account(client, account, cached_id)
    except IGError as e:
        if "expected @" in e.message:
            raise WrongAccount(e.message) from e
        raise
    return cached_id


def connect_with_token(account: str, token: str) -> tuple[IGClient, str]:
    """Use IG_TOKEN_<ACCOUNT>: the cached host first, else graph.instagram.com then graph.facebook.com.
    Remembers the working host and the account id in state/accounts.json (never the token)."""
    cached = load_accounts().get(account, {})
    order = [cached["host"]] if cached.get("host") in HOSTS else []
    order += [h for h in HOSTS if h not in order]
    errors = []
    for host in order:
        client = IGClient(token, host=host, label=token_env(account))
        try:
            ig_id = identify(client, account, cached.get("id"))
        except WrongAccount:
            raise
        except IGError as e:
            if e.transient:
                raise
            errors.append(f"{host}: {e.message}")
            continue
        if cached.get("id") and ig_id != cached["id"]:
            log(f"  @{account}: the token's account id {ig_id} replaces the cached {cached['id']}")
        if (ig_id, host) != (cached.get("id"), cached.get("host")):
            update_accounts({account: {"id": ig_id, "host": host}})
        return client, ig_id
    raise IGError(f"{token_env(account)} works on neither host ({'; '.join(errors)})", code=190,
                  hint=f"generate a new token for @{ACCOUNTS[account]['username']} in the Meta dashboard "
                       f"and update {token_env(account)}")


def connect(account: str) -> tuple[IGClient, str]:
    """(client, Instagram account id) for publishing: the account's own token if set, else the shared one."""
    token = account_token(account)
    if token:
        return connect_with_token(account, token)
    client = IGClient()
    return client, resolve_account(client, account)


# ---- local checks --------------------------------------------------------------------

def check_jpeg(path: Path) -> None:
    """Instagram feed images: JPEG, <= 8 MB, width 320-1440, aspect 4:5 to 1.91:1."""
    from PIL import Image  # local import: only needed for local files

    if not path.is_file():
        raise ValueError(f"image not found: {path}")
    if path.stat().st_size > MAX_JPEG_BYTES:
        raise ValueError(f"{path.name} is over 8 MB")
    with Image.open(path) as im:
        if im.format != "JPEG":
            raise ValueError(f"{path.name} is {im.format}, Instagram needs JPEG")
        w, h = im.size
    if not (0.8 <= w / h <= 1.91) or not 320 <= w <= 1440:
        raise ValueError(f"{path.name} is {w}x{h}: needs width 320-1440 and aspect 4:5 to 1.91:1")


def is_video(item: str) -> bool:
    return item.split("?")[0].lower().endswith(VIDEO_EXT)


def resolve_media(item: str) -> tuple[str, str]:
    """('image' | 'video', public URL). Local files must be under posts/ (committed, so public);
    https URLs pass through unchanged. Videos are .mp4/.mov."""
    kind = "video" if is_video(item) else "image"
    if item.startswith("https://"):
        return kind, item
    if item.startswith("http://"):
        raise ValueError("media URLs must be https")
    path = repo_path(item)
    if kind == "image":
        check_jpeg(path)
    elif not path.is_file():
        raise ValueError(f"video not found: {path}")
    rel = path.resolve().relative_to(REPO).as_posix()
    if not rel.startswith("posts/"):
        raise ValueError(f"{item} must live under posts/ so it is committed and public")
    return kind, public_url(rel)


def collaborator_problems(collaborators, account: str) -> list[str]:
    """Optional collaborators: a list of up to 3 Instagram usernames, not the posting account itself."""
    if collaborators in (None, []):
        return []
    if not isinstance(collaborators, list):
        return ["collaborators must be a list of Instagram usernames, e.g. [\"idlynews\"]"]
    errs, names = [], [str(c).strip().lstrip("@").lower() for c in collaborators]
    for raw, name in zip(collaborators, names):
        if not USERNAME_RE.match(name):
            errs.append(f"collaborator {raw!r} is not an Instagram username")
    if ACCOUNTS.get(account, {}).get("username") in names:
        errs.append(f"@{account} can't be a collaborator on its own post")
    if len(set(names)) > MAX_COLLABORATORS:
        errs.append(f"at most {MAX_COLLABORATORS} collaborators (has {len(set(names))})")
    return errs


def clean_collaborators(collaborators, account: str) -> list[str]:
    errs = collaborator_problems(collaborators, account)
    if errs:
        raise ValueError("; ".join(errs))
    return list(dict.fromkeys(str(c).strip().lstrip("@").lower() for c in collaborators or []))


MAX_TAGS = 3


def clean_tags(tags, account: str) -> list[str]:
    """Official accounts to tag: Instagram usernames, not one of idly's own, at most MAX_TAGS."""
    out = []
    for t in tags or []:
        name = str(t).strip().lstrip("@").lower()
        if not name or name in out or name in {a["username"] for a in ACCOUNTS.values()}:
            continue
        if not all(c.isalnum() or c in "._" for c in name) or len(name) > 30:
            raise ValueError(f"tag {t!r} is not an Instagram username")
        out.append(name)
    return out[:MAX_TAGS]


def user_tags(tags: list[str]) -> list[dict]:
    """Tag positions on the cover: along the upper middle of the photo, clear of the logo and the headline."""
    xs = {1: [0.5], 2: [0.35, 0.65], 3: [0.25, 0.5, 0.75]}[len(tags)]
    return [{"username": u, "x": x, "y": 0.3} for u, x in zip(tags, xs)]


def gate(score: dict | None, force_below_gate: bool) -> bool:
    """Raise unless the score passes the 12/14 gate. Returns True when a manual force was used."""
    if editorial.passes_gate(score):
        return False
    msg = editorial.gate_message(score)
    if not force_below_gate:
        raise GateRefused(f"refused: {msg}; nothing below {editorial.GATE}/{editorial.SCORE_MAX} is published")
    banner = "!" * 72
    log(f"\n{banner}\n!! MANUAL OVERRIDE --force-below-gate: publishing with {msg}\n"
        f"!! This is logged in state/posted.json as forced_below_gate=true\n{banner}\n")
    return True


# ---- publish -----------------------------------------------------------------------

def publish_post(account: str, media: list[str], caption: str, *, score: dict | None, story_id: int | None,
                 date: str | None = None, slot: str | None = None, alt_text: str = "",
                 collaborators: list[str] | None = None, dry_run: bool = False,
                 force_below_gate: bool = False, idly_article: bool = True,
                 record_extra: dict | None = None, tags: list[str] | None = None) -> dict:
    """Publish one image, or a 2-10 item carousel (images and/or .mp4/.mov videos).
    record_extra: extra fields for this post's state/posted.json entry (never overrides the core ones).
    tags: up to 3 official Instagram accounts (the brand, studio or label whose image this is) tagged on the
    cover image. A tag Instagram rejects never blocks the post: it is retried without tags.
    Returns {status, media_id, permalink, ...}."""
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    if not 1 <= len(media) <= MAX_ITEMS:
        raise ValueError(f"need 1 image, or 2-{MAX_ITEMS} items for a carousel")
    collaborators = clean_collaborators(collaborators, account)
    tags = clean_tags(tags, account)
    errs, warns = editorial.post_problems(caption, score, idly_article=idly_article)
    if errs:
        raise GateRefused("refused: caption problems: " + "; ".join(errs))
    for w in warns:
        log(f"  warning: {w}")
    forced = gate(score, force_below_gate)
    items = [resolve_media(m) for m in media]
    if len(items) == 1 and items[0][0] == "video":
        raise ValueError("a single video would be a Reel: feed posts are one image, videos go in carousels")
    urls = [url for _, url in items]
    date, slot = date or default_date(), slot or default_slot()

    if dry_run:
        print_plan(account, items, caption, alt_text, score, collaborators)
        return {"status": "dry-run", "account": account, "story_id": story_id, "images": urls}

    client, ig_id = connect(account)      # own token (IG_TOKEN_<ACCOUNT>) if set, else the shared one
    username = ACCOUNTS[account]["username"]
    used, total = client.quota(ig_id)
    if used >= min(LOCAL_DAILY_CAP, total):
        raise IGError(f"@{username} has published {used} posts in 24h (cap {min(LOCAL_DAILY_CAP, total)})")
    log(f"  @{username}: quota {used}/{min(LOCAL_DAILY_CAP, total)} used in the last 24h")

    extra = {"collaborators": json.dumps(collaborators)} if collaborators else {}
    tag_field = {"user_tags": json.dumps(user_tags(tags))} if tags else {}

    def with_tags(**fields):
        """Create a container carrying the tags; if Instagram rejects them, without (never blocks the post)."""
        if not tag_field:
            return client.create_container(ig_id, **fields)
        try:
            return client.create_container(ig_id, **fields, **tag_field)
        except IGError as e:
            log(f"  warning: tags {tags} rejected ({e}); posting without tags")
            tag_field.clear()
            return client.create_container(ig_id, **fields)

    if len(items) == 1:
        fields = {"image_url": urls[0], "caption": caption, **extra}
        if alt_text:
            fields["alt_text"] = alt_text
        container = with_tags(**fields)
    else:
        children = []
        for i, (kind, url) in enumerate(items):
            if kind == "video":
                children.append(client.create_container(ig_id, media_type="VIDEO", video_url=url,
                                                        is_carousel_item="true"))
            elif i == 0:
                children.append(with_tags(image_url=url, is_carousel_item="true"))
            else:
                children.append(client.create_container(ig_id, image_url=url, is_carousel_item="true"))
        for child in children:            # videos take a while: poll every child until FINISHED
            client.wait_finished(child)
        container = client.create_container(ig_id, media_type="CAROUSEL", children=",".join(children),
                                            caption=caption, **extra)
    log(f"  container {container} created; waiting for FINISHED")
    client.wait_finished(container)
    media_id = client.publish(ig_id, container, caption)
    permalink = client.permalink(media_id)
    entry = {
        "story_id": story_id, "account": account, "media_id": media_id, "permalink": permalink,
        "posted_at": now_utc().isoformat(timespec="seconds"), "date": date, "slot": slot,
        "images": urls, "score_total": editorial.score_total(score),
    }
    if forced:
        entry["forced_below_gate"] = True
    if tag_field:
        entry["tagged"] = tags
    entry = {**(record_extra or {}), **entry}
    append_posted(entry)
    log(f"  published @{username}: {permalink}")
    return {"status": "posted", **entry}


def print_plan(account: str, items: list[tuple[str, str]], caption: str, alt_text: str, score: dict | None,
               collaborators: list[str]) -> None:
    """The would-be API calls. Makes no network calls."""
    cached = load_accounts().get(account, {})
    own = account_token(account) is not None
    host = (cached.get("host") or IG_HOST) if own else FB_HOST
    base = f"{base_url(host)}/{API_VERSION}"
    ig = cached.get("id")
    where = "cached in state/accounts.json" if ig else "found at publish time"
    ig = ig or "<ig-user-id>"
    collab = f", collaborators={json.dumps(collaborators)}" if collaborators else ""
    print(f"[dry-run] @{account}  score {editorial.score_total(score)}/{editorial.SCORE_MAX}  "
          f"access: {describe_account_auth(account, cached.get('host'))}")
    if own and host == IG_HOST:
        print(f"  GET  {base}/me?fields=user_id,username        -> must be @{ACCOUNTS[account]['username']}")
    else:
        print(f"  GET  {base}/{ig}?fields=id,username        -> must be @{ACCOUNTS[account]['username']} "
              f"(id {where})")
    print(f"  GET  {base}/{ig}/content_publishing_limit?fields=quota_usage,config"
          f"  -> stop if used >= {LOCAL_DAILY_CAP}")
    if len(items) == 1:
        alt = f", alt_text=<{len(alt_text)} chars>" if alt_text else ""
        print(f"  POST {base}/{ig}/media  image_url={items[0][1]}, caption=<{len(caption)} chars>{alt}{collab}")
    else:
        for kind, u in items:
            what = f"media_type=VIDEO, video_url={u}" if kind == "video" else f"image_url={u}"
            print(f"  POST {base}/{ig}/media  {what}, is_carousel_item=true")
        print(f"  GET  {base}/<child-id>?fields=status_code,status   (each child, until FINISHED)")
        print(f"  POST {base}/{ig}/media  media_type=CAROUSEL, children=<{len(items)} ids>, "
              f"caption=<{len(caption)} chars>{collab}")
    print(f"  GET  {base}/<container-id>?fields=status_code,status   (poll until FINISHED, max ~5 min)")
    print(f"  POST {base}/{ig}/media_publish  creation_id=<container-id>")
    print(f"  GET  {base}/<media-id>?fields=permalink   -> append to state/posted.json")


# ---- check: every account's token, id, host, publishing limit, expiry ---------------------

def check_accounts(online: bool = True, expiry: bool = True) -> dict:
    """For each account: its own token (IG_TOKEN_<ACCOUNT>: host auto-detected) or the shared one
    (network secret / IG_SYSTEM_TOKEN: discovery on graph.facebook.com); right account? publishing limit;
    for graph.instagram.com tokens, days until the token expires. No token needs to be in the environment."""
    cache = load_accounts()
    own = {a: account_token(a) for a in ACCOUNTS}
    shared = [a for a in ACCOUNTS if not own[a]]
    report = {"api_version": API_VERSION, "business_id": BUSINESS_ID, "online": online,
              "shared_auth": auth_mode(), "shared_accounts": shared, "discovery": None, "auth_error": None,
              "accounts": [], "ok": False}
    ids = {k: v["id"] for k, v in cache.items() if v.get("id")}
    shared_client = None
    if online and shared:
        shared_client = IGClient()
        disc = discover(shared_client, stop_when_complete=False)
        report["discovery"] = {"attempts": disc["attempts"], "via": disc["via"]}
        report["auth_error"] = disc["auth_error"]
        if disc["found"]:
            update_accounts(disc["found"], disc["via"])
        ids.update({k: v["id"] for k, v in disc["found"].items()})
    for account in ACCOUNTS:
        st = {"account": account, "mode": "own token" if own[account] else "shared",
              "ig_id": ids.get(account), "host": cache.get(account, {}).get("host") if own[account] else FB_HOST,
              "warnings": [], "notes": []}
        report["accounts"].append(st)
        if own[account]:
            st["env"] = token_env(account)
            if not online:
                continue
            try:
                client, st["ig_id"] = connect_with_token(account, own[account])
                st["host"], st["reachable"] = client.host, True
            except IGError as e:
                st["reachable"] = False
                st["warnings"].append(f"token problem: {e}")
                continue
        else:
            if not online:
                if not st["ig_id"]:
                    st["warnings"].append("no cached id in state/accounts.json")
                continue
            if report["auth_error"]:
                st["reachable"] = False
                st["warnings"].append(f"no access: set {token_env(account)}, or add the shared network secret")
                continue
            if not st["ig_id"]:
                st["warnings"].append("not found by discovery")
                continue
            client = shared_client
            try:
                verify_account(client, account, st["ig_id"])
                st["reachable"] = True
            except IGError as e:
                st["reachable"] = False
                st["warnings"].append(f"not reachable: {e}")
                continue
        try:
            st["quota_used"], st["quota_total"] = client.quota(st["ig_id"])
            if st["quota_used"] >= min(LOCAL_DAILY_CAP, st["quota_total"]):
                st["warnings"].append(f"publishing limit reached ({st['quota_used']}/"
                                      f"{min(LOCAL_DAILY_CAP, st['quota_total'])} in 24h)")
        except IGError as e:
            st["warnings"].append(f"publishing limit unavailable: {e}")
        if own[account] and expiry and client.host == IG_HOST:
            try:
                days, note = client.token_expiry()
            except IGError as e:
                days, note = None, f"expiry unknown: {e.message}"
            if days is None:
                st["notes"].append(note)
            else:
                st["days_left"] = days
                if days <= EXPIRY_WARN_DAYS:
                    st["warnings"].append(f"token expires in {days} days: generate a new one in the Meta "
                                          f"dashboard and update {token_env(account)}")
    report["ok"] = online and all(st.get("reachable") and not st["warnings"] for st in report["accounts"])
    return report


def format_check(report: dict) -> list[str]:
    lines = [f"Graph API {report.get('api_version', API_VERSION)}"]
    if report.get("shared_accounts"):
        lines.append(f"Shared token (for {', '.join('@' + a for a in report['shared_accounts'])}): "
                     f"{describe_auth(report.get('shared_auth'))}")
    if report.get("discovery"):
        lines.append("Discovery (shared token):")
        for a in report["discovery"]["attempts"]:
            if not a["ok"]:
                result = f"failed: {a['error']}"
            elif "matched" in a:
                result = f"ok, {a['rows']} rows, {a['matched']} of our accounts"
            else:
                result = f"ok ({a.get('name')}, id {a.get('id')})"
            lines.append(f"  {a['lookup']}: {result}")
    elif not report["online"]:
        lines.append("Offline: no API calls; showing state/accounts.json")
    if report.get("auth_error"):
        lines.append(f"ACCESS PROBLEM (shared token): {AUTH_HINT}")
    for st in report["accounts"]:
        if st.get("mode") == "own token":
            how = f"{st['env']} on {st.get('host') or 'host not detected yet'}"
        else:
            how = f"shared token on {FB_HOST}"
        if st["warnings"]:
            status = "; ".join(st["warnings"])
        elif report.get("online"):
            expires = f", token expires in {st['days_left']} days" if "days_left" in st else ""
            status = (f"ok (id {st['ig_id']}, {st.get('quota_used')}/"
                      f"{min(LOCAL_DAILY_CAP, st.get('quota_total') or LOCAL_DAILY_CAP)} posts in 24h{expires})")
        else:
            status = f"cached id {st.get('ig_id') or '-'} (not checked)"
        notes = f" [{'; '.join(st['notes'])}]" if st.get("notes") else ""
        lines.append(f"@{st['account']} ({how}): {status}{notes}")
    return lines


# ---- CLI --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("post", help="publish one image or a carousel")
    p.add_argument("--account", required=True, choices=list(ACCOUNTS))
    p.add_argument("--image", "--video", dest="media", action="append", required=True,
                   help="repeat for a carousel (2-10 items, in order); .mp4/.mov are carousel videos")
    p.add_argument("--caption-file", required=True, type=Path)
    p.add_argument("--score-file", required=True, type=Path,
                   help="JSON with hook, read, send, keep, reply, original, alone, total, notes")
    p.add_argument("--story-id", type=int)
    p.add_argument("--alt-text", default="")
    p.add_argument("--collaborator", action="append", default=[],
                   help="optional; repeat for up to 3 Instagram usernames (default: none)")
    p.add_argument("--tag", action="append", default=[],
                   help="optional; repeat for up to 3 official accounts whose image this is (brand, studio, label)")
    p.add_argument("--date")
    p.add_argument("--slot", choices=["am", "pm"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-idly-article", action="store_true",
                   help="the post has no idly.news article: caption must list Sources and not point to idly.news")
    p.add_argument("--force-below-gate", action="store_true",
                   help="MANUAL USE ONLY: publish a post scoring under 12/14 (loud, logged)")
    c = sub.add_parser("check", help="every account: token, id, host, publishing limit, token expiry")
    c.add_argument("--offline", action="store_true", help="don't call the API; show the cached ids")
    c.add_argument("--no-refresh", action="store_true",
                   help="skip the expiry check (GET graph.instagram.com/refresh_access_token)")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "post":
            result = publish_post(
                args.account, args.media, args.caption_file.read_text(encoding="utf-8").strip(),
                score=json.loads(args.score_file.read_text(encoding="utf-8")), story_id=args.story_id,
                date=args.date, slot=args.slot, alt_text=args.alt_text, collaborators=args.collaborator,
                dry_run=args.dry_run, force_below_gate=args.force_below_gate,
                idly_article=not args.no_idly_article, tags=args.tag)
            print(json.dumps(result, indent=2))
        elif args.cmd == "check":
            report = check_accounts(online=not args.offline, expiry=not args.no_refresh)
            print("\n".join(format_check(report)))
            return 0 if report["ok"] or args.offline else 1
    except GateRefused as e:
        log(str(e))
        return 2
    except (IGError, ValueError) as e:
        log(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
