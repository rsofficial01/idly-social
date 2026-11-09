# RUNBOOK: idly daily Instagram run

You are the scheduled Claude session. Follow this file step by step. It runs twice a day:

| slot | time (IST) | looks back |
|------|-----------|------------|
| `am` | ~8:40 AM  | 14 hours   |
| `pm` | ~6:40 PM  | 14 hours   |

Each run posts **at most one card per account** (@idlynews, @idlytech, @idlyhype, @idlyautomotive,
@idlynerd). Skip an account when no story passes the rules or scores 12/14. Skipping is fine and expected.
Sports stories have no account yet. Leave them out.

## Hard rules (never break these)

1. **Secrets.** Meta tokens are environment variables (`IG_TOKEN_<ACCOUNT>`) and/or a network secret.
   Never print, echo, log, paste or commit a token. Don't run `env`, `printenv` or `set`, and never
   read or echo an `IG_TOKEN_*` or `IG_SYSTEM_TOKEN` variable yourself. Don't call `graph.instagram.com`
   or `graph.facebook.com` by hand (curl etc.): use the pipeline commands. They send tokens only in the
   `Authorization` header and never print Meta's raw responses (paging links and token refreshes can
   carry a token).
2. **The gate.** Nothing below **12/14** on the 7-check score goes out. Never use `--force-below-gate`.
   It is for a human doing a manual post, not for this run.
3. **Only this.** Publish only feed posts through `pipeline/run_day.py`. No stories, reels, comments, DMs,
   likes or follows. No other accounts.
4. **When unsure, skip** and say why in the summary.

## Editorial rules

- **No gossip or personal life.** No celebrity family, babies, pregnancies, relationships, weddings,
  divorces, Botox or looks, "shares photos", birthday or festival greetings, trolling, feuds. The fetch step
  blocks the obvious ones and flags borderline ones `[REVIEW]`. You decide on flagged ones, and a
  festival-greeting or reaction story is a skip.
- **Multiple sources.** `source_count ≥ 2` (fetch enforces this). Don't add facts that only one outlet
  reported.
- **"Alleged"** for anything unproven: charges, accusations, claims. Say who claims it ("police say",
  "the company says"). Skip allegations about private individuals. Charges against public figures need
  `source_count ≥ 3`.
- **No engagement bait.** No "tag a friend", "comment YES", "like if", "share this", "double tap",
  "follow for more", "link in comments", "you won't believe", and no "Send this to…", "Save this" or
  "forward this" lines either (founder's rule, 9 Nov). One genuine question is fine.
- **No "AI"-hype wording.** No game-changing, revolutionary, mind-blowing, groundbreaking, unleash,
  supercharge, AI-powered, "the future is here". State what the thing does.
- **No promises** you can't keep ("Part 2 tomorrow at 8").
- **Never invent facts.** Every number, date, price and name must come from the idly article.
- Write in Indian English. Use ₹ and Indian number style where the story does (₹2,000 crore), and IST dates.

## Image rules

- Use only **official media-kit or press images** (the company's or brand's newsroom or press page),
  **Wikimedia Commons** with a free licence (CC0, public domain, CC BY, CC BY-SA), or **Unsplash**.
  Always credit them.
- **Never** use photos from other news outlets (in the API's `image_credits`, `origin: "outlet"` means
  never). Never use watermarked images.
- **Never use photos of real, identifiable public figures.** That means no politicians, actors, athletes,
  CEOs or creators, and no film posters or stills with actors in them. Use the object, product, place,
  vehicle or a neutral scene instead: the car from the press kit, the city skyline, the headphones.
- **Look at every image before you use it** (open it with the Read tool): check there is no watermark,
  no identifiable person, that it matches the story, and that it is at least ~1080 px wide.
- Record where it came from: `photo_source.page` (the page with the licence), `licence`, `author`, and
  `viewed: true`.
- No compliant photo? Skip the account ("no usable photo").

## Card copy

| field        | rule |
|--------------|------|
| `tag`        | CAPS, 2–3 words, e.g. `TELECOM · INDIA` |
| `stat`       | a number or date, e.g. `₹10,000`, `376`, `13 NOV` |
| `stat_label` | ≤ 8 words, says what the stat is |
| `headline`   | ≤ 10 words |
| `bullets`    | 2–3 bullets, each ≤ 9 words |
| `photo`, `photo_credit` | local path in `_work/…/photos/`, and the credit as shown on the card |

## Caption

```
<fact line(s): what happened, the key number, when/where, who it affects>

<one genuine question from readers' own lives>

Full story on idly.news (link in bio).

#Tag1 #Tag2 #Tag3 #idlytech                             <- 4–5 hashtags in total

Photo: <author> / <source>, <licence>
```

- Exactly one `?` in the whole caption. Don't add a "From N reports" line.

## The 7-check score (gate: 12/14, aim for 14)

Score each check 2 (strong), 1 (partly) or 0 (missing). Be honest. A generous score defeats the gate.

| key        | check | 2 means |
|------------|-------|---------|
| `hook`     | Hook | The stat and headline stop a scroll in about a second: a specific, surprising number or a clear stake. |
| `read`     | Read-through | Every line earns the next. No filler. |
| `send`     | Send reason | A specific person would forward it because of what it says. Never ask for the send in the caption. |
| `keep`     | Keep reason | Worth saving: dates, prices, deadlines, specs, eligibility, where/when. Never ask for the save. |
| `reply`    | Reply prompt | One genuine question from readers' own lives, not bait. |
| `original` | Original | Our synthesis and design, photo credited, nothing reposted. |
| `alone`    | Stands alone | The card makes complete sense with no caption or context. |

Loop: score the card, then rewrite the weak checks (sharper stat, tighter headline, a real send reason,
a keepable detail, a better question). **Never invent facts to raise the score.** Score it again. If it
still can't reach 12, try the next candidate for that account. If none reach 12, skip the account and
record the best story with its best score.

---

## Steps

All commands run from the repo root. Set these once:

```bash
export DATE=$(TZ=Asia/Kolkata date +%F)
export SLOT=$( [ $(TZ=Asia/Kolkata date +%H) -lt 14 ] && echo am || echo pm )
R="python3 pipeline/run_day.py --date $DATE --slot $SLOT"
W=_work/$DATE-$SLOT
```

### 1. Get the repo

```bash
git clone https://github.com/rsofficial01/idly-social.git && cd idly-social   # or: git pull --rebase
pip install -r requirements.txt     # plus whatever cardkit/ needs
python3 -m unittest discover -s tests -t . -q
```

### 2. Fetch candidates and check Meta access

```bash
$R fetch       # -> $W/candidates.json (top 5 per account, [REVIEW] flags, excluded list)
$R check       # -> $W/check.json (per account: token, host, id, publishing limit, days left)
```

For each account `check` uses its own token (`IG_TOKEN_<ACCOUNT>`) if set, else the shared one. It
confirms the token or id is that account, saves ids and hosts to `state/accounts.json`, reads the
publishing limit (we stop at 25 posts per 24 h) and, for `graph.instagram.com` tokens, the days left.

- An account marked **token problem**, **not found**, **not reachable**, **no access** or **publishing
  limit reached**: skip it, with that reason.
- **token expires in N days**: still post, and put it in the summary so the founder makes a new token.
- If **no** account is reachable: still do steps 3–6. Then run `$R dry-run` in place of steps 7–10,
  commit nothing, and send the summary marked DRY RUN with the access problems in it. The founder has
  to fix the setup ([Meta access](#meta-access-one-time-setup)); you can't.

### 3. Pick a story per account

Go down that account's candidates in rank order. For each one, read the full article:
`curl -s https://api.idly.news/api/v1/articles/<id>/`, which has the `content` field. Apply the
editorial rules. Don't post the same story on two accounts. Prefer stories with a hard number or date.

### 4. Find and check a photo

Follow the image rules. Save it as `$W/photos/<account>-<id>.jpg`, and **open it to look at it**.

### 5. Write the card and caption, then score them (loop until 14, or skip below 12)

### 6. Write `$W/cards.json`

```json
{
  "date": "2026-11-09",
  "slot": "pm",
  "posts": [
    {
      "account": "idlytech",
      "story_id": 1664,
      "title": "Jio launches ₹10,000 prepaid plan with three-year validity",
      "cards": [{
        "tag": "TELECOM · INDIA",
        "stat": "₹10,000",
        "stat_label": "three years of Jio on one recharge",
        "headline": "Jio's new plan runs three years on one recharge",
        "bullets": ["2.5GB a day, unlimited calls, 100 SMS", "Works out to about ₹278 a month"],
        "photo": "_work/2026-11-09-pm/photos/idlytech-1664.jpg",
        "photo_credit": "Photo: Jane Doe / Wikimedia Commons, CC BY-SA 4.0"
      }],
      "caption": "…",
      "alt_text": "A smartphone showing a recharge screen, with the card text: …",
      "collaborators": [],
      "photo_source": {"page": "https://commons.wikimedia.org/wiki/File:…", "licence": "CC BY-SA 4.0",
                       "author": "Jane Doe", "viewed": true},
      "score": {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 2, "alone": 1,
                "total": 13, "notes": "alone: needs the caption to explain what Canva Pro Lite is"}
    }
  ],
  "skipped": [
    {"account": "idlyhype", "story_id": 1614, "title": "BTS' V sends Diwali wishes…", "best_total": null,
     "reason": "festival greeting / celebrity reaction: gossip rule"},
    {"account": "idlynerd", "story_id": 1694, "title": "…", "best_total": 10,
     "score": {"hook": 2, "read": 2, "send": 1, "keep": 1, "reply": 1, "original": 2, "alone": 1, "total": 10,
               "notes": "…"},
     "reason": "best rewrite scored 10/14: no keepable detail, weak send reason"}
  ]
}
```

- Every account needs an entry in `posts` or in `skipped`, with a reason. The report flags any account
  with no decision.
- `score.total` must equal the sum of the 7 checks, and `notes` must say why each weak check is weak.
- Captions never ask for a send or a save ("Send this to…", "Save this"). The publisher rejects them.
- `collaborators` is optional and defaults to none (leave it `[]` or out). It takes up to 3 Instagram
  usernames, and Instagram invites them as collaborators on the whole post. Only add one when the founder
  asked for it for that post (e.g. a sister idly account). Never the posting account itself.
- If nothing goes out at all, write `"posts": []` and still run steps 7 and 11 so the report exists.

### 7. Render and stage

```bash
$R render      # validates everything (copy limits, caption rules, photo record, 12/14 gate),
               # renders with cardkit, and copies the JPEGs to posts/$DATE/<slot>-<account>-<id>.jpg
```

If it prints problems, fix `cards.json`, or move the post to `skipped`, and run it again. Then **open
every JPEG in `posts/$DATE/`** and check that the text fits, nothing is cut off, and the photo looks right.

### 8. Commit and push the images (the repo is public; that is how Instagram fetches them)

```bash
git add posts/$DATE
git commit -m "posts: $DATE $SLOT"
git push origin HEAD:main
```

If the push fails for auth or permission reasons, call the **`add_repo`** tool with owner
`rsofficial01`, repo `idly-social` and access `"push"`, then push again. If it still fails, don't publish.
Go to step 11 and say so in the summary.

### 9. Wait until the images are public

```bash
$R wait-urls   # polls raw.githubusercontent.com until each URL is HTTP 200 image/jpeg (max 15 min)
```

If a URL never goes live, `publish` skips that account and the report says why.

### 10. Publish

```bash
$R publish     # per account: right account? quota < 25/24h? container -> FINISHED -> publish -> permalink
```

It uses each account's own token on the host `check` remembered (`graph.instagram.com` or
`graph.facebook.com`, Graph API v27.0), or the shared token on `graph.facebook.com`.

It writes `state/posted.json` after every post. Re-running it is safe: an account already posted in this
slot is skipped.

### 11. Report, commit, push

```bash
$R report      # -> reports/$DATE-$SLOT.md, and prints the summary
git add state/posted.json state/accounts.json reports/
git commit -m "run: $DATE $SLOT"
git pull --rebase origin main && git push origin HEAD:main
```

**This push matters.** `state/posted.json` is how the next run knows what was already posted. Retry
until it lands. If it never lands, say so in the summary.

### 12. Send the summary

End the session with a short message: the summary that `report` printed. It covers what went live
(with permalinks and scores), what was skipped and why (with best scores), and any Meta access problem
or token about to expire. Example:

```
idly Instagram, Mon 9 Nov 2026, pm run (6:40 PM IST)
Live: @idlytech 13/14 https://www.instagram.com/p/… · @idlyautomotive 12/14 https://www.instagram.com/p/…
Skipped: @idlynews: no story reached 12 (best 11/14) · @idlyhype: festival greeting (gossip rule) · @idlynerd: no usable photo
Access: @idlynerd: token expires in 6 days: generate a new one in the Meta dashboard and update IG_TOKEN_IDLYNERD
```

## When things go wrong

| problem | do this |
|---------|---------|
| idly API down | Retry once after 5 min, then skip the run and say so. |
| cardkit fails | Skip the affected accounts and say so. Don't hand-make cards. |
| One account fails at Instagram | The others continue. The report shows `failed` and Meta's error. |
| Quota hit (25 posts in 24 h) | That account is skipped. |
| `token problem: IG_TOKEN_X works on neither host` | The account's token is expired, revoked or mistyped. Skip the account; the founder generates a new token in the Meta dashboard and updates `IG_TOKEN_X`. |
| `IG_TOKEN_X belongs to @y` | The token in that variable is for another account. Skip it; the founder swaps the values. |
| `token expires in N days` | Still post. Put it in the summary: the founder generates a new token and updates `IG_TOKEN_X` (it reaches the next new session). |
| `ACCESS PROBLEM (shared token)` / `no access` / code 2500 | Only matters for accounts with no `IG_TOKEN_X`: there is no shared token either (no network secret, or it's in another environment). Skip those accounts and say so. |
| `not found by discovery` | Shared token only: none of the lookups returned that username. `check` lists each lookup and its error. The founder sets that account's `IG_TOKEN_X`, or adds the account as an asset of the system user. |
| Permission error (code 10 or 200) | A lookup or a post needs a permission the login configuration lacks (see the note under [Meta access](#meta-access-one-time-setup)). Put Meta's message in the summary. |
| "appsecret_proof" error | The Meta app has *Require app secret* switched on, which a network secret can't satisfy. The founder switches it off in the app's Advanced settings. |
| Crash halfway | Re-run the step. `render` overwrites the plan, `publish` skips posted accounts, `report` rewrites the report. |

---

## Meta access (one-time setup)

For the founder, not the scheduled run. The scheduled run can't change any of this.

**What Meta gives us.** The Meta app **idly publisher** (app id `1533702778969280`, business portfolio
`1165348135833967`) uses **API setup with Unified login** (Meta no longer offers *API setup with
Instagram login* to newer apps). Its step *2. Generate access tokens* lists each Instagram account with
its own **Generate token** button: **one token per account**. The pipeline uses those first, from
environment variables. A shared system-user token (below) is only the fallback for an account without
its own token.

The Instagram account ids are already in `state/accounts.json`:

| account | Instagram id |
|---|---|
| @idlynews | 17841456330541050 |
| @idlytech | 17841456360777255 |
| @idlyhype | 17841456251940953 |
| @idlyautomotive | 17841456459864048 |
| @idlynerd | 17841456588019165 |

### Per-account tokens (environment variables)

1. **[browser]** Meta app dashboard → **idly publisher** → *API setup with Unified login* →
   *2. Generate access tokens*. Select **Generate token** next to an account and copy it. Repeat for
   each of the five.
2. **[browser]** Open [claude.ai/code](https://claude.ai/code), open the **environment selector** (the
   first control in the row under the message box), hover over the environment the scheduled idly run
   uses and select its **gear (settings) icon**.
3. **[browser]** In **Environment variables**, add one `KEY=value` per line (no quotes needed, no spaces
   around `=`):

   ```text
   IG_TOKEN_IDLYNEWS=<token for @idlynews>
   IG_TOKEN_IDLYTECH=<token for @idlytech>
   IG_TOKEN_IDLYHYPE=<token for @idlyhype>
   IG_TOKEN_IDLYAUTOMOTIVE=<token for @idlyautomotive>
   IG_TOKEN_IDLYNERD=<token for @idlynerd>
   ```
4. **[browser]** Select **Save changes**. New values reach every **new** session, so the next scheduled
   run picks them up. (A session that is already open keeps its old values until it restarts.)
5. **[Claude Code]** Start a new session in that environment and ask Claude to run
   `python3 pipeline/publish.py check`. Each account should say `ok`, with the host its token works on
   (`graph.instagram.com` or `graph.facebook.com`) and, for `graph.instagram.com` tokens, the days left.
   Then commit `state/accounts.json` (ids and hosts only, never tokens).

To replace a token later (expired, or `check` warns it expires within 10 days): generate a new one in
the dashboard, edit that line in **Environment variables**, **Save changes**.

Keep in mind: anyone using that environment, and every session in it, can read environment variables.
The pipeline never prints them and the scheduled run is told never to look at them, but a network secret
is the only option a session truly can't read. Five tokens for one host can't be told apart by the
proxy, which is why per-account tokens are environment variables.

`check` reads the expiry by calling `graph.instagram.com/refresh_access_token` with the token in the
header. If Meta answers with the same token, its `expires_in` is the days left (and that call extended
it). If Meta answers with a different token, that one is thrown away unsaved and the expiry is reported
as unknown. To skip this call, use `check --no-refresh`.

### Shared token (optional fallback)

Only needed for an account that has no `IG_TOKEN_...` of its own. Facebook Login for Business can also
give **one system-user access token for all five accounts** (configuration token type *System-user
access token*, never expires; business assets: the Instagram accounts; permissions `instagram_basic`
and `instagram_content_publish`; the template also adds `ads_management`, `ads_read`,
`instagram_manage_comments` and `instagram_manage_messages`, which we don't use). The pipeline calls
`graph.facebook.com` with it.

**Store the shared token as a network secret.** It then never enters a Claude session: Anthropic's agent
proxy adds it to each request for `graph.facebook.com` after the request leaves the session.

1. **[browser]** Open [claude.ai/code](https://claude.ai/code).
2. **[browser]** Open the **environment selector** (the first control in the row under the message box).
   Hover over the environment the scheduled idly run uses and select its **gear (settings) icon**. The
   *Edit cloud environment* dialog opens.
3. **[browser]** In the **Network secrets** section, select **Add secret**.
4. **[browser]** Keep **Secret type: Bearer** and fill in:
   - **Name**: `Meta idly publisher`
   - **Allowed websites**: `graph.facebook.com`
   - **Custom headers**: Name `Authorization`, Prefix `Bearer`, and paste the system-user access token as
     the **Value**.
5. **[browser]** Select **Add**. It saves straight away (no *Save changes* needed), and the value can't be
   viewed again. To change it later, delete the secret and add it again.

On a Team plan without an organization admin role, **Add secret** opens a shorter form instead: **Host**
`graph.facebook.com`, **Secret type** *Token*, and the token as the **Value**.

Do **not** put the shared token in *Environment variables* as well: the network secret is the version
no session can read. The scheduled task must run in the **same environment** that has the secret.

If an account's own token turns out to work only on `graph.facebook.com` (`check` shows the host) and a
network secret for `graph.facebook.com` also exists, the proxy may put the shared token on that
account's requests instead. Tokens on `graph.instagram.com` are not affected.

**Check it worked.**

6. **[Claude Code]** Start a session in that environment and ask Claude to run
   `python3 pipeline/publish.py check`. You want `ok` for every account that uses the shared token, with
   an id and the posts used in the last 24 h. Then commit `state/accounts.json` (no tokens in it).
7. If it says `ACCESS PROBLEM (shared token)`, the secret isn't reaching Meta: check the host is exactly
   `graph.facebook.com`, the session runs in the environment that has the secret, and the secret isn't
   marked **Not sent** in the list (the note under it says why).

**How `check` finds the accounts.** It tries these in order and caches whatever works in
`state/accounts.json`:

1. `GET /me?fields=id,name`: who the token is (the system user).
2. `GET /me/assigned_instagram_accounts`: Instagram accounts assigned to the system user.
3. `GET /1165348135833967/owned_instagram_accounts`, then `GET /1165348135833967/instagram_accounts`:
   Instagram accounts that are assets of the business portfolio.
4. `GET /me/accounts?fields=instagram_business_account{id,username}`: accounts linked to a Facebook Page.

If a lookup fails with a permission error, `check` shows Meta's message. Meta's docs list
`pages_read_engagement` (and, for the business lookups, `business_management`) for Facebook Login apps.
If publishing or every lookup is refused for permissions, add those to the login configuration and
generate a new token. If no lookup works, the ids can go into `state/accounts.json` by hand
(`{"accounts": {"idlytech": {"id": "1784…", "username": "idlytech"}}}`). The pipeline still checks every
id with `GET /{id}?fields=id,username` before it posts.

**Outside the Claude cloud** (your own computer or a server) **[plain terminal]**:
`export IG_TOKEN_IDLYTECH=…` (and the others), and/or `export IG_SYSTEM_TOKEN=…`, in that shell only. The
code sends them only as the `Authorization: Bearer` header and never prints them.
