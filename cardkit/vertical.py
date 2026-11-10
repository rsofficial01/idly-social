"""cardkit.vertical: idly's 9:16 formats (1080x1920), built from the same post dict as the hype template.

    render_story(post, out_jpg, report=[])        # an Instagram Story card: one JPEG
    python3 -m cardkit.vertical story POST.json OUT.jpg     # exit 1 if the layout has problems

    (cardkit.reel turns the same pages into a reel: reel.mp4 + reel_cover.jpg.)

POST.json is one hype post dict (see cardkit.render): acct, slug, date, sources, slides (the first is the cover:
headline, photo, photo_credit, focal, zoom; then 'detail' slides). Relative photo paths are taken from the current
directory (the repo root), else from the JSON file's folder.

Layout (Rahul's rules, 10 Nov 2026), shared by the story card and every frame of the reel:
  * the photo fills the width at the top: the cover's own 4:5 full-bleed crop (same photo, focal and zoom), or
    taller when the source allows (up to 1080x1440). A cover slide may carry a 'vertical' dict (photo, focal, zoom,
    photo_h) planned by pipeline.framing for this frame (the lane does that for every photo with people in it);
  * it fades through a smooth gradient into the dark brand background (#0A0A0A) where the text sits;
  * the logo top-centre over the photo (y 240-300), as on covers; the vertical photo credit up the right edge;
  * text: a small kicker with the account handle, the Title Case headline (Inter 800, left-aligned), and the footer
    (date left, idly.news right). Every text line starts at x=64;
  * nothing in Instagram's UI zones: text stays between y 220 and y 1600 (the top ~220 px and the bottom ~320 px
    are Instagram's), and no text is smaller than 30 px.
Never a boxed/letterboxed photo, never a blurred or darkened copy of the photo as a fill.

Every page is checked in the browser the way the hype covers are: the headline fits (<= 3 lines), and the report
lists collisions between text elements, anything in the UI zones or outside the margins, uneven left edges, the
smallest font size and truncated lines. vertical_problems(report) turns that into a list of problems.
"""
from __future__ import annotations

import asyncio
import html
import json
import math
import os
import shutil
import sys
import tempfile
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardkit.render import (EMBER, HYPE_DETAIL_JS, JPEG_QUALITY, LOGO_FILE, LOGOS, _check_hype, _chrome, _esc,  # noqa: E402
                            _hype_css, _hype_slides, _keep_compounds, _lum, credit_line_text)

VW, VH = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 220, 1600       # Instagram's UI covers the top ~220 px and the bottom ~320 px
MIN_TEXT_PX = 30
VBG, VBG_RGB = '#0A0A0A', (10, 10, 10)
VSIDE = 64                               # every text line starts here
LOGO_TOP, LOGO_H = 240, 60
PHOTO_ASPECT = 1080 / 1350               # the cover's 4:5 crop
PHOTO_H_MIN, PHOTO_H_MAX = 1350, 1440
MAX_UPSCALE = 2.0
SHARPEN_ABOVE = 1.15
FOOT_PX, KICK_PX, CREDIT_PX, SRC_PX = 30, 30, 30, 30
HEAD_GAP = 48                            # headline bottom -> footer top
HEAD_W = VW - VSIDE - 96                 # leaves the right edge to the vertical credit
VHEAD_FIT = dict(max=92, min=64, step=2, lines=3)
CREDIT_Y = 1000                          # the credit's lower end (it reads upwards), above Reels' button column
CREDIT_RIGHT = 32
FADE_LEN, SOLID_BELOW_TEXT_TOP = 620, 150
BODY_TOP, BODY_BOTTOM = 380, 1460        # detail slides: the text block is centred in this band
SRC_BOTTOM = 1546                        # detail slides: the Sources line ends here, above the footer
VDETAIL_FIT = dict(stat=300, statMin=140, statMaxW=VW - 2 * VSIDE, label=60, labelMin=40, bullet=48, bulletMin=34)
END_LOGO_H = 150
PUSH_ORIGIN = (540, 630)                 # the reel's push-in centre: the middle of pipeline.framing.VERTICAL's
                                         # face band (y 380-880), so planned faces stay clear of logo and edges


# ---- geometry -----------------------------------------------------------------------------------------------

def vertical_crop_box(w: int, h: int, focal=(0.5, 0.5), zoom: float = 1.0,
                      photo_h: int | None = None) -> tuple[tuple[int, int, int, int], int]:
    """((left, top, right, bottom), photo window height) for a w x h source. The crop is as wide as the hype
    cover's 4:5 crop at this zoom and as tall as the source allows (PHOTO_H_MIN..PHOTO_H_MAX output px);
    pipeline.framing.frame_crop(..., VERTICAL) computes exactly the same box."""
    cw0 = h * PHOTO_ASPECT if w / h > PHOTO_ASPECT else float(w)
    zoom = max(1.0, float(zoom or 1.0))
    cw = cw0 / zoom
    if photo_h is None:
        photo_h = int(min(PHOTO_H_MAX, max(PHOTO_H_MIN, math.floor(VW * h / cw + 1e-9))))
    photo_h = int(photo_h)
    ch = min(float(h), cw * photo_h / VW)
    fx, fy = focal or (0.5, 0.5)
    left = min(max(fx * w - cw / 2, 0), w - cw)
    top = min(max(fy * h - ch / 2, 0), h - ch)
    return (round(left), round(top), round(left + cw), round(top + ch)), photo_h


def _resolve_photo(path: str, base_dir: str | None = None) -> str:
    if os.path.isabs(path) or os.path.exists(path) or not base_dir:
        return path
    alt = os.path.join(base_dir, path)
    return alt if os.path.exists(alt) else path


def vertical_source(slide: dict) -> tuple[str, tuple[float, float], float, int | None]:
    """(photo, focal, zoom, photo_h) for the vertical photo window: the cover slide's own photo, focal and zoom,
    unless the slide carries a 'vertical' plan (pipeline.framing at the vertical frame's limits)."""
    v = slide.get('vertical') or {}
    if v.get('photo'):
        return v['photo'], tuple(v.get('focal') or (0.5, 0.5)), float(v.get('zoom') or 1.0), v.get('photo_h')
    return (slide['photo'], tuple(v.get('focal') or slide.get('focal') or (0.5, 0.5)),
            float(v.get('zoom') or slide.get('zoom') or 1.0), v.get('photo_h'))


class PhotoWindow:
    """The photo at the top of the frame, at any push-in zoom (1.0 = the planned crop). Sub-pixel accurate (Pillow
    resize with a float box), so a slow push-in doesn't jitter."""

    def __init__(self, path: str, focal=(0.5, 0.5), zoom: float = 1.0, photo_h: int | None = None):
        with Image.open(path) as src:
            im = ImageOps.exif_transpose(src).convert('RGB')
        box, self.h = vertical_crop_box(im.width, im.height, focal, zoom, photo_h)
        self.box = box
        cw = box[2] - box[0]
        self.scale = VW / cw                          # output px per source px (> 1: enlarged)
        base = im.crop(box)
        if base.width > 2 * VW:                       # keep per-frame resizes cheap; 2x is plenty for a 6% zoom
            base = base.resize((2 * VW, round(2 * VW * base.height / base.width)), Image.LANCZOS)
        self.base = base

    def at(self, z: float = 1.0, origin=PUSH_ORIGIN) -> Image.Image:
        ox, oy = origin[0], min(origin[1], self.h / 2)
        bx, by = self.base.width / VW, self.base.height / self.h
        box = ((ox - ox / z) * bx, (oy - oy / z) * by, (ox + (VW - ox) / z) * bx, (oy + (self.h - oy) / z) * by)
        out = self.base.resize((VW, self.h), Image.LANCZOS, box=box)
        if self.scale * z > SHARPEN_ABOVE:
            out = out.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
        return out


# ---- HTML ------------------------------------------------------------------------------------------------------

VERTICAL_CSS = """
.bgfill{position:absolute;left:0;top:0;width:%(W)dpx;height:%(H)dpx;background:%(vbg)s}
.v .ph{height:%(photo_h)dpx}
.v .topfade{height:470px}
.vfade{position:absolute;left:0;right:0;top:0;height:1px;
       background:linear-gradient(to bottom,rgba(%(vbg_rgb)s,0) 0%%,rgba(%(vbg_rgb)s,.06) 16%%,rgba(%(vbg_rgb)s,.2) 33%%,
       rgba(%(vbg_rgb)s,.42) 50%%,rgba(%(vbg_rgb)s,.67) 67%%,rgba(%(vbg_rgb)s,.87) 83%%,rgba(%(vbg_rgb)s,.97) 94%%,
       rgb(%(vbg_rgb)s) 100%%)}
.vsolid{position:absolute;left:0;right:0;top:%(H)dpx;bottom:0;background:%(vbg)s}
.v .logo{top:%(logo_top)dpx}
.v .credit{right:%(credit_right)dpx;bottom:%(credit_bottom)dpx;font:500 %(credit_px)dpx/1 Inter;letter-spacing:.1px;
           color:rgba(255,255,255,.8);text-shadow:0 0 2px rgba(0,0,0,.55),0 0 12px rgba(0,0,0,.45)}
.v .cfoot{left:%(side)dpx;width:%(foot_w)dpx;bottom:%(foot_bottom)dpx;font:600 %(foot_px)dpx/1 Inter;
          color:rgba(255,255,255,.72)}
.txt{position:absolute;left:%(side)dpx;bottom:%(head_bottom)dpx;width:%(head_w)dpx}
.kick{font:700 %(kick_px)dpx/1 Inter;letter-spacing:.01em;color:%(ember)s;margin-bottom:28px}
.v .head{position:static;width:%(head_w)dpx;font-size:92px;line-height:1.02;text-shadow:none}
.v.d .body{top:%(body_top)dpx;bottom:%(body_bottom)dpx}
.v.d .slabel,.v.d li{max-width:%(text_w)dpx;text-wrap:wrap}
.v.d .logo,.v.e .logo{filter:none}
.srcwrap{position:absolute;left:%(side)dpx;right:%(side)dpx;bottom:%(src_bottom)dpx}
.v .srcline{font:500 %(src_px)dpx/1.2 Inter;color:rgba(255,255,255,.52);margin:0}
.endblk{position:absolute;left:%(side)dpx;right:%(side)dpx;top:%(safe_top)dpx;bottom:%(safe_bottom)dpx;display:flex;
        flex-direction:column;justify-content:center;align-items:flex-start}
.endlogo{height:%(end_logo_h)dpx;width:auto;display:block;margin-left:%(end_logo_ml)spx}
.endsite{font:800 132px/1 Inter;letter-spacing:-.045em;color:#fff;margin-top:64px}
.endhandle{font:600 50px/1 Inter;letter-spacing:-.01em;color:%(ember)s;margin-top:30px}
.layer-overlay .bgfill,.layer-overlay .ph,.layer-overlay .txt{visibility:hidden}
.layer-text .s > *:not(.txt){visibility:hidden}
"""


def _logo_path(acct: str) -> str:
    return os.path.join(LOGOS, f"{LOGO_FILE[acct]}_white.png")


def _logo_pad(acct: str, height: int) -> float:
    """The logo PNG's transparent left margin at `height`, so its ink lines up with the text column."""
    with Image.open(_logo_path(acct)) as im:
        bbox = im.split()[-1].getbbox() or (0, 0, 0, 0)
        return round(bbox[0] / im.height * height, 1)


def _vcss(acct: str, **kw) -> str:
    base = dict(W=VW, H=VH, bg='transparent', side=VSIDE, dside=VSIDE, logo_h=LOGO_H, ember=EMBER)
    css = _hype_css(**{**base, **{k: v for k, v in kw.items() if k in ('top_a', 'logo_edge', 'logo_glow')}})
    vals = dict(W=VW, H=VH, vbg=VBG, vbg_rgb=','.join(map(str, VBG_RGB)), photo_h=PHOTO_H_MIN, logo_top=LOGO_TOP,
                credit_right=CREDIT_RIGHT, credit_bottom=VH - CREDIT_Y, credit_px=CREDIT_PX, side=VSIDE,
                foot_w=VW - 2 * VSIDE, foot_bottom=VH - SAFE_BOTTOM, foot_px=FOOT_PX,
                head_bottom=VH - SAFE_BOTTOM + FOOT_PX + HEAD_GAP, head_w=HEAD_W, kick_px=KICK_PX, ember=EMBER,
                body_top=BODY_TOP, body_bottom=VH - BODY_BOTTOM, text_w=VW - 2 * VSIDE, src_bottom=VH - SRC_BOTTOM,
                src_px=SRC_PX, safe_top=SAFE_TOP + 80, safe_bottom=VH - SAFE_BOTTOM + 80, end_logo_h=END_LOGO_H,
                end_logo_ml=-_logo_pad(acct, END_LOGO_H))
    vals.update({k: v for k, v in kw.items() if k in vals})
    return css + VERTICAL_CSS % vals


def _foot(post: dict) -> str:
    return (f"<div class='cfoot'><span data-chk='date' data-edge='1'>{_esc(post['date'])}</span>"
            f"<span data-chk='site'>idly.news</span></div>")


def vcover_html(post: dict, slide: dict, photo_file: str, photo_h: int, top_lum: float) -> str:
    """The story card / reel cover. `photo_file` is the already-cropped 1080 x photo_h window."""
    top_a = 0.42 if top_lum > 150 else (0.26 if top_lum > 90 else 0.12)
    logo_edge, logo_glow = (0.35, 0.55) if top_lum > 150 else ((0.2, 0.4) if top_lum > 110 else (0, 0.3))
    css = _vcss(post['acct'], photo_h=photo_h, top_a=top_a, logo_edge=logo_edge, logo_glow=logo_glow)
    credit = (f"<div class='credit' data-chk='credit'>{_esc(slide['photo_credit'])}</div>"
              if slide.get('photo_credit') else '')
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s v c'>
  <div class='bgfill'></div>
  <img class='ph' src='file://{html.escape(photo_file)}'>
  <div class='topfade'></div><div class='vfade'></div><div class='vsolid'></div>
  <img class='logo' data-chk='logo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
  {credit}
  <div class='txt'><div class='kick' data-chk='kicker' data-edge='1'>@{_esc(post['acct'])}</div><div class='head' id='head' data-chk='headline' data-edge='1'>{_esc(slide['headline'])}</div></div>
  {_foot(post)}
</div></body></html>"""


def vdetail_html(post: dict, slide: dict) -> str:
    """A detail slide re-laid out for 9:16: stat, label, bullets and the Sources line on the dark background."""
    css = _vcss(post['acct'])
    stat = (f"<div class='stat' id='stat' data-chk='stat'>{_esc(slide['stat'])}</div>"
            if (slide.get('stat') or '').strip() else '')
    label = (f"<div class='slabel' data-chk='label' data-edge='1'>{_keep_compounds(slide['stat_label'])}</div>"
             if slide.get('stat_label') else '')
    rule = "<div class='rule'></div>" if (stat or label) and slide.get('bullets') else ''
    bullets = ''.join(f"<li data-chk='bullet{i}' data-edge='1'>{_keep_compounds(b)}</li>"
                      for i, b in enumerate(slide.get('bullets') or [], 1))
    src = credit_line_text(post, slide)
    srcline = (f"<div class='srcwrap'><div class='srcline' data-chk='sources' data-edge='1'>{_esc(src)}</div></div>"
               if src else '')
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s v d'>
  <div class='bgfill'></div>
  <img class='logo' data-chk='logo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
  <div class='body'>{stat}{label}{rule}<ul>{bullets}</ul></div>
  {srcline}
  {_foot(post)}
</div></body></html>"""


def vend_html(post: dict) -> str:
    """The end card: the account's logo, idly.news and the handle, left-aligned like everything else."""
    css = _vcss(post['acct'])
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s v e'>
  <div class='bgfill'></div>
  <div class='endblk'>
    <img class='endlogo' data-chk='endlogo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
    <div class='endsite' data-chk='site' data-edge='1'>idly.news</div>
    <div class='endhandle' data-chk='handle' data-edge='1'>@{_esc(post['acct'])}</div>
  </div>
</div></body></html>"""


# cover: fit the headline (<= 3 lines, no word wider than the column), then fade the photo out so it is solid
# background a little below the top of the text block, and keep the credit's upper end out of the top UI zone
VCOVER_JS = """
(o) => {
  const h = document.getElementById('head');
  const lh = () => parseFloat(getComputedStyle(h).lineHeight);
  const lines = () => Math.round(h.getBoundingClientRect().height / lh());
  const wide = () => h.scrollWidth > h.clientWidth + 1;
  let s = o.max; h.style.fontSize = s + 'px';
  while ((lines() > o.lines || wide()) && s > o.min) { s -= o.step; h.style.fontSize = s + 'px'; }
  const top = Math.round(document.querySelector('.txt').getBoundingClientRect().top);
  const solid = Math.min(o.photoH, top + o.solidBelow);
  const start = Math.max(0, solid - o.fadeLen);
  const f = document.querySelector('.vfade');
  f.style.top = start + 'px'; f.style.height = Math.max(1, solid - start) + 'px';
  document.querySelector('.vsolid').style.top = solid + 'px';
  const c = document.querySelector('.credit');
  let cb = o.creditY, clen = 0;
  if (c) {
    clen = Math.ceil(c.getBoundingClientRect().height);
    if (clen > cb - (o.safeTop + o.pad)) cb = Math.min(o.safeBottom, o.safeTop + o.pad + clen);
    c.style.bottom = (o.H - cb) + 'px';
  }
  return {size: s, lines: lines(), overflow: lines() > o.lines || wide(), text_top: top, fade_start: start,
          solid_from: solid, credit_bottom: cb, credit_len: clen};
}
"""

# every page: what collides, what sits in Instagram's UI zones or outside the margins, the left edges, the
# smallest font, and lines cut short with an ellipsis
VCHECK_JS = """
(o) => {
  const vis = el => { const st = getComputedStyle(el);
    return st.display !== 'none' && st.visibility !== 'hidden' && parseFloat(st.opacity) > 0; };
  const els = Array.from(document.querySelectorAll('[data-chk]')).filter(vis);
  const items = els.map(el => { const r = el.getBoundingClientRect();
    return {el, name: el.dataset.chk, mark: el.dataset.kind === 'mark', x0: r.left, y0: r.top, x1: r.right, y1: r.bottom}; })
    .filter(i => i.x1 - i.x0 > 0 && i.y1 - i.y0 > 0);
  const collisions = [];
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i], b = items[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    if (a.x1 > b.x0 + 0.5 && a.x0 < b.x1 - 0.5 && a.y1 > b.y0 + 0.5 && a.y0 < b.y1 - 0.5) collisions.push([a.name, b.name]);
  }
  const r = v => Math.round(v);
  const ui_zone = items.filter(i => i.y0 < o.safeTop - 0.5 || i.y1 > o.safeBottom + 0.5)
                       .map(i => `${i.name} y ${r(i.y0)}-${r(i.y1)}`);
  const outside = items.filter(i => i.x0 < o.margin - 0.5 || i.x1 > o.W - o.margin + 0.5)
                       .map(i => `${i.name} x ${r(i.x0)}-${r(i.x1)}`);
  const left_edges = {};
  els.filter(el => el.dataset.edge).forEach(el => { left_edges[el.dataset.chk] = r(el.getBoundingClientRect().left); });
  const texts = items.filter(i => !i.mark);
  const min_font_px = texts.length ? Math.min(...texts.map(i => parseFloat(getComputedStyle(i.el).fontSize))) : null;
  const truncated = items.filter(i => getComputedStyle(i.el).textOverflow === 'ellipsis' &&
                                      i.el.scrollWidth > i.el.clientWidth + 1).map(i => i.name);
  const boxes = {}; items.forEach(i => { boxes[i.name] = [r(i.x0), r(i.y0), r(i.x1), r(i.y1)]; });
  return {collisions, ui_zone, outside, left_edges, min_font_px, truncated, boxes};
}
"""

# detail slides: balance wrapped labels and bullets ourselves (the narrowest width that keeps the same number of
# lines), because the browser's text-wrap can't balance around the no-break spans that keep "ex-showroom" whole
BALANCE_JS = """
(sel) => {
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const lh = parseFloat(getComputedStyle(el).lineHeight);
    const lines = () => Math.round(el.getBoundingClientRect().height / lh);
    const n = lines();
    if (n < 2) continue;
    let lo = 120, hi = Math.ceil(el.getBoundingClientRect().width);
    while (hi - lo > 2) {
      const mid = Math.floor((lo + hi) / 2);
      el.style.maxWidth = mid + 'px';
      if (lines() > n || el.scrollWidth > el.clientWidth + 1) lo = mid; else hi = mid;
    }
    el.style.maxWidth = hi + 'px';
    out.push(n);
  }
  return out;
}
"""

CHECK_OPTS = dict(safeTop=SAFE_TOP, safeBottom=SAFE_BOTTOM, W=VW, margin=24)


def vertical_problems(rows: list[dict], min_font: int = MIN_TEXT_PX) -> list[str]:
    """The layout problems in a render report (one row per page): empty when the card is fine."""
    out = []
    for row in rows:
        if row.get('type') == 'reel':
            out += [f"reel: {p}" for p in row.get('problems') or []]
            continue
        who = row.get('page') or row.get('type')
        if row.get('overflow'):
            out.append(f"{who}: text does not fit")
        for a, b in row.get('collisions') or []:
            out.append(f"{who}: {a} collides with {b}")
        for z in row.get('ui_zone') or []:
            out.append(f"{who}: {z} is inside Instagram's UI zone (text must stay in y {SAFE_TOP}-{SAFE_BOTTOM})")
        for z in row.get('outside') or []:
            out.append(f"{who}: {z} is outside the margins")
        for t in row.get('truncated') or []:
            out.append(f"{who}: {t} is cut short")
        edges = {k: v for k, v in (row.get('left_edges') or {}).items()}
        if edges and max(edges.values()) - min(edges.values()) > 2:
            out.append(f"{who}: text lines don't share one left edge {edges}")
        if row.get('min_font_px') is not None and row['min_font_px'] < min_font - 0.01:
            out.append(f"{who}: text at {row['min_font_px']}px (minimum {min_font}px)")
        if (row.get('scale') or 0) > MAX_UPSCALE + 0.01:
            out.append(f"{who}: photo enlarged {row['scale']:.2f}x (max {MAX_UPSCALE}x)")
    return out


# ---- rendering (Chrome via Playwright) ---------------------------------------------------------------------------

async def _shot(page, omit_background: bool = False) -> Image.Image:
    data = await page.screenshot(clip={'x': 0, 'y': 0, 'width': VW, 'height': VH}, omit_background=omit_background,
                                 type='png')
    im = Image.open(BytesIO(data))
    im.load()
    return im.convert('RGBA' if omit_background else 'RGB')


async def _load(page, doc: str, tmp: str, name: str) -> None:
    src = os.path.join(tmp, f'{name}.html')
    with open(src, 'w', encoding='utf-8') as f:
        f.write(doc)
    await page.goto('file://' + src)
    await page.evaluate('document.fonts.ready')
    await page.wait_for_function("Array.from(document.images).every(i => i.complete)")


async def _render_pages(post: dict, *, layers: bool, details: list[dict], end_card: bool, base_dir: str | None,
                        report: list | None, verbose: bool) -> dict:
    """Render the cover (always), and for a reel the cover's layers, the vertical detail slides and the end card."""
    from playwright.async_api import async_playwright

    _check_hype(post)
    cover = _hype_slides(post)[0]
    photo, focal, zoom, photo_h = vertical_source(cover)
    photo = _resolve_photo(photo, base_dir)
    if not os.path.isfile(photo):
        raise FileNotFoundError(f"post {post['slug']}: photo not found: {photo}")
    win = PhotoWindow(photo, focal, zoom, photo_h)
    out = {'window': win}
    tmp = tempfile.mkdtemp(prefix='cardkit_vertical_')
    rows = []
    try:
        still = win.at(1.0)
        photo_file = os.path.join(tmp, 'window.png')
        still.save(photo_file)
        top_lum = _lum(still, (330, 200, 750, 330))
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=_chrome(),
                                               args=['--no-sandbox', '--allow-file-access-from-files'])
            page = await browser.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=1)
            await _load(page, vcover_html(post, cover, photo_file, win.h, top_lum), tmp, 'cover')
            info = await page.evaluate(VCOVER_JS, dict(VHEAD_FIT, photoH=win.h, solidBelow=SOLID_BELOW_TEXT_TOP,
                                                       fadeLen=FADE_LEN, creditY=CREDIT_Y, safeTop=SAFE_TOP,
                                                       safeBottom=SAFE_BOTTOM, pad=16, H=VH))
            info.update(await page.evaluate(VCHECK_JS, CHECK_OPTS))
            info.update(page='cover', type='cover', scale=round(win.scale, 3), photo_h=win.h,
                        crop=list(win.box), credit_line=cover.get('photo_credit'))
            rows.append(info)
            out['cover'] = await _shot(page)
            if layers:
                await page.evaluate("document.body.classList.add('layer-overlay')")
                out['overlay'] = await _shot(page, omit_background=True)
                await page.evaluate("document.body.classList.remove('layer-overlay');"
                                    "document.body.classList.add('layer-text')")
                out['text'] = await _shot(page, omit_background=True)
            out['details'] = []
            for i, s in enumerate(details, 1):
                await _load(page, vdetail_html(post, s), tmp, f'detail{i}')
                info = await page.evaluate(HYPE_DETAIL_JS, VDETAIL_FIT)
                await page.evaluate(BALANCE_JS, '.slabel, li')
                info.update(await page.evaluate(VCHECK_JS, CHECK_OPTS))
                info['left_edges'].pop('stat', None)              # the italic stat is aligned optically
                info.update(page=f'detail {i}', type='detail', credit_line=credit_line_text(post, s))
                rows.append(info)
                out['details'].append(await _shot(page))
            if end_card:
                await _load(page, vend_html(post), tmp, 'end')
                info = await page.evaluate(VCHECK_JS, CHECK_OPTS)
                info.update(page='end card', type='end')
                rows.append(info)
                out['end'] = await _shot(page)
            await browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for row in rows:
        row['problems'] = vertical_problems([row])
        if verbose:
            extra = f" head {row['size']}px x{row['lines']}" if row['type'] == 'cover' else ''
            flag = f"  PROBLEMS: {'; '.join(row['problems'])}" if row['problems'] else ''
            print(f"[cardkit:vertical] {post['slug']} {row['page']}:{extra}{flag}", file=sys.stderr)
    if report is not None:
        report.extend(rows)
    out['rows'] = rows
    return out


def _save_jpg(im: Image.Image, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    im.convert('RGB').save(path, 'JPEG', quality=JPEG_QUALITY, subsampling=0, optimize=True)
    return path


def render_story(post: dict, out_jpg: str, report: list | None = None, verbose: bool = True,
                 base_dir: str | None = None) -> str:
    """The Story card for `post` (a hype post dict) as a 1080x1920 JPEG. Pass report=[] for the checks
    (vertical_problems(report) lists anything wrong)."""
    pages = asyncio.run(_render_pages(post, layers=False, details=[], end_card=False, base_dir=base_dir,
                                      report=report, verbose=verbose))
    return _save_jpg(pages['cover'], out_jpg)


# ---- CLI ---------------------------------------------------------------------------------------------------------

def load_post(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    if isinstance(doc, list):
        if len(doc) != 1:
            raise ValueError("POST.json must hold one post (or a list with one post)")
        doc = doc[0]
    return doc


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog='python3 -m cardkit.vertical', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('story', help='a 1080x1920 Story card (JPEG) from a hype post dict')
    s.add_argument('post')
    s.add_argument('out')
    a = ap.parse_args(argv)
    post = load_post(a.post)
    rows: list = []
    path = render_story(post, a.out, report=rows, base_dir=os.path.dirname(os.path.abspath(a.post)))
    problems = vertical_problems(rows)
    print(json.dumps({'story': path, 'ok': not problems, 'problems': problems,
                      'photo_h': rows[0].get('photo_h'), 'scale': rows[0].get('scale')}, indent=1))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
