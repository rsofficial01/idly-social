"""The idly baseline: what idly has already sourced about a place, checked before any local story is written.

    python3 -m pipeline.baseline check "Vijay govt raises women's aid to Rs 2,500"     # what we already know + rule flags
    python3 -m pipeline.baseline check --file draft_caption.txt --region tn
    python3 -m pipeline.baseline due                                                    # dated things to watch, soonest first
    python3 -m pipeline.baseline log --region tn --note "Speaker rejects disqualification plea" --source https://... --ids speaker-ruling
    python3 -m pipeline.baseline validate                                               # schema check (run in tests)

A baseline lives in baseline/<region>/: people.json, facts*.json, promises.json, ledger.json, watch.json (see
baseline/tn/SCHEMA.md), rules.json (things idly never publishes, as patterns) and log.jsonl (developments recorded
since the baseline was built, newest last). `check` matches a story's text against every item's keywords and prints
the items a desk must read before writing: prior facts with their status (verified / single_source / disputed /
alleged), promises and their verdict, ledger entries, and anything in the log. Exit code 2 means a rule was hit and
the story must not be published as written. The repository is public: sourced facts about public figures only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'baseline'
STATUSES = {'verified', 'single_source', 'disputed', 'alleged'}
KINDS = ('people', 'facts', 'promises', 'ledger', 'watch')   # facts_*.json (e.g. facts_history_polity.json) count as facts
_LATIN = re.compile(r"^[a-z0-9 .'&/-]+$")
_cache: dict[str, re.Pattern] = {}
GENERIC = {'tvk', 'dmk', 'aiadmk', 'bjp', 'vijay', 'stalin', 'tamil nadu', 'tamilnadu', 'government', 'minister',
           'chief minister', 'cm', 'chennai', 'crore', 'scheme', 'state', 'தமிழ்நாடு', 'அரசு', 'முதல்வர்', 'அமைச்சர்',
           'தவெக', 'திமுக', 'அதிமுக', 'விஜய்', 'ஸ்டாலின்'}


def _hit(low: str, term: str) -> bool:
    term = term.lower().strip()
    if len(term) < 2:
        return False
    if not _LATIN.match(term):
        return term in low
    pat = _cache.get(term)
    if pat is None:
        pat = _cache[term] = re.compile(r'(?<![a-z0-9])' + re.escape(term) + r'(?:s|es)?(?![a-z0-9])')
    return bool(pat.search(low))


def kind_of(path: Path) -> str:
    stem = path.stem
    return next((k for k in KINDS if stem == k or stem.startswith(k + '_')), '')


def load(region: str) -> list[dict]:
    items = []
    for path in sorted((ROOT / region).glob('*.json')):
        kind = kind_of(path)
        if not kind:
            continue
        for row in json.loads(path.read_text()):
            items.append({**row, '_kind': kind, '_file': path.name})
    return items


def load_log(region: str) -> list[dict]:
    path = ROOT / region / 'log.jsonl'
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def load_rules(region: str) -> list[dict]:
    path = ROOT / region / 'rules.json'
    return json.loads(path.read_text()) if path.exists() else []


def match(text: str, items: list[dict], limit: int = 40) -> list[dict]:
    """Items whose keywords appear in the text. Specific keywords count 3, generic ones (party names, 'minister') 1;
    an item needs at least one specific hit, so 'TVK' alone does not drag in the whole baseline."""
    low = ' ' + text.lower() + ' '
    out = []
    for it in items:
        kws = [k for k in it.get('keywords', []) if isinstance(k, str)]
        if it['_kind'] == 'people':
            kws = kws + [it.get('name', '')] + list(it.get('aliases', []))
        hits = sorted({k.lower() for k in kws if _hit(low, k)})
        specific = [h for h in hits if h not in GENERIC]
        if specific:
            out.append({**it, '_hits': hits, '_score': 3 * len(specific) + len(hits) - len(specific)})
    out.sort(key=lambda r: (-r['_score'], r['_kind'], r['id']))
    return out[:limit]


def rule_hits(text: str, rules: list[dict]) -> list[dict]:
    low = text.lower()
    return [r for r in rules if all(re.search(p, low) for p in r.get('all', [])) and
            (not r.get('any') or any(re.search(p, low) for p in r['any']))]


def line(it: dict) -> str:
    k = it['_kind']
    src = (it.get('sources') or [{}])[0]
    tail = f" [{it.get('status', '?')}, as of {it.get('as_of', '?')}; {src.get('outlet', '')} {src.get('url', '')}]"
    if k == 'people':
        facts = '; '.join(it.get('facts', [])[:3])
        body = f"{it.get('name')} ({it.get('party', '')}), {it.get('role', '')} {it.get('portfolio', '') or ''}. {facts}"
    elif k == 'promises':
        body = f"{it.get('party', '')} promise: {it.get('promise')} | promised: {it.get('promised')} | now: {it.get('current')} | verdict: {it.get('verdict')}"
    elif k == 'ledger':
        body = f"{it.get('party', '')} showcased: {it.get('showcased')} | followed: {it.get('followed')} | legal: {it.get('legal_status')} | response: {it.get('response')}"
    elif k == 'watch':
        body = f"WATCH {it.get('when')}: {it.get('what')} ({it.get('why')})"
    else:
        alt = f" Other figures: {', '.join(map(str, it['alt_values']))}." if it.get('alt_values') else ''
        resp = f" Response: {it['response']}" if it.get('response') else ''
        body = f"{it.get('statement')}{alt}{resp}"
    return re.sub(r'\s+', ' ', body).strip() + tail


def check(text: str, region: str) -> tuple[str, int]:
    items, rules, log = load(region), load_rules(region), load_log(region)
    found, broken = match(text, items), rule_hits(text, rules)
    ids = {f['id'] for f in found}
    low = ' ' + text.lower() + ' '
    recent = [e for e in log if set(e.get('ids', [])) & ids or any(_hit(low, k) for k in e.get('keywords', []))]
    out = []
    if broken:
        out.append('STOP: this text breaks a publishing rule')
        out += [f"  - {r['id']}: {r['why']}" for r in broken]
    if not found and not recent:
        out.append('Nothing in the baseline matches. Treat as new ground: two sources, and log it after publishing.')
    order = {'ledger': 0, 'promises': 1, 'facts': 2, 'people': 3, 'watch': 4}
    for k in sorted({f['_kind'] for f in found}, key=order.get):
        out.append(f'\n## {k} ({sum(1 for f in found if f["_kind"] == k)})')
        out += [f'- {line(f)}' for f in found if f['_kind'] == k]
    if recent:
        out.append('\n## since the baseline (log)')
        out += [f"- {e.get('date')}: {e.get('note')} [{e.get('source', '')}]" for e in recent[-10:]]
    flags = sorted({f.get('status') for f in found} & {'disputed', 'alleged', 'single_source'})
    if flags:
        out.append('\nHandle with care: matched items include ' + ', '.join(flags) +
                   '. Disputed: give both figures. Alleged: say alleged and give the response. Single source: find a second.')
    return '\n'.join(out), (2 if broken else 0)


def due(region: str, today: date | None = None) -> list[str]:
    today = today or date.today()
    rows = []
    for it in load(region):
        if it['_kind'] != 'watch':
            continue
        m = re.search(r'(20\d{2})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?(?!\d)', str(it.get('when', '')))
        try:
            when = date(int(m[1]), int(m[2]), int(m[3] or 1)) if m else None
        except ValueError:
            when = None
        rows.append((when or date.max, it))
    rows.sort(key=lambda r: r[0])
    return [f"{('OVERDUE ' if w < today else '') if w != date.max else 'undated '}{it.get('when')}: {it.get('what')} ({it.get('why')})" for w, it in rows]


def validate(region: str) -> list[str]:
    errs, seen = [], {}
    for it in load(region):
        where = f"{it['_file']}:{it.get('id', '?')}"
        if not it.get('id') or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(it.get('id'))):
            errs.append(f'{where}: bad id')
        if (it['_file'], it.get('id')) in seen:
            errs.append(f'{where}: duplicate id')
        seen[(it['_file'], it.get('id'))] = 1
        srcs = it.get('sources') or []
        if not srcs or any(not str(s.get('url', '')).startswith('https://') for s in srcs if isinstance(s, dict)) \
                or not all(isinstance(s, dict) for s in srcs):
            errs.append(f'{where}: needs sources with https urls')
        if it.get('status') not in STATUSES:
            errs.append(f'{where}: status must be one of {sorted(STATUSES)}')
        if it.get('status') == 'alleged' and not (it.get('response') or it['_kind'] == 'people'):
            errs.append(f'{where}: alleged items need a response')
        if it.get('status') == 'disputed' and it['_kind'] == 'facts' and not it.get('alt_values'):
            errs.append(f'{where}: disputed facts need alt_values')
        if not it.get('keywords'):
            errs.append(f'{where}: no keywords')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(it.get('as_of', ''))):
            errs.append(f'{where}: as_of must be YYYY-MM-DD')
    rules = [r for r in load_rules(region) if r.get('scan_baseline', True)]
    for it in load(region):                      # rule scan item by item, ignoring source links
        text = json.dumps({k: v for k, v in it.items() if k != 'sources'}, ensure_ascii=False)
        for r in rule_hits(text, rules):
            errs.append(f"{it['_file']}:{it.get('id')}: text breaks rule {r['id']}")
    return errs


def add_log(region: str, note: str, source: str, ids: list[str], keywords: list[str]) -> dict:
    if not source.startswith('https://'):
        raise SystemExit('a log entry needs an https source link')
    entry = {'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'note': note.strip(), 'source': source,
             'ids': ids, 'keywords': [k.lower() for k in keywords]}
    with (ROOT / region / 'log.jsonl').open('a') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python3 -m pipeline.baseline')
    ap.add_argument('--region', default='tn')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check'); c.add_argument('text', nargs='?'); c.add_argument('--file'); c.add_argument('--region', default='tn')
    d = sub.add_parser('due'); d.add_argument('--region', default='tn')
    v = sub.add_parser('validate'); v.add_argument('--region', default='tn')
    g = sub.add_parser('log'); g.add_argument('--region', default='tn'); g.add_argument('--note', required=True)
    g.add_argument('--source', required=True); g.add_argument('--ids', nargs='*', default=[]); g.add_argument('--keywords', nargs='*', default=[])
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        text = Path(a.file).read_text() if a.file else (a.text or sys.stdin.read())
        out, code = check(text, a.region)
        print(out)
        return code
    if a.cmd == 'due':
        print('\n'.join(due(a.region)) or 'nothing to watch')
        return 0
    if a.cmd == 'validate':
        errs = validate(a.region)
        print('\n'.join(errs) or f'ok: {len(load(a.region))} items')
        return 1 if errs else 0
    print(json.dumps(add_log(a.region, a.note, a.source, a.ids, a.keywords), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
