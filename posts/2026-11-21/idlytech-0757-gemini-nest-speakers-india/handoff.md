# @idlytech handoff: run 0757, Sat 21 Nov 2026

READY: posts/2026-11-21/idlytech-0757-gemini-nest-speakers-india/
Headline: "Gemini Takes Over Nest Speakers; India Early Access in December"
Score: 12/14 per-check min (desk 12, reviewer 12; hook 1, send 1, all else 2). score.json written by mkscore.py: PASS.
Tag: none (Commons photo). idly_article false, story_id null.

## Leads checked first
- Motorola Edge 70 Neo: India launch 24 Nov confirmed (Flipkart microsite, TelecomTalk, Gadgets 360); no price until then.
- Vivo X500 India prices: tipster leaks only (19 Nov); launch 26 Nov.
- Razorpay: "to file UDRHP by next week" (Inc42, 19 Nov, report). Not filed.
- Google/NPCI sideloading: Google's 20 Nov Android developer verification post says global rollout starts January 2027 and reaches all countries "over several months". No India date. NPCI/UPI apps' approach to Google (MediaNama, 19 Nov) is talks only.

## Candidates (G1)
1. Google Assistant leaves Google/Nest speakers and displays on 2 Aug 2027; Gemini for Home early access in India in December. G1 BUILD (ceiling 12-13). Built.
2. Dell XPS 16 Creator Edition in India, Rs 4,49,990 to Rs 9,49,990 (FoneArena, Gadgets 360). NO BUILD: no official Dell image found (dell.com/en-in product URLs redirect to the homepage; newsroom 403); send 1.
3. Xiaomi Pad 8 / Redmi Pad 2 price hikes of up to Rs 2,000 (Gadgets 360). NO BUILD: small rises, one outlet, only a promo graphic as image.

## Gates
- G1: BUILD #1 with conditions (India stake on the cover, "early access" wording, no-Hindi only as the language list, both dates and free-vs-Premium on slides, no implied India price).
- G23: FIX slide 3 (stat "0 Indian languages" -> "13 Languages on Gemini for Home's List, Not Hindi"). Applied exactly.
- G4: FIX slide 2 mirror bullet (December repeated) -> "Existing speakers get it, Google says; no new device". Applied.
- G4-r1: PASS 12.

## Key facts and URLs
- Assistant retires on speakers/smart displays 2 Aug 2027; Gemini for Home replaces it; Nest app closes 25 Jan 2027:
  https://support.google.com/googlehome/blog/478236207 ; https://9to5google.com/2026/11/20/nest-app-google-assistant/ ;
  https://www.theverge.com/tech/1038834/google-assistant-smart-speakers-nest-app-killed-shut-down
- India early access "coming in December"; free basics; Gemini Live needs Google Home Premium; can't switch back; 13-language list, no Hindi or other Indian language; device compatibility:
  https://support.google.com/googlehome/answer/16618650 ; https://techgenyz.com/gemini-for-home-india-december-2026/
- Existing devices keep working ("Every device supported today works with these updated experiences"): Google post 478236207 + answer 16618650.

## Image
Wikimedia Commons, "Google Nest Mini - 202001 - 01.jpg", Sikander Iqbal, own work, CC BY-SA 4.0:
https://commons.wikimedia.org/wiki/File:Google_Nest_Mini_-_202001_-_01.jpg (1920 px rendition, dl.py faces=0, viewed).
Credit on the cover and as the caption's last line: "Photo: Sikander Iqbal / Wikimedia Commons, CC BY-SA 4.0".

## For Rahul / main
- Posting at exactly 12/14; hook and send are both 1 on both sides. It's a clean, sourced, India-dated service post, not a big hook.
- TechGenyz is the second outlet for the India December date and the no-Hindi point. Google's own Help Centre page is the primary source. The bigger outlets (9to5Google, The Verge) covered the global dates but not India's.
- checkcopy's TN baseline warning ("speaker" matching TN Assembly Speaker items) is a keyword false positive.
- Image safety note: Google Store's Nest Hub product image passed dl.py (faces=0) but shows a child's partly visible face on the screen. I deleted it unused. The face detector misses faces in on-screen photos.
- Outside this post: Lava's homepage (lavamobiles.com) has a third-party script tag (`//raw.githack.com/gogok4nxgo/...`) injected into its CMS content field ("content1" in __NEXT_DATA__). It looks like a site compromise. Not verified, not a story yet, and I didn't load it.
- Check queue/approved/ for an @idlytech lane item before publishing (none seen at 08:24 IST).
