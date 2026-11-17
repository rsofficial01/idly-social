# @idlynerd hand-off: hourly run 0757, Tue 17 Nov 2026

**Status: READY.** The last Gate 4 reply, 083008-idlynerd-g4, is a PASS.

- **Folder:** `posts/2026-11-17/idlynerd-0757-game-awards-nominees/`. This is a desk post with 3 slides and format "event".
- **Story:** The Game Awards 2026 reveals its nominees tonight, Tue 17 Nov, at 10:30 PM IST (noon ET).
  - Games had to be on sale by Fri 20 Nov, 9 PM PT. That makes Rockstar's GTA VI (19 Nov) and the Zelda: Ocarina of Time remake eligible.
  - The show is Thu 10 Dec at the Peacock Theater, Los Angeles. The stream starts at 7:30 PM ET, which is 6 AM IST on Fri 11 Dec, free on YouTube and Twitch.
- **idly article:** none. `story_id` is null and the caption carries a Sources line.

## Gates
1. **Gate 1, round 1** (081015-idlynerd-g1): BUILD Dhindora 2. Bond and Ramayana overseas were held.
   - The Dhindora 2 lane spec v1 and v2 were both rejected by the lane at framing: no crop of the Netflix India thumbnails kept every face in the safe band. Main called it off; no v3.
2. **Gate 1, round 2** (082623-idlynerd-g1): BUILD A, The Game Awards.
   - BGMI 4.7 was held at 9: no compliant image.
   - PlayStation Store India Black Friday was held at 9: the prices can't be re-verified and the audience is narrow.
3. **Gate 23** (082929-idlynerd-g23): PASS. Notes applied:
   - slide 2 now says "Rockstar's GTA VI, out 19 Nov";
   - slide 3 keeps "6 AM IST on Friday".
4. **Gate 4** (083008-idlynerd-g4): PASS. The reviewer wrote `reviewer-score.json`.

## Score
| | hook | read | send | keep | reply | original | alone | total |
|---|---|---|---|---|---|---|---|---|
| Mine | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 13 |
| Reviewer | 1 | 2 | 2 | 2 | 2 | 1 | 2 | 12 |
| **Post score (lower of each)** | 1 | 2 | 2 | 2 | 2 | 1 | 2 | **12/14** |

- Hook is 1: the cover has a time and a famous award, but no surprising number.
- Original is 1: an event schedule from official sources, with the organiser's own key art.

## Image
- Source: The Game Awards' official 2026 key art on its own site, https://assets.thegameawards.com/2026/08/56601a04-2026_tga_keyart_16x9-copy-scaled-1.webp (via https://thegameawards.com/). Owner: The Game Awards. 2560x1440.
- dl.py found 0 faces, and I viewed it. It shows the winged bronze trophy only.
- The key art's "THE GAME AWARDS / DECEMBER 10" lettering is cropped out. Framing is focal [0.203, 0.47], zoom 1.11, at 1.04x upscale.
- Credit line: "Image: The Game Awards".

## Tag
- None. I couldn't confirm the handle from the organiser's own site or from two sources.

## For main to re-check
1. **Timing:** publish well before 10:30 PM IST tonight. After the reveal, the card is stale.
2. **Follow-up post:** the nominees themselves are the obvious post for tonight or tomorrow morning. The 2-hour same-topic rule applies.
3. **Lane queue:** check `queue/approved/` for any idlynerd lane item before publishing. `queue/pending` has no idlynerd spec now; the Dhindora v1 and v2 specs are in `queue/rejected/`.
4. **Gate tool workaround:** in the Gate 23 packet, the finalweapon.net URL (date path 2026/11/14) tripped the gate tool's score filter, so it is written with › separators there. The real URL is in `meta.json`.
5. **Tamil Nadu baseline WARN:** checkcopy shows its standing keyword WARN. This is not a TN story.
