"""Publish to Instagram with the official "Instagram API with Facebook Login" (graph.facebook.com).

    # one image (repo-relative path -> public raw.githubusercontent.com URL, or a full https URL)
    python3 pipeline/publish.py post --account idlytech --image posts/2026-11-09/pm-idlytech-1691.jpg \
        --caption-file caption.txt --score-file score.json --story-id 1691 [--collaborator idlynews] [--dry-run]
    # carousel: repeat --image / --video (2-10 items, in order). .mp4/.mov items are carousel videos.
    python3 pipeline/publish.py check [--offline]   # find the 5 account ids, check each one, publishing limit

Access: ONE Meta system-user access token (Facebook Login for Business) covers all five accounts.
- In the Claude cloud environment it is a network secret: the agent proxy adds "Authorization: Bearer ..."
  to every request for graph.facebook.com. This code then sends no credentials at all and never sees them.
- Anywhere else, set IG_SYSTEM_TOKEN. It is sent only as the Authorization: Bearer header; it is never
  put in a URL or a request body, and never printed or logged.
Nothing is published unless the post's 7-check score is >= 12/14.
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
                             default_slot, load_account_ids, log, now_utc, public_url, repo_path,
                             save_account_ids)

GRAPH = "https://graph.facebook.com"
API_VERSION = "v27.0"            # latest Graph API version in Meta's docs (v27.0, released 4 Nov 2026)
LOCAL_DAILY_CAP = 25             # our own cap; Meta's quota (config.quota_total) is also respected
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

AUTH_HINT = ("Meta got no valid access token. In the Claude cloud environment, add the network secret for "
             "graph.facebook.com (RUNBOOK.md, 'Meta access'); elsewhere set IG_SYSTEM_TOKEN")
PERMISSION_HINT = ("check the Facebook Login for Business configuration's permissions and that the Instagram "
                   "accounts are assets of the system user (RUNBOOK.md, 'Meta access')")


class GateRefused(Exception):
    pass


class IGError(Exception):
    def __init__(self, message: str, code=None, transient=False):
        super().__init__(message)
        self.code, self.transient = code, transient


def auth_mode() -> str:
    """'env' when IG_SYSTEM_TOKEN is set, else 'network-secret' (the agent proxy adds the header)."""
    return "env" if os.environ.get(TOKEN_ENV, "").strip() else "network-secret"


def describe_auth(mode: str | None = None) -> str:
    if (mode or auth_mode()) == "env":
        return f"{TOKEN_ENV} is set: sent only as the Authorization: Bearer header (never printed)"
    return (f"{TOKEN_ENV} not set: no credentials sent; the network secret for graph.facebook.com "
            f"adds the Authorization header at the agent proxy")


class IGClient:
    """Tiny Graph API client. Credentials, if any, live only in the session's Authorization header."""

    def __init__(self, token: str | None = None):
        token = os.environ.get(TOKEN_ENV, "") if token is None else token
        self._token = token.strip() or None
        self._s = requests.Session()
        self._s.headers["User-Agent"] = "idly-social/2.0"
        if self._token:
            self._s.headers["Authorization"] = f"Bearer {self._token}"

    def _clean(self, text: str) -> str:
        text = str(text)
        return text.replace(self._token, "***") if self._token else text

    def call(self, method: str, path: str, params=None, data=None, attempts: int = 4) -> dict:
        url = f"{GRAPH}/{API_VERSION}/{path}"
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
                hint = (f" [{AUTH_HINT}]" if code in AUTH_CODES else
                        f" [{PERMISSION_HINT}]" if code in PERMISSION_CODES else "")
                err = IGError(self._clean(f"{method} /{path} -> HTTP {r.status_code}, code {code}"
                                          f"/{e.get('error_subcode')}: {e.get('message') or r.reason}{hint}"),
                              code=code,
                              transient=bool(e.get("is_transient")) or code in TRANSIENT_CODES
                              or r.status_code == 429 or r.status_code >= 500)
            except requests.RequestException as ex:
                err = IGError(self._clean(f"{method} /{path} -> network error: {type(ex).__name__}"),
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

def discover(client: IGClient, business_id: str = BUSINESS_ID, stop_when_complete: bool = True) -> dict:
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
        return stop_when_complete and len(out["found"]) == len(ACCOUNTS)

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
    """Cached id (state/accounts.json) -> verified; on a miss or a mismatch, run discovery once."""
    cached = load_account_ids().get(account)
    if cached:
        try:
            verify_account(client, account, cached)
            return cached
        except IGError as e:
            if e.code in AUTH_CODES or e.transient:
                raise
            log(f"  cached id for @{account} didn't check out ({e}); running discovery")
    disc = discover(client)
    if disc["auth_error"]:
        raise IGError(disc["auth_error"], code=190)
    if disc["found"]:
        save_account_ids(disc["found"], disc["via"])
    hit = disc["found"].get(account)
    if not hit:
        raise IGError(f"@{ACCOUNTS[account]['username']} not found by discovery "
                      f"({summarize_attempts(disc['attempts'])}); run `publish.py check`")
    verify_account(client, account, hit["id"])
    return hit["id"]


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
                 force_below_gate: bool = False) -> dict:
    """Publish one image, or a 2-10 item carousel (images and/or .mp4/.mov videos).
    Returns {status, media_id, permalink, ...}."""
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    if not 1 <= len(media) <= MAX_ITEMS:
        raise ValueError(f"need 1 image, or 2-{MAX_ITEMS} items for a carousel")
    collaborators = clean_collaborators(collaborators, account)
    errs, warns = editorial.post_problems(caption, score)
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

    client = IGClient()
    ig_id = resolve_account(client, account)
    username = ACCOUNTS[account]["username"]
    used, total = client.quota(ig_id)
    if used >= min(LOCAL_DAILY_CAP, total):
        raise IGError(f"@{username} has published {used} posts in 24h (cap {min(LOCAL_DAILY_CAP, total)})")
    log(f"  @{username}: quota {used}/{min(LOCAL_DAILY_CAP, total)} used in the last 24h")

    extra = {"collaborators": json.dumps(collaborators)} if collaborators else {}
    if len(items) == 1:
        fields = {"image_url": urls[0], "caption": caption, **extra}
        if alt_text:
            fields["alt_text"] = alt_text
        container = client.create_container(ig_id, **fields)
    else:
        children = []
        for kind, url in items:
            if kind == "video":
                children.append(client.create_container(ig_id, media_type="VIDEO", video_url=url,
                                                        is_carousel_item="true"))
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
    append_posted(entry)
    log(f"  published @{username}: {permalink}")
    return {"status": "posted", **entry}


def print_plan(account: str, items: list[tuple[str, str]], caption: str, alt_text: str, score: dict | None,
               collaborators: list[str]) -> None:
    """The would-be API calls. Makes no network calls."""
    base = f"{GRAPH}/{API_VERSION}"
    ig = load_account_ids().get(account)
    where = "cached in state/accounts.json" if ig else "found by discovery at publish time"
    ig = ig or "<ig-user-id>"
    collab = f", collaborators={json.dumps(collaborators)}" if collaborators else ""
    print(f"[dry-run] @{account}  score {editorial.score_total(score)}/{editorial.SCORE_MAX}  "
          f"access: {describe_auth()}")
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


# ---- check: discovery, reachability, publishing limit ---------------------------------

def check_accounts(online: bool = True) -> dict:
    """Run discovery, then check each of the 5 accounts is reachable and read its publishing limit.
    Works with no token in the environment (the network secret supplies it)."""
    mode = auth_mode()
    report = {"auth": mode, "api": f"{GRAPH}/{API_VERSION}", "business_id": BUSINESS_ID, "online": online,
              "discovery": None, "auth_error": None, "accounts": [], "ok": False}
    ids = load_account_ids()
    client = IGClient() if online else None
    disc = None
    if online:
        disc = discover(client, stop_when_complete=False)
        report["discovery"] = {"attempts": disc["attempts"], "via": disc["via"]}
        report["auth_error"] = disc["auth_error"]
        if disc["found"]:
            save_account_ids(disc["found"], disc["via"])
        ids.update({k: v["id"] for k, v in disc["found"].items()})
    for account in ACCOUNTS:
        st = {"account": account, "ig_id": ids.get(account), "warnings": []}
        report["accounts"].append(st)
        if report["auth_error"]:
            st["reachable"] = False
            st["warnings"].append("no access: Meta got no valid access token")
            continue
        if not st["ig_id"]:
            st["warnings"].append("not found by discovery" if online else
                                  "no cached id in state/accounts.json (run check online)")
            continue
        if not online:
            continue
        try:
            verify_account(client, account, st["ig_id"])
            st["username"], st["reachable"] = ACCOUNTS[account]["username"], True
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
    report["ok"] = online and all(st.get("reachable") and not st["warnings"] for st in report["accounts"])
    return report


def format_check(report: dict) -> list[str]:
    lines = [f"Meta access: {describe_auth(report['auth'])}", f"API: {report['api']}"]
    if report.get("discovery"):
        lines.append("Discovery:")
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
        lines.append(f"ACCESS PROBLEM: {AUTH_HINT}")
    for st in report["accounts"]:
        if st["warnings"]:
            status = "; ".join(st["warnings"])
        elif report["online"]:
            status = (f"ok (id {st['ig_id']}, {st.get('quota_used')}/"
                      f"{min(LOCAL_DAILY_CAP, st.get('quota_total') or LOCAL_DAILY_CAP)} posts in 24h)")
        else:
            status = f"cached id {st['ig_id']} (not checked)"
        lines.append(f"@{st['account']}: {status}")
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
    p.add_argument("--date")
    p.add_argument("--slot", choices=["am", "pm"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-below-gate", action="store_true",
                   help="MANUAL USE ONLY: publish a post scoring under 12/14 (loud, logged)")
    c = sub.add_parser("check", help="find the 5 account ids, check each is reachable, report the publishing limit")
    c.add_argument("--offline", action="store_true", help="don't call the API; show the cached ids")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "post":
            result = publish_post(
                args.account, args.media, args.caption_file.read_text(encoding="utf-8").strip(),
                score=json.loads(args.score_file.read_text(encoding="utf-8")), story_id=args.story_id,
                date=args.date, slot=args.slot, alt_text=args.alt_text, collaborators=args.collaborator,
                dry_run=args.dry_run, force_below_gate=args.force_below_gate)
            print(json.dumps(result, indent=2))
        elif args.cmd == "check":
            report = check_accounts(online=not args.offline)
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
