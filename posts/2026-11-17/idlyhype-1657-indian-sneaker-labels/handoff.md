# @idlyhype hand-off, run 1657 (Tue 17 Nov 2026)

**Status: READY.** G4 first pass 172203 PASS 12/14. Main asked for copy fixes, so G4 got a second pass, 172355-idlyhype-g4: "FIX (copy only, then
PASS 12/14)", with a reviewer score file of 12/14. Both FIX items are applied word for word (below). The gate budget allows two
G4 passes, so I did not send a third. Desk score 13. Post score (per-check minimum) = 12: hook 2, read 2, send 1, keep 2, reply 1,
original 2, alone 2.

- Folder: posts/2026-11-17/idlyhype-1657-indian-sneaker-labels/ (01-04.jpg, post.json, caption.txt, alt.txt, meta.json, render_report.json)
- Headline: "Indian Sneakers From ₹3,500: Comet, Gully Labs and Thaely"
- Format: list, cover + 3 detail slides (₹4,499 Comet Aeon V2 Sourbomb / ₹5,990 Gully Labs Number 001 Megh White /
  ₹3,500 Thaely Tech Tabi Sulfur Yellow)
- story_id: null, idly_article false. Publish with `--no-idly-article`; the caption has a Sources line and no idly.news line.
- Tags: ["thecometuniverse"], the image owner. Evidence: Comet's own site (wearcomet.com) links instagram.com/thecometuniverse in its
  footer. The same handle was tagged on the 10 Nov Comet Ajrakh post.
- Image credit: "Image: Comet" (on the cover, and as the last caption line).
- Angle: none of Hypebeast's or Complex's 24-48 h leads had an India listing or ₹ price (see G1). Following the reviewer's G1
  note and the learnings ("try Indian labels and lists"), this is a list of three Indian sneaker labels. Each price matches on
  the label's own store and at an Indian retailer.

## Facts and sources (all read 17 Nov, from each store's own product page and product data)
| Fact | Source 1 | Source 2 |
|---|---|---|
| Comet Aeon V2 Sourbomb ₹4,499 (in stock); neon suede overlay, white mesh, green shooting star (Comet's description) | https://www.wearcomet.com/products/aeon-v2-sourbomb | Comet's Aeon V2 at an Indian retailer: Broadway https://shop.broadwaylive.in/products/aeon-v2-riptide (MRP ₹4,499, the lowest Aeon V2 MRP there; Comet's own Riptide page also shows ₹4,499 https://www.wearcomet.com/products/aeon-v2-riptide) |
| Comet store at Pacific Mall, first floor, VT Road, Mansarovar, Jaipur | Comet store locator https://www.wearcomet.com/pages/store-locator-map | Pacific Mall Jaipur directory https://www.pacificmalls.in/jaipur/shopping (Comet under Footwear) |
| Gully Labs Number 001 Megh White ₹5,990 (in stock); white leather upper, grey suede accents, embroidery on side and back tab | https://gullylabs.com/products/gully-number-001-megh-white | https://www.superkicks.in/products/gully-labs-gully-number-001-megh-white |
| Thaely Tech Tabi Sulfur Yellow ₹3,500 (in stock); Thaely says the upper uses about 15-18 one-litre plastic bottles and it is machine washable (attributed on the card and in the caption; Superkicks' listing has the same text) | https://www.thaely.com/products/tech-tabi-sulfur-yellow | https://www.superkicks.in/products/thaely-tech-tabi-sulfur-yellow |
| Camo Tech Tabi ₹3,750 (caption only) | https://www.thaely.com/products/tech-tabi-digi-camo | https://www.superkicks.in/products/thaely-tech-tabi-digi-camo-black-grey |

| Broadway is a multi-brand store (its own words: "a curated store for fashion, streetwear, sneakers, Korean beauty, personal care, footwear and wellness", "200+ handpicked D2C brands") | https://shop.broadwaylive.in/pages/about-us | https://www.broadwaylive.in/ ("Broadway curates India's best fashion, sneakers, beauty & wellness brands") |

The Sourbomb colourway itself is not on Broadway, so slide 2 says "Other colours at Broadway, a multi-brand store".
Not used: Broadway's offer prices (MRP only, as the reviewer asked). Indian Retailer's 17 Nov headline "Comet Opens New Sneaker Store at
Pacific Mall in Jaipur" (I couldn't open the article, so the card doesn't say when the store opened).

## Image
- Comet's own product photo of the Aeon V2 Sourbomb: side view, plain light studio background. No people, no watermark.
  3684x4995 px; dl.py found 0 faces; viewed.
- Page: https://www.wearcomet.com/products/aeon-v2-sourbomb
  File: https://cdn.shopify.com/s/files/1/0738/5559/8899/files/1_1_ae659e86-2fdf-46e3-bf9c-50068d3dbd91.jpg?v=1794799272
- Licence: the brand's own product image, credited "Image: Comet". Owner Comet.
- Framing: pipeline.framing ok (faces 0) → _work/2026-11-17-hourly-1657/desks/idlyhype/frame_sourbomb/cover_source.png.
  post.json uses focal [0.5, 0.62] and zoom 1.2, at scale 0.35 (a downscale, not an upscale). The shoe sits at y ~260-660 and
  x ~60-1015, clear of the logo and of the headline block.
- Not used: the Sourbomb on-feet shot (lime background, no face). The shoes are too tall to sit above the headline at 4:5.

## Gates
- G1 171552-idlyhype-g1: all three HELD. C1 GTA 6 AF1 ceiling 9, C2 Comet Jaipur + prices ceiling 11, C3 Superkicks x RSF
  Caro ceiling 10. The reviewer pointed to a list of Indian labels with two-source ₹ prices.
- G1 171819-idlyhype-g1 (round 2): BUILD, ceiling 12. Conditions met: framing shown, the cover pair is named as Comet's
  on slide 2, the question everyone can answer is kept, Broadway's offer price is not used.
- G23 172140-idlyhype-g23: PASS (words and picture). Watch note: the cover gradient should not look like a flat grey slab.
- G4 172203-idlyhype-g4: PASS 12/14 (send 1, reply 1). Score file: _work/2026-11-17-hourly-1657/gates/scores/172203-idlyhype-g4.json.
  Nit: slides 3-4 show no picture of their pair (text slides by design).
- Main's fixes after 172203:
  - Slide 2, bullet 2: was "Broadway's Aeon V2 pairs start at MRP ₹4,499" (it repeated the slide's stat and didn't say what
    Broadway is). Now "Other colours at Broadway, a multi-brand store".
  - Caption: "At Broadway, a multi-brand store for Indian fashion and sneaker labels, other Aeon V2 colours start at an MRP of ₹4,499."
  - Slide 4, bullet 1: now "Thaely: upper uses about 15-18 plastic bottles".
  - Caption: now "Thaely says each pair's upper uses ...; Superkicks' listing carries the same description."
  - Main asked for "multi-brand sneaker store", but Broadway's own site describes a store across fashion, beauty and wellness, so
    the card says "multi-brand store".
- G4 172355-idlyhype-g4 (second pass): "FIX (copy only, then PASS 12/14)". Score file:
  _work/2026-11-17-hourly-1657/gates/scores/172355-idlyhype-g4.json (12/14: send 1, reply 1). Both fixes applied word for word:
  (1) Caption line 1 is now "Three Indian sneaker labels with their prices on each label's own store on Tuesday 17 November;
  two are also at Superkicks." It used to say each pair was checked at an Indian retailer, but the Sourbomb isn't on Broadway.
  (2) Slide 4, bullet 2: "made for heat, dust and rain" (Thaely's marketing claim) is dropped. It now reads "Machine washable,
  Thaely says".
  Re-rendered; all four slides opened at full size; checkcopy CLEAN; one "?"; the credit is the last line.


## Caption (caption.txt, final)
Three Indian sneaker labels with their prices on each label's own store on Tuesday 17 November; two are also at Superkicks.

Comet's Aeon V2 Sourbomb, the pair on the cover, is ₹4,499 on Comet's site. Comet says it pairs a neon suede overlay with white mesh and a green shooting star. At Broadway, a multi-brand store for Indian fashion and sneaker labels, other Aeon V2 colours start at an MRP of ₹4,499. Comet's store list and Pacific Mall's directory both show a Comet store at Pacific Mall, Jaipur.

Gully Labs' Number 001 in Megh White is ₹5,990 on Gully Labs' site and at Superkicks, with a white leather upper, grey suede accents and embroidery on the side and back tab.

Thaely's Tech Tabi in Sulfur Yellow is ₹3,500 at Thaely and at Superkicks; the camo versions are ₹3,750. Thaely says each pair's upper uses about 15 to 18 one-litre plastic bottles and that the shoe is machine washable; Superkicks' listing carries the same description.

Have you ever bought sneakers from an Indian label?

Sources: Comet, Broadway, Pacific Mall Jaipur, Gully Labs, Superkicks, Thaely

#IndianSneakers #Comet #GullyLabs #Thaely #idlyhype

Image: Comet
