"""One posting run (am ~8:40 IST, pm ~18:40 IST). Every step runs on its own; see RUNBOOK.md.

  python3 pipeline/run_day.py fetch        # 1. candidates  -> _work/<date>-<slot>/candidates.json
  python3 pipeline/run_day.py check        # 2. Meta access per account: token, id, host, quota, expiry -> check.json
     ... the Claude run writes _work/<date>-<slot>/cards.json (picks, copy, photos, captions, scores)
  python3 pipeline/run_day.py render       # 3. validate + 12/14 gate + cardkit render + copy JPEGs to posts/<date>/
     ... the Claude run commits posts/<date>/ and pushes
  python3 pipeline/run_day.py wait-urls    # 4. wait until every public URL is HTTP 200 image/jpeg
  python3 pipeline/run_day.py publish      # 5. publish (never below 12/14) -> state/posted.json
  python3 pipeline/run_day.py report       # 6. reports/<date>-<slot>.md, summary on stdout
     ... the Claude run commits state/posted.json + reports/, pushes, sends the summary

  python3 pipeline/run_day.py dry-run      # render + publish + report without touching posts/, state/ or Instagram

Options for every step: --date YYYY-MM-DD --slot am|pm (default: now, IST).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import date as Date
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial, fetch, publish
from pipeline.common import (ACCOUNTS, POSTS_DIR, REPO, REPORTS_DIR, default_date, default_slot, load_json,
                             log, posted_story_ids, public_url, repo_path, save_json, slot_already_posted,
                             work_dir)

SLOT_TIME = {"am": "8:40 AM IST", "pm": "6:40 PM IST"}


# ---- cards JSON validation -----------------------------------------------------------

def validate_cards(doc: dict, date: str, slot: str, allow_carousel: bool = False) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    if (doc.get("date"), doc.get("slot")) != (date, slot):
        errs.append(f"cards.json is for {doc.get('date')} {doc.get('slot')}, this run is {date} {slot}")
    seen = set()
    for i, post in enumerate(doc.get("posts") or [], 1):
        acct, sid = post.get("account"), post.get("story_id")
        who = f"post {i} (@{acct} #{sid})"
        if acct not in ACCOUNTS:
            errs.append(f"{who}: unknown account")
            continue
        if acct in seen:
            errs.append(f"{who}: only one post per account per run")
        seen.add(acct)
        if not isinstance(sid, int):
            errs.append(f"{who}: story_id must be the idly article id")
        elif sid in posted_story_ids(acct):
            errs.append(f"{who}: story already posted on @{acct}")
        if slot_already_posted(acct, date, slot):
            errs.append(f"{who}: @{acct} already posted in this slot")
        cards = post.get("cards") or []
        if not cards or len(cards) > 10 or (len(cards) > 1 and not allow_carousel):
            errs.append(f"{who}: needs exactly 1 card (carousels need --allow-carousel, max 10)")
        for j, card in enumerate(cards, 1):
            errs += [f"{who} card {j}: {e}" for e in editorial.card_problems(card)]
            if not card.get("photo") or not repo_path(card["photo"]).is_file():
                errs.append(f"{who} card {j}: photo file not found: {card.get('photo')!r}")
        errs += [f"{who}: {e}" for e in publish.collaborator_problems(post.get("collaborators"), acct)]
        src = post.get("photo_source") or {}
        if src.get("viewed") is not True:
            errs.append(f"{who}: photo_source.viewed must be true (look at every image before use)")
        for key in ("page", "licence"):
            if not src.get(key):
                errs.append(f"{who}: photo_source.{key} is required")
        cap_errs, cap_warns = editorial.post_problems(post.get("caption", ""), post.get("score"))
        errs += [f"{who} caption: {e}" for e in cap_errs]
        warns += [f"{who} caption: {w}" for w in cap_warns]
        problems = editorial.score_problems(post.get("score"))
        errs += [f"{who}: {p}" for p in problems]
        total = editorial.score_total(post.get("score"))
        if not problems and total < editorial.GATE:
            errs.append(f"{who}: scores {total}/{editorial.SCORE_MAX}, below the {editorial.GATE} gate. "
                        f"Rewrite it, or move it to 'skipped' with its best score")
    for s in doc.get("skipped") or []:
        if s.get("account") not in ACCOUNTS or not s.get("reason"):
            errs.append(f"skipped entry needs a known account and a reason: {s}")
    return errs, warns


# ---- rendering ----------------------------------------------------------------------

def card_date(date: str) -> str:
    d = Date.fromisoformat(date)
    return f"{d.day} {d:%b %Y}"            # "9 Nov 2026"


def render_with_cardkit(cards: list[dict], out_dir: Path) -> list[Path]:
    """Render with cardkit and return one JPEG per card, in order."""
    from cardkit.render import render_cards

    out_dir.mkdir(parents=True, exist_ok=True)
    returned = [Path(p) for p in render_cards(cards, str(out_dir))]
    jpgs = []
    for card in cards:
        jpg = out_dir / f"{card['slug']}.jpg"
        if not jpg.is_file():
            jpg = next((p.with_suffix(".jpg") for p in returned
                        if card["slug"] in p.name and p.with_suffix(".jpg").is_file()), None)
        if jpg is None:
            raise RuntimeError(f"cardkit produced no JPEG for {card['slug']}")
        jpgs.append(jpg)
    return jpgs


RENDERER = render_with_cardkit      # tests swap this for a stub when cardkit isn't available


def render_and_stage(doc: dict, date: str, slot: str, dry_run: bool) -> dict:
    wd = work_dir(date, slot)
    stage_root = wd / "dryrun-posts" if dry_run else POSTS_DIR
    plan = {"date": date, "slot": slot, "dry_run": dry_run, "posts": [],
            "skipped": doc.get("skipped") or [], "results": {}}
    for post in doc.get("posts") or []:
        base = f"{slot}-{post['account']}-{post['story_id']}"
        many = len(post["cards"]) > 1
        kit_cards = [{
            "acct": post["account"], "tag": c["tag"], "stat": c["stat"], "stat_label": c["stat_label"],
            "headline": c["headline"], "bullets": c["bullets"], "photo": str(repo_path(c["photo"])),
            "photo_credit": c["photo_credit"], "date": card_date(date),
            "slug": f"{base}-{n}" if many else base,
        } for n, c in enumerate(post["cards"], 1)]
        images = []
        for card, jpg in zip(kit_cards, RENDERER(kit_cards, wd / "render")):
            rel = f"posts/{date}/{card['slug']}.jpg"
            dest = stage_root / date / f"{card['slug']}.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(jpg, dest)
            publish.check_jpeg(dest)
            images.append({"rel": rel, "local": str(dest), "url": public_url(rel)})
        plan["posts"].append({**post, "images": images})
    save_json(wd / "plan.json", plan)
    return plan


# ---- public URL check ---------------------------------------------------------------

def url_ready(url: str, size: int | None = None, content_types=("image/jpeg",)) -> tuple[bool, str]:
    """HTTP 200 with one of `content_types` (raw.githubusercontent.com serves .jpg as image/jpeg, .mp4 as
    application/octet-stream) and, if given, the staged file's size."""
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.close()
    except requests.RequestException as e:
        return False, type(e).__name__
    ctype, length = r.headers.get("content-type", ""), r.headers.get("content-length")
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not ctype.startswith(tuple(content_types)):
        return False, f"content-type {ctype!r}"
    if size and length and int(length) != size:
        return False, "size differs from the staged file (stale cache?)"
    return True, "ok"


# ---- publish -------------------------------------------------------------------------

def publish_one(post: dict, date: str, slot: str, dry_run: bool) -> dict:
    acct, score = post["account"], post.get("score")
    base = {"story_id": post["story_id"], "score_total": editorial.score_total(score)}
    if not editorial.passes_gate(score):          # also enforced inside publish.publish_post
        return {**base, "status": "refused", "reason": editorial.gate_message(score)}
    if not dry_run:
        if slot_already_posted(acct, date, slot):
            return {**base, "status": "skipped", "reason": "already posted in this slot"}
        for img in post["images"]:
            ok, why = url_ready(img["url"], Path(img["local"]).stat().st_size)
            if not ok:
                return {**base, "status": "skipped", "reason": f"image not public yet ({why}): {img['url']}"}
    try:
        res = publish.publish_post(acct, [i["url"] for i in post["images"]], post["caption"], score=score,
                                   story_id=post["story_id"], date=date, slot=slot,
                                   alt_text=post.get("alt_text", ""), collaborators=post.get("collaborators"),
                                   dry_run=dry_run)
        return {**base, **res}
    except publish.GateRefused as e:
        return {**base, "status": "refused", "reason": str(e)}
    except (publish.IGError, ValueError) as e:
        return {**base, "status": "failed", "reason": str(e)}


# ---- report ----------------------------------------------------------------------------

def build_report(plan: dict, candidates: dict | None, check: dict | None) -> tuple[str, str]:
    date, slot, dry = plan["date"], plan["slot"], plan["dry_run"]
    nice = f"{Date.fromisoformat(date):%a} {card_date(date)}, {slot} run ({SLOT_TIME[slot]})"
    results = plan.get("results") or {}
    posted = [(p, results.get(p["account"], {})) for p in plan["posts"]]
    covered = {p["account"] for p in plan["posts"]} | {s.get("account") for s in plan["skipped"]}

    lines = [f"# idly Instagram: {nice}", "", f"Mode: {'DRY RUN (nothing posted)' if dry else 'LIVE'}  ",
             f"Gate: {editorial.GATE}/{editorial.SCORE_MAX} on the 7-check score", "", "## Results", ""]
    for p, r in posted:
        status = r.get("status", "not published")
        link = r.get("permalink") or ""
        reason = f": {r['reason']}" if r.get("reason") else ""
        lines.append(f"- @{p['account']} · #{p['story_id']} {p.get('title', '')} · "
                     f"{editorial.score_total(p.get('score'))}/14 · **{status}** {link}{reason}")
    for s in plan["skipped"]:
        best = s.get("best_total")
        best = f"best {best}/14" if best is not None else "not scored"
        story = f"#{s['story_id']} {s.get('title', '')}" if s.get("story_id") else "no story"
        lines.append(f"- @{s['account']} · {story} · {best} · **skipped**: {s['reason']}")
    for acct in ACCOUNTS:
        if acct not in covered:
            lines.append(f"- @{acct} · **no decision recorded** in cards.json")

    lines += ["", "## Scores", "", "| account | story | hook | read | send | keep | reply | original | alone "
              "| total | notes |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p, _ in posted:
        sc = p.get("score") or {}
        cells = " | ".join(str(sc.get(k, "")) for k in editorial.SCORE_KEYS)
        lines.append(f"| @{p['account']} | #{p['story_id']} | {cells} | **{editorial.score_total(sc)}** "
                     f"| {str(sc.get('notes', '')).replace('|', '/')} |")
    for s in plan["skipped"]:
        sc = s.get("score") or {}
        cells = " | ".join(str(sc.get(k, "")) for k in editorial.SCORE_KEYS)
        best = "-" if s.get("best_total") is None else s["best_total"]
        lines.append(f"| @{s['account']} (skipped) | #{s.get('story_id') or '-'} | {cells} "
                     f"| {best} | {str(s.get('reason', '')).replace('|', '/')} |")

    access_warn = [f"@{t['account']}: {w}" for t in (check or {}).get("accounts", [])
                   for w in t.get("warnings", [])]
    if check is None:
        access_lines = ["- access check not run (run_day.py check)"]
    else:                                      # the check's own output: token, host, id, quota per account
        access_lines = ["```", *publish.format_check(check), "```"]
    lines += ["", "## Meta access", ""] + access_lines

    lines += ["", "## Captions", ""]
    for p, _ in posted:
        lines += [f"### @{p['account']} · #{p['story_id']}", "",
                  *[f"- image: {i['url']}" for i in p["images"]],
                  f"- photo: {(p.get('photo_source') or {}).get('page', '')} "
                  f"({(p.get('photo_source') or {}).get('licence', '')})",
                  *([f"- collaborators: {', '.join('@' + c for c in p['collaborators'])}"]
                    if p.get("collaborators") else []),
                  "", "```", p["caption"], "```", ""]

    if candidates:
        lines += ["## Candidates seen", ""]
        for acct, rows in candidates.get("accounts", {}).items():
            lines.append(f"- @{acct}: " + ("; ".join(
                f"#{r['id']} {r['title']}" + (" [review]" if r["review"] else "") for r in rows) or "none"))
        for e in candidates.get("excluded", []):
            lines.append(f"- excluded #{e['id']} (@{e['account']}) {e['title']}: {e['reason']}")

    # short summary for the session's final message
    live = [f"@{p['account']} {editorial.score_total(p.get('score'))}/14 {r.get('permalink', '')}"
            for p, r in posted if r.get("status") == "posted"]
    would = [f"@{p['account']} {editorial.score_total(p.get('score'))}/14"
             for p, r in posted if r.get("status") == "dry-run"]
    not_live = [f"@{p['account']}: {r.get('status', 'not published')} ({r.get('reason', '')})"
                for p, r in posted if r.get("status") not in ("posted", "dry-run")]
    not_live += [f"@{s['account']}: {s['reason']}" + (f" (best {s['best_total']}/14)"
                 if s.get("best_total") is not None else "") for s in plan["skipped"]]
    not_live += [f"@{a}: no decision recorded" for a in ACCOUNTS if a not in covered]
    summary = [f"idly Instagram, {nice}{' [DRY RUN]' if dry else ''}"]
    if live or not would:
        summary.append("Live: " + (" · ".join(live) or "nothing"))
    if would:
        summary.append("Would post: " + " · ".join(would))
    summary.append("Skipped: " + (" · ".join(not_live) or "none"))
    if access_warn:
        summary.append("Access: " + " · ".join(access_warn))
    return "\n".join(lines) + "\n", "\n".join(summary)


# ---- commands ------------------------------------------------------------------------------

def cmd_fetch(a) -> int:
    result, out = fetch.run(a.hours, a.top, a.date, a.slot)
    fetch.print_summary(result)
    log(f"\nwrote {out.relative_to(REPO)}")
    return 0


def cmd_check(a) -> int:
    """Per account: own token (IG_TOKEN_<ACCOUNT>) or the shared one; id, host, publishing limit, expiry."""
    report = publish.check_accounts(online=not a.offline, expiry=not a.no_refresh)
    save_json(work_dir(a.date, a.slot) / "check.json", report)
    print("\n".join(publish.format_check(report)))
    return 0 if report["ok"] or a.offline else 1


def cmd_render(a) -> int:
    wd = work_dir(a.date, a.slot)
    cards_path = a.cards or wd / "cards.json"
    doc = load_json(cards_path)
    if doc is None:
        log(f"no cards file at {cards_path}")
        return 2
    errs, warns = validate_cards(doc, a.date, a.slot, a.allow_carousel)
    for w in warns:
        log(f"warning: {w}")
    if errs:
        log("cards.json has problems; fix them (or move the post to 'skipped') and run render again:")
        for e in errs:
            log(f"  - {e}")
        return 2
    plan = render_and_stage(doc, a.date, a.slot, a.dry_run)
    for p in plan["posts"]:
        for img in p["images"]:
            print(f"@{p['account']}: {Path(img['local']).relative_to(REPO)}  ->  {img['url']}")
    if not a.dry_run and plan["posts"]:
        log(f"\nnext: git add posts/{a.date} && git commit -m 'posts {a.date} {a.slot}' && git push, "
            f"then run wait-urls")
    return 0


def cmd_wait_urls(a) -> int:
    plan = load_json(work_dir(a.date, a.slot) / "plan.json")
    if not plan or plan["dry_run"]:
        log("dry run (or no plan): nothing to wait for")
        return 0
    pending = {i["url"]: Path(i["local"]).stat().st_size for p in plan["posts"] for i in p["images"]}
    deadline = time.monotonic() + a.timeout
    while pending:
        for url, size in list(pending.items()):
            ok, why = url_ready(url, size)
            if ok:
                log(f"live: {url}")
                del pending[url]
        if not pending:
            break
        if time.monotonic() > deadline:
            for url in pending:
                log(f"NOT live after {a.timeout}s: {url} ({url_ready(url)[1]})")
            return 1
        time.sleep(15)
    return 0


def cmd_publish(a) -> int:
    wd = work_dir(a.date, a.slot)
    plan = load_json(wd / "plan.json")
    if not plan:
        log("no plan.json: run render first")
        return 2
    dry = a.dry_run or plan["dry_run"]
    failed = 0
    for post in plan["posts"]:
        log(f"@{post['account']} #{post['story_id']}:")
        res = publish_one(post, a.date, a.slot, dry)
        plan["results"][post["account"]] = res
        save_json(wd / "plan.json", plan)          # saved after every post, so a crash loses nothing
        failed += res["status"] == "failed"
        if res["status"] not in ("posted", "dry-run"):
            log(f"  {res['status']}: {res.get('reason')}")
    return 1 if failed else 0


def cmd_report(a) -> int:
    wd = work_dir(a.date, a.slot)
    plan = load_json(wd / "plan.json")
    if not plan:
        log("no plan.json: run render first (a cards.json with only 'skipped' entries is fine)")
        return 2
    md, summary = build_report(plan, load_json(wd / "candidates.json"), load_json(wd / "check.json"))
    out = wd / "report-dryrun.md" if plan["dry_run"] else REPORTS_DIR / f"{a.date}-{a.slot}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    log(f"wrote {out.relative_to(REPO)}\n")
    print(summary)
    return 0


def cmd_dry_run(a) -> int:
    a.dry_run = True
    for step in (cmd_render, cmd_publish, cmd_report):
        if code := step(a):
            return code
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None)
    ap.add_argument("--slot", choices=["am", "pm"], default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--hours", type=float, default=14)
    f.add_argument("--top", type=int, default=5)
    c = sub.add_parser("check", aliases=["tokens"],
                       help="Meta access per account: token, id, host, publishing limit, expiry "
                            "('tokens' is the old name)")
    c.add_argument("--offline", action="store_true")
    c.add_argument("--no-refresh", action="store_true", help="skip the token expiry check")
    for name in ("render", "dry-run"):
        r = sub.add_parser(name)
        r.add_argument("--cards", type=Path, help="default: _work/<date>-<slot>/cards.json")
        r.add_argument("--allow-carousel", action="store_true")
        if name == "render":
            r.add_argument("--dry-run", action="store_true", help="stage in _work/, not posts/")
    sub.add_parser("wait-urls").add_argument("--timeout", type=int, default=900)
    sub.add_parser("publish").add_argument("--dry-run", action="store_true")
    sub.add_parser("report")
    a = ap.parse_args(argv)
    a.date, a.slot = a.date or default_date(), a.slot or default_slot()
    commands = {"fetch": cmd_fetch, "check": cmd_check, "tokens": cmd_check, "render": cmd_render,
                "wait-urls": cmd_wait_urls, "publish": cmd_publish, "report": cmd_report, "dry-run": cmd_dry_run}
    return commands[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
