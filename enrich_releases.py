"""Per-RELEASE genres/styles. Genre belongs to a record, not to a person:
Kolter's 'Between Fragments' is Breakbeat/Ambient/Dub while 'Authentic Computers'
is House - both are Kolter. Artist->genre is many-to-many precisely because
release->genre is one-to-many and artist->release is one-to-many.
Keyed by (artist, album) so every track inherits its OWN record's tags."""
import json, re, time, collections, os, urllib.parse, urllib.request

TOKEN = os.environ['DISCOGS_TOKEN']
base = json.load(open('listening_base.json'))
out = json.load(open('release_meta.json')) if os.path.exists('release_meta.json') else {}

hours = collections.Counter()
for t in base['tracks']:
    if t.get('al'): hours[(t['a'], t['al'])] += t['h']
targets = [k for k, _ in hours.most_common()]          # most-listened releases first

def norm(s):
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s or '')
    s = re.sub(r'\s*-\s*(original|radio|extended|club|dub|vocal|instrumental|remix|edit|mix|version).*$', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', s.lower())

def q(p):
    u = "https://api.discogs.com/database/search?" + urllib.parse.urlencode({**p, 'token': TOKEN, 'per_page': 12})
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'SpotifyDive/1.0'}), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(8); continue
            return {}
        except Exception: time.sleep(3); continue
    return {}

for i, (art, alb) in enumerate(targets):
    key = art + '|' + alb
    if key in out: continue
    na = norm(alb)
    res = q({'artist': art, 'release_title': alb, 'type': 'release'}).get('results', [])
    time.sleep(1.05)
    keep = []
    for r in res:                      # title must really match this release
        ti = r.get('title', '')
        ti = norm(ti.split(' - ', 1)[1] if ' - ' in ti else ti)
        if ti and na and (ti in na or na in ti): keep.append(r)
    if not keep: keep = res[:3] if res else []
    if keep:
        g, s, l = collections.Counter(), collections.Counter(), collections.Counter()
        for r in keep:
            for x in (r.get('genre') or []): g[x] += 1
            for x in (r.get('style') or []): s[x] += 1
            for x in (r.get('label') or []):
                x = re.sub(r'\s*\(\d+\)$', '', x).strip()
                if x and x.lower() != 'not on label': l[x] += 1
        out[key] = {'g': [k for k, _ in g.most_common(3)], 's': [k for k, _ in s.most_common(5)],
                    'l': [k for k, _ in l.most_common(2)]}
    else:
        out[key] = None
    if i % 40 == 0:
        json.dump(out, open('release_meta.json', 'w'))
        ok = sum(1 for v in out.values() if v)
        print(f'{i+1}/{len(targets)} · resolved {ok}', flush=True)
json.dump(out, open('release_meta.json', 'w'))
ok = sum(1 for v in out.values() if v)
print(f'DONE · {ok}/{len(out)} releases resolved', flush=True)
