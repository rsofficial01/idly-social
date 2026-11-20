# Handoff: idlytech-2057-bike-taxi-karnataka

STATUS: READY. Post score 13/14 (per-check min of self 13 and reviewer 13: hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2).

- Account: @idlytech. Format: news carousel (cover + 2 detail slides).
- Headline: "Supreme Court: Bike Taxis Can Keep Running in Karnataka"
- story_id: null; idly_article: false (no idly.news article on this ruling in candidates.json). Caption uses a "Sources:" line, no idly.news mention.
- Tag: none (cover is an individual's Commons photo, not a brand's own image).
- Image: Wikimedia Commons "Supreme Court of India.jpg" (Central Wing), Subhashish Panigrahi, CC BY-SA 4.0, 1920px rendition of 2959x1973 (original refused by upload.wikimedia.org, HTTP 429). No people. Credit: "Photo: Subhashish Panigrahi / Wikimedia Commons, CC BY-SA 4.0". Cover focal [0.30, 0.5], zoom 1.0, upscale 1.05.

## Gates
- G1: BUILD #1 (this story); #2 Android developer verification and #3 Anthropic Indian retail: NO BUILD. Conditions: attribute Justice Sharma's remarks, no "permits granted" wording, Karnataka + bike taxis on every slide, Rapido/Uber/Ola once, SC building photo acceptable with no people, flag cross-page overlap to main.
- G2+G3: words PASS; FIX cover framing (focal 0.34 -> 0.30 so the logo clears the cupola). Fixed.
- G4: PASS 12 (reviewer: hook 2, read 2, send 1, keep 1, reply 2, original 2, alone 2). Optional keep lift suggested (where permits are applied for). Taken: slide 2 bullet 2 and one caption sentence changed; re-sent as G4-r1.
- G4-r1: PASS 13 (reviewer: hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2). send 1: Karnataka-only and keeps the status quo.

## Facts with sources
1. 20 Nov 2026: SC (Justices Satish Chandra Sharma, N Kotiswar Singh) dismissed Karnataka's SLP against the Karnataka HC division bench ruling of 23 Jan 2026 lifting the bike-taxi ban. Bar and Bench, LiveLaw, Moneycontrol, Inc42.
2. Five auto/taxi driver associations' appeals also dismissed; continuation of bike taxi services permitted. Bar and Bench.
3. Services running since the 23 Jan HC ruling. Deccan Herald (30 Jan 2026), Bar and Bench.
4. HC: owners can apply to register motorcycles as transport vehicles / contract carriages; RTAs may impose conditions (s.74(2) MV Act) but can't refuse merely because it's a two-wheeler. Bar and Bench, Moneycontrol, Inc42; MV Act s.74 (MoRTH, AdvocateKhoj).
5. Justice Sharma: "better to regulate it than ban it"; bike taxis "already there in 25 states"; his women staff said autos cost "five times". Moneycontrol, LiveLaw, Bar and Bench.
6. Karnataka cited passenger safety and insurance concerns. Bar and Bench, Inc42.
(URLs in meta.json fact_sources.)

## Dropped candidates
- Android developer verification, global rollout from Jan 2027 (Google blog 19 Nov) + NPCI asking Google to curb sideloaded APKs: no India date ("all countries over several months"), NPCI angle only context; G1 ceiling 10.
- Anthropic IPO, Indian retail rush (INDmoney 40%, Mudrex 35%, Vested #2; $83 IPO vs $111.50 open): India figures single-outlet, narrow audience, live prices, no subject image; G1 ~9.
- Motorola Edge 70 Neo (24 Nov India launch): no ₹ price yet.
- Lava Smart 4 Pro ₹10,999: narrow (dropped at 17:00 too), nothing stronger to pair it with.
- Gemini computer use on Mac (#3242): no India availability or price known.
- Airtel Travel Week (#3149): discounts limited to 2,000 selected customers.
- Vivo X500 India launch 26 Nov: confirmed 12 Nov (stale), no price.
- Razorpay UDRHP / IPO by Feb 2027: report only, not confirmed by the company.
- Jio ₹123 plan (JioPhone only): old plan, narrow, and a telecom-plan post already ran today.
- TRAI Network Anubhav dashboard: launched 4 Nov (stale).
- Dell XPS 16 Creator Edition (from ₹4,49,990), Logitech MX Master 4 Creator Edition: narrow.

## Leads
- Motorola Edge 70 Neo India price on 24 Nov (launch event); Vivo X500 series India prices on 26 Nov.
- Razorpay UDRHP filing (report: by next week) — post when filed.
- NPCI/Google talks on sideloaded APK curbs — post if Google or NPCI announce an India measure or date.
- Uber/Rapido/Ola Karnataka permit applications after this ruling (fare or permit-fee news would make a keepable follow-up).

## Flags for main
- Cross-page overlap: the SC bike-taxi ruling could also suit @idlynews or @idlyautomotive. Only one page should run it.
- Commons upload.wikimedia.org is rate-limiting (HTTP 429) originals; 1920px thumbnails work through dl.py.
