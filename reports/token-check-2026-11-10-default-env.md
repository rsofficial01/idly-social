# Token check: Default env, 10 Nov 2026 (IST)

A one-time connection check for Instagram posting, run from a new session in the Default cloud environment.
**Nothing was posted.** The check makes only GET calls.

- Command: `python3 pipeline/publish.py check --no-refresh`
- Run at: 2026-11-09 18:43 UTC (00:13 IST, 10 Nov), scheduled Claude cloud session
- Environment: the session reports environment type `cloud_default` (the Default cloud environment).
  This session's container started at 18:41:25 UTC, so it was a new session, not a re-fire of an old one.
- Exit code: 0 (ok)
- Graph API: v27.0
- Setup note: `python3` (3.11) didn't have `requests` at first, so the first attempt stopped at
  `ModuleNotFoundError` before making any API call. `pip install -r requirements.txt` fixed it, and the
  second attempt is the result below.
- Expiry check skipped (`--no-refresh`). It only runs for `graph.instagram.com` tokens anyway, and all
  five accounts worked on `graph.facebook.com`.

## Variables present in this session

| Variable | Present |
|---|---|
| `IG_TOKEN_IDLYNEWS` | yes |
| `IG_TOKEN_IDLYTECH` | yes |
| `IG_TOKEN_IDLYHYPE` | yes |
| `IG_TOKEN_IDLYAUTOMOTIVE` | yes |
| `IG_TOKEN_IDLYNERD` | yes |
| `IG_SYSTEM_TOKEN` | no (not needed: every account has its own token) |

## Result: all five accounts ok

| Account | Variable present | Host that worked | IG user ID / username returned | Posts used in 24 h | Error |
|---|---|---|---|---|---|
| @idlynews | yes | graph.facebook.com | 17841456330541050 / idlynews | 0 of 25 | none |
| @idlytech | yes | graph.facebook.com | 17841456360777255 / idlytech | 0 of 25 | none |
| @idlyhype | yes | graph.facebook.com | 17841456251940953 / idlyhype | 0 of 25 | none |
| @idlyautomotive | yes | graph.facebook.com | 17841456459864048 / idlyautomotive | 0 of 25 | none |
| @idlynerd | yes | graph.facebook.com | 17841456588019165 / idlynerd | 0 of 25 | none |

How each account was checked: `graph.facebook.com` was tried first because `state/accounts.json` already
listed it as the host. `GET /me` succeeded with the account's own token. Then
`GET /{ig-user-id}?fields=id,username` returned the username shown, which matches the account. Finally,
`GET /{ig-user-id}/content_publishing_limit` gave the posts used. `graph.instagram.com` wasn't needed, so it
wasn't called. "25" is the pipeline's own daily cap (`LOCAL_DAILY_CAP`). The check output shows the lower
of that and Meta's quota, which means Meta allows at least 25.

## `state/accounts.json`

The check confirmed all five cached ids and the cached host. Because nothing differed, the script didn't
rewrite the file, so there was no change to commit.

## Check output

The check's own output contained no token text. It was also passed through a filter that would have masked
any token value, and that filter found nothing to mask.

```
Graph API v27.0
@idlynews (IG_TOKEN_IDLYNEWS on graph.facebook.com): ok (id 17841456330541050, 0/25 posts in 24h)
@idlytech (IG_TOKEN_IDLYTECH on graph.facebook.com): ok (id 17841456360777255, 0/25 posts in 24h)
@idlyhype (IG_TOKEN_IDLYHYPE on graph.facebook.com): ok (id 17841456251940953, 0/25 posts in 24h)
@idlyautomotive (IG_TOKEN_IDLYAUTOMOTIVE on graph.facebook.com): ok (id 17841456459864048, 0/25 posts in 24h)
@idlynerd (IG_TOKEN_IDLYNERD on graph.facebook.com): ok (id 17841456588019165, 0/25 posts in 24h)
```

## Compared with 9 Nov

The 18:30 UTC re-run on 9 Nov ([token-check-2026-11-09-rerun.md](token-check-2026-11-09-rerun.md)) saw none
of the five variables. At 18:39 UTC, commit `402ec1c` updated only `state/accounts.json` (ids entered by hand
from the Meta dashboard, host `graph.facebook.com`) and added no report. This run is the first report to show
all five variables present in the Default environment, with every token working and every cached id
confirmed by the API.
