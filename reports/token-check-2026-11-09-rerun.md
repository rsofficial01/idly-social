# Token check re-run: 9 Nov 2026

Re-run of the connection check for Instagram posting, after the five `IG_TOKEN_IDLY…` variables were
reported as added to the Default cloud environment. **Nothing was posted.** The earlier report,
[token-check-2026-11-09.md](token-check-2026-11-09.md), is unchanged.

- Command: `python3 pipeline/publish.py check --no-refresh`
- Run at: 2026-11-09 18:30 UTC (00:00 IST, 10 Nov), scheduled Claude cloud session (manual re-fire)
- Environment: the session reports environment type `cloud_default` (the Default cloud environment). It
  doesn't expose the environment's display name.
- This session's container started at **18:28:19 UTC**. The re-fire was delivered into that same running
  session, and a container only picks up environment variables when it starts.
- Exit code: 1 (not ok)
- Graph API: v27.0
- API calls made: one, `GET graph.facebook.com/v27.0/me?fields=id,name` (shared-token fallback). It
  failed, so discovery stopped there. No call went to `graph.instagram.com`, because no account had its own
  token.
- `state/accounts.json`: **not changed** (no ids filled in or confirmed), so it isn't part of this commit.

## Variables present in this session

| Variable | Present |
|---|---|
| `IG_TOKEN_IDLYNEWS` | no |
| `IG_TOKEN_IDLYTECH` | no |
| `IG_TOKEN_IDLYHYPE` | no |
| `IG_TOKEN_IDLYAUTOMOTIVE` | no |
| `IG_TOKEN_IDLYNERD` | no |
| `IG_SYSTEM_TOKEN` | no |

None of them is defined, not even as an empty value.

## Result: all five accounts failed, same as 18:05 and 18:29

| Account | Present | Host that worked | IG user ID / username returned | Posts used in 24 h | Status |
|---|---|---|---|---|---|
| @idlynews | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456330541050) | unavailable | no access |
| @idlytech | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456360777255) | unavailable | no access |
| @idlyhype | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456251940953) | unavailable | no access |
| @idlyautomotive | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456459864048) | unavailable | no access |
| @idlynerd | no | none (graph.facebook.com tried, shared fallback) | none (cached, unverified: 17841456588019165) | unavailable | no access |

Meta answered:

> GET graph.facebook.com/me -> HTTP 400, code 2500: An active access token must be used to query
> information about the current user.

## Error per account (check output)

The output had no token text in it (nothing to redact).

```
@idlynews (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYNEWS, or add the shared network secret
@idlytech (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYTECH, or add the shared network secret
@idlyhype (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYHYPE, or add the shared network secret
@idlyautomotive (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYAUTOMOTIVE, or add the shared network secret
@idlynerd (shared token on graph.facebook.com): no access: set IG_TOKEN_IDLYNERD, or add the shared network secret
ACCESS PROBLEM (shared token): Meta got no valid shared access token. In the Claude cloud environment, add the network secret for graph.facebook.com (RUNBOOK.md, 'Meta access'); elsewhere set IG_SYSTEM_TOKEN
```

## Likely cause and what to do

The variables didn't reach this session. The most likely reason is timing: this re-fire woke the
**existing** session, whose container started at 18:28:19 UTC. If the variables were saved after that,
this container can't see them, however many times it's re-fired.

1. Run the check from a **new** session in the Default environment, not by re-firing this one. A new
   session reads the variables when it starts.
2. If a new session still shows `no` for all five, check that the variables are saved under the Default
   environment's *Environment variables* (not under *network secrets* or a different environment).
3. Once they show up, `check` should say `ok` per account with host, id and posts used. Commit
   `state/accounts.json` if it changes.
