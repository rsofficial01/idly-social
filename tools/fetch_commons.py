"""Fetch Commons files (by title) as 2000px thumbs + licence metadata into a candidate dir.
Usage: python3 fetch_commons.py OUTDIR key='File:Title.jpg' ...
"""
import json, re, subprocess, sys, time, os
sys.path.insert(0, '/home/claude/statics')
from commons import api, UA

out = sys.argv[1]
meta_path = os.path.join(out, 'meta.json')
meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
for arg in sys.argv[2:]:
    key, title = arg.split('=', 1)
    d = api({'action': 'query', 'titles': title, 'prop': 'imageinfo',
             'iiprop': 'url|extmetadata|size', 'iiurlwidth': 1920})
    pages = d.get('query', {}).get('pages', {})
    p = list(pages.values())[0] if pages else {}
    if 'imageinfo' not in p:
        print(key, 'MISSING', title); continue
    ii = p['imageinfo'][0]; m = ii.get('extmetadata', {})
    g = lambda x: re.sub(r'<[^>]+>', '', m.get(x, {}).get('value', '')).strip()
    url = ii.get('thumburl') or ii['url']
    ext = os.path.splitext(url.split('?')[0])[1].lower() or '.jpg'
    f = os.path.join(out, f'{key}{ext}')
    r = subprocess.run(['curl', '-sS', '-A', UA, '-o', f, '-w', '%{http_code}', url], capture_output=True, text=True)
    meta[key] = dict(title=title, artist=g('Artist'), credit=g('Credit')[:200], licence=g('LicenseShortName'),
                     licence_url=g('LicenseUrl'), file=f, http=r.stdout, page=ii.get('descriptionurl'),
                     orig_w=ii['width'], orig_h=ii['height'], desc=g('ImageDescription')[:200])
    print(key, r.stdout, ii['width'], 'x', ii['height'], '|', meta[key]['artist'][:50], '|', meta[key]['licence'])
    time.sleep(4)
json.dump(meta, open(meta_path, 'w'), indent=1, ensure_ascii=False)
