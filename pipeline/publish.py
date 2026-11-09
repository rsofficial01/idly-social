"""Publish to Instagram with the official "Instagram API with Instagram Login" (graph.instagram.com).

    # one image (repo-relative path -> public raw.githubusercontent.com URL, or a full https URL)
    python3 pipeline/publish.py post --account idlytech --image posts/2026-11-09/pm-idlytech-1691.jpg \
        --caption-file caption.txt --score-file score.json --story-id 1691 [--dry-run]
    # carousel: repeat --image (2-10)
    python3 pipeline/publish.py check [--account idlytech]     # tokens, usernames, quota, expiry
    python3 pipeline/publish.py refresh --account idlytech     # new 60-day token -> state/secrets/

Tokens come from IG_TOKEN_<ACCOUNT> and are sent only as "Authorization: Bearer"; they are never
printed, logged or put in a URL. Nothing is published unless the post's 7-check score is >= 12/14.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date as Date, timedelta
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial
from pipeline.common import (ACCOUNTS, REPO, SECRETS_DIR, append_posted, default_date, default_slot,
                             expiry_env, log, now_ist, now_utc, public_url, repo_path, token_env)

GRAPH = "https://graph.instagram.com"
API_VERSION = "v25.0"            # latest version shown in Meta's content-publishing docs (Nov 2026)
LOCAL_DAILY_CAP = 25             # our own cap; Meta's quota (config.quota_total) is also respected
EXPIRY_WARN_DAYS = 10
MAX_JPEG_BYTES = 8 * 1024 * 1024
POLL_WAITS = [3, 5, 10, 20, 30, 60, 60, 60, 60]   # ~5 minutes in total, per Meta's guidance
# Meta error codes worth retrying: temporary, throttling, "media not ready", "could not fetch media"
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613, 9004, 9007}


class MissingToken(Exception):
    pass


class GateRefused(Exception):
    pass


class IGError(Exception):
    def __init__(self, message: str, code=None, transient=False):
        super().__init__(message)
        self.code, self.transient = code, transient


def get_token(account: str) -> str:
    token = os.environ.get(token_env(account), "").strip()
    if not token:
        raise MissingToken(f"{token_env(account)} is not set")
    return token


class IGClient:
    """Tiny Graph API client. The token lives only in the session's Authorization header."""

    def __init__(self, token: str):
        self._token = token
        self._s = requests.Session()
        self._s.headers.update({"Authorization": f"Bearer {token}", "User-Agent": "idly-social/1.0"})

    def _clean(self, text: str) -> str:
        return str(text).replace(self._token, "***")

    def call(self, method: str, path: str, params=None, data=None, attempts: int = 4, versioned=True) -> dict:
        url = f"{GRAPH}/{API_VERSION}/{path}" if versioned else f"{GRAPH}/{path}"
        for attempt in range(1, attempts + 1):
            try:
                r = self._s.request(method, url, params=params, data=data, timeout=60)
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                if r.ok and "error" not in body:
                    return body
                e = body.get("error") or {}
                code = e.get("code")
                err = IGError(self._clean(f"{method} /{path} -> HTTP {r.status_code}, code {code}"
                                          f"/{e.get('error_subcode')}: {e.get('message') or r.reason}"),
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
    def me(self) -> dict:
        return self.call("GET", "me", params={"fields": "user_id,username"})

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

    def refresh(self) -> dict:
        return self.call("GET", "refresh_access_token", params={"grant_type": "ig_refresh_token"},
                         versioned=False, attempts=2)


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


def resolve_image(image: str) -> str:
    """Check a local JPEG under posts/ and return its public URL; https URLs pass through unchanged."""
    if image.startswith("https://"):
        return image
    if image.startswith("http://"):
        raise ValueError("image URLs must be https")
    path = repo_path(image)
    check_jpeg(path)
    rel = path.resolve().relative_to(REPO).as_posix()
    if not rel.startswith("posts/"):
        raise ValueError(f"{image} must live under posts/ so it is committed and public")
    return public_url(rel)


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

def publish_post(account: str, images: list[str], caption: str, *, score: dict | None, story_id: int | None,
                 date: str | None = None, slot: str | None = None, alt_text: str = "",
                 dry_run: bool = False, force_below_gate: bool = False) -> dict:
    """Publish one image (or a 2-10 image carousel). Returns {status, media_id, permalink, ...}."""
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    if not 1 <= len(images) <= 10:
        raise ValueError("need 1 image, or 2-10 for a carousel")
    errs, warns = editorial.post_problems(caption, score)
    if errs:
        raise GateRefused("refused: caption problems: " + "; ".join(errs))
    for w in warns:
        log(f"  warning: {w}")
    forced = gate(score, force_below_gate)
    urls = [resolve_image(i) for i in images]
    date, slot = date or default_date(), slot or default_slot()

    if dry_run:
        print_plan(account, urls, caption, alt_text, score)
        return {"status": "dry-run", "account": account, "story_id": story_id, "images": urls}

    client = IGClient(get_token(account))
    me = client.me()
    ig_id, username = me.get("user_id"), me.get("username")
    expected = ACCOUNTS[account]["username"]
    if not ig_id or (username or "").lower() != expected:
        raise IGError(f"{token_env(account)} belongs to @{username}, expected @{expected}: not posting")
    used, total = client.quota(ig_id)
    if used >= min(LOCAL_DAILY_CAP, total):
        raise IGError(f"@{username} has published {used} posts in 24h (cap {min(LOCAL_DAILY_CAP, total)})")
    log(f"  @{username}: quota {used}/{min(LOCAL_DAILY_CAP, total)} used in the last 24h")

    if len(urls) == 1:
        fields = {"image_url": urls[0], "caption": caption}
        if alt_text:
            fields["alt_text"] = alt_text
        container = client.create_container(ig_id, **fields)
    else:
        children = []
        for url in urls:
            child = client.create_container(ig_id, image_url=url, is_carousel_item="true")
            client.wait_finished(child)
            children.append(child)
        container = client.create_container(ig_id, media_type="CAROUSEL", children=",".join(children),
                                            caption=caption)
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


def print_plan(account: str, urls: list[str], caption: str, alt_text: str, score: dict | None) -> None:
    env = token_env(account)
    state = "set" if os.environ.get(env) else "NOT SET"
    base = f"{GRAPH}/{API_VERSION}"
    print(f"[dry-run] @{account}  score {editorial.score_total(score)}/{editorial.SCORE_MAX}  "
          f"token {env}: {state} (sent as Authorization: Bearer header, never printed)")
    print(f"  GET  {base}/me?fields=user_id,username        -> must be @{ACCOUNTS[account]['username']}")
    print(f"  GET  {base}/<ig-user-id>/content_publishing_limit?fields=quota_usage,config"
          f"  -> stop if used >= {LOCAL_DAILY_CAP}")
    if len(urls) == 1:
        extra = f", alt_text=<{len(alt_text)} chars>" if alt_text else ""
        print(f"  POST {base}/<ig-user-id>/media  image_url={urls[0]}, caption=<{len(caption)} chars>{extra}")
    else:
        for u in urls:
            print(f"  POST {base}/<ig-user-id>/media  image_url={u}, is_carousel_item=true  (+ poll status)")
        print(f"  POST {base}/<ig-user-id>/media  media_type=CAROUSEL, children=<{len(urls)} ids>, "
              f"caption=<{len(caption)} chars>")
    print(f"  GET  {base}/<container-id>?fields=status_code,status   (poll until FINISHED, max ~5 min)")
    print(f"  POST {base}/<ig-user-id>/media_publish  creation_id=<container-id>")
    print(f"  GET  {base}/<media-id>?fields=permalink   -> append to state/posted.json")


# ---- token check / refresh ------------------------------------------------------------

def token_status(account: str, online: bool = True) -> dict:
    """Is the token set and valid, does it belong to the right account, quota, days to expiry."""
    st = {"account": account, "env": token_env(account), "set": bool(os.environ.get(token_env(account)))}
    exp = os.environ.get(expiry_env(account), "").strip()
    if exp:
        try:
            st["expires_on"] = exp
            st["days_left"] = (Date.fromisoformat(exp) - now_ist().date()).days
        except ValueError:
            st["expiry_note"] = f"{expiry_env(account)} is not YYYY-MM-DD"
    if st["set"] and online:
        try:
            client = IGClient(get_token(account))
            me = client.me()
            st["username"] = me.get("username")
            st["valid"] = (me.get("username") or "").lower() == ACCOUNTS[account]["username"]
            if st["valid"]:
                st["quota_used"], st["quota_total"] = client.quota(me["user_id"])
            else:
                st["error"] = f"token belongs to @{me.get('username')}"
        except IGError as e:
            st["valid"], st["error"] = False, str(e)
    warn = []
    if not st["set"]:
        warn.append(f"{st['env']} not set")
    elif st.get("valid") is False:
        warn.append(f"token problem: {st.get('error')}")
    if "days_left" in st and st["days_left"] <= EXPIRY_WARN_DAYS:
        warn.append(f"token expires in {st['days_left']} days ({st['expires_on']}): refresh it")
    if st["set"] and "days_left" not in st:
        warn.append(f"expiry unknown: set {expiry_env(account)}=YYYY-MM-DD")
    st["warnings"] = warn
    return st


def refresh_token(account: str) -> None:
    """Get a fresh 60-day token. It is written to state/secrets/ (gitignored), never printed."""
    data = IGClient(get_token(account)).refresh()
    new, expires_in = data.get("access_token"), int(data.get("expires_in", 0))
    if not new:
        raise IGError("refresh returned no token")
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    path = SECRETS_DIR / token_env(account)
    path.write_text(new + "\n", encoding="utf-8")
    path.chmod(0o600)
    expires_on = (now_ist() + timedelta(seconds=expires_in)).date().isoformat()
    print(f"Refreshed @{account}: new token saved to {path.relative_to(REPO)} (not printed).")
    print(f"Update the environment: {token_env(account)}=<contents of that file>, "
          f"{expiry_env(account)}={expires_on}. Then delete the file.")


# ---- CLI --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("post", help="publish one image or a carousel")
    p.add_argument("--account", required=True, choices=list(ACCOUNTS))
    p.add_argument("--image", action="append", required=True, help="repeat for a carousel (2-10)")
    p.add_argument("--caption-file", required=True, type=Path)
    p.add_argument("--score-file", required=True, type=Path,
                   help="JSON with hook, read, send, keep, reply, original, alone, total, notes")
    p.add_argument("--story-id", type=int)
    p.add_argument("--alt-text", default="")
    p.add_argument("--date")
    p.add_argument("--slot", choices=["am", "pm"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force-below-gate", action="store_true",
                   help="MANUAL USE ONLY: publish a post scoring under 12/14 (loud, logged)")
    c = sub.add_parser("check", help="check tokens, usernames, quota and expiry")
    c.add_argument("--account", choices=list(ACCOUNTS))
    c.add_argument("--offline", action="store_true", help="don't call the API")
    r = sub.add_parser("refresh", help="refresh a long-lived token (60 days)")
    r.add_argument("--account", required=True, choices=list(ACCOUNTS))
    args = ap.parse_args(argv)

    try:
        if args.cmd == "post":
            result = publish_post(
                args.account, args.image, args.caption_file.read_text(encoding="utf-8").strip(),
                score=json.loads(args.score_file.read_text(encoding="utf-8")), story_id=args.story_id,
                date=args.date, slot=args.slot, alt_text=args.alt_text, dry_run=args.dry_run,
                force_below_gate=args.force_below_gate)
            print(json.dumps(result, indent=2))
        elif args.cmd == "check":
            for account in [args.account] if args.account else ACCOUNTS:
                st = token_status(account, online=not args.offline)
                print(f"@{account}: " + ("; ".join(st["warnings"]) or
                                         f"ok (@{st.get('username')}, quota {st.get('quota_used')}/"
                                         f"{st.get('quota_total')}, expires {st.get('expires_on')})"))
        elif args.cmd == "refresh":
            refresh_token(args.account)
    except GateRefused as e:
        log(str(e))
        return 2
    except MissingToken as e:
        log(f"skipped: {e}")
        return 3
    except (IGError, ValueError) as e:
        log(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
