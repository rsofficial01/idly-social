"""YouTube Data API v3 (official). Quota: search.list 100 units, videos.list 1, commentThreads.list 1."""
from __future__ import annotations

import os
import re

import requests

from .model import PlatformError, Post, Skipped, author_key, parse_time, to_int

BASE = 'https://www.googleapis.com/youtube/v3'
TIMEOUT = 20
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{6,20}$')


class Budget:
    def __init__(self, units: int):
        self.limit, self.used = int(units), 0

    def take(self, units: int) -> bool:
        if self.used + units > self.limit:
            return False
        self.used += units
        return True


def _key() -> str:
    key = os.environ.get('YOUTUBE_API_KEY', '').strip()
    if not key:
        raise Skipped('YOUTUBE_API_KEY is not set')
    return key


def _get(path: str, params: dict, session=None) -> dict:
    http = session or requests
    try:
        resp = http.get(f'{BASE}/{path}', params=params, headers={'X-Goog-Api-Key': _key()}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise PlatformError(f'YouTube {path}: network error ({type(exc).__name__})') from None
    if resp.status_code != 200:
        reason = ''
        try:
            reason = (resp.json().get('error', {}).get('errors') or [{}])[0].get('reason', '')
        except ValueError:
            pass
        raise PlatformError(f'YouTube {path}: HTTP {resp.status_code} {reason}'.strip())
    return resp.json()


def search_videos(query: str, since: str, until: str | None, budget: Budget, max_results: int = 15,
                  order: str = 'viewCount', session=None) -> list[dict]:
    if not budget.take(100):
        return []
    params = {'part': 'snippet', 'type': 'video', 'q': query, 'maxResults': min(50, max_results), 'order': order,
              'regionCode': 'IN', 'publishedAfter': f'{since}T00:00:00Z', 'safeSearch': 'none'}
    if until:
        params['publishedBefore'] = f'{until}T23:59:59Z'
    out = []
    for item in _get('search', params, session).get('items') or []:
        vid = (item.get('id') or {}).get('videoId') or ''
        sn = item.get('snippet') or {}
        if VIDEO_ID.match(vid):
            out.append({'id': vid, 'title': sn.get('title') or '', 'channel': sn.get('channelTitle') or '',
                        'channel_id': sn.get('channelId') or '', 'published': sn.get('publishedAt') or ''})
    return out


def video_details(ids: list[str], budget: Budget, session=None) -> dict[str, dict]:
    out = {}
    ids = [i for i in dict.fromkeys(ids) if VIDEO_ID.match(i)]
    for n in range(0, len(ids), 50):
        if not budget.take(1):
            break
        data = _get('videos', {'part': 'snippet,statistics', 'id': ','.join(ids[n:n + 50])}, session)
        for item in data.get('items') or []:
            sn, st = item.get('snippet') or {}, item.get('statistics') or {}
            out[item['id']] = {'id': item['id'], 'title': sn.get('title') or '', 'channel': sn.get('channelTitle') or '',
                               'channel_id': sn.get('channelId') or '', 'published': sn.get('publishedAt') or '',
                               'views': to_int(st.get('viewCount')), 'comments': to_int(st.get('commentCount'))}
    return out


def comments(video: dict, budget: Budget, salt: str, max_comments: int = 100, session=None) -> list[Post]:
    """Top-level comments under one video, most relevant first. A video with comments off returns []."""
    out, token = [], None
    while len(out) < max_comments and budget.take(1):
        params = {'part': 'snippet', 'videoId': video['id'], 'order': 'relevance', 'textFormat': 'plainText',
                  'maxResults': min(100, max_comments - len(out))}
        if token:
            params['pageToken'] = token
        try:
            data = _get('commentThreads', params, session)
        except PlatformError as exc:
            if 'commentsDisabled' in str(exc) or 'HTTP 404' in str(exc):
                return out
            raise
        for item in data.get('items') or []:
            top = ((item.get('snippet') or {}).get('topLevelComment') or {})
            sn = top.get('snippet') or {}
            text = (sn.get('textDisplay') or sn.get('textOriginal') or '').strip()
            cid = top.get('id') or item.get('id') or ''
            if not text or not cid:
                continue
            handle = (sn.get('authorChannelId') or {}).get('value') or sn.get('authorDisplayName') or ''
            if handle and handle == video.get('channel_id'):
                continue    # the channel's own pinned comment is not a citizen
            out.append(Post(platform='youtube', kind='comment', id=cid, text=text,
                            url=f"https://www.youtube.com/watch?v={video['id']}&lc={cid}",
                            author_key=author_key('youtube', handle, salt), likes=to_int(sn.get('likeCount')),
                            replies=to_int((item.get('snippet') or {}).get('totalReplyCount')),
                            published=parse_time(sn.get('publishedAt')), context=video.get('title', ''),
                            context_url=f"https://www.youtube.com/watch?v={video['id']}",
                            context_owner=video.get('channel', '')))
        token = data.get('nextPageToken')
        if not token:
            break
    return out


def pull(cfg: dict, since: str, until: str | None, salt: str, session=None) -> tuple[list[Post], dict]:
    _key()
    budget = Budget(cfg.get('max_units', 1500))
    per_query, per_video = cfg.get('videos_per_query', 12), cfg.get('comments_per_video', 100)
    skip = {c.lower() for c in cfg.get('skip_channels', [])}
    found: dict[str, dict] = {}
    for query in cfg.get('queries', []):
        for v in search_videos(query, since, until, budget, per_query, cfg.get('order', 'viewCount'), session):
            found.setdefault(v['id'], v)
    ids = list(dict.fromkeys(list(cfg.get('video_ids', [])) + list(found)))
    details = video_details(ids, budget, session)
    videos = sorted(details.values(), key=lambda v: v['comments'], reverse=True)
    videos = [v for v in videos if v['comments'] > 0 and v['channel'].lower() not in skip][:cfg.get('max_videos', 60)]
    posts: list[Post] = []
    for v in videos:
        posts += comments(v, budget, salt, per_video, session)
    channels: dict[str, int] = {}
    for v in videos:
        channels[v['channel']] = channels.get(v['channel'], 0) + 1
    note = {'videos_read': len(videos), 'units_used': budget.used, 'units_cap': budget.limit,
            'channels': dict(sorted(channels.items(), key=lambda kv: -kv[1])[:25])}
    return posts, note
