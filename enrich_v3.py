"""Discogs enrichment with TITLE-ANCHORED artist verification.
Name-only matching produced ~30% false positives in the long tail
(e.g. house producer 'Garrett David' -> violinist David Garrett -> Classical/Baroque).
Every match here must be corroborated by a release title we know the artist made."""
import json, re, time, urllib.parse, urllib.request, collections, os

TOKEN = os.environ['DISCOGS_TOKEN']
base = json.load(open('listening_base.json'))
targets = json.load(open('enrich_targets.json'))
out = json.load(open('artist_meta_v3.json')) if os.path.exists('artist_meta_v3.json') else {}

works = collections.defaultdict(collections.Counter)
for t in base['tracks']:
    if t.get('al'): works[t['a']][t['al']] += t['h']
    if t.get('n'):  works[t['a']][t['n']]  += t['h']

GENERIC = {'',' ','untitled','ep','album','single','remixes','remix','various','vol1','vol2'}
def norm(s):
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s or '')
    s = re.sub(r'\s*-\s*(original|radio|extended|club|dub|vocal|instrumental|remix|edit|mix|version).*$', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', s.lower())

def q(params):
    url = "https://api.discogs.com/database/search?" + urllib.parse.urlencode({**params, 'token': TOKEN, 'per_page': 15})
    req = urllib.request.Request(url, headers={'User-Agent': 'SpotifyDive/1.0'})
    for _ in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(8); continue
            return {}
        except Exception: time.sleep(3); continue
    return {}

def collect(results):
    g, s, l, c = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for r in results:
        for x in (r.get('genre') or []): g[x] += 1
        for x in (r.get('style') or []): s[x] += 1
        for x in (r.get('label') or []):
            x = re.sub(r'\s*\(\d+\)$', '', x).strip()
            if x and x.lower() != 'not on label': l[x] += 1
        if r.get('country'): c[r['country']] += 1
    return ({'g': [k for k, _ in g.most_common(2)], 's': [k for k, _ in s.most_common(4)],
             'l': [k for k, _ in l.most_common(3)], 'c': (c.most_common(1)[0][0] if c else None)})

def rel_titles(results):
    t = []
    for r in results:
        x = r.get('title', '')
        t.append(norm(x.split(' - ', 1)[1] if ' - ' in x else x))
    return t

def overlaps(known, titles):
    return any(t and any(t in k or k in t for k in known if len(k) > 3) for t in titles)

for i, a in enumerate(targets):
    if a in out: continue
    known = {norm(w) for w in works[a]} - GENERIC
    anchors = [w for w, _ in works[a].most_common(14) if w and norm(w) not in GENERIC][:5]
    meta, conf = None, 0
    for title in anchors:                       # strongest: artist + known release title
        res = q({'artist': a, 'release_title': title, 'type': 'release'}).get('results', [])
        time.sleep(1.05)
        if res:
            meta, conf = collect(res), 2
            break
    if not meta:                                # fallback: name-only, but must corroborate
        res = q({'artist': a, 'type': 'release'}).get('results', [])
        time.sleep(1.05)
        if res and overlaps(known, rel_titles(res)):
            meta, conf = collect(res), 1
    out[a] = {**(meta or {'g': [], 's': [], 'l': [], 'c': None}), 'v': conf}
    if i % 20 == 0:
        json.dump(out, open('artist_meta_v3.json', 'w'))
        v = collections.Counter(x['v'] for x in out.values())
        print(f'{i+1}/{len(targets)} · verified={v[2]} corroborated={v[1]} unverified={v[0]}', flush=True)
json.dump(out, open('artist_meta_v3.json', 'w'))
v = collections.Counter(x['v'] for x in out.values())
print(f'DONE · verified={v[2]} corroborated={v[1]} unverified={v[0]}', flush=True)
