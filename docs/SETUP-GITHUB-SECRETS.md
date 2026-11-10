# Setting up GitHub secrets for idly's automatic posting

**Who this is for:** Rahul. **Time:** about 10 minutes. **Where:** a web browser on your Mac. Every step says
where it happens: **[Mac browser]**, **[phone]** or **[Mac]**.

## What this does

idly's "official image lane" runs on GitHub (free, because the repo is public). It posts the approved
Instagram cards by itself, every 10 minutes, with no one at a keyboard. To post, GitHub needs the same
Instagram tokens you already gave the Claude environment. You store each one in GitHub as a **secret**.

A secret is safe to store there:

- After you save it, nobody can see it again, including you. You can only replace it.
- The posting code never prints it, and GitHub hides it in every log as `***`.
- Copies of the repo (forks) never get your secrets.

If a secret is missing, the lane simply skips that Instagram account and writes a line in the day's report
(`reports/lane-<date>.md`). Nothing breaks.

## Step 1: Copy your five tokens

You need the same five token values you pasted into the Claude environment before.

1. **[Mac browser]** Open [claude.ai/code](https://claude.ai/code).
2. **[Mac browser]** Click the **environment selector** (the first control in the row under the message box).
   Hover over the environment the idly runs use and click its **gear (settings) icon**.
3. **[Mac browser]** In **Environment variables** you will see five lines like
   `IG_TOKEN_IDLYNEWS=EAAG…`. Keep this tab open. For each account you will copy **only the part after
   the `=`** (the long token), not the name and not the `=`.

Don't paste the tokens into a chat, an email or a notes app. Copy them straight from this tab into GitHub.

## Step 2: Open the repo's secrets page

1. **[Mac browser]** In a new tab, go to [github.com](https://github.com) and sign in as **rsofficial01**.
2. **[Mac browser]** Open the repo: [github.com/rsofficial01/idly-social](https://github.com/rsofficial01/idly-social).
3. **[Mac browser]** Click **Settings** (the last tab in the row under the repo name, with a gear icon). If
   you don't see it, click the **⋯** at the end of that row, then **Settings**.
4. **[Mac browser]** In the left sidebar, under **Security**, click **Secrets and variables**, then
   **Actions**.
5. **[Mac browser]** You are now on **Actions secrets and variables**, on the **Secrets** tab. This is the
   page for every step below. (Direct link:
   [github.com/rsofficial01/idly-social/settings/secrets/actions](https://github.com/rsofficial01/idly-social/settings/secrets/actions).)

## Step 3: Add one secret per Instagram account

Do this five times, once per row of the table:

| Name (type it exactly) | Secret (paste) |
|---|---|
| `IG_TOKEN_IDLYNEWS` | the token after `IG_TOKEN_IDLYNEWS=` in the Claude environment |
| `IG_TOKEN_IDLYTECH` | the token after `IG_TOKEN_IDLYTECH=` |
| `IG_TOKEN_IDLYHYPE` | the token after `IG_TOKEN_IDLYHYPE=` |
| `IG_TOKEN_IDLYAUTOMOTIVE` | the token after `IG_TOKEN_IDLYAUTOMOTIVE=` |
| `IG_TOKEN_IDLYNERD` | the token after `IG_TOKEN_IDLYNERD=` |

1. **[Mac browser]** Click the green **New repository secret** button.
2. **[Mac browser]** In **Name**, type the name from the table exactly: capital letters, underscores, no
   spaces. (GitHub turns letters into capitals for you anyway.)
3. **[Mac browser]** Go to the Claude tab, select the token after the `=` on the matching line, copy it
   (**⌘C**), come back and click in the **Secret** box, then paste (**⌘V**). No quotes, no spaces before or
   after, no `IG_TOKEN_…=` in front.
4. **[Mac browser]** Click **Add secret**. The secret now appears in the list under **Repository secrets**,
   with its name only.

When all five are listed, you're done with the Instagram part.

**[phone]** You can also do this in Safari or Chrome on your phone at the direct link above (turn on
**Request Desktop Website** if the Settings tab is missing). The GitHub mobile app can't add secrets.

## Step 4: Check it worked

1. **[Mac browser]** In the repo, click the **Actions** tab.
2. **[Mac browser]** In the left list click **lane-publish**, then **Run workflow** (on the right) →
   **Run workflow**.
3. **[Mac browser]** Wait about a minute, click the new run, then the **publish** job, then the step
   **Publish approved posts**. You should see five lines:

   ```
   IG_TOKEN_IDLYNEWS: set
   IG_TOKEN_IDLYTECH: set
   IG_TOKEN_IDLYHYPE: set
   IG_TOKEN_IDLYAUTOMOTIVE: set
   IG_TOKEN_IDLYNERD: set
   ```

   It only ever says `set` or `NOT SET`. It never shows a token. A name showing `NOT SET` was typed
   differently in step 3: delete that secret and add it again with the exact name.

## When a token expires or changes

Instagram tokens expire. When the daily summary says a token expires soon (or an account starts failing):

1. **[Mac browser]** Make a new token in the Meta app dashboard (RUNBOOK.md, *Meta access*), and update it in
   the Claude environment as before.
2. **[Mac browser]** On the GitHub secrets page (step 2), click the **pencil** next to that secret, paste the
   new token into **Value**, and click **Update secret**.

Keep the Claude environment and GitHub in step: the hourly Claude runs use the first, the lane uses the second.

## Optional: licensed news-agency photos

The lane can use photos from the news agencies idly has licences with, through each agency's official
API. It never logs into an agency's website and never uses Reuters or Getty (idly has no licence for them).

Before you add any of these, check that your agency contract allows use **on Instagram / social media**,
not only on the website.

| Agency | Status in the lane | Secret name(s) | Where the value comes from |
|---|---|---|---|
| **AP** (Associated Press) | **Ready**: works as soon as the secret exists | `AP_MEDIA_API_KEY` | Your AP account: ask your AP account manager or AP Customer Support for an **AP Media API key** for your plan (AP's developer guide: [api.ap.org/media/v/docs](https://api.ap.org/media/v/docs/)). The lane only takes photos that are included in your plan at no extra cost, and only AP's own photos. |
| **PTI** (Press Trust of India) | Not built yet: PTI publishes no API documentation we could find | `PTI_API_BASE`, `PTI_API_KEY` (planned) | Ask PTI's subscription desk: *"Do you offer an API or XML/JSON feed of photos for subscribers? Please send the endpoint, the credentials and the documentation, and your required photo credit for Instagram."* |
| **ANI** (Asian News International) | Not built yet, same reason | `ANI_API_BASE`, `ANI_API_KEY` (planned) | Ask ANI the same question. |
| **IANS** (Indo-Asian News Service) | Not built yet, same reason | `IANS_API_BASE`, `IANS_API_KEY` (planned) | Ask IANS the same question. |

**To add the AP key:**

1. **[Mac browser]** Open the secrets page (step 2) and click **New repository secret**.
2. **[Mac browser]** Name: `AP_MEDIA_API_KEY`. Secret: paste the key AP gave you. Click **Add secret**.

**For PTI, ANI or IANS:** don't add the secrets yet. When an agency sends API documentation and
credentials, forward the *documentation* (not the key) to a Claude Code session and ask it to finish
`pipeline/wire/pti.py` (or `ani.py`, `ians.py`). It will tell you the exact secret names to add, on this
same page, the same way.

The credit line each agency's photos get (on the card and as the caption's last line):
`AP Photo/<Photographer>`, `Photo: PTI`, `ANI Photo`, `Photo: IANS`. If your contract asks for a
different form, tell a Claude session and it changes it in `pipeline/wire/base.py`.

## What you never need to do

- **[Mac]** Nothing on your Mac's terminal. Everything above is in the browser.
- You don't need to touch the workflows or the code. To pause the lane, open **Actions** → **lane-publish**
  (or **lane-render**) → **⋯** → **Disable workflow**. **Enable workflow** turns it back on.
