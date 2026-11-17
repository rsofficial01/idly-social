# Hand-off: @idlynews, 17 Nov 2026, 11:57 run

**STATUS: READY**

- Folder: posts/2026-11-17/idlynews-1157-us-student-stay-cap (01.jpg, 02.jpg, 03.jpg, post.json, caption.txt, alt.txt, meta.json, render_report.json)
- Headline: US Judge Scraps 4-Year Cap; Indian Students Keep Full-Course Stay
- Format: news carousel, cover + 2 detail slides. story_id null, idly_article false.
- Story: On 16 Nov (US time), US District Judge F. Dennis Saylor (Boston) struck down the DHS rule that would have capped F-1/J-1 stays at 4 years (then an extension needed), cut the post-study grace period from 60 to 30 days and capped journalists at 240 days. The rule never took effect (postponed 14 Sept). India sends the most students to the US: 3,63,019 in 2024-25 (Open Doors 2025).

## Gates
| gate | packet id | outcome |
|---|---|---|
| 1 | 121504-idlynews-g1 | A BUILD (ceiling 13); B Cyclone Akvan HOLD 11; C Calcutta HC contempt HOLD 10 |
| 23 | 121827-idlynews-g23 | PASS (G4 notes: VERTEX sign, slide 3 label, re-render) |
| 4 | 122127-idlynews-g4 | PASS 13: 1/2/2/2/2/2/2 (hook soft: no India on cover) |
| 4 (2nd) | 122225-idlynews-g4 | PASS 14: 2/2/2/2/2/2/2 after cover headline change |

Score file: _work/2026-11-17-hourly-1157/gates/scores/idlynews.json (14). The post's score (lower of mine and the reviewer's, per check) is 2/2/2/1/2/2/2 = 13.

## Image
- Commons: https://commons.wikimedia.org/wiki/File:John_Joseph_Moakley_United_States_Courthouse_September_2024.jpg
- Fetched the 3840px thumbnail (https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/John_Joseph_Moakley_United_States_Courthouse_September_2024.jpg/3840px-John_Joseph_Moakley_United_States_Courthouse_September_2024.jpg); original 6000x4000.
- Author 4300streetcar (own work), CC BY 4.0. Credit: "Photo: 4300streetcar / Wikimedia Commons, CC BY 4.0" (cover and last caption line).
- Subject: the John Joseph Moakley US Courthouse, Boston, where the US District Court for Massachusetts sits (the court that ruled).
- Framing: focal [0.5, 0.5], zoom 1.0, upscale 0.53, faces 0 (used as given).
- Tag: none (Commons photographer, no official account).

## Main should re-check
1. The final headline wording is the reviewer's own suggestion from the 2nd G4 pass ("not blocking"). I applied it after that pass and re-rendered: 3 lines, 88px, no overflow. The reviewer saw the near-identical "Judge Scraps 4-Year Cap; Indian Students in US Keep Full-Course Stay".
2. A "VERTEX" company sign is on an office tower behind the courthouse (top left, about 215-250 px, clear of the logo band). The reviewer accepted it as incidental. It is behind the courthouse in every Commons harbour view I checked.
3. Face checks: OK on the full source, on the exact cover region and on the rendered 01.jpg. A tighter crop made to drop the sign was QUARANTINED (tiny figure, likely on the motorboat) and never opened. In the published cover, the boat figures behind the headline can't be identified.
4. Wikimedia returned 429 to dl.py's browser user agent. I fetched the thumbnail with curl and a descriptive UA into the scratchpad, then ran dl.py on that local file before opening it.
5. Appeal wording: per ANI, the government appealed the 14 Sept order to the First Circuit, and it was pending. Per VisaVerge, the First Circuit put it in abeyance on 13 Nov, and DHS hasn't said whether it will appeal the final ruling. So the copy says "had appealed the September order" and "can still appeal".
6. Open Doors 2026 may come out this week. Our figure is labelled 2024-25 everywhere.
7. checkcopy prints a Tamil Nadu baseline WARN, which is a keyword false positive (no TN content).
