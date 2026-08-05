"""Fill the releases Discogs never had, using Deezer's free public API (no key).
Beatport requires an approved partner OAuth (401) and Traxsource has no API, so
Deezer is the only open catalogue with a real label field. Its genre taxonomy is
coarse ('Dance', 'Electro') so it is used for LABELS first; Discogs stays the
source of truth for subgenres."""
import json, re, time, collections, os, urllib.parse, urllib.request

base = json.load(open('listening_base.json'))
disc = json.load(open('release_meta.json'))
out = json.load(open('deezer_meta.json')) if os.path.exists('deezer_meta.json') else {}

hrs = collections.Counter()
for t in base['tracks']:
    if t.get('al'): hrs[(t['a'], t['al'])] += t['h']
targets = [k for k, _ in hrs.most_common() if not disc.get(k[0] + '|' + k[1])]
print(f'{len(targets)} releases unresolved by Discogs', flush=True)

def get(u):
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'SpotifyDive/1.0'}), timeout=15) as r:
                return json.load(r)
        except Exception:
            time.sleep(2)
    return None

def norm(s):
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s or '')
    s = re.sub(r'\s*-\s*(ep|lp|single|original mix|remixes?)$', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', s.lower())

for i, (art, alb) in enumerate(targets):
    key = art + '|' + alb
    if key in out: continue
    d = get("https://api.deezer.com/search/album?q=" + urllib.parse.quote(f'artist:"{art}" album:"{alb}"'))
    time.sleep(0.35)
    hit = None
    na, nr = norm(alb), norm(art)
    for c in (d or {}).get('data', [])[:5]:
        if norm(c.get('title')) and (norm(c['title']) in na or na in norm(c['title'])) \
           and nr and (nr in norm(c.get('artist', {}).get('name', '')) or norm(c.get('artist', {}).get('name', '')) in nr):
            hit = c; break
    if not hit:
        out[key] = None
    else:
        al = get(f"https://api.deezer.com/album/{hit['id']}")
        time.sleep(0.35)
        out[key] = {'l': (al or {}).get('label'),
                    'g': [g['name'] for g in ((al or {}).get('genres') or {}).get('data', [])][:2],
                    'y': ((al or {}).get('release_date') or '')[:4]} if al else None
    if i % 50 == 0:
        json.dump(out, open('deezer_meta.json', 'w'))
        ok = sum(1 for v in out.values() if v and v.get('l'))
        print(f'{i+1}/{len(targets)} · labels {ok}', flush=True)
json.dump(out, open('deezer_meta.json', 'w'))
ok = sum(1 for v in out.values() if v and v.get('l'))
print(f'DONE · {ok}/{len(out)} labels recovered', flush=True)
