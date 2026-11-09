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
SECRETS_DIR = STATE_DIR / "secrets"          # gitignored; only `publish.py refresh` writes here
POSTS_DIR = REPO / "posts"                   # committed; served publicly via raw.githubusercontent.com
REPORTS_DIR = REPO / "reports"
WORK_DIR = REPO / "_work"                    # gitignored scratch space, one folder per run

IDLY_API = "https://api.idly.news/api/v1"
IMAGE_BASE = os.environ.get(
    "IDLY_IMAGE_BASE", "https://raw.githubusercontent.com/rsofficial01/idly-social/main")

IST = timezone(timedelta(hours=5, minutes=30), "IST")

# Instagram account -> idly category and the username its token must belong to.
ACCOUNTS: dict[str, dict] = {
    "idlynews":       {"category": "news",       "username": "idlynews"},
    "idlytech":       {"category": "tech",       "username": "idlytech"},
    "idlyhype":       {"category": "hype",       "username": "idlyhype"},
    "idlyautomotive": {"category": "automotive", "username": "idlyautomotive"},
    "idlynerd":       {"category": "nerd",       "username": "idlynerd"},
}
CATEGORY_TO_ACCOUNT = {v["category"]: k for k, v in ACCOUNTS.items()}  # sports: no account yet


def token_env(account: str) -> str:
    return f"IG_TOKEN_{account.upper()}"


def expiry_env(account: str) -> str:
    """Optional, non-secret: the token's expiry date (YYYY-MM-DD), used for the 10-day warning."""
    return f"IG_TOKEN_EXPIRES_{account.upper()}"


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


# ---- logging ----------------------------------------------------------------

def log(*parts) -> None:
    """Progress messages go to stderr; stdout is kept for results."""
    print(*parts, file=sys.stderr, flush=True)
