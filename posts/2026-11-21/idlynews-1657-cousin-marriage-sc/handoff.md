READY: posts/2026-11-21/idlynews-1657-cousin-marriage-sc (post 12/14: desk 12, reviewer 12; checkcopy --no-idly-article ERRORS: none)

Publish with `--no-idly-article` (no idly.news article). Ship exactly this card and caption (no margin at 12).

## Gates
- G1-1: BUILD (ceiling 12, send/keep capped at 1). Goa Blue Flag and Siang dam NO BUILD.
- G23-1: FIX: cover "Wives" -> "Married Women"; drop the Hindu Marriage Act / Special Marriage Act sentence. Picture PASS.
- G23-2: PASS (reviewer's exact head overflowed in cardkit; "Top Court Seeks Centre's View" fits at 78px x3).
- G4-1: FIX 11/14 (slide 2 repeated the cover; slide 3 "20 NOV" said nothing). G4-2: PASS 12/14.

## Key facts
- 20 Nov: CJI Surya Kant, Justices Joymalya Bagchi, V Mohana: limited notice; Parliament's domain; not directing legislation; Centre to consider law or awareness incl. curricula. LawTrend, Verdictum, HT.
- Petitioner: 20-year-old law student, parents first cousins, 40% visual impairment (counsel). DH, The Open Press, LawTrend. Not named (cause title "X").
- Plea asks: premarital genetic counselling in high-prevalence areas, voluntary screening, awareness campaign; existing marriages not criminalised. DH, The Pioneer.
- NFHS-5: TN 28% (highest), Karnataka 27%, India ~11% (10.8%), ever-married women 15-49. Dataful, DH (2022), Cureus/PMC.

## Image
Commons File:Supreme_Court_of_India_01.jpg, Subhashish Panigrahi, CC BY-SA 4.0 (1920 rendition, upscale 1.13x). No tag.

## For Rahul / main
- TN story: after publishing, the RUNBOOK says log it: `python3 -m pipeline.baseline log --note "SC limited notice to Centre on consanguineous-marriage health risks (20 Nov 2026); NFHS-5 TN 28%" --source https://lawtrend.in/supreme-court-issues-notice-to-centre-on-health-risks-of-consanguineous-marriages-says-it-cannot-direct-legislation/ --keywords consanguineous cousin marriage NFHS`.
- Manipur spurious liquor (Chandel/Sugnu): 13 dead per officials to PTI, 16 and 370+ hospitalised per Northeast Now; not built: no image of the actual place and licensed_wire is not configured (AP_MEDIA_API_KEY).
- Banned-subject flag: Nikhil Gupta sentenced (19-20 years reported) in the Pannun murder plot; not built.
- Tooling: upload.wikimedia.org returned HTTP 429 to dl.py's browser-like User-Agent most of the run; downloads went through dl.py unchanged via a wrapper that set the UA to `idly-desk/1.0 (https://idly.news)` (all dl.py face/width checks ran). Worth changing dl.py's UA.
