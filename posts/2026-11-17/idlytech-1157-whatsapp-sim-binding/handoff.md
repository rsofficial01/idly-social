# Hand-off: @idlytech, hourly run 1157, Tue 17 Nov 2026

**Status: READY** (Gate 4 PASS, reply 121756-idlytech-g4)

## Story
From 1 January 2027, chat apps that sign users up with a phone number must work only while the registered SIM is in the phone and active. The rule, known as SIM binding, comes from the Department of Telecommunications' November 2025 directions. Apps have until 31 December 2026 to comply.

The apps named are WhatsApp, Telegram, Signal, Arattai, ShareChat, Josh and JioChat. Users who could be cut off:
- WhatsApp on Wi-Fi-only tablets or spare phones that have no SIM.
- Phones whose registered SIM has been removed, swapped or not recharged.

The fixed 6-hour WhatsApp Web logout was dropped; logouts will be risk-based.

Peg: MediaNama's 16-17 Nov reporting. Its 24-hour SIM-check claim rests on one anonymous source and is deliberately left out. The page has never run SIM binding.

- Format: news carousel (cover + 2 detail slides). story_id null and idly_article false, so the caption has a `Sources:` line and no idly.news line.
- Cover: "WhatsApp Must Be Tied to Your Phone's SIM From 1 January 2027"

## Gates
| Gate | Packet / reply id | Outcome |
|---|---|---|
| 1 | 121317-idlytech-g1 | **A (SIM binding): BUILD, ceiling 12.** The reviewer asked for the lead to be what stops working, not the old deadline, and for the 24-hour figure to stay out. **B (Lava ProBuds ₹969): HOLD, 10** (no official image, narrow). **C (FirstCry Q2): HOLD, 9** (no image, investor-only). |
| 23 | 121659-idlytech-g23 | FIX: the question-style cover overstated what slide 2 says ("could stop"). Changed to the reviewer's statement wording. Everything else PASS. |
| 4 | 121756-idlytech-g4 | **PASS**, 13. |

## Score
- Desk: hook 2, read 2, send 2, keep 2, reply 2, original 2, alone 2.
- Reviewer: hook 1, read 2, send 2, keep 2, reply 2, original 2, alone 2 = 13. Score file: `_work/2026-11-17-hourly-1157/gates/scores/idlytech.json`.
- **Post score (per-check min) = 13/14.** Hook is 1 because the cover has a date but no number, and "tied to your SIM" is abstract.

## Image
- Wikimedia Commons, `File:Dual_SIM_on_modern_smartphone.png`, by Paowee, CC BY-SA 4.0.
  - Page: https://commons.wikimedia.org/wiki/File:Dual_SIM_on_modern_smartphone.png
  - Fetched at 3840x3720 via Special:FilePath; the original is 4273x4140.
- Content: a Samsung Galaxy A02s with its tray ejected, holding two SIMs and a microSD card. The author edited out the ICCID and numbers.
- Checks: dl.py OK, faces 0. Viewed: no watermark and no people.
- Cover: `_work/2026-11-17-hourly-1157/idlytech/frame_sim/cover_source.png`, focal [0.39, 0.5], zoom 1.0. It is downscaled 0.36, so it stays sharp.
- Credit: "Photo: Paowee / Wikimedia Commons, CC BY-SA 4.0". It is on the cover and is the last line of the caption.

## Tag
None. The image owner is an individual Commons author, not a brand.

## For main to re-check
1. The 31 Dec deadline and 1 Jan start come from reports in late October (Inc42 citing TOI, Digit, Outlook Business), plus MediaNama on 17 Nov. There is no new DoT notice in the last 48 h. The card states only those reported dates.
2. Check that no WhatsApp or SIM-binding post went out on another idly page today.
3. Before publishing, check `queue/approved/` for any idlytech lane item. None was there at 12:18 IST.
4. Every fact has 2-4 URLs in `meta.json` `fact_sources`.

## Cover-swap search (main's request, 12:19-12:24 IST): NO-SWAP
I searched the WhatsApp images on Meta Newsroom (about.fb.com) and checked them through dl.py. whatsapp.com refuses scripted fetches (400), and its page images are signed links on scontent.whatsapp.net.
- **Quarantined (faces):** guest calling, group chats, web calling, events, username, and both Mar-2026 carousel images.
- **Burned-in marketing text:** account-security header ("1 billion passkeys"…), the three "New Feature Roundup" headers, Message Translations, passkey backup.
- **Wrong subject:** Meta AI incognito screens, Apple Watch, the spyware shield.
- **Closest: Strict Account Settings header (2026/01).** It is a 1920x1080 illustration of a hand holding a green phone with a lock and shield. dl.py OK, framing upscale 1.25. Test render: `_work/2026-11-17-hourly-1157/idlytech/test-wastrict/01.jpg`. In the 4:5 crop it doesn't work:
  - The WhatsApp logo (bottom-left) is cut off, so nothing identifies it as WhatsApp.
  - The password box and toggle bubble are clipped at both edges.
  - The phone and hand run into the headline block.
  - The scrim is 0.86.
  - It is a generic security illustration, no closer to the subject than the SIM-tray photo.
- If main swaps anyway: credit "Image: WhatsApp". The whatsapp.com footer links https://www.instagram.com/whatsapp/ (@whatsapp).
