"""Shared constants and small helpers for the idly Instagram pipeline."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / "state"
POSTED_FILE = STATE_DIR / "posted.json"
ACCOUNTS_FILE = STATE_DIR / "accounts.json"  # committed: account ids, usernames and API hosts; no tokens
POSTS_DIR = REPO / "posts"                   # committed; served publicly via raw.githubusercontent.com
REPORTS_DIR = REPO / "reports"
WORK_DIR = REPO / "_work"                    # gitignored scratch space, one folder per run

IDLY_API = "https://api.idly.news/api/v1"
IMAGE_BASE = os.environ.get(
    "IDLY_IMAGE_BASE", "https://raw.githubusercontent.com/rsofficial01/idly-social/main")

IST = timezone(timedelta(hours=5, minutes=30), "IST")

# Meta access, per account (first match wins):
# 1. IG_TOKEN_<ACCOUNT>: that account's own token from the Meta dashboard ("Generate token"), an
#    environment variable. Its host (graph.instagram.com or graph.facebook.com) is auto-detected.
# 2. Shared: ONE system-user access token for all accounts, on graph.facebook.com. In the Claude cloud it
#    is a network secret (the agent proxy adds the Authorization header, so this process never has it);
#    elsewhere IG_SYSTEM_TOKEN.
TOKEN_ENV = "IG_SYSTEM_TOKEN"
META_APP_ID = "1533702778969280"             # "idly publisher" (not secret)
BUSINESS_ID = os.environ.get("IG_BUSINESS_ID", "1165348135833967")   # business portfolio (not secret)

# Instagram account -> idly category and the Instagram username it must resolve to.
ACCOUNTS: dict[str, dict] = {
    "idlynews":       {"category": "news",       "username": "idlynews"},
    "idlytech":       {"category": "tech",       "username": "idlytech"},
    "idlyhype":       {"category": "hype",       "username": "idlyhype"},
    "idlyautomotive": {"category": "automotive", "username": "idlyautomotive"},
    "idlynerd":       {"category": "nerd",       "username": "idlynerd"},
}
CATEGORY_TO_ACCOUNT = {v["category"]: k for k, v in ACCOUNTS.items()}  # sports: no account yet


def token_env(account: str) -> str:
    """The environment variable holding this account's own token (optional)."""
    return f"IG_TOKEN_{account.upper()}"


# ---- time -----------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_ist() -> datetime:
    return now_utc().astimezone(IST)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def default_slot(t: datetime | None = None) -> str:
    """'am' for the ~8:40 IST run, 'pm' for the ~18:40 IST run."""
    return "am" if (t or now_ist()).hour < 14 else "pm"


def default_date() -> str:
    return now_ist().date().isoformat()


# ---- files ----------------------------------------------------------------

def work_dir(date: str, slot: str) -> Path:
    path = WORK_DIR / f"{date}-{slot}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: Path, data) -> None:
    """Write atomically so a crash never leaves half a state file behind."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def repo_path(path: str | Path) -> Path:
    """Resolve a path given relative to the repo root (as used in cards JSON)."""
    p = Path(path)
    return p if p.is_absolute() else REPO / p


def public_url(rel_path: str) -> str:
    """Public URL of a committed file, e.g. posts/2026-11-09/pm-idlytech-1691.jpg."""
    return f"{IMAGE_BASE}/{rel_path.lstrip('/')}"


# ---- posted state -----------------------------------------------------------

def load_posted() -> list[dict]:
    return load_json(POSTED_FILE, default=[]) or []


def posted_story_ids(account: str | None = None) -> set[int]:
    return {p["story_id"] for p in load_posted() if account in (None, p.get("account"))}


def slot_already_posted(account: str, date: str, slot: str) -> dict | None:
    for p in load_posted():
        if (p.get("account"), p.get("date"), p.get("slot")) == (account, date, slot):
            return p
    return None


def append_posted(entry: dict) -> None:
    posted = load_posted()
    posted.append(entry)
    save_json(POSTED_FILE, posted)


# ---- Instagram accounts (state/accounts.json) -------------------------------------

ACCOUNT_FIELDS = ("id", "username", "host")      # the only fields ever written: never a token


def load_accounts() -> dict[str, dict]:
    """Cached {account: {"id", "username", "host"?}}. "host" is where that account's own token works."""
    doc = load_json(ACCOUNTS_FILE, default={}) or {}
    return {k: {f: str(v[f]) for f in ACCOUNT_FIELDS if v.get(f)}
            for k, v in (doc.get("accounts") or {}).items() if k in ACCOUNTS and isinstance(v, dict)}


def load_account_ids() -> dict[str, str]:
    return {k: v["id"] for k, v in load_accounts().items() if v.get("id")}


def update_accounts(updates: dict[str, dict], via: list[str] | None = None) -> None:
    """Merge {account: {"id"?, "username"?, "host"?}} into state/accounts.json (commit-safe on purpose).
    Accounts and fields not in `updates` keep their old values (publishing re-checks every id)."""
    doc = load_json(ACCOUNTS_FILE, default={}) or {}
    accounts = load_accounts()
    for k, v in updates.items():
        entry = accounts.setdefault(k, {})
        entry.update({f: str(v[f]) for f in ACCOUNT_FIELDS if v.get(f)})
        entry.setdefault("username", ACCOUNTS[k]["username"])
    save_json(ACCOUNTS_FILE, {"updated_at": now_utc().isoformat(timespec="seconds"),
                              "via": doc.get("via", []) if via is None else via,
                              "accounts": dict(sorted(accounts.items()))})


# ---- logging ----------------------------------------------------------------

def log(*parts) -> None:
    """Progress messages go to stderr; stdout is kept for results."""
    print(*parts, file=sys.stderr, flush=True)
