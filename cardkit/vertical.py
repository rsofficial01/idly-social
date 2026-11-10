"""cardkit.vertical: idly's 9:16 formats (1080x1920), built from the same post dict as the hype template.

    render_story(post, out_jpg, report=[])        # an Instagram Story card: one JPEG
    python3 -m cardkit.vertical story POST.json OUT.jpg     # exit 1 if the layout has problems

    (cardkit.reel films the same layout, CSS and checks as a motion reel: reel.mp4 + reel_cover.jpg.)

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
  * nothing in Instagram's UI zones (a SafeZone): on a Story, text stays between y 220 and y 1600 (STORY_ZONE);
    on a Reel, where the caption, username and audio overlay covers the bottom ~540 px and the like/comment/share
    buttons sit at x >= 960 from y ~1000 down, text stays in y 220-1380 and clear of that column
    (REEL_SAFE_ZONE). No text is smaller than 30 px.
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

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter, ImageOps

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardkit.render import (EMBER, JPEG_QUALITY, LOGO_FILE, LOGOS, _check_hype, _chrome, _esc, _hype_css,  # noqa: E402
                            _hype_slides, _lum)

VW, VH = 1080, 1920
VSIDE = 64                               # every text line starts here


@dataclass(frozen=True)
class SafeZone:
    """Where text may sit on a 1080x1920 frame; Instagram's own UI covers the rest. Below `right_from`, nothing
    important sits right of `right` (the Reels button column). head_max and fade_len are the cover's headline size
    and photo fade for that frame (a higher text block needs a smaller headline and a shorter fade)."""
    name: str
    top: int
    bottom: int
    right: int = VW
    right_from: int = VH
    head_max: int = 92
    fade_len: int = 620

    @property
    def col_right(self) -> int:
        """Right edge of the text column."""
        return min(VW - VSIDE, self.right)


# Stories: Instagram's progress bar and name on top (~220 px), the reply bar at the bottom (~320 px).
STORY_ZONE = SafeZone("story", top=220, bottom=1600)
# Reels: the caption, username and audio overlay covers roughly the bottom 540 px; the like/comment/share buttons sit
# at x >= 960 from y ~1000 down. Every reel frame keeps its text inside this zone. THE setting to change if Instagram
# moves its Reels UI.
REEL_SAFE_ZONE = SafeZone("reel", top=220, bottom=1380, right=960, right_from=1000, head_max=84, fade_len=500)
SAFE_TOP, SAFE_BOTTOM = STORY_ZONE.top, STORY_ZONE.bottom
MIN_TEXT_PX = 30
VBG, VBG_RGB = '#0A0A0A', (10, 10, 10)
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
FADE_LEN, SOLID_BELOW_TEXT_TOP = STORY_ZONE.fade_len, 150
SRC_GAP, SRC_H = 24, 36                  # detail slides: Sources line, then this gap, then the footer
BODY_GAP = 30                            # detail slides: the body band starts/ends this far from logo and Sources
OPTICAL_LIFT = 40                        # detail slides: the block sits this far above the band's centre
MAX_EMPTY_BAND = 220                     # detail slides: no empty horizontal band taller than this (Rahul's rule)
# detail slides (reels): start sizes, the smallest they may shrink to and the largest they may grow to; spacing
# (label, rule and bullet gaps) may grow up to gapMax times, until no band above or below the block is over maxGap
VDETAIL_FIT = dict(stat=360, statMin=150, statMax=420, label=60, labelMin=52, labelMax=72, bullet=48, bulletMin=40,
                   bulletMax=56, gapMax=2.2, labelGap=40, ruleTop=44, ruleBottom=40, liGap=24, maxGap=150)
END_LOGO_H = 150
PUSH_ORIGIN = (540, 530)                 # the reel's push-in centre: the middle of pipeline.framing.REEL's face
                                         # band (y 360-700), so planned faces stay clear of logo, text and edges


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
.v .head{position:static;width:%(head_w)dpx;font-size:%(head_max)dpx;line-height:1.02;text-shadow:none}
.v.d .body{top:%(body_top)dpx;bottom:%(body_bottom)dpx;padding-bottom:%(lift2)dpx;right:auto;width:%(body_w)dpx}
.v.d .slabel,.v.d li{max-width:%(text_w)dpx;text-wrap:wrap}
.v.d .logo,.v.e .logo{filter:none}
.srcwrap{position:absolute;left:%(side)dpx;width:%(text_w)dpx;bottom:%(src_bottom)dpx}
.v .srcline{font:500 %(src_px)dpx/1.2 Inter;color:rgba(255,255,255,.52);margin:0}
.endblk{position:absolute;left:%(side)dpx;width:%(text_w)dpx;top:%(safe_top)dpx;bottom:%(safe_bottom)dpx;display:flex;
        flex-direction:column;justify-content:center;align-items:flex-start}
.endlogo{height:%(end_logo_h)dpx;width:auto;display:block;margin-left:%(end_logo_ml)spx}
.endsite{font:800 132px/1 Inter;letter-spacing:-.045em;color:#fff;margin-top:64px}
.endhandle{font:600 50px/1 Inter;letter-spacing:-.01em;color:%(ember)s;margin-top:30px}
"""


def _logo_path(acct: str) -> str:
    return os.path.join(LOGOS, f"{LOGO_FILE[acct]}_white.png")


def _logo_pad(acct: str, height: int) -> float:
    """The logo PNG's transparent left margin at `height`, so its ink lines up with the text column."""
    with Image.open(_logo_path(acct)) as im:
        bbox = im.split()[-1].getbbox() or (0, 0, 0, 0)
        return round(bbox[0] / im.height * height, 1)


def _vcss(acct: str, zone: SafeZone = STORY_ZONE, **kw) -> str:
    base = dict(W=VW, H=VH, bg='transparent', side=VSIDE, dside=VSIDE, logo_h=LOGO_H, ember=EMBER)
    css = _hype_css(**{**base, **{k: v for k, v in kw.items() if k in ('top_a', 'logo_edge', 'logo_glow')}})
    text_w = zone.col_right - VSIDE
    src_bottom_y = zone.bottom - FOOT_PX - SRC_GAP
    body_top_y, body_bottom_y = LOGO_TOP + LOGO_H + BODY_GAP, src_bottom_y - SRC_H - BODY_GAP
    vals = dict(W=VW, H=VH, vbg=VBG, vbg_rgb=','.join(map(str, VBG_RGB)), photo_h=PHOTO_H_MIN, logo_top=LOGO_TOP,
                credit_right=CREDIT_RIGHT, credit_bottom=VH - CREDIT_Y, credit_px=CREDIT_PX, side=VSIDE,
                foot_w=text_w, foot_bottom=VH - zone.bottom, foot_px=FOOT_PX,
                head_bottom=VH - zone.bottom + FOOT_PX + HEAD_GAP, head_w=min(HEAD_W, text_w), head_max=zone.head_max,
                kick_px=KICK_PX, ember=EMBER, body_top=body_top_y, body_bottom=VH - body_bottom_y,
                body_w=text_w + 40, lift2=2 * OPTICAL_LIFT, text_w=text_w, src_bottom=VH - src_bottom_y,
                src_px=SRC_PX, safe_top=zone.top, safe_bottom=VH - zone.bottom, end_logo_h=END_LOGO_H,
                end_logo_ml=-_logo_pad(acct, END_LOGO_H))
    vals.update({k: v for k, v in kw.items() if k in vals})
    return css + VERTICAL_CSS % vals


def detail_band(zone: SafeZone, has_sources: bool = True) -> tuple[int, int]:
    """(y just below the logo, y of the top of the Sources line or footer): the band a detail slide's block fills."""
    src_bottom_y = zone.bottom - FOOT_PX - SRC_GAP
    return LOGO_TOP + LOGO_H, (src_bottom_y - SRC_H) if has_sources else (zone.bottom - FOOT_PX)


def _foot(post: dict) -> str:
    return (f"<div class='cfoot'><span data-chk='date' data-edge='1'>{_esc(post['date'])}</span>"
            f"<span data-chk='site'>idly.news</span></div>")


def vcover_html(post: dict, slide: dict, photo_file: str, photo_h: int, top_lum: float,
                zone: SafeZone = STORY_ZONE) -> str:
    """The story card / reel cover. `photo_file` is the already-cropped 1080 x photo_h window."""
    top_a = 0.42 if top_lum > 150 else (0.26 if top_lum > 90 else 0.12)
    logo_edge, logo_glow = (0.35, 0.55) if top_lum > 150 else ((0.2, 0.4) if top_lum > 110 else (0, 0.3))
    css = _vcss(post['acct'], zone, photo_h=photo_h, top_a=top_a, logo_edge=logo_edge, logo_glow=logo_glow)
    credit = (f"<div class='credit' data-chk='credit'>{_esc(slide['photo_credit'])}</div>"
              if slide.get('photo_credit') else '')
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>
<div class='s v c'>
  <div class='bgfill'></div>
  <img class='ph' src='file://{html.escape(photo_file)}'>
  <div class='topfade'></div><div class='vfade'></div><div class='vsolid'></div>
  <img class='logo' data-chk='logo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
  {credit}
  <div class='txt'><div class='kick' data-chk='kicker' data-edge='1'>@{_esc(post['acct'])}</div><div class='head' id='head' data-chk='headline' data-edge='1' data-lines='1'>{_esc(slide['headline'])}</div></div>
  {_foot(post)}
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
    if (clen > cb - (o.safeTop + o.pad)) cb = Math.min(o.creditMax, o.safeTop + o.pad + clen);
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
    const it = parseFloat(el.dataset.inkTop || 0), ib = parseFloat(el.dataset.inkBottom || 0);
    return {el, name: el.dataset.chk, mark: el.dataset.kind === 'mark', x0: r.left, y0: r.top + it, x1: r.right,
            y1: r.bottom - ib}; })
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
  const buttons = items.filter(i => i.y1 > o.rightFrom + 0.5 && i.x1 > o.rightX + 0.5)
                       .map(i => `${i.name} x ${r(i.x0)}-${r(i.x1)} y ${r(i.y0)}-${r(i.y1)}`);
  const lineWidths = el => {
    const rg = document.createRange(); rg.selectNodeContents(el);
    const lines = [];
    for (const q of rg.getClientRects()) {
      if (q.width < 0.5) continue;
      const L = lines.find(x => Math.abs(x.mid - (q.top + q.bottom) / 2) < q.height * 0.4);
      if (L) { L.l = Math.min(L.l, q.left); L.r = Math.max(L.r, q.right); }
      else lines.push({mid: (q.top + q.bottom) / 2, l: q.left, r: q.right});
    }
    return lines.sort((a, b) => a.mid - b.mid).map(x => x.r - x.l);
  };
  const orphans = els.filter(el => el.dataset.lines).filter(el => {
    const w = lineWidths(el);            // a last line under 30% of the longest: a lone word left hanging
    return w.length >= 2 && w[w.length - 1] < 0.3 * Math.max(...w);
}).map(el => el.dataset.chk);
  const left_edges = {};
  els.filter(el => el.dataset.edge).forEach(el => { left_edges[el.dataset.chk] = r(el.getBoundingClientRect().left); });
  const texts = items.filter(i => !i.mark);
  const min_font_px = texts.length ? Math.min(...texts.map(i => parseFloat(getComputedStyle(i.el).fontSize))) : null;
  const truncated = items.filter(i => getComputedStyle(i.el).textOverflow === 'ellipsis' &&
                                      i.el.scrollWidth > i.el.clientWidth + 1).map(i => i.name);
  const boxes = {}; items.forEach(i => { boxes[i.name] = [r(i.x0), r(i.y0), r(i.x1), r(i.y1)]; });
  return {collisions, ui_zone, outside, ui_buttons: buttons, orphans, left_edges, min_font_px, truncated, boxes};
}
"""

# reel detail scenes: balance wrapped labels and bullets ourselves (the narrowest width that keeps the same number of
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

def check_opts(zone: SafeZone) -> dict:
    return dict(safeTop=zone.top, safeBottom=zone.bottom, W=VW, margin=24, rightX=zone.right, rightFrom=zone.right_from)


CHECK_OPTS = check_opts(STORY_ZONE)


def max_empty_band(im: Image.Image, top: int, bottom: int, tol: int = 14) -> int:
    """The tallest run of rows between `top` and `bottom` with nothing on them but the brand background."""
    region = im.convert('RGB').crop((0, top, VW, bottom))
    diff = ImageChops.difference(region, Image.new('RGB', region.size, VBG_RGB)).convert('L')
    data = diff.point(lambda v: 255 if v > tol else 0).tobytes()
    run = best = 0
    for y in range(region.height):
        if data[y * VW:(y + 1) * VW].strip(b'\x00'):
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


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
        top, bottom = row.get('safe') or (SAFE_TOP, SAFE_BOTTOM)
        for z in row.get('ui_zone') or []:
            out.append(f"{who}: {z} is inside Instagram's UI zone (text must stay in y {top}-{bottom})")
        for z in row.get('ui_buttons') or []:
            out.append(f"{who}: {z} is under the Reels buttons (right of x {REEL_SAFE_ZONE.right} below "
                       f"y {REEL_SAFE_ZONE.right_from})")
        for z in row.get('outside') or []:
            out.append(f"{who}: {z} is outside the margins")
        for z in row.get('orphans') or []:
            out.append(f"{who}: {z} ends with a lone word on its last line")
        if row.get('type') == 'detail' and (row.get('max_band') or 0) > MAX_EMPTY_BAND:
            out.append(f"{who}: a {row['max_band']}px empty band (max {MAX_EMPTY_BAND}px)")
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


async def _render_pages(post: dict, *, base_dir: str | None, report: list | None, verbose: bool,
                        zone: SafeZone = STORY_ZONE) -> dict:
    """Render the story card (the cover page) inside `zone`. (cardkit.reel lays out and films its own page.)"""
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
            opts = check_opts(zone)
            safe = [zone.top, zone.bottom]
            await _load(page, vcover_html(post, cover, photo_file, win.h, top_lum, zone), tmp, 'cover')
            credit_max = zone.right_from if zone.right < VW else zone.bottom   # reels: stay above the buttons
            info = await page.evaluate(VCOVER_JS, dict(VHEAD_FIT, max=zone.head_max, photoH=win.h,
                                                       solidBelow=SOLID_BELOW_TEXT_TOP, fadeLen=zone.fade_len,
                                                       creditY=CREDIT_Y, creditMax=credit_max, safeTop=zone.top,
                                                       safeBottom=zone.bottom, pad=16, H=VH))
            info.update(await page.evaluate(VCHECK_JS, opts))
            info.update(page='cover', type='cover', zone=zone.name, safe=safe, scale=round(win.scale, 3),
                        photo_h=win.h, crop=list(win.box), credit_line=cover.get('photo_credit'))
            rows.append(info)
            out['cover'] = await _shot(page)
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
    pages = asyncio.run(_render_pages(post, base_dir=base_dir, report=report, verbose=verbose))
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
