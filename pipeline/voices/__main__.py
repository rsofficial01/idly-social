from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import analyse, reddit, x, youtube
from .model import PlatformError, Skipped

ROOT = Path(__file__).resolve().parents[2]
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{1,60}$')
PLATFORMS = {'youtube': youtube.pull, 'reddit': reddit.pull, 'x': x.pull}
KEYS = {'youtube': ['YOUTUBE_API_KEY'], 'reddit': ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET'], 'x': ['X_BEARER_TOKEN']}


def load_topic(slug: str) -> dict:
    if not SLUG.match(slug):
        sys.exit(f'bad topic name: {slug!r}')
    path = ROOT / 'config' / 'voices' / f'{slug}.json'
    if not path.exists():
        sys.exit(f'no such topic: config/voices/{slug}.json')
    topic = json.loads(path.read_text())
    topic['slug'] = slug
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', topic.get('since', '')):
        sys.exit('the topic needs "since": "YYYY-MM-DD"')
    return topic


def run(topic: dict, only: list[str] | None = None, pullers: dict | None = None) -> dict:
    salt = secrets.token_hex(16)        # per run: author keys cannot be linked across runs or reversed
    posts, notes = [], {}
    for name, pull in (pullers or PLATFORMS).items():
        cfg = topic.get(name)
        if not cfg or (only and name not in only):
            continue
        try:
            got, note = pull(cfg, topic['since'], topic.get('until'), salt)
            posts += got
            notes[name] = note
        except Skipped as exc:
            notes[name] = f'skipped: {exc}'
        except PlatformError as exc:
            notes[name] = f'failed: {exc}'
    posts = analyse.prepare(posts, topic.get('must_match', []), topic.get('extra_themes'))
    return analyse.digest(topic, posts, notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python3 -m pipeline.voices')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('pull')
    p.add_argument('topic')
    p.add_argument('--only', nargs='*', choices=list(PLATFORMS))
    p.add_argument('--out', default=str(ROOT / 'research' / 'voices'))
    sub.add_parser('check')
    args = ap.parse_args(argv)
    if args.cmd == 'check':
        for name, keys in KEYS.items():
            print(f"{name}: {'ready' if all(os.environ.get(k, '').strip() for k in keys) else 'no key'}")
        return 0
    topic = load_topic(args.topic)
    d = run(topic, args.only)
    summary = '; '.join(f'{k}: {v if isinstance(v, str) else "ok"}' for k, v in d['platform_notes'].items())
    if not d['totals']['posts_counted']:
        print(f'nothing read, nothing written ({summary})')
        return 0
    out = Path(args.out) / topic['slug']
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    (out / f'{stamp}.json').write_text(json.dumps(d, ensure_ascii=False, indent=1))
    (out / f'{stamp}.md').write_text(analyse.markdown(d))
    (out / 'latest.md').write_text(analyse.markdown(d))
    print(f"{d['totals']['posts_counted']} posts from {d['totals']['people']} accounts; {len(d['themes'])} themes; {summary}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
