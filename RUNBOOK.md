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
3. **Only this.** Publish feed posts through `pipeline/run_day.py` (or the official image lane), and a feed
   post's Instagram Story with `pipeline/publish.py story` ([Stories](#stories-916)). Reels only through the
   lane's reel queue (`lane.py request-reel`, [Reels](#reels-916)): a session never renders or posts a reel itself.
   No comments, DMs, likes or follows. No other accounts.
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
  "forward this" lines either (founder's rule, 9 Nov). No comment prompts: "Tell us below", "Tell us in the
  comments", "Let us know below / in the comments". One genuine question is fine.
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
- No compliant photo? Skip the account ("no usable photo"), or, when the story needs an official
  publicity image (a film's trailer still, a licensed agency photo of an event, a company's own press image),
  hand it to the [official image lane](#official-image-lane): you write a spec, and code in GitHub Actions
  fetches the image from an allowlisted official source. You never download, crop or composite those
  images yourself.

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
- **The credit line is always the last line** (`Photo: …`, `Image: …`, or a wire agency's own form such as
  `AP Photo/<Photographer>`, `Photo: PTI`, `ANI Photo`, `Photo: IANS`). The publisher rejects a caption
  that doesn't end with it.

## Credits on the cards (cardkit `hype` template)

- **Cover:** the vertical credit on the right edge is always filled: cardkit refuses a cover without
  `photo_credit`.
- **Every other slide** gets a quiet one-line credit/source line just above the footer rule (16px, white
  at 45%). On a slide that shows an image it is that image's credit; on text slides it is the story's main
  sources. Give every hype post `"sources": ["CNBC", "Yahoo Finance"]` (the outlets the idly article draws
  on) and cardkit writes `Sources: CNBC, Yahoo Finance` on its text slides. A slide can override it with
  `"credit_line": "Source: SIAM"`. The render report says per slide what it shows and whether it collides
  with anything (`credit_collision`); look at it on every render.

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

## Cover style (Rahul, 10 Nov 2026)

Every cover looks like the @idlynews Oxford museum post: **the photo fills the whole 1080x1350 frame** and the
dark gradient behind the headline makes it stand out. **Never** a boxed/letterboxed image on a blurred or darkened
copy of itself, never blurred side-fills or extended backgrounds (the @idlyautomotive Alto K10 post was rejected for
this). Sources should be high-res (900px wide or more). A small source may be enlarged up to 2x:
`python3 -m pipeline.framing <photo> <work_dir>` plans the full-bleed 4:5 crop (faces kept whole and clear of the
logo and headline), enlarges and sharpens it when needed, and prints the photo/focal/zoom for the cardkit cover
slide. If it says the photo can't be framed full-bleed, use a different, larger image of the same subject.
The lane does the same automatically and falls through to the next image attempt.

## Stories (9:16)

Rahul's go-ahead (10 Nov 2026): every feed post may get an **Instagram Story**, one 1080x1920 card made from the same
post dict as the hype cover (`cardkit/vertical.py`).

> **Switch:** stories and reels go live only while `config/formats.json` says so (`{"stories": true, "reels": true}`).
> Today both are `false` (Rahul reviews the format first): `publish.py story`/`reel` refuse, and the lane logs
> `stories paused (config/formats.json)` / `reels paused (…)`, posts the feed post as usual and keeps approved reels
> waiting. A missing file means paused. Only Rahul turns them on.

- **The look.** The photo fills the width at the top: the cover's own 4:5 full-bleed crop (same photo, focal and
  zoom), or taller (up to 1080x1440) when the photo allows. It fades through a smooth gradient into the dark brand
  background (#0A0A0A), where the text sits: a small `@account` kicker, the cover's Title Case headline (Inter,
  left-aligned) and the footer (date, idly.news). The logo sits top-centre over the photo and the photo credit runs
  up the right edge, as on covers. Every text line starts at the same left edge (x=64). Nothing sits in Instagram's
  UI zones: text stays between y 220 and y 1600 of the 1920 px frame, and no text is under 30 px. **Never** a boxed
  photo on a blurred or darkened copy of itself, never side fills.
- **Lane posts: automatic.** `render-pending` makes `queue/rendered/<slug>/story.jpg`, with the photo re-planned for
  the 9:16 window (faces in y 380-880, clear of the logo and the text). If the story can't be framed or laid out, the
  post goes ahead without one and `render_report.json` says why. The reviewer looks at `story.jpg` with the slides;
  `lane.py approve <slug> --score-file F --no-story` posts the feed post without it, and `"story": false` in a spec
  turns it off. `publish-approved` posts the story right after the feed post.
- **Hourly posts** (your own photos: never a person; see the image rules):
  1. Make the card from the hype post dict you rendered the cover with (save it as JSON in `$W`, photo paths as you
     used them): `python3 -m cardkit.vertical story $W/<account>-post.json posts/$DATE/<folder>/story.jpg`. It
     prints the problems and exits 1 when the layout breaks a rule (text doesn't fit, collisions, UI zones, uneven
     left edges): fix the copy or skip the story. **Open `story.jpg` and look at it.** To plan the 9:16 photo
     window yourself, `python3 -m pipeline.framing <photo> $W/vertical --vertical` prints a photo, focal, zoom and
     photo_h for the cover slide's `"vertical"` key.
  2. Commit and push `story.jpg` with the feed images (step 8). Meta fetches it from raw.githubusercontent.com.
  3. Once the feed post is live (step 10):
     `python3 pipeline/publish.py story --account <account> --image posts/$DATE/<folder>/story.jpg`. It waits until
     the image is public, posts it, links it to the feed post from the same folder and records it in
     `state/posted.json` as `"type": "story"` (`"story_of"`: the feed post's media id). `--dry-run` prints the API
     calls and posts nothing.
  4. **A story is never worth a feed post.** If it fails, the feed post stands: put `story failed: <reason>` in the
     summary and carry on. Don't retry more than once.
- Stories never take the last 5 of the 25 posts a day: Meta's docs don't say whether stories count toward the
  publishing limit, so `publish.py story` stops at 20 and the feed keeps its room.

## Reels (9:16)

A silent 10-14 second **Reel** of a post that is already live, made and posted by the lane in GitHub Actions
(`cardkit/reel.py`): the photo may show people, so a session never renders one.

- **What it is.** Motion graphics, not a slide show (Rahul, 10 Nov 2026: "a reel is what you made on Jensen
  Huang", the Nvidia counter clip). `reel.mp4`, 1080x1920, 30 fps, H.264 with a **silent** AAC track (Instagram
  wants an audio track; there is never anyone else's music or audio). Chrome films one HTML page frame by frame
  (a JS `setT(t)` poses every element) and ffmpeg encodes the JPEG frames (`-preset veryfast`), about 20-60 s per
  reel. The scenes, none longer than 3.5 s:
  1. **Cover** (3.2-3.5 s): the full-width photo pushes in and drifts under the gradient, the text and the
     logo/credit/footer drift at their own speeds (parallax), the `@account` kicker types in, the Title Case
     headline rises line by line from behind its own mask, 120 ms apart. The vertical photo credit stays up.
  2. **1-2 detail slides** (3.4-3.5 s each), each a panel that **pushes up** over the last: the stat **counts up**
     with an ease-out in its own format (23,747 · 2,24,000 · +86% · −4.27% · ₹2.69 lakh · $192B), fades in from
     its first real value (never a "0") and lands on the exact stat; a year, date or score doesn't count, it
     rises in. The label rises line by line, the rule draws across, bullets slide in one by one with their
     markers, and the Sources line and footer are there. A detail slide may carry a **chart** for a ranked list
     or comparison: `"chart": [["WagonR", 23747], ["Brezza", 22436], …]`, optional `"chart_unit": "Units sold"`
     (values are numbers, or stat-like strings in one unit; 2-8 rows). Bars grow from zero 120 ms apart while
     their values count up; the leader is ember. In a lane spec, `chart` goes on a `detail_slides` entry that also
     has a stat or bullets (the feed slide shows those; only the reel draws the chart).
  3. **End card** (2-3 s) after a hard cut: the account's logo scales in with a small overshoot, then idly.news
     and the handle rise in.

  Nothing ever sits still (slow drifts on every hold), and transitions are pushes or a cut, never crossfades.
  12.1 s with two detail slides, 10 s with one; **a reel needs at least one detail slide** (request-reel says
  so). Same look as the story (full-width photo fading into #0A0A0A, Inter and Playfair Italic, one left edge,
  no text under 30 px), but a reel's own safe zone: Instagram's caption, username and audio overlay covers the
  bottom ~540 px of a reel and its like/comment/share buttons sit at x ≥ 960 from y ~1000 down, so every frame
  keeps its text in **y 220-1380** and clear of that column (`REEL_SAFE_ZONE` in `cardkit/vertical.py`, the one
  setting to change if Instagram moves its UI). Detail scenes fill the zone: big type (label 52 px or more,
  bullets 40 px or more), no empty band over 220 px, no lone word on a last line. The renderer checks every scene
  settled and at its furthest drift, every counter's first visible and last value, and that no run of identical
  frames is longer than 0.8 s; anything wrong rejects the reel with the reason. `reel_cover.jpg` (the settled
  cover frame) is the Reels-tab cover. (Renderer development only, on a photo with no people such as
  `tests/fixtures/commons_wagonr.jpg`: `python3 -m cardkit.reel post.json OUT_DIR --previews --sheet sheet.jpg`.
  A posting run never renders a reel; the lane does.)
- **Ask for one** (any run, once the feed post is live):
  1. Write the reel's caption with the same caption rules, but **leave the credit line off**: the lane appends the
     post's own credit. Score the reel on the 7 checks (12 or more, honestly: a reel isn't better than its post).
  2. Queue it:

     ```bash
     python3 pipeline/lane.py request-reel --source lane:<slug> \
         --caption-file $W/<account>-reel-caption.txt --score-file $W/<account>-reel-score.json [--details 1,2]
     ```

     `--source lane:<slug>` for a lane post (`queue/posted/<slug>/`); the lane fetches the same official image again
     and refuses if it changed. For an hourly post use `--source posts/$DATE/<folder>`: that folder needs
     `post.json` (the hype post dict you rendered, with the cover photo's path relative to the repo root) and the
     photo itself, committed (your own non-people photos only). `--details` picks the detail slides (default: the
     first two). The command checks everything it can (the source is posted, the account, the caption rules with
     the post's credit, the score, one reel per post) and prints the git line.
  3. Commit and push `queue/reels/pending/reel-<name>.json`. lane-render renders it within about 10 minutes into
     `queue/reels/rendered/reel-<name>/`: `reel.mp4`, `reel_cover.jpg` and preview stills at 0.5 s, 4 s, 7 s and the
     last frame. Anything wrong (layout, framing, caption, a changed image) goes to `queue/reels/rejected/` with
     the reasons.
- **Review** (the reviewer step, same gate): `python3 pipeline/lane.py show reel-<name>` gives the blind packet. Open
  `reel_cover.jpg` and every `preview_*.jpg`, check the layout, the photo and the caption, score the 7 checks, then
  `lane.py approve reel-<name> --score-file F` (the lower score must be 12 or more) or `lane.py reject reel-<name>
  --reason "…"`. Commit and push `queue/` as for any review.
- **Publishing.** lane-publish posts approved reels after the feed posts: one post per account per run, 30 minutes
  after the account's last post, only while fresh (8 hours from the request unless `--evergreen`), never twice. It
  records `"type": "reel"` in `state/posted.json` and `posted reel · …` in `reports/lane-<date>.md`.
- **Where Meta fetches the video.** From raw.githubusercontent.com, like the images. That host serves `.mp4` as
  `application/octet-stream`, and Meta's docs neither promise nor refuse that, so if the container ends in `ERROR`
  the publisher tries again from jsDelivr's free CDN pinned to the commit (`cdn.jsdelivr.net/gh/…@<commit>/…`, served
  as `video/mp4`), then (for graph.facebook.com tokens only) Meta's resumable upload of the file itself. The report
  line says which host worked (`via raw`, `via jsdelivr`, `via resumable`).

## Review while building (not at the end)

The founder's rule (10 Nov): "have the reviewer review every text and image while building so there's no bad
product that comes out." Re-doing finished posts after an end-of-line review wastes hours. So one reviewer
works **alongside** the build, at four short gates, and nothing moves to the next stage until its gate passes.

**The reviewer.** At the start of the run, start ONE fresh reviewer with the Agent tool (it never sees your
self-scores) and keep it for the whole run: send each gate to it with SendMessage (if SendMessage isn't
available, start a short fresh reviewer per gate with the same instructions). Give it the rubric
(the 7-check score below), the editorial, image and caption rules from this file, and: "Be strict; a
generous score defeats the gate. Answer each gate with PASS or FIX: <exact fix>, in one short message."

**Gate 1, the angle (before any writing).** Send the 3 strongest candidates per account: id, title, the key
fact or number, the proposed hook, who would send it, what's worth keeping. The reviewer predicts the
ceiling of each (hook, send, keep, original). Drop anything whose ceiling is under 12; build only the best.
This is where most weak posts die, for free.

**Gate 2, the words (before rendering).** Send the cover headline, slide copy and full caption, plus the
article text. The reviewer checks every fact against the article, allegation wording, Title Case, the
one-question rule, bait (send/save/tag/comment prompts, "Tell us below"), credit and Sources lines, and
that each slide stands alone (no "He's…" without a name). Also run
`python3 -c "from pipeline import editorial; ..."` (post_problems) yourself first: the code catches the
mechanical rules so the reviewer spends its time on judgment.

**Gate 3, the picture (before compositing).** Send the photo you plan to use (or the lane spec's image
plan) with its source page and licence, and the planned focal point and zoom. The reviewer checks rights,
watermarks, identifiable people, that it matches the story, and that the subject will sit clear of the
logo (top ~170px) and the headline block (bottom ~45%). (Lane images: the code fetches and frames them;
the reviewer checks them at Gate 4.)

**Gate 4, the finished card (quick).** Render, then send the slide images. Because Gates 1–3 passed, this
is a look for layout problems (overflow, collisions, cut-off subjects, legibility at phone size) plus the
final 7-check score. The post's score is the LOWER of yours and the reviewer's; publish at 12/14 or above.

A FIX at any gate is fixed on the spot and re-sent to that gate only; earlier gates don't re-run unless the
fix changed what they checked. Work on different accounts in parallel where you can.

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

Every run, hourly ones included: read `state/learnings.md` (the weekly numbers report's guidance) before choosing stories.

Go down that account's candidates in rank order. For each one, read the full article:
`curl -s https://api.idly.news/api/v1/articles/<id>/`, which has the `content` field. Apply the
editorial rules. Don't post the same story on two accounts. Prefer stories with a hard number or date.

### 4. Find and check a photo

Follow the image rules. Save it as `$W/photos/<account>-<id>.jpg`, and **open it to look at it**.

### 5. Write the card and caption, then score them (loop until 14, or skip below 12; run Gates 1–3 of "Review while building" as you go, Gate 4 after rendering)

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
For each post's story, make `story.jpg` now ([Stories](#stories-916), step 1) and look at it too.

### 8. Commit and push the images (the repo is public; that is how Instagram fetches them)

```bash
git add posts/$DATE
git commit -m "posts: $DATE $SLOT"
git push origin HEAD:main
```

`git add posts/$DATE` includes any `story.jpg`.

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

Then post each live feed post's story: `python3 pipeline/publish.py story --account <account> --image
posts/$DATE/<folder>/story.jpg`. A failed story is a line in the summary, never a reason to touch the feed post.

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

## Official image lane

For posts that need an **official publicity image**: a film or series story (the official trailer still),
an event a licensed agency photographed (AP; PTI, ANI and IANS once their APIs are set up), or a company
story (the company's own newsroom image). These images may show real people, so the Claude session never
downloads, views, crops or composites them. Plain code does that in GitHub Actions, from allowlisted
official sources only. The session writes a **spec**; a later **reviewer** run approves or rejects the
rendered card.

```
you: queue/pending/<slug>.json ──► lane-render (Actions, every 10 min) ──► queue/rendered/<slug>/
                                    resolve → frame → cardkit hype → checks     01.jpg … spec.json render_report.json
reviewer: lane.py show / approve ──► queue/approved/<slug>.json ──► lane-publish (Actions, every 10 min)
                                                                     gate + freshness → Instagram → queue/posted/<slug>/
anything that fails ──► queue/rejected/<slug>/reasons.json
```

### 1. Write a spec (the posting run)

Same editorial rules, copy rules and 7-check score as any post. Then:

1. Pick the slug: lowercase words and hyphens, unique, e.g. `2026-11-10-idlynerd-kaalam-trailer`.
2. Write `queue/pending/<slug>.json`:

   ```json
   {
     "account": "idlynerd",
     "story_id": 1741,
     "idly_article": true,
     "title": "Kaalam trailer: Netflix sets 4 December release",
     "headline": "Kaalam's first trailer sets up a 4 December Netflix release",
     "caption": "<fact lines>\n\n<one genuine question>\n\nFull story on idly.news (link in bio).\n\n#Kaalam #Netflix #TamilCinema #idlynerd",
     "alt_text": "A still from the Kaalam trailer, with the headline on the card.",
     "sources": ["The Hindu", "Cinema Express"],
     "detail_slides": [{"stat": "4 DEC", "stat_label": "Kaalam streams on Netflix", "bullets": ["…", "…"]}],
     "image": {"resolver": "youtube_official", "ref": "https://www.youtube.com/watch?v=XXXXXXXXXXX",
               "fallback": [{"resolver": "og_image_official", "ref": "https://about.netflix.com/en/news/…"}]},
     "scores": {"self": {"hook": 2, "read": 2, "send": 2, "keep": 2, "reply": 2, "original": 1, "alone": 1,
                         "total": 12, "notes": "…"}},
     "created_at": "2026-11-10T09:12:00+05:30"
   }
   ```

   - **Leave the image credit out of the caption.** The lane adds the exact credit as the last line
     (`Image: Netflix India (official trailer)`, `Image: Maruti Suzuki`, `AP Photo/<Photographer>`,
     `Photo: PTI`, …) once it knows which image it used.
   - `detail_slides` are optional (0–9 slides after the cover). If you add any, `sources` is required:
     it becomes the `Sources: …` line on those slides.
   - `idly_article: false` (with `story_id: null`) for a post with no idly.news article: the caption then
     needs a `Sources: …` line and must not mention idly.news.
   - `evergreen: true` only for timeless posts. Otherwise the lane drops the spec once `created_at` is
     8 hours old.
   - Your self score must already be 12 or more, as for any post.
3. Check it, then commit and push it (it renders within about 10 minutes):

   ```bash
   python3 pipeline/lane.py validate queue/pending/<slug>.json
   git add queue/pending/<slug>.json && git commit -m "lane: spec <slug>"
   git pull --rebase origin main && git push origin HEAD:main
   ```

### 2. Which resolver

The lane tries `image` first, then each `fallback` in order, **except that `licensed_wire` always goes
first** when you list it.

| story | resolver | `image` fields |
|---|---|---|
| A news event with people (a match, a premiere, a press conference, a court appearance) | `licensed_wire` | `"query"`: who + what + where, e.g. `"Virat Kohli Perth Test"`; optional `"agencies": ["ap", "pti"]`, `"since_hours": 48` |
| A film or series: trailer, teaser, first look, release date | `youtube_official` | `"ref"`: the video URL or id. It **must** be uploaded by an allowlisted official channel (studio, label or streamer), checked through YouTube's oEmbed |
| A company: launch, results, product, policy | `og_image_official` | `"ref"`: the company's **own** newsroom or press-release page (an allowlisted domain). Never a news site |

- **Wire photos:** only through the agency's official API with the secrets in GitHub (today: AP, once
  `AP_MEDIA_API_KEY` is set; PTI, ANI and IANS are stubs until they give us an API). The lane picks the
  newest photo whose caption matches the query, big enough, that passes face framing, and costs nothing
  extra. **Never Reuters or Getty.** If wire isn't set up, it falls through to your fallback.
- **Trailers:** YouTube thumbnails are 1280×720. Covers are always full-bleed ([Cover style](#cover-style-rahul-10-nov-2026)):
  the lane crops the still to 4:5 around any faces (enlarging it up to 2x, with sharpening). If no full-bleed crop
  keeps every face clear, it moves on to the next image attempt. Never a letterbox or a blurred fill.
- **Newsrooms:** pages from news outlets (NDTV, Times of India, Cinema Express, 123telugu, Hindustan Times,
  Indian Express …) are always refused, as are images they host.

What the lane checks (every one rejects the spec with a reason): allowlist and denylist; no placeholders,
logos or blank images; under 900 px wide never (1080 px at more than 1.2× upscale); every face detected
(YuNet) sits between y 190 and y 702 of the 1080×1350 cover, not cut by an edge, and nothing busy under the
logo (else the next image attempt, else reject); the headline fits; the credit line on every slide doesn't collide; the
caption passes every caption rule with the credit appended.

### 3. Review (the reviewer step)

After the posting step, review what the lane has rendered:

```bash
git pull --rebase origin main
python3 pipeline/lane.py status                 # what is pending, rendered, approved, rejected, posted
python3 pipeline/lane.py show <slug>            # blind packet: copy, final caption, credit, source, framing
```

For each item in `queue/rendered/`, a **blind** reviewer (one that has not seen the self score: `show`
leaves it out) opens `queue/rendered/<slug>/01.jpg`, `02.jpg` …, `story.jpg` and `render_report.json` and checks: the
headline is legible and not over a face; no face is cut off or under the logo; the credit on the cover and
the source line on the other slides are there and readable; the image matches the story; the caption is
right. Then it scores the 7 checks and writes the score to a file:

```bash
python3 pipeline/lane.py approve <slug> --score-file /tmp/<slug>-review.json   # the lower score must be >= 12
python3 pipeline/lane.py reject  <slug> --reason "headline sits on the actor's face"
git add queue reports && git commit -m "lane: review <slug>"
git pull --rebase origin main && git push origin HEAD:main
```

If the story has a layout problem but the slides are fine, approve with `--no-story`.

`approve` rejects the item itself when the lower of the two scores is under 12. The `lane-publish` workflow
posts approved items within about 10 minutes: one post per account per run, only while fresh, only with that
account's `IG_TOKEN_…` secret set in GitHub, and never twice (it checks `state/posted.json` and the account's
recent posts first). It records the post in `state/posted.json` (slot `lane`) and the day's events in
`reports/lane-<date>.md`; read that file in your summary. Right after each feed post it posts the item's
`story.jpg` (`story · …` in the report, or `story failed · …`, which leaves the feed post as it is).

### 4. Adding a source to the allowlist

All in `config/official_sources.json`, by a session with a human's go-ahead, in its own commit:

- **YouTube channel:** open the channel and one of its videos, and confirm it is the official channel (the
  studio, label or streamer's own; verified badge; the company links to it). Run
  `curl -s "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<id>&format=json"` and copy
  `author_url` exactly into a new `youtube_channels` entry with `name` (as it should appear in the credit),
  `channel_id` and a `verified` note (date and how). Can't confirm it? Put it in `pending_review` instead.
- **Official website:** add `{"domain": "…", "organisation": "…"}` to `official_domains` (subdomains are
  included). Add `"path_prefixes": ["/newsroom"]` when only part of a site is a newsroom. Never add a news
  outlet, a fan site, a wiki or a social network.
- **Never** remove a domain from `denied_domains` to make a story work.
- Run `python3 -m unittest discover tests` before committing.

### Lane troubleshooting

| report line / reason | meaning |
|---|---|
| `uploader … is not on the official channel allowlist` | Not an official upload (fan channel, re-upload). Find the studio's own upload, or add the channel (above) if it really is official. |
| `… is not an official domain on the allowlist` / `… is a news outlet` | Use the company's own newsroom page. |
| `framing: …` | No layout keeps every face in the safe band. Try another source (another trailer, another photo). |
| `licensed_wire: … not configured` | No agency API is set up yet; the lane used your fallback (or rejected if there was none). |
| `waiting · … will retry` | The source was unreachable; the next run tries again. |
| `skipped · … IG_TOKEN_X secret is not set` | Rahul needs to add that GitHub secret ([docs/SETUP-GITHUB-SECRETS.md](docs/SETUP-GITHUB-SECRETS.md)). |
| `stale` | Over 8 hours old: write a new spec if the story still matters. |
| `no story (framing: …)` / `no story (… collides …)` | The 9:16 story couldn't be framed or laid out; the feed post is unaffected. |
| `story failed · …` | The story didn't post (quota headroom, Meta error); the feed post is up. Nothing to do. |
| `rejected (validate) · reel …` | The reel request is wrong: the reasons say what (source not posted yet, missing `post.json`, caption rule, score). Fix it and queue it again under a new name. |
| `… changed since the feed post` | The official image is no longer the one the feed post used; that reel can't be made. |
| `failed · reel … every host` | Meta refused the video from raw.githubusercontent.com, jsDelivr and (if possible) the resumable upload: put Meta's message in the summary for Rahul. It retries next run while fresh. |

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


## Citizen voices

What ordinary people are posting about a story, read through each platform's official API
(`pipeline/voices/`, workflow `voices-pull`). It exists because outlets take sides: a scorecard needs the
public's own words next to the media's.

- **Topic file:** `config/voices/<topic>.json` gives the dates, the YouTube searches, the subreddits, and
  `must_match` words. Pushing a change to a topic file runs the pull; so does Actions → voices-pull → Run workflow.
- **Output:** `research/voices/<topic>/latest.md` (and a dated `.md` and `.json`): themes ranked by how many
  different people raised them, the most-liked excerpts with links, copy-paste text reported separately.
- **Keys (GitHub → Settings → Secrets and variables → Actions; Rahul types them):**
  `YOUTUBE_API_KEY` (free Google Cloud key, YouTube Data API v3; about 2,600 of the 10,000 free daily units per pull),
  `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME` (a Reddit "script" app; Reddit's free tier is for
  non-commercial use, so apply for commercial access if idly publishes from it regularly).
  `X_BEARER_TOKEN` is optional and paid per post: it stays off unless the repository variable
  `VOICES_X_ENABLED` is `true` and the topic sets `x.max_posts` above 0. X search only reaches back 7 days.
- **Rules:** this repository is public, so no username is ever written and raw posts are never saved. The digest
  is a reading of public posts, not a poll: say "N posts from M accounts", never "X% of Tamil Nadu". Comment
  sections skew angry and organised. Themes are keyword matches; no stance or sentiment is inferred, so a human
  (or the desk) reads the excerpts before anything is quoted. Quote a post only as "a commenter on YouTube/Reddit",
  with the link kept in the sources, and never a private person's name.
- **Discord** is not covered: it has no public search, and a bot can read only servers whose admins invite it.


## The baseline (Tamil Nadu first)

idly does not write local news from the fresh headline alone. `baseline/tn/` holds what idly has already sourced about
Tamil Nadu: the people in office, the numbers, every promise and its verdict, the "showcased v what followed" ledger,
the state's history and constitutional rules, dated things to watch, and the rules for what idly never publishes.
It was built from the report "Six Months of TVK: The Record" (11 Nov 2026) and grows with every story.

**Every desk, for any story that touches Tamil Nadu politics, government, policy, courts, the economy or public figures:**
1. Before Gate 1, run `python3 -m pipeline.baseline check "<headline and the key facts>"`. Read everything it prints.
2. Use it. Put the new development in its context in the caption or a detail slide: what was promised, what the last
   number was, how the previous governments did on the same point, what happened the last time this was announced.
   A story that only repeats today's headline, when the baseline shows the claim was made before or contradicts a
   sourced figure, does not pass Gate 2.
3. Follow the status labels. `disputed`: give both figures. `alleged`: say alleged and carry the response.
   `single_source`: find a second source before leaning on it. If the new story contradicts a `verified` item, check
   the story twice; if the story is right, the baseline gets corrected in the same commit.
4. `STOP` (exit code 2) means the text breaks a rule in `baseline/tn/rules.json`. Rewrite or drop it. Never edit the
   rule to get a post through. `editorial.caption_problems` runs the same rules and blocks the post.
5. After publishing, record it: `python3 -m pipeline.baseline log --note "<what happened, one line>" --source <https link>
   --ids <baseline ids it updates> --keywords <words a later story would use>`, and commit `baseline/tn/log.jsonl`.
   When a development settles something (a ruling, a scheme starting, a figure revised), also edit the item in its
   JSON file: new `current`/`value`, new `as_of`, new source. Run `python3 -m pipeline.baseline validate` before committing.
6. Once a day (the first run after 08:00 IST), @idlynews runs `python3 -m pipeline.baseline due` and treats anything due
   within a week as a story to prepare, with its history already in hand.

**The same test for every party.** When a story criticises one party on a point, the baseline usually shows how the
others did on it. Say so in a line. **History and polity:** `facts_history_polity.json` carries the constitutional rule
or the precedent (how a floor test works, what the Governor may do with a bill, what happened to earlier star-led
parties). Use it to explain, not to predict. **Citizen voices:** `python3 -m pipeline.voices pull <topic>` gives a reading
of public comments; it is never a poll. **Not Tamil Nadu?** There is no baseline yet for other states; say so in the
report so the gap is visible. New regions go in `baseline/<region>/` with the same files.
