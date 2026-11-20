# @idlytech 17:00 slot: handoff: READY

- **Status:** READY. G1 BUILD (ceiling 14). G2+G3: FIX on three bullets, applied; picture PASS. G4: FIX on the cover framing, re-framed. G4-r1: PASS 14/14. Not published; no git run.
- **Folder:** posts/2026-11-20/idlytech-1700-upi-pin-ruling
- **Headline:** Consumer Panel: UPI PIN Alone Isn't Proof, SBI Owes ₹85,000
- **Format:** news carousel, cover + 3 detail slides (01-04.jpg): a consumer ruling plus what RBI's rules give fraud victims now and from 1 Jan 2027.
  - 02: ₹85,000, "SBI Must Pay for Unauthorised ₹55,000 UPI Debit"
  - 03: 3 WORKING DAYS, "Tell Your Bank About UPI Fraud Within This"
  - 04: 1 JAN 2027, "RBI's New Window: 5 Calendar Days to Report"
- **idly article:** none (story_id null). Post with `--no-idly-article`; the caption has a Sources line.
- **Tag:** none. The cover is a Wikimedia Commons photo by an individual, not SBI's own image.
- **Image:** SBI branch on Radhapuram Road, Vadakkankulam (Tirunelveli, Tamil Nadu), photographed 8 May 2026.
  - Source: https://commons.wikimedia.org/wiki/File:SBI,_Vadakkankulam_branch,_Radhapuram_Road.jpg, by Sujithshivam511, CC BY-SA 4.0, own work.
  - Saved through dl.py from Commons' 1920x3413 rendition: faces 0, sharpness 920.6, viewed.
  - Credit, on the cover and as the caption's last line: "Photo: Sujithshivam511 / Wikimedia Commons, CC BY-SA 4.0"
  - Framing: zoom 1.2, focal [0.4167, 0.5274], crop (0, 800, 1600, 2000), downscale to 0.675. The signboard sits at y≈170-446. The arch lettering and badges sit above the headline. Both motorbike plates are cropped out, and there are no people.
- **Scores:** self 14/14; reviewer 14/14. Post score (per-check minimum, score.json) is 14/14.
- **Checks:** checkcopy 0 errors; prepublish.py no problems (posts_24h 2).
  - Its two warnings are expected. The TN-baseline warning is a number-pattern false positive: this is no TN politics or courts story, so **no baseline**, and nothing to log. The "crime without alleged" warning fires on generic "fraud"/"scam"; the customer's claim is attributed ("She says...").

## Gates
| gate | outcome |
|---|---|
| G1 | BUILD #1 (ceiling 14). NO BUILD for Motorola Edge 70 Neo (ceiling 9-10) and Lava Smart 4 Pro (ceiling 10). Fixes applied: "alone" plus who decided on the cover, labels at 8 words or fewer, "tell your bank", bank + 1930 on the 2027 slide, not called a court or final. |
| G2+G3 | FIX: three bullets. Slide 4 now carries the "losses to ₹50,000" condition. Slide 3 now reads "your loss capped" and "The SBI customer told her branch on day 3". All applied. Picture PASS. |
| G4 | FIX on the cover only: the arch's "Blessings of prosperity" line and the badge lettering collided with the headline. Slides 02-04 PASS. |
| G4-r1 | Re-framed to zoom 1.2, focal y 0.5274 (my crop; the reviewer's suggested crop still left the badges behind line 1). **PASS 14/14.** |

## Facts (all URLs in meta.json fact_sources)
- **Ruling:** Telangana State Consumer Disputes Redressal Commission, order 10 Nov 2026.
  - ₹55,000 left the customer's SBI account by UPI on 3 Nov 2022.
  - The PIN alone doesn't prove she authorised it; the bank must show it.
  - Her complaints (cybercrime portal 6 Nov, branch 7 Nov) were in time, with Sunday excluded.
  - SBI must pay ₹55,000 + ₹20,000 + ₹10,000 = ₹85,000.
  - Sources: MediaNama (20 Nov), Law Trend (17 Nov), The420.in.
- **RBI 2017 rule** (RBI/2017-18/15): zero liability within 3 working days; 4-7 working days capped at ₹5,000-₹25,000 per transaction; burden of proof on the bank. Sources: RBI, The Better India.
- **RBI 2027 rules** (RBI/2026-27/167, issued 24 Jun 2026, from 1 Jan 2027):
  - 5 calendar days for zero liability.
  - Report to the bank and to 1930 or cybercrime.gov.in.
  - Burden of proof on the bank.
  - Once-in-a-lifetime 85% of the loss, max ₹25,000, on losses up to ₹50,000, including customer-negligence cases, for frauds in the first year.
  - Sources: RBI, MediaNama (25 Jun 2026), CorpLawUpdates, The Bar Bulletin.
- **Left out:**
  - "UPI" on the RBI 2027 slide (RBI's text says "electronic funds transfer" and doesn't name UPI).
  - Any claim that the order is final.
  - The ₹10,000 savings-account cap (RBI-only).

## Dropped candidates
- **Motorola Edge 70 Neo India launch, 24 Nov** (Flipkart microsite, Beebom, Digit, TelecomTalk): no ₹ price, so no stake and nothing to keep. G1 ceiling 9-10.
- **Lava Smart 4 Pro ₹10,999** (FoneArena, Gadgets 360): a plain launch price for a narrow audience, and the second product-price card today. G1 ceiling 10.
- **Not sent to G1:**
  - TRAI Network Anubhav dashboard: launched 4 Nov, not new.
  - UPI MDR delay: unnamed sources again.
  - Android developer verification, Jan 2027: India not named.
  - SatSure ₹200 cr Series B (Antariksh VC Fund's second investment): narrow audience.
  - Urban Company ₹2,500 cr QIP: matters to shareholders only.
  - Xiaomi 18 Pro "₹1.7 lakh": tipster only.
  - Anthropic IPO (#3251): no India angle as strong as this one.
  - Airtel Travel Week, Instagram Story edits, Gemini on Mac: dropped in earlier runs for the same reasons.

## Leads for later runs
- Motorola Edge 70 Neo on 24 Nov, once the ₹ price is out.
- Razorpay UDRHP "by next week" (Inc42 report): wait for the filing.
- RBI's 2027 fraud rules as a standalone explainer closer to 1 Jan 2027.
- NPCI and UPI apps asking Google to curb sideloaded APKs (MediaNama report), if it's confirmed officially.
- JioMart refund-to-wallet "dark pattern" consumer order (MediaNama, 19 Nov), if a second source appears.

## Notes for main
- No lane item. Stories and Reels not requested.
- Commons rate-limited upload.wikimedia.org (429) during this run. thumb.wikimedia.org worked.
