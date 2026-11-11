from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Post:
    platform: str            # youtube | reddit | x
    kind: str                # comment | post
    id: str
    url: str
    text: str
    author_key: str          # salted hash of the public handle; the handle itself is never kept
    likes: int = 0
    replies: int = 0
    published: datetime | None = None
    context: str = ''        # the video or thread title the post sits under
    context_url: str = ''
    context_owner: str = ''  # the channel or subreddit
    themes: list[str] = field(default_factory=list)
    lang: str = ''
    about: list[str] = field(default_factory=list)   # parties/leaders the post names
    tone: str = ''           # praise | criticism | mixed | '' (word match only)


class PlatformError(Exception):
    """A platform could not be read. Its message never contains a key."""


class Skipped(Exception):
    """A platform is not set up (no key) or is switched off."""


def author_key(platform: str, handle: str, salt: str) -> str:
    return hashlib.sha256(f'{salt}|{platform}|{handle}'.encode()).hexdigest()[:12]


def parse_time(value) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def to_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
