"""The official image lane: posts that need an official publicity image go out with no staff.

A Claude session writes a spec; GitHub Actions (plain code, in this repo) fetches the image from an official
source, frames it around any faces, renders the cards and later publishes; a Claude reviewer run approves.

    queue/pending/<slug>.json        spec, written by a Claude session          (schema: config/spec.schema.json)
    queue/rendered/<slug>/           01.jpg, 02.jpg ..., story.jpg, spec.json, render_report.json   (render-pending)
    queue/approved/<slug>.json       the blind reviewer's score                 (lane.py approve, by Claude)
    queue/posted/<slug>/             the rendered files + approved.json + result.json    (publish-approved)
    queue/rejected/<slug>/           spec.json + reasons.json (+ render_report.json)

    python3 pipeline/lane.py validate [FILE ...]            # check pending specs (all, or the files given)
    python3 pipeline/lane.py render-pending [--push]        # GitHub Actions, every 10 min
    python3 pipeline/lane.py status                         # what is where, with ages
    python3 pipeline/lane.py show SLUG                      # blind review packet (no self score)
    python3 pipeline/lane.py approve SLUG --score-file F    # reviewer's 7-check score -> approved/ (or rejected/)
    python3 pipeline/lane.py reject SLUG --reason TEXT      # reviewer (or anyone) rejects an item
    python3 pipeline/lane.py publish-approved [--push] [--dry-run]   # GitHub Actions, every 10 min (feed + reels)

Reels (queue/reels/): a run asks for a silent 9:16 Reel of an already-posted post; Actions renders it, a blind
reviewer approves it through the same gate, and publish-approved posts it.
    queue/reels/pending/reel-<name>.json   request: source (lane:<slug> or posts/<date>/<folder>), caption, score
    queue/reels/rendered/reel-<name>/      reel.mp4, reel_cover.jpg, preview_*.jpg, request.json, render_report.json
    queue/reels/approved|posted|rejected/  as for feed posts
    python3 pipeline/lane.py request-reel --source lane:<slug> --caption-file F --score-file F [--details 1,2]
    python3 pipeline/lane.py render-reels [--push]           # GitHub Actions (needs ffmpeg and Chrome)
    show / approve / reject take reel-<name> slugs too.

The gate: published only if the LOWER of the self score and the reviewer's score is >= 12/14, and only while
fresh (created_at under 8 hours ago, unless the spec says "evergreen": true). One post per account per run.
Stories: render-pending also makes story.jpg (cardkit.vertical, framed with pipeline.framing.VERTICAL) unless the
spec says "story": false; publish-approved posts it right after the feed post. Stories and reels are posted only
while config/formats.json turns them on ({"stories": true, "reels": true}); missing or false means paused. A story that can't be framed,
rendered or published is logged and skipped; it never holds up or changes the feed post.
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
from pipeline.common import (REPO, REPORTS_DIR, entry_type, load_json, load_posted, log, now_ist, now_utc,
                             parse_time, posted_story_ids, public_url, save_json, token_env)

QUEUE = Path(os.environ.get("IDLY_QUEUE_DIR") or REPO / "queue")
MIN_GAP = timedelta(minutes=30)      # never two posts on one account within 30 minutes
REPORTS = REPORTS_DIR
SCHEMA_FILE = REPO / "config" / "spec.schema.json"
STAGES = ("pending", "rendered", "approved", "rejected", "posted")
FRESH_HOURS = 8
LANE_SLOT = "lane"
FUTURE_SKEW = timedelta(minutes=15)
REEL_PREFIX = "reel-"
REEL_SCHEMA_FILE = REPO / "config" / "reel.schema.json"


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


def rqdir(stage: str) -> Path:
    """queue/reels/<stage>."""
    path = QUEUE / "reels" / stage
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_reel(slug: str) -> bool:
    return slug.startswith(REEL_PREFIX)


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

def schema_errors(spec, schema_file: Path = SCHEMA_FILE) -> list[str]:
    import jsonschema

    schema = json.loads(Path(schema_file).read_text(encoding="utf-8"))
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
    dest = (rqdir if is_reel(slug) else qdir)("rejected") / slug
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
    kind = "reel " if is_reel(slug) else ""
    report_line(f"rejected ({stage}) · {kind}{who}{slug} · " + "; ".join(reasons))


# ---- render-pending -------------------------------------------------------------------------------------

def render_with_cardkit(posts: list[dict], out_dir: Path, png_dir: Path, report: list) -> list[str]:
    from cardkit.render import render_cards

    return render_cards(posts, str(out_dir), template="hype", png_dir=str(png_dir), report=report)


RENDERER = render_with_cardkit       # tests swap this for a stub when Chrome isn't available


def render_story_with_cardkit(post: dict, out_jpg: Path, report: list) -> str:
    from cardkit.vertical import render_story

    return render_story(post, str(out_jpg), report=report, verbose=False)


STORY_RENDERER = render_story_with_cardkit      # tests swap this too


def story_problems(rows: list) -> list[str]:
    from cardkit.vertical import vertical_problems

    return vertical_problems(rows)


def make_story(spec: dict, im, plan, post: dict, work: Path) -> tuple[Path | None, dict]:
    """story.jpg for a lane post: the same photo, re-planned for the 9:16 photo window (faces kept clear of the
    logo and the text, never letterboxed), the same headline and credit. (None, why) when it can't be made."""
    if spec.get("story") is False:
        return None, {"status": "off", "reasons": ["the spec says \"story\": false"]}
    try:
        faces = framing.faces_from_plan(plan) if plan.notes else None      # detected once, for the cover
        vplan = framing.plan_image(im, faces=faces, frame=framing.VERTICAL)
        if vplan.upscale > framing.MAX_UPSCALE + 1e-6:
            raise framing.FramingError([f"{vplan.upscale:.2f}x upscale (max {framing.MAX_UPSCALE}x)"])
        vphoto, vfocal, vzoom = framing.render_input(im, vplan, work / "vertical")
        vpost = json.loads(json.dumps(post, default=str))
        vpost["slides"][0]["vertical"] = {"photo": str(vphoto), "focal": list(vfocal), "zoom": vzoom,
                                          "photo_h": vplan.out_h}
        rows: list = []
        path = Path(STORY_RENDERER(vpost, work / "story.jpg", rows))
        problems = story_problems(rows)
        if not problems:
            publish.check_story_jpeg(path)
    except framing.FramingError as e:
        return None, {"status": "skipped", "reasons": [f"framing: {r}" for r in e.reasons]}
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        return None, {"status": "skipped", "reasons": [f"render: {e}"]}
    info = {"status": "rendered", "framing": vplan.to_dict(), "upscale": round(vplan.upscale, 3),
            "checks": [{k: v for k, v in r.items() if k not in ("boxes",)} for r in rows]}
    if problems:
        return None, {**info, "status": "skipped", "reasons": problems}
    return path, info


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
        # Try the image attempts in order; an image that resolves but can't be framed falls through to the
        # next attempt (e.g. a wide banner with a face at its edge, then the trailer still).
        remaining = official_image.attempts_of(spec["image"])
        unusable: list[str] = []
        tried: list = []
        while True:
            if not remaining:
                raise LaneReject(unusable, "framing")
            image = {**remaining[0], "fallback": remaining[1:]} if len(remaining) > 1 else dict(remaining[0])
            order = official_image.attempts_of(image)
            try:
                res, t = official_image.resolve_first(image, spec)
            except official_image.ResolveError as e:
                if unusable:
                    raise LaneReject(unusable + [e.reason], "framing")
                if e.transient:
                    report_line(f"waiting · @{account} {slug} · image source not reachable, will retry: {e.reason}")
                    return "retry", e.reason
                raise LaneReject(e.reason, "resolve")
            tried += t
            remaining = order[len(t):]
            try:
                im = official_image.open_image(res.data)
            except official_image.ResolveError as e:
                unusable.append(f"{res.resolver}: {e.reason}")
                continue
            plan = res.extra.get("plan")
            if plan is None:
                try:
                    plan = framing.plan_image(im)
                except framing.FramingError as e:
                    unusable += [f"framing ({res.resolver} {res.source_url}): {r}" for r in e.reasons]
                    continue
            if plan.upscale > framing.MAX_UPSCALE + 1e-6:
                unusable.append(f"framing ({res.resolver}): {plan.upscale:.2f}x upscale (max {framing.MAX_UPSCALE}x)")
                continue
            break
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
            story_jpg, story_info = make_story(spec, im, plan, post, work)   # never rejects the post itself

            staging = qdir("rendered") / f".{slug}.tmp"
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir()
            files = []
            for i, jpg in enumerate(jpgs, 1):
                shutil.copyfile(jpg, staging / f"{i:02d}.jpg")
                files.append(f"{i:02d}.jpg")
            if story_jpg:
                shutil.copyfile(story_jpg, staging / "story.jpg")
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
                "files": files, "caption_final": caption,
                "story": {**story_info, "file": "story.jpg" if story_jpg else None}})
            os.replace(staging, qdir("rendered") / slug)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        path.unlink()
        story_note = "story ready" if story_jpg else f"no story ({'; '.join(story_info.get('reasons') or [])[:160]})"
        msg = (f"{res.resolver} ({res.organisation}) · {plan.mode} · {len(plan.faces_src)} face(s) · "
               f"upscale {plan.upscale:.2f}x · {len(files)} slide(s) · {story_note}")
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
    base = rqdir if is_reel(slug) else qdir
    for stage in ("approved", "rendered", "pending"):
        p = base(stage) / (f"{slug}.json" if stage in ("approved", "pending") else slug)
        if p.exists():
            return stage, p
    return None


def cmd_show(a) -> int:
    if is_reel(a.slug):
        return show_reel(a.slug)
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
        "story": rel_to_repo(rdir / "story.jpg") if (rdir / "story.jpg").exists() else None,
        "story_note": ((rep or {}).get("story") or {}).get("reasons"),
        "note": ("Blind packet: the self score is left out on purpose. Score the 7 checks yourself. Look at the "
                 "story too; approve with --no-story to post the feed post without it."),
    }
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


def cmd_approve(a) -> int:
    rdir = (rqdir if is_reel(a.slug) else qdir)("rendered") / a.slug
    spec = load_json(rdir / ("request.json" if is_reel(a.slug) else "spec.json"))
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
    save_json((rqdir if is_reel(a.slug) else qdir)("approved") / f"{a.slug}.json", {
        "slug": a.slug, "reviewer": score, "reviewed_at": now_utc().isoformat(timespec="seconds"),
        "reviewed_by": a.by, "notes": a.notes or "", **({"story": False} if a.no_story else {})})
    kind = "reel " if is_reel(a.slug) else ""
    report_line(f"approved · {kind}@{spec['account']} {a.slug} · self {mine}, reviewer {theirs} -> "
                f"{min(mine, theirs)}/14")
    print(f"approved: {min(mine, theirs)}/14 (publish-approved posts it on its next run)")
    return 0


def cmd_reject(a) -> int:
    found = find_item(a.slug)
    if not found:
        log(f"no pending, rendered or approved item {a.slug!r}")
        return 2
    stage, path = found
    rdir = (rqdir if is_reel(a.slug) else qdir)("rendered") / a.slug
    spec = load_json(rdir / ("request.json" if is_reel(a.slug) else "spec.json")) or \
        (load_json(path) if stage == "pending" else None)
    if stage == "approved":
        path.unlink()
        path = rdir if rdir.exists() else None
    reject_item(a.slug, "review", [a.reason], spec, src=path)
    return 0


def cmd_status(a) -> int:
    for label, base in (("", qdir), ("reels/", rqdir)):
        _status(label, base)
    return 0


def _status(label: str, base) -> None:
    for stage in STAGES:
        items = sorted(p for p in base(stage).iterdir() if not p.name.startswith("."))
        print(f"{label}{stage}: {len(items)}")
        for p in items[-15:]:
            name = "request.json" if label else "spec.json"
            spec = load_json(p) if p.suffix == ".json" and stage == "pending" else load_json(p / name) \
                if p.is_dir() else None
            extra = ""
            if spec and spec.get("created_at"):
                extra = f"  @{spec.get('account')}  {age_hours(spec):.1f}h old"
            if stage == "rejected" and p.is_dir():
                why = (load_json(p / "reasons.json") or {}).get("reasons") or []
                extra += f"  ({'; '.join(why)[:140]})"
            print(f"  {p.stem if p.suffix == '.json' else p.name}{extra}")


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
    prior = next((p for p in load_posted() if p.get("lane_slug") == slug and entry_type(p) == "feed"), None)
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
                if p.get("account") == account and p.get("posted_at") and entry_type(p) != "story"), default=None)
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
        dry_run=dry_run, idly_article=spec["idly_article"], tags=spec.get("tags"),
        record_extra={"lane": "official-image", "lane_slug": slug, "image_credit": spec.get("image_credit"),
                      "image_source": (spec.get("lane") or {}).get("source_url"), "archived_images": archived,
                      "score_self": editorial.score_total(spec["scores"]["self"]),
                      "score_reviewer": editorial.score_total(approval.get("reviewer"))})
    story = publish_lane_story(slug, rdir, spec, approval, res, dry_run)
    if dry_run:
        return "dry-run", f"would post {len(urls)} image(s) to @{account}" + (
            " and its story" if story.get("status") == "dry-run" else "")
    res = {**res, "story": {k: story.get(k) for k in ("status", "media_id", "permalink", "reason") if story.get(k)}}
    finish_posted(slug, approval, res)
    busy.add(account)
    report_line(f"posted · @{account} {slug} · {editorial.score_total(low)}/14 · {res.get('permalink', '')}")
    return "posted", res.get("permalink", "")


def publish_lane_story(slug: str, rdir: Path, spec: dict, approval: dict, feed: dict, dry_run: bool) -> dict:
    """Post the item's story.jpg right after its feed post (still at queue/rendered/<slug>/, which is public until
    this run pushes the move to posted/). Never raises: a failed story is logged and the feed post stands."""
    path = rdir / "story.jpg"
    account = spec["account"]
    if not path.exists():
        return {"status": "none"}
    if spec.get("story") is False or approval.get("story") is False:
        return {"status": "off"}
    if not publish.format_enabled("stories"):
        (log if dry_run else report_line)("stories paused (config/formats.json)")
        return {"status": "paused"}
    url = public_url(rel_to_repo(path))
    try:
        publish.check_story_jpeg(path)
        if not dry_run:
            from pipeline.run_day import url_ready
            ok, why = url_ready(url, path.stat().st_size)
            if not ok:
                raise publish.IGError(f"story image not public ({why}): {url}")
        res = publish.publish_story(account, url, dry_run=dry_run,
                                    story_of=feed.get("media_id"), date=now_ist().date().isoformat(),
                                    slot=LANE_SLOT, record_extra={"lane": "official-image", "story_of_slug": slug},
                                    wait=False)
        if not dry_run:
            report_line(f"story · @{account} {slug} · {res.get('permalink') or res.get('media_id')}")
        return res
    except Exception as e:  # noqa: BLE001 - a story is an extra; the feed post is already up
        report_line(f"story failed · @{account} {slug} · {e} (the feed post is up; no story this time)")
        return {"status": "failed", "reason": str(e)[:300]}


def cmd_publish_approved(a) -> int:
    with queue_lock() as got:
        if not got:
            return 0
        approved = sorted(p.stem for p in qdir("approved").glob("*.json"))
        if not approved and not any(rqdir("approved").glob("*.json")):
            log("publish-approved: nothing approved")
            return 0
        if not approved and not publish.format_enabled("reels"):
            (log if a.dry_run else report_line)("reels paused (config/formats.json)")
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
        reels = sorted(p.stem for p in rqdir("approved").glob("*.json"))
        if reels and not publish.format_enabled("reels"):
            (log if a.dry_run else report_line)("reels paused (config/formats.json)")
            reels = []                                    # they wait in queue/reels/approved until Rahul turns them on
        for slug in reels:
            log(f"{slug}:")
            req = load_json(rqdir("rendered") / slug / "request.json")
            try:
                status, msg = publish_reel_one(slug, dry_run=a.dry_run, allow_shared=a.allow_shared_token, busy=busy)
            except (LaneReject, publish.GateRefused) as e:
                (rqdir("approved") / f"{slug}.json").unlink(missing_ok=True)
                reasons = e.reasons if isinstance(e, LaneReject) else [str(e)]
                reject_item(slug, getattr(e, "stage", "publish"), reasons, req, src=rqdir("rendered") / slug)
                status, msg = "rejected", str(e)
            except (publish.IGError, ValueError) as e:
                status, msg = "failed", str(e)
                failed += 1
                report_line(f"failed · reel {slug} · {e} (kept in reels/approved; retried next run while fresh)")
            counts[status] = counts.get(status, 0) + 1
            log(f"  {status}: {msg}")
            if a.push and status in ("posted", "rejected"):
                if not gitsync.commit_and_push(["queue", "state", "reports"], f"lane: reel {status} {slug}"):
                    return 1
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        log(f"publish-approved: {summary}")
        if a.push and not gitsync.commit_and_push(["queue", "state", "reports"], f"lane: publish-approved ({summary})"):
            return 1
        return 1 if failed else 0


# ---- reels: request -> render-reels -> review -> publish ----------------------------------------------------------

def render_reel_with_cardkit(post: dict, out_dir: Path, details, report: list) -> dict:
    from cardkit.reel import render_reel

    return render_reel(post, str(out_dir), details=details, report=report, verbose=False)


REEL_RENDERER = render_reel_with_cardkit        # tests swap this for a stub (no Chrome or ffmpeg needed)


def feed_entry_for_folder(account: str, folder: str) -> dict | None:
    """The feed post on @account whose images are in posts/<date>/<folder>/."""
    prefix = public_url(folder.rstrip("/")) + "/"
    hits = [p for p in load_posted() if entry_type(p) == "feed" and p.get("account") == account
            and any(str(u).startswith(prefix) for u in p.get("images") or [])]
    return hits[-1] if hits else None


def reel_already(source: str) -> dict | None:
    return next((p for p in load_posted() if entry_type(p) == "reel" and p.get("reel_source") == source), None)


def describe_source(source: str) -> dict:
    """What a reel source points at: {kind, account, idly_article, story_id, reel_of, headline, details, problem}."""
    if source.startswith("lane:"):
        src = source[5:]
        spec = load_json(qdir("posted") / src / "spec.json")
        if not spec:
            return {"problem": f"{source}: no posted lane item queue/posted/{src}/ (reels are made from posted posts)"}
        result = load_json(qdir("posted") / src / "result.json") or {}
        out = {"kind": "lane", "account": spec["account"], "idly_article": spec["idly_article"],
               "story_id": spec.get("story_id"), "reel_of": result.get("media_id"), "headline": spec.get("headline"),
               "details": len(spec.get("detail_slides") or []), "credit": spec.get("image_credit")}
        if (spec.get("lane") or {}).get("source") == "prebuilt" or not spec.get("image"):
            out["problem"] = (f"{source} was a prebuilt post (no source image to re-frame): request the reel from "
                              f"its posts/ folder with a post.json instead")
        return out
    folder = REPO / source
    post = load_json(folder / "post.json")
    if not post:
        return {"problem": f"{source}/post.json is missing: save the hype post dict there (photo committed in the "
                           f"repo) to make a reel of it"}
    account = post.get("acct")
    caption = (folder / "caption.txt").read_text(encoding="utf-8") if (folder / "caption.txt").exists() else ""
    feed = feed_entry_for_folder(account, source) or {}
    slides = post.get("slides") or []
    out = {"kind": "posts", "account": account, "idly_article": post.get("idly_article", editorial.LINK_LINE in caption
                                                                          if caption else True),
           "story_id": feed.get("story_id"), "reel_of": feed.get("media_id"),
           "headline": (slides[0] if slides else post).get("headline"),
           "details": sum(1 for x in slides[1:] if x.get("type", "cover") == "detail"),
           "credit": (slides[0] if slides else post).get("photo_credit")}
    if not feed:
        out["problem"] = f"{source} has no feed post in state/posted.json (reels are made from posted posts)"
    return out


def validate_reel_request(req, slug: str) -> list[str]:
    if not isinstance(req, dict):
        return ["the request must be a JSON object"]
    errs = schema_errors(req, REEL_SCHEMA_FILE)
    if not (is_reel(slug) and official_image_slug_ok(slug)):
        errs.append(f"file name {slug!r}: use reel- plus lowercase letters, digits and hyphens (3-80 characters)")
    if req.get("slug") and req["slug"] != slug:
        errs.append(f"slug {req['slug']!r} does not match the file name {slug!r}")
    if errs:
        return errs
    self_score = req["scores"]["self"]
    errs += [f"scores.self: {p}" for p in editorial.score_problems(self_score)]
    if not errs and editorial.score_total(self_score) < editorial.GATE:
        errs.append(f"self score {editorial.score_total(self_score)}/14 is below the {editorial.GATE} gate")
    try:
        if parse_time(req["created_at"]) - now_utc() > FUTURE_SKEW:
            errs.append("created_at is in the future")
    except ValueError:
        errs.append(f"created_at is not a date-time: {req['created_at']!r}")
    src = describe_source(req["source"])
    if src.get("problem"):
        errs.append(src["problem"])
    elif src.get("account") != req["account"]:
        errs.append(f"{req['source']} is @{src.get('account')}'s post, not @{req['account']}'s")
    if not src.get("problem") and any(n > src.get("details", 0) for n in req.get("details") or []):
        errs.append(f"details {req['details']}: {req['source']} has {src.get('details', 0)} detail slide(s)")
    if reel_already(req["source"]):
        errs.append(f"{req['source']} already has a reel")
    if src.get("credit"):                     # the same caption rules as feed posts, with the post's own credit
        cap_errs, _ = editorial.post_problems(editorial.with_credit(req["caption"], src["credit"]),
                                              self_score, idly_article=req["idly_article"])
        errs += [f"caption: {e}" for e in cap_errs]
    return errs


def reel_post_from_lane(src_slug: str, slug: str, work: Path) -> tuple[dict, str, dict]:
    """(post dict with a vertical plan, image credit, render info) for a posted lane item: the official image is
    fetched again (Actions only: it may show people) and must be the very image the feed post used."""
    spec = load_json(qdir("posted") / src_slug / "spec.json")
    lane_info = spec.get("lane") or {}
    attempts = official_image.attempts_of(spec["image"])
    attempts.sort(key=lambda t: t.get("resolver") != lane_info.get("resolver"))     # the one that worked first
    image = {**attempts[0], "fallback": attempts[1:]} if len(attempts) > 1 else dict(attempts[0])
    try:
        res, _ = official_image.resolve_first(image, spec)
    except official_image.ResolveError as e:
        if e.transient:
            raise
        raise LaneReject(f"image: {e.reason}", "resolve")
    if lane_info.get("image_url") and res.image_url != lane_info["image_url"]:
        raise LaneReject(f"the official image changed since the feed post ({res.image_url} is not "
                         f"{lane_info['image_url']}): the reel must show the same photo", "resolve")
    try:
        im = official_image.open_image(res.data)
    except official_image.ResolveError as e:
        raise LaneReject(f"image: {e.reason}", "resolve")
    credit = spec.get("image_credit") or res.credit
    post, info = vertical_post(build_post(spec, slug, Path("unused"), (0.5, 0.5), 1.0, credit), im, work)
    return post, credit, {**info, "image_url": res.image_url, "resolver": res.resolver}


def reel_post_from_folder(source: str, slug: str, work: Path) -> tuple[dict, str, dict]:
    """(post dict with a vertical plan, image credit, render info) from posts/<date>/<folder>/post.json."""
    post = load_json(REPO / source / "post.json")
    post = {**post, "slides": [dict(x) for x in post.get("slides") or []]} if post.get("slides") else {
        "acct": post.get("acct"), "slides": [{"type": "cover", **{k: post.get(k) for k in (
            "headline", "photo", "photo_credit", "focal", "zoom")}}], "sources": post.get("sources")}
    cover = post["slides"][0]
    photo = (REPO / cover["photo"]).resolve() if not Path(cover["photo"]).is_absolute() else Path(cover["photo"])
    if not str(photo).startswith(str(REPO.resolve()) + "/") or not photo.is_file():
        raise LaneReject(f"post.json: the photo {cover['photo']} must be a committed file in the repo", "validate")
    credit = str(cover.get("photo_credit") or "").strip()
    if not credit:
        raise LaneReject("post.json: the cover has no photo_credit", "validate")
    try:
        im = official_image.open_image(photo.read_bytes())
    except official_image.ResolveError as e:
        raise LaneReject(f"photo: {e.reason}", "validate")
    post.update(slug=slug)
    post, info = vertical_post(post, im, work)
    return post, credit, info


def vertical_post(post: dict, im, work: Path) -> tuple[dict, dict]:
    """Plan the 9:16 photo window (faces detected here, in Actions) and put it on the cover slide."""
    try:
        vplan = framing.plan_image(im, frame=framing.VERTICAL)
    except framing.FramingError as e:
        raise LaneReject([f"framing: {r}" for r in e.reasons], "framing")
    if vplan.upscale > framing.MAX_UPSCALE + 1e-6:
        raise LaneReject(f"framing: {vplan.upscale:.2f}x upscale (max {framing.MAX_UPSCALE}x)", "framing")
    vphoto, vfocal, vzoom = framing.render_input(im, vplan, work / "vertical")
    post = json.loads(json.dumps(post, default=str))
    post["slides"][0].update(photo=str(vphoto), focal=list(vfocal), zoom=vzoom,
                             vertical={"photo": str(vphoto), "focal": list(vfocal), "zoom": vzoom,
                                       "photo_h": vplan.out_h})
    post["date"] = card_date()
    return post, {"framing": vplan.to_dict(), "faces": vplan.faces_src, "upscale": round(vplan.upscale, 3)}


def render_reel_one(path: Path) -> tuple[str, str]:
    """Render one reel request. Returns (status, message): rendered | rejected | retry | skipped."""
    slug = path.stem
    try:
        req = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        reject_item(slug, "validate", [f"not valid JSON: {e}"], src=path)
        return "rejected", "invalid JSON"
    digest = spec_hash(req) if isinstance(req, dict) else ""
    for stage in ("rendered", "posted"):
        existing = rqdir(stage) / slug
        if existing.exists():
            old = load_json(existing / "request.json") or {}
            if (old.get("lane") or {}).get("request_sha256") == digest:
                path.unlink()
                return "skipped", f"already {stage}"
            reject_item(slug, "validate", [f"slug {slug!r} is already used by a {stage} reel: use a new file name"],
                        req if isinstance(req, dict) else None, src=path)
            return "rejected", "slug in use"
    errs = validate_reel_request(req, slug)
    if errs:
        reject_item(slug, "validate", errs, req if isinstance(req, dict) else None, src=path)
        return "rejected", "; ".join(errs)
    if (rqdir("rejected") / slug).exists():
        shutil.rmtree(rqdir("rejected") / slug)
    account, source = req["account"], req["source"]
    src = describe_source(source)
    work = Path(tempfile.mkdtemp(prefix=f"reel-{slug}-"))
    try:
        if stale(req):
            raise LaneReject(f"stale: requested {age_hours(req):.1f}h ago (limit {FRESH_HOURS}h)")
        try:
            if source.startswith("lane:"):
                post, credit, info = reel_post_from_lane(source[5:], slug, work)
            else:
                post, credit, info = reel_post_from_folder(source, slug, work)
        except official_image.ResolveError as e:
            report_line(f"waiting · reel @{account} {slug} · image source not reachable, will retry: {e.reason}")
            return "retry", e.reason
        caption = editorial.with_credit(req["caption"], credit)
        cap_errs, cap_warns = editorial.post_problems(caption, req["scores"]["self"], idly_article=req["idly_article"])
        if cap_errs:
            raise LaneReject([f"caption: {e}" for e in cap_errs], "caption")
        rows: list = []
        try:
            out = REEL_RENDERER(post, work / "out", req.get("details"), rows)
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            raise LaneReject(f"render: {e}", "render")
        if out.get("problems"):
            raise LaneReject(out["problems"], "render")
        video = Path(out["video"])
        try:
            publish.check_reel_mp4(video)
            publish.check_story_jpeg(Path(out["cover"]))
        except ValueError as e:
            raise LaneReject(str(e), "render")
        staging = rqdir("rendered") / f".{slug}.tmp"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        files = []
        for f in [out["video"], out["cover"], *out.get("previews", [])]:
            shutil.copyfile(f, staging / Path(f).name)
            files.append(Path(f).name)
        rendered_at = now_utc().isoformat(timespec="seconds")
        save_json(staging / "request.json", {
            **req, "slug": slug, "caption_final": caption, "image_credit": credit, "story_id": src.get("story_id"),
            "reel_of": src.get("reel_of"), "headline": src.get("headline"),
            "lane": {"request_sha256": digest, "rendered_at": rendered_at}})
        probe = next((r for r in rows if r.get("type") == "reel"), {})
        save_json(staging / "render_report.json", {
            "slug": slug, "account": account, "source": source, "rendered_at": rendered_at, **info,
            "duration": out.get("duration"), "frames": out.get("frames"), "files": files, "caption_final": caption,
            "checks": {"caption_warnings": cap_warns, "problems": []},
            "pages": [{k: v for k, v in r.items() if k not in ("boxes",)} for r in rows if r.get("type") != "reel"],
            "video": {k: v for k, v in probe.items() if k not in ("path",)}})
        os.replace(staging, rqdir("rendered") / slug)
        path.unlink()
        msg = f"{source} · {out.get('duration', 0):.1f}s · {len(post['slides'][1:])} slide(s) available"
        report_line(f"rendered · reel @{account} {slug} · {msg} · awaiting review")
        return "rendered", msg
    except LaneReject as e:
        reject_item(slug, e.stage, e.reasons, req, src=path)
        return "rejected", str(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def cmd_render_reels(a) -> int:
    with queue_lock() as got:
        if not got:
            return 0
        reqs = sorted(rqdir("pending").glob("*.json"))[: a.limit or None]
        if not reqs:
            log("render-reels: queue/reels/pending is empty")
            return 0
        counts, crashed = {}, 0
        for path in reqs:
            log(f"{path.stem}:")
            try:
                status, msg = render_reel_one(path)
            except Exception as e:  # noqa: BLE001 - infrastructure trouble: keep the request, go red, retry later
                status, msg = "retry", f"{type(e).__name__}: {e}"
                crashed += 1
                report_line(f"error · {path.stem} · {msg} (kept in reels/pending, will retry)")
            counts[status] = counts.get(status, 0) + 1
            log(f"  {status}: {msg}")
        summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        log(f"render-reels: {summary}")
        if a.push and not gitsync.commit_and_push(["queue", "reports"], f"lane: render-reels ({summary})"):
            return 1
        return 1 if crashed else 0


def show_reel(slug: str) -> int:
    rdir = rqdir("rendered") / slug
    req, rep = load_json(rdir / "request.json"), load_json(rdir / "render_report.json") or {}
    if not req:
        log(f"no rendered reel {slug!r}")
        return 2
    packet = {
        "slug": slug, "account": req["account"], "source": req["source"], "headline": req.get("headline"),
        "story_id": req.get("story_id"), "idly_article": req["idly_article"], "caption_final": req["caption_final"],
        "image_credit": req["image_credit"], "details": req.get("details"), "share_to_feed": req.get("share_to_feed", True),
        "duration": rep.get("duration"), "framing": rep.get("framing"), "faces": len(rep.get("faces") or []),
        "created_at": req["created_at"], "age_hours": round(age_hours(req), 1),
        "files": [rel_to_repo(rdir / f) for f in rep.get("files", [])],
        "note": ("Blind packet: the self score is left out on purpose. Open reel_cover.jpg and every preview still "
                 "(0.5 s, 4 s, 7 s, last frame), check the layout, the photo and the caption, and score the 7 checks."),
    }
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


def finish_reel_posted(slug: str, approval: dict, result: dict) -> None:
    rdir, dest = rqdir("rendered") / slug, rqdir("posted") / slug
    if rdir.exists() and not dest.exists():
        os.replace(rdir, dest)
    save_json(dest / "approved.json", approval)
    save_json(dest / "result.json", result)
    (rqdir("approved") / f"{slug}.json").unlink(missing_ok=True)


def publish_reel_one(slug: str, *, dry_run: bool, allow_shared: bool, busy: set) -> tuple[str, str]:
    """Returns (status, message): posted | dry-run | rejected | skipped | waiting | failed."""
    apath = rqdir("approved") / f"{slug}.json"
    approval = load_json(apath) or {}
    rdir = rqdir("rendered") / slug
    req = load_json(rdir / "request.json")
    if (rqdir("posted") / slug).exists():
        apath.unlink(missing_ok=True)
        return "skipped", "already posted"
    if not req:
        apath.unlink(missing_ok=True)
        reject_item(slug, "publish", ["approved, but there is no rendered reel"], extra={"approval": approval})
        return "rejected", "no rendered reel"
    account = req["account"]
    prior = next((p for p in load_posted() if p.get("reel_slug") == slug and entry_type(p) == "reel"), None)
    if prior:
        finish_reel_posted(slug, approval, {**prior, "status": "posted", "recovered": True})
        report_line(f"posted reel (recovered record) · @{account} {slug} · {prior.get('permalink', '')}")
        return "posted", "recovered"
    problems = editorial.score_problems(req["scores"]["self"]) + \
        [f"reviewer: {p}" for p in editorial.score_problems(approval.get("reviewer"))]
    if problems:
        raise LaneReject(problems, "publish")
    low = lower_score(req, approval)
    if editorial.score_total(low) < editorial.GATE:
        raise LaneReject(f"lower score {editorial.score_total(low)}/14 is below the {editorial.GATE} gate", "publish")
    if stale(req):
        raise LaneReject(f"stale: requested {age_hours(req):.1f}h ago (limit {FRESH_HOURS}h)", "publish")
    if reel_already(req["source"]):
        raise LaneReject(f"{req['source']} already has a reel", "publish")
    if account in busy:
        return "waiting", f"@{account} already posted in this run; next run"
    last = max((parse_time(p["posted_at"]) for p in load_posted()
                if p.get("account") == account and p.get("posted_at") and entry_type(p) != "story"), default=None)
    if last is not None and now_utc() - last < MIN_GAP:
        return "waiting", f"@{account} posted {int((now_utc() - last).total_seconds() // 60)} min ago (min gap {MIN_GAP})"
    if not dry_run and not publish.account_token(account) and not allow_shared:
        report_line(f"skipped · reel @{account} {slug} · the {token_env(account)} secret is not set "
                    f"(docs/SETUP-GITHUB-SECRETS.md); it posts once it is, if still fresh")
        return "skipped", f"{token_env(account)} not set"
    video, cover = rdir / "reel.mp4", rdir / "reel_cover.jpg"
    try:
        publish.check_reel_mp4(video)
        publish.check_story_jpeg(cover)
    except ValueError as e:
        raise LaneReject(str(e), "publish")
    video_url, cover_url = public_url(rel_to_repo(video)), public_url(rel_to_repo(cover))
    caption = req["caption_final"]
    if not dry_run:
        from pipeline.run_day import url_ready
        for f, url, types in ((video, video_url, publish.VIDEO_TYPES), (cover, cover_url, ("image/jpeg",))):
            ok, why = url_ready(url, f.stat().st_size, content_types=types)
            if not ok:
                return "waiting", f"not public yet ({why}): {url}"
        client, ig_id = publish.connect(account)          # duplicate guard: is this reel already on the account?
        media_id = client.find_recent_reel(ig_id, caption)
        if media_id:
            result = {"status": "posted", "media_id": media_id, "permalink": client.permalink(media_id),
                      "recovered": True, "note": "found on Instagram already; not posted again"}
            finish_reel_posted(slug, approval, result)
            report_line(f"posted reel (found on Instagram) · @{account} {slug} · {result['permalink']}")
            return "posted", "recovered from Instagram"
    # in the repo (GitHub Actions): pass the committed path, so the jsDelivr and resumable fallbacks can work
    in_repo = (REPO / rel_to_repo(video)).resolve() == video.resolve()
    res = publish.publish_reel(
        account, rel_to_repo(video) if in_repo else video_url, caption, score=low, alt_text=req.get("alt_text", ""),
        share_to_feed=req.get("share_to_feed", True), dry_run=dry_run,
        cover=rel_to_repo(cover) if in_repo else cover_url, story_id=req.get("story_id"),
        idly_article=req["idly_article"], date=now_ist().date().isoformat(), slot=LANE_SLOT, wait=False,
        record_extra={"lane": "reel", "reel_slug": slug, "reel_source": req["source"], "reel_of": req.get("reel_of"),
                      "image_credit": req.get("image_credit"),
                      "score_self": editorial.score_total(req["scores"]["self"]),
                      "score_reviewer": editorial.score_total(approval.get("reviewer"))})
    if dry_run:
        return "dry-run", f"would post the reel {slug} to @{account}"
    finish_reel_posted(slug, approval, res)
    busy.add(account)
    report_line(f"posted reel · @{account} {slug} · {editorial.score_total(low)}/14 · via {res.get('video_host')} · "
                f"{res.get('permalink', '')}")
    return "posted", res.get("permalink", "")


def without_credit(caption: str) -> str:
    """The caption minus any trailing credit line(s): the lane appends the post's exact credit itself."""
    lines = (caption or "").rstrip().splitlines()
    while lines and (not lines[-1].strip() or editorial.CREDIT_LINE.match(lines[-1].strip())):
        lines.pop()
    return "\n".join(lines).rstrip()


def cmd_request_reel(a) -> int:
    """Write queue/reels/pending/<slug>.json for an already-posted post (hourly or daily runs)."""
    src = describe_source(a.source)
    if src.get("problem"):
        log(src["problem"])
        return 2
    try:
        score = json.loads(Path(a.score_file).read_text(encoding="utf-8"))
        caption = Path(a.caption_file).read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as e:
        log(f"can't read the caption or score file: {e}")
        return 2
    import re
    name = a.source[5:] if a.source.startswith("lane:") else Path(a.source).name
    slug = a.slug or (REEL_PREFIX + re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-"))[:80].rstrip("-")
    req = {"source": a.source, "account": a.account or src["account"], "story_id": src.get("story_id"),
           "idly_article": src["idly_article"] if a.idly_article is None else a.idly_article,
           "caption": without_credit(caption),
           "scores": {"self": score}, "created_at": now_utc().isoformat(timespec="seconds")}
    if a.details:
        req["details"] = [int(x) for x in a.details.split(",")]
    if a.alt_text:
        req["alt_text"] = a.alt_text
    if a.no_share_to_feed:
        req["share_to_feed"] = False
    if a.evergreen:
        req["evergreen"] = True
    errs = validate_reel_request(req, slug)
    if errs:
        print("PROBLEMS:\n" + "\n".join(f"  - {e}" for e in errs))
        return 1
    path = rqdir("pending") / f"{slug}.json"
    if path.exists() or (rqdir("rendered") / slug).exists() or (rqdir("posted") / slug).exists():
        print(f"{slug} is already queued: pass --slug with a new name")
        return 1
    save_json(path, req)
    print(f"queued {rel_to_repo(path)}\nnext: git add {rel_to_repo(path)} && git commit -m \"lane: reel {slug}\" && "
          f"git pull --rebase origin main && git push origin HEAD:main")
    return 0


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
    ok.add_argument("--no-story", action="store_true", help="post the feed post without its story")
    no = sub.add_parser("reject", help="reject a pending, rendered or approved item")
    no.add_argument("slug")
    no.add_argument("--reason", required=True)
    p = sub.add_parser("publish-approved", help="post every approved item (feed posts, then reels) that passes the gate")
    p.add_argument("--push", action="store_true", help="commit and push after each post (GitHub Actions)")
    p.add_argument("--dry-run", action="store_true", help="print the would-be API calls, post nothing")
    p.add_argument("--allow-shared-token", action="store_true",
                   help="use the shared token for accounts without IG_TOKEN_<ACCOUNT> (not in GitHub Actions)")
    rq = sub.add_parser("request-reel", help="ask for a 9:16 reel of an already-posted post")
    rq.add_argument("--source", required=True,
                    help="lane:<slug> (a posted lane item) or posts/<date>/<folder> (a posted post with post.json)")
    rq.add_argument("--caption-file", required=True, help="the reel caption (same rules; the credit is added)")
    rq.add_argument("--score-file", required=True, help="your 7-check score for the reel (>= 12)")
    rq.add_argument("--account", help="default: the source post's account")
    rq.add_argument("--details", help="which detail slides, 1-based, e.g. 1,2 (default: the first two)")
    rq.add_argument("--slug", help="default: reel-<source name>")
    rq.add_argument("--alt-text", default="")
    rq.add_argument("--no-share-to-feed", action="store_true", help="Reels tab only")
    rq.add_argument("--evergreen", action="store_true")
    rq.add_argument("--idly-article", dest="idly_article", action="store_true", default=None)
    rq.add_argument("--no-idly-article", dest="idly_article", action="store_false")
    rr = sub.add_parser("render-reels", help="render every reel request in queue/reels/pending (needs ffmpeg)")
    rr.add_argument("--push", action="store_true", help="commit and push queue/ and reports/ (GitHub Actions)")
    rr.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    commands = {"validate": cmd_validate, "render-pending": cmd_render_pending, "status": cmd_status,
                "show": cmd_show, "approve": cmd_approve, "reject": cmd_reject,
                "publish-approved": cmd_publish_approved, "request-reel": cmd_request_reel,
                "render-reels": cmd_render_reels}
    return commands[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
