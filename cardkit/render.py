"""cardkit.render: idly Instagram news cards (1080x1350) with a photo band.

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
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import shutil
import sys
import tempfile

from PIL import Image

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


async def render_cards_async(cards: list[dict], out_dir: str, verbose: bool = True) -> list[str]:
    """Render cards to <out_dir>/<slug>.png and .jpg. Returns the JPEG paths (Instagram takes JPEG only)."""
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


def render_cards(cards: list[dict], out_dir: str, verbose: bool = True) -> list[str]:
    """Synchronous wrapper around render_cards_async (do not call from inside a running event loop)."""
    return asyncio.run(render_cards_async(cards, out_dir, verbose))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print('usage: python3 render.py cards.json OUT_DIR', file=sys.stderr)
        return 2
    with open(argv[1], encoding='utf-8') as f:
        cards = json.load(f)
    for path in render_cards(cards, argv[2]):
        print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
