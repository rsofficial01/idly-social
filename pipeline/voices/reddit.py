"""Reddit Data API (official, OAuth "script" app, application-only token). Reddit asks for a descriptive
User-Agent naming the app and the Reddit account that owns it; requests go to oauth.reddit.com."""
from __future__ import annotations

import os
import re
import time

import requests

from .model import PlatformError, Post, Skipped, author_key, parse_time, to_int

TOKEN_URL = 'https://www.reddit.com/api/v1/access_token'
BASE = 'https://oauth.reddit.com'
TIMEOUT = 20
SUB = re.compile(r'^[A-Za-z0-9_]{2,21}$')
BOTS = {'automoderator', '[deleted]', ''}


def _creds() -> tuple[str, str, str]:
    cid, secret = os.environ.get('REDDIT_CLIENT_ID', '').strip(), os.environ.get('REDDIT_CLIENT_SECRET', '').strip()
    if not cid or not secret:
        raise Skipped('REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not set')
    user = re.sub(r'[^A-Za-z0-9_-]', '', os.environ.get('REDDIT_USERNAME', '')) or 'idlynews'
    return cid, secret, f'web:news.idly.voices:1.0 (by /u/{user})'


class Client:
    def __init__(self, max_calls: int = 120, session=None, pause: float = 0.7):
        self.http, self.max_calls, self.calls, self.pause = session or requests, max_calls, 0, pause
        cid, secret, self.ua = _creds()
        try:
            resp = self.http.post(TOKEN_URL, auth=(cid, secret), data={'grant_type': 'client_credentials'},
                                  headers={'User-Agent': self.ua}, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise PlatformError(f'Reddit token: network error ({type(exc).__name__})') from None
        if resp.status_code != 200 or 'access_token' not in (resp.json() if resp.content else {}):
            raise PlatformError(f'Reddit token: HTTP {resp.status_code}')
        self._token = resp.json()['access_token']

    def get(self, path: str, params: dict):
        if self.calls >= self.max_calls:
            return None
        self.calls += 1
        if self.pause:
            time.sleep(self.pause)
        try:
            resp = self.http.get(f'{BASE}{path}', params={**params, 'raw_json': 1}, timeout=TIMEOUT,
                                 headers={'User-Agent': self.ua, 'Authorization': f'Bearer {self._token}'})
        except requests.RequestException as exc:
            raise PlatformError(f'Reddit {path}: network error ({type(exc).__name__})') from None
        if resp.status_code in (403, 404):
            return None     # private, banned or missing subreddit/thread
        if resp.status_code != 200:
            raise PlatformError(f'Reddit {path}: HTTP {resp.status_code}')
        return resp.json()


def _in_window(ts, since: str, until: str | None) -> bool:
    when = parse_time(ts)
    if when is None:
        return False
    day = when.date().isoformat()
    return day >= since and (until is None or day <= until)


def search(client: Client, sub: str, query: str, since: str, until: str | None, salt: str, limit: int = 50,
           sort: str = 'top') -> list[Post]:
    if not SUB.match(sub):
        return []
    data = client.get(f'/r/{sub}/search', {'q': query, 'restrict_sr': 1, 'sort': sort, 't': 'year',
                                           'limit': min(100, limit), 'type': 'link'})
    out = []
    for child in ((data or {}).get('data') or {}).get('children') or []:
        d = child.get('data') or {}
        if not d.get('id') or not _in_window(d.get('created_utc'), since, until):
            continue
        if d.get('over_18') or (d.get('author') or '').lower() in BOTS:
            continue
        body = (d.get('selftext') or '').strip()
        url = f"https://www.reddit.com{d.get('permalink', '')}"
        out.append(Post(platform='reddit', kind='post', id=d['id'], url=url,
                        text=(d.get('title', '') + ('\n' + body if body else '')).strip(),
                        author_key=author_key('reddit', d.get('author', ''), salt), likes=to_int(d.get('score')),
                        replies=to_int(d.get('num_comments')), published=parse_time(d.get('created_utc')),
                        context=d.get('title', ''), context_url=url, context_owner=f"r/{d.get('subreddit', sub)}"))
    return out


def thread_comments(client: Client, post: Post, salt: str, limit: int = 60) -> list[Post]:
    data = client.get(f'/comments/{post.id}', {'limit': limit, 'sort': 'top', 'depth': 2})
    if not isinstance(data, list) or len(data) < 2:
        return []
    out = []

    def walk(children):
        for child in children or []:
            if child.get('kind') != 't1':
                continue
            d = child.get('data') or {}
            body = (d.get('body') or '').strip()
            if body and body not in ('[deleted]', '[removed]') and (d.get('author') or '').lower() not in BOTS \
                    and not d.get('stickied'):
                out.append(Post(platform='reddit', kind='comment', id=d.get('id', ''), text=body,
                                url=f"https://www.reddit.com{d.get('permalink', '')}",
                                author_key=author_key('reddit', d.get('author', ''), salt),
                                likes=to_int(d.get('score')), published=parse_time(d.get('created_utc')),
                                context=post.context, context_url=post.url, context_owner=post.context_owner))
            replies = d.get('replies')
            if isinstance(replies, dict):
                walk((replies.get('data') or {}).get('children'))

    walk((data[1].get('data') or {}).get('children'))
    return out


def pull(cfg: dict, since: str, until: str | None, salt: str, session=None, pause: float = 0.7) -> tuple[list[Post], dict]:
    client = Client(cfg.get('max_calls', 120), session, pause)
    threads: dict[str, Post] = {}
    for sub in cfg.get('subreddits', []):
        for query in cfg.get('queries', []):
            for sort in cfg.get('sorts', ['top', 'comments']):
                for p in search(client, sub, query, since, until, salt, cfg.get('posts_per_query', 50), sort):
                    threads.setdefault(p.id, p)
    ranked = sorted(threads.values(), key=lambda p: p.replies, reverse=True)
    posts = list(ranked)
    for p in ranked[:cfg.get('max_threads', 40)]:
        if p.replies:
            posts += thread_comments(client, p, salt, cfg.get('comments_per_thread', 60))
    subs: dict[str, int] = {}
    for p in ranked:
        subs[p.context_owner] = subs.get(p.context_owner, 0) + 1
    return posts, {'threads_found': len(ranked), 'calls_used': client.calls, 'calls_cap': client.max_calls,
                   'subreddits': subs}
