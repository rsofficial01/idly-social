"""10 Nov 2026: idly's Diwali 2026 review carousels for @idlynerd (consolidated published reviews).

Data: /home/claude/reviews_diwali/research_v4.json (v4: ratings seen on 10 Nov on outlet pages or in thereviewmonk /
Rotten Tomatoes critics lists, all opened with WebFetch; pre-release ratings left out; nothing read with curl, caches or
mirrors). Every number on the cards comes from there. idly consolidates published reviews and did not watch the films.
The roundup is built only when 4 or more films qualify.
Renders with cardkit's hype template via render_cards(..., template='hype'). The four slide kinds used here
('vcover', 'verdict', 'scores', 'rank', plus 'picks') are registered at runtime below; cardkit/render.py itself
is not modified. They share the hype template's fonts, colours, logo and footer.

    python3 cardkit/reviews_10nov.py            # render all posts into posts/2026-11-10/review_*/
"""
from __future__ import annotations

import html
import json
import os
import sys

from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = HERE[:HERE.rindex(os.sep + 'cardkit')]   # works from cardkit/ or cardkit/_work/
sys.path.insert(0, REPO)
from cardkit import render as R  # noqa: E402

# research_v4 is copied into the repo next to the roundup so the build is reproducible from a checkout.
RESEARCH = os.environ.get('REVIEWS_RESEARCH') or os.path.join(REPO, 'posts', '2026-11-10', 'review_roundup', 'research_v4.json')

OUT = os.path.join(REPO, 'posts', '2026-11-10')
PNG = '/home/claude/reviews_diwali/png'
TMP = '/home/claude/reviews_diwali/tmp'
DATE = '10 Nov 2026'
ACCT = 'idlynerd'

# v5 covers are type only: no photo (the v4 projector photo was cut at the edge and sat behind the title and score).
# The cover graphic is a strip of the critics' own ratings, drawn by idly. Credits say so.
COVER_CREDIT = 'Design: idly. Type and chart only, no photo.'
CAPTION_CREDIT = 'Image: idly design (type and a chart of the ratings; no photo used).'
SRC_LINE = 'Ratings: outlet pages and the thereviewmonk / Rotten Tomatoes critics lists, read 10 Nov 2026.'

e = lambda s: html.escape(str(s or ''), quote=False)  # noqa: E731


def fmt(x: float) -> str:
    return f'{x:.1f}'


def fmt_pub(x) -> str:
    return (f'{x:g}')


# ---------------------------------------------------------------------------------------------
# extra CSS shared by the custom slides (on top of cardkit's HYPE_CSS)
# ---------------------------------------------------------------------------------------------
X_CSS = """
.x{position:absolute;inset:0;background:%(bg)s;color:#fff;font-family:Inter}
.x .bgph{position:absolute;inset:0;width:1080px;height:1350px;display:block}
.x .shade{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(14,14,16,.62) 0%%,rgba(14,14,16,.50) 34%%,
          rgba(14,14,16,.70) 62%%,rgba(14,14,16,.93) 86%%,rgba(14,14,16,.97) 100%%)}
.x .toplogo{position:absolute;top:50px;left:50%%;transform:translateX(-50%%);height:60px;width:auto;display:block}
.x .credit{position:absolute;right:20px;bottom:60px;writing-mode:vertical-rl;transform:rotate(180deg);
          font:500 15px/1 Inter;letter-spacing:.2px;color:rgba(255,255,255,.6);white-space:nowrap}
.x .cfoot{position:absolute;left:72px;right:72px;bottom:44px;display:flex;justify-content:space-between;
          font:600 24px/1 Inter;color:rgba(255,255,255,.7)}
.x .body{position:absolute;left:72px;right:72px;top:170px;bottom:120px;display:flex;flex-direction:column;
         justify-content:space-between;overflow:hidden}
.kicker{font:800 24px/1 Inter;letter-spacing:3px;text-transform:uppercase;color:%(ember)s}
.kicker span{color:rgba(255,255,255,.62)}
.ttl{font-weight:800;font-size:104px;line-height:.98;letter-spacing:-.035em;margin-top:26px;text-wrap:balance;max-width:936px}
.meta{font:600 32px/1.25 Inter;color:rgba(255,255,255,.74);margin-top:24px}
.score{font-family:Playfair;font-style:italic;font-weight:900;color:%(ember)s;line-height:.8;letter-spacing:-.02em;
       display:flex;align-items:baseline;white-space:nowrap}
.score .big{font-size:330px}
.score .of{font-size:118px;color:rgba(255,255,255,.88);margin-left:10px}
.hook{font:800 56px/1.08 Inter;letter-spacing:-.025em;margin-top:58px;text-wrap:balance;max-width:936px}
.basis{font:500 25px/1.3 Inter;color:rgba(255,255,255,.62);margin-top:22px;text-wrap:balance;max-width:936px}

/* detail-style pages */
.d2 .body{position:absolute;left:72px;right:72px;top:92px;bottom:200px;display:flex;flex-direction:column;justify-content:flex-start;overflow:hidden}
.d2 .src{position:absolute;left:72px;right:72px;bottom:150px;font:500 21px/1.3 Inter;color:rgba(255,255,255,.5)}
.d2 .sub{font:700 34px/1.2 Inter;margin-top:16px;color:#fff}
.d2 .sub b{font-family:Playfair;font-style:italic;font-weight:900;color:%(ember)s}
.sect{font-family:Playfair;font-style:italic;font-weight:900;font-size:76px;line-height:1;margin-top:26px;letter-spacing:-.01em}
.sect.hi{color:%(ember)s}
.sect.lo{color:#fff}
.pt{position:relative;padding-left:44px;margin-top:15px}
.pt .t{font:600 38px/1.18 Inter;letter-spacing:-.012em;text-wrap:pretty}
.pt .n{font:500 23px/1.25 Inter;color:rgba(255,255,255,.58);margin-top:5px}
.pt:before{content:'';position:absolute;left:0;top:15px;width:18px;height:18px;border-radius:3px}
.hi + .pt:before,.pt.h:before{background:%(ember)s}
.pt.l:before{background:transparent;border:3px solid rgba(255,255,255,.85);width:12px;height:12px}
.note{font:500 27px/1.3 Inter;color:rgba(255,255,255,.6);margin-top:18px}

.rows{margin-top:30px}
.row{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1.5px solid rgba(255,255,255,.12);
     padding:%(rowpad)s 0}
.row .o{font:600 %(rowfs)s/1.15 Inter;letter-spacing:-.01em}
.row .o i{font-style:normal;color:%(ember)s}
.row .v{display:flex;align-items:baseline;gap:22px;white-space:nowrap}
.row .p{font:500 25px/1 Inter;color:rgba(255,255,255,.5)}
.row .nv{font:800 %(rowfs)s/1 Inter;color:#fff;min-width:66px;text-align:right;font-variant-numeric:tabular-nums}
.tot{display:flex;align-items:baseline;justify-content:space-between;margin-top:22px}
.tot .o{font:800 34px/1 Inter;align-self:flex-end;padding-bottom:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;column-gap:56px;margin-top:22px}
.grid2 .row{padding:%(rowpad)s 0}
.grid2 .row .o{font:600 %(rowfs)s/1.15 Inter;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.split{margin-top:24px;border-left:4px solid %(ember)s;padding-left:24px}
.split .k{font:800 22px/1 Inter;letter-spacing:3px;text-transform:uppercase;color:%(ember)s}
.split .w{font:600 31px/1.22 Inter;margin-top:10px;text-wrap:pretty}
.split .n{font:500 23px/1.25 Inter;color:rgba(255,255,255,.58);margin-top:6px}
.tot .nv{font-family:Playfair;font-style:italic;font-weight:900;font-size:86px;line-height:.9;color:%(ember)s}
.who{margin-top:26px;border-left:4px solid %(ember)s;padding-left:24px}
.ws{display:grid;grid-template-columns:1fr 1fr;column-gap:40px;margin-top:24px}
.ws .who{margin-top:0}
.ws .who .w{font:600 28px/1.22 Inter}
.d2 .srcline{white-space:normal;overflow:visible;text-overflow:clip;font:500 21px/1.3 Inter;color:rgba(255,255,255,.5)}
.who .k{font:800 22px/1 Inter;letter-spacing:3px;text-transform:uppercase;color:%(ember)s}
.who .w{font:600 34px/1.22 Inter;margin-top:12px;text-wrap:pretty}
.foot2{position:absolute;left:72px;right:72px;bottom:56px}
.foot2 .line{height:2px;background:rgba(255,255,255,.18);margin-bottom:24px}
.foot2 .r{display:flex;align-items:center}
.foot2 img{height:58px;width:auto;display:block}
.foot2 .date{font:600 24px/1 Inter;color:rgba(255,255,255,.6);margin-left:22px;padding-left:22px;
             border-left:2px solid rgba(255,255,255,.6);height:30px;display:flex;align-items:center}
.foot2 .site{margin-left:auto;font:800 27px/1 Inter;letter-spacing:-.5px}

/* roundup ranking */
.rk{display:flex;align-items:center;border-bottom:1.5px solid rgba(255,255,255,.12);padding:9px 0}
.rk .no{font-family:Playfair;font-style:italic;font-weight:900;font-size:50px;width:70px;color:rgba(255,255,255,.45)}
.rk .mid{flex:1;min-width:0}
.rk .tt{font:800 34px/1.08 Inter;letter-spacing:-.02em}
.rk .ln{font:500 24px/1.25 Inter;color:rgba(255,255,255,.62);margin-top:6px}
.rk .bar{height:6px;background:rgba(255,255,255,.12);border-radius:3px;margin-top:10px;width:100%%}
.rk .bar i{display:block;height:6px;border-radius:3px;background:%(ember)s}
.rk .sc{font-family:Playfair;font-style:italic;font-weight:900;font-size:66px;line-height:1;color:%(ember)s;
        margin-left:26px;min-width:150px;text-align:right}
.pick{border-bottom:1.5px solid rgba(255,255,255,.12);padding:17px 0}
.pick .tt{font:800 35px/1.1 Inter;letter-spacing:-.015em}
.pick .tt b{font-family:Playfair;font-style:italic;font-weight:900;color:%(ember)s;margin-left:10px}
.pick .w{font:500 28px/1.25 Inter;color:rgba(255,255,255,.78);margin-top:6px;text-wrap:pretty}
"""


def css(rowfs='34px', rowpad='11px'):
    base = R._hype_css()
    return base + X_CSS % dict(bg=R.HYPE_BG, ember=R.EMBER, rowfs=rowfs, rowpad=rowpad)


def logo_white():
    return os.path.join(R.LOGOS, f"{R.LOGO_FILE[ACCT]}_white.png")


def doc(body: str, extra_css: str = '') -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{extra_css}</style></head>"
            f"<body><div class='s x'>{body}</div></body></html>")


def foot2(post):
    return (f"<div class='foot2'><div class='line'></div><div class='r'><img src='file://{logo_white()}'>"
            f"<div class='date'>{e(post['date'])}</div><div class='site'>idly.news</div></div></div>")


def strip_html(points, mean, label, legend):
    """A 0-10 strip: one dot per rating (equal ratings stack upwards), a marker at the mean."""
    W_, D, STEP, BASE = 936, 20, 23, 40
    stacks, dots, placed = {}, [], []
    for v in sorted(points):
        x = v / 10 * W_
        n = sum(1 for px in placed if abs(px - x) < D + 2)   # equal or overlapping values stack upwards
        placed.append(x)
        stacks[len(placed)] = n + 1
        dots.append(f"<i class='dot' style='left:{x - D / 2:.1f}px;bottom:{BASE + n * STEP}px'></i>")
    top = BASE + max(stacks.values()) * STEP          # top of the tallest stack
    mx = mean / 10 * W_
    ticks = ''.join(f"<span class='tk' style='left:{t / 10 * W_:.1f}px;"
                    f"transform:translateX({'0' if t == 0 else '-100%' if t == 10 else '-50%'})'>{t}</span>"
                    for t in (0, 2, 4, 6, 8, 10))
    return (f"<div class='strip' style='height:{top + 40}px'>"
            f"<div class='axis'></div>{ticks}{''.join(dots)}"
            f"<div class='mean' style='left:{mx:.1f}px;height:{top - 32 + 6}px'></div>"
            f"<div class='ml' style='left:{mx:.1f}px;bottom:{top + 10}px'>{e(label)}</div></div>"
            f"<div class='legend'>{e(legend)}</div>")


COVER_CSS = """
.x .glow{position:absolute;inset:0;background:radial-gradient(900px 700px at 100%% 0%%,rgba(240,96,58,.20),rgba(240,96,58,0) 70%%),
        radial-gradient(700px 600px at 0%% 100%%,rgba(240,96,58,.10),rgba(240,96,58,0) 70%%)}
.strip{position:relative;width:936px;margin-top:28px}
.strip .axis{position:absolute;left:0;right:0;bottom:32px;height:3px;background:rgba(255,255,255,.35)}
.strip .tk{position:absolute;bottom:0;font:600 20px/1 Inter;color:rgba(255,255,255,.5)}
.strip .dot{position:absolute;width:20px;height:20px;border-radius:50%%;background:rgba(255,255,255,.88)}
.strip .mean{position:absolute;bottom:32px;width:4px;margin-left:-2px;background:%(ember)s}
.strip .ml{position:absolute;transform:translateX(-50%%);font:800 22px/1 Inter;letter-spacing:1px;color:%(ember)s;
           white-space:nowrap;text-transform:uppercase}
.legend{font:500 21px/1.3 Inter;color:rgba(255,255,255,.55);margin-top:10px}
.x .strip ~ .hook{margin-top:40px}
"""


def html_vcover(post, s):
    ttl_size = s.get('title_px', 104)
    body = f"""
<div class='glow'></div>
<img class='toplogo' src='file://{logo_white()}'>
<div class='credit'>{e(COVER_CREDIT)}</div>
<div class='body'>
  <div>
    <div class='kicker'>{s['kicker']}</div>
    <div class='ttl' style='font-size:{ttl_size}px'>{e(s['title'])}</div>
    <div class='meta'>{e(s['meta'])}</div>
  </div>
  <div>
    {s.get('score_html', '')}
    {s.get('strip', '')}
    <div class='hook'>{e(s['hook'])}</div>
    <div class='basis'>{e(s.get('basis', ''))}</div>
  </div>
</div>
<div class='cfoot'><span>{e(post['date'])}</span><span>idly.news</span></div>"""
    return doc(body, css() + COVER_CSS % dict(ember=R.EMBER))


def names(outlets, k=3):
    """'DT Next, Gulte, Outlook +7' for the count line under a point."""
    head = ', '.join(outlets[:k])
    return head + (f' +{len(outlets) - k}' if len(outlets) > k else '')


def html_verdict(post, s):
    pts = ["<div class='sect hi' style='margin-top:26px'>Highs</div>"]
    for h in s['highs']:
        n = f"{len(h['outlets'])} reviews: {names(h['outlets'])}"
        if h.get('dissent'):
            n += f" · {len(h['dissent'])} disagree{'s' if len(h['dissent']) == 1 else ''}"
        pts.append(f"<div class='pt h'><div class='t'>{e(h['point'])}</div><div class='n'>{e(n)}</div></div>")
    if s.get('highs_note'):
        pts.append(f"<div class='note' style='font-size:24px;margin-top:12px'>{e(s['highs_note'])}</div>")
    pts.append("<div class='sect lo'>Lows</div>")
    for h in s['lows']:
        n = f"{len(h['outlets'])} reviews: {names(h['outlets'])}"
        if h.get('dissent'):
            n += f" · {len(h['dissent'])} disagree{'s' if len(h['dissent']) == 1 else ''}"
        pts.append(f"<div class='pt l'><div class='t'>{e(h['point'])}</div><div class='n'>{e(n)}</div></div>")
    split = ''
    if s.get('split'):
        sp = s['split']
        split = (f"<div class='split'><div class='k'>Where they split</div><div class='w'>{e(sp['line'])}</div>"
                 f"<div class='n'>{e('For: ' + ', '.join(sp['pro']) + '. Against: ' + ', '.join(sp['con']) + '.')}</div></div>")
    body = f"""
<div class='d2'><div class='body'>
  <div class='kicker'>What critics agree on</div>
  <div class='sub'>{e(s['title'])} · <b>{e(s['score'])}/10</b></div>
  {''.join(pts)}
  {split}
</div><div class='src srcline'>{e(SRC_LINE)} Points paraphrased by idly.</div>{foot2(post)}</div>"""
    return doc(body, css())


def html_scores(post, s):
    n = len(s['rows'])
    two = n > 12
    rows = []
    for r in s['rows']:
        if two:
            rows.append(f"<div class='row'><div class='o'>{e(r['outlet'])}</div><div class='v'><span class='nv'>{fmt(r['rating_10'])}</span></div></div>")
        else:
            rows.append(f"<div class='row'><div class='o'>{e(r['outlet'])}</div><div class='v'>"
                        f"<span class='p'>{e(r['shown'])}</span><span class='nv'>{fmt(r['rating_10'])}</span></div></div>")
    notes = [x for x in (s.get('extra'), s.get('unrated')) if x]
    note_html = ''.join(f"<div class='note' style='font-size:24px;margin-top:10px;color:rgba(255,255,255,.66)'>{e(x)}</div>" for x in notes)
    grid = f"<div class='grid2'>{''.join(rows)}</div>" if two else f"<div class='rows'>{''.join(rows)}</div>"
    body = f"""
<div class='d2'><div class='body'>
  <div class='kicker'>Every score <span>· out of 10</span></div>
  <div class='sub'>{e(s['title'])}</div>
  {grid}
  <div class='tot'><div class='o'>Consolidated ({n} ratings)</div><div class='nv'>{e(s['score'])}/10</div></div>
  {note_html}
  <div class='ws'><div class='who'><div class='k'>Watch it if</div><div class='w'>{e(s['watch'])}</div></div>
    <div class='who'><div class='k'>Skip it if</div><div class='w'>{e(s['skip'])}</div></div></div>
</div><div class='src srcline'>{e(SRC_LINE)}</div>{foot2(post)}</div>"""
    if two:
        fs, pad = ('31px', '12px') if n <= 16 else ('28px', '7px')
    else:
        fs, pad = ('31px', '8px') if n >= 10 else (('32px', '9px') if n >= 6 else ('40px', '24px'))
    return doc(body, css(fs, pad))


def html_rank(post, s):
    rows = []
    for i, f in enumerate(s['films'], 1):
        w = round(f['score'] * 10, 1)
        rows.append(f"<div class='rk'><div class='no'>{i}</div><div class='mid'><div class='tt'>{e(f['title'])}</div>"
                    f"<div class='ln'>{e(f['line'])}</div><div class='bar'><i style='width:{w}%'></i></div></div>"
                    f"<div class='sc'>{fmt(f['score'])}</div></div>")
    body = f"""
<div class='d2'><div class='body' style='top:90px'>
  <div class='kicker'>Diwali 2026 <span>· consolidated critic scores, out of 10</span></div>
  <div class='rows' style='margin-top:18px'>{''.join(rows)}</div>
  <div class='note' style='font-size:23px'>{e(s['method'])}</div>
</div><div class='src srcline'>{e(SRC_LINE)}</div>{foot2(post)}</div>"""
    return doc(body, css())


def html_picks(post, s):
    rows = []
    for f in s['films']:
        rows.append(f"<div class='pick'><div class='tt'>{e(f['title'])}<b>{fmt(f['score'])}</b></div><div class='w'>{e(f['who'])}</div></div>")
    body = f"""
<div class='d2'><div class='body' style='top:90px'>
  <div class='kicker'>Who should watch what</div>
  <div class='rows' style='margin-top:12px'>{''.join(rows)}</div>
  <div class='note' style='font-size:23px'>Lines paraphrase the critics' consensus. idly did not watch the films.</div>
</div><div class='src srcline'>{e(SRC_LINE)}</div>{foot2(post)}</div>"""
    return doc(body, css())


BUILDERS = {'vcover': html_vcover, 'verdict': html_verdict, 'scores': html_scores, 'rank': html_rank,
            'picks': html_picks}

# --- register the extra slide kinds with cardkit's hype renderer (runtime only) ---------------
_orig_detail = R.hype_detail_html
_orig_check = R._check_hype


def _detail_dispatch(post, slide):
    kind = slide.get('type')
    return BUILDERS[kind](post, slide) if kind in BUILDERS else _orig_detail(post, slide)


def _check(post):
    custom = [s for s in post.get('slides', []) if s.get('type') in BUILDERS]
    if not custom:
        return _orig_check(post)
    for k in ('acct', 'slug', 'date'):
        if not post.get(k):
            raise ValueError(f"post {post.get('slug')}: missing {k}")
    if not 1 <= len(post['slides']) <= 10:
        raise ValueError('needs 1-10 slides')


R.hype_detail_html = _detail_dispatch
R._check_hype = _check


# ---------------------------------------------------------------------------------------------
# posts
# ---------------------------------------------------------------------------------------------
def score_html(score: float, px: int = 230) -> str:
    return (f"<div class='score'><span class='big' style='font-size:{px}px'>{fmt(score)}</span>"
            f"<span class='of' style='font-size:96px'>/10</span></div>")


def shown(r) -> str:
    """The rating as the outlet published it (outlet page or Rotten Tomatoes). thereviewmonk lists every rating on
    its own /10 scale, which may not be the outlet's scale, so those rows show only the /10 figure."""
    return '' if r['method'] == 'aggregator:thereviewmonk' else f"{fmt_pub(r['rating'])}/{r['scale']}"


def row_name(r, f) -> str:
    """The outlet, plus the critic's surname when the outlet has two critics on this film (Rediff on Ramayana)."""
    two = sum(1 for x in f['rated'] + f['unrated'] if x['outlet'] == r['outlet']) > 1
    return f"{r['outlet']} ({r['critic'].split()[-1]})" if two else r['outlet']


def rel_date(iso: str) -> str:
    import datetime as _dt
    d = _dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b')}"


# ---------------------------------------------------------------------------------------------
# v5 editorial decisions (10 Nov). The research file is unchanged; everything that differs is here.
# ---------------------------------------------------------------------------------------------
# Pyre: its 4th rating (Indian Express) has no confirmed day, and could not be confirmed on 10 Nov (the IE page is
# not reachable from this session; searches surface no dated copy). Two outlets also announced a 23 Oct India
# release. With 3 confirmed ratings it fails the 4-rating rule, so it is out of the roundup and gets no post.
NOT_QUALIFIED = {'pyre'}
# Films that qualify for the roundup but whose own carousel does not reach 12/14 on an honest score: no post.
NO_POST = {'summer-holidays', 'aadarsha-kutumbam', 'nakhrewaalii', 'cult'}

EDIT = {
    'ramayana-part-1': dict(
        cover_title='Ramayana: Part 1', meta='Hindi · in theatres from 5 Nov',
        hook="Critics agree on Ravana. Rama splits them.",
        split_con=['Rediff (Sreeju Sudhakaran)', 'Outlook'],
        watch="You want big-screen spectacle and Yash's Ravana (10 reviews single him out).",
        skip="You want the epic's emotion: 9 critics say the spectacle outweighs it.",
        verdict=("Critics agree that Yash's Ravana and the visuals are the reasons to go; nine critics say the "
                 "spectacle outweighs the emotion. They split on Ranbir's Rama."),
        quote="Rediff's Sukanya Verma, in an unrated review: \"all scale, no soul\".",
        q="Seen it already: did Ranbir's Rama work for you?",
        tags='#Ramayana #Yash #RanbirKapoor #MovieReview #idlynerd'),
    'scene': dict(
        cover_title="Suriya's Scene", meta='Tamil · in theatres from 6 Nov',
        hook="8 critics say Suriya is having fun. The jokes split them.",
        watch="You like dark comedy and Suriya sending up his own hero image (8 reviews).",
        skip="You want a tense investigation: The Week and Deccan Chronicle find it short on tension.",
        verdict=("Critics enjoy Suriya sending up his own image and Jithu Madhavan's fresh take on a cop thriller. "
                 "Five call it great fun; two say the humour wears thin."),
        quote="Hindustan Times's Neeshita Nyayapati: \"Suriya truly has fun poking fun at himself\".",
        q="Would you rather see Suriya send up his hero image like this, or play the hero straight?",
        tags='#Scene #Suriya #JithuMadhavan #TamilCinema #MovieReview'),
    'mookuthi-amman-2': dict(
        cover_title='Mookuthi Amman 2', meta='Nayanthara · Tamil · in theatres from 6 Nov',
        hook="9 critics. Not one rated it above 5/10.",
        watch="You are a committed Nayanthara or Amman-film fan (3 reviews say she holds the screen).",
        skip="Effects matter to you: 6 reviews call the VFX cheap-looking.",
        verdict=("The lowest-rated of the seven Diwali releases idly ranked. Critics say Nayanthara holds the screen, "
                 "but cheap-looking VFX, a weak, overstuffed screenplay and comedy that misfires sink it. "
                 "No critic rated it above 5/10."),
        quote="NDTV's Latha Srinivasan: \"desperately needed a storytelling miracle\".",
        q="Would cheap-looking VFX keep you away from a Nayanthara film in theatres?",
        tags='#MookuthiAmman2 #Nayanthara #TamilCinema #MovieReview'),
}

SCORES = {
    'review_roundup': dict(hook=2, read=2, send=2, keep=2, reply=1, original=2, alone=2, notes=(
        "Self 13/14. hook 2: retitled to a true claim ('7 Diwali Releases, Ranked by Critics'); range 7.1 to 3.3 and "
        "'Two clear 6/10. Five don't.' on a clean type-only cover with a dot strip of the 7 scores. read 2: cover, ranking, "
        "who-should-watch. send 2: one card answers 'what do we see this weekend' across Hindi, Tamil and Telugu. "
        "keep 2: a reference list for the season. reply 1: one specific question (Ramayana vs Scene), but a pick-one "
        "prompt draws short answers. original 2: 62 ratings consolidated under one stated method. alone 2: method, "
        "rounding and 'idly did not watch' on the cards and in the caption. Pyre dropped (Indian Express date unconfirmed).")),
    'review_ramayana-part-1': dict(hook=2, read=2, send=1, keep=1, reply=2, original=2, alone=2, notes=(
        "Self 12/14. hook 2: the season's biggest film, 'Critics agree on Ravana. Rama splits them.', type-only cover "
        "with the 21 ratings as a dot strip. read 2: score, highs/lows with counts, every rating. send 1: useful before "
        "booking, five days after release. keep 1: the watch-if/skip-if box and all 21 ratings help, but it is still a "
        "one-time decision. reply 2: one contested, specific question. original 2: 29 reviews consolidated with counted "
        "agreement and named dissent. alone 2. Fixed: 'nine critics' (9 of 29), '8 unrated reviews (7 outlets)', both "
        "Rediff critics named, thereviewmonk /10 figures marked as its conversions.")),
    'review_scene': dict(hook=2, read=2, send=1, keep=1, reply=2, original=2, alone=2, notes=(
        "Self 12/14. hook 2 (was 1): 'Suriya's Scene' puts the star in the title; '8 critics say Suriya is having fun. "
        "The jokes split them.' teases the split with counts; the dot strip shows the lone 4.0. read 2. send 1: mainly "
        "Suriya fans. keep 1: the watch-if/skip-if box is a real decision aid but a one-time one. reply 2 (was 1): the "
        "question is answerable by any Suriya fan, not only those who have seen it. original 2. alone 2. Fixed: 'Five "
        "call it great fun; two say the humour wears thin' replaces 'Most find it great fun'.")),
    'review_mookuthi-amman-2': dict(hook=2, read=2, send=1, keep=1, reply=2, original=2, alone=2, notes=(
        "Self 12/14. hook 2: '9 critics. Not one rated it above 5/10.' (true: the highest is DT Next 5/10). read 2. "
        "send 1: a 'critics say skip' post for Nayanthara fans; forwardable but niche. keep 1: watch-if/skip-if, still a "
        "one-time decision. reply 2: a specific question anyone can answer (does bad VFX keep you away from a star's "
        "film). original 2: 11 reviews consolidated with counts. alone 2. Borderline: needs every check to hold.")),
}


def film_post(f):
    ed = EDIT[f['slug']]
    n = f['n_rated']
    title = ed['cover_title']
    tpx = 112 if len(title) <= 16 else 92
    pts = [r['rating_10'] for r in f['rated']]
    cover = dict(type='vcover', kicker="The verdict <span>· Diwali 2026</span>", title=title, meta=ed['meta'],
                 score_html=score_html(f['score']), title_px=tpx, hook=ed['hook'],
                 strip=strip_html(pts, f['score'], f"avg {fmt(f['score'])}",
                                  f"Each dot is one critic's rating, out of 10 ({n} ratings)."),
                 basis=("The average of published critic ratings, converted to /10. "
                        "idly did not watch the film; this post consolidates reviews."))
    split = dict(f['split'], con=ed.get('split_con', f['split']['con'])) if f.get('split') else None
    verdict = dict(type='verdict', title=f['short'], score=fmt(f['score']), highs=f['highs'], lows=f['lows'],
                   highs_note=f.get('highs_note'), split=split)
    rows = [dict(r, shown=shown(r), outlet=row_name(r, f)) for r in sorted(f['rated'], key=lambda r: -r['rating_10'])]
    unr = f['unrated']
    k = len({x['outlet'] for x in unr})
    unrated_line = ''
    if unr:
        unrated_line = (f"Highs and lows also draw on {len(unr)} unrated review{'s' if len(unr) > 1 else ''}"
                        + (f" ({k} outlets)" if k != len(unr) else '') + ', named in the caption.')
    exact = abs(f['mean_exact'] - f['score']) < 1e-9
    trm = any(r['method'] == 'aggregator:thereviewmonk' for r in f['rated'])
    extra = (f"Mean {f['mean_exact']:g}{' exactly' if exact else ', rounded half-up'}. Reviews published before release "
             f"are left out." + (" Ratings from thereviewmonk are its /10 conversions." if trm else '')
             + " idly did not watch the film.")
    scores = dict(type='scores', title=f['short'], score=fmt(f['score']), rows=rows, unrated=unrated_line,
                  watch=ed['watch'], skip=ed['skip'], extra=extra)
    return dict(acct=ACCT, slug=f"review_{f['slug']}", date=DATE, slides=[cover, verdict, scores])


def roundup_post(films):
    total_rated = sum(f['n_rated'] for f in films)
    above6 = sum(1 for f in films if f['score'] > 6)
    rest = len(films) - above6
    word = {2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six'}
    cover = dict(type='vcover', kicker="Diwali 2026 <span>· the verdicts</span>",
                 title=f'{len(films)} Diwali Releases, Ranked by Critics',
                 meta=f"Indian films in theatres 30 Oct to 9 Nov · {total_rated} critic ratings", title_px=92,
                 score_html=(f"<div class='score'><span class='big' style='font-size:230px'>{fmt(films[0]['score'])}</span>"
                             f"<span class='of' style='font-size:76px'>to</span><span class='big' style='font-size:230px;margin-left:24px'>{fmt(films[-1]['score'])}</span></div>"),
                 strip=strip_html([f['score'] for f in films], 6.0, '6/10',
                                  f"Each dot is one film's critic average, out of 10."),
                 hook=f"{word[above6]} clear 6/10. {word[rest]} don't.",
                 basis=('Films with 4+ ratings from established outlets, published on or after release. '
                        'idly did not watch the films.'))
    rank = dict(type='rank', films=[dict(title=f['short'], score=f['score'], line=f"{f['round_line']} · {f['n_rated']} ratings")
                                    for f in films],
                method=('Indian films released in theatres 30 Oct to 9 Nov with at least four ratings from established outlets, '
                        'published on or after release. Score: their average, converted to /10.'))
    picks = dict(type='picks', films=[dict(title=f['short'], score=f['score'], who=f['short_who']) for f in films])
    return dict(acct=ACCT, slug='review_roundup', date=DATE, slides=[cover, rank, picks])


# ---------------------------------------------------------------------------------------------
# caption.txt, alt.txt, score.json
# ---------------------------------------------------------------------------------------------
def oxford(xs):
    xs = list(dict.fromkeys(xs))
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]


def named(r, f):
    """'Rediff's Sreeju Sudhakaran' when the outlet has two critics on this film, else the outlet."""
    two = sum(1 for x in f['rated'] + f['unrated'] if x['outlet'] == r['outlet']) > 1
    return f"{r['outlet']}'s {r['critic']}" if two else r['outlet']


def rating_txt(r):
    if r['method'] == 'aggregator:thereviewmonk':
        return f"{fmt(r['rating_10'])}/10 (thereviewmonk's conversion)"
    return f"{fmt_pub(r['rating'])}/{r['scale']}"


def film_caption(f):
    ed = EDIT[f['slug']]
    rated = sorted(f['rated'], key=lambda r: -r['rating_10'])
    hi, lo = rated[0]['rating_10'], rated[-1]['rating_10']

    def ends(rs):
        return '; '.join(f"{named(r, f)} {rating_txt(r)}" for r in rs)
    exact = abs(f['mean_exact'] - f['score']) < 1e-9
    mean_txt = f"mean exactly {f['mean_exact']:g}" if exact else f"mean {f['mean_exact']:g}, rounded half-up to one decimal"
    two = lambda o: sum(1 for x in f['rated'] + f['unrated'] if x['outlet'] == o) > 1  # noqa: E731
    unr = [u['outlet'] + (f" ({u['critic']})" if two(u['outlet']) else '') for u in f['unrated']]
    unr = list(dict.fromkeys(unr))
    rel = rel_date(f['release'])
    lines = [
        f"{f['title']}, the critics' verdict: {fmt(f['score'])}/10. {ed['verdict']} {ed['quote']}",
        '',
        f"Where: in theatres since {rel}.",
        f"Watch it if: {ed['watch']}",
        f"Skip it if: {ed['skip']}",
        '',
        'Highs: ' + ' · '.join(h['point'] for h in f['highs']),
        'Lows: ' + ' · '.join(h['point'] for h in f['lows']),
        '',
        (f"Score: {fmt(f['score'])}/10, the average of {f['n_rated']} published critic ratings converted to /10 "
         f"({mean_txt}). Highest: {ends([r for r in rated if r['rating_10'] == hi])}. "
         f"Lowest: {ends([r for r in rated if r['rating_10'] == lo])}. "
         f"Only reviews published on or after the {rel} release count. "
         f"idly has not watched the film; this post consolidates published reviews."),
        '',
        ed['q'],
        '',
        (f"Sources: Reviews consolidated from {oxford(r['outlet'] for r in rated)}"
         + (f"; unrated reviews from {oxford(unr)}" if unr else '')
         + ". Ratings read on the outlets' pages and in the thereviewmonk and Rotten Tomatoes critics lists."),
        '',
        ed['tags'],
        '',
        CAPTION_CREDIT,
    ]
    return '\n'.join(lines) + '\n'


def film_alt(f):
    ed = EDIT[f['slug']]
    rated = sorted(f['rated'], key=lambda r: -r['rating_10'])
    each = '; '.join(f"{named(r, f)} {fmt(r['rating_10'])}" for r in rated)
    sp = f" Where they split: {f['split']['line']}" if f.get('split') else ''
    return (f"Three slides, type only. 1: \"{ed['cover_title']}\", {ed['meta']}. A consolidated critics' score of "
            f"{fmt(f['score'])}/10 from {f['n_rated']} ratings, a strip of dots showing each rating from "
            f"{fmt(rated[-1]['rating_10'])} to {fmt(rated[0]['rating_10'])}, and the line \"{ed['hook']}\" "
            f"2: what critics agree on. Highs: {'; '.join(h['point'] for h in f['highs'])}. "
            f"Lows: {'; '.join(h['point'] for h in f['lows'])}.{sp} "
            f"3: every rating, out of 10: {each}. Consolidated {fmt(f['score'])}/10. Watch it if: {ed['watch']} "
            f"Skip it if: {ed['skip']} idly did not watch the film.")


def roundup_caption(films):
    rows = [f"{i}. {f['short']} {fmt(f['score'])} ({f['n_rated']} ratings): {f['short_who']}" for i, f in enumerate(films, 1)]
    outlets = sorted({r['outlet'] for f in films for r in f['rated']})
    gap = films[0]['score'] - films[1]['score']
    lines = [
        (f"{len(films)} Diwali releases, ranked by critics: the Indian films in theatres from 30 Oct to 9 Nov that drew "
         f"at least four ratings from established outlets, ranked by the average of {sum(f['n_rated'] for f in films)} "
         f"published critic ratings. Only two clear 6/10."),
        '',
        *rows,
        '',
        ("Score: for each film, its ratings converted to /10; the mean is rounded half-up to one decimal. A film needs "
         "at least 4 ratings, published on or after release. Smaller releases with fewer ratings are not ranked. "
         "idly has not watched these films; this post consolidates published reviews."),
        '',
        f"{films[0]['short']} edges {films[1]['short']} by {gap:.1f}: which would you book first?",
        '',
        f"Sources: Reviews consolidated from {oxford(outlets)}. Ratings read on the outlets' pages and in the thereviewmonk and Rotten Tomatoes critics lists.",
        '',
        '#Diwali2026 #MovieReview #IndianCinema #idlynerd',
        '',
        CAPTION_CREDIT,
    ]
    return '\n'.join(lines) + '\n'


def roundup_alt(films):
    return (f"Three slides, type only. 1: \"{len(films)} Diwali Releases, Ranked by Critics\", scores from "
            f"{fmt(films[0]['score'])} to {fmt(films[-1]['score'])} out of 10, a strip of one dot per film, and the line "
            f"\"Two clear 6/10. Five don't.\" 2: the ranking: "
            + '; '.join(f"{i}. {f['short']} {fmt(f['score'])} from {f['n_rated']} ratings" for i, f in enumerate(films, 1))
            + ". 3: who should watch what: " + '; '.join(f"{f['short']}: {f['short_who']}" for f in films)
            + " idly did not watch the films.")


def write_text(slug, caption, alt, score):
    from pipeline import editorial as E
    d = os.path.join(OUT, slug)
    sc = dict(score)
    sc['total'] = E.score_total(sc)
    sc['reviewer'] = 'pending'
    sc = {k: sc[k] for k in ('hook', 'read', 'send', 'keep', 'reply', 'original', 'alone', 'total', 'notes', 'reviewer')}
    errs, warns = E.post_problems(caption, sc, idly_article=False)
    errs += E.score_problems(sc)
    with open(os.path.join(d, 'caption.txt'), 'w') as fh:
        fh.write(caption)
    with open(os.path.join(d, 'alt.txt'), 'w') as fh:
        fh.write(alt.strip() + '\n')
    with open(os.path.join(d, 'score.json'), 'w') as fh:
        json.dump(sc, fh, indent=2)
        fh.write('\n')
    print(f"{slug:<28} caption {len(caption):>4} chars  score {sc['total']:>2}/14  errors {errs}  warnings {warns}")
    return not errs


def main(argv):
    data = json.load(open(RESEARCH))
    films = [f for f in data['films'] if f['slug'] not in NOT_QUALIFIED]
    films.sort(key=lambda f: -f['score'])
    posted = [f for f in films if f['slug'] not in NO_POST]
    posts = ([roundup_post(films)] if len(films) >= 4 else []) + [film_post(f) for f in posted]
    if len(argv) > 1:
        posts = [p for p in posts if p['slug'] in argv[1:]]
    report = []
    R.render_cards(posts, OUT, template='hype', png_dir=PNG, report=report)
    bad = [r for r in report if r.get('overflow') or r.get('credit_collision')]
    print('slides:', len(report), 'problems:', [(r['slug'], r['slide']) for r in bad])
    ok = not bad
    slugs = {p['slug'] for p in posts}
    if 'review_roundup' in slugs:
        ok &= write_text('review_roundup', roundup_caption(films), roundup_alt(films), SCORES['review_roundup'])
    for f in posted:
        s = f"review_{f['slug']}"
        if s in slugs:
            ok &= write_text(s, film_caption(f), film_alt(f), SCORES[s])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
