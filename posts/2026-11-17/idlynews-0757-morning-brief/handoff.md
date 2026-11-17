# Hand-off: @idlynews 08:00 Morning Brief, Tue 17 Nov 2026

**Status: READY** (last Gate 4 reply 081853-idlynews-g4 = PASS)

Folder: `posts/2026-11-17/idlynews-0757-morning-brief/` (01-05.jpg, post.json, caption.txt, alt.txt, meta.json, self-score.json, reviewer-score.json, render_report.json). story_id null, idly_article false, format special. No tags.

## The brief (cover + 4 detail slides)
1. Cover / lead: "India vs Pakistan Football Final: 7:30 PM Tonight on Veto App": SAFF Championship final, National Stadium Dhaka, 19:30 IST, Veto app; India holders, record nine titles; Pakistan's first final (AIFF, Khel Now).
2. ₹30 LAKH: Supreme Court awards Devilal Gond ₹30 lakh after 7+ years in jail post-acquittal (HC acquittal Jan 2018, freed May 2025); no law for wrongful-jailing compensation (LiveLaw, ETV Bharat).
3. ₹18.5 LAKH: Supreme Court, DDA v Rajender Kumar Sharma: gratuity can't be withheld just because the State appealed an acquittal (LiveLaw, LawChakra).
4. 2 SUMMITS: PM Modi at the 23rd ASEAN-India and 21st East Asia summits in Manila today; Quad meeting planned per PTI, not confirmed (Daily Excelsior/PTI, The Week).
5. 6 TANKERS: Iran's claim that mines damaged six tankers in Hormuz since Sunday, unverified (AP, TRT World, dpa).

## Gates
- Gate 1 `081142-idlynews-g1`: BUILD A (SAFF lead; predicted ceiling 13). B (SC ₹30 lakh lead) 11; C (Cyclone Akvan lead) 9, HOLD as stale. Conditions: kick-off + Veto on the cover; Hormuz as an attributed claim; Manila "expected/reports", BrahMos only if attributed (dropped: single source); gratuity rule in plain words; one ?.
- Gate 23 `081638-idlynews-g23`: FIX, 6 points (whole-stadium framing at zoom 1.0; no bare "SAFF" on the cover; "Supreme Court" not "SC" on labels; explain the two gratuity sums; slide 4 stat "2 SUMMITS"); all applied, then went to Gate 4 as the reviewer asked.
- Gate 4 `081739-idlynews-g4`: FIX (cover credit hard to read over light roof panels) -> crop nudged to focal [0.4, 0.5], zoom 1.0 -> `081853-idlynews-g4`: **PASS**.

## Score
Self 13 (hook 2, read 1, send 2, keep 2, reply 2, original 2, alone 2). Reviewer 13 (original 1: a round-up of widely reported items). **Post score (per-check minimum) = 12/14** (read 1, original 1): at the gate, not above it. read is 1 on my side because the Hormuz and Manila slides are weaker for Indian readers than the other three.

## Image
Wikimedia Commons "File:National Stadium, Dhaka.jpg" by Jubair Bin Iqbal (Jubair1985), own work, 6 March 2026, **CC BY-SA 4.0**. https://commons.wikimedia.org/wiki/File:National_Stadium,_Dhaka.jpg . Downloaded the 3840x2880 thumbnail via dl.py (faces 0). Aerial view of the actual venue; players are dots. Credit on the cover and last caption line: "Photo: Jubair Bin Iqbal / Wikimedia Commons, CC BY-SA 4.0". The 2018 SAFF-final stills of the same ground were rejected (big Suzuki Dzire promo car, people; several quarantined by the face check, never opened).
Tag evidence: none. The photographer is an individual Commons contributor, not a brand with an official account.

## Main should re-check before publishing
- **Manila is live today.** If a Quad meeting has been confirmed, held or cancelled, or a Modi-Marcos/BrahMos outcome announced by publish time, slide 4 and its caption paragraph ("planned, PTI reports; not officially confirmed") may be out of date.
- **Cyclone Akvan left out on purpose** (IMD Bulletin 12, 05:45 IST: stationary 9 h, forecast unchanged, landfall Nellore-Tuni around noon 20 Nov; no evacuation, school or train orders found). If the 08:30/11:30 bulletin or Andhra Pradesh issues a new stage (cyclone warning, evacuation, school holidays, train cancellations), that is a separate post.
- SAFF final: kick-off 19:30 IST (AIFF; Dhaka Tribune lists 8 pm Dhaka time). The post must go out before kick-off.
- Gratuity second source is LawChakra (a legal-news site; read in full and it matches LiveLaw). Deccan Herald and Dhaka Tribune returned 403, so they are not cited.
- checkcopy gives a generic WARN for the Tamil Nadu baseline (triggered by "Modi"/"Supreme Court"); no Tamil Nadu story is in this brief. No banned or designated groups are mentioned.
- Wikimedia upload.wikimedia.org was returning HTTP 429 (retry-after 600) on original files during this run; thumbnails worked.
