# @idlyhype hand-off, run 2057 (Mon 16 Nov 2026)

**Status: READY** (image swapped to Nike's own product image at main's request. G23 picture re-run PASS and G4 re-run PASS,
reviewer 13/14, self 13; post score = per-check min = 13, send 1)

- Folder: posts/2026-11-16/idlyhype-2057-nike-mind-india/ (01-04.jpg, post.json, caption.txt, alt.txt, render_report.json)
- Headline: "Nike Mind 002 Costs ₹12,795 in India. Four New Models Are Coming"
- Format: news carousel, cover + 3 details (SUMMER 2027 / ₹12,795 / FALL 2027)
- story_id: no idly article. Publish with `--no-idly-article` (the caption has no idly.news line).
- Image credit: "Image: Nike" (last caption line, and on the cover). **No tag** (nike.in has no Instagram link).
- Angle: Complex and Sneaker News led today with Nike's "World of Athletes" 2027 line-up. The card ties it to India through the
  Nike Mind 002's ₹12,795 price on nike.in and at Superkicks.

## Facts and sources
| Fact | Source 1 | Source 2 |
|---|---|---|
| Nike Mind 002 is ₹12,795 in India (every style on nike.in) | nike.in search https://www.nike.in/catalogsearch/result/?q=mind (10 Mind 002 styles, all ₹12,795) and https://www.nike.in/nike-mind-002-men-s-shoes/p/24933550 ("₹12,795", "Inclusive of all taxes", HQ4308-003) | Superkicks https://www.superkicks.in/products/nike-mind-002-flyknit-sanddrift-fossil-rose-plum-eclipse and https://www.superkicks.in/products/nike-mind-002-flyknit-light-bone-saturn-gold-infinite-gold (₹12,795) |
| Superkicks shows both Mind 002 Flyknit colourways unavailable (re-checked 21:25 IST) | Superkicks product JSON, both listings available:false in every size | (stated as a Superkicks listing status, not "sold out") |
| Four new Nike Mind shoes: Mind Sock, Sneaker, Slip, Moc Flyknit | Nike newsroom https://about.nike.com/en/newsroom/releases/nike-training-introduces-prime-train-recover-a-connected-system-built-around-athlete-progress | Sneaker News https://sneakernews.com/2026/11/16/nike-mind-2027-footwear-models/ ; Complex https://www.complex.com/sneakers/a/victor-deng/nike-mind-lineup-2027-release-date |
| From summer 2027 | Complex (same URL) "beginning in summer 2027" | Sneaker News (same URL) "Summer 2027" (Nike: "debut in 2027") |
| Mind Sock keeps 22 separate nodes (most intense); Sneaker/Slip/Moc join them, softer | Nike Training release (quotes) | Sneaker News Mind article |
| Shown at the World of Athletes showcase, 16 Nov | Nike main release https://about.nike.com/en/newsroom/releases/nike-inc-unveils-the-next-generation-of-innovation-across-performance-sports-and-sportswear | Sneaker News https://sneakernews.com/2026/11/16/nike-free-returning-in-2027/ |
| Vaporfly 5: fall 2027, prototype, no price, wave-shaped plate between two foams | Complex https://www.complex.com/sneakers/a/victor-deng/nike-vaporfly-5-everything-you-need-to-know | Sneaker News https://sneakernews.com/2026/11/16/nike-vaporfly-5-2027/ |
| Vomero 19, Book 3 (Devin Booker), Nike Free 3.0/5.0 also shown | Nike main + Training releases | Sneaker News (Book 3, Free articles) |
| Nike's announcement gives no prices | Nike releases (none listed) | Complex/Sneaker News: pricing not announced |

## Image (final, after main's ruling at ~21:28 IST)
- Nike's own product render of the Nike Mind 002 (women's, raspberry pink with dark burgundy collar, laces and heel tab), side view,
  light grey studio background. No people, no hands, no watermark. 1728x2160 px (Nike's native 4:5 gallery asset); dl.py: 0 faces.
  The same colourway is on nike.in at ₹12,795 (women's Mind 002, HQ4310-600).
- Source page (Nike's own site): https://www.nike.com/at/en/t/mind-002-womens-pre-game-shoes-2mqfRUAl
  image: https://static.nike.com/a/images/t_PDP_1728_v1/f_auto,q_auto:eco,u_9ddf04c7-2a9a-4d76-add1-d15af8f0263d,c_scale,fl_relative,w_1.0,h_1.0,fl_layer_apply/ae85350c-7976-4618-a89b-2280bb0854a5/W+NIKE+MIND+002.png
- Owner: Nike. Credit "Image: Nike".
- Framing: pipeline.framing gave {"ok": true, "photo": "_work/2026-11-16-hourly-2057/idlyhype/frame_nk_ae85350c/cover_source.png",
  "focal": [0.5,0.5], "zoom": 1.0, "upscale": 0.62, "faces": 0}. post.json uses focal [0.5,1.0] and zoom 1.06 to lift the shoe: it is whole
  at x ~45-1035 and y ~515-955 of 1080x1350, above the headline (top ~985). The reviewer accepted the empty light-grey top third. The
  shoe can't go higher without clipping the toe or heel tab.
- Tag: no tag. nike.in's header and footer carry no Instagram or other social link, so there is no evidence for @nikeindia.
- Not used: the Superkicks shop photo (main ruled it out); Nike newsroom images (hands, and four-shoe compositions that won't crop
  whole); nike.in's 2500x2500 squares (shoe clipped and behind the headline at 4:5). In the nike.com gallery, one image shows legs
  (not used) and dl.py quarantined another (not opened).
- Also fixed: slide 2 bullet 1 is now "Mind Sock, Sneaker, Slip and Moc Flyknit" (one line). Alt text was rewritten for the new photo.
  Every other word is as passed at G23.

## Gates
- G1 211451-idlyhype-G1: HOLD. No candidate reached 12. C1 (Nike showcase) was capped at 11 with no India stake. The reviewer said to
  re-send it if India availability or a ₹ price with two sources could be added.
- G1 212027-idlyhype-G1 (re-angle with nike.in + Superkicks ₹12,795): PASS, ceiling 13. Conditions met: price wording, "unavailable"
  not "sold out" and re-checked, framing shown, one "?", no idly.news line.
- G23 212622-idlyhype-G23: PASS (words; Superkicks image later replaced, see below).
- G4 212654-idlyhype-G4: PASS, 13/14 (send 1), on the Superkicks cover. Minor point: the slide 2 bullet wrap.
- Main overruled the Superkicks photo. The card was re-rendered with Nike's image and the bullet fix.
- G23 213128-idlyhype-G23 (picture only): PASS. Nike product image, "Image: Nike", no tag.
- G4 213152-idlyhype-G4 (re-run): PASS, 13/14 (send 1). scores/idlyhype-reviewer-G4.json updated by the reviewer.

## The three G1 candidates
1. **Nike 2027 line-up (Complex / Sneaker News lead)**: BUILT after the re-angle on the Mind 002's India price.
2. **Superkicks x Retrosuperfuture "Caro" sunglasses** (₹19,999, 50 numbered pairs, Superkicks start date 17 Nov 12:30 IST): dropped.
   Superkicks is the only source (brand and store). retrosuperfuture.com doesn't list it and no outlet has covered it. If a second
   source appears before tomorrow's 12:30 drop, it's a ready India story.
3. **Drops This Week in India (16-22 Nov)**: dropped. Only Nike SB AF1 "Navy" and AJ3 "Not Nice" (both ran 12-13 Nov) plus the
   single-source Caro and adidas "Nora x Welcome" (Superkicks only, ₹8,999) were available. Superkicks' whole catalogue has only
   those three start-date tags.
Also checked and not used: Converse x GOLF le FLEUR Bronco Boot "Cocoa Brown" (on Converse India since 2 Nov; Bronco Boot ran
10 Nov); Crocs Pokemon 30th clogs (not on crocs.in); Indian Sneaker Festival 19-20 Dec (old news, only people/event photos).

## Publishing notes for main
- Schedule rule: no other @idlyhype post today, so there's no clash. Check queue/approved/ for @idlyhype lane items first.
- Nike Mind has not appeared on any idly page in recent_coverage (9-16 Nov).
