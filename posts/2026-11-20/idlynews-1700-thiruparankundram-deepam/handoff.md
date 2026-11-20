# handoff: idlynews 1700, READY

**Status:** READY. Final score **13/14** (per-check MIN: desk 13, blind reviewer 14). Built and rendered 17:26 IST.

- **Folder:** `posts/2026-11-20/idlynews-1700-thiruparankundram-deepam/`
- **Headline (cover):** Supreme Court Allows One-Time Thiruparankundram Hill Lamp on 24 Nov
- **Format:** news, cover + 2 detail slides (24 NOV: who may go up and what's barred; JAN 2027: the next hearing, the three sides, the HC stay, both governments' appeals)
- **Story:** On Fri 20 Nov the Supreme Court (Justices Aravind Kumar and Vipul M Pancholi) allowed a one-time Karthigai Deepam lamp on 24 Nov at the disputed stone pillar on Thiruparankundram hill, Madurai. Only a small temple team may go up, picked by the Collector with the temple EO, ASI and police. The public, gatherings, processions and slogans are barred, and access to the dargah and mosque continues. The court stayed the Madras HC findings on the pillar and land, said this sets no custom or right, and listed the appeals for the 2nd week of January 2027.
- **idly article:** none (`story_id` null). Post with `--no-idly-article`. The caption has a Sources line and no idly.news mention.
- **Tag:** none. The image is an individual's Commons photo, with no brand or maker owner.
- **Image:** Wikimedia Commons "Thirupparankundram Hills..jpg" by Mamichaelraj, CC BY-SA 4.0 (https://commons.wikimedia.org/wiki/File:Thirupparankundram_Hills..jpg). It shows the actual hill from Nilaiyur Road, with no people (dl.py: 0 faces). It is 3840x2560 (5400x3600 original), sharpness 1527. Framing: focal [0.5, 0.5], zoom 1.0, downscale 0.527. The hill sits at y≈220-600 with both summit structures in frame. Credit on the cover and as the last caption line: `Photo: Mamichaelraj / Wikimedia Commons, CC BY-SA 4.0`.
- **Scores:** desk 13 (send 1: mainly Madurai/TN readers); reviewer 14 (after the r1 fix; the first G4 was 13 with alone 1). score.json = 13: hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2.
- **Checks:** checkcopy 0 errors (one generic TN-baseline keyword warning, nothing about this dispute); render.py 0 problems; all three slides viewed at full size.

## Gates
- **G1** (`review/idlynews-g1.md`): BUILD #1 (ceiling 14). NO BUILD for bike taxis (no image of the subject) and Nitish Setu (ceiling 10, image 720 px). The reviewer set the neutrality rules (no "Deepathoon" as fact, the dargah side in the same terms, dated government steps, no religious hashtags) and the question "Have you ever visited Thiruparankundram?". All were applied.
- **G2+G3** (`review/idlynews-g2.md`): PASS on words and picture.
- **G4** (`review/idlynews-g4.md`): PASS 13 (alone 1: no slide named Karthigai Deepam or who disputes the pillar).
- **G4-r1** (`review/idlynews-g4-r1.md`): fixed two slides' bullets (Karthigai Deepam named; "Temple side, dargah and State differ on the pillar"; "High Court findings stayed; this lamp sets no precedent"). PASS 14. The first reviewer score is kept as `reviewer-score.g4-r0.json`.

## Note for main
- This is a communal-site dispute. The copy is strictly attributed: three sides in equal terms and both governments' steps as dated actions. Please don't add hashtags or wording that takes a side.
- Same page, same state: the SC Cauvery post (Tamil Nadu) ran at 12:28. This is a different story, more than 5 h apart.

## TN baseline (log after publishing)
There is no existing baseline item on this dispute (checked before G1 and on the caption: no STOP). Suggested:
```
python3 -m pipeline.baseline log --note "20 Nov 2026: SC (Justices Aravind Kumar, Vipul M Pancholi) allowed a one-time Karthigai Deepam lamp by a small temple team at the disputed Thiruparankundram hill pillar on 24 Nov 2026; public barred; dargah/mosque access undisturbed; Madras HC findings on the pillar and land stayed; not recognition of custom; appeals listed 2nd week Jan 2027. Then DMK govt appealed the Dec 2025 single-judge order; TVK govt filed the SLP on 11 June 2026." --source https://www.barandbench.com/news/litigation/supreme-court-allows-lighting-of-lamp-at-thiruparankundram-as-one-time-measure-but-stays-madras-high-court-observations --keywords thiruparankundram deepathoon "karthigai deepam" madurai dargah pillar hr&ce
```
Consider a `watch.json` item for the SC hearing in the 2nd week of January 2027. Verdictum alone also reports that the Collector must file a compliance report within 3 days of the festival (single source, not used in the post).

## Dropped candidates
- **SC dismisses Karnataka's appeal; bike taxis can run under permits** (20 Nov; Bar & Bench, Indian Startup News, Storyboard18). Reviewer: 12 on words, but NO BUILD. There is no image of a Karnataka bike taxi: Commons has only a 2016 Gurgaon stand, and the SC building is a stand-in already used 16 Nov. There is also no permit-start date (keep 1). Lead for later: rebuild through the lane if an official aggregator or Karnataka transport image exists, or once Karnataka sets a permit process or date.
- **Nitish Setu opens Sat 21 Nov** (ThePrint, Swarajya). NO BUILD, ceiling 10. The only image is a 720 px CC0 file by an unknown author, the length differs by source, and the audience is narrow. Lead: PIB images after Saturday's opening, if they have no people and are 1080+ px.
- **Rajasthan panchayat samiti / zila parishad results** (Congress ahead of BJP in early counts): counting is still incomplete (4 districts deferred to 17 Dec) and it comes from a single live blog (Outlook). Lead for tomorrow's brief once the SEC final tally is out.
- **SCO Civilisational Dialogue Forum at Purana Qila (20-22 Nov), Pakistan minister's visit:** low reader stake; already trailed in the 15 Nov brief.
- **Cyclone Akvan landfall:** led the 07:57 brief. Only a genuinely new stage (damage or deaths figures, restoration) would justify another cover.
- No story this run centred on a banned or designated person or group; nothing to flag for Rahul.

## Leads for later runs
Nepal PM Balendra Shah in Delhi 22-23 Nov (Hyderabad House via Commons); SC unwed-parents custody observation (LiveLaw 20 Nov, needs a second source); SC strikes down UP rule excluding work-charged employees' pre-regularisation service from pensions (LiveLaw, Indian Masterminds); RBI meets NBFC CEOs 23 Nov; Karthigai Deepam 24 Nov itself (the lamp-lighting outcome is a new stage for this story).
