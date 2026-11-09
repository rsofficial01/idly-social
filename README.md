# idly-social

This repo runs idly's automated Instagram feed posts for @idlynews, @idlytech, @idlyhype,
@idlyautomotive and @idlynerd. A scheduled Claude session runs it twice a day, at about 8:40 AM and
6:40 PM IST, following [RUNBOOK.md](RUNBOOK.md). Each run makes at most one card per account.

**The gate:** nothing is published unless it scores at least **12/14** on the 7-check score (hook,
read-through, send reason, keep reason, reply prompt, original, stands alone). Both `run_day.py` and
`publish.py` enforce it. The automated path has no override. Skipping an account is normal.

## How a run works

1. `pipeline/fetch.py` pulls the last 14 h of stories from `api.idly.news` and keeps the ones with
   2+ sources that aren't archived, posted or gossip. It ranks them and writes the top 5 per account,
   with borderline stories flagged for review.
2. `run_day.py check` confirms Meta access: it finds the Instagram account id of all five accounts,
   checks each one is reachable and reads its publishing limit.
3. The Claude run picks a story, finds a licensed photo, writes the card and caption, and scores them.
   All of it goes into `_work/<date>-<slot>/cards.json`.
4. `run_day.py render` validates the cards and renders them with `cardkit/`. It copies the JPEGs to
   `posts/<date>/`, which the run commits and pushes so they are public on raw.githubusercontent.com.
5. `run_day.py wait-urls`, then `publish`, which uses the **Instagram API with Facebook Login**
   (`graph.facebook.com`, Graph API v27.0): container → wait for `FINISHED` → `media_publish` → permalink.
6. `run_day.py report` writes `reports/<date>-<slot>.md`. The run commits it with `state/posted.json` and
   `state/accounts.json`, and sends a short summary.

## Meta access: one token, kept out of the session

The Meta app **idly publisher** (app id `1533702778969280`, business portfolio `1165348135833967`) uses
**API setup with Unified login**: Facebook Login for Business with a configuration whose token is a
**system-user access token** that never expires. Its business assets are the five Instagram accounts, and
its permissions are `instagram_basic` and `instagram_content_publish` (the template also adds
`ads_management`, `ads_read`, `instagram_manage_comments` and `instagram_manage_messages`; the pipeline
doesn't use them). **One token covers all five accounts.** (Meta no longer offers "API setup with
Instagram login" to newer apps, so there are no per-account Instagram tokens any more.)

In the Claude cloud environment the token is a **network secret**: Anthropic's agent proxy adds
`Authorization: Bearer <token>` to every request for `graph.facebook.com`, after the request leaves the
session. The session never sees the token, and the code sends no credentials at all.
[RUNBOOK.md → Meta access](RUNBOOK.md#meta-access-one-time-setup) has the exact setup steps.

Running somewhere else (your own computer, a server)? Set `IG_SYSTEM_TOKEN` in that shell. The code sends
it only as the `Authorization: Bearer` header: never in a URL or a request body, never printed or logged.
**Don't** put it in the Claude environment's *Environment variables*: every session can read those.

The account ids are cached in `state/accounts.json` (ids and usernames only, safe to commit). Before
every post the pipeline re-checks the id with `GET /{ig-user-id}?fields=id,username`, and runs discovery
again if the cached id is wrong.

## Setup

- Python 3.11+, `pip install -r requirements.txt`, plus cardkit's own requirements.
- Meta access as above (network secret, or `IG_SYSTEM_TOKEN` outside the Claude cloud).
- Optional: `IG_BUSINESS_ID` (default `1165348135833967`), `IDLY_IMAGE_BASE` (a different public base URL
  for `posts/`; default raw.githubusercontent.com).

## Useful commands

```bash
python3 pipeline/fetch.py                          # today's candidates
python3 pipeline/publish.py check                  # find the 5 account ids, reachable?, publishing limit
python3 pipeline/publish.py check --offline        # what's cached, no API calls
python3 pipeline/run_day.py dry-run                # render + would-be API calls + report, nothing posted
python3 -m unittest discover -s tests -t .         # unit tests (rules, gate, mock graph.facebook.com)
python3 tests/dry_run_e2e.py                       # end-to-end dry run on live idly data with stub cards
```

Manual posts (a human, not the scheduled run) can use `publish.py post` directly: repeat `--image` for a
carousel, use `--video clip.mp4` for a video carousel item (videos only go in carousels, never as a single
post), and `--collaborator <username>` (up to 3) to invite collaborators. In `cards.json` the optional
`"collaborators": ["username"]` field does the same for one post; the default is none.

## Layout

`pipeline/` holds the code (`editorial.py` has every rule in one place). `posts/` holds the published
JPEGs, which are committed and public. `state/posted.json` records what was posted and
`state/accounts.json` the Instagram account ids. `reports/` holds the run reports. `_work/` is per-run
scratch space and is gitignored. `cardkit/` is the card renderer, kept separately.
