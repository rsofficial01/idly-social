"""The official image lane: posts that need an official publicity image go out with no staff.

A Claude session writes a spec; GitHub Actions (plain code, in this repo) fetches the image from an official
source, frames it around any faces, renders the cards and later publishes; a Claude reviewer run approves.

    queue/pending/<slug>.json        spec, written by a Claude session          (schema: config/spec.schema.json)
    queue/rendered/<slug>/           01.jpg, 02.jpg ..., spec.json, render_report.json   (render-pending)
    queue/approved/<slug>.json       the blind reviewer's score                 (lane.py approve, by Claude)
    queue/posted/<slug>/             the rendered files + approved.json + result.json    (publish-approved)
    queue/rejected/<slug>/           spec.json + reasons.json (+ render_report.json)

    python3 pipeline/lane.py validate [FILE ...]            # check pending specs (all, or the files given)
    python3 pipeline/lane.py render-pending [--push]        # GitHub Actions, every 10 min
    python3 pipeline/lane.py status                         # what is where, with ages
    python3 pipeline/lane.py show SLUG                      # blind review packet (no self score)
    python3 pipeline/lane.py approve SLUG --score-file F    # reviewer's 7-check score -> approved/ (or rejected/)
    python3 pipeline/lane.py reject SLUG --reason TEXT      # reviewer (or anyone) rejects an item
    python3 pipeline/lane.py publish-approved [--push] [--dry-run]   # GitHub Actions, every 10 min

The gate: published only if the LOWER of the self score and the reviewer's score is >= 12/14, and only while
fresh (created_at under 8 hours ago, unless the spec says "evergreen": true). One post per account per run.
Both Actions commands are idempotent, take a lock, and with --push commit and push with a rebase-retry loop.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial, framing, gitsync, official_image, publish
from pipeline.common import (REPO, REPORTS_DIR, load_json, load_posted, log, now_ist, now_utc,
                             parse_time, posted_story_ids, public_url, save_json, token_env)

QUEUE = Path(os.environ.get("IDLY_QUEUE_DIR") or REPO / "queue")
MIN_GAP = timedelta(minutes=30)      # never two posts on one account within 30 minutes
REPORTS = REPORTS_DIR
SCHEMA_FILE = REPO / "config" / "spec.schema.json"
STAGES = ("pending", "rendered", "approved", "rejected", "posted")
FRESH_HOURS = 8
LANE_SLOT = "lane"
FUTURE_SKEW = timedelta(minutes=15)


class LaneReject(Exception):
    def __init__(self, reasons, stage: str = "render"):
        self.reasons = [reasons] if isinstance(reasons, str) else list(reasons)
        self.stage = stage
        super().__init__("; ".join(self.reasons))


# ---- small helpers ------------------------------------------------------------------------------------

def qdir(stage: str) -> Path:
    path = QUEUE / stage
    path.mkdir(parents=True, exist_ok=True)
    return path


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def age_hours(spec: dict) -> float:
    return (now_utc() - parse_time(spec["created_at"])).total_seconds() / 3600


def stale(spec: dict) -> bool:
    return not spec.get("evergreen") and age_hours(spec) >= FRESH_HOURS


def card_date() -> str:
    d = now_ist().date()
    return f"{d.day} {d:%b %Y}"


def rel_to_repo(path: Path) -> str:
    """queue/rendered/<slug>/01.jpg as committed (works when QUEUE is elsewhere too, e.g. in tests)."""
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return "queue/" + Path(path).resolve().relative_to(QUEUE.resolve()).as_posix()


def report_line(text: str) -> None:
    """One line in reports/lane-<IST date>.md (deduplicated), stdout and the Actions step summary."""
    stamp = now_ist()
    line = f"- {stamp:%H:%M} IST · {text}"
    print(line)
    path = REPORTS / f"lane-{stamp.date().isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else f"# Official image lane: {stamp:%d %b %Y}\n\n"
    if text not in existing:                                  # same event (e.g. a missing secret) once a day
        path.write_text(existing + line + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(line + "\n")


@contextlib.contextmanager
def queue_lock():
    """An exclusive lock on this checkout's queue; a second concurrent run exits quietly."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(QUEUE / ".lock", "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another lane run holds the queue lock: nothing to do")
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ---- spec validation ------------------------------------------------------------------------------------

def schema_errors(spec) -> list[str]:
    import jsonschema

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    out = []
    for e in sorted(v.iter_errors(spec), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in e.absolute_path) or "(top)"
        out.append(f"{where}: {e.message}")
    return out


def validate_spec(spec, slug: str) -> list[str]:
    if not isinstance(spec, dict):
        return ["the spec must be a JSON object"]
    errs = schema_errors(spec)
    if not official_image_slug_ok(slug):
        errs.append(f"file name {slug!r}: use 3-80 lowercase letters, digits and hyphens")
    if spec.get("slug") and spec["slug"] != slug:
        errs.append(f"slug {spec['slug']!r} does not match the file name {slug!r}")
    if errs:
        return errs
    self_score = spec["scores"]["self"]
    errs += [f"scores.self: {p}" for p in editorial.score_problems(self_score)]
    if not errs and editorial.score_total(self_score) < editorial.GATE:
        errs.append(f"self score {editorial.score_total(self_score)}/14 is below the {editorial.GATE} gate")
    if spec["idly_article"] and not isinstance(spec.get("story_id"), int):
        errs.append("idly_article is true, so story_id must be the idly article id")
    try:
        if parse_time(spec["created_at"]) - now_utc() > FUTURE_SKEW:
            errs.append("created_at is in the future")
    except ValueError:
        errs.append(f"created_at is not a date-time: {spec['created_at']!r}")
    errs += publish.collaborator_problems(spec.get("collaborators"), spec["account"])
    extra = spec.get("append_slides") or []
    if 1 + len(spec.get("detail_slides") or []) + len(extra) > 10:
        errs.append("a carousel holds at most 10 slides (cover + detail_slides + append_slides)")
    for rel in extra:
        f = (REPO / rel).resolve()
        if not str(f).startswith(str((REPO / "posts").resolve()) + "/") or not f.is_file():
            errs.append(f"append_slides: {rel} is not a file under posts/")
    return errs


def official_image_slug_ok(slug: str) -> bool:
    import re
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", slug or ""))


# ---- moving items ------------------------------------------------------------------------------------------

def reject_item(slug: str, stage: str, reasons: list[str], spec: dict | None = None,
                src: Path | None = None, extra: dict | None = None) -> None:
    dest = qdir("rejected") / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if src and src.is_dir() and (src / "render_report.json").exists():
        shutil.copyfile(src / "render_report.json", dest / "render_report.json")
    if spec is not None:
        save_json(dest / "spec.json", spec)
    save_json(dest / "reasons.json", {"slug": slug, "stage": stage, "reasons": reasons,
                                      "rejected_at": now_utc().isoformat(timespec="seconds"), **(extra or {})})
    if src and src.exists():
        shutil.rmtree(src) if src.is_dir() else src.unlink()
    who = f"@{spec['account']} " if spec and spec.get("account") else ""
    report_line(f"rejected ({stage}) · {who}{slug} · " + "; ".join(reasons))


# ---- render-pending -------------------------------------------------------------------------------------

def render_with_cardkit(posts: list[dict], out_dir: Path, png_dir: Path, report: list) -> list[str]:
    from cardkit.render import render_cards

    return render_cards(posts, str(out_dir), template="hype", png_dir=str(png_dir), report=report)


RENDERER = render_with_cardkit       # tests swap this for a stub when Chrome isn't available


def build_post(spec: dict, slug: str, photo: Path, focal, zoom: float, credit: str) -> dict:
    slides = [{"type": "cover", "headline": spec["headline"], "photo": str(photo), "photo_credit": credit,
               "focal": tuple(focal), "zoom": zoom}]
    for d in spec.get("detail_slides") or []:
        slides.append({"type": "detail", **{k: d[k] for k in ("stat", "stat_label", "bullets", "credit_line")
                                            if d.get(k)}})
    return {"acct": spec["account"], "slug": slug, "date": card_date(), "sources": spec.get("sources"),
            "slides": slides}


def render_one(path: Path) -> tuple[str, str]:
    """Render one pending spec. Returns (status, message): rendered | rejected | retry | skipped."""
    slug = path.stem
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        reject_item(slug, "validate", [f"not valid JSON: {e}"], src=path)
        return "rejected", "invalid JSON"
    errs = validate_spec(spec, slug)
    if errs:
        reject_item(slug, "validate", errs, spec if isinstance(spec, dict) else None, src=path)
        return "rejected", "; ".join(errs)
    digest = spec_hash(spec)
    for stage in ("rendered", "posted"):
        existing = qdir(stage) / slug
        if existing.exists():
            old = load_json(existing / "spec.json") or {}
            if (old.get("lane") or {}).get("spec_sha256") == digest:
                path.unlink()                         # an earlier run finished this one; just tidy up
                return "skipped", f"already {stage}"
            reject_item(slug, "validate", [f"slug {slug!r} is already used by a {stage} item: use a new file name"],
                        spec, src=path)
            return "rejected", "slug in use"
    if (qdir("rejected") / slug).exists():           # a fixed spec under a rejected slug: try again
        shutil.rmtree(qdir("rejected") / slug)
    account = spec["account"]
    try:
        if stale(spec):
            raise LaneReject(f"stale: created {age_hours(spec):.1f}h ago (limit {FRESH_HOURS}h; set "
                             f"\"evergreen\": true only for timeless posts)")
        if spec.get("story_id") is not None and spec["story_id"] in posted_story_ids(account):
            raise LaneReject(f"story #{spec['story_id']} is already posted on @{account}")
        try:
            res, tried = official_image.resolve_first(spec["image"], spec)
        except official_image.ResolveError as e:
            if e.transient:
                report_line(f"waiting · @{account} {slug} · image source not reachable, will retry: {e.reason}")
                return "retry", e.reason
            raise LaneReject(e.reason, "resolve")
        try:
            im = official_image.open_image(res.data)
        except official_image.ResolveError as e:
            raise LaneReject(e.reason, "resolve")
        plan = res.extra.get("plan")
        if plan is None:
            try:
                plan = framing.plan_image(im)
            except framing.FramingError as e:
                raise LaneReject([f"framing: {r}" for r in e.reasons], "framing")
        if plan.upscale > framing.MAX_UPSCALE + 1e-6:
            raise LaneReject(f"framing: {plan.upscale:.2f}x upscale (max {framing.MAX_UPSCALE}x)", "framing")
        caption = editorial.with_credit(spec["caption"], res.credit)
        cap_errs, cap_warns = editorial.post_problems(caption, spec["scores"]["self"],
                                                      idly_article=spec["idly_article"])
        if cap_errs:
            raise LaneReject([f"caption: {e}" for e in cap_errs], "caption")
        if not res.credit.strip():
            raise LaneReject("no image credit", "resolve")

        work = Path(tempfile.mkdtemp(prefix=f"lane-{slug}-"))
        try:
            photo, focal, zoom = framing.render_input(im, plan, work)
            post = build_post(spec, slug, photo, focal, zoom, res.credit)
            slides_report: list = []
            try:
                jpgs = [Path(p) for p in RENDERER([post], work / "out", work / "png", slides_report)]
            except (ValueError, FileNotFoundError) as e:
                raise LaneReject(f"render: {e}", "render")
            problems = []
            for r in slides_report:
                if r.get("overflow"):
                    problems.append(f"slide {r.get('slide')}: text does not fit")
                if r.get("credit_collision") or r.get("credit_inside") is False:
                    problems.append(f"slide {r.get('slide')}: credit line collides with {r.get('credit_collision')}")
                if r.get("type") == "cover" and (r.get("scale") or 0) > framing.MAX_UPSCALE + 0.01:
                    problems.append(f"cover upscaled {r['scale']:.2f}x (max {framing.MAX_UPSCALE}x)")
            if len(jpgs) != len(post["slides"]):
                problems.append(f"rendered {len(jpgs)} files for {len(post['slides'])} slides")
            jpgs += [REPO / rel for rel in spec.get("append_slides") or []]   # prebuilt slides after the cover
            for jpg in jpgs:
                try:
                    publish.check_jpeg(jpg)
                except ValueError as e:
                    problems.append(str(e))
            if problems:
                raise LaneReject(problems, "render")

            staging = qdir("rendered") / f".{slug}.tmp"
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir()
            files = []
            for i, jpg in enumerate(jpgs, 1):
                shutil.copyfile(jpg, staging / f"{i:02d}.jpg")
                files.append(f"{i:02d}.jpg")
            rendered_at = now_utc().isoformat(timespec="seconds")
            save_json(staging / "spec.json", {
                **spec, "slug": slug, "caption_final": caption, "image_credit": res.credit,
                "lane": {"spec_sha256": digest, "rendered_at": rendered_at, "resolver": res.resolver,
                         "source_url": res.source_url, "image_url": res.image_url}})
            save_json(staging / "render_report.json", {
                "slug": slug, "account": account, "rendered_at": rendered_at, "resolver": res.resolver,
                "attempts": tried, "source": res.summary(),
                "faces": plan.faces_src, "framing": plan.to_dict(), "upscale": round(plan.upscale, 3),
                "checks": {"caption_errors": [], "caption_warnings": cap_warns, "jpeg": "ok",
                           "overflow": False, "credit_lines": [r.get("credit_line") for r in slides_report],
                           "max_upscale": framing.MAX_UPSCALE},
                "slides": [{k: v for k, v in r.items() if k != "jpg"} for r in slides_report],
                "files": files, "caption_final": caption})
            os.replace(staging, qdir("rendered") / slug)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        path.unlink()
        msg = (f"{res.resolver} ({res.organisation}) · {plan.mode} · {len(plan.faces_src)} face(s) · "
               f"upscale {plan.upscale:.2f}x · {len(files)} slide(s)")
        report_line(f"rendered · @{account} {slug} · {msg} · awaiting review")
        return "rendered", msg
    except LaneReject as e:
        reject_item(slug, e.stage, e.reasons, spec, src=path)
        return "rejected", str(e)


def cmd_render_pending(a) -> int:
    with queue_lock() as got:
        if not got:
            return 0
        specs = sorted(p for p in qdir("pending").glob("*.json"))[: a.limit or None]
        if not specs:
            log("render-pending: queue/pending is empty")
            return 0
        counts, crashed = {}, 0
        for path in specs:
            log(f"{path.stem}:")
            try:
                status, msg = render_one(path)
            except Exception as e:  # noqa: BLE001 - infrastructure trouble: keep the spec, go red, retry later
                status, msg = "retry", f"{type(e).__name__}: {e}"
                crashed += 1
                report_line(f"error · {path.stem} · {msg} (kept in pending, will retry)")
            counts[status] = counts.get(status, 0) + 1
            log(f"  {status}: {msg}")
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        log(f"render-pending: {summary}")
        if a.push and not gitsync.commit_and_push(["queue", "reports"], f"lane: render-pending ({summary})"):
            return 1
        return 1 if crashed else 0


# ---- review: show / approve / reject ------------------------------------------------------------------

def find_item(slug: str) -> tuple[str, Path] | None:
    for stage in ("approved", "rendered", "pending"):
        p = qdir(stage) / (f"{slug}.json" if stage in ("approved", "pending") else slug)
        if p.exists():
            return stage, p
    return None


def cmd_show(a) -> int:
    rdir = qdir("rendered") / a.slug
    spec, rep = load_json(rdir / "spec.json"), load_json(rdir / "render_report.json")
    if not spec:
        log(f"no rendered item {a.slug!r}")
        return 2
    packet = {
        "slug": a.slug, "account": spec["account"], "story_id": spec.get("story_id"), "title": spec.get("title"),
        "idly_article": spec["idly_article"], "headline": spec["headline"], "detail_slides": spec.get("detail_slides"),
        "sources": spec.get("sources"), "caption_final": spec["caption_final"], "alt_text": spec.get("alt_text", ""),
        "image": {"credit": spec["image_credit"], **{k: (rep or {}).get("source", {}).get(k)
                                                     for k in ("resolver", "source_url", "image_url", "organisation")}},
        "framing": (rep or {}).get("framing"), "faces": len((rep or {}).get("faces") or []),
        "created_at": spec["created_at"], "age_hours": round(age_hours(spec), 1),
        "files": [rel_to_repo(rdir / f) for f in (rep or {}).get("files", [])],
        "note": "Blind packet: the self score is left out on purpose. Score the 7 checks yourself.",
    }
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


def cmd_approve(a) -> int:
    rdir = qdir("rendered") / a.slug
    spec = load_json(rdir / "spec.json")
    if not spec:
        log(f"no rendered item {a.slug!r} (render-pending makes it; check `lane.py status`)")
        return 2
    try:
        score = json.loads(Path(a.score_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log(f"can't read the score file: {e}")
        return 2
    problems = editorial.score_problems(score)
    if problems:
        log("reviewer score problems: " + "; ".join(problems))
        return 2
    mine, theirs = editorial.score_total(spec["scores"]["self"]), editorial.score_total(score)
    if min(mine, theirs) < editorial.GATE:
        reject_item(a.slug, "review", [f"lower score {min(mine, theirs)}/14 is below the {editorial.GATE} gate "
                                       f"(self {mine}, reviewer {theirs}): {score.get('notes', '')}"],
                    spec, src=rdir, extra={"reviewer": score})
        print(f"rejected: {min(mine, theirs)}/14")
        return 0
    save_json(qdir("approved") / f"{a.slug}.json", {
        "slug": a.slug, "reviewer": score, "reviewed_at": now_utc().isoformat(timespec="seconds"),
        "reviewed_by": a.by, "notes": a.notes or ""})
    report_line(f"approved · @{spec['account']} {a.slug} · self {mine}, reviewer {theirs} -> {min(mine, theirs)}/14")
    print(f"approved: {min(mine, theirs)}/14 (publish-approved posts it on its next run)")
    return 0


def cmd_reject(a) -> int:
    found = find_item(a.slug)
    if not found:
        log(f"no pending, rendered or approved item {a.slug!r}")
        return 2
    stage, path = found
    rdir = qdir("rendered") / a.slug
    spec = load_json(rdir / "spec.json") or (load_json(path) if stage == "pending" else None)
    if stage == "approved":
        path.unlink()
        path = rdir if rdir.exists() else None
    reject_item(a.slug, "review", [a.reason], spec, src=path)
    return 0


def cmd_status(a) -> int:
    for stage in STAGES:
        items = sorted(p for p in qdir(stage).iterdir() if not p.name.startswith("."))
        print(f"{stage}: {len(items)}")
        for p in items[-15:]:
            spec = load_json(p) if p.suffix == ".json" and stage == "pending" else load_json(p / "spec.json") \
                if p.is_dir() else None
            extra = ""
            if spec and spec.get("created_at"):
                extra = f"  @{spec.get('account')}  {age_hours(spec):.1f}h old"
            if stage == "rejected" and p.is_dir():
                why = (load_json(p / "reasons.json") or {}).get("reasons") or []
                extra += f"  ({'; '.join(why)[:140]})"
            print(f"  {p.stem if p.suffix == '.json' else p.name}{extra}")
    return 0


def cmd_validate(a) -> int:
    paths = [Path(p) for p in a.files] or sorted(qdir("pending").glob("*.json"))
    bad = 0
    for p in paths:
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
            errs = validate_spec(spec, p.stem)
        except (OSError, ValueError) as e:
            errs = [str(e)]
        print(f"{p}: {'ok' if not errs else 'PROBLEMS'}")
        for e in errs:
            print(f"  - {e}")
        bad += bool(errs)
    return 1 if bad else 0


# ---- publish-approved ----------------------------------------------------------------------------------

def lower_score(spec: dict, approval: dict) -> dict:
    a, b = spec["scores"]["self"], approval.get("reviewer")
    return a if editorial.score_total(a) <= editorial.score_total(b) else b


def finish_posted(slug: str, approval: dict, result: dict) -> None:
    rdir, dest = qdir("rendered") / slug, qdir("posted") / slug
    if rdir.exists() and not dest.exists():
        os.replace(rdir, dest)
    save_json(dest / "approved.json", approval)
    save_json(dest / "result.json", result)
    (qdir("approved") / f"{slug}.json").unlink(missing_ok=True)


def publish_one(slug: str, *, dry_run: bool, allow_shared: bool, busy: set) -> tuple[str, str]:
    """Returns (status, message): posted | dry-run | rejected | skipped | waiting | failed."""
    apath = qdir("approved") / f"{slug}.json"
    approval = load_json(apath) or {}
    rdir = qdir("rendered") / slug
    spec = load_json(rdir / "spec.json")
    if (qdir("posted") / slug).exists():
        apath.unlink(missing_ok=True)
        return "skipped", "already posted"
    if not spec:
        apath.unlink(missing_ok=True)
        reject_item(slug, "publish", ["approved, but there is no rendered item"], extra={"approval": approval})
        return "rejected", "no rendered item"
    account = spec["account"]
    prior = next((p for p in load_posted() if p.get("lane_slug") == slug), None)
    if prior:                                     # posted by an earlier run whose final commit didn't land
        finish_posted(slug, approval, {**prior, "status": "posted", "recovered": True})
        report_line(f"posted (recovered record) · @{account} {slug} · {prior.get('permalink', '')}")
        return "posted", "recovered"
    problems = editorial.score_problems(spec["scores"]["self"]) + \
        [f"reviewer: {p}" for p in editorial.score_problems(approval.get("reviewer"))]
    if problems:
        raise LaneReject(problems, "publish")
    low = lower_score(spec, approval)
    if editorial.score_total(low) < editorial.GATE:
        raise LaneReject(f"lower score {editorial.score_total(low)}/14 is below the {editorial.GATE} gate", "publish")
    if stale(spec):
        raise LaneReject(f"stale: created {age_hours(spec):.1f}h ago (limit {FRESH_HOURS}h)", "publish")
    if spec.get("story_id") is not None and spec["story_id"] in posted_story_ids(account):
        raise LaneReject(f"story #{spec['story_id']} is already posted on @{account}", "publish")
    if account in busy:
        return "waiting", f"@{account} already posted in this run; next run"
    last = max((parse_time(p["posted_at"]) for p in load_posted()
                if p.get("account") == account and p.get("posted_at")), default=None)
    if last is not None and now_utc() - last < MIN_GAP:
        return "waiting", f"@{account} posted {int((now_utc() - last).total_seconds() // 60)} min ago (min gap {MIN_GAP})"
    if not dry_run and not publish.account_token(account) and not allow_shared:
        report_line(f"skipped · @{account} {slug} · the {token_env(account)} secret is not set "
                    f"(docs/SETUP-GITHUB-SECRETS.md); it posts once it is, if still fresh")
        return "skipped", f"{token_env(account)} not set"
    rep = load_json(rdir / "render_report.json") or {}
    files = [rdir / f for f in rep.get("files") or sorted(p.name for p in rdir.glob("*.jpg"))]
    for f in files:
        try:
            publish.check_jpeg(f)
        except ValueError as e:
            raise LaneReject(str(e), "publish")
    urls = [public_url(rel_to_repo(f)) for f in files]
    caption = spec["caption_final"]
    if not dry_run:
        from pipeline.run_day import url_ready
        for f, url in zip(files, urls):
            ok, why = url_ready(url, f.stat().st_size)
            if not ok:
                return "waiting", f"image not public yet ({why}): {url}"
        client, ig_id = publish.connect(account)      # duplicate guard: is this caption already on the account?
        media_id = client.find_recent(ig_id, caption)
        if media_id:
            result = {"status": "posted", "media_id": media_id, "permalink": client.permalink(media_id),
                      "recovered": True, "note": "found on Instagram already; not posted again"}
            finish_posted(slug, approval, result)
            report_line(f"posted (found on Instagram) · @{account} {slug} · {result['permalink']}")
            return "posted", "recovered from Instagram"
    archived = [public_url(rel_to_repo(qdir("posted") / slug / f.name)) for f in files]
    res = publish.publish_post(
        account, urls, caption, score=low, story_id=spec.get("story_id"), date=now_ist().date().isoformat(),
        slot=LANE_SLOT, alt_text=spec.get("alt_text", ""), collaborators=spec.get("collaborators"),
        dry_run=dry_run, idly_article=spec["idly_article"],
        record_extra={"lane": "official-image", "lane_slug": slug, "image_credit": spec.get("image_credit"),
                      "image_source": (spec.get("lane") or {}).get("source_url"), "archived_images": archived,
                      "score_self": editorial.score_total(spec["scores"]["self"]),
                      "score_reviewer": editorial.score_total(approval.get("reviewer"))})
    if dry_run:
        return "dry-run", f"would post {len(urls)} image(s) to @{account}"
    finish_posted(slug, approval, res)
    busy.add(account)
    report_line(f"posted · @{account} {slug} · {editorial.score_total(low)}/14 · {res.get('permalink', '')}")
    return "posted", res.get("permalink", "")


def cmd_publish_approved(a) -> int:
    with queue_lock() as got:
        if not got:
            return 0
        approved = sorted(p.stem for p in qdir("approved").glob("*.json"))
        if not approved:
            log("publish-approved: nothing approved")
            return 0
        busy, failed, counts = set(), 0, {}
        for slug in approved:
            log(f"{slug}:")
            spec = load_json(qdir("rendered") / slug / "spec.json")
            try:
                status, msg = publish_one(slug, dry_run=a.dry_run, allow_shared=a.allow_shared_token, busy=busy)
            except LaneReject as e:
                (qdir("approved") / f"{slug}.json").unlink(missing_ok=True)
                reject_item(slug, e.stage, e.reasons, spec, src=qdir("rendered") / slug)
                status, msg = "rejected", str(e)
            except publish.GateRefused as e:
                (qdir("approved") / f"{slug}.json").unlink(missing_ok=True)
                reject_item(slug, "publish", [str(e)], spec, src=qdir("rendered") / slug)
                status, msg = "rejected", str(e)
            except (publish.IGError, ValueError) as e:
                status, msg = "failed", str(e)
                failed += 1
                report_line(f"failed · {slug} · {e} (kept in approved; retried next run while fresh)")
            counts[status] = counts.get(status, 0) + 1
            log(f"  {status}: {msg}")
            if a.push and status in ("posted", "rejected"):
                if not gitsync.commit_and_push(["queue", "state", "reports"], f"lane: {status} {slug}"):
                    return 1
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        log(f"publish-approved: {summary}")
        if a.push and not gitsync.commit_and_push(["queue", "state", "reports"], f"lane: publish-approved ({summary})"):
            return 1
        return 1 if failed else 0


# ---- CLI ------------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check pending specs against config/spec.schema.json and the rules")
    v.add_argument("files", nargs="*")
    r = sub.add_parser("render-pending", help="resolve, frame and render every pending spec")
    r.add_argument("--push", action="store_true", help="commit and push queue/ and reports/ (GitHub Actions)")
    r.add_argument("--limit", type=int, default=0)
    sub.add_parser("status", help="what is in each queue folder")
    s = sub.add_parser("show", help="blind review packet for a rendered item (no self score)")
    s.add_argument("slug")
    ok = sub.add_parser("approve", help="record the reviewer's blind score (rejects below the gate)")
    ok.add_argument("slug")
    ok.add_argument("--score-file", required=True)
    ok.add_argument("--notes", default="")
    ok.add_argument("--by", default="claude reviewer (blind)")
    no = sub.add_parser("reject", help="reject a pending, rendered or approved item")
    no.add_argument("slug")
    no.add_argument("--reason", required=True)
    p = sub.add_parser("publish-approved", help="post every approved item that still passes the gate")
    p.add_argument("--push", action="store_true", help="commit and push after each post (GitHub Actions)")
    p.add_argument("--dry-run", action="store_true", help="print the would-be API calls, post nothing")
    p.add_argument("--allow-shared-token", action="store_true",
                   help="use the shared token for accounts without IG_TOKEN_<ACCOUNT> (not in GitHub Actions)")
    a = ap.parse_args(argv)
    commands = {"validate": cmd_validate, "render-pending": cmd_render_pending, "status": cmd_status,
                "show": cmd_show, "approve": cmd_approve, "reject": cmd_reject,
                "publish-approved": cmd_publish_approved}
    return commands[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
