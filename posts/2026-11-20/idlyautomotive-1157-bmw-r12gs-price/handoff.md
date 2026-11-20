# Handoff: @idlyautomotive, 20 Nov 2026, 11:57 IST slot

**Status: READY.** Main checks and publishes. The desk ran no git, no publish and no lane commands.

- Folder: posts/2026-11-20/idlyautomotive-1157-bmw-r12gs-price
- Headline: "BMW R 12 G/S Lands in India at ₹25.40 Lakh"
- Format: news carousel (cover + 3 detail slides: ₹25.40 LAKH / 2 PACKAGES / 109 HP)
- idly article: none. Post with `--no-idly-article`. The caption has a Sources line and no idly.news mention.
- Tag: **none**. The reviewer's condition was to tag BMW Motorrad India only if the handle is verified on bmw-motorrad.in. That site returned 503 / no connection from here, and the BMW Group India newsroom release has no Instagram link.
- Cover image: official BMW Motorrad press photo P90592200 from the BMW Group India newsroom release (19 Nov 2026), 1920x1433, no faces, sharpness 442.
  - Credit: "Image: BMW Motorrad".
  - Framing: focal [0.483, 0.72], zoom 1.75, upscale 1.65x. Set by hand, because pipeline.framing's zoom 1.0 would have put the bike under the headline.

## Scores
- Self: hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2 = 13/14
- Reviewer (blind, G4): hook 1, read 2, send 1, keep 2, reply 2, original 2, alone 2 = 12/14
- **Post score (per-check minimum): 12/14.** Passes the 12 gate with no margin.

## Gates
- G1: BUILD #1 (ceiling 13, conditional); no build for #2 Rebel 500 (no image) or #3 Carens CNG (ceiling 10).
- G2+G3: FIX (original needed a sourced comparison); the picture passed.
- G2 round 2: PASS. Used the sister R 12's July 2024 launch price, ₹19.90 lakh (Autocar Pro, Top Gear India, Autocar India). Did not use the R 12 nineT, whose launch price conflicts across sources (₹20.90 vs ₹20.20 lakh).
- G4: PASS 12/14 (reviewer-score.json).

## Checks
- render.py: problems [].
- checkcopy: errors []. One warning is a baseline-tn false positive: "109" and "R." match TVK MLA-count items. Nothing political is in the caption.

## Dropped candidates
- **Honda Rebel 500 at ₹4.50 lakh:** strongest story, but no official image of 1080 px or more. Honda India only has 1920x754 and 600x800 banners; the Honda EU/US/JP newsrooms are script-only or 403 here.
- **Kia Carens / Clavis CNG, 6,200 dispatches (#3198):** reviewer ceiling 10, and no press image.
- **Verna 5-star Bharat NCAP:** official images are at most 600 px tall, and Commons has nothing of the facelift.
- **Tata Sierra EV Bharat NCAP:** no image, and the Sierra already led 2 posts this week.
- **October bestsellers:** already ran 10 Nov (lane item brezza-wagonr-10nov).
- **MINI Cooper SE:** no price yet, and no India release.

## Leads for later runs
- MINI Cooper SE India price on 27 Nov: the BMW Group India newsroom will have hi-res images.
- VW Virtus facelift prices on 11 Dec.
- Innova Hycross facelift on 25 Nov.
- Kia line-up rejig: Seltos iMT dropped.
- NHAI toll-plaza SMS alert for expired insurance: pilot at Mundka, UER-II.
- Honda Rebel 500: post it if an official Honda image of 1080 px or more turns up.
