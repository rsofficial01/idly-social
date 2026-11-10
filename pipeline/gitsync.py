"""Commit and push to main with a rebase-retry loop, for the lane's GitHub Actions runs.

    from pipeline import gitsync
    gitsync.commit_and_push(["queue", "state", "reports"], "lane: rendered 2 specs")

The hourly Claude runs push to the same branch, so a push can be rejected. Then: fetch, rebase onto
origin/main, push again (up to `attempts` times, with backoff). Conflicts the lane can settle itself:
  state/posted.json      both sides appended posts: keep upstream's list plus our new entries
  state/accounts.json    keep upstream, plus the accounts our commit changed
  reports/lane-*.md      keep both sides' lines
Any other conflict aborts the rebase and returns False: the lane's commands are idempotent, so the next run
redoes the work from the remote state (and publish-approved checks Instagram before it ever posts again).
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import time
from pathlib import Path

if __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.common import REPO, log


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_EDITOR": "true", "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *args], cwd=REPO, check=check, capture_output=True, text=True, env=env)


def _show(stage: int, path: str) -> str | None:
    r = git("show", f":{stage}:{path}", check=False)
    return r.stdout if r.returncode == 0 else None


def _key(entry: dict) -> str:
    if isinstance(entry, dict) and entry.get("media_id"):
        return f"{entry.get('account')}:{entry['media_id']}"
    return json.dumps(entry, sort_keys=True, ensure_ascii=False)


def merge_posted(upstream: str, mine: str) -> str:
    up, me = json.loads(upstream or "[]"), json.loads(mine or "[]")
    seen = {_key(e) for e in up}
    merged = up + [e for e in me if _key(e) not in seen]
    return json.dumps(merged, ensure_ascii=False, indent=2) + "\n"


def merge_accounts(base: str | None, upstream: str, mine: str) -> str:
    b, up, me = json.loads(base or "{}"), json.loads(upstream or "{}"), json.loads(mine or "{}")
    accounts = dict(up.get("accounts") or {})
    for name, entry in (me.get("accounts") or {}).items():
        if entry != (b.get("accounts") or {}).get(name):
            accounts[name] = entry
    out = {**up, "accounts": dict(sorted(accounts.items()))}
    return json.dumps(out, ensure_ascii=False, indent=2) + "\n"


def merge_lines(upstream: str, mine: str) -> str:
    up = (upstream or "").splitlines()
    have = set(up)
    return "\n".join(up + [l for l in (mine or "").splitlines() if l not in have]) + "\n"


def resolve_conflict(path: str) -> bool:
    """Settle a rebase conflict in a file the lane knows how to merge. Stage 2 is upstream, 3 is ours."""
    base, upstream, mine = _show(1, path), _show(2, path), _show(3, path)
    if upstream is None or mine is None:
        return False
    try:
        if path == "state/posted.json":
            text = merge_posted(upstream, mine)
        elif path == "state/accounts.json":
            text = merge_accounts(base, upstream, mine)
        elif path.startswith("reports/lane-") and path.endswith(".md"):
            text = merge_lines(upstream, mine)
        else:
            return False
    except ValueError:
        return False
    (REPO / path).write_text(text, encoding="utf-8")
    git("add", "--", path)
    return True


def rebase_onto_origin() -> tuple[bool, str]:
    git("fetch", "origin", "main")
    r = git("rebase", "origin/main", check=False)
    for _ in range(50):                       # one round per replayed commit
        if r.returncode == 0:
            return True, ""
        conflicted = [p for p in git("diff", "--name-only", "--diff-filter=U").stdout.split() if p]
        if not conflicted:
            git("rebase", "--abort", check=False)
            return False, f"rebase failed: {(r.stderr or r.stdout).strip()[:300]}"
        for path in conflicted:
            if not resolve_conflict(path):
                git("rebase", "--abort", check=False)
                return False, f"conflict in {path} that the lane can't merge"
        r = git("rebase", "--continue", check=False)
    git("rebase", "--abort", check=False)
    return False, "rebase did not finish"


def commit(paths: list[str], message: str) -> bool:
    """Stage everything under `paths` (adds, edits, deletions) and commit. False when nothing changed."""
    existing = [p for p in paths if (REPO / p).exists() or git("ls-files", "--", p).stdout.strip()]
    if not existing:
        return False
    git("add", "-A", "--", *existing)
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    git("commit", "-m", message)
    return True


def push_with_retry(attempts: int = 6) -> tuple[bool, str]:
    why = ""
    for i in range(attempts):
        r = git("push", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            return True, ""
        why = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["push rejected"]
        why = why[0]
        log(f"  push {i + 1}/{attempts} rejected ({why}); rebasing onto origin/main")
        ok, msg = rebase_onto_origin()
        if not ok:
            return False, msg
        time.sleep(min(30, 2 ** i) + random.uniform(0, 1.5))
    return False, f"push still rejected after {attempts} tries: {why}"


def commit_and_push(paths: list[str], message: str, attempts: int = 6) -> bool:
    if not commit(paths, message):
        return True
    ok, why = push_with_retry(attempts)
    if not ok:
        log(f"  PUSH FAILED: {why}")
    return ok
