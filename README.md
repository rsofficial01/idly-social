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
2. `run_day.py check` confirms Meta access for each account: which token and host, the right account,
   its publishing limit, and how long the token has left.
3. The Claude run picks a story, finds a licensed photo, writes the card and caption, and scores them.
   All of it goes into `_work/<date>-<slot>/cards.json`.
4. `run_day.py render` validates the cards and renders them with `cardkit/`. It copies the JPEGs to
   `posts/<date>/`, which the run commits and pushes so they are public on raw.githubusercontent.com.
5. `run_day.py wait-urls`, then `publish`, which uses Meta's Instagram API (Graph API v27.0) on
   `graph.instagram.com` or `graph.facebook.com`, depending on the token: container → wait for
   `FINISHED` → `media_publish` → permalink.
6. `run_day.py report` writes `reports/<date>-<slot>.md`. The run commits it with `state/posted.json` and
   `state/accounts.json`, and sends a short summary.

## Meta access: a token per account, or one shared token

The Meta app **idly publisher** (app id `1533702778969280`, business portfolio `1165348135833967`) uses
**API setup with Unified login** (Meta no longer offers "API setup with Instagram login" to newer apps).
For each account the pipeline picks, in this order:

1. **The account's own token**, `IG_TOKEN_IDLYNEWS`, `IG_TOKEN_IDLYTECH`, `IG_TOKEN_IDLYHYPE`,
   `IG_TOKEN_IDLYAUTOMOTIVE`, `IG_TOKEN_IDLYNERD`: environment variables holding the tokens from the
   dashboard's *2. Generate access tokens* step, where each Instagram account has its own **Generate token**
   button. The pipeline works out which API each token belongs to: it tries
   `graph.instagram.com/me?fields=user_id,username`, then `graph.facebook.com/me?fields=id,name`, and
   remembers the one that works in `state/accounts.json`.
2. **A shared system-user token** for every account without its own (Facebook Login for Business, one
   token for all five, on `graph.facebook.com`). In the Claude cloud it can be a **network secret**:
   Anthropic's agent proxy adds the `Authorization` header after the request leaves the session, so the
   session never sees it. Elsewhere, `IG_SYSTEM_TOKEN`.

Either way a token is sent only as the `Authorization: Bearer` header: never in a URL or a request body,
never printed, logged or saved. Values in the Claude environment's *Environment variables* are readable
by every session in that environment (a network secret is not), so the runbook forbids printing them.
[RUNBOOK.md → Meta access](RUNBOOK.md#meta-access-one-time-setup) has the exact setup steps.

`check` also reports how many days a `graph.instagram.com` token has left, when Meta's
`refresh_access_token` reply says so, and warns 10 days ahead. New tokens come from the Meta dashboard;
the pipeline never writes a token anywhere.

`state/accounts.json` holds each account's Instagram id, username and (for its own token) the working
host: no tokens, safe to commit. It is seeded with the five ids from the dashboard. Before every post the
pipeline re-checks that the token or id really is that account.

## Setup

- Python 3.11+, `pip install -r requirements.txt`, plus cardkit's own requirements.
- Meta access as above: `IG_TOKEN_<ACCOUNT>` per account, and/or the shared token (network secret, or
  `IG_SYSTEM_TOKEN` outside the Claude cloud).
- Optional: `IG_BUSINESS_ID` (default `1165348135833967`), `IDLY_IMAGE_BASE` (a different public base URL
  for `posts/`; default raw.githubusercontent.com).

## Useful commands

```bash
python3 pipeline/fetch.py                          # today's candidates
python3 pipeline/publish.py check                  # per account: token, host, id, publishing limit, expiry
python3 pipeline/publish.py check --no-refresh     # the same without the expiry check
python3 pipeline/publish.py check --offline        # what's cached, no API calls
python3 pipeline/run_day.py dry-run                # render + would-be API calls + report, nothing posted
python3 -m unittest discover -s tests -t .         # unit tests (rules, gate, mock graph.facebook.com)
python3 tests/dry_run_e2e.py                       # end-to-end dry run on live idly data with stub cards
python3 -m cardkit.vertical story post.json posts/<date>/<folder>/story.jpg   # 9:16 Story card from a hype post
python3 pipeline/publish.py story --account idlytech --image posts/<date>/<folder>/story.jpg [--dry-run]
python3 pipeline/lane.py request-reel --source lane:<slug> --caption-file c.txt --score-file s.json   # ask for a reel
python3 -m cardkit.reel post.json OUT_DIR --previews  # render a reel locally (non-people photos only; needs ffmpeg)
```

**Stories** (Rahul, 10 Nov 2026): each feed post can get a 1080x1920 Instagram Story made from the same post dict
(`cardkit/vertical.py`: photo full-width at the top fading into #0A0A0A, headline and footer clear of Instagram's
UI zones). The lane makes and posts them automatically; hourly runs use the two commands above. A story never
holds up or changes its feed post. See [RUNBOOK.md → Stories](RUNBOOK.md#stories-916).

**Reels**: a run asks for a silent 9-14 s reel of a post that is already live (`lane.py request-reel`); the
**lane-render** workflow renders it with `cardkit/reel.py` and ffmpeg (cover push-in, 1-2 detail slides, end card,
silent AAC track), a blind reviewer approves it through the same 12/14 gate, and **lane-publish** posts it. See
[RUNBOOK.md → Reels](RUNBOOK.md#reels-916).

Manual posts (a human, not the scheduled run) can use `publish.py post` directly: repeat `--image` for a
carousel, use `--video clip.mp4` for a video carousel item (videos only go in carousels, never as a single
post), and `--collaborator <username>` (up to 3) to invite collaborators. In `cards.json` the optional
`"collaborators": ["username"]` field does the same for one post; the default is none.

## Official image lane (GitHub Actions)

Posts that need an official publicity image (a trailer still, a licensed agency photo, a company's press
image) go through `queue/`: a Claude session writes `queue/pending/<slug>.json`, the **lane-render** workflow
(every 10 min) resolves the image from an allowlisted official source (`config/official_sources.json`),
frames it around any faces (OpenCV YuNet), renders it with cardkit and commits `queue/rendered/<slug>/`; a
Claude reviewer approves with a blind score (`pipeline/lane.py approve`), and **lane-publish** (every 10 min)
posts it with the per-account tokens stored as GitHub secrets. See [RUNBOOK.md → Official image
lane](RUNBOOK.md#official-image-lane) and, for the secrets, [docs/SETUP-GITHUB-SECRETS.md](docs/SETUP-GITHUB-SECRETS.md).

```bash
python3 pipeline/lane.py status                     # what is pending, rendered, approved, rejected, posted
python3 pipeline/lane.py validate                   # check pending specs
python3 pipeline/lane.py render-pending             # what lane-render runs (add --push to commit); + story.jpg
python3 pipeline/lane.py publish-approved --dry-run # what lane-publish would post (feed, stories, reels)
python3 pipeline/lane.py render-reels               # what lane-render runs for queue/reels/pending (needs ffmpeg)
```

## Layout

`pipeline/` holds the code (`editorial.py` has every rule in one place). `posts/` holds the published
JPEGs, which are committed and public. `state/posted.json` records what was posted and
`state/accounts.json` the Instagram account ids and hosts. `reports/` holds the run reports. `_work/` is per-run
scratch space and is gitignored. `cardkit/` is the card renderer, kept separately (`render.py`: feed cards; `vertical.py`: 9:16 stories;
`reel.py`: reels).
