"""End-to-end dry run on today's real idly data with STUB card copy.  Nothing is posted.

    python3 tests/dry_run_e2e.py

1. fetch real candidates      2. write a stub cards.json (top un-flagged story per account)
3. render (cardkit if present, else a plain PIL stand-in) and stage in _work/
4. publish --dry-run (prints the would-be API calls)      5. dry-run report
6. show the 12/14 gate refusing a below-gate post.
"""
import importlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from pipeline import editorial, fetch, publish, run_day  # noqa: E402
from pipeline.common import REPO, default_date, default_slot, save_json, work_dir  # noqa: E402


def words(text, n):
    return " ".join(re.sub(r"[?]", "", str(text)).split()[:n]).rstrip(",;:.")


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def stub_photo(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1600, 1200), (120, 124, 130))
    ImageDraw.Draw(im).text((560, 560), "STUB PHOTO", fill="white", font=font(72))
    im.save(path, "JPEG", quality=88)
    return path


def stub_renderer(cards, out_dir: Path):
    """Stand-in for cardkit: a plain 1080x1350 card with the copy on it (.png + .jpg)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for c in cards:
        im = Image.new("RGB", (1080, 1350), (241, 236, 226))
        d = ImageDraw.Draw(im)
        y = 90
        for text, size in [(c["tag"], 30), (c["stat"], 120), (c["stat_label"], 34), (c["headline"], 50),
                           *[("- " + b, 32) for b in c["bullets"]], (c["photo_credit"], 22),
                           (f"@{c['acct']} · {c['date']} · STUB CARD", 22)]:
            for line in re.findall(r".{1,34}(?:\s|$)", text) or [text]:
                d.text((84, y), line.strip(), fill=(22, 24, 28), font=font(size))
                y += int(size * 1.25)
            y += 24
        im.save(out_dir / f"{c['slug']}.png")
        im.save(out_dir / f"{c['slug']}.jpg", "JPEG", quality=90)
        out.append(out_dir / f"{c['slug']}.jpg")
    return out


def stub_post(c: dict, photo: Path) -> dict:
    stat = re.search(r"[₹$]?\d[\d,.]*\s?(crore|%|million|billion|lakh)?", " ".join([c["title"], c["dek"] or ""]))
    caption = (f"{words(c['dek'], 40)}.\n\nSTUB caption for the dry-run test; the Claude run writes the real one.\n\n"
               f"Send this to a friend who follows {c['category']} news.\n\nWhat do you make of this?\n\n"
               f"{editorial.LINK_LINE}\n\n#idly #{c['account']} #stub #dryrun\n\n"
               f"Photo: stub placeholder (dry run)")
    return {
        "account": c["account"], "story_id": c["id"], "title": c["title"],
        "cards": [{
            "tag": f"{(c['subcategory'] or c['category']).upper()} · STUB",
            "stat": stat.group(0).strip() if stat else "9 NOV",
            "stat_label": words(c["dek"] or c["title"], 8),
            "headline": words(c["title"], 10),
            "bullets": [words(g, 9) for g in (c["gist"] or [c["title"]] * 2)[:3]],
            "photo": str(photo.relative_to(REPO)), "photo_credit": "Photo: stub placeholder",
        }],
        "caption": caption,
        "alt_text": f"Stub card: {c['title']}",
        "photo_source": {"page": "stub", "licence": "stub (generated)", "viewed": True},
        "score": {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 1, "alone": 1,
                  "total": 12, "notes": "STUB score for the dry-run test, not a real assessment"},
    }


def main():
    date, slot = default_date(), default_slot()
    wd = work_dir(date, slot)
    print(f"=== 1. fetch ({date} {slot}) ===")
    result, _ = fetch.run(date=date, slot=slot)
    fetch.print_summary(result)

    print("\n=== 2. stub cards.json ===")
    photo = stub_photo(wd / "photos" / "stub.jpg")
    doc = {"date": date, "slot": slot, "posts": [], "skipped": []}
    for acct, rows in result["accounts"].items():
        pick = next((r for r in rows if not r["review"]), None)
        if pick:
            doc["posts"].append(stub_post(pick, photo))
            print(f"@{acct}: stub post for #{pick['id']} {pick['title']}")
        else:
            doc["skipped"].append({"account": acct, "story_id": None, "best_total": None,
                                   "reason": "no un-flagged candidate (stub run)"})
        for r in rows:
            if r is pick:
                break                     # list only the flagged stories ranked above the pick
            if r["review"]:
                doc["skipped"].append({"account": acct, "story_id": r["id"], "title": r["title"],
                                       "best_total": None, "reason": "flagged for review: " + "; ".join(r["review"])})
    save_json(wd / "cards.json", doc)

    try:
        importlib.import_module("cardkit.render")
        print("\nrendering with cardkit")
    except ImportError as e:
        print(f"\ncardkit not importable ({e}); using the PIL stand-in card")
        run_day.RENDERER = stub_renderer

    print("\n=== Meta access check (offline: no API calls) ===")
    run_day.main(["--date", date, "--slot", slot, "check", "--offline"])

    print("\n=== 3-5. run_day dry-run (render -> publish --dry-run -> report) ===")
    code = run_day.main(["--date", date, "--slot", slot, "dry-run"])

    print("\n=== 6. gate check: the same post at 11/14 ===")
    low = {**doc, "posts": [{**doc["posts"][0], "score": {**doc["posts"][0]["score"], "alone": 0, "total": 11}}]}
    errs, _ = run_day.validate_cards(low, date, slot)
    print("render refuses:", [e for e in errs if "gate" in e])
    try:
        publish.publish_post(low["posts"][0]["account"], ["https://example.com/x.jpg"], low["posts"][0]["caption"],
                             score=low["posts"][0]["score"], story_id=1, dry_run=True)
    except publish.GateRefused as e:
        print("publish refuses:", e)
    return code


if __name__ == "__main__":
    sys.exit(main())
