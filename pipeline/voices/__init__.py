"""Citizen voices: what ordinary people are posting about a story, read through each platform's official API.

    python3 -m pipeline.voices pull tvk-six-months          # config/voices/tvk-six-months.json
    python3 -m pipeline.voices check                        # which platforms have keys (never prints a key)

Platforms (each is skipped, with a note in the digest, when its key is absent):

youtube   YouTube Data API v3: search.list (100 quota units a call) finds videos for the topic's queries;
          commentThreads.list (1 unit a call) reads the top comments under them.     env YOUTUBE_API_KEY
reddit    Reddit Data API (OAuth, script app): searches the topic's subreddits and reads the top comments of
          the matching posts.                         env REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME
x         X API v2 recent search (the past 7 days only; X bills per post read). OFF unless VOICES_X_ENABLED=true
          and the topic sets x.max_posts.                                              env X_BEARER_TOKEN

Rules this package keeps:
* official APIs only; keys come from the environment and travel in headers, never in a URL, a log or a file
* this repository is public, so nothing that names an ordinary person is written to disk: the digest holds
  counts, and short excerpts (<= 220 characters) with the public link to the post, never a username
* raw posts live only in memory for the length of one run (YouTube API data may not be kept past 30 days)
* the digest says what it is: a reading of N public posts found by these searches, not a poll. Comment
  sections skew towards the angry and the organised; repeated copy-paste text is counted and flagged.
* themes are matched by keyword (English, Tamil, Tamil in Latin script). No sentiment or stance is inferred.
"""
from .model import Post  # noqa: F401
