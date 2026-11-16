# @idlynews hand-off, run 2057 (Mon 16 Nov 2026)

**Status: READY** (G4 PASS, reviewer total 13/14, reply 1)

- Folder: posts/2026-11-16/idlynews-2057-cyclone-akvan-landfall/ (post.json, caption.txt, alt.txt, 01-04.jpg,
  render_report.json)
- Headline: "IMD: Cyclone Akvan to Cross Andhra Coast Around Noon 20 Nov"
- Format: news carousel, cover + 3 detail slides
- story_id: no idly article (publish with `--no-idly-article`; caption has no idly.news / link-in-bio line)
- Why it clears last run's lead rule: new stage since the 07:57 Morning Brief (which said "IMD has not named a
  landfall point"): IMD now gives a landfall point and time (Nellore-Tuni, around noon 20 Nov), and the system became
  Cyclonic Storm "Akvan" at 17:30 IST (IMD 20:35 IST bulletin).
- Before publishing: re-check IMD for a newer bulletin (at 21:14 IST the newest was the 20:35 all-India bulletin;
  national bulletin page still lists NB8). If the landfall place/time changes, the card must change.

## Facts and sources (each fact: IMD primary + at least one outlet)
1. Forecast to cross Andhra Pradesh & Yanam coasts between Nellore and Tuni around noon 20 Nov as a very severe
   cyclonic storm, 120-130 km/h gusting to 145 km/h
   - IMD National Bulletin No. 8 (16:00 IST): https://mausam.imd.gov.in/backend/assets/cyclone_pdf/8__National_Bulletin_No_8-16Nov2026_1130IST.pdf
   - IMD All India Weather Bulletin (20:35 IST): https://internal.imd.gov.in/section/nhac/dynamic/allindianew.pdf
   - ANI (14:22 IST): https://aninews.in/news/national/general-news/deep-depression-over-bay-of-bengal-likely-to-intensify-into-very-severe-cyclonic-storm-cross-andhra-coast-on-november-2020261116142210/
   - Lokmat Times (15:07 IST): https://www.lokmattimes.com/national/cyclone-akvan-live-tracking-map-cyclonic-storm-likely-to-cross-andhra-coast-between-nellore-and-tuni-by-november-20-a517/
2. Became Cyclonic Storm "Akvan" on Monday evening (17:30 IST)
   - IMD All India Weather Bulletin (20:35 IST), link above; IMD TCAC advisory "TC: AKVAN": https://rsmcnewdelhi.imd.gov.in/uploads/archive/3/3_aacd4df6c29b77690164.pdf
   - ETV Bharat (to be named Akvan on formation, by Monday evening): https://www.etvbharat.com/en/bharat/cyclone-akvan-imd-update-very-severe-storm-to-reach-andhra-pradesh-coast-on-november-19-heavy-rain-in-odisha-andhra-tamil-nadu-puducherry-enn26111601377
   - ANI (cyclonic storm by Monday evening), link above
3. Extremely heavy rain (21 cm or more, isolated) in coastal Andhra 19-20 Nov
   - IMD NB8 and 20:35 bulletin (links above)
   - Deccan Chronicle (ANI, 08:24 IST): https://www.deccanchronicle.com/nation/current-affairs/bay-of-bengal-depression-to-intensify-into-cyclone-heavy-rain-likely-in-tn-2004764
   - ANI 14:22 ("extremely heavy falls at isolated places" 19-20 Nov)
4. Flooded roads / waterlogging in low-lying areas: IMD NB8; Deccan Chronicle (ANI)
5. Heavy rain in Rayalaseema: IMD NB8 (19-20 Nov); ANI
6. North Tamil Nadu (and Puducherry, caption) very heavy rain 18-19 Nov: IMD NB8; Deccan Chronicle (ANI); ETV Bharat
7. Odisha heavy to very heavy rain 19-21 Nov: IMD NB8; Deccan Chronicle (ANI)
8. Telangana heavy rain 20 Nov: IMD NB8 (very heavy, eastern Telangana); ETV Bharat (heavy)
9. Third cyclone to head for the Andhra coast since 28 Oct, after Arnab and Murasu: ETV Bharat; Lokmat Times (landfall
   places differ between outlets, so none used)
- Dropped: storm surge 1-1.5 m in six districts (only IMD + one unknown site, transclew); fishermen dates (IMD says
  central Bay to 20 Nov, ETV Bharat says to 21 Nov).

## Image
- NASA Worldview snapshot, VIIRS on NOAA-20, true colour, 16 Nov 2026 (today's daytime pass), bbox 7-23N, 76.2-89E
- Page: https://worldview.earthdata.nasa.gov/?v=76.2,7,89,23&l=VIIRS_NOAA20_CorrectedReflectance_TrueColor&t=2026-11-16
- Image URL: https://wvs.earthdata.nasa.gov/api/v1/snapshot?REQUEST=GetSnapshot&TIME=2026-11-16&BBOX=7,76.2,23,89&CRS=EPSG:4326&LAYERS=VIIRS_NOAA20_CorrectedReflectance_TrueColor&WRAP=day&FORMAT=image/jpeg&WIDTH=1920&HEIGHT=2400
- Licence/owner: NASA EOSDIS GIBS via NASA Worldview, US government work, public domain. Credit on card and caption:
  "Image: NASA Worldview / VIIRS" (caption: "Image: NASA Worldview / VIIRS (NOAA-20), 16 Nov 2026")
- Size 1920x2400; dl.py OK, 0 faces; opened and checked: no people, no watermark
- Local: _work/2026-11-16-hourly-2057/idlynews/raw/VIIRS_NOAA20_CorrectedReflectance_TrueColor.jpg
- Framing: {"ok": true, "photo": "_work/2026-11-16-hourly-2057/idlynews/frame_viirs/cover_source.png",
  "focal": [0.5, 0.5], "zoom": 1.0, "upscale": 0.56, "faces": 0}
- Not the same still as the 07:57 cover (that was MODIS Aqua, 15 Nov, different crop)
- Tag: no tag

## Gates
- G1 210953-idlynews-G1: PASS, build Candidate 1 (ceiling 14); conditions: Akvan only if a public IMD bulletin names
  it, two sources per fact (surge dropped), forecast wording, NASA credit, one easy question. All met.
- G23 211309-idlynews-G23: PASS (words and picture). After it I made two small copy edits (slide 2 bullets to remove a
  repeated "IMD says"; slide 4 bullet 1 shortened to avoid an orphan wrap), declared at G4.
- G4 211357-idlynews-G4: PASS, all 4 slides checked at full size (full-bleed cover, headline on scrim, credit clear,
  no overlap/cut-off, dates on every detail slide); reviewer total 13 (reply 1). Reviewer: re-check IMD for a newer
  bulletin right before publishing. Reviewer score file: _work/2026-11-16-hourly-2057/scores/idlynews-reviewer-G4.json

## G1 candidates and why the others were dropped
1. Cyclone Akvan landfall forecast (built).
2. Allahabad HC (CJ Arun Bhansali, Justice Kshitij Shailendra; LiveLaw 15 Nov): grandparents' wealth no ground to deny a
   mother custody of her 8-year-old. Dropped: reviewer ceiling ~10, restates settled law, one source, no date for readers.
3. Modi at ASEAN-India/East Asia summits, Manila, 17 Nov. Dropped: nothing concrete for Indians yet, ceiling ~7.

## Schedule note
Same topic as the 07:57 lead; 07:57 posted at about 08:25 IST, so far more than 2 hours apart. Not a reused cover still.
