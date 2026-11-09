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

1. **Secrets.** The Meta token is a network secret: the agent proxy adds it to requests for
   `graph.facebook.com`, and you never see it. Don't look for it, and never print, echo, log, paste or
   commit a token. Don't run `env`, `printenv` or `set`. Don't call `graph.facebook.com` by hand (curl
   etc.): use the pipeline commands, which never print Meta's raw responses (Meta's paging links can
   carry the token).
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
  "follow for more", "link in comments", "you won't believe". One genuine question is fine. So is
  "Send this to [a specific person]".
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

Send this to <a specific person who would care>.        <- only if there is a real send reason

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
| `send`     | Send reason | A specific person would forward it, and the caption names who ("Send this to …"). |
| `keep`     | Keep reason | Worth saving: dates, prices, deadlines, specs, eligibility, where/when. |
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
$R check       # -> $W/check.json (finds the 5 account ids, reachable? publishing limit?)
```

`check` needs no token in the environment: the network secret supplies it. It finds each account's
Instagram id (and saves them to `state/accounts.json`), checks each id is the right account, and reads
the publishing limit (we stop at 25 posts per 24 h).

- An account marked **not found**, **not reachable** or **publishing limit reached**: skip it, with that
  reason.
- **ACCESS PROBLEM** (no account reachable): still do steps 3–6. Then run `$R dry-run` in place of
  steps 7–10, commit nothing, and send the summary marked DRY RUN with the access problem in it. The
  founder has to fix the setup ([Meta access](#meta-access-one-time-setup)); you can't.

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
- If `send` is 2, the caption must contain "Send this to …".
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

It calls `graph.facebook.com` (Graph API v27.0) with no credentials of its own; the network secret
adds them.

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
(with permalinks and scores), what was skipped and why (with best scores), and any Meta access problem.
Example:

```
idly Instagram, Mon 9 Nov 2026, pm run (6:40 PM IST)
Live: @idlytech 13/14 https://www.instagram.com/p/… · @idlyautomotive 12/14 https://www.instagram.com/p/…
Skipped: @idlynews: no story reached 12 (best 11/14) · @idlyhype: festival greeting (gossip rule) · @idlynerd: no usable photo
Access: @idlynerd: not found by discovery
```

## When things go wrong

| problem | do this |
|---------|---------|
| idly API down | Retry once after 5 min, then skip the run and say so. |
| cardkit fails | Skip the affected accounts and say so. Don't hand-make cards. |
| One account fails at Instagram | The others continue. The report shows `failed` and Meta's error. |
| Quota hit (25 posts in 24 h) | That account is skipped. |
| `ACCESS PROBLEM` / code 190 or 2500 ("An active access token must be used") | The network secret is missing, was added to a different environment, or the token was revoked. Dry run only; put it in the summary for the founder ([Meta access](#meta-access-one-time-setup)). |
| `not found by discovery` | None of the lookups returned that username. `check` lists each lookup and its error. The founder adds the account as an asset of the system user (or the login configuration), then you run `$R check` again. |
| Permission error (code 10 or 200) | A lookup or a post needs a permission the login configuration lacks (see the note under [Meta access](#meta-access-one-time-setup)). Put Meta's message in the summary. |
| "appsecret_proof" error | The Meta app has *Require app secret* switched on, which a network secret can't satisfy. The founder switches it off in the app's Advanced settings. |
| Crash halfway | Re-run the step. `render` overwrites the plan, `publish` skips posted accounts, `report` rewrites the report. |

---

## Meta access (one-time setup)

For the founder, not the scheduled run. The scheduled run can't see or change any of this.

**What Meta gives us.** The Meta app **idly publisher** (app id `1533702778969280`, business portfolio
`1165348135833967`) uses **API setup with Unified login** (Meta no longer offers *API setup with
Instagram login* to newer apps):

- Facebook Login for Business, with a configuration whose token type is a **system-user access token**
  that never expires.
- Business assets: the **Instagram accounts** @idlynews, @idlytech, @idlyhype, @idlyautomotive, @idlynerd.
- Permissions: `instagram_basic`, `instagram_content_publish`. The template also adds `ads_management`,
  `ads_read`, `instagram_manage_comments`, `instagram_manage_messages`; we don't use them.

That is **one token for all five accounts**. The pipeline calls `graph.facebook.com` with it.

**Store the token as a network secret.** It then never enters a Claude session: Anthropic's agent proxy
adds it to each request for `graph.facebook.com` after the request leaves the session.

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

Do **not** put the token in the environment's *Environment variables*: every session can read those.
The scheduled task must run in the **same environment** that has the secret.

**Check it worked.**

6. **[Claude Code]** Start a session in that environment and ask Claude to run
   `python3 pipeline/publish.py check`. You want `ok` for all five accounts, with an id and the posts used
   in the last 24 h. Then commit `state/accounts.json` (ids and usernames only).
7. If it says `ACCESS PROBLEM`, the secret isn't reaching Meta: check the host is exactly
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
`export IG_SYSTEM_TOKEN=…` in that shell only. The code sends it only as the `Authorization: Bearer`
header and never prints it.
