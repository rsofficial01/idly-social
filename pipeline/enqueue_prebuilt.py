"""Put an already-built post (posts/<date>/<folder>/) into the lane as a rendered item, so the
GitHub Actions publisher posts it once a blind reviewer approves it with `lane.py approve`.

For posts made outside the lane (morning cards, Nvidia, reviews) when the Claude scheduled
posting runs are unreliable. Nothing is re-rendered: the committed JPEGs are copied as they are.

    python3 pipeline/enqueue_prebuilt.py posts/2026-11-10/nvidia_idlynews --account idlynews \
        [--slides 01.jpg 02.jpg] [--no-idly-article] [--story-id 1664] [--evergreen]

Then: python3 pipeline/lane.py show <slug> -> reviewer -> python3 pipeline/lane.py approve <slug> --score-file F
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import editorial, publish
from pipeline.common import ACCOUNTS, REPO, now_utc, save_json
from pipeline.lane import qdir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--account", required=True, choices=list(ACCOUNTS))
    ap.add_argument("--slides", nargs="+", help="JPEG files in order (default: 01.jpg, 02.jpg, ... in the folder)")
    ap.add_argument("--slug")
    ap.add_argument("--story-id", type=int)
    ap.add_argument("--no-idly-article", action="store_true")
    ap.add_argument("--evergreen", action="store_true")
    ap.add_argument("--headline", help="the cover headline as published (default: the folder name)")
    ap.add_argument("--title", help="one-line description of the story for the reviewer")
    ap.add_argument("--image-source-url", help="page the image came from (official newsroom, media kit, Commons)")
    ap.add_argument("--image-org", help="organisation that published the image")
    a = ap.parse_args(argv)

    src = a.folder if a.folder.is_absolute() else REPO / a.folder
    slides = a.slides or sorted(p.name for p in src.glob("[0-9][0-9].jpg"))
    if not slides:
        print("no slides found", file=sys.stderr)
        return 2
    caption = (src / "caption.txt").read_text(encoding="utf-8").strip()
    score = json.loads((src / "score.json").read_text(encoding="utf-8"))
    self_score = {k: score[k] for k in ("hook", "read", "send", "keep", "reply", "original", "alone")}
    self_score["total"] = sum(self_score.values())
    self_score["notes"] = str(score.get("notes", ""))[:900] or "maker's score"
    story_id = a.story_id if a.story_id is not None else score.get("story_id")
    idly_article = not a.no_idly_article

    errs, _ = editorial.post_problems(caption, self_score, idly_article=idly_article)
    if errs:
        print("caption problems: " + "; ".join(errs), file=sys.stderr)
        return 2
    for s in slides:
        publish.check_jpeg(src / s)

    slug = a.slug or re.sub(r"[^a-z0-9-]+", "-", f"{src.parent.name}-{src.name}".lower()).strip("-")[:80]
    dest = qdir("rendered") / slug
    if dest.exists() or (qdir("posted") / slug).exists():
        print(f"{slug} is already queued or posted", file=sys.stderr)
        return 2
    dest.mkdir(parents=True)
    files = []
    for i, s in enumerate(slides, 1):
        name = f"{i:02d}.jpg"
        shutil.copyfile(src / s, dest / name)
        files.append(name)
    alt = (src / "alt.txt").read_text(encoding="utf-8").strip().splitlines()[0] if (src / "alt.txt").exists() else ""
    credit = next((l for l in reversed(caption.splitlines()) if re.match(r"(Photo|Poster|Image|Still)s?:", l.strip())), "")
    spec = {"slug": slug, "account": a.account, "story_id": story_id, "idly_article": idly_article,
            "evergreen": a.evergreen, "headline": a.headline or src.name, "title": a.title, "caption": caption, "caption_final": caption,
            "alt_text": alt[:1000], "image_credit": credit, "scores": {"self": self_score},
            "created_at": now_utc().isoformat(timespec="seconds"),
            "lane": {"source": "prebuilt", "folder": src.relative_to(REPO).as_posix()}}
    save_json(dest / "spec.json", spec)
    rep = {"files": files, "prebuilt": True, "caption_final": caption}
    if a.image_source_url or a.image_org:
        rep["source"] = {"resolver": "prebuilt (recorded by the maker)", "source_url": a.image_source_url,
                         "image_url": None, "organisation": a.image_org}
    save_json(dest / "render_report.json", rep)
    print(f"queued {slug}: {len(files)} slide(s) for @{a.account}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
