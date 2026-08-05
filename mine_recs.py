"""Mine Discogs for releases the user has NEVER played, anchored on the labels and
artists they actually listen to. Two axes:
  A) label catalogs  - 'more from Dirtybird you haven't heard'
  B) artist catalogs - 'Kolter records missing from your history'"""
import json, re, time, collections, os, urllib.parse, urllib.request

TOKEN = os.environ['DISCOGS_TOKEN']
base = json.load(open('listening_base.json'))
meta = json.load(open('artist_meta_v3.json')) if os.path.exists('artist_meta_v3.json') else json.load(open('artist_meta_v2.json'))
tl = json.load(open('track_labels.json')) if os.path.exists('track_labels.json') else {}
out = json.load(open('recs_raw.json')) if os.path.exists('recs_raw.json') else {'label': {}, 'artist': {}}

def norm(s):
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s or '')
    s = re.sub(r'\s*-\s*(original|radio|extended|club|dub|vocal|instrumental|remix|edit|mix|version).*$', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', s.lower())

hours_by_artist = collections.Counter(); hours_by_label = collections.Counter()
for t in base['tracks']:
    hours_by_artist[t['a']] += t['h']
    lb = tl.get(t['id']) or ((meta.get(t['a']) or {}).get('l') or [None])[0]
    if lb: hours_by_label[lb] += t['h']

top_artists = [a for a, _ in hours_by_artist.most_common(300)]
top_labels  = [l for l, _ in hours_by_label.most_common(150)]

def q(p):
    u = "https://api.discogs.com/database/search?" + urllib.parse.urlencode({**p, 'token': TOKEN, 'per_page': 50})
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'SpotifyDive/1.0'}), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(8); continue
            return {}
        except Exception: time.sleep(3); continue
    return {}

def pack(results):
    seen, rows = set(), []
    for r in results:
        title = r.get('title') or ''
        art, _, name = title.partition(' - ')
        art = re.sub(r'\s*\(\d+\)$', '', art).strip()
        if not name: continue
        k = norm(art) + '|' + norm(name)
        if k in seen: continue
        seen.add(k)
        rows.append({'a': art, 'n': name.strip(), 'y': r.get('year'),
                     's': (r.get('style') or [])[:2], 'l': (r.get('label') or [])[:1],
                     'th': r.get('thumb') or ''})
    return rows

for i, l in enumerate(top_labels):
    if l in out['label']: continue
    res = q({'label': l, 'type': 'release', 'sort': 'year', 'sort_order': 'desc'}).get('results', [])
    out['label'][l] = pack(res)[:40]
    time.sleep(1.05)
    if i % 15 == 0:
        json.dump(out, open('recs_raw.json', 'w')); print(f'labels {i+1}/{len(top_labels)}', flush=True)
json.dump(out, open('recs_raw.json', 'w'))

for i, a in enumerate(top_artists):
    if a in out['artist']: continue
    res = q({'artist': a, 'type': 'release', 'sort': 'year', 'sort_order': 'desc'}).get('results', [])
    out['artist'][a] = pack(res)[:40]
    time.sleep(1.05)
    if i % 15 == 0:
        json.dump(out, open('recs_raw.json', 'w')); print(f'artists {i+1}/{len(top_artists)}', flush=True)
json.dump(out, open('recs_raw.json', 'w'))
print(f"DONE labels={len(out['label'])} artists={len(out['artist'])}", flush=True)
