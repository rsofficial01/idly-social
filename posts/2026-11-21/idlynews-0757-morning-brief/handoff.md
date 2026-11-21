# Handoff: @idlynews Morning Brief, Sat 21 Nov 2026 (07:57 slot)

**Status:** READY. G4 PASSED. Not published (main publishes).
**Folder:** posts/2026-11-21/idlynews-0757-morning-brief
**Format:** special (Morning Brief): a cover plus 4 detail slides, one story each. idly_article false, story_id null.
**Cover headline:** Nitish Setu, Bihar's 9.7‑Km Ganga Bridge, Opens Today; Modi Visits 1:15 PM (the "9.7‑Km" hyphen is U+2011, non-breaking)
**Slides:** 2 train-noise fine "₹1,000" · 3 Rajasthan panchayat polls "33 OF 37" · 4 Nepal PM's talks with Modi "23 NOV" · 5 KL Rahul's first Test hundred in New Zealand "100"
**Tag:** none. The cover is open Copernicus Sentinel-2 data, not a brand's image.

**Before you publish:**
- Publish this morning, before about 13:00 IST. The cover says "Opens Today; Modi Visits 1:15 PM" (PMO schedule), and it goes stale once the visit happens.
- Slide 5 and the caption say Rahul's hundred came "Day 3, after lunch". That stays true. If India's innings has ended, or Rahul is out for a big score by publish time, the caption's cricket sentence could be updated, but nothing on it is wrong as it stands.
- There is no TN content. checkcopy's TN-baseline warning is a keyword match on Modi/Congress; `pipeline.baseline check` raised no STOP.

## Candidates (G1)
- A. **Nitish Setu opens today** (lead, Sentinel-2 cover of the actual bridge): BUILD, ceiling 13. Built.
- B. **Loud calls on trains: ₹1,000 fine** as the lead: NO BUILD as lead. The only cover available was an empty AC-coach photo, which is a representative image. It runs as slide 2.
- C. **Cyclone Akvan weakens into a depression**: NO BUILD, ceiling 10. The danger has passed, it would be the 9th Akvan post, and the cloud-swirl cover would repeat. Not in the caption.
- Yesterday's carried leads: EPFO SWP has nothing new (CBT approval only, no notification found). NEET-UG trial has nothing new before 25 Nov. Thiruparankundram lamp ran 20 Nov at 17:00, nothing new since.

## Gates (blind reviewer)
- G1: A BUILD. Conditions:
  - Sentinel-2 bridge readable at 1080 px with no upscaling, exact Copernicus credit.
  - Cost off the cover and attributed to the PMO; 9.7 km consistent; time on the cover; name explained; RJD line attributed, caption only.
  - Train slide checked against the statute; Rajasthan from SEC figures plus a second source; cricket settled numbers only.
  - All met.
- G23: FIX, applied exactly:
  - Slide 2 bullet 3 now carries both statute alternatives.
  - National Herald (Congress-linked) replaced as a source by Deccan Herald and The Tribune.
  - Slide 3 bullet now says "Of 37 districts counted".
  - I also took the optional headline change ("Ganga Bridge" on the cover) and named Shah in slide 4 bullet 1.
  - Picture PASS.
- G4: PASS 13. All five slides were checked at full size: full-bleed native image, bridge visible end to end, one left edge, no collisions, credit identical on the cover and the caption's last line.

## Scores
- Desk self-score: 13/14 (hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2)
- Reviewer: 13/14 (hook 1, read 2, send 2, keep 2, reply 2, original 2, alone 2), in reviewer-score.json, unchanged.
- Post score (per-check min, mkscore.py → score.json): **12/14** (hook 1, send 1). PASS at the 12 bar.

## Key facts and sources
| fact | sources |
|---|---|
| PM visits Nitish Setu about 1:15 PM on 21 Nov and dedicates it, among projects worth about ₹34,470 crore in Vaishali | https://www.pmindia.gov.in/en/news_updates/pm-to-visit-bihar-on-21-november/ · https://www.thehansindia.com/news/national/pm-modi-to-unveil-development-projects-worth-rs-34470-crore-in-bihar-today-1144298 |
| Six-lane extradosed cable-stayed Ganga bridge, Kachchi/Kachhi Dargah (NH-22, Patna) to Bidupur (NH-322, Vaishali). PMO: about ₹4,280 crore, 9.7 km main bridge plus 10 km approaches, eases Mahatma Gandhi Setu and JP Setu. DH (officials) says ₹5,500 crore and 9.76 km, so the cost is attributed to the PMO | PMO (above) · Hans India (above) · https://www.deccanherald.com/india/bihar/pm-modi-to-inaugurate-nitish-setu-over-ganga-in-bihar-on-november-21-4225023 |
| Bihar govt named it after Nitish Kumar; the RJD objects to naming it after a living leader | DH (above) · https://etvbharat.com/en/bharat/explained-nitish-setu-the-naming-controversy-special-features-cost-and-benefits-enn26112006371 |
| Eastern Railway (20 Nov, per a Railway Board advisory): speaker-mode media and loud calls may draw action under Railways Act s.145 | https://indianexpress.com/article/india/loud-phone-calls-playing-music-inside-trains-six-months-jail-railway-rules-10971775/ · https://www.deccanherald.com/india/playing-loud-music-videos-on-trains-may-invite-rs-1000-fine-six-month-jail-eastern-railway-4225718 |
| s.145(2) as substituted by the Jan Vishwas (Amendment of Provisions) Act, 2026: ₹1,000 fine for nuisance; continuing after being told to stop, up to 6 months' simple imprisonment or up to ₹5,000 fine or both | https://indiacode.ecourtsindia.com/rules/the-jan-vishwas-amendment-of-provisions-act-2026-7e07659e/ · https://www.oneindia.com/india/using-phone-speakers-in-trains-southern-railway-warns-of-fine-up-to-rs-1000-jail-term-8239527.html · https://english.rtvlive.com/loud-calls-speaker-music-and-videos-on-trains-can-now-draw-fines-and-jail-time/ |
| Southern Railway warned similarly in October | Oneindia (above) · https://news24online.com/india/attention-train-travellers-playing-music-loud-phone-calls-on-train-may-get-you-6-months-in-jail-indian-railways-makes-big-announcement-check-details/944837 |
| Rajasthan: Congress won more Panchayat Samiti seats than the BJP in 33 of 37 counted districts; BJP ahead in Ajmer, Balotra, Salumber, Udaipur; Congress 3,700+ and BJP about 2,200 seats (SEC) | https://www.hindustantimes.com/india-news/congress-sweeps-rajasthan-panchayat-polls-wins-548-zila-parishad-seats-as-bjp-suffers-setbacks-101795185273336.html · https://www.deccanherald.com/india/rajasthan/congress-wins-big-in-rajasthan-panchayat-elections-leads-in-33-of-37-districts-4225638 · https://www.tribuneindia.com/news/india/cong-beats-bjp-in-rajasthan-panchayat-zila-parishad-polls/ |
| Nepal PM Balendra Shah: state visit 22-23 Nov, his first to India since March; calls on President Murmu; talks with Modi 23 Nov (MEA) | https://indianexpress.com/article/india/nepal-pm-balen-shah-india-visit-modi-trade-energy-tech-talks-10972063/ · https://www.tribuneindia.com/news/bilateral-talks/nepal-pm-to-be-offered-all-state-honours-talks-focus-on-development-energy-ties-connectivity-with-pm-modi-during-visit-mea |
| KL Rahul's first Test hundred in New Zealand (Day 3, after lunch); he now has Test hundreds in England, Australia, South Africa and New Zealand; Padikkal out for 80; NZ 368 | https://indianexpress.com/article/sports/cricket/india-vs-new-zealand-1st-test-day-3-live-cricket-score-ind-vs-nz-2026-series-match-today-updates-10972018/ · https://www.hindustantimes.com/cricket/india-vs-new-zealand-live-score-1st-test-day-3-ind-vs-nz-latest-updates-scorecard-wellington-november-21-101795194753027.html · https://www.outlookindia.com/sports/cricket/india-vs-new-zealand-1st-test-day-3-live-score-ind-vs-nz-scorecard-latest-updates-highlights · https://www.deccanchronicle.com/sports/cricket/live-ind-vs-nz-1st-test-india-reach-2391-at-lunch-on-day-3-2006491 |

## Image provenance
- Copernicus Sentinel-2C L2A, item S2C_MSIL2A_20261117T045051_R076_T45RUJ_20261117T073753 (17 Nov 2026, 04:50 UTC, 0.03% cloud). True-colour "visual" (TCI) asset, rendered through Microsoft Planetary Computer's open data API: https://planetarycomputer.microsoft.com/api/data/v1/item/bbox/85.2494,25.5151,85.3580,25.6383/1080x1350.jpg?collection=sentinel-2-l2a&item=S2C_MSIL2A_20261117T045051_R076_T45RUJ_20261117T073753&assets=visual&asset_bidx=visual%7C1%2C2%2C3&nodata=0
- Licence: Copernicus Sentinel data, free and open (attribution required). Credit on the cover and the caption's last line: "Image: Contains modified Copernicus Sentinel data, 17 Nov 2026".
- 1080x1350 at about 10 m/px (native, framing upscale 1.0). dl.py faces=0. Viewed. Local: _work/2026-11-21-hourly-0757/desks/idlynews/nitish-setu-s2-17nov-tight.jpg (framing output frame_1/cover_source.png).
- Process note: one 1104x1380 test crop (s2test.jpg) was first pulled with curl before I ran it through dl.py (faces=0). Satellite data at 10 m can't show a face. Everything used was downloaded through dl.py.

## For Rahul
- Left out (designated person): on 20 Nov a US court sentenced Nikhil Gupta to 235 months (19 years 7 months) in the murder-for-hire plot against Pannun. It is widely covered (The Hindu, Indian Express, ThePrint). Not built, per the designated-person rule.
