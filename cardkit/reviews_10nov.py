"""10 Nov 2026: idly's Diwali 2026 review carousels for @idlynerd (consolidated published reviews).

Data: /home/claude/reviews_diwali/research.json (v2: only reviews read with the fetch tool, or a rating in the
outlet's own headline; nothing read only with curl). Every number on the cards comes from there.
The roundup is built only when 4 or more films qualify.
Renders with cardkit's hype template via render_cards(..., template='hype'). The four slide kinds used here
('vcover', 'verdict', 'scores', 'rank', plus 'picks') are registered at runtime below; cardkit/render.py itself
is not modified. They share the hype template's fonts, colours, logo and footer.

    python3 cardkit/_work/reviews_10nov.py            # render all posts into posts/2026-11-10/review_*/
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

RESEARCH = '/home/claude/reviews_diwali/research.json'
PHOTOS = '/home/claude/reviews_diwali/photos'
OUT = os.path.join(REPO, 'posts', '2026-11-10')
PNG = '/home/claude/reviews_diwali/png'
TMP = '/home/claude/reviews_diwali/tmp'
DATE = '10 Nov 2026'
ACCT = 'idlynerd'

SEATS = dict(file=os.path.join(PHOTOS, 'seats_cc0.jpg'), focal=(0.5, 0.62), zoom=1.0,
             credit='Photo: Elijah Flores / Wikimedia Commons (CC0)',
             page='https://commons.wikimedia.org/wiki/File:Movie_theater_seats_(Unsplash).jpg',
             licence='CC0', author='Elijah Flores (via Unsplash)')
SCREEN = dict(file=os.path.join(PHOTOS, 'nazrul_02.jpg'), focal=(0.42, 0.5), zoom=1.0,
              credit='Photo: Projjal Moitra / Wikimedia Commons (CC BY-SA 4.0)',
              page='https://commons.wikimedia.org/wiki/File:Nazrul_Tirtha_screen_1_interior_02.jpg',
              licence='CC BY-SA 4.0', author='Projjal Moitra')

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
.basis{font:500 25px/1.3 Inter;color:rgba(255,255,255,.62);margin-top:22px}

/* detail-style pages */
.d2 .body{position:absolute;left:72px;right:72px;top:96px;bottom:176px;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.d2 .sub{font:700 34px/1.2 Inter;margin-top:16px;color:#fff}
.d2 .sub b{font-family:Playfair;font-style:italic;font-weight:900;color:%(ember)s}
.sect{font-family:Playfair;font-style:italic;font-weight:900;font-size:96px;line-height:1;margin-top:44px;letter-spacing:-.01em}
.sect.hi{color:%(ember)s}
.sect.lo{color:#fff}
.pt{position:relative;padding-left:44px;margin-top:22px}
.pt .t{font:600 41px/1.2 Inter;letter-spacing:-.012em;text-wrap:pretty}
.pt .n{font:500 24px/1.2 Inter;color:rgba(255,255,255,.55);margin-top:6px}
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
.tot{display:flex;align-items:baseline;justify-content:space-between;margin-top:20px}
.tot .o{font:800 34px/1 Inter}
.tot .nv{font-family:Playfair;font-style:italic;font-weight:900;font-size:86px;line-height:.9;color:%(ember)s}
.who{margin-top:26px;border-left:4px solid %(ember)s;padding-left:24px}
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
.rk{display:flex;align-items:center;border-bottom:1.5px solid rgba(255,255,255,.12);padding:14px 0}
.rk .no{font-family:Playfair;font-style:italic;font-weight:900;font-size:50px;width:70px;color:rgba(255,255,255,.45)}
.rk .mid{flex:1;min-width:0}
.rk .tt{font:800 38px/1.08 Inter;letter-spacing:-.02em}
.rk .ln{font:500 24px/1.25 Inter;color:rgba(255,255,255,.62);margin-top:6px}
.rk .bar{height:6px;background:rgba(255,255,255,.12);border-radius:3px;margin-top:10px;width:100%%}
.rk .bar i{display:block;height:6px;border-radius:3px;background:%(ember)s}
.rk .sc{font-family:Playfair;font-style:italic;font-weight:900;font-size:78px;line-height:1;color:%(ember)s;
        margin-left:26px;min-width:150px;text-align:right}
.pick{border-bottom:1.5px solid rgba(255,255,255,.12);padding:15px 0}
.pick .tt{font:800 33px/1.1 Inter;letter-spacing:-.015em}
.pick .tt b{font-family:Playfair;font-style:italic;font-weight:900;color:%(ember)s;margin-left:10px}
.pick .w{font:500 27px/1.25 Inter;color:rgba(255,255,255,.78);margin-top:6px;text-wrap:pretty}
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


def bg_photo(photo: dict, slug: str) -> str:
    os.makedirs(TMP, exist_ok=True)
    crop, scale = R._hype_crop(photo['file'], photo['focal'], photo['zoom'])
    crop = ImageEnhance.Brightness(crop).enhance(1.0)
    out = os.path.join(TMP, f'{slug}_bg.png')
    crop.save(out)
    return out


# ---------------------------------------------------------------------------------------------
# slide builders
# ---------------------------------------------------------------------------------------------
def html_vcover(post, s):
    bg = bg_photo(s['photo'], post['slug'])
    ttl_size = s.get('title_px', 104)
    body = f"""
<img class='bgph' src='file://{bg}'><div class='shade'></div>
<img class='toplogo' src='file://{logo_white()}'>
<div class='credit'>{e(s['photo']['credit'])}</div>
<div class='body'>
  <div>
    <div class='kicker'>{s['kicker']}</div>
    <div class='ttl' style='font-size:{ttl_size}px'>{e(s['title'])}</div>
    <div class='meta'>{e(s['meta'])}</div>
  </div>
  <div>
    {s.get('score_html', '')}
    <div class='hook'>{e(s['hook'])}</div>
    <div class='basis'>{e(s.get('basis', ''))}</div>
  </div>
</div>
<div class='cfoot'><span>{e(post['date'])}</span><span>idly.news</span></div>"""
    return doc(body, css())


def html_verdict(post, s):
    pts = []
    pts.append("<div class='sect hi'>Highs</div>")
    for h in s['highs']:
        pts.append(f"<div class='pt h'><div class='t'>{e(h['point'])}</div><div class='n'>{len(h['outlets'])} reviews say so</div></div>")
    if s.get('highs_note'):
        pts.append(f"<div class='note'>{e(s['highs_note'])}</div>")
    pts.append("<div class='sect lo'>Lows</div>")
    for h in s['lows']:
        pts.append(f"<div class='pt l'><div class='t'>{e(h['point'])}</div><div class='n'>{len(h['outlets'])} reviews say so</div></div>")
    body = f"""
<div class='d2'><div class='body'>
  <div class='kicker'>What critics agree on</div>
  <div class='sub'>{e(s['title'])} · <b>{e(s['score'])}/10</b></div>
  {''.join(pts)}
</div>{foot2(post)}</div>"""
    return doc(body, css())


def html_scores(post, s):
    rows = []
    for r in s['rows']:
        star = '<i>*</i>' if r.get('read') == 'headline' else ''
        rows.append(f"<div class='row'><div class='o'>{e(r['outlet'])}{star}</div><div class='v'>"
                    f"<span class='p'>{e(fmt_pub(r['rating']))}/{r['scale']}</span><span class='nv'>{fmt(r['rating_10'])}</span></div></div>")
    notes = []
    if any(r.get('read') == 'headline' for r in s['rows']):
        notes.append("* Rating taken from NDTV's published headline.")
    if s.get('extra'):
        notes.append(s['extra'])
    if s.get('unrated'):
        notes.append(s['unrated'])
    note_html = ''.join(f"<div class='note' style='font-size:23px;margin-top:10px'>{e(n)}</div>" for n in notes)
    body = f"""
<div class='d2'><div class='body'>
  <div class='kicker'>Every score <span>· out of 10</span></div>
  <div class='sub'>{e(s['title'])}</div>
  <div class='rows'>{''.join(rows)}</div>
  <div class='tot'><div class='o'>Consolidated ({len(s['rows'])} ratings)</div><div class='nv'>{e(s['score'])}/10</div></div>
  {note_html}
  <div class='who'><div class='k'>Who should watch</div><div class='w'>{e(s['who'])}</div></div>
</div>{foot2(post)}</div>"""
    n = len(s['rows'])
    fs, pad = ('30px', '6px') if n >= 12 else (('33px', '12px') if n >= 6 else ('36px', '16px'))
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
</div>{foot2(post)}</div>"""
    return doc(body, css())


def html_picks(post, s):
    rows = []
    for f in s['films']:
        rows.append(f"<div class='pick'><div class='tt'>{e(f['title'])}<b>{fmt(f['score'])}</b></div><div class='w'>{e(f['who'])}</div></div>")
    body = f"""
<div class='d2'><div class='body' style='top:90px'>
  <div class='kicker'>Who should watch what</div>
  <div class='rows' style='margin-top:12px'>{''.join(rows)}</div>
</div>{foot2(post)}</div>"""
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
HOOKS = {
    'ramayana-part-1': "Critics agree: dazzling scale, and Yash's Ravana steals it.",
    'scene': "Suriya's back in form; the script wobbles, critics say.",
    'summer-holidays': 'Sweet, nostalgic and predictable, critics say.',
    'aadarsha-kutumbam': 'A fun first half, then it runs out of steam.',
    'cult': 'Plenty of gore, not much tension, critics say.',
    'mookuthi-amman-2': 'Critics agree on one thing: Nayanthara.',
    'disco': 'The lowest-rated Diwali release in our count.',
}
TITLE_PX = {'aadarsha-kutumbam': 92, 'ramayana-part-1': 104, 'mookuthi-amman-2': 104}
ROUND_LINE = {
    'ramayana-part-1': "Hindi · Yash's Ravana, epic scale",
    'scene': 'Tamil · Suriya back in form',
    'summer-holidays': 'Telugu · warm but predictable',
    'aadarsha-kutumbam': 'Telugu · fun first half only',
    'cult': 'Telugu · gore over tension',
    'mookuthi-amman-2': 'Tamil · only Nayanthara works',
    'disco': 'Malayalam · violent and hollow',
}
SPLIT_NOTE = {
}
SHORT_WHO = {
    'ramayana-part-1': 'Big-screen spectacle; set aside 3h15m.',
    'scene': 'Suriya fans and dark-comedy lovers. Be patient early on.',
    'summer-holidays': 'Families with kids, and anyone who misses village summers.',
    'aadarsha-kutumbam': 'Venkatesh fans; others can wait for streaming.',
    'cult': 'Slasher fans who are fine with heavy gore.',
    'mookuthi-amman-2': 'Nayanthara completists only.',
    'disco': 'Only if ultra-violent gangster films are your thing.',
}


def score_html(score: float) -> str:
    return f"<div class='score'><span class='big'>{fmt(score)}</span><span class='of'>/10</span></div>"


def film_post(f):
    title = f['title']
    n = f['n_rated']
    fx = f.get('facts') or {}
    meta = ' · '.join(x for x in (f['language'], fx.get('cert'), fx.get('runtime'), 'in theatres') if x)
    cover = dict(type='vcover', photo=SEATS, kicker="The verdict <span>· Diwali 2026</span>", title=title, meta=meta,
                 score_html=score_html(f['score']), hook=HOOKS[f['slug']], title_px=TITLE_PX.get(f['slug'], 112),
                 basis=f"Consolidated from {n} critic ratings, each converted to /10")
    verdict = dict(type='verdict', title=f.get('short', title), score=fmt(f['score']), highs=f['highs'], lows=f['lows'],
                   highs_note=f.get('highs_note'))
    unr = f['unrated']
    unrated_line = ''
    if unr:
        k = len(unr)
        unrated_line = (f"Plus {k} unrated review{'s' if k > 1 else ''} (listed in the caption), "
                        f"used only for the highs and lows.")
    scores = dict(type='scores', title=f.get('short', title), score=fmt(f['score']),
                  rows=sorted(f['rated'], key=lambda r: -r['rating_10']), unrated=unrated_line, who=f['who'],
                  extra=SPLIT_NOTE.get(f['slug']))
    return dict(acct=ACCT, slug=f"review_{f['slug']}", date=DATE, slides=[cover, verdict, scores])


def roundup_post(films):
    total_rated = sum(f['n_rated'] for f in films)
    total = sum(f['n_rated'] + f['n_unrated'] for f in films)
    cover = dict(type='vcover', photo=SCREEN, kicker="Diwali 2026 <span>· the verdicts</span>",
                 title='Every Diwali release, rated', meta=f"{len(films)} films · {total} reviews read · {total_rated} critic ratings",
                 score_html=(f"<div class='score'><span class='big' style='font-size:250px'>{fmt(films[0]['score'])}</span>"
                             f"<span class='of' style='font-size:80px'>to</span><span class='big' style='font-size:250px;margin-left:24px'>{fmt(films[-1]['score'])}</span></div>"),
                 hook='From the best-reviewed release to the worst, in one list.', title_px=112,
                 basis='Scores out of 10: the average of published Indian critic ratings')
    rank = dict(type='rank', films=[dict(title=f.get('short', f['title']), score=f['score'], line=f"{ROUND_LINE[f['slug']]} · {f['n_rated']} ratings")
                                    for f in films],
                method='Theatrical releases from 30 Oct to 9 Nov with at least four reviews from established Indian outlets. Score: the average of their published ratings, converted to /10.')
    picks = dict(type='picks', films=[dict(title=f.get('short', f['title']), score=f['score'], who=SHORT_WHO[f['slug']]) for f in films])
    return dict(acct=ACCT, slug='review_roundup', date=DATE, slides=[cover, rank, picks])


def main(argv):
    data = json.load(open(RESEARCH))
    films = data['films']
    posts = ([roundup_post(films)] if len(films) >= 4 else []) + [film_post(f) for f in films]
    if len(argv) > 1:
        posts = [p for p in posts if p['slug'] in argv[1:]]
    report = []
    R.render_cards(posts, OUT, template='hype', png_dir=PNG, report=report)
    bad = [r for r in report if r.get('overflow')]
    print('slides:', len(report), 'overflow:', [(r['slug'], r['slide']) for r in bad])
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
