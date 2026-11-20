# Handoff: @idlyhype, 17:00 slot (second pass), Fri 20 Nov 2026

**Status:** READY (G4 PASS), with one condition on the caption (below).
**Headline:** K3G's Raichand House on Airbnb: ₹0, Requests Open 23 Nov
**Format:** news carousel. 01.jpg is the cover; 02.jpg is "23 NOV, 12 PM: Raichand House Booking Requests Open on Airbnb"; 03.jpg is "180: Raichand House Guests in Total, 1-6 Dec"; 04.jpg is "25 YEARS: K3G's Raichand House, Rebuilt in Mumbai".
**Scores:** desk 13/14 (original 1), reviewer 13/14 (original 1), post score 13/14 (per-check min, in score.json).
**story_id:** 3125, idly_article true (main's instruction). The caption carries "Full story on idly.news (link in bio)." on its own line after the question, and has no Sources line.
**Tag:** `airbnb`. Airbnb's own India newsroom page links https://www.instagram.com/airbnb four times (checked 20 Nov, about 17:20 IST). The reviewer verified it at G1-r2.
**Baseline:** none (not Tamil Nadu; checkcopy's TN baseline warning is a false match).

## CONDITION before publishing (reviewer's G4)
idly.news article #3125 says Karan Johar, Hrithik Roshan and Kareena Kapoor "will host the experience". Airbnb's own page says "the experience does not include Karan, Poo or Rohan's appearance", and afaqs flags the same conflict. The card and caption follow Airbnb. Do one of these:
- **Either:** correct #3125's line before the post goes out with "Full story on idly.news (link in bio).",
- **or:** revert to no-idly-article mode. Set story_id null and idly_article false in meta.json, and in caption.txt replace the line `Full story on idly.news (link in bio).` with `Sources: Airbnb, afaqs`. Then post with `--no-idly-article`. That version passed G2 and checkcopy.

## Facts and sources (fetched 20 Nov, about 17:15-17:40 IST)
| Fact | Sources |
|---|---|
| Raichand House from K3G reimagined in Mumbai for the film's 25th year ("At Home with the Raichands") | news.airbnb.com/en-in/the-raichand-house-now-on-airbnb/ ; afaqs (19 Nov) ; Vogue India (20 Nov) |
| Booking requests open 23 Nov 2026 (a Monday), 12 PM IST, at airbnb.com/k3g | Airbnb ; afaqs ; idly #3125 |
| In Mumbai, 1-6 Dec 2026; two-hour experience | Airbnb ; afaqs |
| Priced at ₹0 | Airbnb ; afaqs ; idly #3125 |
| "Each spot covers one guest plus one companion, for 180 guests in total" (afaqs: 180 invitations) | Airbnb ; afaqs |
| Not a contest; needs an active Airbnb profile with a history of positive reviews; government ID; guests pay their own travel to Mumbai | Airbnb ; idly #3125 |
| Grand staircase, family study, Poo's closet; audio tour of the film's moments | Airbnb ; afaqs ; idly #3125 |
| The film's stars won't be there in person | Airbnb ; afaqs |

There are no real people's names on the slides or in the caption. Character names (Poo) are used only as Airbnb uses them.

## Image
- Source: Airbnb's own newsroom press photo, https://news-assets.withairbnb.com/wp-content/uploads/sites/21/2026/11/newsroom1.jpeg (from the newsroom page above).
- Size and checks: 1365x2048, faces 0 (dl.py), sharpness 133.9. I viewed it: no people, no watermark.
- Shows: a gold "Raichands" sign above a wooden console with red roses and pink headphones.
- Credit: "Image: Airbnb" on the cover and as the caption's last line.
- Framing: src/cover_source.png, focal [0.5, 0.3], zoom 1.0, render scale 0.791 (no upscale).
  - The "Raichands" lettering sits at y ≈ 230-470, clear of the logo.
  - The headline (3 lines) starts at y 968.
  - The roses and table sit under the headline gradient.
- Other images: 6 of Airbnb's 8 newsroom images have faces, and dl.py refused them.

## Gates
- **G1** (idlyhype-g1.md): NO BUILD on all three first-pass candidates (AJ3 'Not Nice' ceiling 11, F1 list 12 only on paper, Golden Goose x D'YAVOL X had no image). Main then asked for a wider pass.
- **G1-r2** (idlyhype-g1-r2.md): BUILD, ceiling 13. The fixes are in:
  - the 180 is "in total", following Airbnb's literal wording;
  - eligibility is on a slide in plain words;
  - no real names appear.
- **G23** (idlyhype-g23.md): one FIX, done. "no contest" became "not a contest". I also took the reviewer's optional change: "An audio tour of the film's famous scenes". The picture passed.
- **G4** (idlyhype-g4.md): PASS 13/14, with the article condition above. reviewer-score.json was written by the reviewer.
- Main's caption change to idly-article mode came after G23 (caption only). It was disclosed in the G4 packet.

## Correction check: Uniqlo x Cecilie Bahnsen (the 13 Nov post said India 27 Nov)
- **Confirmed 27 Nov 2026.** Uniqlo India's own store page, https://www.uniqlo.com/in/en/special-feature/collaboration/uniqlo-and-cecilie-bahnsen/26fw/store, says "Available Online + In Select Stores November 27th 2026" (fetched 20 Nov, about 17:15 IST).
- It lists four stores: Ambience Vasant Kunj, Ambience Mall Gurgaon, Phoenix Palladium Mumbai and Phoenix Market City Bengaluru.
- The 13 Nov post was right, so no correction is needed. The 23 Nov date in Fashion Value Chain (4 Nov, https://fashionvaluechain.com/uniqlo-x-cecilie-bahnsen-fw26-collection-launch/) and InFashionBusiness is the outlier.
- There's no new stage before 27 Nov, so it isn't a candidate today.

## Dropped candidates (both passes)
1. **Air Jordan 3 'Not Nice'**, ₹19,295 at Superkicks, ships 21 Nov; US $215. Ceiling 11:
   - one Indian source only;
   - the India price is about par with the US price, so there's no stake;
   - it's the same template as this morning's AJ4 'Bred' cover.
2. **F1 sneakers in India list** (hooked on the Nike-F1 2027 deal). Ceiling 12 only on paper:
   - the deal has no India stake, and nothing on the list is new;
   - every price has one source;
   - the square studio shots can't go full-bleed 4:5.
3. **Golden Goose x D'YAVOL X**: no ₹ price, and every campaign image has faces.
4. **Wider pass, also dropped:**
   - Lululemon Delhi and Off-White Mumbai/Delhi: no dates.
   - Esquire India watch launches: only Timex has a ₹ price, and it isn't new.
   - Highsnobiety non-sneaker items (Evisu, ssstein, Richard Mille): no India stake.
   - Travis Scott x GTA VI AF1: US-only; Nike's India help page says SNKRS is no longer offered in India.
   - Comet Aeres Nubra/Ziro/Sohra: one source, and an Indian-labels list ran 17 Nov.
   - Lists: no theme has 3+ new India items with ₹ prices from 2 sources each. Superkicks' holiday items (Grinch Forum, Eggnog) are sold out.

## Leads for later runs
- **Golden Goose x D'YAVOL X, 24 Nov.**
  - Golden Goose India's page: "November 24th: available online and in selected stores. RESERVE NOW". The stores are New Delhi (The Chanakya), Mumbai (Phoenix Palladium) and Bengaluru (Phoenix Mall of Asia).
  - The press release (ANI/Business Standard, Deccan Chronicle, Tribune, 20 Nov) lists Super-Star sneakers in three unisex colourways plus apparel, with a second drop in early 2027.
  - Build it once goldengoose.com/in shows ₹ prices and product-only shots (`/in/en/ls/dyavol-en_in`). Never use the campaign images, which show people.
- **K3G Raichand House follow-up:** a new stage would be the 23 Nov 12 PM opening (for example, if requests close or fill).

## Main, at publish (17:31 IST)
Reverted to no idly article: idly.news #3125 says the stars "will host"; Airbnb's booking terms say they won't appear. Caption now ends "Sources: Airbnb, afaqs, Vogue India" (story_id null, published with --no-idly-article). Slide 4 bullet changed to "Airbnb says the film's stars won't appear" and re-rendered. Posted: https://www.instagram.com/p/Df9m6NBDR3D/
