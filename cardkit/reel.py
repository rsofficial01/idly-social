"""cardkit.reel: a post as a silent 9:16 Instagram Reel in motion graphics, from the same post dict as the Story card.

    render_reel(post, out_dir, details=None, report=[])   # <out_dir>/reel.mp4 + reel_cover.jpg (+ preview stills)
    python3 -m cardkit.reel POST.json OUT_DIR [--details 1,2] [--previews] [--sheet SHEET.jpg]   # exit 1 if wrong

How it is made (the technique of the Nvidia counter clip, 10 Nov 2026): every scene is one HTML page, a JS
setT(t) poses every element for time t, Chrome films it at 30 fps as JPEG screenshots (one page, reused) and ffmpeg
encodes them as they arrive: 1080x1920, H.264 high yuv420p (BT.709), faststart, no edit lists, a silent AAC track
(Instagram wants one; never anyone else's music or audio), ffmpeg -preset veryfast. reel_cover.jpg (the settled
cover frame) is saved for the Reels-tab thumbnail.

Scenes (10-14 s in all, none longer than 3.5 s):
  * cover: the full-width photo pushes in (1.00 -> 1.075) and drifts up under the gradient (parallax against the
    text), the @account kicker types in, the Title Case headline rises line by line from behind its own mask
    (120 ms apart), the vertical photo credit stays visible;
  * 1-2 of the post's detail slides, each a panel that pushes up over the last: the stat counts up with an ease-out
    in its own format (23,747; 2,24,000; +86%; -4.27%; Rs 2.69 lakh; $192B) and never shows a "0" (it fades in from
    its first real value; the last frame is the exact stat), the label rises line by line, the rule draws across,
    bullets slide in one by one with their markers. A detail slide may carry a "chart": [[label, value], ...]
    ("chart_unit": "Units sold" optional): bars grow from zero one after another while their values count up;
  * an end card after a hard cut: the account's logo scales in with a small overshoot, then idly.news and the handle.
  Nothing sits still: the photo, the text and the frame furniture drift at different speeds on every hold.
Every frame keeps its text inside cardkit.vertical.REEL_SAFE_ZONE (y 220-1380, clear of the Reels buttons at
x >= 960 below y 1000), one left edge (x=64), no text under 30 px, Sources line and footer on the fact scenes.
Never a boxed photo on a blurred copy of itself.

Needs Chrome (Playwright) and ffmpeg/ffprobe. probe_reel(path) checks a file against Instagram's Reels spec;
mp4_boxes(path) needs nothing but Python, for the publisher.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cardkit.render import (EMBER, FONTS, _check_hype, _chrome, _esc, _hype_slides, _keep_compounds,  # noqa: E402
                            _lum, credit_line_text)
from cardkit.vertical import (BALANCE_JS, CREDIT_Y, END_LOGO_H, PUSH_ORIGIN, REEL_SAFE_ZONE, SHARPEN_ABOVE,  # noqa: E402
                              SOLID_BELOW_TEXT_TOP, VBG_RGB, VCHECK_JS, VCOVER_JS, VDETAIL_FIT, VH, VHEAD_FIT, VSIDE,
                              VW, PhotoWindow, SafeZone, _foot, _logo_pad, _logo_path, _resolve_photo, _save_jpg,
                              _vcss, check_opts, detail_band, load_post, max_empty_band, vertical_problems,
                              vertical_source)

__all__ = ['render_reel', 'probe_reel', 'mp4_boxes', 'video_frame', 'timeline', 'pick_details', 'ffmpeg_cmd',
           'count_spec', 'count_text', 'count_texts', 'chart_rows',
           'contact_sheet']

FPS = 30
JPEG_Q = 92                              # Chrome's JPEG frames (x264 re-encodes them; 92 keeps edges clean)
REEL_MIN_S, REEL_MAX_S = 9.0, 14.0       # Instagram allows more; idly's reels are 10-14 s
SCENE_MAX_S = 3.5
PUSH_S = 0.42                            # the next panel pushes up over the last (ease-in-out)
PUSH_BACK = 260                          # ... while the last one slides up this far and darkens
PUSH_DIM = 0.55
PHOTO_ZOOM = 1.075                       # cover: push-in over the scene (and on through the push out)
PHOTO_RISE = 22                          # cover: the photo drifts up this far (px) ...
TEXT_RISE = 14                           # ... the text block this far ...
CHROME_RISE = 8                          # ... and the logo, credit, Sources and footer this far (parallax)
DETAIL_RISE = 20                         # detail and end scenes: the content block's drift over the scene
PHOTO_OVERSAMPLE = 1.1                   # the photo goes to Chrome 10% larger than shown, so the push stays sharp
LINE_STAGGER = 0.12                      # headline lines rise 120 ms apart
STAT_AT, STAT_COUNT_S = 0.12, 1.45       # detail scenes: the stat counts up from 0.12 s (as the panel lands)
BAR_GROW_S = 0.9                         # chart bars grow (and their values count) for 0.9 s, 120 ms apart
STILL_MAX_S = 0.8                        # no stretch of identical frames longer than this
CHART_MAX_ROWS = 8
PREVIEW_TIMES = (0.5, 4.0, 7.0, 'last')
SHEET_TIMES = (0.3, 1.0, 2.0, 3.5, 5.0, 7.0, 9.0, 'last')
# detail scenes: VDETAIL_FIT plus the chart rows (name/value type, bar thickness, spacing)
REEL_DETAIL_FIT = dict(VDETAIL_FIT, row=44, rowMin=34, rowMax=54, bar=24, barMin=16, barMax=34, rowGap=34,
                       barGap=14, unitGap=26, ruleMax=1.8)   # ruleMax: then the rule's margins may grow this much more


# ---- the stats: what counts up, and how it is written ----------------------------------------------------------------

_COUNT_RE = re.compile(r"^(?P<pre>[+\-−–]?\s?(?:₹|Rs\.?\s?|INR\s?|US\$|\$|€|£|¥)?\s?)"
                       r"(?P<int>\d{1,3}(?:,\d{2,3})+|\d+)(?P<dec>\.\d+)?(?P<suf>.*)$")


def count_spec(text) -> dict | None:
    """How the stat `text` counts up, or None when it shouldn't (a year, a date, a score, a word):
    {pre, value, dec, group ('indian' | 'western' | 'none'), suf, final}. Sign and currency stay put in `pre`;
    the magnitude counts from its first real value to `value`, written like the original (decimals, grouping)."""
    text = str(text or '').strip()
    m = _COUNT_RE.match(text)
    if not m:
        return None
    pre, ip, dec, suf = m.group('pre'), m.group('int'), m.group('dec') or '', m.group('suf')
    if re.match(r"^\s*[:\-–—]\s?\d", suf) or re.match(r"^\d", suf):
        return None                                                    # 2-1, 1:30
    digits = ip.replace(',', '')
    if (not pre.strip() and not dec and ',' not in ip and len(digits) == 4 and 1900 <= int(digits) <= 2099
            and '%' not in suf):
        return None                                                    # a year
    value = float(digits + dec)
    if value <= 0:
        return None
    if ',' in ip:
        groups = ip.split(',')
        if any(len(g) == 2 for g in groups[1:-1]) or (len(groups) == 2 and len(groups[0]) <= 2):
            group = 'indian'                                           # 2,24,000 (and 23,747: the same either way)
        else:
            group = 'western'                                          # 224,000
    else:
        group = 'none'
    return {'pre': pre, 'value': value, 'dec': len(dec) - 1 if dec else 0, 'group': group, 'suf': suf,
            'final': text}


def _group(ip: str, how: str) -> str:
    if how == 'none' or len(ip) <= 3:
        return ip
    if how == 'western':
        return re.sub(r"\B(?=(\d{3})+(?!\d))", ",", ip)
    head, last3 = ip[:-3], ip[-3:]
    return re.sub(r"\B(?=(\d{2})+(?!\d))", ",", head) + ',' + last3


def count_text(spec: dict, e: float) -> str:
    """The stat at eased progress e (0..1): the exact original at 1; never below one unit of its last digit (so
    never "0"); same decimals and grouping as the original. (The page's fmt() does the same in JS.)"""
    if e >= 1:
        return spec['final']
    step = 10 ** -spec['dec']
    v = min(spec['value'], max(step, spec['value'] * max(0.0, e)))
    # JS toFixed: the exact binary value, ties rounded up (Python's format would round ties to even)
    s = str(Decimal(v).quantize(Decimal(1).scaleb(-spec['dec']), rounding=ROUND_HALF_UP))
    ip, _, fp = s.partition('.')
    return spec['pre'] + _group(ip, spec['group']) + ('.' + fp if fp else '') + spec['suf']


def _number_text(v) -> str:
    """A chart value given as a number, written the Indian way (23747 -> 23,747; 224000 -> 2,24,000)."""
    if isinstance(v, float) and not v.is_integer():
        ip, _, fp = repr(v).partition('.')
        return _group(ip, 'indian') + '.' + fp
    return _group(str(int(v)), 'indian')


def chart_rows(slide: dict) -> tuple[list[dict], str] | None:
    """A detail slide's chart as ([{label, text, value, frac, spec, lead}], unit), or None when it has none.
    `chart` is a list of [label, value] (value a number, or a stat-like string such as "Rs 2.69 lakh"), or
    {"rows": [...], "unit": "..."}; `chart_unit` also sets the unit. Bars start at zero: frac = value / max."""
    c = slide.get('chart')
    if not c:
        return None
    unit = slide.get('chart_unit') or ''
    if isinstance(c, dict):
        unit = c.get('unit') or unit
        c = c.get('rows') or []
    if not isinstance(c, (list, tuple)) or not 2 <= len(c) <= CHART_MAX_ROWS:
        raise ValueError(f"chart: give 2-{CHART_MAX_ROWS} rows of [label, value]")
    rows = []
    for r in c:
        if not (isinstance(r, (list, tuple)) and len(r) == 2 and str(r[0]).strip()):
            raise ValueError(f"chart: each row is [label, value], not {r!r}")
        label, v = str(r[0]).strip(), r[1]
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            raise ValueError(f"chart: {label}: the value must be a number")
        text = _number_text(v) if isinstance(v, (int, float)) else str(v).strip()
        spec = count_spec(text)
        value = float(v) if isinstance(v, (int, float)) else (spec or {}).get('value')
        if value is None or value < 0 or (spec is None and value != 0):
            raise ValueError(f"chart: {label}: {text!r} is not a number")
        rows.append({'label': label, 'text': text, 'value': value, 'spec': spec})
    top = max(r['value'] for r in rows)
    if top <= 0:
        raise ValueError("chart: every value is zero")
    affixes = {((r['spec'] or {}).get('pre', '').strip(), (r['spec'] or {}).get('suf', '').strip()) for r in rows
               if r['spec']}
    if len(affixes) > 1:
        raise ValueError(f"chart: the values mix units {sorted(affixes)}: bars only compare like with like")
    lead = max(range(len(rows)), key=lambda i: rows[i]['value'])
    for i, r in enumerate(rows):
        r.update(frac=r['value'] / top, lead=i == lead)
    return rows, str(unit).strip()


# ---- timeline -------------------------------------------------------------------------------------------------------

def pick_details(post: dict, details: list[int] | None = None) -> list[dict]:
    """The detail slides for the reel: `details` are 1-based positions among the post's detail slides
    (default: the first two)."""
    pool = [s for s in _hype_slides(post)[1:] if s.get('type', 'cover') == 'detail']
    if details:
        bad = [n for n in details if not 1 <= int(n) <= len(pool)]
        if bad:
            raise ValueError(f"post {post.get('slug')}: no detail slide {bad} (it has {len(pool)})")
        picked = [pool[int(n) - 1] for n in details]
    else:
        picked = pool[:2]
    if len(picked) > 2:
        raise ValueError("a reel shows at most 2 detail slides")
    return picked


def timeline(n_details: int) -> list[tuple[str, int]]:
    """(scene, frames) at 30 fps: 10-14 s in all, no scene over 3.5 s. A reel needs at least one detail slide
    (a cover alone can't make 10 s of motion without holding a scene too long)."""
    if n_details >= 2:
        return [('cover', 96), ('detail1', 102), ('detail2', 105), ('end', 60)]       # 3.2 + 3.4 + 3.5 + 2.0 = 12.1 s
    if n_details == 1:
        return [('cover', 105), ('detail1', 105), ('end', 90)]                         # 3.5 + 3.5 + 3.0 = 10.0 s
    raise ValueError("a reel needs at least one detail slide (a stat, bullets or a chart): the cover alone can't "
                     "carry 10 seconds")


def _enter(name: str) -> str:
    """How a scene arrives: the cover opens the reel, detail panels push up over the last, the end card is a cut."""
    return 'open' if name == 'cover' else ('cut' if name == 'end' else 'push')


# ---- the page ---------------------------------------------------------------------------------------------------------

REEL_CSS = """
#stage{position:relative;width:%(W)dpx;height:%(H)dpx;overflow:hidden;background:%(vbg)s}
#stage>.scene{position:absolute;left:0;top:0;visibility:hidden}
.grp{position:absolute;left:0;top:0;width:%(W)dpx;height:%(H)dpx}
/* composited layers: Chrome moves them by fractions of a pixel (painted text snaps to whole pixels, so a slow drift
   would tick); the photo stays painted, so every frame of the push-in is drawn from the full-size image */
#stage>.scene,.grp,.lni,.stat,.v.d li,.rlab,.cfoot,.srcwrap,.cunit,.endlogo{will-change:transform}
.dim{position:absolute;left:0;top:0;width:%(W)dpx;height:%(H)dpx;background:#000;opacity:0}
.v.c .ph{width:%(W)dpx;transform-origin:%(ox)dpx %(oy)dpx}
.v.d .body{overflow:visible}
.ln{display:block;overflow:hidden;white-space:nowrap;padding:.08em 0 .18em;margin:-.08em 0 -.18em}
.lni{display:block}
.kick .ch{white-space:pre}
.chart{width:100%%;flex:none}
.cunit{font:600 30px/1.1 Inter;letter-spacing:.01em;color:rgba(255,255,255,.6)}
.row .rtop{display:flex;align-items:baseline;width:100%%}
.rlab{flex:0 1 auto;min-width:0;font:700 44px/1.1 Inter;letter-spacing:-.01em;color:#fff;white-space:nowrap;
      overflow:hidden;text-overflow:ellipsis}
.rval{flex:none;margin-left:auto;padding-left:24px;font:800 44px/1.1 Inter;letter-spacing:-.01em;color:#fff;
      font-variant-numeric:tabular-nums;white-space:nowrap}
.row.lead .rval{color:%(ember)s}
.track{position:relative;width:100%%;height:24px;background:rgba(255,255,255,.09);border-radius:3px;overflow:hidden}
.bar{position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(255,255,255,.88);border-radius:3px}
.row.lead .bar{background:%(ember)s}
.endsite,.endhandle{white-space:nowrap}
"""


def _ink_mark(cls: str, chk: str, text: str, extra: str = '') -> str:
    return f"<div class='{cls}' data-chk='{chk}' data-edge='1'{extra}>{text}</div>"


def _cover_scene(post: dict, slide: dict) -> str:
    credit = (f"<div class='credit' data-chk='credit'>{_esc(slide['photo_credit'])}</div>"
              if slide.get('photo_credit') else '')
    kick = ''.join(f"<span class='ch'>{_esc(ch)}</span>" for ch in f"@{post['acct']}")
    return f"""<div class='scene s v c' id='sc0'>
  <div class='bgfill'></div>
  <img class='ph' src='photo.jpg'>
  <div class='topfade'></div><div class='vfade'></div><div class='vsolid'></div>
  <div class='grp chrome'>
    <img class='logo' data-chk='logo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
    {credit}
    {_foot(post)}
  </div>
  <div class='grp content'>
    <div class='txt'><div class='kick' data-chk='kicker' data-edge='1'>{kick}</div><div class='head' id='head' data-chk='headline' data-edge='1' data-lines='1'>{_esc(slide['headline'])}</div></div>
  </div>
  <div class='dim'></div>
</div>"""


def _detail_scene(post: dict, slide: dict, i: int) -> str:
    stat = (f"<div class='stat' data-chk='stat'>{_esc(slide['stat'])}</div>"
            if (slide.get('stat') or '').strip() else '')
    label = (f"<div class='slabel' data-chk='label' data-edge='1' data-lines='1'>{_keep_compounds(slide['stat_label'])}</div>"
             if slide.get('stat_label') else '')
    chart = ''
    rows = chart_rows(slide)
    if rows:
        rs, unit = rows
        chart = "<div class='chart'>" + (_ink_mark('cunit', 'unit', _esc(unit)) if unit else '')
        for n, r in enumerate(rs, 1):
            chart += (f"<div class='row{' lead' if r['lead'] else ''}'><div class='rtop'>"
                      f"<span class='rlab' data-chk='row{n}' data-edge='1'>{_esc(r['label'])}</span>"
                      f"<span class='rval' data-chk='value{n}'>{_esc(r['text'])}</span></div>"
                      f"<div class='track'><div class='bar'></div></div></div>")
        chart += "</div>"
    rule = "<div class='rule'></div>" if (stat or label) and (slide.get('bullets') or chart) else ''
    bullets = ''.join(f"<li data-chk='bullet{n}' data-edge='1' data-lines='1'>{_keep_compounds(b)}</li>"
                      for n, b in enumerate(slide.get('bullets') or [], 1))
    src = credit_line_text(post, slide)
    srcline = (f"<div class='srcwrap'><div class='srcline' data-chk='sources' data-edge='1'>{_esc(src)}</div></div>"
               if src else '')
    return f"""<div class='scene s v d' id='sc{i}'>
  <div class='bgfill'></div>
  <div class='grp chrome'>
    <img class='logo' data-chk='logo' data-kind='mark' src='file://{_logo_path(post['acct'])}'>
    {srcline}
    {_foot(post)}
  </div>
  <div class='grp content'><div class='body'>{stat}{label}{rule}{chart}<ul>{bullets}</ul></div></div>
  <div class='dim'></div>
</div>"""


def _end_scene(post: dict, i: int) -> str:
    pad = _logo_pad(post['acct'], END_LOGO_H)
    return f"""<div class='scene s v e' id='sc{i}'>
  <div class='bgfill'></div>
  <div class='grp content'><div class='endblk'>
    <img class='endlogo' data-chk='endlogo' data-kind='mark' style='transform-origin:{pad}px 50%' src='file://{_logo_path(post['acct'])}'>
    <div class='endsite' data-chk='site' data-edge='1'>idly.news</div>
    <div class='endhandle' data-chk='handle' data-edge='1'>@{_esc(post['acct'])}</div>
  </div></div>
  <div class='dim'></div>
</div>"""


def reel_html(post: dict, cover: dict, details: list[dict], photo_h: int, top_lum: float,
              zone: SafeZone = REEL_SAFE_ZONE) -> str:
    """The whole reel as one page: #sc0 the cover, #sc1.. the detail panels, the end card last (photo.jpg is the
    cover photo window, next to the page)."""
    top_a = 0.42 if top_lum > 150 else (0.26 if top_lum > 90 else 0.12)
    logo_edge, logo_glow = (0.35, 0.55) if top_lum > 150 else ((0.2, 0.4) if top_lum > 110 else (0, 0.3))
    css = _vcss(post['acct'], zone, photo_h=photo_h, top_a=top_a, logo_edge=logo_edge, logo_glow=logo_glow)
    css += REEL_CSS % dict(W=VW, H=VH, vbg='#%02X%02X%02X' % VBG_RGB, ember=EMBER, ox=PUSH_ORIGIN[0],
                           oy=min(PUSH_ORIGIN[1], photo_h // 2))
    scenes = [_cover_scene(post, cover)] + [_detail_scene(post, s, i) for i, s in enumerate(details, 1)]
    scenes.append(_end_scene(post, len(details) + 1))
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>"
            f"<div id='stage'>{''.join(scenes)}</div><script>{REEL_JS}</script></body></html>")


# detail scenes: VDETAIL_JS (cardkit.vertical) for one scene of the page (o.root), with the chart rows: shrink until
# the block fits, then grow the type, the bars and the spacing until no empty band above or below it is over maxGap.
# The stat is sized for the widest value it will show while counting (o.texts, frame by frame), so counting never
# pushes it past the column.
REEL_DETAIL_JS = """
(o) => {
  const R = document.querySelector(o.root);
  const body = R.querySelector('.body'), stat = R.querySelector('.stat'), lab = R.querySelector('.slabel');
  const rule = R.querySelector('.rule'), chart = R.querySelector('.chart'), unit = R.querySelector('.cunit');
  const rows = Array.from(R.querySelectorAll('.row')), lis = Array.from(R.querySelectorAll('li'));
  const ul = R.querySelector('ul');
  const ctx = document.createElement('canvas').getContext('2d');
  let s = o.stat, l = o.label, b = o.bullet, c = o.row, h = o.bar, g = 1, r = 1, statMax = o.statMax;
  const sfont = () => { const cs = getComputedStyle(stat); return `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`; };
  const ink = () => {
    const cs = getComputedStyle(stat); ctx.font = sfont();
    const m = ctx.measureText(stat.textContent.trim());
    const lh = parseFloat(cs.lineHeight);
    const base = (lh - (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent)) / 2 + m.fontBoundingBoxAscent;
    return {top: base - m.actualBoundingBoxAscent, bottom: base + m.actualBoundingBoxDescent, lh,
            pad: parseFloat(cs.paddingBottom), left: m.actualBoundingBoxLeft};
  };
  const set = () => {
    if (stat) {
      stat.style.fontSize = s + 'px';
      const k = ink();
      const mt = Math.max(0, k.top), mb = Math.max(0, k.lh + k.pad - k.bottom);
      stat.style.marginTop = (-mt) + 'px'; stat.style.marginBottom = (-mb) + 'px';
      stat.dataset.inkTop = mt; stat.dataset.inkBottom = mb;
    }
    if (lab) { lab.style.fontSize = l + 'px'; lab.style.marginTop = (stat ? Math.round(o.labelGap * g) : 0) + 'px'; }
    if (rule) rule.style.margin = `${Math.round(o.ruleTop * g * r)}px 0 ${Math.round(o.ruleBottom * g * r)}px`;
    if (chart) {
      chart.style.marginTop = (rule || !(stat || lab) ? 0 : Math.round(o.labelGap * g)) + 'px';
      if (unit) unit.style.marginBottom = Math.round(o.unitGap * g) + 'px';
      rows.forEach((r, i) => {
        r.style.marginTop = (i ? Math.round(o.rowGap * g) : 0) + 'px';
        r.querySelectorAll('.rlab,.rval').forEach(x => x.style.fontSize = c + 'px');
        const t = r.querySelector('.track'); t.style.height = h + 'px'; t.style.marginTop = Math.round(o.barGap * g) + 'px';
      });
    }
    if (ul) ul.style.marginTop = (chart && lis.length ? Math.round(o.ruleTop * g) : 0) + 'px';
    lis.forEach((li, i) => { li.style.fontSize = b + 'px';
                             li.style.marginBottom = (i < lis.length - 1 ? Math.round(o.liGap * g) : 0) + 'px'; });
  };
  const statW = () => {
    if (!stat) return 0;
    ctx.font = sfont();
    const base = ctx.measureText(stat.textContent.trim()).width;
    const extra = Math.max(0, ...(o.texts || []).map(t => ctx.measureText(t).width - base));
    return stat.getBoundingClientRect().width + extra;
  };
  const over = () => body.scrollHeight > body.clientHeight + 1;
  const wide = () => rows.some(r => { const x = r.querySelector('.rlab'); return x.scrollWidth > x.clientWidth + 1; });
  const extent = () => {
    let top = Infinity, bot = -Infinity;
    for (const k of body.children) {
      const r = k.getBoundingClientRect();
      if (r.height <= 0) continue;
      const t = k === stat ? r.top + parseFloat(stat.dataset.inkTop || 0) : r.top;
      const d = k === stat ? r.bottom - parseFloat(stat.dataset.inkBottom || 0) : r.bottom;
      top = Math.min(top, t); bot = Math.max(bot, d);
    }
    return [top, bot];
  };
  const gaps = () => { const [t, d] = extent(); return [t - o.above, o.below - d]; };
  set();
  if (stat) while (statW() > o.statMaxW && s > 80) { s -= 4; set(); }
  while (over() || wide()) {
    if (stat && s > o.statMin) s -= 6;
    else if (rows.length && (c > o.rowMin || h > o.barMin)) { if (c > o.rowMin) c -= 1; if (h > o.barMin) h -= 1; }
    else if (b > o.bulletMin) b -= 1;
    else if (l > o.labelMin) l -= 1;
    else break;
    set();
  }
  for (let guard = 0; guard < 400 && Math.max(...gaps()) > o.maxGap; guard++) {
    const prev = [s, l, b, c, h, g, r];
    let grew = false;
    if (stat && s < statMax) { s += 4; grew = true; }
    if (lab && l < o.labelMax) { l += 1; grew = true; }
    if (lis.length && b < o.bulletMax) { b += 1; grew = true; }
    if (rows.length && c < o.rowMax) { c += 1; grew = true; }
    if (rows.length && h < o.barMax) { h += 1; grew = true; }
    if (!grew && g < o.gapMax) { g = Math.round((g + 0.05) * 100) / 100; grew = true; }
    if (!grew && rule && r < o.ruleMax) { r = Math.round((r + 0.05) * 100) / 100; grew = true; }
    if (!grew) break;
    set();
    if (stat && statW() > o.statMaxW) { s = prev[0]; statMax = s; set(); }
    if (over() || wide()) { [s, l, b, c, h, g, r] = prev; set(); break; }
  }
  if (stat) { const k = ink(); stat.style.marginLeft = Math.max(-40, Math.min(20, k.left)) + 'px'; }
  const [gt, gb] = gaps();
  return {stat: stat ? s : 0, label: lab ? l : 0, bullet: lis.length ? b : 0, row: rows.length ? c : 0,
          bar: rows.length ? h : 0, spacing: g, rule_spacing: r, overflow: over() || wide(), gap_above: Math.round(gt),
          gap_below: Math.round(gb)};
}
"""

# The animation engine. __setup(tl) binds the timeline Python built (scenes: start, dur, enter, cues);
# setT(t) poses every element for time t and returns the visible counters [[id, text, opacity], ...];
# __pose(i, t) shows scene i alone at its local time t (for the checks and the cover still);
# __split(el) re-sets a wrapped text block as one masked line per line, without changing a single break.
REEL_JS = r"""
const clamp = (x) => Math.max(0, Math.min(1, x));
const E = {
  lin: (x) => x,
  out3: (x) => 1 - Math.pow(1 - x, 3),
  out4: (x) => 1 - Math.pow(1 - x, 4),
  io3: (x) => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
  back: (x) => { const s = 1.9; return 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); },
};
function group(ip, how) {
  if (how === 'none' || ip.length <= 3) return ip;
  if (how === 'western') return ip.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return ip.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + ip.slice(-3);
}
function fmt(sp, e) {                  // cardkit.reel.count_text, in JS
  if (e >= 1) return sp.final;
  const step = Math.pow(10, -sp.dec);
  const v = Math.min(sp.value, Math.max(step, sp.value * Math.max(0, e)));
  const [ip, fp] = v.toFixed(sp.dec).split('.');
  return sp.pre + group(ip, sp.group) + (fp ? '.' + fp : '') + sp.suf;
}
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
window.__split = (el) => {
  const toks = [];
  for (const n of Array.from(el.childNodes)) {
    if (n.nodeType === 3) n.textContent.split(/\s+/).filter(Boolean).forEach(w => toks.push(esc(w)));
    else if (n.nodeType === 1) toks.push(n.outerHTML);
  }
  const h0 = el.getBoundingClientRect().height;
  el.innerHTML = toks.map(t => `<span class="w">${t}</span>`).join(' ');
  const lines = []; let top = null;
  for (const w of el.querySelectorAll(':scope > .w')) {
    const y = w.getBoundingClientRect().top;
    if (top === null || Math.abs(y - top) > 2) { lines.push([]); top = y; }
    lines[lines.length - 1].push(w.innerHTML);
  }
  el.innerHTML = lines.map(l => `<span class="ln"><span class="lni">${l.join(' ')}</span></span>`).join('');
  el.style.display = 'flex'; el.style.flexDirection = 'column';     // flex items: the masks' margins never collapse
  const lis = Array.from(el.querySelectorAll('.lni'));
  return {lines: lines.length, height_change: Math.round(el.getBoundingClientRect().height - h0),
          wide: lis.some(x => x.scrollWidth > el.clientWidth + 1)};
};
let TL = null;
window.__setup = (tl) => {
  TL = tl;
  TL.scenes.forEach((sc, i) => {
    sc.el = document.getElementById('sc' + i);
    sc.dimEl = sc.el.querySelector(':scope > .dim');
    sc.cues.forEach(c => { if (c.sel) c.el = sc.el.querySelector(c.sel); });
    sc.cues = sc.cues.filter(c => !c.sel || c.el);
    sc.cues.forEach(c => {
      if (c.k === 'lines') c.items = Array.from(c.el.querySelectorAll('.lni'));
      if (c.k === 'type') c.items = Array.from(c.el.querySelectorAll('.ch'));
      if (c.k === 'slide') c.items = Array.from(sc.el.querySelectorAll(c.all));
      if (c.k === 'bars') c.items = Array.from(sc.el.querySelectorAll('.row')).map((r, n) => ({
        lab: r.querySelector('.rlab'), val: r.querySelector('.rval'), bar: r.querySelector('.bar'), ...c.rows[n]}));
    });
  });
  window.__ready = true;
};
const A = {
  zoom(c, L) { const p = clamp((L - c.at) / c.dur);
    c.el.style.transform = `translateY(${(c.dy * p).toFixed(3)}px) scale(${(c.z0 + (c.z1 - c.z0) * p).toFixed(5)})`; },
  drift(c, L) { const p = clamp((L - c.at) / c.dur);
    c.el.style.transform = `translateY(${(c.y0 + (c.y1 - c.y0) * p).toFixed(3)}px)`; },
  type(c, L) { const n = L < c.at ? 0 : Math.floor((L - c.at) * c.cps + 1e-6) + 1;
    c.items.forEach((s, i) => { s.style.opacity = i < n ? 1 : 0; }); },
  lines(c, L) { c.items.forEach((e, i) => { const p = E.out4(clamp((L - c.at - i * c.stagger) / c.dur));
    e.style.transform = p >= 1 ? '' : `translateY(${((1 - p) * c.from).toFixed(3)}%)`; }); },
  fade(c, L) { const p = clamp((L - c.at) / c.dur), e = E.out3(p);
    c.el.style.opacity = e.toFixed(4);
    c.el.style.transform = c.dy && p < 1 ? `translateY(${(c.dy * (1 - e)).toFixed(3)}px)` : ''; },
  slide(c, L) { c.items.forEach((e, i) => { const p = clamp((L - c.at - i * c.stagger) / c.dur), q = E.out3(p);
    e.style.opacity = clamp(p * 2.5).toFixed(4);
    e.style.transform = p < 1 ? `translateX(${(c.dx * (1 - q)).toFixed(3)}px)` : ''; }); },
  rule(c, L) { c.el.style.width = (c.w * E.out3(clamp((L - c.at) / c.dur))).toFixed(3) + 'px'; },
  count(c, L, out) { const p = clamp((L - c.at) / c.dur), o = clamp((L - c.at) / c.fade);
    c.el.textContent = fmt(c.spec, p >= 1 ? 1 : E.out3(p));
    c.el.style.opacity = o.toFixed(4);
    const r = E.out3(clamp((L - c.at) / c.rise));
    c.el.style.transform = r < 1 ? `translateY(${(c.dy * (1 - r)).toFixed(3)}px)` : '';
    out.push([c.id, c.el.textContent, o]); },
  bars(c, L, out) { c.items.forEach((r, i) => {
    const p = clamp((L - c.at - i * c.stagger) / c.dur), e = E.out3(p);
    r.bar.style.width = (100 * r.frac * e).toFixed(4) + '%';
    r.lab.style.opacity = clamp(p * 3).toFixed(4);
    r.lab.style.transform = p < 1 ? `translateX(${(c.dx * (1 - E.out3(clamp(p * 1.6)))).toFixed(3)}px)` : '';
    if (r.spec) r.val.textContent = fmt(r.spec, p >= 1 ? 1 : e);
    const o = r.spec ? clamp(p / 0.1) : clamp(p * 3);
    r.val.style.opacity = o.toFixed(4);
    if (r.spec) out.push([c.id + '.' + i, r.val.textContent, o]); }); },
  pop(c, L) { const p = clamp((L - c.at) / c.dur);
    c.el.style.transform = p < 1 ? `scale(${(c.s0 + (1 - c.s0) * E.back(p)).toFixed(5)})` : '';
    c.el.style.opacity = clamp((L - c.at) / c.fade).toFixed(4); },
};
function pose(sc, L, out) { sc.cues.forEach(c => A[c.k](c, L, out)); }
function show(sc, vis, ty, dim) {
  sc.el.style.visibility = vis ? 'visible' : 'hidden';
  sc.el.style.transform = ty ? `translateY(${ty.toFixed(3)}px)` : '';
  sc.dimEl.style.opacity = dim ? dim.toFixed(4) : 0;
}
window.setT = (t) => {
  const S = TL.scenes, out = [];
  let k = S.length - 1;
  for (let i = 0; i < S.length; i++) if (t < S[i].start + S[i].dur - 1e-9) { k = i; break; }
  const lk = t - S[k].start, pushing = S[k].enter === 'push' && lk < TL.push;
  const q = pushing ? E.io3(clamp(lk / TL.push)) : 1;
  S.forEach((sc, i) => {
    if (i === k) { show(sc, true, pushing ? TL.H * (1 - q) : 0, 0); pose(sc, lk, out); }
    else if (pushing && i === k - 1) { show(sc, true, -TL.back * q, TL.dim * q); pose(sc, t - sc.start, out); }
    else show(sc, false, 0, 0);
  });
  return out;
};
window.__pose = (i, L) => {
  const out = [];
  TL.scenes.forEach((sc, j) => show(sc, j === i, 0, 0));
  pose(TL.scenes[i], L, out);
  return out;
};
"""


def _cues(name: str, info: dict, dur: float, tail: float) -> list[dict]:
    """The animation cues of one scene (seconds from the scene's start). `info` is what the layout pass measured
    (line counts, what the scene holds); `tail` is how long the scene stays visible after `dur` (the push out)."""
    span = dur + tail
    if name == 'cover':
        return [
            {'k': 'zoom', 'sel': '.ph', 'at': 0, 'dur': span, 'z0': 1.0, 'z1': PHOTO_ZOOM, 'dy': -PHOTO_RISE},
            {'k': 'drift', 'sel': '.chrome', 'at': 0, 'dur': span, 'y0': 0, 'y1': -CHROME_RISE},
            {'k': 'drift', 'sel': '.content', 'at': 0, 'dur': span, 'y0': 0, 'y1': -TEXT_RISE},
            {'k': 'type', 'sel': '.kick', 'at': 0.0, 'cps': 36, 'n': info.get('kick_chars', 16)},
            {'k': 'lines', 'sel': '.head', 'at': 0.12, 'stagger': LINE_STAGGER, 'dur': 0.6, 'from': 130,
             'n': info.get('head_lines', 3)},
            {'k': 'fade', 'sel': '.cfoot', 'at': 0.42, 'dur': 0.4, 'dy': 14},
        ]
    if name == 'end':
        return [
            {'k': 'drift', 'sel': '.content', 'at': 0, 'dur': span, 'y0': DETAIL_RISE * 0.4, 'y1': -DETAIL_RISE * 0.4},
            # the cut lands on the logo already on its way in (0.05 s pre-roll), never on an empty frame
            {'k': 'pop', 'sel': '.endlogo', 'at': -0.05, 'dur': 0.55, 's0': 0.55, 'fade': 0.12},
            {'k': 'lines', 'sel': '.endsite', 'at': 0.26, 'stagger': LINE_STAGGER, 'dur': 0.55, 'from': 130, 'n': 1},
            {'k': 'lines', 'sel': '.endhandle', 'at': 0.26 + LINE_STAGGER * 1.5, 'stagger': LINE_STAGGER,
             'dur': 0.55, 'from': 130, 'n': 1},
        ]
    t = STAT_AT                                                 # content arrives with the panel (push: 0.42 s)
    cues = [{'k': 'drift', 'sel': '.chrome', 'at': 0, 'dur': span, 'y0': 0, 'y1': -CHROME_RISE},
            {'k': 'drift', 'sel': '.content', 'at': 0, 'dur': span, 'y0': DETAIL_RISE / 2, 'y1': -DETAIL_RISE / 2},
            {'k': 'fade', 'sel': '.srcwrap', 'at': 0.35, 'dur': 0.45, 'dy': 0}]
    if info.get('stat'):
        if info.get('stat_spec'):
            cues.append({'k': 'count', 'id': f"{name}.stat", 'sel': '.stat', 'at': t, 'dur': STAT_COUNT_S, 'fade': 0.22,
                         'rise': 0.55, 'dy': 26, 'spec': info['stat_spec']})
        else:
            cues.append({'k': 'fade', 'sel': '.stat', 'at': t, 'dur': 0.55, 'dy': 26})
        t += 0.2
    if info.get('label_lines'):
        cues.append({'k': 'lines', 'sel': '.slabel', 'at': t, 'stagger': LINE_STAGGER, 'dur': 0.55, 'from': 130,
                     'n': info['label_lines']})
        t += LINE_STAGGER * (info['label_lines'] - 1) + (0.1 if info.get('rows') else 0.42)
    if info.get('rule'):
        cues.append({'k': 'rule', 'sel': '.rule', 'at': t, 'dur': 0.4, 'w': 96})
        t += 0.05 if info.get('rows') else 0.15
    if info.get('rows'):                                        # bars start while the title is still rising
        if info.get('unit'):
            cues.append({'k': 'fade', 'sel': '.cunit', 'at': t, 'dur': 0.4, 'dy': 10})
            t += 0.05
        cues.append({'k': 'bars', 'id': f"{name}.bar", 'at': t, 'stagger': LINE_STAGGER, 'dur': BAR_GROW_S,
                     'dx': -24, 'rows': info['rows']})
        t += LINE_STAGGER * (len(info['rows']) - 1) + 0.5
    if info.get('bullets'):
        cues.append({'k': 'slide', 'all': 'li', 'at': t, 'stagger': 0.16, 'dur': 0.45, 'dx': -36,
                     'n': info['bullets']})
    return cues


def _ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def count_texts(spec: dict, at: float, dur: float, frames: int) -> list[str]:
    """Every value a counter shows, frame by frame, when it counts from `at` for `dur` seconds of a scene that is
    visible for `frames` frames (the fit sizes the stat for the widest of them)."""
    out = []
    for n in range(frames):
        p = (n / FPS - at) / dur
        t = count_text(spec, 1.0 if p >= 1 else _ease_out(p))
        if not out or out[-1] != t:
            out.append(t)
    return out


def _settled(cues: list[dict]) -> float:
    """When the last reveal of a scene has finished (drifts and the photo push go on)."""
    end = 0.0
    for c in cues:
        if c['k'] in ('zoom', 'drift'):
            continue
        n = len(c.get('rows') or []) or c.get('n', 1)
        if c['k'] == 'type':
            end = max(end, c['at'] + c.get('n', 1) / c['cps'])
        else:
            end = max(end, c['at'] + c.get('stagger', 0) * max(0, n - 1) + c.get('dur', 0.5))
    return end


# ---- encoding ---------------------------------------------------------------------------------------------------------

def _ffmpeg() -> str:
    exe = shutil.which('ffmpeg')
    if not exe:
        raise RuntimeError("ffmpeg is not installed (the lane-render workflow installs it)")
    return exe


def ffmpeg_cmd(duration: float, out_mp4: str, preset: str = 'veryfast') -> list[str]:
    """JPEG frames on stdin (Chrome's screenshots, 30 fps) -> 1080x1920 H.264 high, yuv420p BT.709 limited range,
    closed GOP, faststart, no edit lists, plus a silent stereo AAC track (48 kHz, 128 kbps) as long as the video."""
    return [_ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', str(FPS), '-i', 'pipe:0',
            '-f', 'lavfi', '-t', f'{duration:.3f}', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
            '-map', '0:v:0', '-map', '1:a:0',
            '-vf', f'scale={VW}:{VH}:in_color_matrix=bt601:in_range=full:out_color_matrix=bt709:out_range=tv,'
                   f'format=yuv420p',
            '-c:v', 'libx264', '-preset', preset, '-crf', '19', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
            '-r', str(FPS), '-g', str(2 * FPS), '-maxrate', '14M', '-bufsize', '28M', '-x264-params', 'open-gop=0',
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
            '-t', f'{duration:.3f}', '-movflags', '+faststart', '-use_editlist', '0', out_mp4]


def mp4_boxes(path: str) -> dict:
    """Top-level MP4 boxes in order, and whether an edit list (elst) is present (Instagram wants none)."""
    order, elst = [], False
    with open(path, 'rb') as f:
        data = f.read()
    i = 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], 'big')
        kind = data[i + 4:i + 8].decode('latin-1')
        if size == 1:
            size = int.from_bytes(data[i + 8:i + 16], 'big')
        elif size == 0:
            size = len(data) - i
        order.append(kind)
        if kind == 'moov' and b'elst' in data[i:i + size]:
            elst = True
        if size < 8:
            break
        i += size
    return {'boxes': order, 'elst': elst,
            'faststart': 'moov' in order and 'mdat' in order and order.index('moov') < order.index('mdat')}


def probe_reel(path: str) -> dict:
    """What Instagram's Reels spec cares about, and the problems with this file (empty when it's fine)."""
    info = {'path': path, 'bytes': os.path.getsize(path), **mp4_boxes(path)}
    problems = []
    exe = shutil.which('ffprobe')
    if exe:
        r = subprocess.run([exe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                           capture_output=True, text=True)
        doc = json.loads(r.stdout or '{}')
        v = next((s for s in doc.get('streams', []) if s.get('codec_type') == 'video'), {})
        a = next((s for s in doc.get('streams', []) if s.get('codec_type') == 'audio'), {})
        num, _, den = (v.get('r_frame_rate') or '0/1').partition('/')
        info.update(video_codec=v.get('codec_name'), width=v.get('width'), height=v.get('height'),
                    pix_fmt=v.get('pix_fmt'), fps=round(int(num) / int(den or 1), 3), profile=v.get('profile'),
                    color_space=v.get('color_space'), audio_codec=a.get('codec_name'),
                    sample_rate=int(a.get('sample_rate') or 0), channels=a.get('channels'),
                    duration=round(float((doc.get('format') or {}).get('duration') or 0), 3),
                    bit_rate=int((doc.get('format') or {}).get('bit_rate') or 0))
        if (info['video_codec'], info['width'], info['height'], info['pix_fmt']) != ('h264', VW, VH, 'yuv420p'):
            problems.append(f"video is {info['video_codec']} {info['width']}x{info['height']} {info['pix_fmt']} "
                            f"(needs h264 {VW}x{VH} yuv420p)")
        if info['fps'] != FPS:
            problems.append(f"{info['fps']} fps (needs {FPS})")
        if info['audio_codec'] != 'aac' or not 0 < info['sample_rate'] <= 48000:
            problems.append(f"audio is {info['audio_codec']} {info['sample_rate']} Hz (needs a silent AAC track, "
                            f"<= 48 kHz)")
        if not REEL_MIN_S - 0.05 <= info['duration'] <= REEL_MAX_S + 0.05:
            problems.append(f"{info['duration']} s long (needs {REEL_MIN_S:g}-{REEL_MAX_S:g} s)")
        if info['bit_rate'] > 25_000_000:
            problems.append(f"bitrate {info['bit_rate']} (max 25 Mbps)")
    else:
        info['note'] = 'ffprobe not installed: codec checks skipped'
    if not info['faststart']:
        problems.append("the moov atom is not at the front (faststart)")
    if info['elst']:
        problems.append("the file has an edit list (Instagram wants none)")
    if info['bytes'] > 300 * 1024 * 1024:
        problems.append("over 300 MB")
    info['problems'] = problems
    return info


def video_frame(path: str, n: int) -> Image.Image | None:
    """Frame n decoded from the encoded file (what viewers get), or None if ffmpeg can't."""
    exe = shutil.which('ffmpeg')
    if not exe:
        return None
    r = subprocess.run([exe, '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{int(n)})', '-fps_mode', 'passthrough',
                        '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    im = Image.open(BytesIO(r.stdout))
    im.load()
    return im.convert('RGB')


def _frame_no(t, total: int) -> int:
    return total - 1 if t == 'last' else min(total - 1, round(float(t) * FPS))


def contact_sheet(video: str, out_jpg: str, times=SHEET_TIMES, frames: int | None = None, cols: int = 4,
                  tile_w: int = 360) -> str:
    """Frames of the encoded reel at `times` (seconds, or 'last') side by side, each labelled with its time."""
    total = frames or int(round(probe_reel(video).get('duration', 0) * FPS))
    tile_h = round(tile_w * VH / VW)
    rows = math.ceil(len(times) / cols)
    gap, lab, mg = 18, 44, 28
    sheet = Image.new('RGB', (2 * mg + cols * tile_w + (cols - 1) * gap, 2 * mg + rows * (tile_h + lab + gap) - gap),
                      '#DAD6CE')
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(os.path.join(FONTS, 'inter.ttf'), 24)
    try:
        font.set_variation_by_name('Bold')
    except Exception:  # noqa: BLE001 - a static Inter is fine too
        pass
    for i, t in enumerate(times):
        n = _frame_no(t, total)
        im = video_frame(video, n) or Image.new('RGB', (VW, VH), (255, 0, 255))
        x, y = mg + (i % cols) * (tile_w + gap), mg + (i // cols) * (tile_h + lab + gap)
        sheet.paste(im.resize((tile_w, tile_h), Image.LANCZOS), (x, y + lab))
        d.text((x, y + 8), f"{n / FPS:.2f} s (last frame)" if t == 'last' else f"{float(t):g} s", font=font,
               fill=(14, 14, 16))
    os.makedirs(os.path.dirname(os.path.abspath(out_jpg)), exist_ok=True)
    sheet.save(out_jpg, 'JPEG', quality=90)
    return out_jpg


# ---- render -----------------------------------------------------------------------------------------------------------

def _photo_for_chrome(win: PhotoWindow, path: str) -> None:
    """The cover's photo window at PHOTO_OVERSAMPLE x its shown size (so the push-in never enlarges it in Chrome),
    sharpened like PhotoWindow.at when the source had to be enlarged."""
    w, h = round(VW * PHOTO_OVERSAMPLE), round(win.h * PHOTO_OVERSAMPLE)
    im = win.base.resize((w, h), Image.LANCZOS)
    if win.scale * PHOTO_OVERSAMPLE > SHARPEN_ABOVE:
        im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
    im.save(path, 'JPEG', quality=95, subsampling=0)


def _value_of(text: str) -> float | None:
    spec = count_spec(text)
    if spec:
        return spec['value']
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text or '')
    return float(m.group().replace(',', '')) if m else None


async def _film(post: dict, picked: list[dict], out_dir: str, *, base_dir: str | None, preset: str,
                zone: SafeZone = REEL_SAFE_ZONE) -> dict:
    from playwright.async_api import async_playwright

    _check_hype(post, reel=True)
    cover = _hype_slides(post)[0]
    photo, focal, zoom, photo_h = vertical_source(cover)
    photo = _resolve_photo(photo, base_dir)
    if not os.path.isfile(photo):
        raise FileNotFoundError(f"post {post['slug']}: photo not found: {photo}")
    for s in picked:
        chart_rows(s)                                          # a bad chart fails here, with its reason
    win = PhotoWindow(photo, focal, zoom, photo_h)
    segs = timeline(len(picked))
    total = sum(n for _, n in segs)
    starts, acc = [], 0
    for _, n in segs:
        starts.append(acc / FPS)
        acc += n
    tmp = tempfile.mkdtemp(prefix='cardkit_reel_')
    rows: list[dict] = []
    out: dict = {'segments': segs, 'frames': total}
    try:
        _photo_for_chrome(win, os.path.join(tmp, 'photo.jpg'))
        top_lum = _lum(win.at(1.0), (330, 200, 750, 330))
        page_file = os.path.join(tmp, 'reel.html')
        with open(page_file, 'w', encoding='utf-8') as f:
            f.write(reel_html(post, cover, picked, win.h, top_lum, zone))
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=_chrome(),
                                               args=['--no-sandbox', '--allow-file-access-from-files'])
            page = await browser.new_page(viewport={'width': VW, 'height': VH}, device_scale_factor=1)
            await page.goto('file://' + page_file)
            await page.evaluate('document.fonts.ready')
            await page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            await page.evaluate("document.querySelectorAll('#stage > .scene').forEach("
                                "(s, i) => s.style.visibility = i ? 'hidden' : 'visible')")
            # ---- layout: the same fits as the story card and the detail slides, then the masked lines
            credit_max = zone.right_from if zone.right < VW else zone.bottom
            cinfo = await page.evaluate(VCOVER_JS, dict(VHEAD_FIT, max=zone.head_max, photoH=win.h,
                                                        solidBelow=SOLID_BELOW_TEXT_TOP, fadeLen=zone.fade_len,
                                                        creditY=CREDIT_Y, creditMax=credit_max, safeTop=zone.top,
                                                        safeBottom=zone.bottom, pad=16 + CHROME_RISE, H=VH))
            split = await page.evaluate("window.__split(document.querySelector('#sc0 .head'))")
            cinfo.update(head_split=split)
            infos = [{'kind': 'cover', 'fit': cinfo, 'head_lines': split['lines'], 'kick_chars': len(post['acct']) + 1}]
            for i, s in enumerate(picked, 1):
                root = f'#sc{i}'
                spec = count_spec(s.get('stat')) if (s.get('stat') or '').strip() else None
                above, below = detail_band(zone, bool(credit_line_text(post, s)))
                shown = segs[i][1] + round(PUSH_S * FPS)
                texts = count_texts(spec, STAT_AT, STAT_COUNT_S, shown) if spec else []
                fit = await page.evaluate(REEL_DETAIL_JS, dict(REEL_DETAIL_FIT, root=root, texts=texts,
                                                               statMaxW=zone.col_right - VSIDE, above=above,
                                                               below=below))
                await page.evaluate(BALANCE_JS, f'{root} .slabel, {root} li')
                lab = (await page.evaluate(f"window.__split(document.querySelector('{root} .slabel'))")
                       if s.get('stat_label') else None)
                cr = chart_rows(s)
                infos.append({'kind': 'detail', 'fit': fit, 'stat': bool((s.get('stat') or '').strip()),
                              'stat_spec': spec, 'label_lines': lab['lines'] if lab else 0, 'label_split': lab,
                              'rule': bool((s.get('stat') or s.get('stat_label')) and (s.get('bullets') or cr)),
                              'rows': [{'frac': r['frac'], 'spec': r['spec']} for r in cr[0]] if cr else [],
                              'unit': bool(cr and cr[1]), 'bullets': len(s.get('bullets') or [])})
            end_i = len(picked) + 1
            await page.evaluate(f"window.__split(document.querySelector('#sc{end_i} .endsite'));"
                                f"window.__split(document.querySelector('#sc{end_i} .endhandle'))")
            infos.append({'kind': 'end'})
            # ---- the timeline
            scenes = []
            for i, ((name, n), info) in enumerate(zip(segs, infos)):
                dur = n / FPS
                tail = PUSH_S if i + 1 < len(segs) and _enter(segs[i + 1][0]) == 'push' else 0.0
                cues = _cues(name, info, dur, tail)
                scenes.append({'name': name, 'start': starts[i], 'dur': dur, 'tail': tail, 'enter': _enter(name),
                               'cues': cues, 'settled': _settled(cues)})
            await page.evaluate("tl => window.__setup(tl)", {'scenes': scenes, 'push': PUSH_S, 'back': PUSH_BACK,
                                                              'dim': PUSH_DIM, 'H': VH})
            # ---- checks, each scene settled and at its last visible moment (the drifts at their furthest)
            opts = check_opts(zone)
            safe = [zone.top, zone.bottom]
            for i, (sc, info) in enumerate(zip(scenes, infos)):
                if sc['settled'] > sc['dur'] - 0.25:
                    raise RuntimeError(f"scene {sc['name']}: its reveals end at {sc['settled']:.2f}s, too close to "
                                       f"its {sc['dur']:.2f}s")
                await page.evaluate("([i, t]) => window.__pose(i, t)", [i, sc['settled'] + 0.05])
                row = dict(info['fit']) if info.get('fit') else {}
                row.update(await page.evaluate(VCHECK_JS, opts))
                shot = await page.screenshot(type='png')
                still = Image.open(BytesIO(shot)).convert('RGB')
                await page.evaluate("([i, t]) => window.__pose(i, t)", [i, sc['dur'] + sc['tail'] - 1 / FPS])
                late = await page.evaluate(VCHECK_JS, opts)
                for key in ('ui_zone', 'outside', 'ui_buttons', 'collisions'):
                    row[key] = list(row.get(key) or []) + [x for x in late.get(key) or [] if x not in row.get(key, [])]
                row.update(zone=zone.name, safe=safe, scene=sc['name'], start=round(sc['start'], 3),
                           seconds=round(sc['dur'], 3), settled_at=round(sc['settled'], 2))
                if info['kind'] == 'cover':
                    row.update(page='cover', type='cover', scale=round(win.scale, 3), photo_h=win.h,
                               crop=list(win.box), credit_line=cover.get('photo_credit'))
                    if info['fit']['head_split']['wide'] or info['fit']['head_split']['height_change']:
                        row['overflow'] = True
                    out['cover'] = _save_jpg(still, os.path.join(out_dir, 'reel_cover.jpg'))
                elif info['kind'] == 'detail':
                    s = picked[i - 1]
                    row.update(page=f'detail {i}', type='detail', credit_line=credit_line_text(post, s),
                               max_band=max_empty_band(still, zone.top, zone.bottom),
                               chart=len(info['rows']), counts=bool(info['stat_spec']))
                    row['left_edges'].pop('stat', None)                 # the italic stat is aligned optically
                    if (info['label_split'] or {}).get('wide') or (info['label_split'] or {}).get('height_change'):
                        row['overflow'] = True
                else:
                    row.update(page='end card', type='end')
                rows.append(row)
            # ---- film: one JPEG screenshot per frame, straight into ffmpeg
            video = os.path.join(out_dir, 'reel.mp4')
            proc = subprocess.Popen(ffmpeg_cmd(total / FPS, video, preset), stdin=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            counters: dict = {}
            still_run = longest = 0
            prev = None
            t0 = time.monotonic()
            try:
                for f in range(total):
                    states = await page.evaluate("t => window.setT(t)", f / FPS)
                    data = await page.screenshot(type='jpeg', quality=JPEG_Q)
                    proc.stdin.write(data)
                    digest = hashlib.md5(data).digest()
                    still_run = still_run + 1 if digest == prev else 0
                    longest = max(longest, still_run + 1)
                    prev = digest
                    for cid, text, op in states:
                        c = counters.setdefault(cid, {'id': cid, 'first': None, 'first_frame': None, 'last': None})
                        if op > 0.001:
                            if c['first'] is None:
                                c.update(first=text, first_frame=f)
                            c['last'] = text
                proc.stdin.close()
            except BrokenPipeError:
                pass
            err = proc.stderr.read().decode(errors='replace')
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed: {err.strip()[-500:]}")
            await browser.close()
        out.update(video=video, film_s=round(time.monotonic() - t0, 1), longest_still=longest, rows=rows)
        finals = {}
        for sc in scenes:
            for c in sc['cues']:
                if c['k'] == 'count':
                    finals[c['id']] = c['spec']['final']
                elif c['k'] == 'bars':
                    for n, r in enumerate(c['rows']):
                        if r['spec']:
                            finals[f"{c['id']}.{n}"] = r['spec']['final']
        problems = []
        for cid, final in finals.items():
            c = counters.get(cid) or {'id': cid}
            c['final'] = final
            if c.get('first') is None:
                problems.append(f"counter {cid} ({final}) never shows")
                continue
            if not _value_of(c['first']):
                problems.append(f"counter {cid} first shows {c['first']!r} (never a zero)")
            if c['last'] != final:
                problems.append(f"counter {cid} ends on {c['last']!r}, not {final!r}")
        if longest > STILL_MAX_S * FPS:
            problems.append(f"{longest} identical frames in a row ({longest / FPS:.1f}s; nothing may sit still "
                            f"over {STILL_MAX_S}s)")
        long_scenes = [f"{s['name']} {s['dur']:.1f}s" for s in scenes if s['dur'] > SCENE_MAX_S + 0.01]
        if long_scenes:
            problems.append(f"scenes over {SCENE_MAX_S}s: {', '.join(long_scenes)}")
        out.update(counters=[counters.get(k) or {'id': k, 'final': v} for k, v in finals.items()],
                   motion_problems=problems,
                   scenes=[{k: v for k, v in s.items() if k != 'cues'} for s in scenes])
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _preview_name(t) -> str:
    return 'preview_last.jpg' if t == 'last' else f'preview_{float(t):04.1f}s.jpg'


def render_reel(post: dict, out_dir: str, details: list[int] | None = None, report: list | None = None,
                previews=PREVIEW_TIMES, verbose: bool = True, base_dir: str | None = None,
                preset: str = 'veryfast') -> dict:
    """Render `post` as a silent 9:16 motion reel: <out_dir>/reel.mp4, reel_cover.jpg and (previews) stills at the
    given times in seconds ('last' = the last frame), taken from the encoded file. Returns {'video', 'cover',
    'previews', 'duration', 'frames', 'problems', 'render_s'}; the report rows (one per scene, then the reel's probe
    and motion checks) go to `report`."""
    t0 = time.monotonic()
    os.makedirs(out_dir, exist_ok=True)
    picked = pick_details(post, details)
    timeline(len(picked))                                      # no detail slide: say so before Chrome starts
    film = asyncio.run(_film(post, picked, out_dir, base_dir=base_dir, preset=preset))
    rows = film['rows']
    for row in rows:
        row['problems'] = vertical_problems([row])
        if verbose:
            extra = f" head {row['size']}px x{row['lines']}" if row['type'] == 'cover' else ''
            flag = f"  PROBLEMS: {'; '.join(row['problems'])}" if row['problems'] else ''
            print(f"[cardkit:reel] {post['slug']} {row['page']}:{extra}{flag}", file=sys.stderr)
    video, total = film['video'], film['frames']
    shots = []
    for t in previews or ():
        f = _frame_no(t, total)
        shots.append(_save_jpg(video_frame(video, f) or Image.new('RGB', (VW, VH)),
                               os.path.join(out_dir, _preview_name(t))))
    probe = probe_reel(video)
    render_s = round(time.monotonic() - t0, 1)
    reel_row = {'type': 'reel', 'page': 'reel', 'frames': total, 'segments': film['segments'],
                'scenes': film['scenes'], 'details': len(picked), 'counters': film['counters'],
                'longest_still_frames': film['longest_still'], 'film_s': film['film_s'], 'render_s': render_s,
                **probe, 'problems': probe['problems'] + film['motion_problems']}
    rows.append(reel_row)
    if report is not None:
        report.extend(rows)
    problems = vertical_problems(rows)
    if verbose:
        print(f"[cardkit:reel] {post['slug']}: {total / FPS:.1f}s, {probe['bytes'] / 1e6:.1f} MB, rendered in "
              f"{render_s}s" + (f"  PROBLEMS: {'; '.join(problems)}" if problems else ''), file=sys.stderr)
    return {'video': video, 'cover': film['cover'], 'previews': shots, 'duration': total / FPS, 'frames': total,
            'problems': problems, 'render_s': render_s}


# ---- CLI ---------------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog='python3 -m cardkit.reel', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('post')
    ap.add_argument('out_dir')
    ap.add_argument('--details', help='which detail slides, 1-based, e.g. 1,2 (default: the first two)')
    ap.add_argument('--previews', action='store_true', help='also save stills at 0.5 s, 4 s, 7 s and the last frame')
    ap.add_argument('--sheet', help='also save a contact sheet of 8 labelled frames (0.3-9 s and the last) here')
    a = ap.parse_args(argv)
    details = [int(x) for x in a.details.split(',')] if a.details else None
    res = render_reel(load_post(a.post), a.out_dir, details=details, report=[],
                      base_dir=os.path.dirname(os.path.abspath(a.post)), previews=PREVIEW_TIMES if a.previews else ())
    if a.sheet:
        res['sheet'] = contact_sheet(res['video'], a.sheet, frames=res['frames'])
    print(json.dumps({**res, 'ok': not res['problems']}, indent=1))
    return 1 if res['problems'] else 0


if __name__ == '__main__':
    sys.exit(main())
