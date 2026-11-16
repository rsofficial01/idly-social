# @idlynerd hand-off, run 2057 (Mon 16 Nov 2026)

**Status:** READY (G4 PASS; see gate outcomes below)
**Folder:** posts/2026-11-16/idlynerd-2057-gta6-12-million-preorders/ (01.jpg, 02.jpg, 03.jpg, post.json, caption.txt, alt.txt, render_report.json)
**Headline:** GTA VI Passes 12 Million Pre-Orders, Sensor Tower Estimates
**Format:** news carousel (cover + 2 detail slides)
**story_id:** 2632 (idly article exists: caption carries "Full story on idly.news (link in bio)."; publish WITH the idly article, not --no-idly-article)

Schedule note: third GTA VI card on @idlynerd this week (12 Nov 10M pre-orders, 15 Nov Kick giveaway, 10 Nov pre-load lane post). Today's @idlynerd leads were Ramayana / Weekend Box Office / Godzilla, so no same-day clash. Check queue/approved/ for @idlynerd lane items before posting.

## Facts and sources (each with two)
1. Past 12 million GTA VI pre-orders (Sensor Tower estimate, as of 13 Nov)
   - Motor1 (16 Nov): "approximately 12.13 million digital pre-orders worldwide as of November 13" https://www.motor1.com/news/815604/gta-6-reaches-1-billion-revenue-pre-orders/
   - GameSpot (updated article, read via RSS): Sensor Tower tracker now 14.94M units (not printed; supports "12M+") https://www.gamespot.com/articles/gta-6-has-sold-almost-8-million-copies-so-far-and-ps5-is-dominating-the-split-of-course/
   - Primary tracker: https://sensortower.com/grand-theft-auto-VI/sales-tracker (client-side data; not readable)
2. Worth over $1 billion: Motor1 ($1.18B), GameSpot (~$1.45B) (same URLs).
3. About 3 in 4 on PS5: Motor1 (~75%, 9.08M), GameSpot (74%).
4. Rockstar/Take-Two haven't confirmed a count: Motor1 ("third-party estimates, not official Rockstar or Take-Two figures"); idly #2632 ("The publisher has not made a statement on pre-order totals").
5. 10.31 million on 11 Nov (caption only): Rockstar Report https://rockstarreport.com/news/gta-6-preorders-pass-10-million-sensor-tower-estimate ; Insider Gaming https://insider-gaming.com/gta-6-surpasses-1-billion-presales/ (also GamesBeat https://gamesbeat.com/grand-theft-auto-vi-preorders-cross-1b-analyst-roundup/).
6. Unlocks 19 Nov, 12:00 AM IST (store listings, not Rockstar): PlayStation India game page releaseDate "2026-11-18T18:30:00Z" https://www.playstation.com/en-in/games/grand-theft-auto-vi/ ; Business Today "PlayStation and Xbox listings in India show 12:00 am IST on Thursday, 19 November" https://www.businesstoday.in/latest/trends/photo/gta-6-arrives-at-midnight-on-19-november-india-price-preload-and-editions-565630-2026-11-04
7. ₹5,999 Standard / ₹7,499 Ultimate: PlayStation India page ("Rs 5,999" GTAVISTANDARD001, "Rs 7,499" GTAVIULTIMATE001); Business Today (same URL).
8. PS5 and Xbox Series X|S only: Business Today; PlayStation India ("only playable on PS5 and is not available for PS4").

## Image
- Official GTA VI in-game screenshot "Leonida_Keys_01": a long bridge across the Leonida Keys towards the Vice City skyline; no people (dl.py 0 faces; checked by eye: two jet-ski wakes at the bottom are specks under the scrim). (First cover, Vice_City_01, was replaced at G4: the 4:5 crop cut the sign to "ICE".)
- Source page: https://www.rockstargames.com/VI/media/screenshots ; file: https://www.rockstargames.com/VI/_next/static/media/Leonida_Keys_01.0zgz7tveur6y8.jpg
- Owner/licence: Rockstar Games official media screenshot; credit "Image: Rockstar Games". Not used on any earlier idly cover (earlier: Vice_City_10/22/27).
- Size 3840x2160; framing: photo _work/2026-11-16-hourly-2057/idlynerd/frame_Leonida_Keys_01/cover_source.png, framing tool ok (focal 0.5, zoom 1.0, upscale 0.62, faces 0); card uses focal [0.42, 0.5] so the seaplane is cropped out and the skyline + bridge sit whole above the headline.
- Tag: no tag.

## Gates
- G1 210924-idlynerd-G1: PASS (conditional), build Candidate 1, ceiling 12, no slack.
- G23 211234-idlynerd-G23: FIX (add "as of 13 Nov" on slide 2 + caption; drop Gadgets 360 from Sources; "On 11 November it was 10.31 million") -> all fixed.
- G4 211346-idlynerd-G4: FIX (cover crop cut the Vice City sign to "ICE") -> cover swapped to Leonida_Keys_01.
- G4 211631-idlynerd-G4: PASS. Reviewer total 12 (send 1, original 1); scores/idlynerd-reviewer-G4.json. Self-score 12 (scores/idlynerd-self.json).

## G1 candidates
1. **GTA VI pre-orders pass 12 million, 3 days before launch (built).** Only one I could finish in-session with a clean unused official image and an India date/price on the card.
2. **Robert Pattinson named the new James Bond** (official @007 post, Mon 16 Nov ~20:40 IST; Indian Express, Hindustan Times, statements to Variety). Reviewer ceiling ~12 but the image can only be the actor, so it's official-lane only; no India date, no release date. I did NOT write a lane spec: I couldn't find an allowlisted resolver (no Amazon MGM/007 YouTube channel in config/official_sources.json; no aboutamazon.com newsroom item found yet). Main's call if a Prime Video (allowlisted) clip or aboutamazon.com post appears.
3. **IFFI Goa 2026 opens Fri 20 Nov** (Dhurandhar opens Indian Panorama). Dropped: 3 days old, narrow, no lawful image found (ceiling ~9).
Also skipped: #2616 Hanuman Ansh (makers' unverified figure; poster shows actors); #2589 Aakasamlo Oka Tara (channel not allowlisted); #2625 Ramayana (no Ramayana lead today); Game Awards nominees (not until Tue 22:30 IST).
