# Handoff: @idlyhype, 20:57 run, Fri 20 Nov 2026

**Status:** READY (G4-r1 PASS 13, after main's HOLD on the v1 cover).
**Headline:** Nike Moon Shoe: $437,500 Original, ₹8,995 Retro
**Format:** news carousel, cover plus 2 detail slides:
- 01.jpg: the cover.
- 02.jpg: "₹8,995: Nike Moon Shoe OG Price in India".
- 03.jpg: "$437,500: Paid for a 1972 Nike Moon Shoe Pair".

**Scores:** desk 13/14 and reviewer 13/14, both with send at 1. Post score 13/14 (score.json, per-check min).
**story_id:** null. idly_article is false, so the caption ends with a Sources line and doesn't mention idly.news.
**Tag:** `nike`. Evidence: the Organization schema on https://www.nike.com/ has `"name":"Nike","sameAs":[... "https://www.instagram.com/nike/"]`. Checked 20 Nov ~21:15 IST; the reviewer accepted it at G2.
**Image credit:** "Image: Nike". It's on the cover and is the caption's last line.
**Peg:** the shoe is on sale in India now. It isn't a launch: the first colourway was listed on Superkicks on 28 Oct, and more were added 17-19 Nov. The copy never says "new", "launch" or "drop".

## Facts and sources (fetched 20 Nov, 21:00-21:15 IST)
| Fact | Sources |
|---|---|
| Moon Shoe OG Black/Sail (IX3952-001) costs ₹8,995 at Superkicks | superkicks.in/products/nike-moon-shoe-og-black-sail-black-safety-orange (product JSON: every size 8995.00) |
| The same IX3952-001 pair is ₹8,995 at VegNonVeg, MRP incl. taxes; the listing says it's imported by Nike India Pvt Ltd | vegnonveg.com/products/nike-moon-shoe-og-blacksail |
| Superkicks has three colourways, all ₹8,995: IX3952-001, IX3952-002 and IW0955-101 | Superkicks product pages and JSON |
| VegNonVeg lists 12 Moon Shoe colourways: 9 at ₹8,995 and 3 at ₹10,995 | vegnonveg.com/search?q=moon+shoe |
| Nike's US price is $105 | nike.com/t/moon-shoe-og-mens-shoes-QjBip6mn/IX3952-001 (page data: currentPrice 105) ; kith.com/.../nkix3952-400 ($105) |
| $437,500 at Sotheby's, 23 July 2019, a sneaker auction record at the time. About 12 pairs were made. Bowerman designed it for runners at the 1972 Olympic Trials. It's the only known unworn pair | sothebys.com/en/articles/new-world-auction-record-for-a-pair-of-sneakers-set-by-1972-nike-waffle-racing-flat ; aljazeera.com/economy/2019/7/23/a-pair-of-nike-sneakers-just-sold-for-437500 |
| The idea for the waffle sole came from his wife's waffle iron | Sotheby's ; Nike's product copy |

## Image (G4-r1: cover replaced after main's HOLD)
- **Source:** Nike's own US product page for the same pair (IX3952-001), gallery image 1 of 8, the rear view of the pair.
  - Page: https://www.nike.com/t/moon-shoe-og-mens-shoes-QjBip6mn/IX3952-001
  - Image: static.nike.com/a/images/f_jpg,q_100,…/20e75a29-4966-4a06-ac0e-07431697ba27/NIKE+MOON+SHOE+OG.png
- **Checks:** 2880x3600 at full native size, faces 0 (dl.py). No people and no watermark.
- **Shows:** the heel tabs, white Swooshes and waffle lugs.
- **Framing:**
  - The framing tool returned ok (upscale 0.38).
  - I used focal [0.5, 0.8] and zoom 1.55, with render scale 0.581 (no upscale).
  - The pair is whole at y 303-778 and x 44-1028. The logo is clear, and the headline starts at ~965.
- **Files:** `_work/2026-11-20-hourly-2057/desks/idlyhype/moon_1_hq.jpg` and `…/frame_moon1hq/cover_source.png`.
- **Why it changed:** main held the v1 cover (`moon_6.jpg`, the three-quarter pair at 1728x2160), which had two problems:
  - the top ~45% was plain grey, which counts as "a big empty band";
  - faint banding lines showed at y ~325 and ~465.

  All 8 of Nike's gallery images are studio cut-outs. The three-quarter and side views can't be enlarged without cutting the shoe, and the top-down view runs under the headline. The rear pair is the only whole-shoe view that fills the frame. The credit is unchanged: "Image: Nike".

## Gates
- **G1:** BUILD #2 (Moon Shoe, ceiling 13) with 6 conditions, all met. C1 (Nike x F1) and C3 (Comet Aeres) were NO BUILD.
- **G2+G3:** PASS. I took the optional wording change on slide 3, bullet 1.
- **G4:** PASS 13. Main then held the cover over the empty grey band and the banding.
- **G4-r1:** PASS 13 with the new rear-view Nike image. The reviewer re-wrote reviewer-score.json (send 1: only sneaker fans would forward it, and the shoe has been on sale since late October). mkscore gives desk 13, reviewer 13, post 13.

## Dropped candidates
1. **Nike named Formula 1's official apparel partner from 2027** (Complex's lead today; idly #3272, filed as sports). Reviewer's ceiling was 12 at the very best, and the story breaks the brief: there's no India price, date or effect.
   - The Las Vegas capsule (20 Nov) is sold only at the Caesars Palace Nike store and the F1 Hub at The Venetian.
   - Nike gives no ₹ price and no India date.
   - A good no-people image exists: Nike's newsroom 4:5 key visual of red-lit laces with the F1 x Swoosh lace-lock, 3840x4812, saved at `desks/idlyhype/f1-4x5-thumbnail.jpg`. Nike's 7 campaign photos all have faces.
2. **Comet Aeres NUBRA/ZIRO/SOHRA**, ₹5,499 each. Comet's copy says the pack is "inspired by the diverse landscapes of India". Dropped because:
   - Comet's own site is the only source;
   - Comet already led the 17 Nov Indian-labels list.

   Ceiling 11.
3. **Also checked and dropped:**
   - Golden Goose x D'YAVOL X: goldengoose.com/in still shows "0 products" and no ₹ prices at 21:00.
   - Nike Tuned Air: concept only, with no price and no India date.
   - Fear of God Trainer: summer 2027.
   - Jordan's on-court retro updates: 2027, with no prices.
   - AJ3 'Not Nice' (21 Nov, Superkicks) and the AJ3 'Santa', which is kids' sizes only.
   - Hypebeast's site returns 202/empty to our fetches.

## Leads
- **Nike x F1:** build it once Nike names an India date or ₹ price for its F1 fan collections. The no-people key visual above is ready.
- **Superkicks new this week:**
  - Converse x HAVEN Chuck 70 GORE-TEX, ₹10,999 (18 Nov);
  - Nike AF1 '07 "Plaid", ₹10,995 (20 Nov);
  - Nike AF1 Low Retro Camo, ₹11,995 (18 Nov);
  - adidas Tokyo Ballerina Fruition, ₹9,999.

  An AF1 list ("3+ new AF1s in India") is possible if each price gets a second source.
- **Golden Goose x D'YAVOL X, 24 Nov:** check goldengoose.com/in/en/ls/dyavol-en_in for ₹ prices.
