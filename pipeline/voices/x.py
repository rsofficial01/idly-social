"""X API v2 recent search (official; covers only the past 7 days; X bills per post returned). OFF unless
VOICES_X_ENABLED=true, X_BEARER_TOKEN is set and the topic gives x.max_posts (the hard cap on posts read)."""
from __future__ import annotations

import os

import requests

from .model import PlatformError, Post, Skipped, author_key, parse_time, to_int

URL = 'https://api.x.com/2/tweets/search/recent'
TIMEOUT = 20


def pull(cfg: dict, since: str, until: str | None, salt: str, session=None) -> tuple[list[Post], dict]:
    if os.environ.get('VOICES_X_ENABLED', '').strip().lower() != 'true':
        raise Skipped('X search is off (it is paid per post; set VOICES_X_ENABLED=true to allow it)')
    token = os.environ.get('X_BEARER_TOKEN', '').strip()
    if not token:
        raise Skipped('X_BEARER_TOKEN is not set')
    cap = int(cfg.get('max_posts', 0))
    if cap <= 0:
        raise Skipped('the topic sets no x.max_posts, so no posts may be read')
    http, posts, read = session or requests, [], 0
    for query in cfg.get('queries', []):
        if read >= cap:
            break
        size = max(10, min(100, cap - read))
        try:
            resp = http.get(URL, timeout=TIMEOUT, headers={'Authorization': f'Bearer {token}'}, params={
                'query': f'({query}) -is:retweet -is:reply', 'max_results': size,
                'tweet.fields': 'created_at,public_metrics,author_id,lang'})
        except requests.RequestException as exc:
            raise PlatformError(f'X search: network error ({type(exc).__name__})') from None
        if resp.status_code != 200:
            raise PlatformError(f'X search: HTTP {resp.status_code}')
        for t in resp.json().get('data') or []:
            read += 1
            m = t.get('public_metrics') or {}
            posts.append(Post(platform='x', kind='post', id=t['id'], url=f"https://x.com/i/status/{t['id']}",
                              text=t.get('text', ''), author_key=author_key('x', t.get('author_id', ''), salt),
                              likes=to_int(m.get('like_count')), replies=to_int(m.get('reply_count')),
                              published=parse_time(t.get('created_at')), context_owner='X'))
    return posts, {'posts_read': read, 'posts_cap': cap, 'window': 'past 7 days only'}
