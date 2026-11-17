# Hand-off: @idlytech, hourly run 0757, Tue 17 Nov 2026

**Status: READY** (Gate 4 PASS, reply 082103-idlytech-g4)

## Story
Samsung raised Galaxy A prices in India from Mon 16 Nov. The Galaxy A57 5G 8GB+256GB went from ₹62,999 to ₹66,999 and the 12GB+256GB from ₹72,499 to ₹76,499. This is the A57's third rise since August. It launched in March at ₹56,999, so the base model is now ₹10,000 above its launch price. The other A models (A07, A17, A36, A37, A56) are up ₹2,000 per variant. The F17 and F70e are also up ₹2,000 (from 15 Nov).
- Format: news carousel (cover + 2 detail slides). story_id null, idly_article false, so the caption carries a `Sources:` line and does not mention idly.news.
- Cover: "Galaxy A57 Now Starts at ₹66,999, ₹10,000 Above Launch Price"

## Candidates and gates
| Gate | Reply id | Outcome |
|---|---|---|
| 1 | 081246-idlytech-g1 | A (Samsung A57 price hike) ceiling 14 on words, HOLD on the first image (1440px white render). B (DoT lifts 95 website blocks made on forged HC orders) ceiling 10. C (Bharat Semi $24M seed) ceiling 9, no image. |
| 23 | 081903-idlytech-g23 | PASS with 3 notes, all applied: focal moved to [0.42, 0.5]; "Samsung" added to both slide labels; A57 subject confirmed from Samsung page text. |
| 4 | 082103-idlytech-g4 | PASS. reviewer-score.json 13/14 (send 1). |

## Score
- Self: hook 2, read 2, send 1, keep 2, reply 2, original 2, alone 2 = **13**.
- Reviewer: the same, 13.
- **Post score (per-check min) = 13/14.**
- Why send is 1: the audience is mainly people shopping for a Galaxy A phone. Also, the account ran yesterday's Redmi price-hike post, so "phones cost more" is partly known news.

## Image
- Samsung Newsroom (global) downloadable press image `…Latest-Innovation_dl9_FF.jpg`, 10000x4371, no faces (dl.py), viewed. It shows the Galaxy A57 5G in Navy, Gray, Icyblue and Lilac on blue and cream paper. There is no text and no watermark.
- URL: https://img.global.news.samsung.com/global/wp-content/uploads/2026/04/14114522/Samsung-Mobile-Galaxy-A-series-Galaxy-A57-5G-Galaxy-A37-5G-Latest-Innovation_dl9_FF.jpg
- Page: https://news.samsung.com/global/user-guide-galaxy-a57-5g-and-galaxy-a37-5g-bringing-latest-innovation-within-reach
- How we know it is the A57: the page text lists the A57 colours as Navy, Gray, Icyblue and Lilac, and the combined colour photo is captioned "(From top to bottom) Galaxy A57 5G and Galaxy A37 5G". This file is that top set.
- Credit: "Image: Samsung" (owner: Samsung Electronics, press image).
- Cover file: `_work/2026-11-17-hourly-0757/idlytech/frame_dl9/cover_source.png`, focal [0.42, 0.5], zoom 1.0. It is downscaled 0.31, so it is sharp.

## Tag
- `samsungindia`: the samsung.com/in homepage footer links https://www.instagram.com/samsungindia (checked this run).

## For main to re-check
1. **Price source.** TelecomTalk says Samsung announced the new prices. Cashify says they come from retailer price lists and Samsung had not confirmed. Inc42 gives the same numbers without naming a source. The caption therefore says "TelecomTalk and Cashify report".
2. **Same topic as yesterday.** @idlytech posted the Redmi price hike on 16 Nov at 11:57. This post is a different brand plus a new running total since launch, and the reviewer did not object at Gate 1. Main should still check that it is OK to run two phone-price-hike posts in two days.
3. **checkcopy baseline warning.** checkcopy printed a Tamil Nadu baseline WARN (`rs2500-full-cost: single_source`). It matched on the ₹ figures; this is not a TN story. COPY OK.
4. **Lane check.** Check `queue/approved/` for any idlytech lane item before publishing.
5. **Facts and URLs.** Every fact has 2–3 source URLs in meta.json `fact_sources`.
