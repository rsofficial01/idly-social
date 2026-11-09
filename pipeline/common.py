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
ACCOUNTS_FILE = STATE_DIR / "accounts.json"  # committed: username -> Instagram account id, nothing secret
POSTS_DIR = REPO / "posts"                   # committed; served publicly via raw.githubusercontent.com
REPORTS_DIR = REPO / "reports"
WORK_DIR = REPO / "_work"                    # gitignored scratch space, one folder per run

IDLY_API = "https://api.idly.news/api/v1"
IMAGE_BASE = os.environ.get(
    "IDLY_IMAGE_BASE", "https://raw.githubusercontent.com/rsofficial01/idly-social/main")

IST = timezone(timedelta(hours=5, minutes=30), "IST")

# Meta access: ONE system-user access token (Facebook Login for Business) covers all five accounts.
# In the Claude cloud environment it is a network secret: the agent proxy adds the Authorization header
# to requests for graph.facebook.com, so the token is never in this process. Elsewhere, IG_SYSTEM_TOKEN.
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


# ---- Instagram account ids (state/accounts.json) ------------------------------------

def load_account_ids() -> dict[str, str]:
    """Cached {account: Instagram professional account id}; empty until `publish.py check` discovers them."""
    doc = load_json(ACCOUNTS_FILE, default={}) or {}
    return {k: str(v["id"]) for k, v in (doc.get("accounts") or {}).items()
            if k in ACCOUNTS and isinstance(v, dict) and v.get("id")}


def save_account_ids(found: dict[str, dict], via: list[str]) -> None:
    """Commit-safe on purpose: only account ids, usernames, which lookup found them, and when.
    Accounts not found this time keep their old entry (publishing re-checks every id before use)."""
    old = (load_json(ACCOUNTS_FILE, default={}) or {}).get("accounts") or {}
    merged = {k: v for k, v in old.items() if k in ACCOUNTS}
    merged.update({k: {"id": str(v["id"]), "username": v["username"]} for k, v in found.items()})
    doc = {"updated_at": now_utc().isoformat(timespec="seconds"), "via": via,
           "accounts": dict(sorted(merged.items()))}
    save_json(ACCOUNTS_FILE, doc)


# ---- logging ----------------------------------------------------------------

def log(*parts) -> None:
    """Progress messages go to stderr; stdout is kept for results."""
    print(*parts, file=sys.stderr, flush=True)
