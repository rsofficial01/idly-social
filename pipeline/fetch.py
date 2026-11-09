"""Fetch recent idly stories and pick Instagram candidates per account.

    python3 pipeline/fetch.py [--hours 14] [--top 5] [--date YYYY-MM-DD --slot am|pm] [--out PATH]

Rules: published in the last N hours, source_count >= 2, not archived, not sponsored,
not already posted (state/posted.json), not gossip. Borderline stories stay in the list
with a "review" flag. Ranked by priority_score, then trending_score.
Writes _work/<date>-<slot>/candidates.json and prints a short summary.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial
from pipeline.common import (ACCOUNTS, CATEGORY_TO_ACCOUNT, IDLY_API, IST, default_date, default_slot,
                             log, now_utc, parse_time, posted_story_ids, save_json, work_dir)

USER_AGENT = "idly-social/1.0 (+https://idly.news)"


def get_json(url: str, params: dict, attempts: int = 3) -> dict:
    for i in range(1, attempts + 1):
        try:
            r = requests.get(url, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if i == attempts:
                raise RuntimeError(f"idly API failed after {attempts} tries: {e}") from e
            time.sleep(2 * i)


def fetch_articles(hours: float, max_pages: int = 20, page_size: int = 50) -> list[dict]:
    """Newest first; stop paging once a page reaches past the time window."""
    cutoff = now_utc() - timedelta(hours=hours)
    seen: dict[int, dict] = {}
    for page in range(1, max_pages + 1):
        data = get_json(f"{IDLY_API}/articles/",
                        {"ordering": "-published_at", "page_size": page_size, "page": page})
        rows = data.get("results") or []
        for row in rows:
            seen.setdefault(row["id"], row)
        if not rows or not data.get("next"):
            break
        if min(parse_time(r["published_at"]) for r in rows) < cutoff:
            break
    return list(seen.values())


def summarize(a: dict, account: str, review: list[str]) -> dict:
    published = parse_time(a["published_at"])
    free_images = [
        {k: ic.get(k) for k in ("credit", "licence_name", "subject", "file_page", "url") if ic.get(k)}
        for ic in a.get("image_credits") or []
        if ic.get("origin") not in ("outlet", "card")      # never other outlets' photos
    ]
    return {
        "id": a["id"],
        "account": account,
        "title": a.get("title"),
        "dek": a.get("dek"),
        "gist": a.get("gist") or [],
        "category": a.get("category"),
        "subcategory": a.get("subcategory"),
        "format": a.get("format"),
        "source_count": a.get("source_count"),
        "sources": [o.get("name") for o in a.get("source_outlets") or []],
        "published_at": a["published_at"],
        "published_ist": published.astimezone(IST).strftime("%d %b %H:%M IST"),
        "age_hours": round((now_utc() - published).total_seconds() / 3600, 1),
        "priority_score": round(a.get("priority_score") or 0, 4),
        "trending_score": round(a.get("trending_score") or 0, 4),
        "tags": [t.get("name") for t in a.get("tags") or []],
        "review": review,
        "free_images": free_images,
    }


def select_candidates(articles: list[dict], hours: float, top: int = 5) -> dict:
    cutoff = now_utc() - timedelta(hours=hours)
    already = posted_story_ids()
    per_account: dict[str, list[dict]] = {a: [] for a in ACCOUNTS}
    excluded: list[dict] = []
    counts = {"fetched": len(articles), "outside_window": 0, "no_account": 0}

    for a in articles:
        if parse_time(a["published_at"]) < cutoff:
            counts["outside_window"] += 1
            continue
        account = CATEGORY_TO_ACCOUNT.get(a.get("category"))
        if not account:
            counts["no_account"] += 1          # e.g. sports: no Instagram account yet
            continue
        reason = None
        if a.get("is_archived"):
            reason = "archived"
        elif (a.get("source_count") or 0) < 2:
            reason = f"single source (source_count={a.get('source_count')})"
        elif a.get("is_sponsored"):
            reason = "sponsored"
        elif a["id"] in already:
            reason = "already posted"
        verdict, terms = editorial.screen_story(a)
        if not reason and verdict == "block":
            reason = "gossip/personal life: " + ", ".join(terms)
        if reason:
            excluded.append({"id": a["id"], "account": account, "title": a.get("title"), "reason": reason})
            continue
        review = [f"gossip check: {t}" for t in terms] if verdict == "review" else []
        if a.get("pr_supplied"):
            review.append("press-release supplied")
        per_account[account].append(summarize(a, account, review))

    for account, rows in per_account.items():
        rows.sort(key=lambda c: (c["priority_score"], c["trending_score"]), reverse=True)
        per_account[account] = rows[:top]
    return {"accounts": per_account, "excluded": excluded, "counts": counts}


def run(hours: float = 14, top: int = 5, date: str | None = None, slot: str | None = None,
        out: Path | None = None) -> tuple[dict, Path]:
    date, slot = date or default_date(), slot or default_slot()
    result = select_candidates(fetch_articles(hours), hours, top)
    result = {"date": date, "slot": slot, "window_hours": hours,
              "generated_at": now_utc().isoformat(timespec="seconds"), **result}
    out = Path(out) if out else work_dir(date, slot) / "candidates.json"
    save_json(out, result)
    return result, out


def print_summary(result: dict) -> None:
    c = result["counts"]
    print(f"Candidates for {result['date']} {result['slot']} (last {result['window_hours']}h; "
          f"{c['fetched']} fetched, {c['no_account']} without an account, {len(result['excluded'])} excluded)")
    for account, rows in result["accounts"].items():
        print(f"\n@{account}")
        if not rows:
            print("  (no story passes the rules)")
        for i, r in enumerate(rows, 1):
            flag = f"  [REVIEW: {'; '.join(r['review'])}]" if r["review"] else ""
            print(f"  {i}. #{r['id']} p={r['priority_score']:.3f} src={r['source_count']} "
                  f"{r['published_ist']}  {r['title']}{flag}")
    if result["excluded"]:
        print("\nExcluded:")
        for e in result["excluded"]:
            print(f"  #{e['id']} @{e['account']}: {e['title']}  -> {e['reason']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=14)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--date")
    ap.add_argument("--slot", choices=["am", "pm"])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    result, out = run(args.hours, args.top, args.date, args.slot, args.out)
    print_summary(result)
    log(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
