"""cardkit.render: idly Instagram news cards (1080x1350), in two templates.

    render_cards(cards, out_dir)                    # 'classic' (default): one card per dict, below
    render_cards(posts, out_dir, template='hype')   # 'hype': full-bleed photo covers + detail slides,
                                                    #  one folder per post (see HYPE TEMPLATE below)

CLASSIC TEMPLATE
Layout (top to bottom)
    * Photo band, full-bleed (default 600px tall), with a soft fade into the card
      background. The ember tag pill sits on it at top-left; the photo credit sits
      in small text at its bottom-right.
    * Stat (Playfair italic 900, ember), stat label, short rule.
    * Headline (Inter 800) and 2-3 bullets (Inter 500, ember squares).
    * Footer: thin rule, branch logo + date at left, "idly.news" at right.

Text is auto-fitted: the stat shrinks until it is at most 912px wide; then, while
the text overflows, the stat, headline and bullets step down (stat first, so the
headline stays readable) to the sizes in FIT_STAT / FIT_NOSTAT. If it still does
not fit at the minimum sizes, the third bullet is dropped. Rough copy budget at
full size: headline <= 60 characters, each bullet <= 55 (one line).

Card dict keys
    acct          'idlynews' | 'idlytech' | 'idlyhype' | 'idlyautomotive' | 'idlynerd'
    tag           text for the ember pill, e.g. 'INDIA · AIR'
    stat          big number/word; '' for a no-stat card (bigger headline)
    stat_label    line under the stat
    headline      main line
    bullets       list of 2-3 strings
    photo         absolute path to a JPEG/PNG/WebP
    photo_credit  e.g. 'Photo: Jane Doe / Wikimedia Commons (CC BY-SA 4.0)'
    date          e.g. '9 Nov 2026'
    slug          output file stem, e.g. 'idlynews_01'
  optional
    photo_pos     CSS object-position for cover crops (default 'center')
    photo_fit     'cover' (default) or 'contain' (show a graphic whole, letterboxed)
    photo_bg      letterbox colour for 'contain' (default: sampled from the image corner)
    band_h        photo band height in px (default 600)
    fade_h        photo-to-background fade height in px (default: auto, shorter for dark
                  photos on cream cards)

Usage
    from cardkit import render_cards
    jpgs = render_cards(cards, '/path/out')        # writes <slug>.png and <slug>.jpg

    python3 render.py cards.json /path/out           # CLI; cards.json is a list of card dicts

Inside a running asyncio loop, use ``await render_cards_async(...)`` instead.

HYPE TEMPLATE (template='hype')
A Hypebeast-style post: a full-bleed photo cover, optionally followed by detail slides.
    * Cover: the photo cropped to 4:5 around a focal point; the white branch logo small at
      top-centre; the headline bottom-left in white Inter 800 (100px, stepping down to 72px
      until it fits in 3 lines), 48px from the left and 100px from the bottom, over a bottom
      gradient whose strength follows the photo's brightness; below it a quiet footer row
      (24px, white at 70%: the date left, "idly.news" right, 44px from the bottom, inside the
      headline column so Instagram's 3:4 grid crop leaves it whole); the photo credit in 15px
      white at 60%, running up the right edge. The footer is on by default; set
      cover_footer=False on a post to leave it off.
    * Detail slide: near-black (#0E0E10); stat in Playfair italic 900 (ember), stat label,
      2-3 bullets; a quiet one-line credit/source line (16px, white at 45%, left-aligned) just above
      the footer rule; footer with the branch logo, date and "idly.news".
    * Credits everywhere: a cover's vertical credit is required (photo_credit). Every other slide gets
      the credit/source line by default: the slide's 'credit_line', else the credit of the image it
      shows, else "Sources: <post 'sources'>". Custom slide kinds that have a footer rule
      (.foot .line or .foot2 .line) get it injected at render time. The report says per slide what it
      shows (credit_line) and whether it collides with anything (credit_collision, credit_inside).

Post dict keys
    acct, slug, date      as for classic cards (date is required: cover footer and detail slides)
    sources               the story's main sources, e.g. ['CNBC', 'Yahoo Finance'] -> "Sources: CNBC,
                          Yahoo Finance" on text slides (recommended whenever there are detail slides)
    cover_footer          optional, default True
    slides                list of slide dicts, in order. The first is normally the cover:
        {'type': 'cover', 'headline': ..., 'photo': path, 'photo_credit': ...,
         'focal': (x, y), 'zoom': 1.0}
            focal  point of the source photo to centre the crop on, as fractions (0-1) of its
                   width and height (default (0.5, 0.5)); the crop is clamped to the image
            zoom   >1 crops tighter (default 1: the largest 4:5 crop the photo allows)
        {'type': 'detail', 'stat': ..., 'stat_label': ..., 'bullets': [...], 'credit_line': optional}
  shorthand: a post with no 'slides' is a single cover built from its 'headline', 'photo',
  'photo_credit', 'focal' and 'zoom' keys.

Output: <out_dir>/<slug>/01.jpg, 02.jpg, ... (JPEG q92, RGB, 1080x1350) plus the PNG masters
as <png_dir or out_dir>/<slug>/01.png, ...  Returns the JPEG paths. A warning is printed when a
cover photo has to be upscaled (crop narrower than 1080px) or a headline does not fit; pass
report=[] to get one dict per slide (fitted sizes, photo scale, overflow) for build checks.

    python3 render.py posts.json OUT_DIR --hype      # CLI for the hype template
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import shutil
import sys
import tempfile

from PIL import Image, ImageFilter, ImageOps, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'fonts')
LOGOS = os.path.join(HERE, 'logos')

W, H = 1080, 1350
SIDE = 84                     # left/right margin
BAND_H = 600                  # default photo band height
EMBER = '#F0603A'
THEMES = {                    # idlynews is the dark hub; branches use cream
    'dark': dict(bg='#111214', bg_rgb='17,18,20', ink='#F1ECE2', logo='white'),
    'light': dict(bg='#F1ECE2', bg_rgb='241,236,226', ink='#16181C', logo='ink'),
}
LOGO_FILE = {'idlynews': 'idly', 'idlytech': 'tech', 'idlyhype': 'hype',
             'idlyautomotive': 'auto', 'idlynerd': 'nerd'}
DARK_ACCOUNTS = {'idlynews'}
JPEG_QUALITY = 92
# auto-fit sizes in px: start, 'mid' (first-pass floor), minimum
FIT_STAT = dict(stat=164, statMid=132, statMin=108, head=62, headMid=52, headMin=46,
                bullet=32, bulletMid=30, bulletMin=27)
FIT_NOSTAT = dict(stat=0, statMid=0, statMin=0, head=92, headMid=78, headMin=64,
                  bullet=32, bulletMid=30, bulletMin=27)


def _chrome() -> str | None:
    """System Chrome if present (override with CARDKIT_CHROME); else Playwright's bundled Chromium."""
    path = os.environ.get('CARDKIT_CHROME') or '/usr/bin/google-chrome'
    return path if os.path.exists(path) else None


def _esc(s: str) -> str:
    return html.escape(s or '', quote=False)


def _corner_colour(path: str) -> str:
    """Average colour of the image's top-left corner, used to letterbox 'contain' photos."""
    with Image.open(path) as im:
        px = im.convert('RGB').crop((0, 0, 24, 24)).resize((1, 1), Image.BOX).getpixel((0, 0))
    return '#%02x%02x%02x' % px


def _bottom_luminance(path: str) -> float:
    """Mean luminance (0-255) of the bottom fifth of the image (what meets the card background)."""
    with Image.open(path) as im:
        g = im.convert('L')
        strip = g.crop((0, int(g.height * 0.8), g.width, g.height)).resize((1, 1), Image.BOX)
        return float(strip.getpixel((0, 0)))


def _fade_height(c: dict, theme: str) -> int:
    """Height of the photo-to-background fade. A dark photo meeting a cream card gets a short, steep
    fade (a long one turns muddy grey); otherwise a long soft one. Override per card with 'fade_h'."""
    if c.get('fade_h'):
        return int(c['fade_h'])
    if c.get('photo_fit') == 'contain':
        return 56
    if theme == 'light' and _bottom_luminance(c['photo']) < 90:
        return 120
    return 210


CSS = """
@font-face{font-family:'Inter';src:url('file://%(fonts)s/inter.ttf');font-weight:100 900}
@font-face{font-family:'Playfair';src:url('file://%(fonts)s/playfair-italic.ttf');font-style:italic;font-weight:400 900}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(W)dpx;height:%(H)dpx;background:%(bg)s}
.card{position:relative;width:%(W)dpx;height:%(H)dpx;overflow:hidden;background:%(bg)s;color:%(ink)s;
      font-family:Inter;-webkit-font-smoothing:antialiased}

/* photo band */
.photo{position:absolute;left:0;top:0;width:%(W)dpx;height:%(band)dpx;overflow:hidden;background:%(photo_bg)s}
.photo img{display:block;width:100%%;height:100%%;object-fit:cover;object-position:%(pos)s}
.photo.contain img{object-fit:contain;padding:132px 64px 64px}
/* graphics shown whole: credit tucked into the bottom padding */
.photo.contain .credit{bottom:18px}
.fade{position:absolute;left:0;right:0;bottom:0;height:%(fade_h)dpx;
      background:linear-gradient(to bottom,rgba(%(bg_rgb)s,0) 0%%,rgba(%(bg_rgb)s,.5) 52%%,rgba(%(bg_rgb)s,.92) 86%%,%(bg)s 100%%)}
.tag{position:absolute;left:%(side)dpx;top:64px;background:%(ember)s;color:#fff;font:800 24px/1 Inter;
     letter-spacing:2.5px;padding:13px 18px 12px;border-radius:6px;box-shadow:0 2px 14px rgba(0,0,0,.22)}
.credit{position:absolute;right:22px;bottom:%(credit_b)dpx;max-width:760px;font:500 18px/1.2 Inter;letter-spacing:.1px;
        color:rgba(255,255,255,.78);background:rgba(0,0,0,.36);padding:5px 10px 6px;border-radius:4px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* text block between the photo and the footer */
.body{position:absolute;left:%(side)dpx;right:%(side)dpx;top:%(body_top)dpx;bottom:%(body_bottom)dpx;
      display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.stat{align-self:flex-start;font-family:Playfair;font-style:italic;font-weight:900;line-height:.94;
      letter-spacing:-4px;padding-right:26px;color:%(ember)s;white-space:nowrap}
.slabel{font:600 30px/1.22 Inter;opacity:.74;margin-top:18px;max-width:900px;text-wrap:balance}
.rule{height:3px;width:96px;background:currentColor;opacity:.85;margin:26px 0 24px;flex:none}
.head{font:800 62px/1.06 Inter;letter-spacing:-.027em;max-width:912px;text-wrap:balance}
.nostat .head{font-size:92px;line-height:1.0;letter-spacing:-.03em}
ul{list-style:none;margin-top:26px}
li{font:500 32px/1.27 Inter;padding-left:36px;position:relative;margin-bottom:12px;max-width:912px;text-wrap:pretty}
li:last-child{margin-bottom:0}
li:before{content:'';position:absolute;left:0;top:13px;width:14px;height:14px;background:%(ember)s;border-radius:2px}

/* footer */
.foot{position:absolute;left:%(side)dpx;right:%(side)dpx;bottom:50px}
.foot .line{height:2px;background:currentColor;opacity:.22;margin-bottom:22px}
.foot .row{display:flex;align-items:center}
.foot img{height:60px;width:auto;display:block}
.foot .date{font:600 24px/1 Inter;opacity:.6;margin-left:22px;padding-left:22px;border-left:2px solid currentColor;
            height:30px;display:flex;align-items:center}
.foot .site{margin-left:auto;font:800 27px/1 Inter;letter-spacing:-.5px}
"""

# JS auto-fit. Returns sizes used so the caller can log them.
FIT_JS = """
(opts) => {
  const body = document.querySelector('.body');
  const stat = document.getElementById('stat');
  const head = document.getElementById('head');
  const lis = () => Array.from(document.querySelectorAll('li'));
  const over = () => body.scrollHeight > body.clientHeight + 1;
  const setSizes = (s, h, b) => {
    if (stat) stat.style.fontSize = s + 'px';
    head.style.fontSize = h + 'px';
    lis().forEach(li => li.style.fontSize = b + 'px');
  };
  // 1) the stat may not be wider than 912px
  let s0 = opts.stat;
  if (stat) { stat.style.fontSize = s0 + 'px';
    while (stat.getBoundingClientRect().width > 912 && s0 > 80) { s0 -= 2; stat.style.fontSize = s0 + 'px'; } }
  let dropped = 0;
  for (;;) {
    let s = s0, h = opts.head, b = opts.bullet;
    setSizes(s, h, b);
    // 2) shrink headline, then bullets, then stat, a step at a time, until it fits
    // order keeps the hierarchy: stat down to statMid, headline to headMid, bullets to bulletMid,
    // then everything to its minimum
    while (over()) {
      if (stat && s > opts.statMid) s -= 4;
      else if (h > opts.headMid) h -= 2;
      else if (b > opts.bulletMid) b -= 1;
      else if (stat && s > opts.statMin) s -= 4;
      else if (h > opts.headMin) h -= 2;
      else if (b > opts.bulletMin) b -= 1;
      else break;
      setSizes(s, h, b);
    }
    // 3) still overflowing at minimum sizes: drop the last bullet (keep at least two)
    if (over() && lis().length > 2) { lis()[lis().length - 1].remove(); dropped++; continue; }
    return {stat: stat ? s : 0, head: h, bullet: b, dropped, overflow: over(),
            bodyH: body.clientHeight, contentH: body.scrollHeight};
  }
}
"""


def card_html(c: dict) -> str:
    """Build the HTML document for one card."""
    theme_name = 'dark' if c['acct'] in DARK_ACCOUNTS else 'light'
    theme = THEMES[theme_name]
    fade_h = _fade_height(c, theme_name)
    band = int(c.get('band_h') or BAND_H)
    fit = c.get('photo_fit', 'cover')
    photo_bg = c.get('photo_bg') or (_corner_colour(c['photo']) if fit == 'contain' else theme['bg'])
    logo = os.path.join(LOGOS, f"{LOGO_FILE[c['acct']]}_{theme['logo']}.png")
    css = CSS % dict(fonts=FONTS, W=W, H=H, side=SIDE, ember=EMBER, band=band,
                     body_top=band - 6, body_bottom=50 + 2 + 22 + 60 + 30,
                     pos=c.get('photo_pos', 'center'), photo_bg=photo_bg, fade_h=fade_h,
                     credit_b=max(18, int(fade_h * 0.5)), **theme)
    has_stat = bool((c.get('stat') or '').strip())
    stat = (f"<div class='stat' id='stat'>{_esc(c['stat'])}</div>"
            f"<div class='slabel'>{_esc(c.get('stat_label', ''))}</div><div class='rule'></div>") if has_stat else ''
    bullets = ''.join(f'<li>{_esc(b)}</li>' for b in c.get('bullets', []))
    credit = f"<div class='credit'>{_esc(c['photo_credit'])}</div>" if c.get('photo_credit') else ''
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='card {'' if has_stat else 'nostat'}'>
  <div class='photo {'contain' if fit == 'contain' else ''}'>
    <img src='file://{html.escape(c['photo'])}'><div class='fade'></div>{credit}
  </div>
  <div class='tag'>{_esc(c['tag'])}</div>
  <div class='body'>{stat}<div class='head' id='head'>{_esc(c['headline'])}</div><ul>{bullets}</ul></div>
  <div class='foot'><div class='line'></div><div class='row'>
    <img src='file://{logo}'><div class='date'>{_esc(c['date'])}</div><div class='site'>idly.news</div>
  </div></div>
</div></body></html>"""


REQUIRED = ('acct', 'tag', 'headline', 'bullets', 'photo', 'date', 'slug')


def _check(c: dict) -> None:
    missing = [k for k in REQUIRED if not c.get(k)]
    if missing:
        raise ValueError(f"card {c.get('slug', '?')}: missing {missing}")
    if c['acct'] not in LOGO_FILE:
        raise ValueError(f"card {c['slug']}: unknown acct {c['acct']!r}")
    if not os.path.isfile(c['photo']):
        raise FileNotFoundError(f"card {c['slug']}: photo not found: {c['photo']}")


# ------------------------------------------------------------------------------------------------
# hype template
# ------------------------------------------------------------------------------------------------
HYPE_BG = '#0E0E10'
HYPE_SIDE = 48                # cover headline: left margin
HYPE_BOTTOM = 100             # cover headline: bottom margin (the footer row sits below it)
HYPE_CREDIT_BOTTOM = 60       # cover: where the vertical photo credit starts
HYPE_FOOT_BOTTOM = 44         # cover footer row (date, idly.news): bottom margin
HYPE_HEAD_W = W - HYPE_SIDE - 72   # headline column; leaves room for the credit on the right edge
HYPE_FIT = dict(max=100, min=72, step=2, lines=3)
HYPE_LOGO_H = 60
DETAIL_SIDE = 72
DETAIL_FIT = dict(stat=280, statMin=150, statMaxW=W - 2 * DETAIL_SIDE, label=38, labelMin=30,
                  bullet=41, bulletMin=32)
UPSCALE_WARN = 1.0            # warn when a cover crop is narrower than 1080px


def _hype_crop(path: str, focal=(0.5, 0.5), zoom: float = 1.0) -> tuple[Image.Image, float]:
    """Crop a photo to 4:5 around `focal` (fractions of width/height) and resize to 1080x1350.
    Returns the image and the scale factor applied (>1 means the photo was upscaled)."""
    with Image.open(path) as src:
        im = ImageOps.exif_transpose(src).convert('RGB')
    aspect = W / H
    if im.width / im.height > aspect:
        ch = im.height
        cw = ch * aspect
    else:
        cw = im.width
        ch = cw / aspect
    zoom = max(1.0, float(zoom or 1.0))
    cw, ch = cw / zoom, ch / zoom
    fx, fy = focal or (0.5, 0.5)
    left = min(max(fx * im.width - cw / 2, 0), im.width - cw)
    top = min(max(fy * im.height - ch / 2, 0), im.height - ch)
    crop = im.crop((round(left), round(top), round(left + cw), round(top + ch)))
    scale = W / crop.width
    crop = crop.resize((W, H), Image.LANCZOS)
    if scale > 1.15:   # light sharpening after a real upscale
        crop = crop.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
    return crop, scale


def _lum(im: Image.Image, box: tuple) -> float:
    return ImageStat.Stat(im.convert('L').crop(box)).mean[0]


def _scrim_alpha(lum: float) -> float:
    """Darkest point of the bottom gradient: subtle on dark photos, stronger on bright ones."""
    return round(min(0.86, max(0.5, 0.42 + lum / 255 * 0.55)), 2)


HYPE_CSS = """
@font-face{font-family:'Inter';src:url('file://%(fonts)s/inter.ttf');font-weight:100 900}
@font-face{font-family:'Playfair';src:url('file://%(fonts)s/playfair-italic.ttf');font-style:italic;font-weight:400 900}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(W)dpx;height:%(H)dpx;background:%(bg)s}
.s{position:relative;width:%(W)dpx;height:%(H)dpx;overflow:hidden;background:%(bg)s;color:#fff;
   font-family:Inter;-webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}

/* cover */
.ph{position:absolute;left:0;top:0;width:%(W)dpx;height:%(H)dpx;display:block}
.topfade{position:absolute;left:0;right:0;top:0;height:280px;
         background:linear-gradient(to bottom,rgba(0,0,0,%(top_a)s) 0%%,rgba(0,0,0,0) 100%%)}
.scrim{position:absolute;left:0;right:0;bottom:0;height:640px;
       background:linear-gradient(to top,rgba(0,0,0,%(a0)s) 0%%,rgba(0,0,0,%(a1)s) 24%%,rgba(0,0,0,%(a2)s) 48%%,
                  rgba(0,0,0,%(a3)s) 70%%,rgba(0,0,0,%(a4)s) 87%%,rgba(0,0,0,0) 100%%)}
.logo{position:absolute;top:50px;left:50%%;transform:translateX(-50%%);height:%(logo_h)dpx;width:auto;display:block;
      filter:drop-shadow(0 0 1.5px rgba(0,0,0,%(logo_edge)s)) drop-shadow(0 1px 12px rgba(0,0,0,%(logo_glow)s))}
.credit{position:absolute;right:20px;bottom:%(credit_bottom)dpx;writing-mode:vertical-rl;transform:rotate(180deg);
        font:500 15px/1 Inter;letter-spacing:.2px;color:rgba(255,255,255,.6);white-space:nowrap;
        text-shadow:0 0 8px rgba(0,0,0,.35)}
.cfoot{position:absolute;left:%(side)dpx;width:%(head_w)dpx;bottom:%(foot_bottom)dpx;display:flex;
       justify-content:space-between;font:600 24px/1 Inter;letter-spacing:.1px;color:rgba(255,255,255,.7);
       text-shadow:0 1px 10px rgba(0,0,0,.3)}
.head{position:absolute;left:%(side)dpx;bottom:%(bottom)dpx;width:%(head_w)dpx;font-weight:800;font-size:100px;
      line-height:1.0;letter-spacing:-.034em;color:#fff;text-wrap:balance;
      text-shadow:0 2px 28px rgba(0,0,0,.22)}

/* detail */
.d .body{position:absolute;left:%(dside)dpx;right:%(dside)dpx;top:110px;bottom:190px;
         display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.d .stat{align-self:flex-start;font-family:Playfair;font-style:italic;font-weight:900;line-height:.95;
         letter-spacing:-.02em;padding-right:28px;color:%(ember)s;white-space:nowrap}
.d .slabel{font:600 38px/1.22 Inter;color:rgba(255,255,255,.78);margin-top:22px;max-width:936px;text-wrap:balance}
.d .rule{height:3px;width:96px;background:rgba(255,255,255,.85);margin:40px 0 36px;flex:none}
.d ul{list-style:none}
.d li{font:500 41px/1.26 Inter;padding-left:40px;position:relative;margin-bottom:22px;max-width:936px;text-wrap:pretty}
.d li:last-child{margin-bottom:0}
.d li:before{content:'';position:absolute;left:0;top:.45em;width:15px;height:15px;background:%(ember)s;border-radius:2px}
.d .foot{position:absolute;left:%(dside)dpx;right:%(dside)dpx;bottom:56px}
.d .foot .line{height:2px;background:rgba(255,255,255,.18);margin-bottom:24px}
.d .foot .row{display:flex;align-items:center}
.d .foot img{height:58px;width:auto;display:block}
.d .foot .date{font:600 24px/1 Inter;color:rgba(255,255,255,.6);margin-left:22px;padding-left:22px;
               border-left:2px solid rgba(255,255,255,.6);height:30px;display:flex;align-items:center}
.d .foot .site{margin-left:auto;font:800 27px/1 Inter;letter-spacing:-.5px}

/* quiet credit / source line, just above the footer rule (detail slides, and custom slides with a footer) */
.srcline{display:block;font:500 16px/1.25 Inter;letter-spacing:.2px;color:rgba(255,255,255,.45);text-align:left;
         white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0 0 10px;max-width:100%%}
"""

# cover: step the headline down until it fits in `lines` lines and no word overflows the column
HYPE_COVER_JS = """
(o) => {
  const h = document.getElementById('head');
  const lh = () => parseFloat(getComputedStyle(h).lineHeight);
  const lines = () => Math.round(h.getBoundingClientRect().height / lh());
  const wide = () => h.scrollWidth > h.clientWidth + 1;
  let s = o.max;
  h.style.fontSize = s + 'px';
  while ((lines() > o.lines || wide()) && s > o.min) { s -= o.step; h.style.fontSize = s + 'px'; }
  const r = h.getBoundingClientRect();
  // the gradient starts ~320px above the headline's first line
  const scrim = document.querySelector('.scrim');
  scrim.style.height = Math.min(1100, Math.max(560, (1350 - r.top) + 320)) + 'px';
  return {size: s, lines: lines(), overflow: lines() > o.lines || wide(), top: Math.round(r.top)};
}
"""

# detail: stat no wider than the column, then shrink stat/label/bullets until the body fits
HYPE_DETAIL_JS = """
(o) => {
  const body = document.querySelector('.body');
  const stat = document.getElementById('stat');
  const lab = document.querySelector('.slabel');
  const lis = Array.from(document.querySelectorAll('li'));
  const over = () => body.scrollHeight > body.clientHeight + 1;
  let s = o.stat, l = o.label, b = o.bullet;
  const set = () => { if (stat) stat.style.fontSize = s + 'px'; if (lab) lab.style.fontSize = l + 'px';
                      lis.forEach(li => li.style.fontSize = b + 'px'); };
  set();
  if (stat) while (stat.getBoundingClientRect().width > o.statMaxW && s > 80) { s -= 4; set(); }
  while (over()) {
    if (stat && s > o.statMin) s -= 6;
    else if (b > o.bulletMin) b -= 1;
    else if (l > o.labelMin) l -= 1;
    else break;
    set();
  }
  return {stat: stat ? s : 0, label: l, bullet: b, overflow: over()};
}
"""


# non-cover slides: add the quiet credit/source line above the footer rule when the slide's own HTML has none
# (custom slide kinds registered by other scripts), then check it collides with nothing and stays in margins
CREDIT_LINE_JS = """
(o) => {
  let s = document.querySelector('.srcline');
  let injected = false;
  if (!s && o.text) {
    const rule = document.querySelector('.foot .line, .foot2 .line');
    if (rule) {
      s = document.createElement('div'); s.className = 'srcline'; s.textContent = o.text;
      rule.parentNode.insertBefore(s, rule); injected = true;
    }
  }
  if (!s) return {credit_line: null, credit_injected: false, credit_collision: [], credit_inside: true};
  const r = s.getBoundingClientRect();
  const hits = [];
  const shown = (el) => {           // the part of el not clipped away by an overflow:hidden ancestor
    const b = el.getBoundingClientRect();
    let x0 = b.left, y0 = b.top, x1 = b.right, y1 = b.bottom;
    for (let a = el.parentElement; a; a = a.parentElement) {
      const st = getComputedStyle(a);
      if (st.overflow !== 'visible' || st.overflowX !== 'visible' || st.overflowY !== 'visible') {
        const c = a.getBoundingClientRect();
        x0 = Math.max(x0, c.left); y0 = Math.max(y0, c.top); x1 = Math.min(x1, c.right); y1 = Math.min(y1, c.bottom);
      }
    }
    return {left: x0, top: y0, right: x1, bottom: y1, width: x1 - x0, height: y1 - y0};
  };
  for (const el of document.querySelectorAll('body *')) {
    if (el === s || el.contains(s) || s.contains(el)) continue;
    if (el.classList.contains('ph') || el.classList.contains('bgph') || el.classList.contains('shade')) continue;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity) === 0) continue;
    const text = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
    const mark = el.tagName === 'IMG' || el.tagName === 'LI' || el.classList.contains('line') ||
                 el.classList.contains('rule');
    if (!text && !mark) continue;
    const e = shown(el);
    if (e.width <= 0 || e.height <= 0) continue;
    if (e.right > r.left && e.left < r.right && e.bottom > r.top && e.top < r.bottom)
      hits.push((el.className || el.tagName).toString());
  }
  return {credit_line: s.textContent, credit_injected: injected, credit_collision: hits,
          credit_truncated: s.scrollWidth > s.clientWidth + 1,
          credit_inside: r.left >= 40 && r.right <= 1040 && r.top >= 40 && r.bottom <= 1310,
          credit_rect: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]};
}
"""


def _hype_slides(post: dict) -> list[dict]:
    if post.get('slides'):
        return post['slides']
    return [dict(type='cover', headline=post.get('headline'), photo=post.get('photo'),
                 photo_credit=post.get('photo_credit'), focal=post.get('focal'), zoom=post.get('zoom'))]


def _hype_css(**kw) -> str:
    base = dict(fonts=FONTS, W=W, H=H, bg=HYPE_BG, ember=EMBER, side=HYPE_SIDE, bottom=HYPE_BOTTOM,
                credit_bottom=HYPE_CREDIT_BOTTOM, foot_bottom=HYPE_FOOT_BOTTOM,
                head_w=HYPE_HEAD_W, logo_h=HYPE_LOGO_H, dside=DETAIL_SIDE, top_a=0, logo_edge=0, logo_glow=.3,
                a0=0, a1=0, a2=0, a3=0, a4=0)
    base.update(kw)
    return HYPE_CSS % base


def hype_cover_html(post: dict, slide: dict, photo_file: str, bottom_lum: float, top_lum: float) -> str:
    """HTML for a cover slide. `photo_file` is the already-cropped 1080x1350 image."""
    a = _scrim_alpha(bottom_lum)
    stops = dict(a0=a, a1=round(a * .84, 3), a2=round(a * .55, 3), a3=round(a * .25, 3), a4=round(a * .07, 3))
    top_a = 0.40 if top_lum > 150 else (0.22 if top_lum > 90 else 0.08)
    # a bright patch behind the logo gets a crisper, darker shadow so the white lockup still reads
    logo_edge, logo_glow = (0.35, 0.55) if top_lum > 150 else ((0.2, 0.4) if top_lum > 110 else (0, 0.3))
    css = _hype_css(top_a=top_a, logo_edge=logo_edge, logo_glow=logo_glow, **stops)
    logo = os.path.join(LOGOS, f"{LOGO_FILE[post['acct']]}_white.png")
    credit = f"<div class='credit'>{_esc(slide['photo_credit'])}</div>" if slide.get('photo_credit') else ''
    # footer row (date left, idly.news right) is on by default; a post can opt out with cover_footer=False
    foot = (f"<div class='cfoot'><span>{_esc(post['date'])}</span><span>idly.news</span></div>"
            if post.get('cover_footer', True) else '')
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s c'>
  <img class='ph' src='file://{html.escape(photo_file)}'>
  <div class='topfade'></div><div class='scrim'></div>
  <img class='logo' src='file://{logo}'>
  {credit}
  <div class='head' id='head'>{_esc(slide['headline'])}</div>
  {foot}
</div></body></html>"""


def credit_line_text(post: dict, slide: dict) -> str:
    """The quiet one-line credit/source shown above the footer rule of a non-cover slide:
    the slide's own 'credit_line' if set; else, on a slide that shows an image, that image's credit;
    else the post's (or slide's) 'sources' as "Sources: A, B". '' when there is nothing to say."""
    if str(slide.get('credit_line') or '').strip():
        return str(slide['credit_line']).strip()
    photo = slide.get('photo')
    credit = slide.get('photo_credit') or (photo.get('credit') if isinstance(photo, dict) else None)
    if credit:
        return str(credit).strip()
    src = slide.get('sources') or post.get('sources')
    if isinstance(src, (list, tuple)):
        src = ', '.join(str(s).strip() for s in src if str(s).strip())
    src = str(src or '').strip()
    if not src:
        return ''
    return src if src.lower().startswith(('source', 'photo', 'image')) else f'Sources: {src}'


def hype_detail_html(post: dict, slide: dict) -> str:
    """HTML for a near-black detail slide (stat, label, bullets, credit/source line, footer)."""
    css = _hype_css()
    logo = os.path.join(LOGOS, f"{LOGO_FILE[post['acct']]}_white.png")
    stat = (f"<div class='stat' id='stat'>{_esc(slide['stat'])}</div>" if (slide.get('stat') or '').strip() else '')
    label = f"<div class='slabel'>{_esc(slide['stat_label'])}</div>" if slide.get('stat_label') else ''
    rule = "<div class='rule'></div>" if (stat or label) and slide.get('bullets') else ''
    bullets = ''.join(f'<li>{_esc(b)}</li>' for b in slide.get('bullets', []))
    src = credit_line_text(post, slide)
    srcline = f"<div class='srcline'>{_esc(src)}</div>" if src else ''
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s d'>
  <div class='body'>{stat}{label}{rule}<ul>{bullets}</ul></div>
  <div class='foot'>{srcline}<div class='line'></div><div class='row'>
    <img src='file://{logo}'><div class='date'>{_esc(post['date'])}</div><div class='site'>idly.news</div>
  </div></div>
</div></body></html>"""


def _check_hype(p: dict) -> None:
    for k in ('acct', 'slug'):
        if not p.get(k):
            raise ValueError(f"post {p.get('slug', '?')}: missing {k!r}")
    if p['acct'] not in LOGO_FILE:
        raise ValueError(f"post {p['slug']}: unknown acct {p['acct']!r}")
    if not p.get('date'):
        raise ValueError(f"post {p['slug']}: missing 'date' (shown in the cover footer and on detail slides)")
    slides = _hype_slides(p)
    if not 1 <= len(slides) <= 10:
        raise ValueError(f"post {p['slug']}: needs 1-10 slides")
    for i, s in enumerate(slides, 1):
        kind = s.get('type', 'cover')
        if kind == 'cover':
            if not s.get('headline'):
                raise ValueError(f"post {p['slug']} slide {i}: cover needs a headline")
            if not s.get('photo') or not os.path.isfile(s['photo']):
                raise FileNotFoundError(f"post {p['slug']} slide {i}: photo not found: {s.get('photo')}")
            if not str(s.get('photo_credit') or '').strip():
                raise ValueError(f"post {p['slug']} slide {i}: cover needs a photo_credit (the vertical credit "
                                 f"on the right edge is always filled)")
        elif kind == 'detail':
            if not (s.get('stat') or s.get('bullets')):
                raise ValueError(f"post {p['slug']} slide {i}: detail needs a stat or bullets")
        else:
            raise ValueError(f"post {p['slug']} slide {i}: unknown slide type {kind!r}")


async def _render_hype(posts: list[dict], out_dir: str, verbose: bool, png_dir: str | None,
                       report: list | None = None) -> list[str]:
    from playwright.async_api import async_playwright

    for p in posts:
        _check_hype(p)
    png_dir = png_dir or out_dir
    tmp = tempfile.mkdtemp(prefix='cardkit_hype_')
    written = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=_chrome(),
                                               args=['--no-sandbox', '--allow-file-access-from-files'])
            page = await browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
            for p in posts:
                jdir, pdir = os.path.join(out_dir, p['slug']), os.path.join(png_dir, p['slug'])
                os.makedirs(jdir, exist_ok=True)
                os.makedirs(pdir, exist_ok=True)
                for i, s in enumerate(_hype_slides(p), 1):
                    kind = s.get('type', 'cover')
                    src = os.path.join(tmp, f"{p['slug']}_{i:02d}.html")
                    if kind == 'cover':
                        crop, scale = _hype_crop(s['photo'], s.get('focal') or (0.5, 0.5), s.get('zoom') or 1.0)
                        photo_file = os.path.join(tmp, f"{p['slug']}_{i:02d}_photo.png")
                        crop.save(photo_file)
                        bottom = _lum(crop, (0, H - 520, W - 80, H))
                        top = _lum(crop, (330, 0, 750, 170))
                        doc = hype_cover_html(p, s, photo_file, bottom, top)
                    else:
                        doc = hype_detail_html(p, s)
                    with open(src, 'w', encoding='utf-8') as f:
                        f.write(doc)
                    await page.goto('file://' + src)
                    await page.evaluate('document.fonts.ready')
                    await page.wait_for_function("Array.from(document.images).every(i => i.complete)")
                    if kind == 'cover':
                        info = await page.evaluate(HYPE_COVER_JS, HYPE_FIT)
                        msg = (f"cover head {info['size']}px x{info['lines']} lines, photo scale {scale:.2f}"
                               f", scrim {_scrim_alpha(bottom)}")
                        if scale > UPSCALE_WARN:
                            msg += f"  UPSCALED {scale:.2f}x (crop {round(W / scale)}px wide)"
                        info['credit_line'] = s.get('photo_credit')     # the vertical credit on the right edge
                    else:
                        info = await page.evaluate(HYPE_DETAIL_JS, DETAIL_FIT)
                        msg = f"detail stat {info['stat']}px label {info['label']}px bullets {info['bullet']}px"
                        info.update(await page.evaluate(CREDIT_LINE_JS, {'text': credit_line_text(p, s)}))
                        if not info.get('credit_line'):
                            msg += '  no credit/source line (give the post "sources")'
                        if info.get('credit_collision') or not info.get('credit_inside', True):
                            msg += f"  CREDIT LINE COLLIDES: {info.get('credit_collision')}"
                    if info.get('overflow'):
                        msg += '  OVERFLOW!'
                    png = os.path.join(pdir, f'{i:02d}.png')
                    jpg = os.path.join(jdir, f'{i:02d}.jpg')
                    await page.screenshot(path=png, clip={'x': 0, 'y': 0, 'width': W, 'height': H})
                    with Image.open(png) as im:
                        im.convert('RGB').save(jpg, 'JPEG', quality=JPEG_QUALITY, subsampling=0, optimize=True)
                    written.append(jpg)
                    if report is not None:
                        report.append(dict(info, slug=p['slug'], slide=i, type=kind, jpg=jpg,
                                           scale=round(scale, 3) if kind == 'cover' else None))
                    if verbose:
                        print(f"[cardkit:hype] {p['slug']}/{i:02d}: {msg}")
            await browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return written


async def render_cards_async(cards: list[dict], out_dir: str, verbose: bool = True,
                             template: str = 'classic', png_dir: str | None = None,
                             report: list | None = None) -> list[str]:
    """Render cards (classic) or posts (template='hype'). Returns the JPEG paths (Instagram takes JPEG only).
    classic: <out_dir>/<slug>.png and .jpg.  hype: <out_dir>/<slug>/NN.jpg, PNGs in <png_dir or out_dir>/<slug>/.
    hype only: pass a list as `report` to get one dict per slide (fitted sizes, photo scale, overflow)."""
    if template == 'hype':
        return await _render_hype(cards, out_dir, verbose, png_dir, report)
    if template != 'classic':
        raise ValueError(f'unknown template {template!r}')
    from playwright.async_api import async_playwright

    for c in cards:
        _check(c)
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='cardkit_')
    written = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=_chrome(),
                                              args=['--no-sandbox', '--allow-file-access-from-files'])
            page = await browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
            for c in cards:
                src = os.path.join(tmp, f"{c['slug']}.html")
                with open(src, 'w', encoding='utf-8') as f:
                    f.write(card_html(c))
                await page.goto('file://' + src)
                await page.evaluate('document.fonts.ready')
                await page.wait_for_function("Array.from(document.images).every(i => i.complete)")
                nostat = not (c.get('stat') or '').strip()
                info = await page.evaluate(FIT_JS, FIT_NOSTAT if nostat else FIT_STAT)
                png = os.path.join(out_dir, f"{c['slug']}.png")
                jpg = os.path.join(out_dir, f"{c['slug']}.jpg")
                await page.screenshot(path=png, clip={'x': 0, 'y': 0, 'width': W, 'height': H})
                with Image.open(png) as im:
                    im.convert('RGB').save(jpg, 'JPEG', quality=JPEG_QUALITY, subsampling=0, optimize=True)
                written.append(jpg)
                if verbose:
                    flag = '  OVERFLOW!' if info['overflow'] else ''
                    drop = f"  dropped {info['dropped']} bullet(s)" if info['dropped'] else ''
                    print(f"[cardkit] {c['slug']}: stat {info['stat']}px head {info['head']}px "
                          f"bullets {info['bullet']}px{drop}{flag}")
            await browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return written


def render_cards(cards: list[dict], out_dir: str, verbose: bool = True,
                 template: str = 'classic', png_dir: str | None = None,
                 report: list | None = None) -> list[str]:
    """Synchronous wrapper around render_cards_async (do not call from inside a running event loop)."""
    return asyncio.run(render_cards_async(cards, out_dir, verbose, template, png_dir, report))


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != '--hype']
    if len(args) != 2:
        print('usage: python3 render.py cards.json OUT_DIR [--hype]', file=sys.stderr)
        return 2
    with open(args[0], encoding='utf-8') as f:
        cards = json.load(f)
    for path in render_cards(cards, args[1], template='hype' if '--hype' in argv else 'classic'):
        print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
