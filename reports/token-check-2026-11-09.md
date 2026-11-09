# Token check: 9 Nov 2026

One-time connection check for Instagram posting. **Nothing was posted.**

- Command: `python3 pipeline/publish.py check --no-refresh` (run in-process, same code path, so the ids and
  usernames Meta returned could be recorded; output scrubbed of anything token-shaped)
- Run at: 2026-11-09 18:05 UTC (23:35 IST), scheduled Claude cloud session
- Exit code: 1 (not ok)
- Graph API: v27.0
- API calls made: one, `GET graph.facebook.com/v27.0/me?fields=id,name` (shared-token fallback). It
  failed, so discovery stopped there. No call went to `graph.instagram.com`, because no account had its own
  token.
- `state/accounts.json`: **not changed** by the check (it still holds the five ids entered by hand at
  17:45 UTC), so it isn't part of this commit.

## Result: all five accounts failed

None of the `IG_TOKEN_*` variables was set in this session, and neither was `IG_SYSTEM_TOKEN`. So every
account fell back to the shared token on `graph.facebook.com`, and there's no network secret for that host
either. Meta answered:

> GET graph.facebook.com/me -> HTTP 400, code 2500: An active access token must be used to query
> information about the current user.

| Account | Variable | Present | Host that worked | IG user ID / username returned | Posts used in 24 h | Status |
|---|---|---|---|---|---|---|
| @idlynews | `IG_TOKEN_IDLYNEWS` | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456330541050) | unavailable | no access |
| @idlytech | `IG_TOKEN_IDLYTECH` | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456360777255) | unavailable | no access |
| @idlyhype | `IG_TOKEN_IDLYHYPE` | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456251940953) | unavailable | no access |
| @idlyautomotive | `IG_TOKEN_IDLYAUTOMOTIVE` | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456459864048) | unavailable | no access |
| @idlynerd | `IG_TOKEN_IDLYNERD` | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456588019165) | unavailable | no access |

Also checked: `IG_SYSTEM_TOKEN` present: no.

## Error per account (check output)

```
@idlynews (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYNEWS, or add the shared network secret
@idlytech (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYTECH, or add the shared network secret
@idlyhype (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYHYPE, or add the shared network secret
@idlyautomotive (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYAUTOMOTIVE, or add the shared network secret
@idlynerd (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYNERD, or add the shared network secret
ACCESS PROBLEM (shared token): Meta got no valid shared access token. In the Claude cloud environment, add the network secret for graph.facebook.com (RUNBOOK.md, 'Meta access'); elsewhere set IG_SYSTEM_TOKEN
```

## What to do

1. Open the Claude cloud **environment this scheduled task runs in** and check that its *Environment
   variables* has all five `IG_TOKEN_IDLY…` names spelled exactly like that. If you added them in a
   different environment, or after this session started, they won't show up here. New values only reach
   sessions started afterwards.
2. Then run `python3 pipeline/publish.py check` again in a fresh session. Each account should say `ok`
   with its host, id and posts used. Commit `state/accounts.json` if the check updates it.
3. Until then, the twice-daily runs will skip every account (RUNBOOK: "no access" means skip).
