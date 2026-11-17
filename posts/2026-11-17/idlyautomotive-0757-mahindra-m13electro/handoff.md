# Hand-off: @idlyautomotive, run 0757 (Tue 17 Nov 2026)

**Status: READY** (last Gate 4 reply 081517-idlyautomotive-g4 = PASS)

## Story
Mahindra Racing revealed the M13Electro on 15 Nov. It is the team's car for the 2027 Formula E season and the first built to the Gen4 rules. Figures: 600 kW (about 804 bhp), 0-100 km/h in 1.8 s, 335 km/h, active all-wheel drive and 700 kW regen. Mahindra is the only Indian manufacturer in the championship. De Vries and Mortara return for a 4th season, and testing at Jarama began on 16 Nov. Formula E moved the Jeddah opener to 16-17 April 2027 (its own notice of 12 Nov). Autocar India and Motoroids report that the season now opens in Mexico City on 16 Jan 2027, and the card and caption attribute that date to Autocar India.
Format: news carousel, 3 slides (cover + 2 detail). story_id null, idly_article false, so the caption has a Sources line and no idly.news mention.

## Candidates and gates
- Gate 1, 081008-idlyautomotive-g1: BUILD A (M13Electro), predicted ceiling 13. The two others were each predicted at 10:
  - B: Bajaj Pulsar 180 delisted again. No official image (Bajaj's page now returns 404).
  - C: Scooter sales cross 10 lakh in October. Only one source, and the send is weak.
  - The idly API candidates were all foreign with no India angle (BMW electric M3, US Honda probe, Defender EV, Mercedes US driver assist), so none was used.
- Gate 23, 081353-idlyautomotive-g23: PASS with 2 fixes, both applied:
  1. The slide 3 bullet now reads "Season now opens in Mexico City, Autocar India reports".
  2. The cover unit is no longer "Kmph". checkcopy's Title Case check rejects lowercase "km/h" in a headline, so the cover uses "KM/H".
- Gate 4, 081455-idlyautomotive-g4: PASS at 12. I then replaced the caption question with "Have you ever watched a Formula E race?" and re-sent.
- Gate 4 re-send, 081517-idlyautomotive-g4: PASS. reviewer-score.json is from this send (13).

## Score
Self 13 (send 1). Reviewer 13 (send 1). **Post score (per-check minimum) = 13/14:** hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2.
Send is weak because the audience is Formula E and Mahindra fans, with no buyer decision attached.

## Image
- Formula E's official studio livery shot of the actual M13Electro: `LJP-MR-S2027-LiveryStudio-103.jpg`.
- Source page: https://www.fiaformulae.com/en/news/teams/mahindra-racing-introduces-the-m13electro-as-gen4-era-begins
- Downloaded at 3200x1800 via dl.py, faces=0. I viewed it: no watermark, and the only lettering is the car's own sponsor decals.
- Credit: "Image: Formula E", on the card and as the caption's last line.
- Framing: focal [0.5, 0.5], zoom 1.0, scale 0.75. The front-wing tips touch the frame edges and the nose decals sit under the headline gradient. The reviewer accepted this.
- No other official image exists yet:
  - Mahindra's newsroom release has no downloadable image.
  - mahindraracing.com hasn't been updated.
  - Formula E's team-page image is the old Gen3 car.
  - The Jarama gallery images are Getty-numbered agency photos, which I avoided.

## Tags (meta.json)
- `mahindraracing`: https://www.mahindraracing.com/ footer links to instagram.com/mahindraracing. Mahindra Racing makes the car.
- `fiaformulae`: fiaformulae.com article pages link to instagram.com/fiaformulae. Formula E published the cover image.
- I could not see the verified badges from here, so main may want to check both.

## For main to re-check
- The Mexico City 16 Jan opener comes from press reports (Autocar India, Motoroids, NewsBytes). Formula E's own 12 Nov notice moves Jeddah to April but does not name the new opener. Re-check it before publishing, in case Formula E has posted the updated calendar since.
- Same-topic spacing is fine: there was no Mahindra or Formula E post in the last two days.
- Fact URLs are in meta.json `fact_sources`. The key one is Mahindra's own release: https://www.mahindra.com/news-room/press-release/en/mahindra-racing-unveils-new-m13electro-as-formula-e-enters-the-gen4-era
