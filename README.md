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
2. The Claude run picks a story, finds a licensed photo, writes the card and caption, and scores them.
   All of it goes into `_work/<date>-<slot>/cards.json`.
3. `run_day.py render` validates the cards and renders them with `cardkit/`. It copies the JPEGs to
   `posts/<date>/`, which the run commits and pushes so they are public on raw.githubusercontent.com.
4. `run_day.py wait-urls`, then `publish`, which uses the Instagram API with Instagram Login (Graph API v25.0).
5. `run_day.py report` writes `reports/<date>-<slot>.md`. The run commits it with `state/posted.json` and
   sends a short summary.

## Setup

- Python 3.11+, `pip install -r requirements.txt`, plus cardkit's own requirements.
- Environment (never committed):
  - `IG_TOKEN_IDLYNEWS`, `IG_TOKEN_IDLYTECH`, `IG_TOKEN_IDLYHYPE`, `IG_TOKEN_IDLYAUTOMOTIVE`, `IG_TOKEN_IDLYNERD`:
    long-lived Instagram User tokens with `instagram_business_basic` and `instagram_business_content_publish`.
  - Optional `IG_TOKEN_EXPIRES_<ACCOUNT>=YYYY-MM-DD`: lets the run warn you 10 days before a token expires.
  - Optional `IDLY_IMAGE_BASE`: a different public base URL for `posts/` (default: raw.githubusercontent.com).
- If a token is missing, that account is skipped. Nothing crashes.

## Useful commands

```bash
python3 pipeline/fetch.py                          # today's candidates
python3 pipeline/publish.py check                  # tokens, usernames, quota, expiry
python3 pipeline/publish.py refresh --account idlytech   # new 60-day token -> state/secrets/ (gitignored)
python3 pipeline/run_day.py dry-run                # render + would-be API calls + report, nothing posted
python3 -m unittest discover -s tests -t .         # unit tests (rules, gate, mock publish flow)
python3 tests/dry_run_e2e.py                       # end-to-end dry run on live idly data with stub cards
```

## Layout

`pipeline/` holds the code (`editorial.py` has every rule in one place). `posts/` holds the published
JPEGs, which are committed and public. `state/posted.json` records what was posted. `reports/` holds the
run reports. `_work/` is per-run scratch space and is gitignored. `cardkit/` is the card renderer, kept
separately.
