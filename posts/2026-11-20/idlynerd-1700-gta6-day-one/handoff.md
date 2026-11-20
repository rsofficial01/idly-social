# @idlynerd hand-off, hourly run 1700 (Fri 20 Nov 2026)

**Status:** READY (G1 BUILD, G2+G3 PASS, G4 PASS; score 12/14, exactly at the gate)
**Folder:** posts/2026-11-20/idlynerd-1700-gta6-day-one/ (01.jpg-04.jpg, post.json, caption.txt, alt.txt, meta.json, render_report.json, self-score.json, reviewer-score.json, score.json)
**Headline:** GTA VI at Launch: 24.6 Million Copies, Sensor Tower Estimates
**Format:** news carousel (cover + 3 detail slides: $2.36B estimate / $800M+ GTA V 2013 / ₹5,999 PS Store India)
**story_id:** null, no idly article. Publish with `--no-idly-article`. The caption has a Sources line and no idly.news mention.
**Tag:** @rockstargames. Evidence: Rockstar owns the cover image, and its own GTA VI site (rockstargames.com/VI/media/screenshots, the cover's source page) links to instagram.com/rockstargames twice. It is a company account, not a person.
**Baseline:** none (not Tamil Nadu).
**prepublish.py:** run 17:23 IST, no problems, no warnings (score 12, 1 @idlynerd post in 24 h).

## BEFORE PUBLISHING (reviewer's condition)
Re-check that Take-Two/Rockstar haven't released an official GTA VI sales figure. Zelnick said "soon". Places to check: take2games.com/ir/news, rockstargames.com/newswire, GameSpot. Last check was ~17:30 IST: none found. If an official number is out, **do not publish this**: the estimate would be stale. Re-pitch with the official figure instead.
Also check queue/approved/ for an @idlynerd lane item (none pending/approved at 17:05).

## Scores
- Desk self-score: 13 (send 1; everything else 2).
- Blind reviewer (G4): 12 (send 1, keep 1).
- Post score, per-check MIN: hook 2, read 2, send 1, keep 1, reply 2, original 2, alone 2 = **12** (score.json).
- Weak checks: send 1 (sixth GTA VI card in 10 days, third-party estimate, record headlines already everywhere); keep 1 (the only keepable item is the PS Store price, which we posted on 15/16 Nov; nothing new to save).

## Image
- Official GTA VI in-game screenshot "Vice_City_11": Vice City bay at sunset with a Ferris wheel, yachts, the skyline and a helicopter. No people or characters, no watermark, no overlay text.
- Page: https://www.rockstargames.com/VI/media/screenshots ; file: https://www.rockstargames.com/VI/_next/static/media/Vice_City_11.09paum3g942sc.jpg
- 3840x2160, sharpness 498, dl.py 0 faces, viewed. Credit "Image: Rockstar Games" (on the cover and as the last caption line).
- Never used on an earlier idly cover. Already used: Vice_City_01/10/15/22/27, Leonida_Keys_01, launch-gallery night skyline.
- Framing: card focal [0.63, 0.5], zoom 1.0, a downscale (0.625). This crops out the left towers and their MEGAMUNDO sign. The helicopter sits at y≈250-350 and the skyline at y≈650-760. The headline sits over the bay and park.

## Facts (2+ sources each; full URLs in meta.json)
1. Sensor Tower estimate: 24.58M copies and ~$2.36B by the end of launch day (19 Nov). Sources: GameSpot, TweakTown, Notebookcheck, MakeTechEasier, Globe and Mail.
2. The count is digital, PS5 + Xbox Series X|S, with pre-orders included. Sources: GameSpot, Notebookcheck, MakeTechEasier.
3. PS5 18.44M, Xbox 6.15M (75/25). Sources: GameSpot, Notebookcheck, TweakTown.
4. Take-Two has given no official figure; Zelnick says it's coming soon. Sources: GameSpot, Notebookcheck, TweakTown.
5. GTA V's first-day retail sell-through was more than $800M (Take-Two press release, 18 Sept 2013, SEC 8-K exhibit). Second source: Notebookcheck. "Nearly three times": 2.36/0.80 = 2.95.
6. GTA V passed $1B in three days. Sources: Take-Two 8-K (20 Sept 2013), Bloomberg, Engadget.
7. PS Store India prices: ₹5,999 Standard, ₹7,499 Ultimate. Sources: PlayStation India page, Business Today, MySmartPrice.
8. GTA VI is on PS5 and Xbox Series X|S only. Sources: PlayStation India, Business Today, GameSpot.

## Gates
- G1 (review/idlynerd-g1.md): BUILD #1 (ceiling 13). Conditions: put "Estimated" and "Sensor Tower" on the cover; put "pre-orders included" and "digital PS5 + Xbox" on a slide; say "by the end of launch day"; label GTA V's figure as retail sell-through; ask "Would you pay ₹5,999 for GTA VI?". All done.
- G2+G3 (review/idlynerd-g23.md): PASS, no fixes. The reviewer noted the stake ("nearly 3x GTA V") is on slide 3, not the cover.
- G4 (review/idlynerd-g4.md): PASS 12/14. Layout is clean, the render report is clean, and reviewer-score.json is written.

## Dropped candidates
- **Panchayat Season 5 streams 3 Dec on Prime Video** (announced Wed 18 Nov; Khaleej Times/ANI, Digit, Outlook, Business Standard). G1 ceiling 11: the date was already 2 days old (send 1), a date reveal with no stake is hook 1, it's a single announcement (original 1), and it's lane-only with unknown framing (Prime Video India VUC_Vi-iVvI). Lead: it fits better as an item in a weekly OTT list nearer 3 Dec, or as a trailer post when Prime Video India uploads the S5 trailer.
- **Ramayana ₹1,547 cr worldwide / sixth Indian film past ₹1,000 cr India gross** (Sacnilk day 15). G1 ceiling 8-10: fourth milestone in 10 days, not a round number, nothing to keep, India net disputed (Sacnilk ₹863.75 cr vs Koimoi ₹900.93 cr), and it would retry the 11:57 framing reject. Not built.
- Also considered: GTA VI livestream record (7.91M peak concurrent viewers, Streams Charts; Variety): same subject, folded out. Robert Pattinson as Bond: announced 16 Nov, image is the actor only. OM: Operation Mole and Aakasamlo Oka Tara: released today, no numbers yet. Godzilla Minus Zero India release: already posted 16 Nov.

## Leads for later runs
- Take-Two's official GTA VI sales figure ("soon", per Zelnick). It would be a genuine new stage: build it from the official release, with an unused Rockstar screenshot (no people) such as Port_Gellhorn_06 or Leonida_Keys_06 (iguana). Both passed dl.py with 0 faces. They were deleted from this folder, so re-download them via dl.py.
- Opening numbers for OM: Operation Mole and Aakasamlo Oka Tara (Sat/Sun). Ramayana passing Baahubali 2's ₹1,031 cr India net, if the trackers agree. The Panchayat S5 trailer on Prime Video India's YouTube.
