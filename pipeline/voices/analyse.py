"""Turn one run's posts into a digest: counts, repeated-text flags, and short linked excerpts (no usernames)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import themes
from .model import Post

EXCERPT = 220
_WS = re.compile(r'\s+')
_NORM = re.compile(r'[^\w஀-௿]+')


def excerpt(text: str, limit: int = EXCERPT) -> str:
    text = _WS.sub(' ', text).strip()
    text = re.sub(r'(?<!\w)@[\w.]+', '@…', text)       # never carry another user's handle into the digest
    return text if len(text) <= limit else text[:limit - 1].rsplit(' ', 1)[0] + '…'


def _norm(text: str) -> str:
    return _NORM.sub(' ', text.lower()).strip()


def prepare(posts: list[Post], must_match: list[str], extra_themes: dict | None = None, min_chars: int = 25) -> list[Post]:
    """Drop duplicates by id, very short posts, and posts under a broad search that never mention the topic."""
    seen, out = set(), []
    terms = [t.lower() for t in must_match]
    for p in posts:
        key = (p.platform, p.id)
        if key in seen or len(p.text.strip()) < min_chars:
            continue
        seen.add(key)
        hay = f'{p.text} {p.context}'.lower()
        if terms and not any(t in hay for t in terms):
            continue
        p.themes = themes.tag(p.text, extra_themes)
        p.lang = themes.language(p.text)
        p.about = themes.about(p.text)
        p.tone = themes.tone(p.text)
        out.append(p)
    return out


def repeated(posts: list[Post], min_authors: int = 3, min_chars: int = 60) -> dict[str, set]:
    """Normalised texts posted by several different accounts: likely copy-paste (party IT wings, fan pages)."""
    by_text = defaultdict(set)
    for p in posts:
        n = _norm(p.text)
        if len(n) >= min_chars:
            by_text[n].add(p.author_key)
    return {t: a for t, a in by_text.items() if len(a) >= min_authors}


_TOKEN = re.compile(r'[a-z]{4,}|[\u0B80-\u0BFF]{3,}')
_STOP = set('''this that with have from they will what your there their about would which when were been them then than
very just like only also more some into over such even much many most does dont cant here please sir brother anna
இந்த அந்த என்று என்ன ஒரு அது இது நான் நீங்கள் அவர் அவர்கள் இருக்கு இல்லை வேண்டும் மட்டும் தான் எல்லா நம்ம எங்கள் உங்கள் அவங்க இருக்கும்
செய்ய வந்து போல மேலும் ஆனால் எனக்கு நாங்கள் ஐயா அண்ணா சார் பண்ண இனி இப்போ எப்போ எங்க யார் ஏன் கூட'''.split())


def unmatched_terms(posts: list[Post], top: int = 80, min_people: int = 6) -> list[list]:
    """The commonest words in posts that matched no theme and named no party: what the keyword lists are missing."""
    who = defaultdict(set)
    for p in posts:
        if p.themes or p.about:
            continue
        for tok in set(_TOKEN.findall(p.text.lower())):
            if tok not in _STOP:
                who[tok].add(p.author_key)
    rows = sorted(((t, len(a)) for t, a in who.items() if len(a) >= min_people), key=lambda r: -r[1])
    return [list(r) for r in rows[:top]]


def _tones(group: list[Post]) -> dict:
    c = Counter(p.tone or 'neither' for p in group)
    return {k: c.get(k, 0) for k in ('praise', 'criticism', 'mixed', 'neither')}


def digest(topic: dict, posts: list[Post], notes: dict, now: datetime | None = None, per_theme: int = 6) -> dict:
    now = now or datetime.now(timezone.utc)
    rep = repeated(posts)
    rep_ids = {(p.platform, p.id) for p in posts if _norm(p.text) in rep}
    clean = [p for p in posts if (p.platform, p.id) not in rep_ids]
    authors = Counter(p.author_key for p in clean)
    heavy = {a for a, n in authors.items() if n >= 8}       # one account posting 8+ times is counted once per theme
    by_platform = Counter(p.platform for p in clean)
    langs = Counter(p.lang for p in clean)
    theme_rows = []
    for key in list(themes.THEMES) + [k for k in (topic.get('extra_themes') or {}) if k not in themes.THEMES]:
        group = [p for p in clean if key in p.themes]
        if not group:
            continue
        voices = len({p.author_key for p in group})
        top, used_authors, used_ctx = [], set(), Counter()
        for p in sorted(group, key=lambda p: (p.likes, len(p.text)), reverse=True):
            if p.author_key in used_authors or used_ctx[p.context_url] >= 2:
                continue        # one excerpt per person; at most two from the same video or thread
            used_authors.add(p.author_key)
            used_ctx[p.context_url] += 1
            top.append({'text': excerpt(p.text), 'url': p.url, 'platform': p.platform, 'likes': p.likes,
                        'lang': p.lang, 'date': p.published.date().isoformat() if p.published else '',
                        'under': excerpt(p.context, 90), 'owner': p.context_owner})
            if len(top) >= per_theme:
                break
        theme_rows.append({'key': key, 'label': themes.label(key, topic.get('extra_labels')), 'posts': len(group),
                           'people': voices, 'likes': sum(p.likes for p in group),
                           'by_platform': dict(Counter(p.platform for p in group)),
                           'heavy_posters': len({p.author_key for p in group} & heavy), 'top': top})
    theme_rows.sort(key=lambda r: r['people'], reverse=True)
    owners = Counter(p.context_owner for p in clean)
    return {
        'topic': topic.get('slug', ''), 'title': topic.get('title', ''), 'generated': now.isoformat(timespec='minutes'),
        'window': {'since': topic.get('since'), 'until': topic.get('until')},
        'totals': {'posts_read': len(posts), 'posts_counted': len(clean), 'people': len(authors),
                   'by_platform': dict(by_platform), 'by_language': dict(langs),
                   'untagged': sum(1 for p in clean if not p.themes),
                   'tone': _tones(clean)},
        'repeated_text': {'distinct_texts': len(rep), 'posts': len(rep_ids),
                          'examples': [excerpt(t, 140) for t in sorted(rep, key=lambda t: -len(rep[t]))[:5]]},
        'where_from': dict(owners.most_common(20)),
        'about': [{'key': k, 'label': themes.ABOUT[k][0], 'people': len({p.author_key for p in g}), 'posts': len(g),
                   'only_this_party': sum(1 for p in g if len(p.about) == 1),
                   'tone_when_only_this_party': _tones([p for p in g if len(p.about) == 1])}
                  for k in themes.ABOUT for g in [[p for p in clean if k in p.about]] if g],
        'by_month': [{'month': m, 'posts': len(g), 'tone': _tones(g),
                      'tvk_only_tone': _tones([p for p in g if p.about == ['tvk']]),
                      'top_themes': [themes.label(k) for k, _ in Counter(t for p in g for t in p.themes).most_common(4)]}
                     for m in sorted({p.published.strftime('%Y-%m') for p in clean if p.published})
                     for g in [[p for p in clean if p.published and p.published.strftime('%Y-%m') == m]]],
        'unmatched': {'posts': sum(1 for p in clean if not p.themes and not p.about),
                      'common_words': unmatched_terms(clean)},
        'themes': theme_rows, 'platform_notes': notes,
        'caveats': [
            'This is a reading of public posts found by the searches below, not a poll. It cannot give a share of the population.',
            'Comment sections over-represent people who are angry, organised or very online; party IT wings and fan pages post in them.',
            'Text repeated word for word by three or more accounts is left out of the counts and reported separately.',
            'Tone is a word match (praise words v criticism words), not a reading of meaning: sarcasm and insults aimed at the other side are miscounted. Use it for direction over time, never as a percentage of support.',
            'Themes are matched by keyword. A post that mentions power cuts is counted under power whether it blames or defends anyone.',
            'YouTube comments sit under videos from channels with their own lean; the list of channels is in platform notes.',
        ],
    }


def markdown(d: dict) -> str:
    t = d['totals']
    lines = [f"# Citizen voices: {d['title']}", '',
             f"Generated {d['generated']} UTC · window {d['window']['since']} to {d['window']['until'] or 'now'}", '',
             f"**{t['posts_counted']:,} posts from {t['people']:,} accounts** counted "
             f"({', '.join(f'{k} {v:,}' for k, v in t['by_platform'].items()) or 'none'}); "
             f"languages: {', '.join(f'{k} {v:,}' for k, v in t['by_language'].items()) or 'n/a'}. "
             f"{d['repeated_text']['posts']:,} copy-paste posts left out. {t['untagged']:,} matched no theme (some of those still name a party; see Unmatched posts).", '',
             '## Read this first', ''] + [f'- {c}' for c in d['caveats']] + ['', '## Themes, by number of different people', '',
             '| Theme | People | Posts | Likes | Platforms |', '|---|---:|---:|---:|---|']
    for r in d['themes']:
        plat = ', '.join(f'{k} {v}' for k, v in r['by_platform'].items())
        lines.append(f"| {r['label']} | {r['people']:,} | {r['posts']:,} | {r['likes']:,} | {plat} |")
    for r in d['themes']:
        lines += ['', f"### {r['label']}", '']
        for x in r['top']:
            under = f" · under “{x['under']}” ({x['owner']})" if x['under'] else f" · {x['owner']}"
            lines.append(f"- “{x['text']}” · {x['likes']:,} likes · {x['date']}{under} · [link]({x['url']})")
    lines += ['', '## Who the posts are about', '', '| Party | People | Posts | Naming only this party | Praise words | Criticism words |', '|---|---:|---:|---:|---:|---:|']
    for r in d.get('about', []):
        t = r['tone_when_only_this_party']
        lines.append(f"| {r['label']} | {r['people']:,} | {r['posts']:,} | {r['only_this_party']:,} | {t['praise']:,} | {t['criticism']:,} |")
    lines += ['', '## Month by month', '', '| Month | Posts | Praise words | Criticism words | TVK-only: praise | TVK-only: criticism | Top themes |', '|---|---:|---:|---:|---:|---:|---|']
    for r in d.get('by_month', []):
        lines.append(f"| {r['month']} | {r['posts']:,} | {r['tone']['praise']:,} | {r['tone']['criticism']:,} | "
                     f"{r['tvk_only_tone']['praise']:,} | {r['tvk_only_tone']['criticism']:,} | {', '.join(r['top_themes'])} |")
    u = d.get('unmatched', {})
    lines += ['', f"## Unmatched posts ({u.get('posts', 0):,}): commonest words", '',
              ', '.join(f'{w} ({n})' for w, n in u.get('common_words', [])) or 'none']
    lines += ['', '## Copy-paste text (left out of the counts)', '']
    lines += [f'- “{e}”' for e in d['repeated_text']['examples']] or ['- none found']
    lines += ['', '## Where the posts sit', ''] + [f'- {k}: {v:,}' for k, v in d['where_from'].items()]
    lines += ['', '## Platform notes', '']
    for name, note in d['platform_notes'].items():
        lines.append(f'- **{name}**: {note if isinstance(note, str) else ", ".join(f"{k}: {v}" for k, v in note.items())}')
    return '\n'.join(lines) + '\n'
